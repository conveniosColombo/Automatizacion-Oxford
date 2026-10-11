import os
import re
from playwright.sync_api import sync_playwright, expect

# 1. Datos para iniciar sesión
URL_LOGIN = "https://site2.q10.com/User/Login"
USUARIO = "ramon.franco@colombobogota.edu.co"
CLAVE = "Colombia2626*"
ROL_ELEGIDO = "Administrativo"
SEDE_DESEADA = "B2G - Única"
Programa = "YES BOGOTA 2026-2"
Periodo = "B2G_YES BOGOTA-2 C1_SEP_2026"

# Puedes poner:
# - "Todos" (recorre y descarga todos los cursos del período)
# - Un curso específico: "C1.1-7PM217 SDDE_2026-2 (B2G_YES BOGOTA-2 C1_SEP_2026)"
# - Una lista de cursos: ["Curso 1", "Curso 2"]
Curso = "Todos"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    context = browser.new_context(viewport={"width": 1366, "height": 768})
    page = context.new_page()

    print(f"\n1. Navegando a: {URL_LOGIN}")
    page.goto(URL_LOGIN)
    page.wait_for_load_state('domcontentloaded')
    page.locator('#form-username').fill(USUARIO)
    page.locator('#btn-submit-login').click()
    page.locator('#form-password').fill(CLAVE)
    page.locator('#btn-submit-login').click()
    page.wait_for_load_state('domcontentloaded')
    page.get_by_role("link", name="informes").click()
    page.get_by_role("link", name="Generales").click()
    page.get_by_role("link", name="Inasistencias por curso").click()
    # Sede
    page.locator('button[data-id="sedeJornada"]').click()
    page.locator('.bootstrap-select.open .dropdown-menu.inner li').filter(has_text=SEDE_DESEADA).click()
    page.wait_for_timeout(1000)

    # Programa
    page.locator('button[data-id="programa"]').click()
    page.locator('.bootstrap-select.open .dropdown-menu.inner li').filter(has_text=Programa).click()
    page.wait_for_timeout(1000)

    # Período
    page.locator('button[data-id="periodo"]').click()
    page.locator('.bootstrap-select.open .dropdown-menu.inner li').filter(has_text=Periodo).click()

    # En Q10 el campo de curso internamente se llama 'plaaca_consecutivoP' (no 'curso')
    # 1. Esperamos a que la lista de cursos termine de cargar por AJAX (al menos 1 opción además de 'Seleccione')
    print("\nEsperando a que carguen los cursos desde el servidor...")
    expect(page.locator('#plaaca_consecutivoP option').nth(1)).to_be_attached(timeout=15000)

    # 2. Obtenemos todas las opciones de cursos disponibles en Q10 (omitiendo 'Seleccione')
    todos_los_cursos = [
        o.strip()
        for o in page.locator('#plaaca_consecutivoP option').all_inner_texts()
        if o.strip() and o.strip().lower() != "seleccione"
    ]

    # 3. Determinamos cuáles cursos procesar
    if isinstance(Curso, str) and Curso.strip().lower() == "todos":
        cursos_a_procesar = todos_los_cursos
    elif isinstance(Curso, list):
        cursos_a_procesar = Curso
    else:
        cursos_a_procesar = [Curso]

    print(f"\nSe encontraron {len(todos_los_cursos)} cursos en este período.")
    print(f"Iniciando descarga de {len(cursos_a_procesar)} curso(s)...\n")

    carpeta_descargas = "Descargas"
    os.makedirs(carpeta_descargas, exist_ok=True)

    # 4. Ciclo FOR para recorrer cada curso y descargarlo
    for i, curso_actual in enumerate(cursos_a_procesar, start=1):
        print(f"[{i}/{len(cursos_a_procesar)}] Procesando curso: {curso_actual}")

        # Selección directa del curso (rápida y confiable sin trabarse con animaciones)
        page.select_option('#plaaca_consecutivoP', label=curso_actual, force=True)

        # Esperar y capturar la descarga del archivo Excel
        with page.expect_download() as download_info:
            page.locator('#generar-reporte-btn').click()

        download = download_info.value

        # Limpiar el nombre del archivo para que sea válido en Windows
        nombre_limpio = re.sub(r'[\\/*?:"<>|]', '_', curso_actual.strip())
        ruta_archivo = os.path.join(carpeta_descargas, f"Inasistencias_{nombre_limpio[:60]}.xlsx")
        download.save_as(ruta_archivo)
        print(f"   -> Guardado en: {ruta_archivo}")

        # Pausa breve entre reportes
        page.wait_for_timeout(1000)

    print("\n¡Todos los cursos solicitados han sido descargados con éxito!")

    page.wait_for_load_state('domcontentloaded')

    # OPCIÓN 1: Esperar un tiempo fijo (en milisegundos). Ej: 5000 ms = 5 segundos
    print("Esperando 5 segundos...")
    page.wait_for_timeout(5000)

    # OPCIÓN 2 (Recomendada para practicar): Mantenerlo abierto hasta que presiones Enter
    input("\nPresiona Enter en la consola para cerrar el navegador...")
