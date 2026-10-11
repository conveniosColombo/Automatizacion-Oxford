"""Q10: inicia sesion, abre cada informe del Config, llena sus filtros y exporta el reporte."""
import re
import unicodedata

from playwright.sync_api import expect

import nucleo

NOMBRE = "Q10"
# Claves del Config que no son filtros de los informes
CLAVES_GENERALES = {"rol", "informes"}


def esperar_captcha(page):
    """Si Q10 muestra la verificacion de seguridad (Cloudflare), la tiene que resolver una persona."""
    if page.locator("#login-form-captcha").is_visible():
        input("  Q10 pide verificacion de seguridad: resuelvela en el navegador y presiona Enter aqui...")


def iniciar_sesion(page, usuario, clave, link, rol):
    page.goto(link)

    # Primera pantalla: usuario y "Siguiente"
    page.locator("#form-username").fill(usuario)
    page.locator("#btn-submit-login").click()

    # Segunda pantalla: el mismo formulario muestra la contrasena y el boton cambia a "Ingresar"
    campo_clave = page.locator("#form-password")
    expect(campo_clave).to_be_visible(timeout=15_000)
    campo_clave.fill(clave)
    esperar_captcha(page)
    page.locator("#btn-submit-login").click()

    # Ventana "Seleccione el rol" (Administrativo / Estudiante)
    opciones = page.locator("#roles a.list-group-item")
    opcion = opciones.filter(has_text=re.compile(rf"^\s*{re.escape(rol)}\s*$", re.I))
    try:
        expect(opcion).to_be_visible(timeout=30_000)
    except AssertionError:
        if "/user/login" not in page.url.lower():
            return  # la cuenta tiene un solo rol y entro directo
        if opciones.count():
            raise ValueError(f"No existe el rol '{rol}'. Opciones: {opciones.all_inner_texts()}")
        mensaje = page.locator("#login-form-messages").inner_text().strip()
        raise ValueError("No pude iniciar sesion en Q10" + (f": {mensaje}" if mensaje else ""))
    print(f"  Rol: {rol}")
    opcion.click()
    page.wait_for_url(lambda url: "/user/login" not in url.lower(), timeout=60_000)
    page.wait_for_load_state()


def abrir_informes(page):
    # Enlace "Informes" de la barra superior; se usa el enlace y no la URL porque tras el login
    # Q10 cambia de servidor (site2 -> site3) y ese numero puede variar
    page.locator("nav.q10navbar a[href='/Informes']").click()
    page.wait_for_url(re.compile(r"/Informes", re.I))
    page.wait_for_load_state()


def leer_informes(config):
    informes = [i.strip() for i in config.get("informes", "").split(",") if i.strip()]
    if not informes or informes[0].startswith("escribe_aqui"):
        raise ValueError("Escribe en 'Informes' de Config Q10.txt los informes a descargar, separados por coma")
    return informes


def leer_filtros(config):
    """Filtros con valor, en el orden del Config (los vacios se saltan). Cada uno puede tener varios valores."""
    return [(clave, [v.strip() for v in valor.split(",") if v.strip()])
            for clave, valor in config.items() if clave not in CLAVES_GENERALES and valor]


def abrir_informe(page, nombre):
    """En la pagina Informes da clic en el enlace con el nombre exacto (puede repetirse en Favoritos)."""
    enlace = page.get_by_role("link", name=nombre, exact=True).first
    try:
        expect(enlace).to_be_visible(timeout=10_000)
    except AssertionError:
        raise ValueError(f"No encontre el informe '{nombre}'. Revisa Informes en Config Q10.txt")
    print(f"  Clic en el informe: {nombre}")
    enlace.click()
    page.wait_for_load_state()
    page.wait_for_timeout(2_000)  # dar tiempo a que carguen las listas de filtros


