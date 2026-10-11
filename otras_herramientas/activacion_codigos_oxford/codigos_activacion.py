"""
Activación de códigos de acceso en Oxford English Hub.

Asume que ya existe un contexto de navegador AUTENTICADO y que la página
está en la vista principal de la plataforma (el login se maneja aparte).

Columnas esperadas en el Excel:
    Usuario | Contrasena | Codigo_Ebook | Codigo_Practica

Fase actual: solo se activa Codigo_Ebook (Codigo_Practica se implementa después).
"""

import re
import sys
import traceback
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

URL_HUB = "https://englishhub.oup.com"

# Como .exe, la planilla y las capturas van junto al ejecutable (no en la carpeta temporal donde se descomprime)
ES_EXE = getattr(sys, "frozen", False)

# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
if ES_EXE:
    RUTA_EXCEL = Path(sys.executable).resolve().parent / "codigos_oxford.xlsx"
else:
    RUTA_EXCEL = Path(__file__).parent / "codigos_oxford.xlsx"
COLUMNAS_REQUERIDAS = ["Usuario", "Contrasena", "Codigo_Ebook", "Codigo_Practica"]
# Opcional: ID de organización (solo se usa si Oxford lo pide al iniciar sesión)
COLUMNA_ORGANIZACION = "Organizacion"
# Columnas que el script escribe en la planilla al terminar cada estudiante
COLUMNA_ESTADO = "Estado"      # ACTIVADO | ERROR
COLUMNA_DETALLE = "Detalle"
TIMEOUT_MS = 15_000
TEXTO_EXITO = "Code activated successfully"
TEXTO_YA_ACTIVADO = "This code has already been activated"
# True: el navegador NO se cierra al terminar (para validar a mano). El .exe siempre va en False.
MODO_PRUEBA = not ES_EXE

# Selectores (tomados del DOM real de englishhub.oup.com)
# <a data-testid="MY_COURSES_BUTTON_PRIMARY_NAVIGATION_BAR" href="/myCourses" aria-label="My Courses">
SEL_MY_COURSES = "a[data-testid='MY_COURSES_BUTTON_PRIMARY_NAVIGATION_BAR']"
# Botón en el cuerpo de la página: <button><span>Enter a code</span></button>
SEL_ENTER_CODE = "main button:has-text('Enter a code')"
# Modal "What type of code do you have?" (aparece al pulsar Enter a code)
# <label data-testid="ENTER_CODE_MODAL_ENTER_PRODUCT_CODE_RADIO" for="enter-product-code-radio">
SEL_RADIO_PRODUCTO = "[data-testid='ENTER_CODE_MODAL_ENTER_PRODUCT_CODE_RADIO']"
# <button aria-label="Next" data-testid="ENTER_CODE_MODAL_CONFIRM_BUTTON">
SEL_BTN_NEXT = "[data-testid='ENTER_CODE_MODAL_CONFIRM_BUTTON']"
# Menú de la cuenta: <button id="account-menu-button"> y dentro <button data-testid="SIGN_OUT_ACC_WIDGET">Sign out
SEL_MENU_CUENTA = "#account-menu-button"
SEL_SIGN_OUT = "[data-testid='SIGN_OUT_ACC_WIDGET']"
# <input id="enterAccessCode-input" name="enterAccessCode" placeholder="1111-2222-3333">
SEL_INPUT_CODIGO = "#enterAccessCode-input"
# <button id="PopoutNavFooterNextButtonRestyle" aria-label="Activate code">
SEL_BTN_ACTIVAR = "#PopoutNavFooterNextButtonRestyle"
# <button data-testid="Cancel-button">Cancel</button>
SEL_BTN_CANCELAR = "[data-testid='Cancel-button']"


# --------------------------------------------------------------------------- #
# Lectura de datos
# --------------------------------------------------------------------------- #
def leer_excel(ruta: Path) -> list[dict]:
    """Lee el Excel y devuelve una lista de filas (dict) con las columnas requeridas."""
    wb = load_workbook(ruta, read_only=True, data_only=True)
    filas = wb.active.iter_rows(values_only=True)
    encabezados = [str(c).strip() if c is not None else "" for c in next(filas)]

    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in encabezados]
    if faltantes:
        raise ValueError(f"Faltan columnas en el Excel: {faltantes}")

    registros = []
    for num_fila, fila in enumerate(filas, start=2):  # la fila 1 son los encabezados
        reg = {
            enc: ("" if val is None else str(val).strip())
            for enc, val in zip(encabezados, fila)
        }
        if any(reg.get(c) for c in COLUMNAS_REQUERIDAS):  # saltar filas vacías
            reg["_fila"] = num_fila  # fila real en la hoja, para escribir el estado
            registros.append(reg)
    wb.close()
    return registros


