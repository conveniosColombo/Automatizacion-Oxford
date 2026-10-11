from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Lanza el navegador (headless=False para verlo)
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://englishhub.oup.com/")
    page.get_by_role("button", name="Register or Sign in").click()
    page.locator("#username-or-email-address-input").fill("carolina.vega@colombobogota.edu.co")
    page.get_by_test_id("login-page-continue").click()

    # Paso condicional: el campo de organización puede o no aparecer
    org_field = page.get_by_test_id("login-page-orgid")
    if org_field.is_visible(timeout=3000):
        org_field.fill("18xaf")
        page.get_by_test_id("login-page-continue").click()

    page.locator("#password-input").fill("Oxford2026")
    page.get_by_test_id("login-page-continue").click()
    page.get_by_test_id("ACCOUNT_MENU_BUTTON").click()
    more_link = page.locator("a.dd9x")
    more_link.click()
    page.get_by_placeholder("Search by organization name or organization ID").fill("18xaf")

    # Busca la fila (tr) que contiene el ID "18xaf", y dentro de ella, hace clic en el link
    page.locator("tr", has_text="18xaf").locator("a").click()
    page.get_by_role("link", name="My Organization").click()
    page.get_by_role("tab", name="Classes").click()

    clase_a_buscar = "B1.2-5PM109 SDDE_2026-2"
    page.get_by_placeholder("Search classes").fill(clase_a_buscar)

    # Espera a que la fila filtrada esté visible
    fila = page.get_by_test_id("ORG_CLASSES_CLASS_ROW_ITEM").filter(has_text=clase_a_buscar)
    fila.wait_for(state="visible", timeout=5000)

    # CAMBIO: clic en el span con el nombre (ahí está e l manejador de clic),
    # no en el centro de la fila.
    fila.get_by_text(clase_a_buscar, exact=True).click()
    page.get_by_role("tab", name="Progress").click()
    # 1. Filas de la tabla; se queda con la que contiene "Closing soon"
    fila_curso = page.locator("tbody tr.hoverable").filter(has_text="Closing soon")
    fila_curso.first.wait_for(state="visible", timeout=10000)

    # 2. Dentro de esa fila, el enlace real, y clic
    fila_curso.get_by_role("link").first.click()

    input("Presiona Enter para cerrar el navegador...")
    browser.close()