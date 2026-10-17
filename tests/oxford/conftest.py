"""Fixtures especificas de Oxford English Hub."""
import re

import pytest
from playwright.sync_api import sync_playwright

URL_LOGIN = "https://englishhub.oup.com"
TIEMPO_ESPERA_LOGIN_MS = 300_000  # 5 minutos para iniciar sesion a mano


def _abrir_navegador(p):
    """Usa Edge o Chrome instalados (igual que los bots): el .exe no trae navegador propio."""
    for canal in ("msedge", "chrome"):
        try:
            return p.chromium.launch(channel=canal, headless=False, slow_mo=200)
        except Exception:
            continue
    return p.chromium.launch(headless=False, slow_mo=200)


@pytest.fixture(scope="module")
def pagina_dashboard_oxford():
    """
    Abre un navegador visible en englishhub.oup.com y espera a que la persona
    inicie sesion A MANO (esta prueba no escribe usuario/clave).
    Requiere conexion a internet y una cuenta valida de Oxford English Hub;
    no se puede correr en CI/desatendido.
    """
    with sync_playwright() as p:
        navegador = _abrir_navegador(p)
        page = navegador.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(30_000)
        page.goto(URL_LOGIN)

        print(f"\n>>> Inicia sesion manualmente en Oxford English Hub en la ventana "
              f"del navegador (tienes hasta {TIEMPO_ESPERA_LOGIN_MS // 60_000} minutos).")
        page.wait_for_url(re.compile(r"myDashboard"), timeout=TIEMPO_ESPERA_LOGIN_MS)

        # Cerrar el banner de cookies sin aceptar las no esenciales
        try:
            page.get_by_text(re.compile(r"cookie settings|configuraci[oó]n de cookies", re.I)).click(timeout=5_000)
        except Exception:
            pass

        yield page
        navegador.close()
