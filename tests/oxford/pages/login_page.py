"""Page Object del inicio de sesion de Oxford English Hub (mismo flujo que el bot)."""
import logging
import re

from playwright.sync_api import Page

log = logging.getLogger("oxford.login")


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def iniciar_sesion(self, usuario: str, clave: str, link: str, codigo_organizacion: str = "") -> None:
        page = self.page
        log.info("Abriendo %s", link)
        page.goto(link)

        # Banner de cookies: rechazar las no esenciales
        try:
            page.locator("#onetrust-pc-btn-handler").click(timeout=8_000)
            page.get_by_role("button", name=re.compile("rechazarlas todas|reject all", re.I)).click()
        except Exception:
            pass

        patron = re.compile(r"sign in|log in|iniciar sesi", re.I)
        page.get_by_role("button", name=patron).or_(page.get_by_role("link", name=patron)).first.click()

        page.wait_for_url(re.compile(r"id\.oup\.com"))
        campo_usuario = page.locator("#username-or-email-address-input")
        campo_usuario.wait_for(state="visible")
        campo_usuario.fill(usuario)
        page.get_by_role("button", name="Continue", exact=True).filter(visible=True).first.click()

        # Tras el usuario, id.oup.com puede pedir el Organization ID antes de la contraseña
        campo_clave = page.locator("input[type=password]:visible").first
        campo_org = page.get_by_role("textbox", name=re.compile("organi[sz]ation id", re.I))
        campo_clave.or_(campo_org).first.wait_for(state="visible")
        if campo_org.count() and campo_org.first.is_visible():
            assert codigo_organizacion, "Oxford pide el Organization ID: agrega 'Codigo Organizacion : ...' a la cuenta en Credenciales Oxford.txt"
            log.info("Ingresando el codigo de organizacion")
            campo_org.first.fill(codigo_organizacion)
            page.get_by_role("button", name="Continue", exact=True).filter(visible=True).first.click()
        campo_clave.wait_for(state="visible")
        campo_clave.fill(clave)
        page.get_by_role("button", name=re.compile(r"^\s*(continue|sign in|log in)\s*$", re.I)).filter(
            visible=True).first.click()

        # El host debe ser englishhub (la URL de id.oup.com tambien lo contiene en redirect_uri)
        page.wait_for_url(re.compile(r"^https://englishhub\.oup\.com"), timeout=60_000)
        page.wait_for_load_state("networkidle")
        self._ingresar_codigo_organizacion(codigo_organizacion)
        log.info("Sesion iniciada: %s", page.url)

    def _ingresar_codigo_organizacion(self, codigo: str) -> None:
        """Las cuentas nuevas pasan por /register-choice, que pide el 'Organization ID' una sola vez.

        El formulario puede estar en la pagina o en un iframe, por eso se busca en todos los marcos.
        """
        page = self.page
        campo = None
        for _ in range(40):  # hasta ~20 s: la pantalla aparece unos segundos despues del login
            for marco in page.frames:
                candidato = marco.get_by_role("textbox", name=re.compile("organi[sz]ation id", re.I))
                if candidato.count() and candidato.first.is_visible():
                    campo = candidato.first
                    break
            if campo:
                break
            page.wait_for_timeout(500)
        if not campo:
            return  # la cuenta ya esta asociada a su organizacion
        assert codigo, "Oxford pide el Organization ID: agrega 'Codigo Organizacion : ...' a la cuenta en Credenciales Oxford.txt"
        log.info("Ingresando el codigo de organizacion")
        campo.fill(codigo)
        campo.press("Enter")
        campo.wait_for(state="hidden", timeout=30_000)
        page.wait_for_load_state("networkidle")
