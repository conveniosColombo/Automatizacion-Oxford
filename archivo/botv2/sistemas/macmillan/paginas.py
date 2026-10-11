"""Page Objects de Macmillan Education Everywhere (MEE)."""
import math
import re

from playwright.sync_api import expect

from core.pagina import Pagina


class InicioMacmillan(Pagina):
    """Pagina publica de MEE: banner de cookies y boton "Iniciar sesion"."""
    RECHAZAR_COOKIES = re.compile(r"reject optional|rechazar", re.I)
    # El enlace de ingreso cambia de texto segun el idioma (Iniciar sesion / Log in), el href no
    ENTRAR = "a[href='/oidc-login']"

    def abrir(self, link):
        self.page.goto(link)
        self._rechazar_cookies()
        return self

    def _rechazar_cookies(self):
        """Banner de privacidad: rechazar las cookies opcionales (si no aparece, se sigue)."""
        try:
            self.page.get_by_role("button", name=self.RECHAZAR_COOKIES).first.click(timeout=8_000)
            self.esperar(1_000)
        except Exception:
            pass

    def ir_a_login(self):
        self.page.locator(self.ENTRAR).first.click()
        # El ingreso vive en otro dominio (identity.macmillaneducationeverywhere.com)
        self.page.wait_for_url(re.compile(r"identity\.macmillaneducationeverywhere\.com"), timeout=60_000)
        self.page.wait_for_load_state()
        return LoginMacmillan(self.page)


class LoginMacmillan(Pagina):
    """Formulario de ingreso de MEE: usuario y contrasena en la misma pantalla."""
    USUARIO = "#username"
    CLAVE = "#password"
    ENTRAR = re.compile(r"^\s*(log in|iniciar sesi)", re.I)
    ERRORES = "[role=alert]:visible, .validation-summary-errors:visible, .field-validation-error:visible"

    def iniciar_sesion(self, usuario, clave):
        campo_usuario = self.page.locator(self.USUARIO)
        expect(campo_usuario).to_be_visible(timeout=20_000)
        campo_usuario.fill(usuario)
        self.page.locator(self.CLAVE).fill(clave)
        self.page.get_by_role("button", name=self.ENTRAR).first.click()

        # Al entrar, MEE devuelve al sitio principal; si sigue en identity, el ingreso fallo
        try:
            self.page.wait_for_url(re.compile(r"macmillaneducationeverywhere\.com(?!.*identity)"), timeout=60_000)
        except Exception:
            mensajes = self.page.locator(self.ERRORES).all_inner_texts()
            detalle = " ".join(" ".join(m.split()) for m in mensajes if m.strip())
            raise ValueError("No pude iniciar sesion en Macmillan" + (f": {detalle}" if detalle else ""))
        self.page.wait_for_load_state()
        self.esperar(5_000)  # dar tiempo a que cargue la pagina de inicio
        return Estanteria(self.page)


class Estanteria(Pagina):
    """"Mi Estanteria": las portadas de los libros activados."""
    URL = "https://www.macmillaneducationeverywhere.com/bookshelf"
    # Cada libro es un <a class="c-book-tile"> con su nombre en el div del pie
    LIBRO = "a.c-book-tile"
    NOMBRE_LIBRO = ".c-book-tile__footer"

    def abrir(self):
        """Vuelve a la estanteria (por ejemplo, despues de entrar a otro libro)."""
        if "/bookshelf" not in self.page.url:
            self.page.goto(self.URL)
            self.page.wait_for_load_state()
            self.esperar(2_000)
        return self

    def abrir_libro(self, nombre):
        """Da clic en la portada del libro con ese nombre exacto."""
        libro = self.page.locator(self.LIBRO).filter(
            has=self.page.locator(self.NOMBRE_LIBRO, has_text=self.texto_exacto(nombre))).first
        try:
            expect(libro).to_be_visible(timeout=15_000)
        except AssertionError:
            disponibles = [" ".join(t.split()) for t in
                           self.page.locator(f"{self.LIBRO} {self.NOMBRE_LIBRO}").all_inner_texts()]
            raise ValueError(f"No encontre el libro '{nombre}'. En la estanteria hay: {disponibles}")
        print(f"  Clic en el libro: {nombre}")
        libro.click()
        self.page.wait_for_load_state()
        self.esperar(3_000)  # dar tiempo a que cargue el libro
        return Libro(self.page)