def normalizar(texto):
    """Compara nombres sin tildes, mayusculas, '*' ni espacios de mas ("Período *" == "periodo")."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.replace("*", "").lower().split())


def buscar_campo(page, nombre):
    """Devuelve el control (select o input) del filtro cuyo titulo coincide con el nombre, o None si no existe."""
    for etiqueta in page.locator("label:visible").all():
        if normalizar(etiqueta.inner_text()) != normalizar(nombre):
            continue
        destino = etiqueta.get_attribute("for")
        if destino:
            return page.locator(f"[id='{destino}']")
        # Sin "for": el control esta en la misma fila (form-group) que el titulo
        return etiqueta.locator("xpath=ancestor::div[contains(@class,'form-group')][1]").locator("select, input")
    return None


def llenar_filtro(page, nombre, valor):
    campo = buscar_campo(page, nombre)
    if campo is None or not campo.count():
        print(f"  Filtro '{nombre}' no existe en este informe; se salta.")
        return
    campo = campo.first

    if campo.evaluate("el => el.tagName") == "SELECT":
        # Las listas dependen de la anterior (Sede -> Programa -> Periodo -> Curso): esperar a que cargue la opcion
        opcion = campo.locator("option").filter(has_text=re.compile(rf"^\s*{re.escape(valor)}\s*$", re.I))
        try:
            expect(opcion.first).to_be_attached(timeout=15_000)
        except AssertionError:
            opciones = [o.strip() for o in campo.locator("option").all_inner_texts() if o.strip()]
            raise ValueError(f"'{valor}' no es una opcion de '{nombre}'. Opciones: {opciones}")
        valor = opcion.first.inner_text().strip()  # texto exacto de Q10 (mayusculas y tildes)
        # force: Q10 puede tapar el <select> real con una lista decorada; el valor igual se cambia
        campo.select_option(label=valor, force=True)
    else:
        campo.fill(valor)
    print(f"  {nombre}: {valor}")
    page.wait_for_timeout(1_500)  # la siguiente lista se recarga segun esta
    return valor


def opciones_de(campo, nombre):
    """Todas las opciones de una lista (sin "Seleccione"), para el valor "Todos"."""
    opciones = campo.locator("option")
    try:
        # La lista se llena segun el filtro anterior: esperar a que haya algo mas que "Seleccione"
        expect(opciones.nth(1)).to_be_attached(timeout=15_000)
    except AssertionError:
        raise ValueError(f"La lista '{nombre}' no tiene opciones")
    return [o.strip() for o in opciones.all_inner_texts() if o.strip() and normalizar(o) != "seleccione"]


def llenar_y_exportar(page, informe, filtros, etiquetas=()):
    """Llena los filtros en orden y exporta. Si un filtro tiene varios valores (o "Todos"), exporta un
    reporte por cada valor; los filtros que siguen se vuelven a llenar en cada vuelta."""
    if not filtros:
        archivo = exportar(page, " ".join((informe, *etiquetas)))
        print(f"  Reporte guardado en {archivo}")
        return
    (nombre, valores), resto = filtros[0], filtros[1:]

    if [normalizar(v) for v in valores] == ["todos"]:
        campo = buscar_campo(page, nombre)
        if campo is None or not campo.count():
            print(f"  Filtro '{nombre}' no existe en este informe; se salta.")
            return llenar_y_exportar(page, informe, resto, etiquetas)
        valores = opciones_de(campo.first, nombre)
        print(f"  {nombre}: Todos ({len(valores)} opciones)")

    if len(valores) == 1:
        llenar_filtro(page, nombre, valores[0])
        return llenar_y_exportar(page, informe, resto, etiquetas)

    for numero, valor in enumerate(valores, start=1):
        print(f"  --- {nombre} {numero} de {len(valores)} ---")
        try:
            elegido = llenar_filtro(page, nombre, valor) or valor
            llenar_y_exportar(page, informe, resto, (*etiquetas, elegido))
        except Exception as error:
            print(f"  FALLO con {nombre} '{valor}': {nucleo.resumen(error)}")


def exportar(page, prefijo):
    """Da clic en Exportar y guarda el archivo; si Q10 marca campos requeridos, dice cuales."""
    boton = page.get_by_role("button", name=re.compile(r"exportar", re.I)).or_(
        page.get_by_role("link", name=re.compile(r"exportar", re.I))).first
    try:
        with page.expect_download(timeout=120_000) as info:
            boton.click()
    except Exception:
        requeridos = page.locator(".has-error label:visible, .field-validation-error:visible").all_inner_texts()
        if requeridos:
            raise ValueError(f"Q10 pide llenar: {[r.replace('*', '').strip() for r in requeridos]}")
        raise
    return nucleo.guardar_descarga(info.value, NOMBRE, prefijo)


def ejecutar(page, config, credenciales):
    informes = leer_informes(config)  # se valida antes de iniciar sesion
    filtros = leer_filtros(config)

    iniciar_sesion(page, credenciales["user"], credenciales["password"], credenciales["link"],
                   config.get("rol", "Administrativo"))
    print("Paso 1: sesion iniciada en Q10.")
    abrir_informes(page)
    print("Paso 2: Informes abierto.")

    for nombre in informes:
        try:
            if not re.search(r"/Informes/?$", page.url, re.I):
                abrir_informes(page)  # volver a la lista despues del informe anterior
            abrir_informe(page, nombre)
            print(f"Paso 3: informe '{nombre}' abierto.")
            llenar_y_exportar(page, nombre, filtros)
            print(f"Paso 4: informe '{nombre}' terminado.")
        except Exception as error:
            print(f"FALLO en el informe {nombre}: {nucleo.resumen(error)}")
