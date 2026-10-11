"""Lo que se lee de 'Config Q10.txt'."""
from dataclasses import dataclass

from core import archivos

# Lo demas del .txt son filtros de los informes
CLAVES_GENERALES = {"rol", "menu", "tipo", "submenu", "buscar", "accion", "informes", "formato"}

# Formatos que ofrece el visor de Q10 (los informes que descargan Excel directo lo ignoran)
FORMATOS = ("XLSX", "XLS", "PDF", "CSV", "DOC", "HTML", "IMAGEN")


@dataclass
class ConfigQ10:
    rol: str
    informes: list[str]
    filtros: list[tuple[str, list[str]]]  # [(nombre del filtro, [valores])] en el orden del .txt
    formato: str = "XLSX"                 # con que formato exportar desde el visor
    menu: str = "Informes"                # menu de la barra azul por donde entra el bot
    submenu: str = ""                     # ruta dentro de ese menu: "Nivel 1 > Nivel 2"
    buscar: str = ""                      # que escribir en el buscador de esa pantalla
    accion: str = ""                      # que hacer en esa pantalla (vacio = guardar la tabla)

    @classmethod
    def desde_txt(cls, datos):
        informes = archivos.separar_lista(datos.get("informes", ""))
        if not informes or archivos.es_plantilla(informes[0]):
            raise ValueError("Escribe en 'Informes' de Config Q10.txt los informes a descargar, separados por coma")
        formato = (datos.get("formato") or "XLSX").strip().upper()
        if formato not in FORMATOS:
            raise ValueError(f"'Formato : {formato}' no existe en Q10. Usa uno de: {', '.join(FORMATOS)}")
        # Los filtros vacios se saltan: no existen en el informe actual
        filtros = [(clave, archivos.separar_lista(valor))
                   for clave, valor in datos.items() if clave not in CLAVES_GENERALES and valor]
        # "Menu" o "Tipo": las dos valen, para que no haya que recordar cual era
        menu = (datos.get("menu") or datos.get("tipo") or "Informes").strip() or "Informes"
        return cls(rol=datos.get("rol") or "Administrativo", informes=informes, filtros=filtros,
                   formato=formato, menu=menu, submenu=(datos.get("submenu") or "").strip(),
                   buscar=(datos.get("buscar") or "").strip(),
                   accion=(datos.get("accion") or "").strip())