def marcar_estado(ruta: Path, num_fila: int, estado: str, detalle: str) -> None:
    """Escribe el estado (y su detalle) de un estudiante en la propia planilla.

    Crea las columnas 'Estado' y 'Detalle' si no existen. Si la planilla está abierta en Excel
    no se puede guardar: se avisa y se sigue (el resumen final igual se guarda aparte).
    """
    try:
        wb = load_workbook(ruta)
        ws = wb.active
        encabezados = {str(c.value).strip(): c.column for c in ws[1] if c.value is not None}
        for nombre in (COLUMNA_ESTADO, COLUMNA_DETALLE):
            if nombre not in encabezados:
                encabezados[nombre] = ws.max_column + 1
                ws.cell(row=1, column=encabezados[nombre], value=nombre).font = Font(bold=True)
        ws.cell(row=num_fila, column=encabezados[COLUMNA_ESTADO], value=estado)
        ws.cell(row=num_fila, column=encabezados[COLUMNA_DETALLE], value=detalle)
        wb.save(ruta)
        wb.close()
    except PermissionError:
        print(f"    AVISO: no pude escribir el estado en {ruta.name} (¿está abierta en Excel? Ciérrala).")
    except Exception as e:  # noqa: BLE001
        print(f"    AVISO: no pude escribir el estado en la planilla: {e}")


# --------------------------------------------------------------------------- #
# Automatización
# --------------------------------------------------------------------------- #
def abrir_navegador(p):
    """Usa Edge (viene con Windows) o Chrome, así el .exe no tiene que traer su propio navegador."""
    for canal in ("msedge", "chrome"):
        try:
            return p.chromium.launch(channel=canal, headless=False, slow_mo=300)
        except Exception:  # noqa: BLE001
            pass
    return p.chromium.launch(headless=False, slow_mo=300)


def _rechazar_cookies(page: Page) -> None:
    """Banner de cookies: rechazar las no esenciales (si aparece)."""
    try:
        page.locator("#onetrust-pc-btn-handler").click(timeout=5_000)
        page.get_by_role("button", name=re.compile("rechazarlas todas|reject all", re.I)).click()
    except Exception:  # noqa: BLE001
        pass


def iniciar_sesion(page: Page, usuario: str, clave: str, organizacion: str = "") -> None:
    """Login en Oxford English Hub; si Oxford pide 'Organization ID', lo llena con `organizacion`."""
    page.goto(URL_HUB)
    _rechazar_cookies(page)

    patron = re.compile(r"sign in|log in|iniciar sesi", re.I)
    boton_entrar = page.get_by_role("button", name=patron).or_(page.get_by_role("link", name=patron)).first

    # Oxford guarda la sesión también fuera de las cookies: puede abrir ya logueado (como el usuario
    # anterior). Si se ve el menú de la cuenta en vez de "Sign in", se cierra esa sesión primero.
    page.locator(SEL_MENU_CUENTA).or_(boton_entrar).first.wait_for(state="visible", timeout=TIMEOUT_MS)
    if page.locator(SEL_MENU_CUENTA).is_visible():
        print("    Aviso: había una sesión abierta; la cierro antes de entrar.")
        cerrar_sesion(page)
        page.goto(URL_HUB)
        _rechazar_cookies(page)

    boton_entrar.click()

    page.wait_for_url(re.compile(r"id\.oup\.com"))
    page.locator("#username-or-email-address-input").fill(usuario)
    page.get_by_role("button", name="Continue", exact=True).filter(visible=True).first.click()

    # Pantalla opcional: "Enter your organization ID"
    pide_org = page.get_by_role("heading", name=re.compile("organization id", re.I))
    try:
        pide_org.wait_for(state="visible", timeout=4_000)
    except PlaywrightTimeoutError:
        pide_org = None

    if pide_org is not None:
        # Si Oxford ya recuerda el ID (muestra "18xaf  Change") no hay campo: solo se pulsa Continue.
        # Si hay campo vacío, se escribe el ID de la columna Organizacion.
        campo_org = page.locator("input[type=text]:visible").first
        if campo_org.count():
            if not organizacion:
                raise RuntimeError(f"Oxford pide Organization ID para '{usuario}' y la columna "
                                   f"'{COLUMNA_ORGANIZACION}' está vacía")
            campo_org.fill(organizacion)
        page.get_by_role("button", name="Continue", exact=True).filter(visible=True).first.click()

    campo_clave = page.locator("input[type=password]:visible").first
    campo_clave.fill(clave)
    page.get_by_role("button", name=re.compile(r"^\s*(continue|sign in|log in)\s*$", re.I)).filter(
        visible=True).first.click()

    page.wait_for_url(re.compile(r"englishhub\.oup\.com"), timeout=60_000)
    page.wait_for_timeout(5_000)  # dar tiempo a que cargue la página de inicio


