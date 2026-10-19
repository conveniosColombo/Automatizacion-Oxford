"""Diagnostico E2E del bug de sincronizacion de 'My Progress' en Wide Angle Level 3.

Requiere internet y cuentas validas (Credenciales Oxford.txt); registra intentos reales.
Ejecutar:  .venv\\Scripts\\python.exe -m pytest tests/oxford/test_wide_angle_sincronizacion.py -v -s
"""
import logging
from datetime import datetime

from conftest import CAPTURAS
from pages.courses_page import CoursesPage
from pages.login_page import LoginPage
from pages.progress_page import MonitorRed, ProgressPage
from pages.unit_page import UnitPage

log = logging.getLogger("oxford.test")
UNIDADES = range(1, 7)


def _alerta_desync(pagina, monitor, unidad, antes, despues):
    log.critical("[CRITICAL_DESYNC_DETECTED] Unit %s: progreso %s -> %s (sin incremento)", unidad, antes, despues)
    CAPTURAS.mkdir(exist_ok=True)
    marca = datetime.now().strftime("%H%M%S")
    pagina.screenshot(path=str(CAPTURAS / f"desync_unit{unidad}_{marca}.png"))
    monitor.volcar(CAPTURAS / f"desync_unit{unidad}_{marca}_red.json")


def test_progreso_se_sincroniza_por_unidad(pagina, cuenta):
    monitor = MonitorRed(pagina)
    LoginPage(pagina).iniciar_sesion(cuenta["user"], cuenta["password"], cuenta["link"], cuenta.get("codigo", ""))

    cursos = CoursesPage(pagina)
    cursos.abrir_my_courses()
    cursos.abrir_libro("Wide Angle", "Level 3")
    url_libro = pagina.url

    unidad, progreso = UnitPage(pagina), ProgressPage(pagina)
    ultimo = progreso.leer_porcentaje()
    desincronizadas = []

    for n in UNIDADES:
        pagina.goto(url_libro)
        pagina.wait_for_load_state("networkidle")
        intentos = unidad.resolver_unidad(n)
        assert intentos, f"No se pudo abrir/resolver la Unit {n} (revisar selectores en unit_page.py)"

        actual = progreso.leer_porcentaje()
        if ultimo is None or actual is None or actual <= ultimo:
            _alerta_desync(pagina, monitor, n, ultimo, actual)
            desincronizadas.append(n)
        ultimo = actual if actual is not None else ultimo

    assert not monitor.errores, f"Peticiones 4xx/5xx de sincronizacion: {monitor.errores}"
    assert not desincronizadas, f"[CRITICAL_DESYNC_DETECTED] Unidades sin incremento: {desincronizadas}"
