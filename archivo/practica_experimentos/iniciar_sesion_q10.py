"""
PRACTICA 1: Inicio de sesión en Q10 paso a paso (código lineal/procedimental).
Sin clases, sin objetos ni patrones de diseño. Solo Playwright secuencial.
"""
import re
from playwright.sync_api import sync_playwright, expect

# 1. Datos para iniciar sesión
URL_LOGIN = "https://site2.q10.com/User/Login"
USUARIO = "ramon.franco@colombobogota.edu.co"
CLAVE = "Colombia2626*"
ROL_ELEGIDO = "Administrativo"

print("Iniciando Playwright...")

with sync_playwright() as p:
    # 2. Abrir el navegador (visible y con slow_mo para poder ver qué hace)
    # Intenta usar Chrome si está instalado, sino usa Chromium estándar
    try:
        browser = p.chromium.launch(channel="chrome", headless=False, slow_mo=300)
    except Exception:
        browser = p.chromium.launch(headless=False, slow_mo=300)

    # 3. Crear una pestaña nueva
    context = browser.new_context(viewport={"width": 1366, "height": 768})
    page = context.new_page()

    # ==========================================
    # PASO 1: Ir a la página de login
    # ==========================================
    print(f"\n1. Navegando a: {URL_LOGIN}")
    page.goto(URL_LOGIN)

    # ==========================================
    # PASO 2: Escribir el usuario y dar clic en Siguiente
    # ==========================================
    print(f"2. Escribiendo usuario: {USUARIO}")
    # En Q10 el input de usuario tiene el id #form-username
    page.locator("#form-username").fill(USUARIO)

    print("   Dando clic en 'Siguiente'...")
    # El botón de login tiene el id #btn-submit-login
    page.locator("#btn-submit-login").click()

    # ==========================================
    # PASO 3: Esperar el campo de contraseña
    # ==========================================
    # El campo de contraseña ya existía en la página pero estaba oculto.
    # Esperamos explícitamente a que se vuelva visible tras dar clic en Siguiente.
    print("3. Esperando que aparezca el campo de contraseña...")
    campo_clave = page.locator("#form-password")
    expect(campo_clave).to_be_visible(timeout=15_000)

    print("   Escribiendo la contraseña...")
    campo_clave.fill(CLAVE)

    # ==========================================
    # PASO 4: Verificar si aparece Captcha de Cloudflare
    # ==========================================
    captcha = page.locator("#login-form-captcha")
    if captcha.is_visible():
        print("\n⚠️ AVISO: Q10 mostró verificación de Cloudflare.")
        input("👉 Resuélvelo manualmente en la ventana del navegador y presiona Enter aquí...")

    # ==========================================
    # PASO 5: Dar clic en Ingresar
    # ==========================================
    print("4. Dando clic en 'Ingresar'...")
    # Es el mismo botón, pero ahora su texto cambió a 'Ingresar'
    page.locator("#btn-submit-login").click()

    # ==========================================
    # PASO 6: Seleccionar el Rol (si aparece la ventana)
    # ==========================================
    print(f"5. Buscando el rol '{ROL_ELEGIDO}'...")
    # Las opciones del rol están en: #roles a.list-group-item
    opciones_rol = page.locator("#roles a.list-group-item")

    try:
        # Buscamos la opción que coincida con el nombre de nuestro rol
        # Usamos regex para ignorar mayúsculas o espacios accidentales
        patron_rol = re.compile(rf"^\s*{re.escape(ROL_ELEGIDO)}\s*$", re.I)
        boton_rol = opciones_rol.filter(has_text=patron_rol)

        # Esperamos máximo 15 segundos a que la ventana de rol aparezca
        expect(boton_rol).to_be_visible(timeout=15_000)
        print(f"   Seleccionando rol: {ROL_ELEGIDO}")
        boton_rol.click()

    except AssertionError:
        # Si la cuenta tiene un solo rol, Q10 entra directo sin mostrar esta ventana
        if "/user/login" not in page.url.lower():
            print("   (La cuenta entró directo sin pedir rol)")
        else:
            print(f"   No se encontró el rol '{ROL_ELEGIDO}'. Revisa las opciones en pantalla.")

    # ==========================================
    # PASO 7: Esperar a que cargue la página principal
    # ==========================================
    print("6. Esperando que cargue la plataforma...")
    # Esperamos que la URL ya no sea la de login
    page.wait_for_url(lambda url: "/user/login" not in url.lower(), timeout=60_000)
    page.wait_for_load_state()

    print("\n✅ ¡SESIÓN INICIADA CON ÉXITO EN Q10!")
    print(f"URL actual: {page.url}")

    # Guardamos una captura de pantalla de prueba
    page.screenshot(path="practica/resultado_login_q10.png")
    print("Captura guardada en: practica/resultado_login_q10.png")

    # Mantenemos el navegador abierto para que puedas inspeccionarlo
    input("\nPresiona Enter en esta consola para cerrar el navegador...")
    browser.close()
