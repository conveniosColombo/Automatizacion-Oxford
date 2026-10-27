"""Flujo E2E de Wide Angle Level 3 (version 'Closing soon'): login -> My Courses -> libro -> Practice.

Requiere internet y cuentas de PRUEBA en 'Credenciales Oxford.txt' (una por bloque 'User'); estas pruebas
ESCRIBEN intentos reales (Check answers) en el libro de notas de la cuenta, no usar cuentas de alumnos reales.

Variables de entorno opcionales:
    OXFORD_UNIDADES      unidades a resolver, por defecto "1,2,3" (cada una incluye su Unit Test)
    OXFORD_ACTIVIDADES   solo estas claves 'UU/LL/AA' (ej. "01/02/01,03/02/04"), para depurar una actividad

Ejecutar:
    py -3.14 -m pytest tests/oxford/test_wide_angle_practica.py -v -s            # resuelve todo
    py -3.14 -m pytest tests/oxford/test_wide_angle_practica.py -k navegacion    # solo abre actividades (lectura)
"""
import logging
import os

import pytest

from pages.courses_page import CoursesPage
from pages.login_page import LoginPage
from pages.practica_page import NIVEL, PracticaPage, cargar_banco

log = logging.getLogger("oxford.test.practica")


def _unidades() -> list[int]:
    return [int(n) for n in os.environ.get("OXFORD_UNIDADES", "1,2,3").split(",") if n.strip()]


def _claves_de(unidad: int, banco: dict) -> list[str]:
    """Actividades de la unidad (indice impar) y de su Unit Test (el par siguiente), en orden."""
    prefijos = (f"{2 * unidad - 1:02d}/", f"{2 * unidad:02d}/")
    claves = sorted(k for k in banco if k.startswith(prefijos))
    filtro = os.environ.get("OXFORD_ACTIVIDADES")
    if filtro:
        permitidas = {c.strip() for c in filtro.split(",")}
        claves = [k for k in claves if k in permitidas]
    return claves


@pytest.fixture
def practica(pagina, cuenta):
    """Sesion iniciada y sitio de practica abierto (devuelve PracticaPage sobre la pestana nueva)."""
    LoginPage(pagina).iniciar_sesion(cuenta["user"], cuenta["password"], cuenta["link"], cuenta.get("codigo", ""))
    cursos = CoursesPage(pagina)
    cursos.abrir_my_courses()
    cursos.abrir_libro("Wide Angle", f"Level {NIVEL}")  # NIVEL sale de OXFORD_NIVEL (ver practica_page)
    return PracticaPage.abrir_desde_hub(pagina)


def test_navegacion_a_la_primera_actividad_de_cada_unidad(practica):
    """Solo lectura: confirma que la ruta /unit/UU/lesson/01/activity/01 carga el iframe en cada unidad."""
    banco = cargar_banco()
    for unidad in _unidades():
        for prefijo in (2 * unidad - 1, 2 * unidad):
            clave = f"{prefijo:02d}/01/01"
            if clave not in banco:
                continue
            practica.ir_a_actividad(clave)
            practica.esperar_actividad()
            log.info("Actividad %s carga correctamente", clave)


def test_resolver_unidades_y_tests(practica):
    """Resuelve, en orden, las actividades del banco de las unidades pedidas y sus Unit Test."""
    banco = cargar_banco()
    fallos, puntajes = [], {}
    for unidad in _unidades():
        for clave in _claves_de(unidad, banco):
            spec = banco[clave]
            if spec["tipo"] == "omitir":
                log.info("%s omitida: %s", clave, spec.get("razon", ""))
                continue
            try:
                practica.ir_a_actividad(clave)
                practica.esperar_actividad()
                obtenido, total = practica.resolver(clave, spec)
                puntajes[clave] = (obtenido, total)
                if obtenido is None:
                    fallos.append(f"{clave}: no se leyo el puntaje tras 'Check answers'")
            except Exception as exc:  # una actividad rota no debe frenar las demas
                fallos.append(f"{clave} ({spec['tipo']}): {exc}")
                log.error("%s fallo: %s", clave, exc)

    log.info("Puntajes: %s", {k: f"{o}/{t}" for k, (o, t) in puntajes.items()})
    assert puntajes, "No se resolvio ninguna actividad (revisar OXFORD_UNIDADES / OXFORD_ACTIVIDADES)"
    assert not fallos, "Actividades con error:\n" + "\n".join(fallos)