def ir_a_my_courses(page: Page) -> None:
    """Hace clic en 'My Courses' y espera a que cargue el dashboard."""
    page.wait_for_selector(SEL_MY_COURSES, state="visible", timeout=TIMEOUT_MS)
    page.locator(SEL_MY_COURSES).first.click()
    page.wait_for_url("**/myCourses**", timeout=TIMEOUT_MS)
    # La SPA carga el contenido después de la URL: esperamos el botón del dashboard
    page.wait_for_selector(SEL_ENTER_CODE, state="visible", timeout=TIMEOUT_MS)


def cerrar_modal_si_abierto(page: Page) -> None:
    """Cierra el modal 'Activate code' si quedó abierto (para no bloquear el siguiente registro)."""
    try:
        cancelar = page.locator(SEL_BTN_CANCELAR)
        if cancelar.is_visible():
            cancelar.click()
            page.wait_for_selector(SEL_INPUT_CODIGO, state="hidden", timeout=5_000)
    except Exception:  # noqa: BLE001
        pass


def _activar_un_codigo(page: Page, codigo: str, etiqueta: str) -> str:
    """
    Con el panel de códigos abierto: (si aparece) elige 'Product access code' + Next, escribe el
    código, pulsa 'Activate code' y espera el resultado.
    Devuelve 'activado' o 'ya_activado'; lanza RuntimeError con cualquier otro error.
    """
    # Puede aparecer primero la pantalla "What type of code do you have?" o directo el campo
    page.locator(f"{SEL_RADIO_PRODUCTO}, {SEL_INPUT_CODIGO}").first.wait_for(
        state="visible", timeout=TIMEOUT_MS)
    if page.locator(SEL_RADIO_PRODUCTO).is_visible():
        print(f"    [{etiqueta}] Paso: eligiendo 'Product access code' y 'Next'.")
        page.locator(SEL_RADIO_PRODUCTO).click()
        page.wait_for_selector(SEL_BTN_NEXT, state="visible", timeout=TIMEOUT_MS)
        page.locator(SEL_BTN_NEXT).click()

    page.wait_for_selector(SEL_INPUT_CODIGO, state="visible", timeout=TIMEOUT_MS)
    campo = page.locator(SEL_INPUT_CODIGO)
    campo.fill("")
    campo.fill(codigo)
    campo.press("Tab")  # dispara la validación del formulario
    print(f"    [{etiqueta}] Paso: código {codigo} escrito.")

    if campo.get_attribute("aria-invalid") == "true":
        raise RuntimeError(f"[{etiqueta}] Formato de código inválido según la plataforma")

    page.wait_for_selector(SEL_BTN_ACTIVAR, state="visible", timeout=TIMEOUT_MS)
    boton = page.locator(SEL_BTN_ACTIVAR)
    if boton.is_disabled():
        raise RuntimeError(f"[{etiqueta}] El botón 'Activate code' está deshabilitado (¿código inválido?)")

    boton.click()
    print(f"    [{etiqueta}] Paso: clic en 'Activate code' hecho, esperando confirmación...")

    # Resultado: éxito, o el panel "There was an error" (p. ej. "This code has already been activated")
    exito = page.get_by_text(TEXTO_EXITO)
    error = page.get_by_role("heading", name="There was an error")
    try:
        exito.or_(error).first.wait_for(state="visible", timeout=30_000)
    except PlaywrightTimeoutError:
        mensaje = _leer_mensaje_error(page) or _texto_pantalla(page)
        raise RuntimeError(f"[{etiqueta}] No apareció '{TEXTO_EXITO}'. Pantalla: {mensaje}") from None

    if exito.first.is_visible():
        print(f"    [{etiqueta}] Paso: '{TEXTO_EXITO}'.")
        return "activado"

    if page.get_by_text(TEXTO_YA_ACTIVADO).first.is_visible():
        print(f"    [{etiqueta}] Paso: '{TEXTO_YA_ACTIVADO}'.")
        return "ya_activado"

    raise RuntimeError(f"[{etiqueta}] Oxford respondió con error: {_texto_pantalla(page)}")


