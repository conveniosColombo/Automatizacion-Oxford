"""Page Object de las unidades y actividades del libro.

OJO: los selectores de unidad/seccion/actividad se basan en texto visible (no hay
data-testid conocidos); si Oxford cambia la interfaz hay que ajustarlos aqui.
"""
import logging
import random
import re

from playwright.sync_api import Page

log = logging.getLogger("oxford.unidad")

SECCIONES_UNIDAD = ("Listening", "Vocabulary", "Grammar")  # Speaking se omite a proposito
SECCIONES_TEST = ("Grammar", "Vocabulary", "English for Real")
TEXTOS_VALIDOS = ("answer", "the", "is", "was", "have")
BOTON_ENVIAR = re.compile(r"^\s*(submit|check( answers?)?)\s*$", re.I)
BOTON_SIGUIENTE = re.compile(r"^\s*(next|continue)\s*$", re.I)


class UnitPage:
    def __init__(self, page: Page):
        self.page = page

    # ---- navegacion ----
    def _clic_texto(self, patron) -> bool:
        """Clic en el primer enlace/boton/texto visible que coincida; False si no existe."""
        for localizador in (
            self.page.get_by_role("link", name=patron),
            self.page.get_by_role("button", name=patron),
            self.page.get_by_text(patron),
        ):
            visibles = localizador.filter(visible=True)
            if visibles.count():
                el = visibles.first
                el.scroll_into_view_if_needed()
                el.click()
                self.page.wait_for_load_state("networkidle")
                return True
        return False

    def abrir_unidad(self, n: int) -> bool:
        ok = self._clic_texto(re.compile(rf"^\s*Unit\s*{n}\b(?!.*test)", re.I))
        log.info("Abrir Unit %s: %s", n, "ok" if ok else "NO ENCONTRADA")
        return ok

    def abrir_seccion(self, nombre: str) -> bool:
        ok = self._clic_texto(re.compile(rf"^\s*{re.escape(nombre)}\s*$", re.I))
        log.info("  Seccion %s: %s", nombre, "ok" if ok else "no encontrada")
        return ok

    def abrir_test_unidad(self, n: int) -> bool:
        ok = self._clic_texto(re.compile(rf"Unit\s*{n}\s*Test", re.I))
        log.info("Abrir 'Unit %s Test': %s", n, "ok" if ok else "NO ENCONTRADO")
        return ok

    # ---- resolucion de actividades ----
    def _rellenar_actividad(self) -> int:
        """Responde lo que haya visible en pantalla; devuelve cuantos campos toco."""
        page, tocados = self.page, 0
        for campo in page.locator("input[type=text]:visible, textarea:visible").all():
            try:
                if campo.is_editable():
                    campo.fill(random.choice(TEXTOS_VALIDOS))
                    tocados += 1
            except Exception:
                continue
        # Un radio al azar por grupo (name) y una casilla al azar
        grupos = {}
        for r in page.locator("input[type=radio]:visible").all():
            grupos.setdefault(r.get_attribute("name") or id(r), []).append(r)
        for opciones in grupos.values():
            try:
                random.choice(opciones).check(force=True)
                tocados += 1
            except Exception:
                continue
        casillas = page.locator("input[type=checkbox]:visible").all()
        if casillas:
            try:
                random.choice(casillas).check(force=True)
                tocados += 1
            except Exception:
                pass
        return tocados

    def resolver_actividad(self, max_pasos: int = 15) -> int:
        """Rellena y envia (Submit/Check) hasta que no haya mas pasos. Devuelve intentos enviados."""
        enviados = 0
        for _ in range(max_pasos):
            tocados = self._rellenar_actividad()
            boton = self.page.get_by_role("button", name=BOTON_ENVIAR).filter(visible=True)
            if boton.count() and boton.first.is_enabled():
                boton.first.click()
                enviados += 1
                self.page.wait_for_load_state("networkidle")
                log.info("    intento enviado (campos tocados: %s)", tocados)
            siguiente = self.page.get_by_role("button", name=BOTON_SIGUIENTE).filter(visible=True)
            if siguiente.count() and siguiente.first.is_enabled():
                siguiente.first.click()
                self.page.wait_for_load_state("networkidle")
                continue
            if not tocados:
                break
        return enviados

    def resolver_unidad(self, n: int) -> dict:
        """Listening, Vocabulary y Grammar de la unidad n + su Unit Test. Devuelve intentos por seccion."""
        resultado = {}
        if not self.abrir_unidad(n):
            return resultado
        for nombre in SECCIONES_UNIDAD:
            if self.abrir_seccion(nombre):
                resultado[nombre] = self.resolver_actividad()
        if self.abrir_test_unidad(n):
            for nombre in SECCIONES_TEST:
                if self.abrir_seccion(nombre):
                    resultado[f"Test/{nombre}"] = self.resolver_actividad()
        log.info("Unit %s -> intentos enviados: %s", n, resultado)
        return resultado
