"""Page Objects de Oxford English Hub: una clase por pantalla, con sus selectores (donde) y acciones (que hacer)."""
import re

from playwright.sync_api import expect

from core.pagina import Pagina


class InicioOxford(Pagina):
    """English Hub y el formulario de Oxford ID (id.oup.com): usuario -> Continue -> contrasena -> Continue."""
    BANNER_COOKIES = "#onetrust-pc-btn-handler"
    RECHAZAR_COOKIES = re.compile("rechazarlas todas|reject all", re.I)
    ENTRAR = re.compile(r"sign in|log in|iniciar sesi", re.I)
    USUARIO = "#username-or-email-address-input"  # la pagina tiene varios formularios ocultos: este es el exacto
    CLAVE = "input[type=password]:visible"
    CONTINUAR_CLAVE = re.compile(r"^\s*(continue|sign in|log in)\s*$", re.I)

    def iniciar_sesion(self, link, usuario, clave):
        self.page.goto(link)
        self._rechazar_cookies()
        self.page.get_by_role("button", name=self.ENTRAR).or_(
            self.page.get_by_role("link", name=self.ENTRAR)).first.click()

        self.page.wait_for_url(re.compile(r"id\.oup\.com"))
        self.page.locator(self.USUARIO).fill(usuario)
        self.page.get_by_role("button", name="Continue", exact=True).filter(visible=True).first.click()

        self.page.locator(self.CLAVE).first.fill(clave)
        self.page.get_by_role("button", name=self.CONTINUAR_CLAVE).filter(visible=True).first.click()

        self.page.wait_for_url(re.compile(r"englishhub\.oup\.com"), timeout=60_000)
        self.esperar(5_000)  # dar tiempo a que cargue la pagina de inicio
        return MenuCuenta(self.page)

    def _rechazar_cookies(self):
        """Banner de cookies: rechazar las no esenciales (si no aparece, se sigue)."""
        try:
            self.page.locator(self.BANNER_COOKIES).click(timeout=8_000)
            self.page.get_by_role("button", name=self.RECHAZAR_COOKIES).click()
        except Exception:
            pass


class MenuCuenta(Pagina):
    """Menu del boton de la cuenta (arriba a la derecha)."""
    BOTON = "#account-menu-button"
    MENU = "#account-menu-hub"
    VER_MAS = re.compile(r"^\s*\+\s*\d+\s*more\s*$", re.I)  # "+ 8 more": sin id y el numero puede cambiar

    def abrir(self):
        self.page.locator(self.BOTON).click()
        self.esperar(2_000)  # dar tiempo a que se abra el menu

    def ver_mas_organizaciones(self):
        self.page.locator(self.MENU).get_by_text(self.VER_MAS).click()
        self.esperar(2_000)  # dar tiempo a que se abra la ventana de convenios
        return VentanaOrganizaciones(self.page)


class VentanaOrganizaciones(Pagina):
    """Ventana "My Organizations" con la tabla de convenios."""
    VENTANA = "#MY_ORGANIZATION_MODAL"
    FILAS = "#MY_ORGANIZATION_MODAL_TABLE tbody tr"
    BUSCAR = re.compile("search by organization", re.I)

    def seleccionar(self, id_organizacion):
        self.page.locator(self.VENTANA).get_by_placeholder(self.BUSCAR).fill(id_organizacion)

        # Fila cuya celda ID es exactamente la configurada (distingue mayusculas, por eso sin re.I)
        celda_id = self.page.locator("td", has_text=re.compile(rf"^\s*{re.escape(id_organizacion)}\s*$"))
        fila = self.page.locator(self.FILAS).filter(has=celda_id)
        try:
            expect(fila).to_have_count(1, timeout=15_000)
        except AssertionError:
            raise ValueError(f"No encontre el curso con ID '{id_organizacion}'. Revisa el ID en la hoja Oxford de la planilla")

        # El nombre es un <a> sin href en la primera celda, por eso no se busca como "link"
        enlace = fila.locator("td").first.locator("a")
        self.captura("oxford_paso4_busqueda.png")
        print(f"  Clic en el curso: {enlace.inner_text().strip()}")
        enlace.click()  # target="_self": abre en la misma pestana
        self.page.wait_for_load_state()
        self.esperar(3_000)
        return MenuLateral(self.page)


class MenuLateral(Pagina):
    """Menu de la izquierda (Home, My Organization, My Classes...)."""
    # data-testid es estable; las clases CSS cambian con cada version de la pagina
    MI_ORGANIZACION = "MY_ORGANIZATION_BUTTON_PRIMARY_NAVIGATION_BAR"

    def ir_a_mi_organizacion(self):
        self.page.get_by_test_id(self.MI_ORGANIZACION).click()
        self.page.wait_for_url(re.compile(r"/myOrganization"))
        self.esperar(3_000)  # dar tiempo a que cargue la pagina
        return MiOrganizacion(self.page)