def _seguir_con_otro_codigo(page: Page, estado_anterior: str) -> None:
    """Pasa al siguiente código: 'Activate another code' si el anterior se activó, o
    'Try again with a different code' si Oxford dijo que ya estaba activado."""
    nombre = "Try again with a different code" if estado_anterior == "ya_activado" else "Activate another code"
    print(f"    Paso: clic en '{nombre}'.")
    page.get_by_role("button", name=nombre).click()


def activar_codigo_oxford(page: Page, codigo: str, codigo_practica: str = "") -> dict:
    """
    Activa el código del ebook y, si se indica, el de práctica online (en el mismo panel,
    con 'Activate another code').

    Retorna un dict con: codigo, codigo_practica, estado ('OK' | 'ERROR'), detalle.
    """
    resultado = {"codigo": codigo, "codigo_practica": codigo_practica, "estado": "ERROR", "detalle": ""}

    if not codigo:
        resultado["detalle"] = "Código vacío"
        return resultado

    try:
        # 1. Ir a My Courses
        ir_a_my_courses(page)

        # 2. Clic en "Enter a code"
        page.wait_for_selector(SEL_ENTER_CODE, state="visible", timeout=TIMEOUT_MS)
        page.locator(SEL_ENTER_CODE).first.click()

        # 3. Ebook
        estado_ebook = _activar_un_codigo(page, codigo, "Ebook")
        detalle = "Ebook activado" if estado_ebook == "activado" else "Ebook ya estaba activado"

        # 4. Práctica online: seguir con otro código (también si el ebook ya estaba activado)
        if codigo_practica:
            _seguir_con_otro_codigo(page, estado_ebook)
            estado_practica = _activar_un_codigo(page, codigo_practica, "Práctica")
            detalle += ("; Práctica activada" if estado_practica == "activado"
                        else "; Práctica ya estaba activada")

        resultado["estado"] = "OK"
        resultado["detalle"] = detalle

    except RuntimeError as e:
        resultado["detalle"] = str(e)
    except PlaywrightTimeoutError as e:
        resultado["detalle"] = f"Timeout esperando un selector: {e.message.splitlines()[0]}"
    except Exception as e:  # noqa: BLE001
        resultado["detalle"] = f"Error inesperado: {e}"

    if resultado["estado"] != "OK" and not MODO_PRUEBA:
        cerrar_modal_si_abierto(page)

    return resultado


def _texto_pantalla(page: Page, maximo: int = 300) -> str:
    """Texto visible de la página (resumido), para diagnosticar qué mostró Oxford."""
    try:
        return " ".join(page.locator("body").inner_text(timeout=2_000).split())[:maximo]
    except Exception:  # noqa: BLE001
        return "(no se pudo leer)"


def _leer_mensaje_error(page: Page) -> str:
    """Intenta capturar un mensaje de error visible en el modal."""
    candidatos = page.locator("[role='alert'], .error, [class*='error'], [class*='Error']")
    try:
        for i in range(candidatos.count()):
            texto = candidatos.nth(i).inner_text(timeout=1_000).strip()
            if texto:
                return texto
    except Exception:  # noqa: BLE001
        pass
    return ""


def cerrar_sesion(page: Page) -> None:
    """Cierra el panel de códigos (si sigue abierto) y hace 'Sign out' desde el menú de la cuenta."""
    try:
        cerrar = page.get_by_role("button", name=re.compile(r"^\s*Close\b", re.I)).filter(visible=True)
        if cerrar.count():
            cerrar.first.click(timeout=5_000)
    except Exception:  # noqa: BLE001
        pass  # si no hay panel que cerrar seguimos

    page.wait_for_selector(SEL_MENU_CUENTA, state="visible", timeout=TIMEOUT_MS)
    page.locator(SEL_MENU_CUENTA).click()
    page.wait_for_selector(SEL_SIGN_OUT, state="visible", timeout=TIMEOUT_MS)
    page.locator(SEL_SIGN_OUT).click()
    # Sesión cerrada: desaparece el menú de la cuenta
    page.wait_for_selector(SEL_MENU_CUENTA, state="detached", timeout=TIMEOUT_MS)
    print("    Paso: sesión cerrada.")


