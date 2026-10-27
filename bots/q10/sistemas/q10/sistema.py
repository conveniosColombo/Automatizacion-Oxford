"""Q10: el orden de los pasos. Donde hacer clic esta en paginas.py y lo que pide la planilla en config.py."""
import re

from core import archivos
from core.errores import resumen
from core.sistema import Sistema

from .config import ConfigQ10
from .paginas import LoginQ10, PaginaCursoVirtual, PaginaListado


class Q10(Sistema):
    NOMBRE = "Q10"
    SIN_DATOS = "Sin resultados"
    bajados, sin_datos, fallidos = [], [], []  # se reinician en cada informe
    # Avance de TODA la ejecucion, para que la interfaz diga "X de Y reportes". El total crece a
    # medida que se descubren listas con varios valores (Todos / varios periodos / cursos).
    total = hechos = 0

    def avance(self, hechos=0, total=0):
        """Suma al avance y lo informa en una linea que la interfaz lee (y no muestra)."""
        self.hechos += hechos
        self.total += total
        print(f"[[PROGRESO]] {self.hechos} {self.total}", flush=True)

    def leer_config(self, datos):
        return ConfigQ10.desde_hoja(datos)

    def guardar(self, descarga, prefijo):
        """Con 'Ubicación destino' en los Ajustes se guarda ahi; si no, en Descargas/Q10."""
        destino = getattr(self.config, "destino", "")
        if not destino:
            return super().guardar(descarga, prefijo)
        from datetime import datetime
        from pathlib import Path
        extension = Path(descarga.suggested_filename).suffix
        ruta = Path(destino) / f"{datetime.now():%Y-%m-%d_%H%M}_{archivos.nombre_archivo(prefijo)}{extension}"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        descarga.save_as(ruta)
        return ruta

    def ejecutar(self):
        c = self.credenciales
        self.barra = LoginQ10(self.page).iniciar_sesion(c.link, c.usuario, c.clave, self.config.rol)
        print("Paso 1: sesion iniciada en Q10.")
        menu = getattr(self.config, "menu", "Informes")
        pantalla = self.barra.ir_a(menu, getattr(self.config, "submenu", ""))
        print(f"Paso 2: {menu} abierto.")

        # Las pantallas de listado (buscador + tabla) no bajan informes: se guarda la tabla
        if isinstance(pantalla, PaginaListado):
            return self.guardar_listado(pantalla, menu)
        informes = pantalla

        self.total = self.hechos = 0
        for nombre in self.config.informes:
            self.bajados, self.sin_datos, self.fallidos = [], [], []
            self.avance(total=1)           # cada informe cuenta 1 hasta descubrir cuantos valores trae
            try:
                if not informes.esta_abierta():
                    informes = self.barra.ir_a_informes()  # volver a la lista despues del anterior
                formulario = informes.abrir_informe(nombre)
                print(f"Paso 3: informe '{nombre}' abierto.")
                self.llenar_y_exportar(formulario, nombre, self.config.filtros_para(nombre))
                print(f"Paso 4: informe '{nombre}' terminado.")
            except Exception as error:
                print(f"FALLO en el informe {nombre}: {resumen(error)}")
            self.resumen_del_informe(nombre)
            # Un informe que fallo antes de terminar deja reportes sin intentar: ya no se esperan
            self.avance(hechos=self.total - self.hechos)

    def guardar_listado(self, pantalla, menu):
        """Busca lo que diga el Config y, segun 'Accion', guarda la tabla o entra a cada curso."""
        buscado = getattr(self.config, "buscar", "")
        if buscado:
            pantalla.buscar(buscado)
        else:
            print("  Sin 'Buscar' en el Config: se toma la lista completa")

        if "usuario" in pantalla.normalizar(getattr(self.config, "accion", "")):
            return self.exportar_usuarios(pantalla)

        encabezados, filas = pantalla.todas_las_filas()
        if not filas:
            print("  La busqueda no devolvio ninguna fila; no se guarda nada.")
            return

        nombre = " ".join(x for x in (getattr(self.config, "submenu", "").split(">")[-1].strip()
                                      or menu, buscado) if x)
        archivo = archivos.guardar_tabla(encabezados, filas, self.NOMBRE, nombre,
                                         getattr(self.config, "destino", ""))
        print(f"Paso 3: {len(filas)} fila(s) guardadas en {archivo}")

    def exportar_usuarios(self, pantalla, max_paginas=500):
        """Baja los usuarios de cada curso de la lista filtrada.

        Primero se recogen las direcciones de TODOS los cursos del filtro, en una sola pasada
        por la paginacion. Despues se entra a cada uno por su direccion: asi las descargas ya
        no dependen de que Q10 conserve el filtro ni de en que pagina quedo la lista.
        """
        self.bajados, self.sin_datos, self.fallidos = [], [], []
        curso_abierto = PaginaCursoVirtual(self.page)
        formato = getattr(self.config, "formato", "XLSX")
        buscado = getattr(self.config, "buscar", "")

        if buscado and not pantalla.preparar_pagina(1, buscado):
            print("  No pude dejar la lista filtrada; no se baja nada para no equivocarse.")
            return
        cursos = pantalla.todos_los_cursos(max_paginas)
        if not cursos:
            print("  La lista no trae cursos con enlace; no hay a donde entrar.")
            return
        print(f"Paso 3: {len(cursos)} curso(s) para exportar")
        self.total = self.hechos = 0
        self.avance(total=len(cursos))

        for numero, curso in enumerate(cursos, start=1):
            nombre = curso["nombre"]
            print(f"  {numero} de {len(cursos)}: {nombre}")
            try:
                curso_abierto.abrir(curso["href"])
                if curso_abierto.cuantos_usuarios() == 0:
                    # Sin usuarios no hay archivo: se evita esperar una descarga que no llega
                    print("  El curso no tiene usuarios; se salta.")
                    self.sin_datos.append(nombre)
                    continue
                curso_abierto.ir_a_usuarios()
                if curso_abierto.sin_usuarios():
                    # Lo dice la propia pantalla: no hay nada que exportar, no se espera en vano
                    print("  El curso no tiene usuarios registrados; se salta.")
                    self.sin_datos.append(nombre)
                    continue
                archivo = self.guardar(curso_abierto.exportar(formato), f"Usuarios {nombre}")
                print(f"  Guardado en {archivo.name}")
                self.bajados.append(archivo)
            except Exception as error:
                mensaje = resumen(error)
                print(f"  FALLO con '{nombre}': {mensaje}")
                self.fallidos.append((nombre, mensaje))
            finally:
                self.avance(hechos=1)
                # Se sale del curso como lo haria una persona. No hace falta volver a filtrar:
                # las direcciones ya estan recogidas y el curso se abre por la suya.
                curso_abierto.volver_a_cursos()

        self.resumen_del_informe("Usuarios de los cursos")

    def resumen_del_informe(self, informe):
        """Cuenta al final del informe: asi se ve si un valor del Config no bajo y por que."""
        print(f"  Resumen de '{informe}': {len(self.bajados)} archivo(s) descargado(s)")
        for archivo in self.bajados:
            print(f"    OK        {getattr(archivo, 'name', archivo)}")
        for etiqueta in self.sin_datos:
            print(f"    SIN DATOS {etiqueta}")
        for etiqueta, error in self.fallidos:
            print(f"    FALLO     {etiqueta}: {error}")

    def reabrir(self, informe, formulario):
        """Vuelve a abrir el informe cuando la pantalla no quedo lista para otro reporte.

        Si no se puede, se sigue con el formulario que hay: es mejor intentarlo que perder el valor.
        """
        barra = getattr(self, "barra", None)
        if barra is None:
            return formulario
        print("  La pantalla no quedo lista para otro reporte; vuelvo a abrir el informe")
        try:
            return barra.ir_a_informes().abrir_informe(informe)
        except Exception as error:
            print(f"  No pude reabrirlo ({resumen(error)}); sigo con la pantalla actual")
            return formulario

    def guardar_reporte(self, descarga, informe, etiquetas):
        prefijo = " ".join((informe, *etiquetas))
        destino = self.config.destino_para(informe)
        if destino:
            from datetime import datetime
            from pathlib import Path
            from core.archivos import nombre_archivo
            extension = Path(descarga.suggested_filename).suffix
            ruta = Path(destino) / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre_archivo(prefijo)}{extension}"
            ruta.parent.mkdir(parents=True, exist_ok=True)
            descarga.save_as(ruta)
            return ruta
        return self.guardar(descarga, prefijo)

    def llenar_y_exportar(self, formulario, informe, filtros, etiquetas=(), aplicados=()):
        """Llena los filtros en orden y exporta. Si un filtro tiene varios valores (o "Todos"), exporta un
        reporte por cada valor.

        'aplicados' guarda los filtros que ya se pusieron (sede, programa, periodo...). Sirve porque
        cuando un valor sale vacio hay que darle a "Volver a generar", y Q10 devuelve el formulario
        en blanco: antes de seguir con el siguiente valor se vuelven a poner esos filtros.
        """
        if not filtros:
            # 'informe' no cambia en toda la recursion: sirve para saber si "Configurar Q10"
            # le puso a ESTE informe un formato distinto del general (formato_para lo resuelve)
            descarga = formulario.exportar(formato=self.config.formato_para(informe))
            archivo = self.guardar_reporte(descarga, informe, etiquetas)
            print(f"  Reporte guardado en {archivo}")
            self.bajados.append(archivo)
            self.avance(hechos=1)
            return
        (nombre, valores), resto = filtros[0], filtros[1:]

        if [formulario.normalizar(v) for v in valores] in (["todos"], ["todas"]):
            opciones = formulario.opciones(nombre)
            if opciones is None:
                # No es una lista. Si igual existe (casillas "Campos", radios "Estado", un
                # interruptor), el propio formulario sabe que hacer con "Todos".
                if formulario.existe(nombre):
                    elegido = formulario.llenar(nombre, valores[0]) or valores[0]
                    return self.llenar_y_exportar(formulario, informe, resto, etiquetas,
                                                  (*aplicados, (nombre, elegido)))
                print(f"  Filtro '{nombre}' no existe en este informe; se salta.")
                return self.llenar_y_exportar(formulario, informe, resto, etiquetas, aplicados)

            if not opciones:
                # Lista sin opciones propias: Q10 la toma como "todos" si no se toca
                print(f"  {nombre}: la lista no trae opciones; se deja como esta "
                      f"('{formulario.valor_actual(nombre) or 'Todos'}')")
                return self.llenar_y_exportar(formulario, informe, resto, (*etiquetas, "Todos"),
                                              aplicados)

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

        self.avance(total=len(valores) - 1)     # este valor ya contaba como 1 reporte
        reponer_filtros = fallo_anterior = False
        for numero, valor in enumerate(valores, start=1):
            print(f"  --- {nombre} {numero} de {len(valores)} ---")
            try:
                if reponer_filtros:
                    # Se reabre el informe si el valor anterior fallo, si el formulario ya no esta,
                    # o si el boton quedo bloqueado por el informe anterior: asi el siguiente
                    # valor empieza siempre en una pantalla limpia
                    reabierto = False
                    if (fallo_anterior or not formulario.existe(nombre)
                            or not formulario.listo_para_otro_informe()):
                        nuevo = self.reabrir(informe, formulario)
                        reabierto, formulario = nuevo is not formulario, nuevo
                    # Si el formulario conserva los filtros de antes, solo se cambia este
                    if reabierto or not self.filtros_intactos(formulario, aplicados):
                        print("  Vuelvo a poner los filtros")
                        for filtro, anterior in aplicados:
                            formulario.llenar(filtro, anterior)
                    else:
                        print(f"  Los demas filtros siguen puestos; solo cambio {nombre}")
                elegido = formulario.llenar(nombre, valor) or valor
                self.llenar_y_exportar(formulario, informe, resto, (*etiquetas, elegido),
                                       (*aplicados, (nombre, elegido)))
                fallo_anterior = False
            except Exception as error:
                fallo_anterior = True
                self.avance(hechos=1)
                mensaje = resumen(error)
                print(f"  FALLO con {nombre} '{valor}': {mensaje}")
                etiqueta = " ".join((*etiquetas, valor))
                if self.SIN_DATOS in mensaje:
                    self.sin_datos.append(etiqueta)
                else:
                    self.fallidos.append((etiqueta, mensaje))
            # Con datos o sin datos, el informe termina en "Volver a generar": antes del siguiente
            # valor se revisa si el formulario conservo los filtros o hay que reponerlos
            reponer_filtros = True

    @staticmethod
    def filtros_intactos(formulario, aplicados):
        """True si las listas ya puestas (Sede, Programa, Periodo...) siguen con su valor.

        Solo se pueden revisar las listas desplegables. Si todas siguen iguales, el formulario no
        se borro y los demas filtros (fechas, interruptores) tambien siguen: no se tocan.
        """
        revisados = 0
        for filtro, anterior in aplicados:
            try:
                actual = formulario.valor_actual(filtro)
            except Exception:
                return False
            if actual is None:
                continue                      # no es una lista: no se puede revisar
            if formulario.normalizar(actual) != formulario.normalizar(str(anterior)):
                return False
            revisados += 1
        # Sin ninguna lista para comprobar no hay como saberlo: mejor reponer
        return revisados > 0 or not aplicados