class MiOrganizacion(Pagina):
    """My Organization: pestana Classes y la lista de clases."""
    URL_CLASES = "https://englishhub.oup.com/myOrganization/classes"
    PESTANA_CLASES = "ORG_CLASSES"
    FILA_CLASE = "ORG_CLASSES_CLASS_ROW_ITEM"
    BUSCAR = re.compile("search classes", re.I)

    def abrir_clases(self):
        self.page.get_by_test_id(self.PESTANA_CLASES).click()
        self.page.wait_for_url(re.compile(r"/myOrganization/classes"))
        self.esperar(3_000)  # dar tiempo a que cargue la lista de clases

    def abrir_clase(self, nombre):
        if "/myOrganization/classes" not in self.page.url:
            self.page.goto(self.URL_CLASES)  # volver a la lista despues de la clase anterior
        self.page.get_by_placeholder(self.BUSCAR).fill(nombre)

        # <span> con el nombre exacto: la busqueda tambien puede traer nombres parecidos
        span_nombre = (self.page.get_by_test_id(self.FILA_CLASE).locator("span")
                       .filter(has_not=self.page.locator("span"))
                       .filter(has_text=self.texto_exacto(nombre)))
        try:
            expect(span_nombre).to_have_count(1, timeout=15_000)
        except AssertionError:
            raise ValueError(f"No encontre la clase '{nombre}'. Revisa la tabla Clase de la hoja Oxford")

        print(f"  Clic en la clase: {nombre}")
        span_nombre.click()
        self.page.wait_for_load_state()
        self.esperar(3_000)
        return PaginaClase(self.page)


class PaginaClase(Pagina):
    """Pagina de una clase (Course Material, Progress, People)."""
    PESTANA_PROGRESO = "CLASS_PROGRESS"

    def abrir_progreso(self):
        self.page.get_by_test_id(self.PESTANA_PROGRESO).click()
        self.page.wait_for_url(re.compile(r"/progress/"))
        self.esperar(3_000)  # dar tiempo a que carguen los porcentajes
        return ProgresoClase(self.page)


class ProgresoClase(Pagina):
    """Progress: cursos de la clase, ventana "Progress settings" y boton "Download CSV"."""
    FILAS_CURSO = "tbody tr.hoverable"
    CON_PORCENTAJE = re.compile(r"\d\s*%")  # ej. 42.9%; "NaN%" no cuenta porque no tiene digitos
    CERRANDO = re.compile("closing soon", re.I)
    BOTON_AJUSTES = re.compile(r"^\s*progress settings\s*$", re.I)
    AJUSTES = "#gradebook-progress-settings"
    TITULO = "h1:visible"
    DESCARGAR = re.compile(r"^\s*download csv\s*$", re.I)

    def abrir_curso_con_avance(self):
        """Clic en el curso que tiene porcentaje de avance (el otro dice "No data available")."""
        con_avance = self.page.locator(self.FILAS_CURSO).filter(has_text=self.CON_PORCENTAJE)
        try:
            expect(con_avance.first).to_be_visible(timeout=20_000)
        except AssertionError:
            raise ValueError("No encontre ningun curso con porcentaje de avance en Progress")
        if con_avance.count() > 1:
            con_avance = con_avance.filter(has_text=self.CERRANDO)
        if con_avance.count() != 1:
            raise ValueError(f"Hay {con_avance.count()} cursos con porcentaje de avance; no se cual abrir")

        # Primera celda = nombre del curso; si tiene un enlace o boton, se le da clic a ese
        celda = con_avance.locator("td").first
        clicable = celda.locator("a, button")
        objetivo = clicable.first if clicable.count() else celda
        print(f"  Clic en el curso: {' '.join(celda.inner_text().split())}")
        objetivo.click()
        self.page.wait_for_load_state()
        self.esperar(3_000)

    def aplicar_ajustes(self, scores, figuras, puntajes):
        """Abre Progress settings, pone los parametros del Config y cierra la ventana."""
        self.page.get_by_role("button", name=self.BOTON_AJUSTES).click()
        dialogo = self.page.locator(self.AJUSTES)
        expect(dialogo).to_be_visible()

        # Scores: lista desplegable
        select = dialogo.locator("select").first
        opciones = [o.strip() for o in select.locator("option").all_inner_texts()]
        elegida = next((o for o in opciones if o.lower() == scores.lower()), None)
        if not elegida:
            raise ValueError(f"Scores '{scores}' no existe. Opciones: {opciones}")
        select.select_option(label=elegida)
        print(f"  Scores: {elegida}")

        # Show figures as / Show scores for: opciones tipo radio, se eligen con clic en su texto
        for titulo, valor in (("Show figures as", figuras), ("Show scores for", puntajes)):
            opcion = dialogo.get_by_text(self.texto_exacto(valor))
            if not opcion.count():
                raise ValueError(f"'{valor}' no es una opcion de '{titulo}' en Progress settings")
            opcion.first.click()
            print(f"  {titulo}: {valor}")
        self.esperar(2_000)  # la tabla se actualiza con los nuevos ajustes
        self._cerrar_ajustes(dialogo)

    def _cerrar_ajustes(self, dialogo):
        """Clic fuera de la ventana (sobre el titulo de la pagina); si no se cierra, boton Close."""
        titulo = self.page.locator(self.TITULO).filter(has_not_text=self.BOTON_AJUSTES).first
        caja = titulo.bounding_box()
        if caja:
            self.page.mouse.click(caja["x"] + 10, caja["y"] + caja["height"] / 2)
        try:
            expect(dialogo).to_be_hidden(timeout=5_000)
        except AssertionError:
            dialogo.get_by_role("button", name=re.compile("close", re.I)).click()
            expect(dialogo).to_be_hidden()

    def descargar_csv(self):
        """Clic en Download CSV y devuelve la descarga."""
        with self.page.expect_download(timeout=60_000) as info:
            self.page.get_by_role("button", name=self.DESCARGAR).click()
        return info.value