def esperar_cierre_manual(page: Page) -> None:
    """Mantiene vivo el script (y por tanto el navegador) hasta que la pestaña se cierre a mano.

    No depende de input(): en algunos terminales (p. ej. 'Run Python File') input() devuelve al
    instante y el navegador se cerraba apenas terminaba el script.
    """
    try:
        while not page.is_closed():
            page.wait_for_timeout(1_000)
    except Exception:  # noqa: BLE001
        pass  # el navegador se cerró


def procesar_excel(browser, ruta_excel: Path = RUTA_EXCEL) -> list[dict]:
    """Por cada fila: abre una sesión limpia, inicia sesión con sus credenciales y activa el Codigo_Ebook."""
    registros = leer_excel(ruta_excel)
    resultados = []

    # Una sola ventana/pestaña para toda la lista (con 50 usuarios no es viable abrir una por usuario)
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    page = context.new_page()
    page.set_default_timeout(TIMEOUT_MS)

    for idx, fila in enumerate(registros):
        usuario = fila["Usuario"]
        codigo_ebook = fila["Codigo_Ebook"]
        codigo_practica = fila["Codigo_Practica"]
        print(f"[{idx + 1}/{len(registros)}] {usuario} -> Ebook {codigo_ebook} | Práctica {codigo_practica}")

        # Por si la fila anterior falló y la sesión quedó abierta: empezar sin sesión previa
        context.clear_cookies()
        try:
            iniciar_sesion(page, usuario, fila["Contrasena"], fila.get(COLUMNA_ORGANIZACION, ""))
            res = activar_codigo_oxford(page, codigo_ebook, codigo_practica)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            res = {"codigo": codigo_ebook, "codigo_practica": codigo_practica,
                   "estado": "ERROR", "detalle": f"Falló: {e}"}

        res["usuario"] = usuario
        print(f"    {res['estado']}: {res['detalle']}")

        # Ya se intentaron los dos códigos: cerrar la sesión (si hubo error se deja tal cual para revisar)
        if res["estado"] == "OK":
            try:
                cerrar_sesion(page)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                res["detalle"] += f" | No se pudo cerrar la sesión: {e}"
                print(f"    AVISO: no se pudo cerrar la sesión: {e}")
        resultados.append(res)

        # Estudiante terminado: dejar el estado en la planilla (se guarda fila por fila)
        marcar_estado(ruta_excel, fila["_fila"], "ACTIVADO" if res["estado"] == "OK" else "ERROR",
                      res["detalle"])

        if res["estado"] != "OK":
            # Captura de cómo quedó la pantalla, para revisar el error después
            try:
                ruta_png = ruta_excel.parent / "Capturas" / f"error_codigos_{idx + 1}.png"
                ruta_png.parent.mkdir(exist_ok=True)
                page.screenshot(path=str(ruta_png))
                print(f"    Captura del error: {ruta_png}")
            except Exception:  # noqa: BLE001
                pass

    if not MODO_PRUEBA:
        context.close()

    salida = ruta_excel.with_name(f"{ruta_excel.stem}_resultados.xlsx")
    wb = Workbook()
    ws = wb.active
    columnas = ["usuario", "codigo", "codigo_practica", "estado", "detalle"]
    ws.append(columnas)
    for r in resultados:
        ws.append([r.get(c, "") for c in columnas])
    wb.save(salida)
    print(f"\nResultados guardados en: {salida}")
    return resultados


# --------------------------------------------------------------------------- #
# Prueba manual
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = abrir_navegador(p)
        try:
            procesar_excel(browser)
        except Exception:  # noqa: BLE001
            traceback.print_exc()  # si algo revienta, el navegador sigue abierto abajo
        if MODO_PRUEBA:
            print("Fin. El navegador sigue abierto: ciérralo tú cuando termines de validar.")
            try:
                while browser.is_connected():
                    abiertas = [pg for c in browser.contexts for pg in c.pages]
                    if not abiertas:
                        break
                    abiertas[0].wait_for_timeout(1_000)
            except Exception:  # noqa: BLE001
                pass
        else:
            browser.close()

    if ES_EXE:
        # La ventana negra no debe cerrarse sola: así se alcanza a leer el resumen
        try:
            input("\nTerminado. Presiona Enter para cerrar...")
        except EOFError:
            pass