class Libro(Pagina):
    """Pagina de un libro: pestañas de nivel (Level 1, Level 2...) y la lista de recursos del nivel."""
    NIVELES = "ul.c-tabs a[role=tab]"
    # Opciones del nivel: Macmillan Education Everywhere App, Teacher's Resource Centre, Test Generator...
    RECURSOS = "ul.c-level-list a.c-level-target"

    def niveles(self):
        """Nombres de las pestañas de nivel, para el valor "Todos" del Config."""
        return [" ".join(t.split()) for t in self.page.locator(self.NIVELES).all_inner_texts() if t.strip()]

    def abrir_nivel(self, nombre):
        """Da clic en la pestaña del nivel con ese nombre exacto."""
        pestana = self.page.locator(self.NIVELES).filter(has_text=self.texto_exacto(nombre)).first
        try:
            expect(pestana).to_be_visible(timeout=15_000)
        except AssertionError:
            raise ValueError(f"No encontre el nivel '{nombre}'. Este libro tiene: {self.niveles()}")
        print(f"  Clic en el nivel: {nombre}")
        pestana.click()
        self.esperar(3_000)  # el contenido de la pestaña se carga despues del clic
        return self

    def recursos(self):
        """Titulos de las opciones del nivel (la primera linea de cada una)."""
        # De cada opcion se toma solo la primera linea (el titulo), no la descripcion de abajo
        return [t.strip().splitlines()[0].strip()
                for t in self.page.locator(self.RECURSOS).all_inner_texts() if t.strip()]

    def abrir_recurso(self, nombre):
        """Entra a una opcion del nivel, por ejemplo "Macmillan Education Everywhere App".

        Cada opcion trae titulo y descripcion, por eso se busca el nombre como parte del texto
        y no como texto completo.
        """
        opcion = self.page.locator(self.RECURSOS).filter(
            has_text=re.compile(re.escape(nombre), re.I)).first
        try:
            expect(opcion).to_be_visible(timeout=15_000)
        except AssertionError:
            raise ValueError(f"No encontre '{nombre}' en este nivel. Hay: {self.recursos()}")
        print(f"  Clic en: {nombre}")
        return AppMacmillan(self.clic_y_seguir(opcion))


class AppMacmillan(Pagina):
    """Pantalla del recurso: "View in browser" (con su boton View), "View in app" y "Download the app"."""
    # El boton View de "View in browser"; abre el contenido en una pestaña nueva
    VER_EN_NAVEGADOR = "a.view-link--button"

    def ver_en_navegador(self):
        boton = self.page.locator(self.VER_EN_NAVEGADOR).first
        try:
            expect(boton).to_be_visible(timeout=20_000)
        except AssertionError:
            raise ValueError("No encontre el boton 'View' de 'View in browser'")
        print("  Clic en: View (View in browser)")
        return VisorMacmillan(self.clic_y_seguir(boton, espera=8_000))


