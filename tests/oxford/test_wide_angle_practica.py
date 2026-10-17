"""Pruebas de la practica 'Wide Angle Level 3' en Oxford English Hub.

Requieren conexion a internet y una cuenta valida de Oxford English Hub; el
login es manual (ver fixture 'pagina_dashboard_oxford' en conftest.py), por lo
que no se pueden correr en CI/desatendido.

Estas pruebas NO buscan que las actividades queden con respuestas correctas:
usan una heuristica generica (marcar casillas, elegir radios, escribir texto)
solo para ejercitar el flujo de navegacion y envio de cada actividad de las
Unidades 1, 2 y 3 del libro de practica, sin que el recorrido se rompa.
"""
import re

CURSO = "Wide Angle"
LIBRO = "Wide Angle Level 3 Online Practice"
UNIDADES_OBJETIVO = ["Unit 1 Interactions", "Unit 2 Time", "Unit 3 Learning"]
MAX_ACTIVIDADES_POR_UNIDAD = 40


def _abrir_libro_practica(page_dashboard):
    """
    Da clic en el libro de practica y devuelve la pestana nueva que abre.
    Primero intenta la tarjeta 'Last opened' del dashboard (cuentas que ya
    abrieron el libro antes); si no aparece ahi (cuentas nuevas, sin
    historial), navega por 'My Courses' -> tarjeta del curso -> enlace del
    libro en 'Course materials'.
    """
    contexto = page_dashboard.context
    page_dashboard.bring_to_front()
    if "myDashboard" not in page_dashboard.url:
        page_dashboard.goto("https://englishhub.oup.com/myDashboard")
        page_dashboard.wait_for_timeout(2_000)

    enlace_last_opened = page_dashboard.get_by_text(LIBRO, exact=True)
    try:
        enlace_last_opened.first.wait_for(timeout=5_000)
        en_last_opened = True
    except Exception:
        en_last_opened = False

    paginas_antes = set(contexto.pages)

    if en_last_opened:
        enlace_last_opened.first.click()
    else:
        print(f"  '{LIBRO}' no esta en 'Last opened'; navegando por My Courses...")
        page_dashboard.get_by_role("link", name="My Courses").click()
        page_dashboard.wait_for_timeout(2_000)
        page_dashboard.get_by_text(CURSO, exact=True).first.click()
        page_dashboard.wait_for_timeout(2_000)

        enlaces_libro = page_dashboard.get_by_text(LIBRO, exact=True)
        enlaces_libro.first.wait_for(timeout=15_000)
        enlaces_libro.first.click()  # si hay varias licencias, se usa la primera

    page_dashboard.wait_for_timeout(2_000)
    nuevas = [pg for pg in contexto.pages if pg not in paginas_antes]
    practica = nuevas[-1] if nuevas else contexto.pages[-1]
    practica.wait_for_load_state()
    practica.wait_for_timeout(2_000)
    return practica


def _abrir_unidad(page_practica, nombre_unidad):
    """Desde la grilla de unidades del libro, abre la primera actividad de la unidad dada."""
    page_practica.get_by_text(nombre_unidad, exact=True).first.click()
    page_practica.wait_for_timeout(2_000)


def _frame_actividad(page_practica):
    """La actividad vive en un iframe del reproductor de Oxford (static/player/author)."""
    for fr in page_practica.frames:
        if "static/player/author" in fr.url:
            return fr
    return None


def _contar_elementos_respondibles(frame):
    try:
        return (
            frame.get_by_role("checkbox").count()
            + frame.get_by_role("radio").count()
            + frame.locator("textarea, input[type=text], [role=textbox]").count()
        )
    except Exception:
        return 0


def _esperar_frame_actividad(page_practica, tiempo_ms=20_000):
    """
    Reintenta encontrar el iframe de la actividad y espera a que su contenido
    realmente cargue (algunas actividades, sobre todo con audio, tardan varios
    segundos en renderizar las casillas/inputs reales; el iframe existe mucho
    antes de que eso pase). Si tras el tiempo de espera no aparecio ningun
    elemento respondible, se devuelve igual el frame (puede ser un tipo de
    actividad no respondible, ej. arrastrar y soltar, o solo requiere "Next").
    """
    intervalo = 500
    transcurrido = 0
    frame = None
    while transcurrido <= tiempo_ms:
        frame = _frame_actividad(page_practica)
        if frame is not None and _contar_elementos_respondibles(frame) > 0:
            return frame
        page_practica.wait_for_timeout(intervalo)
        transcurrido += intervalo
    return frame


