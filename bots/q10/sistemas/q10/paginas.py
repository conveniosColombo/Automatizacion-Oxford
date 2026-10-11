"""Page Objects de Q10 (v5).

Hecho con el relevamiento de los 71 informes del menu Informes. Lo que hay que saber:

  - Los informes son enlaces 'a.reportes' con 'data-href="/Reporte/<Area>/<Nombre>"'. Al hacer clic
    el formulario se inyecta por AJAX EN LA MISMA URL (tarda hasta ~3 s): se espera #formReportes
    o #form0, nunca un tiempo fijo. En el Config se puede escribir el nombre, "Nombre (Seccion)"
    cuando se repite, o la direccion del informe (ListadoCursos), que es lo mas estable.
  - Segun como entregan el resultado hay cuatro familias:
      A  visor PDF en una ventana (#master-modal > iframe#report). Se exporta con la lista
         'select#exportSelect' (PDF, XLSX, XLS, DOC, HTML, CSV, Imagen) y se cierra con #close.
      B  tarea en segundo plano (#programar-reporte-btn): "Generando reporte" -> "El reporte se ha
         generado exitosamente" + "Abrir reporte" + "Volver a generar".
      C  descarga directa del Excel (#generar-reporte-btn en form0 / rutas /Reportes/Excel/).
      D  resultado pintado en la pantalla (/ReportePantalla/): no genera archivo.
    exportar() vigila A, B y C al mismo tiempo porque varios informes no dicen cual usan.
  - Los filtros no son solo listas: hay listas simples y multiples, radios, interruptores, grupos
    de casillas, rangos de fechas (con presets) y autocompletados de personas.
"""
import re
import time
from urllib.parse import urljoin

from playwright.sync_api import expect

from core.pagina import Pagina


class LoginQ10(Pagina):
    """Ingreso: usuario -> Siguiente -> contrasena -> Ingresar -> ventana "Seleccione el rol"."""
    USUARIO = "#form-username"
    CLAVE = "#form-password"
    BOTON = "#btn-submit-login"          # dice "Siguiente" y despues "Ingresar"
    CAPTCHA = "#login-form-captcha"      # verificacion de Cloudflare: la resuelve una persona
    MENSAJES = "#login-form-messages"    # errores como clave incorrecta
    ROLES = "#roles a.list-group-item"   # opciones de la ventana de rol

    def iniciar_sesion(self, link, usuario, clave, rol):
        self.page.goto(link)
        self.page.locator(self.USUARIO).fill(usuario)
        self.page.locator(self.BOTON).click()

        # El campo de la contrasena ya existe pero oculto: esperar a que se muestre
        campo_clave = self.page.locator(self.CLAVE)
        expect(campo_clave).to_be_visible(timeout=15_000)
        campo_clave.fill(clave)
        self._esperar_captcha()
        self.page.locator(self.BOTON).click()

        self._elegir_rol(rol)
        return BarraQ10(self.page)

    def _esperar_captcha(self):
        if self.page.locator(self.CAPTCHA).is_visible():
            input("  Q10 pide verificacion de seguridad: resuelvela en el navegador y presiona Enter aqui...")

    def _elegir_rol(self, rol):
        opciones = self.page.locator(self.ROLES)
        opcion = opciones.filter(has_text=self.texto_exacto(rol))
        try:
            expect(opcion).to_be_visible(timeout=30_000)
        except AssertionError:
            if "/user/login" not in self.page.url.lower():
                return  # la cuenta tiene un solo rol y entro directo
            if opciones.count():
                raise ValueError(f"No existe el rol '{rol}'. Opciones: {opciones.all_inner_texts()}")
            mensaje = self.page.locator(self.MENSAJES).inner_text().strip()
            raise ValueError("No pude iniciar sesion en Q10" + (f": {mensaje}" if mensaje else ""))
        print(f"  Rol: {rol}")
        opcion.click()
        self.page.wait_for_url(lambda url: "/user/login" not in url.lower(), timeout=60_000)
        self.page.wait_for_load_state()


class BarraQ10(Pagina):
    """Barra superior azul (Institucional, Academico, Tesoreria, Informes)."""
    # Se usa el enlace y no la URL: tras el login Q10 cambia de servidor (site2 -> site3)
    BARRA = "nav.q10navbar"
    INFORMES = "nav.q10navbar a[href='/Informes']"
    OPCIONES = "nav.q10navbar .dropdown-menu a:visible, nav.q10navbar ul ul a:visible"

    def menus(self):
        """Los nombres que se ven en la barra azul."""
        try:
            return [" ".join(t.split()) for t in
                    self.page.locator(f"{self.BARRA} a:visible").all_inner_texts() if t.strip()]
        except Exception:
            return []

    def opciones_a_la_vista(self):
        """Lo que se ve ahora mismo en el menu desplegado."""
        try:
            return [" ".join(t.split()) for t in
                    self.page.locator(self.OPCIONES).all_inner_texts() if t.strip()]
        except Exception:
            return []

    def ir_a(self, menu="Informes", submenu=""):
        """Entra al menu (y submenu) que diga el Config.

        'Submenu' es una ruta separada por '>', porque los menus de Q10 tienen varios niveles:
            Submenu : Educacion virtual v2 > Cursos virtuales
        Hoy solo 'Informes' tiene acciones programadas; con los demas el bot navega, deja una
        captura y avisa donde quedo, que es lo que hace falta para programarlos.
        """
        if self.normalizar(menu) in ("informes", ""):
            return self.ir_a_informes()

        enlace = self.page.locator(self.BARRA).get_by_role(
            "link", name=self.texto_exacto(menu)).first
        if not enlace.count():
            raise ValueError(f"El menu '{menu}' no esta en la barra de Q10. "
                             f"Hay: {self.menus()[:8]}")
        print(f"  Abro el menu '{menu}' de la barra")
        enlace.click()
        self.esperar(1_500)

        pasos = [paso.strip() for paso in str(submenu).split(">") if paso.strip()]
        if not pasos:
            raise ValueError(f"Falta decir que opcion abrir de '{menu}'. En la hoja Q10 de la planilla:\n"
                             f"    Submenú = <opcion>\n"
                             f"  Opciones de '{menu}': {self.opciones_a_la_vista()}")

        for numero, paso in enumerate(pasos, start=1):
            opcion = self.page.locator(self.OPCIONES).filter(
                has_text=self.texto_exacto(paso)).first
            if not opcion.count():
                raise ValueError(f"'{paso}' no esta en ese menu. "
                                 f"Hay: {self.opciones_a_la_vista()}")
            print(f"  Clic en: {paso}")
            if numero == len(pasos):
                opcion.click()
                break
            # Los niveles del medio se abren al pasar el mouse; si no, con clic
            opcion.hover()
            self.esperar(1_000)
            if pasos[numero] not in self.opciones_a_la_vista():
                opcion.click()
                self.esperar(1_000)

        self.page.wait_for_load_state()
        self.esperar(2_000)

        # Las pantallas de listado (buscador + tabla) el bot ya sabe manejarlas
        listado = PaginaListado(self.page)
        if listado.es_listado():
            print(f"  Pantalla de listado: {self.page.url}")
            return listado

        ruta = self.captura(f"menu_{menu}_{pasos[-1]}.png".replace(" ", "_"))
        raise ValueError(f"Llegue a {self.page.url} pero esa pantalla todavia no tiene acciones "
                         f"programadas en el bot. Dejo una captura en {ruta.name} para saber "
                         f"que hay que programar.")

    def ir_a_informes(self):
        """Vuelve al menu de informes.

        Ojo: el formulario de un informe se inyecta dentro de /Informes, asi que estar en esa
        direccion no significa ver el menu. Si el clic no lo trae de vuelta, se entra directo.
        """
        try:
            enlace = self.page.locator(self.INFORMES).first
            if not enlace.is_visible():
                # Ahora "Informes" es un desplegable y /Informes es su opcion "Generales"
                self.page.locator(self.BARRA).locator("a.dropdown-toggle").filter(
                    has_text=self.texto_exacto("Informes")).first.click(timeout=5_000)
                self.esperar(500)
            enlace.click(timeout=8_000)
            self.page.wait_for_url(re.compile(r"/Informes", re.I))
            self.page.wait_for_load_state()
        except Exception as error:
            # El visor de un informe puede estar tapando la barra azul
            print(f"  No pude usar el boton Informes de la barra ({type(error).__name__})")
        informes = PaginaInformes(self.page)
        if not informes.esperar_lista(segundos=10):
            destino = re.sub(r"(https?://[^/]+).*", r"\1/Informes", self.page.url)
            print(f"  El menu no volvio con el clic; entro directo a {destino}")
            self.page.goto(destino)
            self.page.wait_for_load_state()
            informes.esperar_lista()
        return informes