class VisorMacmillan(Pagina):
    """"My library" (mee.macmillaneducation.com): el contenido abierto en el navegador.

    Es otra aplicacion, con sus propias etiquetas (maced-dialog, maced-button...).
    Aqui iran los pasos del reporte.
    """
    # Este dominio tiene su propio banner de cookies, que tapa el pie de la ventana de sesion
    RECHAZAR_COOKIES = re.compile(r"reject optional|rechazar", re.I)
    # Boton Continue del aviso de sesion: <button id="Yes" aria-label="Continue">
    BOTON_CONTINUAR = "maced-dialog-footer button#Yes"
    CONTINUAR = re.compile(r"^\s*(continue|continuar)\s*$", re.I)  # respaldo, por si cambia el id

    # Menu lateral: cada opcion es un <li> con id propio (bookshelf, adminCalss, School...)
    MENU = "nav.c-menu ul.c-menu__list"
    SCHOOL_WORK = "li#School a.c-menu__list-item-link"
    BOTON_MENU = re.compile(r"^\s*(menu|men[uú]|abrir men)", re.I)
    # Submenu de School work: Assessment, Homework, Progress, Grading, Calendar
    PROGRESS = "a#schoolProgresslink"

    def cerrar_aviso_sesion(self):
        """Ventana "Keep me logged in": se presiona Continue SIN marcar la casilla.

        Mantener la sesion abierta es una opcion de seguridad de la cuenta y el bot no la necesita,
        porque inicia sesion cada vez. Si la ventana no aparece, se sigue de largo.
        """
        self.rechazar_cookies()  # el banner de cookies tapa el pie de la ventana

        boton = self.page.locator(self.BOTON_CONTINUAR).or_(
            self.page.get_by_role("button", name=self.CONTINUAR)).first
        try:
            expect(boton).to_be_visible(timeout=15_000)
        except AssertionError:
            print("  (no aparecio la ventana 'Keep me logged in')")
            return self
        print("  Clic en: Continue (sin marcar 'Keep me logged in')")
        boton.scroll_into_view_if_needed()
        try:
            boton.click(timeout=15_000)
        except Exception:
            # Si algo quedo encima (un banner, una animacion), se le envia el evento al elemento
            print("  (algo tapaba el boton: clic directo)")
            boton.dispatch_event("click")
        self.esperar(3_000)  # dar tiempo a que se cierre la ventana y cargue My library
        return self

    def rechazar_cookies(self):
        """Banner "Your privacy, your choice" de mee.macmillaneducation.com: rechazar las opcionales."""
        try:
            boton = self.page.get_by_role("button", name=self.RECHAZAR_COOKIES).first
            expect(boton).to_be_visible(timeout=8_000)
            print("  Clic en: rechazar cookies opcionales")
            boton.click()
            self.esperar(2_000)  # el banner se cierra con una animacion
        except Exception:
            pass  # si no hay banner, se sigue

    def _abrir_menu_lateral(self):
        """En ventanas angostas el menu esta escondido detras del boton de hamburguesa."""
        if self.page.locator(self.MENU).is_visible():
            return
        try:
            self.page.get_by_role("button", name=self.BOTON_MENU).first.click(timeout=5_000)
            self.esperar(1_000)
        except Exception:
            pass

    def abrir_school_work(self):
        """Despliega "School work" del menu lateral."""
        self._abrir_menu_lateral()
        opcion = self.page.locator(self.SCHOOL_WORK).first
        try:
            expect(opcion).to_be_visible(timeout=20_000)
        except AssertionError:
            opciones = [" ".join(t.split()) for t in
                        self.page.locator(f"{self.MENU} li").all_inner_texts() if t.strip()]
            raise ValueError(f"No encontre 'School work' en el menu. Hay: {opciones}")

        # aria-expanded dice si el submenu ya esta abierto; un segundo clic lo cerraria
        if opcion.get_attribute("aria-expanded") == "true":
            print("  'School work' ya estaba desplegado")
            return self
        print("  Clic en: School work")
        opcion.click()
        self.esperar(2_000)  # el submenu se despliega despues del clic
        return self

    def abrir_progress(self):
        """Entra a "Progress" del submenu de School work."""
        opcion = self.page.locator(self.PROGRESS).first
        try:
            expect(opcion).to_be_visible(timeout=20_000)
        except AssertionError:
            opciones = [" ".join(t.split()) for t in
                        self.page.locator(f"{self.MENU} a.c-menu__list-item-link").all_inner_texts() if t.strip()]
            raise ValueError(f"No encontre 'Progress' en School work. Hay: {opciones}")
        print("  Clic en: Progress")
        opcion.click()
        try:
            self.page.wait_for_url(re.compile(r"/school-work/progress", re.I), timeout=30_000)
        except Exception:
            raise ValueError(f"Di clic en 'Progress' pero la pagina no cambio; quedo en {self.page.url}")
        self.page.wait_for_load_state()
        self.esperar(5_000)  # la tabla de progreso se carga despues
        return PaginaProgreso(self.page)


