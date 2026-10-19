"""Fixtures especificas de Oxford English Hub.

Requieren conexion a internet y cuentas validas en 'Credenciales Oxford.txt' (raiz del proyecto);
no se pueden correr en CI/desatendido. Las pruebas ESCRIBEN intentos reales en la cuenta usada,
por eso conviene usar una cuenta de prueba.
"""
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
CAPTURAS = RAIZ / "Capturas"
sys.path.insert(0, str(Path(__file__).parent))  # `from pages...` sin chocar con core/sistemas de los bots

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def leer_cuentas(nombre="Credenciales Oxford.txt"):
    """Cada 'User' repetido empieza una cuenta nueva (lineas 'Clave : valor', '#' comenta)."""
    ruta = RAIZ / nombre
    cuentas, actual = [], {}
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        if ":" not in linea or linea.strip().startswith("#"):
            continue
        clave, valor = (x.strip() for x in linea.split(":", 1))
        clave = clave.lower()
        if clave.startswith("codigo organiza") or clave.startswith("código organiza"):
            clave = "codigo"  # tolera la tilde de 'Organización'
        if clave == "user" and actual:
            cuentas.append(actual)
            actual = {}
        actual[clave] = valor
    if actual:
        cuentas.append(actual)
    return [c for c in cuentas if c.get("user") and c.get("password") and c.get("link")]


def pytest_generate_tests(metafunc):
    if "cuenta" in metafunc.fixturenames:
        cuentas = leer_cuentas()
        metafunc.parametrize("cuenta", cuentas, ids=[c["user"] for c in cuentas])


@pytest.fixture
def navegador():
    with sync_playwright() as p:
        nav = None
        for canal in ("msedge", "chrome"):  # igual que los bots: no se empaqueta navegador
            try:
                nav = p.chromium.launch(channel=canal, headless=False, slow_mo=200)
                break
            except Exception:
                continue
        nav = nav or p.chromium.launch(headless=False, slow_mo=200)
        yield nav
        nav.close()


@pytest.fixture
def pagina(navegador, request):
    ctx = navegador.new_context(viewport={"width": 1400, "height": 900})
    ctx.set_default_timeout(30_000)
    ctx.tracing.start(screenshots=True, snapshots=True)
    page = ctx.new_page()
    yield page
    rep = getattr(request.node, "rep_call", None)
    if rep is not None and rep.failed:
        CAPTURAS.mkdir(exist_ok=True)
        base = re.sub(r"[^\w.-]+", "_", request.node.name) + datetime.now().strftime("_%H%M%S")
        page.screenshot(path=str(CAPTURAS / f"{base}.png"))
        ctx.tracing.stop(path=str(CAPTURAS / f"{base}_traza.zip"))
    else:
        ctx.tracing.stop()
    ctx.close()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    resultado = yield
    setattr(item, "rep_" + call.when, resultado.get_result())
