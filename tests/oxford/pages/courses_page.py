"""Page Object de /myCourses: abre la tarjeta del libro (Wide Angle Level 3)."""
import logging
import re

from playwright.sync_api import Page, expect

log = logging.getLogger("oxford.cursos")


class CoursesPage:
    BOTON_MY_COURSES = '[data-testid="MY_COURSES_BUTTON_PRIMARY_NAVIGATION_BAR"]'

    def __init__(self, page: Page):
        self.page = page

    def abrir_my_courses(self) -> None:
        # Clic directo en la barra de navegacion; no se espera a que la vista general redirija sola
        self.page.locator(self.BOTON_MY_COURSES).click()
        expect(self.page).to_have_url(re.compile(r"/myCourses"))
        # Sin 'networkidle': la tarjeta del libro (abrir_libro) o el boton 'Enter a code' ya esperan lo que necesitan
        log.info("En My Courses: %s", self.page.url)

    def tarjeta_libro(self, serie: str = "Wide Angle", nivel: str = "Level 3"):
        """Tarjeta con la serie y el nivel; si hay varias, prioriza la que dice 'closing soon'."""
        tarjetas = self.page.locator("div, a").filter(has_text=serie).filter(has_text=nivel)
        con_aviso = tarjetas.filter(has_text=re.compile("closing soon", re.I))
        if con_aviso.count():
            log.info("Tarjeta con 'closing soon' encontrada: se prioriza")
            return con_aviso.last
        return tarjetas.last

    def abrir_libro(self, serie: str = "Wide Angle", nivel: str = "Level 3") -> None:
        tarjeta = self.tarjeta_libro(serie, nivel)
        tarjeta.wait_for(state="visible")
        tarjeta.scroll_into_view_if_needed()
        tarjeta.click()
        self.page.wait_for_url(re.compile(r"/singleCourse/"), timeout=30_000)
        log.info("Libro abierto: %s %s -> %s", serie, nivel, self.page.url)
