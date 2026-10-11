"""Oxford English Hub: descarga el reporte de progreso (CSV) de cada clase del Config."""
import re

from playwright.sync_api import expect

import nucleo

NOMBRE = "Oxford"
URL_CLASES = "https://englishhub.oup.com/myOrganization/classes"


def iniciar_sesion(page, usuario, clave, link):
    page.goto(link)

    # Banner de cookies: rechazar las no esenciales
    try:
        page.locator("#onetrust-pc-btn-handler").click(timeout=8_000)
        page.get_by_role("button", name=re.compile("rechazarlas todas|reject all", re.I)).click()
    except Exception:
        pass

    # Boton de inicio de sesion en English Hub
    patron = re.compile(r"sign in|log in|iniciar sesi", re.I)
    page.get_by_role("button", name=patron).or_(page.get_by_role("link", name=patron)).first.click()

    # Formulario de login de Oxford (id.oup.com)
    page.wait_for_url(re.compile(r"id\.oup\.com"))
    # La pagina tiene varios formularios ocultos: usar el campo exacto del usuario
    page.locator("#username-or-email-address-input").fill(usuario)
    page.get_by_role("button", name="Continue", exact=True).filter(visible=True).first.click()

    # Segunda pantalla: la contrasena
    campo_clave = page.locator("input[type=password]:visible").first
    campo_clave.fill(clave)
    page.get_by_role("button", name=re.compile(r"^\s*(continue|sign in|log in)\s*$", re.I)).filter(
        visible=True).first.click()

    page.wait_for_url(re.compile(r"englishhub\.oup\.com"), timeout=60_000)
    page.wait_for_timeout(5_000)  # dar tiempo a que cargue la pagina de inicio


def abrir_menu_cuenta(page):
    page.locator("#account-menu-button").click()
    page.wait_for_timeout(2_000)  # dar tiempo a que se abra el menu


def ver_mas_organizaciones(page):
    # Enlace "+ 8 more" del menu; se busca por texto porque no tiene id y el numero puede cambiar
    page.locator("#account-menu-hub").get_by_text(re.compile(r"^\s*\+\s*\d+\s*more\s*$", re.I)).click()
    page.wait_for_timeout(2_000)  # dar tiempo a que se abra la ventana de convenios


def seleccionar_curso(page, id_curso):
    """Busca el curso por su ID en la ventana "My Organizations" y le da clic a su nombre."""
    page.locator("#MY_ORGANIZATION_MODAL").get_by_placeholder(
        re.compile("search by organization", re.I)).fill(id_curso)

    # Fila de la tabla cuya celda ID es exactamente la configurada (distingue mayusculas)
    celda_id = page.locator("td", has_text=re.compile(rf"^\s*{re.escape(id_curso)}\s*$"))
    fila = page.locator("#MY_ORGANIZATION_MODAL_TABLE tbody tr").filter(has=celda_id)
    try:
        expect(fila).to_have_count(1, timeout=15_000)
    except AssertionError:
        raise ValueError(f"No encontre el curso con ID '{id_curso}'. Revisa el ID en Config Oxford.txt")

    # El nombre es un <a> sin href en la primera celda, por eso no se busca como "link"
    enlace = fila.locator("td").first.locator("a")
    nucleo.captura(page, "oxford_paso4_busqueda.png")
    print(f"  Clic en el curso: {enlace.inner_text().strip()}")
    enlace.click()  # target="_self": abre en la misma pestana
    page.wait_for_load_state()
    page.wait_for_timeout(3_000)


def abrir_mi_organizacion(page):
    # Boton "My Organization" del menu lateral; data-testid es estable, las clases cambian con cada version
    page.get_by_test_id("MY_ORGANIZATION_BUTTON_PRIMARY_NAVIGATION_BAR").click()
    page.wait_for_url(re.compile(r"/myOrganization"))
    page.wait_for_timeout(3_000)  # dar tiempo a que cargue la pagina


def abrir_clases(page):
    # Pestana "Classes" de My Organization
    page.get_by_test_id("ORG_CLASSES").click()
    page.wait_for_url(re.compile(r"/myOrganization/classes"))
    page.wait_for_timeout(3_000)  # dar tiempo a que cargue la lista de clases


def abrir_clase(page, nombre):
    """Busca la clase por su nombre en la lista de Classes y le da clic."""
    if "/myOrganization/classes" not in page.url:
        page.goto(URL_CLASES)
    page.get_by_placeholder(re.compile("search classes", re.I)).fill(nombre)

    # <span> con el nombre exacto: la busqueda tambien puede traer nombres parecidos
    span_nombre = (page.get_by_test_id("ORG_CLASSES_CLASS_ROW_ITEM").locator("span")
                   .filter(has_not=page.locator("span"))
                   .filter(has_text=re.compile(rf"^\s*{re.escape(nombre)}\s*$", re.I)))
    try:
        expect(span_nombre).to_have_count(1, timeout=15_000)
    except AssertionError:
        raise ValueError(f"No encontre la clase '{nombre}'. Revisa Clases en Config Oxford.txt")

    print(f"  Clic en la clase: {nombre}")
    span_nombre.click()
    page.wait_for_load_state()
    page.wait_for_timeout(3_000)


def abrir_progreso(page):
    # Pestana "Progress" de la clase
    page.get_by_test_id("CLASS_PROGRESS").click()
    page.wait_for_url(re.compile(r"/progress/"))
    page.wait_for_timeout(3_000)  # dar tiempo a que carguen los porcentajes