class PaginaProgreso(Pagina):
    """School work > Progress: panel "Go to" (curso, clases, secciones), boton Go, Filters y Export."""
    # Buscador de curso del panel "Go to"
    CURSO = "#all_coursesInput"
    # Boton Go: su id dice "undefined", asi que se usa el aria-label (y el texto como respaldo)
    BOTON_GO = "button[aria-label*='Go to the selected' i]"
    GO = re.compile(r"^\s*go\s*$", re.I)
    # Cada clase listada tiene su boton "View details" con el nombre en el aria-label:
    # "View details, A1.1-12PM04 JOSE CELESTINO MUTIS"
    VER_DETALLES = "button[id^='ViewDetailsId_']"
    # El paginador dice cuantas clases hay en total: "1 - 10 of 14"
    RESUMEN_PAGINAS = re.compile(r"(\d+)\s*-\s*(\d+)\s+of\s+(\d+)", re.I)
    # Mensaje de la propia pagina cuando los filtros no trajeron nada
    SIN_CLASES = re.compile(r"no classes to display|no hay clases", re.I)
    # Paginador: los numeros y la flecha son <a role="button" class="c-pagination__link">, no <button>
    ENLACE_PAGINA = "a.c-pagination__link"
    SIGUIENTE_PAGINA = "a.c-pagination__link--next, a[aria-label='Next Page' i]"

    def elegir_curso(self, libro, nivel=None):
        """Escribe el libro en el buscador y escoge de la lista la opcion "<libro> <nivel>"."""
        campo = self.page.locator(self.CURSO)
        try:
            expect(campo).to_be_visible(timeout=20_000)
        except AssertionError:
            raise ValueError("No encontre el buscador de curso ('Go to') en Progress")
        print(f"  Curso: {libro}")
        campo.click()
        campo.fill(libro)
        self.esperar(2_000)  # la lista de coincidencias se carga despues de escribir

        if not nivel:
            return self

        # En la lista el curso aparece como el libro seguido del nivel: "Speak Your Mind Level 1"
        curso = f"{libro} {nivel}"
        opcion = self.page.get_by_text(self.texto_exacto(curso)).first
        try:
            expect(opcion).to_be_visible(timeout=10_000)
        except AssertionError:
            raise ValueError(f"No encontre '{curso}' en la lista de cursos")
        print(f"  Clic en el curso: {curso}")
        opcion.click()
        self.esperar(2_000)
        return self

    def presionar_go(self, intentos=3):
        """Aplica los filtros del panel "Go to".

        A veces la aplicacion responde con el listado vacio aunque la clase exista, asi que si no
        aparece nada se vuelve a presionar Go antes de darlo por vacio.
        """
        for intento in range(1, intentos + 1):
            boton = self.page.locator(self.BOTON_GO).or_(
                self.page.get_by_role("button", name=self.GO)).first
            try:
                expect(boton).to_be_visible(timeout=20_000)
            except AssertionError:
                raise ValueError("No encontre el boton 'Go' del panel 'Go to'")
            print("  Clic en: Go" + (f" (intento {intento} de {intentos})" if intento > 1 else ""))
            boton.click()
            self.page.wait_for_load_state()
            self.esperar(2_000)
            if self.esperar_clases(segundos=25):  # esperar a las tarjetas, no un tiempo fijo
                return self
            if intento < intentos:
                print("  No aparecio ninguna clase; lo intento de nuevo")
                self.esperar(4_000)
        return self

    def esperar_clases(self, segundos=40):
        """Espera a que el listado termine de cargar. Devuelve True si aparecio al menos una clase.

        La aplicacion pinta la pagina primero y trae los datos despues: sin esta espera, el bot
        podia leer el listado antes de tiempo y creer que no habia ninguna clase.
        """
        tarjetas = self.page.locator(self.VER_DETALLES).first
        aviso = self.page.get_by_text(self.SIN_CLASES).first
        try:
            # Se espera lo que ocurra primero: que aparezcan las tarjetas o el aviso de "sin clases"
            expect(tarjetas.or_(aviso)).to_be_visible(timeout=segundos * 1_000)
        except AssertionError:
            return False
        if not tarjetas.count():
            print("  La pagina dice 'No classes to display' con estos filtros")
            return False
        self.esperar(1_500)  # dar tiempo a que terminen de pintarse las demas tarjetas
        return True

    def clases(self):
        """Nombres de las clases listadas, sacados del aria-label de cada boton "View details"."""
        self.esperar_clases()
        etiquetas = self.page.locator(self.VER_DETALLES).evaluate_all(
            "botones => botones.map(b => b.getAttribute('aria-label') || '')")
        nombres = []
        for etiqueta in etiquetas:
            nombre = " ".join(re.sub(r"^\s*view details\s*,\s*", "", etiqueta, flags=re.I).split())
            if nombre:
                nombres.append(nombre)
        return nombres

    def abrir_clase(self, nombre):
        """Da clic en "View details" de esa clase."""
        boton = self.page.get_by_role("button", name=re.compile(re.escape(nombre), re.I)).first
        try:
            expect(boton).to_be_visible(timeout=15_000)
        except AssertionError:
            raise ValueError(f"No encontre la clase '{nombre}'. En Progress hay: {self.clases()}")
        print(f"  Clic en View details: {nombre}")
        boton.scroll_into_view_if_needed()
        boton.click()
        self.page.wait_for_load_state()
        self.esperar(5_000)  # los datos de la clase se cargan despues
        return DetalleClase(self.page)

    def total_paginas(self):
        """Cuantas paginas de clases hay, segun el texto "1 - 10 of 14" del paginador."""
        self.esperar_clases()  # el paginador aparece junto con las tarjetas
        texto = " ".join(self.page.locator("body").inner_text().split())
        resumen = self.RESUMEN_PAGINAS.search(texto)
        if not resumen:
            return 1  # sin paginador: todas las clases estan a la vista
        desde, hasta, total = (int(n) for n in resumen.groups())
        por_pagina = max(hasta - desde + 1, 1)
        return max(1, math.ceil(total / por_pagina))

    def siguiente_pagina(self):
        """Clic en la flecha "Next Page". Devuelve False si ya no hay mas paginas."""
        flecha = self.page.locator(self.SIGUIENTE_PAGINA)
        if not flecha.count() or flecha.first.get_attribute("aria-disabled") == "true":
            return False
        flecha.first.scroll_into_view_if_needed()
        try:
            flecha.first.click(timeout=15_000)
        except Exception:
            # Si algo tapa la flecha, se le envia el evento directamente al elemento
            print("  (algo tapaba la flecha: clic directo)")
            flecha.first.dispatch_event("click")
        self.esperar(2_000)
        self.esperar_clases()  # el listado se recarga con las clases de esa pagina
        return True

    def ir_a_pagina(self, numero):
        """Va a esa pagina: por su numero en el paginador o, si no esta, avanzando con la flecha."""
        if numero <= 1:
            return self
        enlace = self.page.locator(self.ENLACE_PAGINA).filter(has_text=self.texto_exacto(str(numero)))
        if enlace.count():
            enlace.first.scroll_into_view_if_needed()
            enlace.first.click()
            self.esperar(2_000)
            self.esperar_clases()
            return self
        for _ in range(numero - 1):
            if not self.siguiente_pagina():
                raise ValueError(f"No pude llegar a la pagina {numero} del listado de clases")
        return self

    def volver_a_clases(self):
        """Regresa a la lista de clases para seguir con la siguiente."""
        self.page.go_back()
        self.page.wait_for_load_state()
        self.esperar(1_500)
        self.esperar_clases()
        return self


class DetalleClase(Pagina):
    """Detalle de una clase: pestañas (Students, Coursework, Homework, Assessments), Filters y Export."""
    # <button id="progressExportCsv" name="Export CSV" aria-label="Export Student wise Progress summary CSV...">
    EXPORTAR = "#progressExportCsv"
    EXPORT = re.compile(r"^\s*export\s*$", re.I)  # respaldo por texto

    def exportar(self):
        """Da clic en Export y devuelve el archivo descargado (CSV con el progreso de la clase)."""
        boton = self.page.locator(self.EXPORTAR).or_(
            self.page.get_by_role("button", name=self.EXPORT)).first
        try:
            expect(boton).to_be_visible(timeout=20_000)
        except AssertionError:
            raise ValueError("No encontre el boton 'Export' de la clase")
        print("  Clic en: Export")
        boton.scroll_into_view_if_needed()
        try:
            with self.page.expect_download(timeout=60_000) as descarga:
                boton.click()
        except Exception:
            raise ValueError("Di clic en 'Export' pero no llego ningun archivo")
        return descarga.value