def _unidad_actual(page_practica):
    """Lee la barra de estado (ej. 'Unit 1 Interactions - 1.0 Behind the Photo')."""
    boton = page_practica.get_by_role("button", name=re.compile(r"^Unit \d")).first
    etiqueta = boton.get_attribute("aria-label") or boton.inner_text()
    return etiqueta.split(" - ")[0].strip()


def _resolver_actividad_generica(frame):
    """
    Interactua de forma generica con la actividad actual (sin buscar que sea
    correcta). Devuelve cuantos elementos de cada tipo logro contestar, para
    poder confirmar que si esta respondiendo y no solo avanzando.
    """
    contestados = {"checkbox": 0, "radio": 0, "texto": 0, "select": 0, "enviado": False}

    casillas = frame.get_by_role("checkbox")
    for i in range(casillas.count()):
        try:
            casillas.nth(i).click(timeout=2_000)
            contestados["checkbox"] += 1
        except Exception:
            pass  # puede estar deshabilitada (ej. ya se alcanzo el maximo de selecciones)

    radios = frame.get_by_role("radio")
    for i in range(radios.count()):
        try:
            radios.nth(i).click(timeout=2_000)
            contestados["radio"] += 1
        except Exception:
            pass

    cajas_texto = frame.locator("textarea, input[type=text], [role=textbox]")
    for i in range(cajas_texto.count()):
        caja = cajas_texto.nth(i)
        try:
            es_area = caja.evaluate("el => el.tagName.toLowerCase() === 'textarea'")
        except Exception:
            es_area = False
        texto = "This is my answer." if es_area else "answer"
        try:
            caja.fill(texto, timeout=2_000)
            contestados["texto"] += 1
        except Exception:
            pass

    listas = frame.locator("select")
    for i in range(listas.count()):
        try:
            if listas.nth(i).locator("option").count() > 1:
                listas.nth(i).select_option(index=1)
                contestados["select"] += 1
        except Exception:
            pass

    for nombre in ("Submit", "Check"):
        boton = frame.get_by_role("button", name=nombre, exact=False)
        if boton.count():
            try:
                boton.first.click(timeout=3_000)
                contestados["enviado"] = True
            except Exception:
                pass
            break

    return contestados


def _avanzar_siguiente(page_practica):
    page_practica.get_by_role("button", name="Next Activity").click(timeout=10_000)
    page_practica.wait_for_timeout(1_500)


def test_completa_actividades_unidades_1_2_3(pagina_dashboard_oxford):
    """
    Recorre las Unidades 1, 2 y 3 de 'Wide Angle Level 3 Online Practice' y
    completa cada actividad con la heuristica generica, para confirmar que el
    flujo de navegacion y envio no se rompe a lo largo de las tres unidades.
    """
    resumen = {}

    for unidad in UNIDADES_OBJETIVO:
        page_practica = _abrir_libro_practica(pagina_dashboard_oxford)
        _abrir_unidad(page_practica, unidad)

        completadas = 0
        for _ in range(MAX_ACTIVIDADES_POR_UNIDAD):
            if _unidad_actual(page_practica) != unidad:
                break
            frame = _esperar_frame_actividad(page_practica)
            if frame is not None:
                resultado = _resolver_actividad_generica(frame)
                print(f"  actividad {completadas + 1}: {resultado}")
            else:
                print(f"  actividad {completadas + 1}: sin iframe detectado, se avanza igual")
            completadas += 1
            try:
                _avanzar_siguiente(page_practica)
            except Exception:
                break  # ultima actividad de la unidad: no hay boton "Next Activity"

        resumen[unidad] = completadas
        print(f"{unidad}: {completadas} actividades completadas")
        page_practica.close()

    for unidad in UNIDADES_OBJETIVO:
        assert resumen[unidad] > 0, f"No se completo ninguna actividad en {unidad}"