def abrir_curso_con_avance(page):
    """En Progress da clic en el curso que tiene porcentaje de avance (el otro dice "No data available")."""
    # Numero con % (ej. 42.9%); "NaN%" no cuenta porque no tiene digitos
    con_avance = page.locator("tbody tr.hoverable").filter(has_text=re.compile(r"\d\s*%"))
    try:
        expect(con_avance.first).to_be_visible(timeout=20_000)
    except AssertionError:
        raise ValueError("No encontre ningun curso con porcentaje de avance en Progress")
    if con_avance.count() > 1:
        con_avance = con_avance.filter(has_text=re.compile("closing soon", re.I))
    if con_avance.count() != 1:
        raise ValueError(f"Hay {con_avance.count()} cursos con porcentaje de avance; no se cual abrir")

    # Primera celda = nombre del curso; si tiene un enlace o boton, se le da clic a ese
    celda = con_avance.locator("td").first
    clicable = celda.locator("a, button")
    objetivo = clicable.first if clicable.count() else celda
    print(f"  Clic en el curso: {' '.join(celda.inner_text().split())}")
    objetivo.click()
    page.wait_for_load_state()
    page.wait_for_timeout(3_000)


def abrir_ajustes_progreso(page):
    page.get_by_role("button", name=re.compile(r"^\s*progress settings\s*$", re.I)).click()
    expect(page.locator("#gradebook-progress-settings")).to_be_visible()


def aplicar_ajustes(page, config):
    """Pone en la ventana Progress settings los parametros del config."""
    dialogo = page.locator("#gradebook-progress-settings")

    # Scores: lista desplegable
    valor = config["scores"]
    select = dialogo.locator("select").first
    opciones = [o.strip() for o in select.locator("option").all_inner_texts()]
    elegida = next((o for o in opciones if o.lower() == valor.lower()), None)
    if not elegida:
        raise ValueError(f"Scores '{valor}' no existe. Opciones: {opciones}")
    select.select_option(label=elegida)
    print(f"  Scores: {elegida}")

    # Show figures as / Show scores for: opciones tipo radio, se eligen con clic en su texto
    for clave in ("show figures as", "show scores for"):
        valor = config[clave]
        opcion = dialogo.get_by_text(re.compile(rf"^\s*{re.escape(valor)}\s*$", re.I))
        if not opcion.count():
            raise ValueError(f"'{valor}' no es una opcion de '{clave}' en Progress settings")
        opcion.first.click()
        print(f"  {clave}: {valor}")
    page.wait_for_timeout(2_000)  # la tabla se actualiza con los nuevos ajustes


def cerrar_ajustes(page):
    """Cierra Progress settings con un clic fuera de la ventana (o con Close si ese clic no la cierra)."""
    dialogo = page.locator("#gradebook-progress-settings")
    # Clic sobre el titulo de la pagina: fuera de la ventana y sin enlaces que cambien de pagina
    titulo = page.locator("h1:visible").filter(has_not_text=re.compile("progress settings", re.I)).first
    caja = titulo.bounding_box()
    if caja:
        page.mouse.click(caja["x"] + 10, caja["y"] + caja["height"] / 2)
    try:
        expect(dialogo).to_be_hidden(timeout=5_000)
    except AssertionError:
        dialogo.get_by_role("button", name=re.compile("close", re.I)).click()
        expect(dialogo).to_be_hidden()


def descargar_csv(page, clase):
    """Da clic en Download CSV y guarda el archivo en Descargas/Oxford."""
    with page.expect_download(timeout=60_000) as info:
        page.get_by_role("button", name=re.compile(r"^\s*download csv\s*$", re.I)).click()
    return nucleo.guardar_descarga(info.value, NOMBRE, clase)


def ejecutar(page, config, credenciales):
    id_curso = config["id"]
    clases = [c.strip() for c in config["clases"].split(",") if c.strip()]

    iniciar_sesion(page, credenciales["user"], credenciales["password"], credenciales["link"])
    print("Paso 1: sesion iniciada.")
    abrir_menu_cuenta(page)
    print("Paso 2: menu de la cuenta abierto.")
    ver_mas_organizaciones(page)
    print("Paso 3: clic en '+ more', lista de convenios abierta.")
    seleccionar_curso(page, id_curso)
    print(f"Paso 4: curso con ID '{id_curso}' abierto.")
    abrir_mi_organizacion(page)
    print("Paso 5: My Organization abierto.")
    abrir_clases(page)
    print("Paso 6: Classes abierto.")

    for clase in clases:
        try:
            abrir_clase(page, clase)
            print(f"Paso 7: clase '{clase}' abierta.")
            abrir_progreso(page)
            print("Paso 8a: Progress abierto.")
            abrir_curso_con_avance(page)
            print("Paso 8b: curso con porcentaje de avance abierto.")
            abrir_ajustes_progreso(page)
            print("Paso 9: Progress settings abierto.")
            aplicar_ajustes(page, config)
            print("Paso 10: parametros aplicados.")
            cerrar_ajustes(page)
            print("Paso 11: Progress settings cerrado.")
            archivo = descargar_csv(page, clase)
            print(f"Paso 12: CSV guardado en {archivo}")
        except Exception as error:
            print(f"FALLO en la clase {clase}: {nucleo.resumen(error)}")
