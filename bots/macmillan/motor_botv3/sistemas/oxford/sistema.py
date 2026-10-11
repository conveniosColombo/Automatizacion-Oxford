"""Oxford English Hub: el orden de los pasos. Donde hacer clic esta en paginas.py y lo que pide el .txt en config.py."""
from core.errores import resumen
from core.pagina import Pagina
from core.sistema import Sistema

from .config import ConfigOxford
from .paginas import InicioOxford


class Oxford(Sistema):
    NOMBRE = "Oxford"

    def leer_config(self, datos):
        return ConfigOxford.desde_txt(datos)

    def ejecutar(self):
        c, config = self.credenciales, self.config

        menu = InicioOxford(self.page).iniciar_sesion(c.link, c.usuario, c.clave)
        print("Paso 1: sesion iniciada.")
        menu.abrir()
        print("Paso 2: menu de la cuenta abierto.")
        ventana = menu.ver_mas_organizaciones()
        print("Paso 3: clic en '+ more', lista de convenios abierta.")
        lateral = ventana.seleccionar(config.id_organizacion)
        print(f"Paso 4: curso con ID '{config.id_organizacion}' abierto.")
        organizacion = lateral.ir_a_mi_organizacion()
        print("Paso 5: My Organization abierto.")
        organizacion.abrir_clases()
        print("Paso 6: Classes abierto.")

        clases = self.clases_a_descargar(organizacion)
        bajadas, fallidas = [], []

        for numero, clase in enumerate(clases, start=1):
            print(f"  --- clase {numero} de {len(clases)}: {clase} ---")
            try:
                pagina_clase = organizacion.abrir_clase(clase)
                print(f"Paso 7: clase '{clase}' abierta.")
                progreso = pagina_clase.abrir_progreso()
                print("Paso 8a: Progress abierto.")
                progreso.abrir_curso_con_avance()
                print("Paso 8b: curso con porcentaje de avance abierto.")
                progreso.aplicar_ajustes(config.scores, config.figuras, config.puntajes)
                print("Paso 9-11: Progress settings aplicado y cerrado.")
                archivo = self.guardar(progreso.descargar_csv(), clase)
                print(f"Paso 12: CSV guardado en {archivo}")
                bajadas.append(archivo)
            except Exception as error:
                mensaje = resumen(error)
                print(f"FALLO en la clase {clase}: {mensaje}")
                fallidas.append((clase, mensaje))

        self.resumen_final(len(clases), bajadas, fallidas)

    def clases_a_descargar(self, organizacion):
        """Las clases del Config. Con "Todos" (o "Todas") se bajan todas las que tenga la lista."""
        pedidas = self.config.clases
        if [Pagina.normalizar(c) for c in pedidas] not in (["todos"], ["todas"]):
            return pedidas

        clases = organizacion.clases()
        if not clases:
            raise ValueError("Pedi todas las clases pero la lista de Classes no devolvio ninguna. "
                             "Revisa que el ID del convenio sea el correcto")
        print(f"  Clases: Todos ({len(clases)} en la lista)")
        for nombre in clases:
            print(f"    - {nombre}")
        return clases

    @staticmethod
    def resumen_final(total, bajadas, fallidas):
        """Cuenta al final: con "Todos" son muchas clases y hay que ver de una que falto y por que."""
        print(f"  Resumen: {len(bajadas)} de {total} clase(s) descargada(s)")
        for archivo in bajadas:
            print(f"    OK    {getattr(archivo, 'name', archivo)}")
        for clase, error in fallidas:
            print(f"    FALLO {clase}: {error}")
