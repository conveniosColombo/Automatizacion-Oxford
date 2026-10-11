"""Macmillan Education Everywhere: inicia sesion y abre cada libro y nivel del Config."""
from core.errores import resumen
from core.pagina import Pagina
from core.sistema import Sistema

from .config import ConfigMacmillan
from .paginas import InicioMacmillan


class Macmillan(Sistema):
    NOMBRE = "Macmillan"

    def leer_config(self, datos):
        return ConfigMacmillan.desde_txt(datos)

    def ejecutar(self):
        c = self.credenciales
        login = InicioMacmillan(self.page).abrir(c.link).ir_a_login()
        estanteria = login.iniciar_sesion(c.usuario, c.clave)
        print("Paso 1: sesion iniciada en Macmillan.")

        for nombre_libro in self.config.libros:
            try:
                libro = estanteria.abrir().abrir_libro(nombre_libro)
                print(f"Paso 2: libro '{nombre_libro}' abierto.")
                for nivel in self.niveles_de(libro):
                    try:
                        if nivel is not None:
                            libro.abrir_nivel(nivel)
                            print(f"Paso 3: nivel '{nivel}' abierto.")
                        app = libro.abrir_recurso(self.config.recurso)
                        print(f"Paso 4: '{self.config.recurso}' abierto.")
                        visor = app.ver_en_navegador()
                        print("Paso 5: contenido abierto en el navegador.")
                        visor.cerrar_aviso_sesion()
                        print("Paso 6: aviso de sesion cerrado, My library a la vista.")
                        visor.abrir_school_work()
                        print("Paso 7: School work desplegado.")
                        progreso = visor.abrir_progress()
                        print("Paso 8: Progress abierto.")
                        progreso.elegir_curso(nombre_libro, nivel)
                        curso = f"{nombre_libro} {nivel}" if nivel else nombre_libro
                        print(f"Paso 9: curso '{curso}' puesto en el filtro.")
                        progreso.presionar_go()
                        print("Paso 10: filtros aplicados con Go.")
                        self.recorrer_clases(progreso, curso)
                    except Exception as error:
                        print(f"  FALLO en el nivel {nivel}: {resumen(error)}")
            except Exception as error:
                print(f"FALLO en el libro {nombre_libro}: {resumen(error)}")

    def recorrer_clases(self, progreso, curso):
        """Recorre todas las paginas del listado y exporta el CSV de cada clase pedida en el Config."""
        pedidas = self.config.clases
        todas = [Pagina.normalizar(c) for c in pedidas] == ["todas"]
        paginas = progreso.total_paginas()
        print(f"  Paginas de clases: {paginas}")
        atendidas = []

        for pagina in range(1, paginas + 1):
            if pagina > 1:
                progreso.ir_a_pagina(pagina)
            en_pagina = progreso.clases()
            if not todas:
                en_pagina = [c for c in en_pagina
                             if any(Pagina.normalizar(p) == Pagina.normalizar(c) for p in pedidas)]
            print(f"  --- pagina {pagina} de {paginas}: {len(en_pagina)} clase(s) ---")

            for clase in en_pagina:
                try:
                    detalle = progreso.abrir_clase(clase)
                    print(f"Paso 11: clase '{clase}' abierta.")
                    archivo = self.guardar(detalle.exportar(), f"{curso} {clase}")
                    print(f"Paso 12: CSV guardado en {archivo}")
                    atendidas.append(clase)
                except Exception as error:
                    print(f"  FALLO en la clase {clase}: {resumen(error)}")
                progreso.volver_a_clases()
                if pagina > 1:
                    progreso.ir_a_pagina(pagina)  # al volver, el listado queda en la pagina 1

        if not atendidas:
            raise ValueError("No exporte ninguna clase: con estos filtros no aparecio ninguna en Progress. "
                             "Revisa el curso, el nivel y los desplegables del panel 'Go to'")
        if not todas:
            faltaron = [p for p in pedidas
                        if not any(Pagina.normalizar(p) == Pagina.normalizar(c) for c in atendidas)]
            if faltaron:
                print(f"  Aviso: no encontre estas clases en ninguna pagina: {faltaron}")

    def niveles_de(self, libro):
        """Los niveles del Config; "Todos" son todas las pestañas y, si no hay ninguno, [None]."""
        niveles = self.config.niveles
        if not niveles:
            return [None]  # el libro no tiene pestañas de nivel
        if [Pagina.normalizar(n) for n in niveles] == ["todos"]:
            niveles = libro.niveles()
            print(f"  Niveles: Todos ({len(niveles)} pestañas)")
        return niveles
