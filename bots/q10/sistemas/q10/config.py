"""Lo que se lee de la hoja 'Q10' de la planilla."""
from dataclasses import dataclass, field

from core import archivos

# Lo demas de la hoja son filtros de los informes ("_pares" lo agrega Planilla.leer_hoja,
# no es un ajuste: son los filtros crudos, con su columna Informe, para agrupar por informe)
CLAVES_GENERALES = {"rol", "menu", "tipo", "submenu", "buscar", "accion", "informes", "formato", "_pares"}

# Formatos que ofrece el visor de Q10 (los informes que descargan Excel directo lo ignoran)
FORMATOS = ("XLSX", "XLS", "PDF", "CSV", "DOC", "HTML", "IMAGEN")


@dataclass
class ConfigQ10:
    rol: str
    informes: list[str]
    filtros: list[tuple[str, list[str]]]  # [(nombre del filtro, [valores])], aplican a TODOS los informes
    formato: str = "XLSX"                 # con que formato exportar desde el visor, por defecto
    menu: str = "Informes"                # menu de la barra azul por donde entra el bot
    submenu: str = ""                     # ruta dentro de ese menu: "Nivel 1 > Nivel 2"
    buscar: str = ""                      # que escribir en el buscador de esa pantalla
    accion: str = ""                      # que hacer en esa pantalla (vacio = guardar la tabla)
    # {informe en minuscula: [(nombre del filtro, [valores])]}: filtros que SOLO aplican a ese
    # informe (columna "Informe" de la tabla de Filtros). Los escribe sobre todo "Configurar Q10".
    filtros_por_informe: dict = field(default_factory=dict)

    @classmethod
    def desde_hoja(cls, datos):
        informes = archivos.separar_lista(datos.get("informes", ""))
        if not informes and (datos.get("menu") or "Informes").strip().lower() == "informes":
            raise ValueError("Escribe en la tabla 'Informe' de la hoja Q10 al menos un informe con Usar = Sí")
        formato = (datos.get("formato") or "XLSX").strip().upper()
        if formato not in FORMATOS:
            raise ValueError(f"El Formato '{formato}' no existe en Q10. Usa uno de: {', '.join(FORMATOS)}")
        # Los filtros vacios se saltan: no existen en el informe actual
        filtros = [(clave, archivos.separar_lista(valor))
                   for clave, valor in datos.items() if clave not in CLAVES_GENERALES and valor]

        filtros_por_informe: dict[str, list] = {}
        for informe_fila, nombre_filtro, valor in datos.get("_pares", []):
            if informe_fila:          # sin informe = filtro general, ya esta en 'filtros'
                filtros_por_informe.setdefault(informe_fila.lower(), []).append(
                    (nombre_filtro, archivos.separar_lista(valor)))

        # "Menu" o "Tipo": las dos valen, para que no haya que recordar cual era
        menu = (datos.get("menu") or datos.get("tipo") or "Informes").strip() or "Informes"
        return cls(rol=datos.get("rol") or "Administrativo", informes=informes, filtros=filtros,
                   formato=formato, menu=menu, submenu=(datos.get("submenu") or "").strip(),
                   buscar=(datos.get("buscar") or "").strip(),
                   accion=(datos.get("accion") or "").strip(),
                   filtros_por_informe=filtros_por_informe)

    def filtros_para(self, informe: str) -> list[tuple[str, list[str]]]:
        """Los filtros generales + los propios de ESTE informe (si tiene), en orden.

        La fila 'Formato' no es un filtro de la pantalla: es el formato de salida solo para
        ese informe, y se procesa aparte (vease formato_para).
        """
        propios = [(nombre, valores) for nombre, valores
                  in self.filtros_por_informe.get(informe.strip().lower(), [])
                  if nombre.strip().lower() not in ("formato", "destino")]
        return [*self.filtros, *propios]

    def destino_para(self, informe: str) -> str | None:
        """La carpeta de destino personalizada de ESTE informe, si se configuro."""
        for nombre, valores in self.filtros_por_informe.get(informe.strip().lower(), []):
            if nombre.strip().lower() == "destino" and valores:
                return valores[0].strip()
        return None

    def formato_para(self, informe: str) -> str:
        """El formato de ESTE informe, si "Configurar Q10" le puso uno distinto; si no, el general."""
        for nombre, valores in self.filtros_por_informe.get(informe.strip().lower(), []):
            if nombre.strip().lower() == "formato" and valores:
                candidato = valores[0].strip().upper()
                if candidato in FORMATOS:
                    return candidato
        return self.formato
