"""Fixtures especificas de Oxford English Hub.

Requieren conexion a internet y cuentas validas en 'Credenciales Oxford.txt' (raiz del proyecto);
no se pueden correr en CI/desatendido. Las pruebas ESCRIBEN intentos reales en la cuenta usada,
por eso conviene usar una cuenta de prueba.
"""
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

# OXFORD_RAIZ: carpeta donde viven Capturas/ y las credenciales. La define 'Bot Pruebas Oxford.exe',
# porque empaquetado este archivo vive en una carpeta temporal.
RAIZ = Path(os.environ.get("OXFORD_RAIZ") or Path(__file__).resolve().parents[2])
CAPTURAS = RAIZ / "Capturas"
sys.path.insert(0, str(Path(__file__).parent))  # `from pages...` sin chocar con core/sistemas de los bots

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def leer_cuentas(nombre="Credenciales Oxford.txt"):
    """Cada 'User' repetido empieza una cuenta nueva (lineas 'Clave : valor', '#' comenta).

    Con OXFORD_CUENTAS (un JSON con [{user, password, link, codigo}]) se usan esas cuentas: asi
    la pantalla 'Usuarios' de la aplicacion decide con quien se corre, segun su Excel.
    """
    desde_json = os.environ.get("OXFORD_CUENTAS")
    if desde_json:
        cuentas = json.loads(Path(desde_json).read_text(encoding="utf-8-sig"))
        return [c for c in cuentas if c.get("user") and c.get("password") and c.get("link")]
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


@pytest.fixture(autouse=True)
def _anunciar_usuario(request):
    """Antes de cada prueba dice con que usuario va ('[[USUARIO]] usuario nivel N'); la ventana lo muestra."""
    parametros = getattr(getattr(request.node, "callspec", None), "params", {}) or {}
    cuenta = parametros.get("cuenta")
    if cuenta:
        print(f"\n[[USUARIO]] {cuenta['user']} nivel {os.environ.get('OXFORD_NIVEL', '3')}", flush=True)
    yield


@pytest.fixture
def navegador():
    # Pausa en milisegundos tras CADA accion de Playwright (cada paso del arrastre cuenta). 200 era muy lento;
    # con OXFORD_SLOWMO se puede subir si algun arrastre falla.
    pausa = int(os.environ.get("OXFORD_SLOWMO", "60"))
    with sync_playwright() as p:
        nav = None
        for canal in ("msedge", "chrome"):  # igual que los bots: no se empaqueta navegador
            try:
                nav = p.chromium.launch(channel=canal, headless=False, slow_mo=pausa)
                break
            except Exception:
                continue
        nav = nav or p.chromium.launch(headless=False, slow_mo=pausa)
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
    informe = resultado.get_result()
    setattr(item, "rep_" + call.when, informe)
    if call.when == "call" or (call.when == "setup" and informe.failed):
        # Linea interna que lee la ventana de progreso de la aplicacion: "[[PRUEBA]] usuario resultado"
        cuenta = getattr(item, "callspec", None) and item.callspec.params.get("cuenta", {})
        usuario = (cuenta or {}).get("user", item.name)
        detalle, resultado_txt = "", "OK" if informe.passed else "FALLO"
        propiedades = dict(getattr(item, "user_properties", []))
        bloqueadas = propiedades.get("bloqueadas", "")
        activacion = propiedades.get("activacion", "")          # codigos que se activaron en esta corrida
        avisos = propiedades.get("avisos", "")                  # actividades que no se pudieron resolver
        if informe.passed:
            detalle = "; ".join(p for p in (f"codigos activados: {activacion}" if activacion else "",
                                            f"unidades bloqueadas: {bloqueadas}" if bloqueadas else "",
                                            f"actividades sin resolver: {avisos}" if avisos else "") if p)
        if not informe.passed:
            # Resumen en UNA linea para la columna 'Estado' del Excel: "06/01/03: motivo | ..."
            mensaje = getattr(getattr(informe.longrepr, "reprcrash", None), "message", "") or str(informe.longrepr)
            mensaje = mensaje or str(informe.longrepr)
            if "BLOQUEADO:" in mensaje:
                resultado_txt = "BLOQUEADO"
                detalle = mensaje.split("BLOQUEADO:", 1)[1].splitlines()[0].strip()
            else:
                lineas = [l.strip() for l in mensaje.splitlines()[1:] if l.strip()]
                detalle = (" | ".join(l[:90] for l in lineas if re.match(r"(\d\d/\d\d/\d\d|navegacion):", l))
                           or mensaje.splitlines()[0][:200])
                if bloqueadas:
                    detalle += f" | unidades bloqueadas: {bloqueadas}"
                if activacion:
                    detalle += f" | codigos activados: {activacion}"
        print(f"\n[[PRUEBA]] {usuario} {resultado_txt} {detalle}".rstrip(), flush=True)
