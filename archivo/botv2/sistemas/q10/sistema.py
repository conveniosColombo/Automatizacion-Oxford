"""Q10: el orden de los pasos. Donde hacer clic esta en paginas.py y lo que pide el .txt en config.py."""
import re

from core.errores import resumen
from core.sistema import Sistema

from .config import ConfigQ10
from .paginas import LoginQ10


class Q10(Sistema):
    NOMBRE = "Q10"

    def leer_config(self, datos):
        return ConfigQ10.desde_txt(datos)

    def ejecutar(self):
        c = self.credenciales
        barra = LoginQ10(self.page).iniciar_sesion(c.link, c.usuario, c.clave, self.config.rol)
        print("Paso 1: sesion iniciada en Q10.")
        informes = barra.ir_a_informes()
        print("Paso 2: Informes abierto.")

        for nombre in self.config.informes:
            try:
                if not informes.esta_abierta():
                    informes = barra.ir_a_informes()  # volver a la lista despues del informe anterior
                formulario = informes.abrir_informe(nombre)
                print(f"Paso 3: informe '{nombre}' abierto.")
                self.llenar_y_exportar(formulario, nombre, self.config.filtros)
                print(f"Paso 4: informe '{nombre}' terminado.")
            except Exception as error:
                print(f"FALLO en el informe {nombre}: {resumen(error)}")

    def llenar_y_exportar(self, formulario, informe, filtros, etiquetas=(), aplicados=()):
        """Llena los filtros en orden y exporta. Si un filtro tiene varios valores (o "Todos"), exporta un
        reporte por cada valor.

        'aplicados' guarda los filtros que ya se pusieron (sede, programa, periodo...). Sirve porque
        cuando un valor sale vacio hay que darle a "Volver a generar", y Q10 devuelve el formulario
        en blanco: antes de seguir con el siguiente valor se vuelven a poner esos filtros.
        """
        if not filtros:
            archivo = self.guardar(formulario.exportar(), " ".join((informe, *etiquetas)))
            print(f"  Reporte guardado en {archivo}")
            return
        (nombre, valores), resto = filtros[0], filtros[1:]

        if [formulario.normalizar(v) for v in valores] in (["todos"], ["todas"]):
            opciones = formulario.opciones(nombre)
            if opciones is None:
                print(f"  Filtro '{nombre}' no existe en este informe; se salta.")
                return self.llenar_y_exportar(formulario, informe, resto, etiquetas, aplicados)

            print(f"  {nombre}: la lista trae {len(opciones)} opciones -> {opciones[:4]}")

            # Si la lista ya trae una opcion "Todos", se usa esa: un solo informe con todo,
            # en vez de pedir uno por cada valor. Se acepta escrita de varias formas:
            # "Todos", "TODAS", "-- Todos --", "Todos los cursos"...
            literal = next((o for o in opciones
                            if re.search(r"\btod[oa]s\b", formulario.normalizar(o))), None)
            if literal:
                print(f"  {nombre}: la lista tiene la opcion '{literal}', se usa esa")
                elegido = formulario.llenar(nombre, literal) or literal
                return self.llenar_y_exportar(formulario, informe, resto, (*etiquetas, elegido),
                                              (*aplicados, (nombre, elegido)))

            # En Q10 los filtros opcionales muestran "Todos" cuando estan vacios, pero eso no es
            # una opcion de la lista: la forma de pedir "todos" es no tocar el campo
            actual = formulario.valor_actual(nombre)
            if actual is not None and (not actual or re.search(r"\btod[oa]s\b",
                                                               formulario.normalizar(actual))):
                print(f"  {nombre}: el campo ya dice '{actual or 'vacio'}'; se deja asi "
                      f"(Q10 lo toma como todos)")
                return self.llenar_y_exportar(formulario, informe, resto, (*etiquetas, "Todos"),
                                              aplicados)

            valores = opciones
            print(f"  {nombre}: Todos ({len(valores)} opciones, una por una)")

        if len(valores) == 1:
            elegido = formulario.llenar(nombre, valores[0]) or valores[0]
            return self.llenar_y_exportar(formulario, informe, resto, etiquetas,
                                          (*aplicados, (nombre, elegido)))

        reponer_filtros = False
        for numero, valor in enumerate(valores, start=1):
            print(f"  --- {nombre} {numero} de {len(valores)} ---")
            try:
                if reponer_filtros:
                    print("  Vuelvo a poner los filtros")
                    for filtro, anterior in aplicados:
                        formulario.llenar(filtro, anterior)
                elegido = formulario.llenar(nombre, valor) or valor
                self.llenar_y_exportar(formulario, informe, resto, (*etiquetas, elegido),
                                       (*aplicados, (nombre, elegido)))
            except Exception as error:
                print(f"  FALLO con {nombre} '{valor}': {resumen(error)}")
            # Con datos o sin datos, el informe termina en "Volver a generar" y el formulario
            # queda en blanco, asi que antes del siguiente valor hay que reponer los filtros
            reponer_filtros = True