class PaginaListado(Pagina):
    """Pantallas con buscador y tabla, como Academico > Educacion virtual v2 > Cursos virtuales.

    No tienen boton de exportar: el archivo lo arma el bot leyendo la tabla, pagina por pagina.
    La busqueda es AJAX (data-ajax-update="#resultsDiv"), asi que no hay que esperar una recarga
    de la pagina sino a que cambie la tabla.
    """
    FORMULARIO = "#filters_form"
    # Ojo: NO vale un selector suelto por placeholder. La barra azul de Q10 tiene su propio
    # "Buscar personas...", que esta antes en la pagina, y el bot escribiria ahi.
    BUSCADOR = "#texto"
    BUSCADOR_ALTERNO = "input[type='text']:visible, input:not([type]):visible"
    BOTON_BUSCAR = ".input-group-btn button, .input-group-btn a, button[type='submit']"
    RESULTADOS = "#resultsDiv"
    TABLA = "#resultsDiv table, table"
    SIGUIENTE = re.compile(r"^\s*(»|>>|siguiente)\s*$", re.I)
    PAGINACION = ".pagination"
    TOTAL = "#TotalResultados"          # Q10 deja ahi cuantos resultados dio la busqueda
    # Solo el enlace del NOMBRE, que esta en la primera celda. En la columna "Acciones" hay
    # otro enlace al mismo /Detalle (el ojito), sin texto: contarlo duplicaba los cursos y
    # dejaba descargas con el nombre vacio.
    ENLACE_CURSO = "tbody tr td:first-child a[href*='/Detalle']"
    NUMERO_PAGINA = "a.numberPagination"

    def es_listado(self):
        """Si esta pantalla tiene buscador y tabla, el bot sabe que hacer con ella."""
        try:
            return bool(self.page.locator(self.FORMULARIO).count()
                        and self.page.locator(self.TABLA).count())
        except Exception:
            return False

    def campo_de_busqueda(self):
        """El buscador DE LA PANTALLA ('Buscar cursos virtuales...'), nunca el de la barra azul."""
        campo = self.page.locator(self.BUSCADOR).first
        if campo.count():
            return campo
        # Si algun dia cambia el id, se busca dentro del formulario de filtros, no en toda la pagina
        dentro = self.page.locator(self.FORMULARIO).first.locator(self.BUSCADOR_ALTERNO).first
        return dentro if dentro.count() else None

    def buscar(self, texto):
        """Escribe en el buscador y espera a que la tabla se rearme."""
        campo = self.campo_de_busqueda()
        if campo is None:
            print("  Esta pantalla no tiene buscador; se salta la busqueda.")
            return None
        antes = self.primera_fila()
        try:
            campo.fill(str(texto), timeout=10_000)
        except Exception as error:
            # Mejor avisar y dejar que quien llama decida, que colgarse esperando el buscador
            print(f"  No pude escribir en el buscador ({type(error).__name__})")
            return None
        print(f"  Buscar: {texto}")

        boton = self.page.locator(self.FORMULARIO).locator(self.BOTON_BUSCAR).first
        if boton.count() and boton.is_visible():
            boton.click()
        else:
            campo.press("Enter")
        self.esperar_tabla(antes)
        return texto

    def esperar_tabla(self, era_antes="", segundos=30):
        """Espera a que la tabla cambie (o a que la red se calme, si la busqueda no cambio nada)."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=segundos * 1_000)
        except Exception:
            pass
        limite = time.monotonic() + 5
        while time.monotonic() < limite and self.primera_fila() == era_antes:
            self.page.wait_for_timeout(500)

    def primera_fila(self):
        """Texto de la primera fila: sirve para saber si la tabla ya cambio."""
        try:
            fila = self.page.locator(self.TABLA).first.locator("tbody tr").first
            return " ".join(fila.inner_text().split()) if fila.count() else ""
        except Exception:
            return ""

    def cursos_de_la_pagina(self):
        """Los cursos de la tabla que se ve ahora: su nombre y su direccion.

        Se encadenan los localizadores en vez de pegar los selectores con un espacio: TABLA
        lleva una coma y al juntarlos la coma partiria el selector en dos.
        """
        enlaces = self.page.locator(self.TABLA).first.locator(self.ENLACE_CURSO)
        if not enlaces.count():
            return []
        cursos = enlaces.evaluate_all("""enlaces => enlaces.map(e => ({
            nombre: (e.innerText || '').replace(/\\s+/g, ' ').trim(),
            href: e.getAttribute('href')}))""")
        # Sin nombre no es el enlace del curso sino un icono de la fila
        return [c for c in cursos if c["href"] and c["nombre"]]

    def hay_siguiente(self):
        """Si la paginacion todavia ofrece una pagina mas."""
        return self.boton_siguiente() is not None

    def total_resultados(self):
        """Cuantos resultados dice Q10 que dio la busqueda (0 si no lo publica)."""
        campo = self.page.locator(self.TOTAL).first
        try:
            return int(campo.input_value()) if campo.count() else 0
        except (ValueError, AttributeError, Exception):
            return 0

    def todos_los_cursos(self, max_paginas=500):
        """Recorre la lista UNA sola vez y devuelve todos los cursos: nombre y direccion.

        Se hace en una pasada porque la lista puede tener decenas de paginas: volver a
        recorrerla por cada curso seria lentisimo, y cualquier tropiezo dejaria cursos sin bajar.
        Despues se entra a cada curso por su direccion, sin depender ya de la lista.
        """
        cursos, vistos = [], set()
        total = self.total_resultados()
        if total:
            print(f"  Q10 dice que la busqueda tiene {total} resultado(s)")

        for vuelta in range(1, max_paginas + 1):
            nuevos = [c for c in self.cursos_de_la_pagina() if c["href"] not in vistos]
            vistos.update(c["href"] for c in nuevos)
            cursos.extend(nuevos)
            print(f"  pagina {self.pagina_actual() or vuelta}: {len(nuevos)} curso(s)"
                  f"   (van {len(cursos)}{f' de {total}' if total else ''})")
            if total and len(cursos) >= total:
                break
            # Un tropiezo de la pagina no puede dar la lista por terminada: se reintenta
            if not (self.ir_a_siguiente_pagina() or self.ir_a_siguiente_pagina()):
                break

        if total and len(cursos) < total:
            print(f"  OJO: Q10 dice {total} resultados y solo pude recoger {len(cursos)}")
        return cursos

    def pagina_actual(self):
        """El numero de pagina que la paginacion muestra como activa, o None."""
        activa = self.page.locator(f"{self.PAGINACION} li.active a, {self.PAGINACION} .active").first
        try:
            if activa.count():
                texto = activa.inner_text().strip()
                return int(texto) if texto.isdigit() else None
        except Exception:
            pass
        return None

    def clic_en_paginacion(self, enlace, destino=None, segundos=25):
        """Hace clic en la paginacion y no sigue hasta confirmar que la lista cambio.

        Se mira el numero de pagina activo, no un tiempo de espera: si se leyera la tabla antes
        de que termine el AJAX, se estaria leyendo la pagina anterior.
        """
        pagina_antes, fila_antes = self.pagina_actual(), self.primera_fila()
        enlace.click()
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            self.page.wait_for_timeout(300)
            ahora = self.pagina_actual()
            if destino is not None and ahora == destino:
                return True
            if destino is None and ahora is not None and ahora != pagina_antes:
                return True
            if ahora is None and self.primera_fila() != fila_antes:
                return True
        return False

    def ir_a_siguiente_pagina(self, segundos=25):
        """Pasa a la pagina siguiente, UNA por una.

        Q10 muestra una ventana de 5 numeros (1 2 3 4 5 »). Se hace clic en el numero que sigue
        y, cuando ese numero ya no esta en la ventana, en '»', que abre el bloque siguiente y
        cae justo en esa pagina. Nunca se usa '»' estando en mitad del bloque: saltaria de 5 en 5.
        """
        actual = self.pagina_actual()
        destino = actual + 1 if actual else None
        if destino is not None:
            numero = self.page.locator(f"{self.NUMERO_PAGINA}[data-page='{destino}']").first
            if numero.count() and numero.is_visible():
                if self.clic_en_paginacion(numero, destino, segundos):
                    return True

        siguiente = self.boton_siguiente()
        if siguiente is None:
            return False            # se acabo la lista: el ultimo bloque ya no ofrece flecha
        if self.clic_en_paginacion(siguiente, destino, segundos):
            return True
        print("  La lista no paso a la pagina siguiente a tiempo")
        return False

    def texto_buscado(self):
        """Lo que hay ahora mismo escrito en el buscador de la pantalla."""
        campo = self.campo_de_busqueda()
        try:
            return campo.input_value().strip() if campo is not None else ""
        except Exception:
            return ""

    def preparar_pagina(self, numero, buscado=""):
        """Deja la lista filtrada y en la pagina que se pide.

        Hace falta porque al salir de un curso ('Volver a cursos') Q10 devuelve la lista limpia:
        sin el texto buscado y en la primera pagina. Si el filtro no se pudo volver a poner,
        devuelve False: es preferible parar a bajar cursos que no se pidieron.
        """
        if buscado:
            self.buscar(buscado)
            quedo = self.texto_buscado()
            if self.normalizar(quedo) != self.normalizar(buscado):
                print(f"  No pude volver a poner el filtro '{buscado}' (quedo '{quedo}')")
                return False
        for _ in range(numero - 1):
            siguiente = self.boton_siguiente()
            if siguiente is None:
                return False
            antes = self.primera_fila()
            siguiente.click()
            self.esperar_tabla(antes)
        return True

    def leer_tabla(self):
        """Encabezados y filas de la tabla que se ve ahora (todo de una, no celda por celda)."""
        tabla = self.page.locator(self.TABLA).first
        if not tabla.count():
            return [], []
        datos = tabla.evaluate("""t => {
            const limpia = s => (s || '').replace(/\\s+/g, ' ').trim();
            const encabezados = [...t.querySelectorAll('thead th, thead td')].map(c => limpia(c.innerText));
            const filas = [...t.querySelectorAll('tbody tr')].map(
                f => [...f.querySelectorAll('td')].map(c => limpia(c.innerText)));
            return {encabezados, filas};
        }""")
        return datos["encabezados"], [f for f in datos["filas"] if any(f)]

    def boton_siguiente(self):
        """El '»' de la paginacion, solo si se puede usar (no esta deshabilitado)."""
        for candidato in (self.page.get_by_role("link", name=self.SIGUIENTE),
                          self.page.locator(".pagination a, .pagination li a")
                              .filter(has_text=self.SIGUIENTE)):
            try:
                for indice in range(min(candidato.count(), 4)):
                    enlace = candidato.nth(indice)
                    if not enlace.is_visible():
                        continue
                    apagado = enlace.evaluate(
                        "el => !!el.closest('.disabled') || el.getAttribute('aria-disabled') === 'true'")
                    if not apagado:
                        return enlace
            except Exception:
                continue
        return None

    def todas_las_filas(self, max_paginas=100):
        """Recorre la paginacion y junta las filas de todas las paginas."""
        encabezados, filas = self.leer_tabla()
        print(f"  pagina 1: {len(filas)} fila(s)")
        for numero in range(2, max_paginas + 1):
            siguiente = self.boton_siguiente()
            if siguiente is None:
                break
            antes = self.primera_fila()
            siguiente.click()
            self.esperar_tabla(antes)
            _, nuevas = self.leer_tabla()
            if not nuevas or (nuevas and nuevas == filas[-len(nuevas):]):
                break          # la tabla no cambio: no hay mas paginas
            print(f"  pagina {numero}: {len(nuevas)} fila(s)")
            filas.extend(nuevas)
        return encabezados, filas


class PaginaCursoVirtual(Pagina):
    """Un curso virtual por dentro: su menu lateral, la lista de usuarios y el boton Exportar."""
    USUARIOS = "a[href$='#Usuarios'], .edv-options-item.edv-users a"
    CUANTOS = ".cantidadUsuarios"
    EXPORTAR = (".filter-export, a.dropdown-toggle.filter-export,"
                " .btn-group a.dropdown-toggle, .btn-group button.dropdown-toggle")
    TEXTO_EXPORTAR = re.compile(r"exportar", re.I)
    OPCIONES = ".dropdown-menu:visible a, .dropdown-menu:visible li a, .open .dropdown-menu a"
    SIN_USUARIOS = re.compile(r"no hay usuarios", re.I)
    VOLVER = ".edv-options-item.edv-return a, .edv-return a"
    TEXTO_VOLVER = re.compile(r"volver a cursos", re.I)
    # Lo que ofrece el desplegable no se llama igual que en el Config ("XLSX" vs "Excel")
    IGUALES = {"XLSX": ("xlsx", "excel"), "XLS": ("xls", "excel"), "CSV": ("csv",),
               "PDF": ("pdf",), "DOC": ("doc", "word"), "HTML": ("html",)}

    def abrir(self, href):
        """Entra al curso por su direccion, sin perder la lista de atras."""
        self.page.goto(urljoin(self.page.url, href))
        self.page.wait_for_load_state()
        self.esperar(1_000)

    def cuantos_usuarios(self):
        """El numero que Q10 muestra al lado de 'Usuarios', o None si no se puede leer."""
        contador = self.page.locator(self.CUANTOS).first
        try:
            return int(contador.inner_text().strip()) if contador.count() else None
        except (ValueError, AttributeError):
            return None

    def boton_exportar(self):
        """El boton 'Exportar' de la seccion de usuarios, o None si todavia no esta."""
        for candidato in (self.page.locator(self.EXPORTAR),
                          self.page.get_by_role("link", name=self.TEXTO_EXPORTAR),
                          self.page.get_by_role("button", name=self.TEXTO_EXPORTAR)):
            try:
                for indice in range(min(candidato.count(), 5)):
                    if candidato.nth(indice).is_visible():
                        return candidato.nth(indice)
            except Exception:
                continue
        return None

    def esperar_usuarios(self, segundos=40):
        """Espera a que la seccion de usuarios termine de cargar.

        La lista llega por AJAX y tarda distinto en cada curso: se espera a que aparezca el
        boton 'Exportar' o el aviso de que no hay usuarios, en vez de un tiempo fijo.
        """
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            if self.boton_exportar() is not None or self.sin_usuarios():
                return True
            self.page.wait_for_timeout(500)
        return False

    def ir_a_usuarios(self, segundos=30):
        """Abre la seccion Usuarios del curso, esperando a que cargue el menu lateral."""
        limite = time.monotonic() + segundos
        enlace = None
        while time.monotonic() < limite:
            candidato = self.page.locator(self.USUARIOS).first
            try:
                if candidato.count() and candidato.is_visible():
                    enlace = candidato
                    break
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        if enlace is None:
            raise ValueError("Este curso no tiene la seccion 'Usuarios'")

        enlace.click()
        self.page.wait_for_load_state()
        if not self.esperar_usuarios():
            print("  La seccion de usuarios tardo mas de lo normal; intento igual")

    def volver_a_cursos(self):
        """Clic en 'Volver a cursos' del menu lateral, para quedar otra vez en la lista."""
        for candidato in (self.page.locator(self.VOLVER),
                          self.page.get_by_role("link", name=self.TEXTO_VOLVER),
                          self.page.get_by_text(self.TEXTO_VOLVER)):
            try:
                if candidato.count() and candidato.first.is_visible():
                    print("  Clic en: Volver a cursos")
                    candidato.first.click()
                    self.page.wait_for_load_state()
                    self.esperar(1_500)
                    return True
            except Exception:
                continue
        print("  No encontre 'Volver a cursos'; sigo con el siguiente de todas formas")
        return False

    def sin_usuarios(self):
        """La seccion dice que el curso no tiene usuarios registrados."""
        try:
            return self.page.get_by_text(self.SIN_USUARIOS).count() > 0
        except Exception:
            return False

    def exportar(self, formato="XLSX", espera=60):
        """Abre el desplegable 'Exportar' y escoge el formato. Devuelve la descarga."""
        boton = self.boton_exportar()
        if boton is None:
            self.esperar_usuarios()          # pudo no haber terminado de cargar
            boton = self.boton_exportar()
        if boton is None:
            if self.page.get_by_text(self.SIN_USUARIOS).count():
                raise ValueError("El curso no tiene usuarios registrados")
            raise ValueError("No encontre el boton 'Exportar' en la seccion de usuarios")

        print("  Clic en: Exportar")
        boton.click()
        self.esperar(1_000)

        # El desplegable ofrece varios formatos; se escoge el que diga el Config
        buscados = self.IGUALES.get(formato.upper(), (formato.lower(),))
        opciones = self.page.locator(self.OPCIONES)
        elegida, nombres = None, []
        for indice in range(opciones.count()):
            opcion = opciones.nth(indice)
            try:
                if not opcion.is_visible():
                    continue
                texto = " ".join(opcion.inner_text().split())
            except Exception:
                continue
            nombres.append(texto)
            if elegida is None and any(b in self.normalizar(texto) for b in buscados):
                elegida = opcion
        if elegida is None and nombres:
            print(f"  '{formato}' no esta en el menu ({nombres}); uso la primera opcion")
            elegida = opciones.nth(0)
        if elegida is None:
            raise ValueError("El boton 'Exportar' no desplego ninguna opcion")

        print(f"  Clic en: {' '.join(elegida.inner_text().split())}")
        with self.page.expect_download(timeout=espera * 1_000) as descarga:
            elegida.click()
        return descarga.value


class PaginaInformes(Pagina):
    """Menu de informes agrupados por seccion (Favoritos, Gestion academica, Comunidad en Excel...)."""
    ENLACES = "a.reportes"
    # Ademas de los id de siempre, cualquier formulario que traiga un boton de pedir el informe:
    # con la barra nueva Q10 deja formularios escondidos antes del del informe
    FORMULARIO = ("#formReportes, #form0, form:has(#generar-reporte-btn), form:has(#generar-excel-btn),"
                  " form:has(#programar-reporte-btn)")
    VOLVER_A_GENERAR = ".reiniciar-tarea, [title='Volver a generar']"
    TEXTO_VOLVER = re.compile(r"volver a generar", re.I)
    # "Estudiantes (Comunidad en Excel)" -> nombre + seccion
    NOMBRE_CON_SECCION = re.compile(r"^(?P<nombre>.+?)\s*\((?P<seccion>[^()]+)\)\s*$")

    def hay_lista(self):
        """Si el menu de informes esta a la vista (y no el formulario de un informe)."""
        enlaces = self.page.locator(self.ENLACES)
        try:
            return enlaces.count() > 0 and enlaces.first.is_visible()
        except Exception:
            return False

    def esperar_lista(self, segundos=20):
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            if self.hay_lista():
                return True
            self.page.wait_for_timeout(500)
        return False

    def esta_abierta(self):
        """No basta la direccion: el formulario de un informe vive dentro de la misma /Informes."""
        return bool(re.search(r"/Informes/?$", self.page.url, re.I)) and self.hay_lista()

    def abrir_informe(self, pedido):
        """Abre el informe. Acepta el nombre, "Nombre (Seccion)" o su direccion (ListadoCursos)."""
        encontrado = self.NOMBRE_CON_SECCION.match(pedido)
        nombre = (encontrado["nombre"] if encontrado else pedido).strip()
        seccion = encontrado["seccion"].strip() if encontrado else None

        enlace = self.enlace_por_direccion(nombre) or self.enlace_por_texto(nombre, seccion)
        ruta = enlace.get_attribute("data-href") or ""
        print(f"  Clic en el informe: {' '.join(enlace.inner_text().split())}"
              + (f" [{seccion}]" if seccion else "") + (f"  ({ruta})" if ruta else ""))
        enlace.click()
        self.esperar_formulario()
        return FormularioInforme(self.page, ruta)

    def enlace_por_direccion(self, nombre):
        """Permite escribir la direccion del informe (ListadoCursos) en vez del nombre visible.

        Es la forma mas estable: no depende del texto ni de en que seccion este.
        """
        if " " in nombre:
            return None
        enlaces = self.page.locator(f'{self.ENLACES}[data-href$="/{nombre.strip("/")}"]')
        # El mismo informe puede estar en Favoritos y en su seccion: se usa el que se vea
        for indice in range(enlaces.count()):
            if enlaces.nth(indice).is_visible():
                return enlaces.nth(indice)
        return None

    def enlace_por_texto(self, nombre, seccion):
        enlaces = self.page.get_by_role("link", name=self.texto_exacto(nombre))
        if not enlaces.count():   # por si el Config lo escribio con otras mayusculas o tildes
            buscado = self.normalizar(nombre)
            titulo = next((t for t in self.page.locator("a:visible").all_inner_texts()
                           if self.normalizar(t) == buscado), None)
            if titulo:
                enlaces = self.page.get_by_role("link", name=self.texto_exacto(titulo))

        total = enlaces.count()
        if not total:
            parecidos = [" ".join(t.split()) for t in self.page.locator("a:visible").all_inner_texts()
                         if self.normalizar(nombre).split()[0] in self.normalizar(t)]
            raise ValueError(f"No encontre el informe '{nombre}'. Revisa la tabla Informe de la hoja Q10."
                             + (f" Parecidos: {parecidos[:5]}" if parecidos else ""))

        indice = 0
        if total > 1:
            secciones = self.secciones_de(enlaces)
            if seccion:
                buscada = self.normalizar(seccion)
                indice = next((i for i, s in enumerate(secciones) if buscada in self.normalizar(s)), None)
                if indice is None:
                    raise ValueError(f"'{nombre}' no esta en la seccion '{seccion}'. "
                                     f"Esta en: {secciones}")
            else:
                print(f"  Aviso: '{nombre}' aparece {total} veces ({secciones}); uso el primero. "
                      f"Para escoger, escribe 'Nombre (Seccion)' en el Config")
        return enlaces.nth(indice)

    def secciones_de(self, enlaces):
        """Titulo de la seccion (Favoritos, Gestion academica...) de cada enlace repetido."""
        return enlaces.evaluate_all("""enlaces => enlaces.map(enlace => {
            let nodo = enlace, titulo = '';
            while (nodo && !titulo) {
                let anterior = nodo.previousElementSibling;
                while (anterior && !titulo) {
                    if (/^H[1-6]$/.test(anterior.tagName)) titulo = anterior.innerText;
                    anterior = anterior.previousElementSibling;
                }
                nodo = nodo.parentElement;
            }
            return titulo.trim();
        })""")

    def boton_volver(self):
        """El "Volver a generar" del resultado anterior (es un enlace, no siempre trae title)."""
        for candidato in (self.page.locator(self.VOLVER_A_GENERAR),
                          self.page.get_by_role("link", name=self.TEXTO_VOLVER),
                          self.page.get_by_role("button", name=self.TEXTO_VOLVER),
                          self.page.get_by_text(self.TEXTO_VOLVER)):
            try:
                if candidato.count() and candidato.first.is_visible():
                    return candidato.first
            except Exception:
                continue
        return None

    def esperar_formulario(self, segundos=30):
        """Espera el formulario, que se inyecta por AJAX en la misma URL (tarda ~3 s).

        A veces el informe no abre en el formulario sino en el resultado de una descarga anterior
        ("El reporte se ha generado exitosamente" + Abrir reporte). Ese reporte es viejo y tiene
        otros filtros, asi que hay que darle a "Volver a generar" para empezar de cero.
        """
        limite = time.monotonic() + segundos
        reinicios = 0
        while time.monotonic() < limite:
            if self.formulario_visible():
                self.esperar(1_000)   # dar tiempo a que carguen las primeras listas
                return True

            volver = self.boton_volver()
            if reinicios < 2 and volver is not None:
                print("  El informe abrio con un reporte anterior; clic en 'Volver a generar'")
                try:
                    volver.click(timeout=10_000)
                except Exception:
                    volver.dispatch_event("click")
                reinicios += 1
                self.esperar(2_000)
            self.page.wait_for_timeout(500)
        raise ValueError("Di clic en el informe pero no aparecio el formulario de filtros. "
                         f"Formularios en la pagina: {self.formularios_de_la_pagina()}")

    def formulario_visible(self):
        """Si alguno (no solo el primero) de los formularios de informe se ve."""
        formularios = self.page.locator(self.FORMULARIO)
        try:
            return any(formularios.nth(i).is_visible() for i in range(formularios.count()))
        except Exception:
            return False

    def formularios_de_la_pagina(self):
        """id y si se ve cada <form>: sirve para ajustar FORMULARIO si Q10 lo vuelve a cambiar."""
        try:
            return self.page.locator("form").evaluate_all(
                "fs => fs.map(f => (f.id || '(sin id)') + (f.offsetParent ? '' : ' [oculto]'))")
        except Exception:
            return []


class FormularioInforme(Pagina):
    """Formulario de un informe: sus filtros y el boton que pide el reporte."""
    TITULOS = "label:visible"
    FILA = ("xpath=ancestor::div[contains(@class,'row-filter') or contains(@class,'form-group')"
            " or contains(@class,'row')][1]")
    ERRORES = ".field-validation-error:visible, .has-error label:visible"

    # En orden de preferencia: si un informe trae "Exportar Excel" y "Cargar reporte", se usa el Excel
    BOTONES = ("#generar-excel-btn", "#generar-reporte-btn", "#programar-reporte-btn",
               "[title='Generar reporte']", "[title='Exportar reporte']")
    EXPORTAR = re.compile(r"exportar|generar|cargar", re.I)

    # Panel de resultado (familia B) y visor (familia A)
    VOLVER_A_GENERAR = ".reiniciar-tarea, [title='Volver a generar']"
    TEXTO_VOLVER = re.compile(r"volver a generar", re.I)
    ABRIR_REPORTE = "#abrir-reporte, [title='Abrir reporte']"
    EXITO = re.compile(r"se ha generado exitosamente", re.I)
    SIN_RESULTADOS = re.compile(r"sin resultados|no se encontraron|no hay datos", re.I)
    VISOR = "#master-modal"
    LISTA_DE_FORMATOS = "#exportSelect"      # visor pdf.js de Q10
    PAGINAS_DEL_VISOR = "#numPages"          # dice "de 0" mientras carga
    CERRAR_VISOR = "#close"
    MENU_EXPORTAR = re.compile(r"^\s*exportar\s*$", re.I)
    FORMATOS_DEL_MENU = ["PDF", "XLSX", "XLS", "DOC", "HTML", "CSV", "IMAGEN"]

    # Rango de fechas: se ve DD/MM/YYYY pero se guarda MM/DD/YYYY
    FECHA_INICIO = "input[id$='_InitialDate']"
    FECHA_FIN = "input[id$='_FinalDate']"
    # Solo la clase del calendario: si se buscara algo mas general (.input-group) se confundirian
    # con fechas los campos de texto con adorno, como "Valor inicial de efectivo"
    CALENDARIO = "[class*='daterange']"
    PRESETS = ".daterangepicker:visible .ranges li"
    RANGO = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})\s*(?:-|a|hasta)\s*(\d{1,2}/\d{1,2}/\d{4})")

    AUTOCOMPLETAR = ".selectize-control, input.ui-autocomplete-input"
    SUGERENCIAS = (".selectize-dropdown-content .option:visible, ul.ui-autocomplete:visible li,"
                   " .tt-suggestion:visible")
    INTERRUPTOR = ".bootstrap-switch, .make-switch"
    MARCAR_TODOS = "#todos"
    MARCAR_NINGUNO = "#ninguno"
    SI = re.compile(r"^\s*(si|sí|yes|true|1)\s*$", re.I)

    def __init__(self, page, ruta=""):
        super().__init__(page)
        self.ruta = ruta or ""       # data-href del informe: dice a que familia pertenece

    @property
    def familia(self):
        """A = visor PDF, B = tarea en segundo plano, C = descarga directa, D = solo pantalla."""
        ruta = self.ruta.lower()
        if "/reportepantalla/" in ruta:
            return "D"
        if self.page.locator("#programar-reporte-btn").count():
            return "B"
        if "/reportes/excel/" in ruta or self.page.locator("#form0").count():
            return "C"
        return "A"

    # ------------------------------------------------------------------ filtros ---
    def fila_del_filtro(self, nombre):
        """Fila del filtro cuyo titulo coincide, sin importar mayusculas, tildes ni el '*'.

        Solo mira las etiquetas VISIBLES: los informes con "Filtrar por" esconden los campos de
        los otros modos, y esos no se deben tocar.

        Ojo con los nombres repetidos: en varios informes el "Filtrar por" tiene las opciones
        "Programa" y "Curso", que se llaman igual que los filtros de verdad. Por eso se deja de
        ultimo el texto que solo es la etiqueta de un radio.
        """
        candidatos = []
        for titulo in self.page.locator(self.TITULOS).all():
            try:
                if self.normalizar(titulo.inner_text()) == self.normalizar(nombre):
                    candidatos.append(titulo)
            except Exception:
                continue
        if not candidatos:
            return None

        titulo = next((t for t in candidatos if not self.es_opcion_de_radio(t)), None)
        if titulo is None:
            return None     # ese nombre es solo una opcion de "Filtrar por", no un filtro
        fila = titulo.locator(self.FILA)
        if fila.count():
            return fila.first
        destino = titulo.get_attribute("for")
        if destino and self.page.locator(f"[id='{destino}']").count():
            return self.page.locator(f"[id='{destino}']")
        return None

    def es_opcion_de_radio(self, titulo):
        """True si ese texto es el nombre de una opcion (un radio) y no el nombre de un filtro."""
        destino = titulo.get_attribute("for")
        if not destino:
            return False
        control = self.page.locator(f"[id='{destino}']")
        if not control.count():
            return False
        return (control.first.get_attribute("type") or "").lower() == "radio"

    def esperar_ajax(self, segundos=15):
        """Las listas dependientes se recargan por AJAX: esperar a que la red se calme."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=segundos * 1_000)
        except Exception:
            pass

    def llenar(self, nombre, valor):
        """Pone el valor en el filtro, sea del tipo que sea."""
        fila = self.fila_del_filtro(nombre)
        if fila is None:
            print(f"  Filtro '{nombre}' no existe en este informe (o esta oculto); se salta.")
            return None

        if fila.locator("select").count():
            return self.escoger_de_lista(nombre, fila.locator("select").first, valor)
        if fila.locator(self.FECHA_INICIO).count() or fila.locator(self.CALENDARIO).count():
            return self.poner_fechas(nombre, fila, valor)
        if fila.locator(self.AUTOCOMPLETAR).count():
            return self.autocompletar(nombre, fila, valor)

        casillas = fila.locator("input[type=checkbox]")
        if casillas.count() > 1:
            return self.marcar_casillas(nombre, fila, valor)
        if casillas.count() == 1:
            return self.poner_interruptor(nombre, fila, casillas.first, valor)
        if fila.locator("input[type=radio]").count():
            return self.escoger_radio(nombre, fila, valor)

        texto = fila.locator("input:visible, textarea:visible").first
        if texto.count():
            texto.fill(valor)
            print(f"  {nombre}: {valor}")
            return valor
        print(f"  Filtro '{nombre}': no reconozco el tipo de control; se salta.")
        return None

    def escoger_de_lista(self, nombre, campo, valor):
        """Listas desplegables. En las de seleccion multiple se pueden pedir varias con ';'."""
        multiple = campo.get_attribute("multiple") is not None
        pedidos = [v.strip() for v in str(valor).split(";") if v.strip()] if multiple else [str(valor)]

        etiquetas = []
        for pedido in pedidos:
            # Las listas dependen de la anterior (Sede -> Programa -> Curso): esperar a que cargue
            opcion = campo.locator("option").filter(has_text=self.texto_exacto(pedido)).first
            try:
                expect(opcion).to_be_attached(timeout=15_000)
            except AssertionError:
                opciones = [o.strip() for o in campo.locator("option").all_inner_texts() if o.strip()]
                raise ValueError(f"'{pedido}' no es una opcion de '{nombre}'. Opciones: {opciones[:12]}")
            etiquetas.append(opcion.inner_text().strip())   # texto exacto de Q10

        # force: Q10 tapa el <select> real con un widget (bootstrap-select); el valor igual cambia
        campo.select_option(label=etiquetas if multiple else etiquetas[0], force=True)
        elegido = "; ".join(etiquetas)
        print(f"  {nombre}: {elegido}")
        self.esperar_ajax()                          # la lista siguiente se recarga sola
        return elegido

    def poner_interruptor(self, nombre, fila, casilla, valor):
        """Interruptores Si/No (¿Incluir archivados?, ¿Solo morosos?...).

        La casilla real esta oculta debajo del widget: se hace clic en el widget, que es lo que
        actualiza el campo escondido que Q10 envia.
        """
        quiero = bool(self.SI.match(str(valor).strip()))
        if casilla.is_checked() == quiero:
            print(f"  {nombre}: {valor} (ya estaba asi)")
            return valor

        widget = fila.locator(self.INTERRUPTOR).first
        if widget.count():
            try:
                widget.click(timeout=5_000)
            except Exception:
                pass
        if casilla.is_checked() != quiero:
            try:
                casilla.set_checked(quiero, force=True)
            except Exception:
                casilla.evaluate("(el, quiero) => { el.checked = quiero;"
                                 " el.dispatchEvent(new Event('change', {bubbles: true})); }", quiero)
            self.poner_campo_escondido(casilla, quiero)
        print(f"  {nombre}: {valor}")
        self.esperar_ajax()
        return valor

    def poner_campo_escondido(self, casilla, quiero):
        """Cada interruptor '#algo-switch' tiene un campo escondido '#algo' que es el que se envia."""
        identificador = casilla.get_attribute("id") or ""
        gemelo = identificador.replace("-switch", "")
        if not gemelo or gemelo == identificador:
            return
        escondido = self.page.locator(f"input[type=hidden][id='{gemelo}']")
        if escondido.count():
            escondido.evaluate("(el, valor) => el.value = valor", "true" if quiero else "false")

    def escoger_radio(self, nombre, fila, valor):
        """Opciones tipo radio (Estado: Todos/Activos/Inactivos, Filtrar por: Programa/Curso...)."""
        radios = fila.locator("input[type=radio]")
        textos = []
        for indice in range(radios.count()):
            radio = radios.nth(indice)
            texto = self.texto_de(fila, radio)
            textos.append(texto)
            if self.normalizar(texto) == self.normalizar(valor):
                try:
                    radio.check(force=True)
                except Exception:
                    radio.evaluate("el => { el.checked = true;"
                                   " el.dispatchEvent(new Event('change', {bubbles: true})); }")
                print(f"  {nombre}: {texto}")
                self.esperar(1_000)   # "Filtrar por" muestra y esconde otros filtros
                return texto
        raise ValueError(f"'{valor}' no es una opcion de '{nombre}'. Opciones: {textos}")

    def texto_de(self, fila, control):
        """Texto de la etiqueta de un radio o una casilla (o su valor, si no tiene etiqueta)."""
        identificador = control.get_attribute("id") or ""
        if identificador:
            etiqueta = fila.locator(f"label[for='{identificador}']")
            if etiqueta.count():
                return " ".join(etiqueta.first.inner_text().split())
        return (control.get_attribute("value") or identificador).strip()

    def marcar_casillas(self, nombre, fila, valor):
        """Grupos de casillas (los "Campos" de Comunidad en Excel, que vienen todos marcados).

        Acepta Todos, Ninguno o una lista separada con ';'.
        """
        pedido = str(valor).strip()
        if self.normalizar(pedido) in ("todos", "todas"):
            enlace = self.page.locator(self.MARCAR_TODOS).first
            if enlace.count():
                enlace.click()
                print(f"  {nombre}: Todos")
                return "Todos"
        if self.normalizar(pedido) in ("ninguno", "ninguna"):
            enlace = self.page.locator(self.MARCAR_NINGUNO).first
            if enlace.count():
                enlace.click()
                print(f"  {nombre}: Ninguno")
                return "Ninguno"

        # Lista concreta: se desmarca todo y se marcan solo los pedidos
        deseados = [self.normalizar(c) for c in pedido.split(";") if c.strip()]
        ninguno = self.page.locator(self.MARCAR_NINGUNO).first
        if ninguno.count():
            ninguno.click()
        casillas = fila.locator("input[type=checkbox]")
        marcados, disponibles = [], []
        for indice in range(casillas.count()):
            casilla = casillas.nth(indice)
            texto = self.texto_de(fila, casilla)
            disponibles.append(texto)
            if self.normalizar(texto) in deseados:
                casilla.check(force=True)
                marcados.append(texto)
        if not marcados:
            raise ValueError(f"Ninguno de esos campos existe en '{nombre}'. Hay: {disponibles[:10]}")
        print(f"  {nombre}: {len(marcados)} campo(s) marcados")
        return "; ".join(marcados)

    def poner_fechas(self, nombre, fila, valor):
        """Rango de fechas. Acepta "01/09/2026 - 30/09/2026" o un preset (Hoy, Este mes, Todas...).

        El calendario muestra DD/MM/YYYY pero Q10 guarda MM/DD/YYYY en dos campos escondidos.
        """
        rango = self.RANGO.search(str(valor))
        if rango:
            def a_formato_q10(fecha):
                dia, mes, anio = fecha.split("/")
                return f"{int(mes):02d}/{int(dia):02d}/{anio}"

            for selector, fecha in ((self.FECHA_INICIO, a_formato_q10(rango[1])),
                                    (self.FECHA_FIN, a_formato_q10(rango[2]))):
                campo = fila.locator(selector).first
                if not campo.count():
                    raise ValueError(f"'{nombre}' no guarda el rango como espera el bot")
                campo.evaluate("(el, fecha) => { el.value = fecha;"
                               " el.dispatchEvent(new Event('change', {bubbles: true})); }", fecha)
            print(f"  {nombre}: {rango[1]} a {rango[2]}")
            return f"{rango[1]} a {rango[2]}"
        return self.escoger_preset(nombre, fila, valor)

    def escoger_preset(self, nombre, fila, valor):
        """Presets del calendario: Hoy, Ayer, Ultimos 7 dias, Este mes, Todas..."""
        abridor = fila.locator(f"{self.CALENDARIO}:visible, input:visible, button:visible").first
        if not abridor.count():
            print(f"  Filtro '{nombre}': no pude abrir el calendario; se salta.")
            return None
        abridor.click()
        self.esperar(500)
        presets = self.page.locator(self.PRESETS)
        disponibles = []
        for indice in range(presets.count()):
            opcion = presets.nth(indice)
            texto = " ".join(opcion.inner_text().split())
            disponibles.append(texto)
            if self.normalizar(texto) == self.normalizar(valor):
                opcion.click()
                print(f"  {nombre}: {texto}")
                return texto
        self.page.keyboard.press("Escape")
        raise ValueError(f"'{valor}' no es un rango ni un preset de '{nombre}'. "
                         f"Presets: {disponibles or 'ninguno'}")

    def autocompletar(self, nombre, fila, valor):
        """Campos de persona (docente, asesor, cajero): se escribe y se escoge de la lista."""
        campo = fila.locator(".selectize-input input, input.ui-autocomplete-input, input:visible").first
        campo.click()
        campo.fill("")
        campo.type(str(valor), delay=80)
        sugerencias = self.page.locator(self.SUGERENCIAS)
        try:
            expect(sugerencias.first).to_be_visible(timeout=15_000)
        except AssertionError:
            raise ValueError(f"'{valor}' no dio ninguna sugerencia en '{nombre}'")
        for indice in range(min(sugerencias.count(), 20)):
            opcion = sugerencias.nth(indice)
            texto = " ".join(opcion.inner_text().split())
            if self.normalizar(valor) in self.normalizar(texto):
                opcion.click()
                print(f"  {nombre}: {texto}")
                return texto
        elegido = " ".join(sugerencias.first.inner_text().split())
        sugerencias.first.click()
        print(f"  {nombre}: {elegido} (la primera sugerencia)")
        return elegido

    def existe(self, nombre):
        """Si el informe tiene ese filtro a la vista."""
        return self.fila_del_filtro(nombre) is not None

    def valor_actual(self, nombre):
        """Texto que muestra hoy el filtro. Sirve para saber si ya dice "Todos" sin tocarlo."""
        fila = self.fila_del_filtro(nombre)
        if fila is None:
            return None
        campo = fila.locator("select").first
        if not campo.count():
            return None
        return campo.evaluate(
            "el => el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : ''").strip()

    def opciones(self, nombre):
        """Opciones de una lista (sin "Seleccione"), o None si el filtro no es una lista."""
        fila = self.fila_del_filtro(nombre)
        if fila is None:
            return None
        campo = fila.locator("select").first
        if not campo.count():
            return None
        opciones = campo.locator("option")
        try:
            expect(opciones.nth(1)).to_be_attached(timeout=15_000)
        except AssertionError:
            raise ValueError(f"La lista '{nombre}' no tiene opciones")
        return [o.strip() for o in opciones.all_inner_texts()
                if o.strip() and self.normalizar(o) != "seleccione"]

    # --------------------------------------------------------- pedir el reporte ---
    def boton_generar(self, obligatorio=True):
        """Primer boton VISIBLE para pedir el informe, en orden de preferencia.

        Se busca el visible y no el primero que exista: Q10 deja botones escondidos en el
        formulario y esperar por uno oculto termina en timeout.
        """
        for selector in self.BOTONES:
            candidatos = self.page.locator(selector)
            try:
                for indice in range(min(candidatos.count(), 5)):
                    if candidatos.nth(indice).is_visible():
                        return candidatos.nth(indice)
            except Exception:
                continue
        for candidatos in (self.page.get_by_role("button", name=self.EXPORTAR),
                           self.page.get_by_role("link", name=self.EXPORTAR)):
            try:
                for indice in range(min(candidatos.count(), 5)):
                    if candidatos.nth(indice).is_visible():
                        return candidatos.nth(indice)
            except Exception:
                continue
        if not obligatorio:
            return None
        raise ValueError("No encontre el boton para pedir el informe en esta pantalla")

    def que_lo_tapa(self, elemento):
        """Nombre del elemento que esta encima (si algo tapa al boton y no deja hacer clic)."""
        try:
            return elemento.evaluate("""el => {
                const caja = el.getBoundingClientRect();
                const encima = document.elementFromPoint(caja.left + caja.width / 2,
                                                         caja.top + caja.height / 2);
                if (!encima || encima === el || el.contains(encima)) return '';
                return encima.tagName.toLowerCase() + (encima.id ? '#' + encima.id : '') +
                       (encima.className ? '.' + String(encima.className).trim().split(/\\s+/)[0] : '');
            }""")
        except Exception:
            return ""

    def clic_en_generar(self, boton):
        """Clic en el boton de pedir el informe, contando lo que pase si no se deja."""
        etiqueta = " ".join(boton.inner_text().split()) or "Exportar"
        print(f"  Clic en: {etiqueta}")
        try:
            boton.scroll_into_view_if_needed(timeout=5_000)
        except Exception:
            pass
        # Un boton deshabilitado no recibe clics del raton (ni a la fuerza): se le avisa directo
        if not boton.is_enabled():
            print("  El boton esta bloqueado por el informe anterior; le aviso directamente")
            boton.dispatch_event("click")
            return
        try:
            boton.click(timeout=20_000)
            return
        except Exception as error:
            estorbo = self.que_lo_tapa(boton)
            print(f"  El clic normal no paso ({type(error).__name__}; "
                  f"habilitado={boton.is_enabled()}"
                  + (f", encima esta {estorbo}" if estorbo else "") + ")")
        # Suele ser un panel del informe anterior encima: se intenta a la fuerza y, si no, se
        # avisa al elemento directamente (asi se soluciono el mismo problema en Macmillan)
        try:
            boton.click(force=True, timeout=5_000)
            print("  Clic a la fuerza: hecho")
        except Exception:
            boton.dispatch_event("click")
            print("  Clic enviado directo al boton")

    # ------------------------------------------------------------- el resultado ---
    def marcos(self):
        """Todos los marcos de todas las pestañas: el visor puede abrirse aparte."""
        for pagina in self.page.context.pages:
            try:
                for marco in pagina.frames:
                    yield marco
            except Exception:
                continue

    def visible(self, buscador):
        """True si ese texto o elemento se ve en alguna pestaña (sin reventar si algo falla)."""
        try:
            return buscador.count() > 0 and buscador.first.is_visible()
        except Exception:
            return False

    def boton_volver_a_generar(self):
        for marco in self.marcos():
            for candidato in (marco.locator(self.VOLVER_A_GENERAR),
                              marco.get_by_role("button", name=self.TEXTO_VOLVER),
                              marco.get_by_role("link", name=self.TEXTO_VOLVER),
                              marco.get_by_text(self.TEXTO_VOLVER)):
                if self.visible(candidato):
                    return candidato.first
        return None

    def lista_de_formatos(self):
        """Visor PDF de Q10: la exportacion es una lista 'select#exportSelect' dentro del marco."""
        for marco in self.marcos():
            candidato = marco.locator(self.LISTA_DE_FORMATOS)
            if self.visible(candidato):
                return marco, candidato.first
        return None, None

    def esperar_visor(self, marco, segundos=60):
        """El visor dice "de 0" mientras arma el PDF (tarda 15-20 s): esperar a que tenga paginas."""
        contador = marco.locator(self.PAGINAS_DEL_VISOR)
        if not contador.count():
            return True                      # ese visor no tiene contador de paginas
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            try:
                if re.search(r"[1-9]", contador.inner_text()):
                    return True
            except Exception:
                return True
            marco.page.wait_for_timeout(1_000)
        print("  Aviso: el visor sigue diciendo que no tiene paginas; intento exportar igual")
        return False

    def menu_del_visor(self):
        """Menu "Exportar" del visor (no el boton "Exportar reporte" del formulario)."""
        for marco in self.marcos():
            for candidato in (marco.get_by_role("button", name=self.MENU_EXPORTAR),
                              marco.get_by_role("link", name=self.MENU_EXPORTAR),
                              marco.locator("[title*='Exportar' i], [aria-label*='Exportar' i]"),
                              marco.locator("[class*='export' i]"),
                              marco.get_by_text(self.MENU_EXPORTAR)):
                try:
                    for indice in range(min(candidato.count(), 5)):
                        elemento = candidato.nth(indice)
                        if elemento.is_visible():
                            return marco, elemento
                except Exception:
                    continue
        return None, None

    def opcion_de_formato(self, formato):
        patron = re.compile(rf"^\s*{re.escape(formato)}\s*$", re.I)
        for marco in self.marcos():
            for candidato in (marco.get_by_role("menuitem", name=patron),
                              marco.get_by_role("link", name=patron),
                              marco.get_by_role("button", name=patron),
                              marco.get_by_text(patron)):
                try:
                    for indice in range(min(candidato.count(), 5)):
                        elemento = candidato.nth(indice)
                        if elemento.is_visible():
                            return elemento
                except Exception:
                    continue
        return None

    def exportar_desde_visor(self, formato="XLSX", descargas=()):
        """Saca el archivo del visor: primero la lista de formatos y si no, el menu "Exportar"."""
        marco, lista = self.lista_de_formatos()
        if lista is not None:
            self.esperar_visor(marco)
            print(f"  Visor: escojo {formato} en la lista de exportar")
            try:
                lista.select_option(label=formato, force=True)
            except Exception:
                lista.select_option(value=formato.lower(), force=True)
            espera = time.monotonic() + 30
            while not descargas and time.monotonic() < espera:
                marco.page.wait_for_timeout(500)
            return True
        return self.exportar_desde_menu(formato, descargas)

    def exportar_desde_menu(self, formato="XLSX", descargas=()):
        """Visores viejos: un menu "Exportar" que abre la lista de formatos.

        A veces el menu no se puede leer desde el codigo, asi que hay dos respaldos: recorrerlo
        con el teclado y, si no, hacer clic donde se dibuja la opcion.
        """
        marco, menu = self.menu_del_visor()
        if menu is None:
            return False
        caja = menu.bounding_box()
        pagina = marco.page
        print("  Clic en: Exportar (visor)")
        menu.click()
        self.esperar(2_000)

        opcion = self.opcion_de_formato(formato)
        if opcion is not None:
            print(f"  Clic en: {formato}")
            try:
                opcion.click(timeout=15_000)
            except Exception:
                opcion.dispatch_event("click")
            return True

        posicion = self.FORMATOS_DEL_MENU.index(formato.upper()) + 1
        print(f"  No pude leer el menu; bajo {posicion} veces con el teclado y doy Enter")
        for _ in range(posicion):
            pagina.keyboard.press("ArrowDown")
            pagina.wait_for_timeout(250)
        pagina.keyboard.press("Enter")

        espera = time.monotonic() + 8
        while not descargas and time.monotonic() < espera:
            pagina.wait_for_timeout(500)
        if descargas:
            return True

        if caja:
            alto = 36
            x = caja["x"] + caja["width"] / 2
            y = caja["y"] + caja["height"] + alto * (posicion - 0.5)
            print(f"  Clic por posicion en x={x:.0f} y={y:.0f}")
            pagina.mouse.click(x, y)
        return True

    def cerrar_resultado(self, pestanas_al_inicio):
        """Cierra el visor y las pestañas que abrio el informe, para dejar la pantalla limpia."""
        for marco in self.marcos():
            cerrar = marco.locator(self.CERRAR_VISOR)
            if self.visible(cerrar):
                try:
                    cerrar.first.click(timeout=5_000)
                except Exception:
                    pass
                break
        if self.visible(self.page.locator(self.VISOR)):
            self.page.keyboard.press("Escape")
        for pestana in self.page.context.pages:
            if pestana not in pestanas_al_inicio:
                try:
                    pestana.close()
                except Exception:
                    pass
        try:
            self.page.bring_to_front()
        except Exception:
            pass

    def listo_para_otro_informe(self):
        """El boton de pedir el informe se ve y no esta bloqueado por el informe anterior."""
        boton = self.boton_generar(obligatorio=False)
        try:
            return bool(boton and boton.is_enabled())
        except Exception:
            return False

    def volver_al_formulario(self, espera=15):
        """Deja la pantalla lista para el siguiente valor.

        Q10 muestra "Volver a generar" un momento DESPUES de entregar el archivo, y mientras ese
        panel siga ahi el boton de pedir el informe queda bloqueado. Por eso se espera a que
        aparezca en vez de mirar una sola vez.
        """
        limite = time.monotonic() + espera
        while time.monotonic() < limite:
            volver = self.boton_volver_a_generar()
            if volver:
                print("  Clic en: Volver a generar")
                try:
                    volver.click(timeout=10_000)
                except Exception:
                    volver.dispatch_event("click")
                self.esperar(3_000)
                return True
            if self.listo_para_otro_informe():
                return True          # el formulario quedo servible: no hay nada que limpiar
            self.page.wait_for_timeout(1_000)
        print("  Aviso: el informe anterior no se cerro solo; el siguiente puede tardar mas")
        return False

    def diagnostico(self):
        """Que se ve en cada pestaña mientras se espera el archivo."""
        lineas = []
        for numero, pagina in enumerate(self.page.context.pages, start=1):
            try:
                datos = [f"pestaña {numero}", f"url=...{pagina.url[-40:]}", f"marcos={len(pagina.frames)}"]
                for nombre, selector in (("abrir-reporte", "#abrir-reporte"),
                                         ("reiniciar-tarea", ".reiniciar-tarea"),
                                         ("visor", self.VISOR),
                                         ("lista-formatos", self.LISTA_DE_FORMATOS)):
                    datos.append(f"{nombre}={pagina.locator(selector).count()}")
                texto = " ".join(pagina.locator("body").inner_text().split())[:70]
                datos.append(f"texto='{texto}'")
                lineas.append(" | ".join(datos))
            except Exception as error:
                lineas.append(f"pestaña {numero}: no pude leerla ({type(error).__name__})")
        return "\n      ".join(lineas)

    def exportar(self, espera=240, formato="XLSX"):
        """Pide el informe y devuelve el archivo.

        Se vigilan a la vez las tres formas en que Q10 responde: el visor con su lista de formatos
        (familia A), el panel "Abrir reporte" de las tareas en segundo plano (B) y la descarga
        directa (C). Tambien se detecta "Sin resultados" y los campos requeridos sin llenar.
        """
        if self.familia == "D":
            raise ValueError("Este informe muestra el resultado en la pantalla y no genera archivo")

        boton = self.boton_generar()
        descargas = []
        contexto = self.page.context
        pestanas_al_inicio = list(contexto.pages)

        def guardar_descarga(descarga):
            descargas.append(descarga)

        def escuchar(pagina):
            pagina.on("download", guardar_descarga)

        for pestana in contexto.pages:
            escuchar(pestana)
        contexto.on("page", escuchar)
        try:
            self.clic_en_generar(boton)
            self.esperar(3_000)

            limite = time.monotonic() + espera
            siguiente_aviso = time.monotonic() + 30
            visor_usado = reporte_abierto = False
            while time.monotonic() < limite:
                if descargas:
                    self.cerrar_resultado(pestanas_al_inicio)
                    self.volver_al_formulario()
                    return descargas[0]

                if not visor_usado and self.exportar_desde_visor(formato, descargas):
                    visor_usado = True
                    continue

                # "Abrir reporte" a veces baja el archivo y a veces abre el visor: se da el clic
                # una sola vez y se sigue vigilando, que para eso esta el ciclo
                abrir = self.page.locator(self.ABRIR_REPORTE).first
                if not reporte_abierto and self.visible(abrir):
                    print("  Clic en: Abrir reporte")
                    abrir.click()
                    reporte_abierto = True
                    self.esperar(3_000)
                    continue

                # "Sin resultados" o el panel de volver a empezar sin nada que abrir.
                # Si ya se abrio el reporte, hubo datos: lo que queda es esperar el visor.
                generando = self.visible(self.page.get_by_text(self.EXITO))
                if not reporte_abierto and (self.visible(self.page.get_by_text(self.SIN_RESULTADOS))
                                            or (not generando and self.boton_volver_a_generar())):
                    print("  Q10 respondio 'Sin resultados'")
                    self.volver_al_formulario()
                    raise ValueError("Q10 respondio 'Sin resultados'")

                requeridos = self.page.locator(self.ERRORES).all_inner_texts()
                if requeridos:
                    raise ValueError(f"Q10 pide llenar: "
                                     f"{[r.replace('*', '').strip() for r in requeridos]}")
                if time.monotonic() > siguiente_aviso:
                    print(f"    esperando...\n      {self.diagnostico()}")
                    siguiente_aviso = time.monotonic() + 15
                self.page.wait_for_timeout(1_000)

            raise ValueError(f"Pedi el informe pero en {espera} s no llego ningun archivo. "
                             f"{self.diagnostico()}")
        finally:
            contexto.remove_listener("page", escuchar)
            for pestana in contexto.pages:
                try:
                    pestana.remove_listener("download", guardar_descarga)
                except Exception:
                    pass
