import argparse
import json
import os
import re
import sys
import shutil
import unicodedata
from pathlib import Path

# Configurar rutas para poder importar desde botv3
ES_EXE = getattr(sys, "frozen", False)
# Empaquetado: todo va junto al ejecutable. En desarrollo: bots/macmillan/ -> raiz del proyecto
CARPETA = Path(sys.executable).resolve().parent if ES_EXE else Path(__file__).resolve().parent
ROOT = CARPETA if ES_EXE else CARPETA.parents[1]
if not ES_EXE:
    sys.path.insert(0, str(CARPETA / "motor_botv3"))
if getattr(sys, "frozen", False):
    # Empaquetado: Playwright buscaria los navegadores dentro del .exe; se usan los del equipo
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"))

from playwright.sync_api import sync_playwright
from sistemas.macmillan.paginas import InicioMacmillan
from core.errores import resumen

def abrir_navegador(p, visible):
    """Chromium de Playwright; si el equipo no lo tiene (caso tipico del .exe), Chrome o Edge."""
    try:
        return p.chromium.launch(headless=not visible)
    except Exception as sin_chromium:
        for canal in ("chrome", "msedge"):
            try:
                return p.chromium.launch(channel=canal, headless=not visible)
            except Exception:
                pass
        raise sin_chromium


def renombrar_descarga(archivo_origen, nombre_base, carpeta_destino, formato="CSV"):
    """Mueve y renombra el archivo descargado a la carpeta final, SIN convertirlo.

    Macmillan entrega un CSV; se conserva la extensión original. (Antes se le ponía ".xlsx" a un CSV,
    lo que dejaba un archivo que Excel no abría bien.)
    """
    if hasattr(archivo_origen, "suggested_filename"):
        ext = Path(archivo_origen.suggested_filename).suffix or ".csv"
    else:
        ext = Path(str(archivo_origen)).suffix or ".csv"
    destino_dir = Path(carpeta_destino)
    destino_dir.mkdir(parents=True, exist_ok=True)
    
    nombre_limpio = unicodedata.normalize('NFKD', nombre_base).encode('ascii', 'ignore').decode('ascii')
    nuevo_nombre = "".join(c if c.isalnum() or c in " .-_" else "_" for c in nombre_limpio)
    destino_final = destino_dir / f"{nuevo_nombre}{ext}"
    
    # Mover el archivo descargado
    if hasattr(archivo_origen, "save_as"):
        archivo_origen.save_as(str(destino_final))
    else:
        shutil.move(str(archivo_origen), str(destino_final))
    return destino_final

# lo lee la pantalla de configuracion, que vive en herramientas/macmillan/
CATALOGO = (ROOT if ES_EXE else ROOT / "herramientas" / "macmillan") / "catalogo_clases_macmillan.json"


def registrar_catalogo(progreso, libro, nivel, primera_pagina):
    """Guarda las clases que Macmillan lista para este libro y nivel, para que el panel las ofrezca
    en 'Organizacion'. Lee todas las paginas del listado; si algo falla, deja al menos la primera.
    Nunca debe frenar la descarga.

    Devuelve {clase: numero de pagina del listado}, para poder ir directo a la pagina de cada clase
    (el listado muestra 10 por pagina y "View details" solo existe para las de la pagina abierta)."""
    clases = list(primera_pagina)
    ubicacion = {c: 1 for c in primera_pagina}
    try:
        paginas = progreso.total_paginas()
        if paginas > 1:
            for n in range(2, paginas + 1):
                progreso.ir_a_pagina(n)
                nuevas = progreso.clases()
                for c in nuevas:
                    ubicacion.setdefault(c, n)
                clases += [c for c in nuevas if c not in clases]
            ir_a_primera_pagina(progreso)
    except Exception as error:
        print(f"Aviso: no pude leer todas las paginas de clases para el catalogo: {resumen(error)}")
        try:
            ir_a_primera_pagina(progreso)
        except Exception:
            pass
    try:
        datos = json.loads(CATALOGO.read_text(encoding="utf-8")) if CATALOGO.exists() else {}
        datos.setdefault(libro, {})[nivel or ""] = sorted(set(clases))
        CATALOGO.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Catalogo: {len(clases)} clase(s) guardadas para {libro} {nivel or ''}".rstrip())
    except Exception as error:
        print(f"Aviso: no pude guardar el catalogo de clases: {resumen(error)}")
    return ubicacion


def ir_a_primera_pagina(progreso):
    """Deja el listado en la pagina 1. 'Go' no la reinicia (conserva la pagina en la que se estaba),
    asi que se usa el enlace '1' del paginador; sin paginador ya esta en la unica pagina."""
    enlaces = progreso.page.locator(progreso.ENLACE_PAGINA)
    if not enlaces.count():
        return
    uno = enlaces.filter(has_text=progreso.texto_exacto("1"))
    if uno.count():
        uno.first.scroll_into_view_if_needed()
        uno.first.click()
        progreso.esperar(2_000)
        progreso.esperar_clases()
    else:
        progreso.presionar_go()


def ir_a_pagina_de(progreso, pagina):
    """Va a la pagina del listado indicada, partiendo SIEMPRE de la pagina 1."""
    ir_a_primera_pagina(progreso)
    if pagina > 1:
        progreso.ir_a_pagina(pagina)


def ejecutar():
    # line_buffering: con la salida redirigida a la pantalla, Python acumulaba todo y lo soltaba
    # al terminar (el progreso parecia congelado). UTF-8: es como la pantalla lee la salida.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, 'reconfigure'):
            flujo.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
        
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Ruta al JSON con la configuracion")
    args = parser.parse_args()

    ruta_config = Path(args.config)
    if not ruta_config.exists():
        print(f"Error: No se encontro el archivo de configuracion {ruta_config}")
        sys.exit(1)

    with ruta_config.open("r", encoding="utf-8") as f:
        config = json.load(f)

    perfil = config.get("perfil", {})
    cred = config.get("credenciales", {})
    ajustes = config.get("ajustes", {})

    url = cred.get("url", "https://www.macmillaneducationeverywhere.com")
    usuario = cred.get("usuario")
    clave = cred.get("password")
    
    libro_nombre = perfil.get("libro")
    libro_nivel = perfil.get("nivel")
    recurso = perfil.get("recurso", "Macmillan Education Everywhere App")
    clases = perfil.get("clases", [])
    todas_clases = perfil.get("todas_clases", False)
    
    ruta_descargas = ajustes.get("ruta_descargas", str(ROOT / "Descargas" / "Macmillan"))
    visible = ajustes.get("navegador_visible", True)

    try:
        with sync_playwright() as p:
            print(f"Iniciando Chromium con Playwright ({'visible' if visible else 'headless'})...")
            browser = abrir_navegador(p, visible)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(30_000)

            print(f"Abriendo {url}")
            # Inicio y Login
            login = InicioMacmillan(page).abrir(url).ir_a_login()
            print(f"Iniciando sesion como {usuario}")
            estanteria = login.iniciar_sesion(usuario, clave)
            print("Sesion iniciada")
            
            # Libro
            print(f"Seleccionando libro: {libro_nombre}")
            libro = estanteria.abrir().abrir_libro(libro_nombre)
            
            # Nivel
            if libro_nivel:
                print(f"Seleccionando nivel: {libro_nivel}")
                libro.abrir_nivel(libro_nivel)
            
            # Recurso
            print(f"Abriendo recurso: {recurso}")
            app = libro.abrir_recurso(recurso)
            visor = app.ver_en_navegador()
            visor.cerrar_aviso_sesion()
            
            print("Navegando a School work > Progress")
            visor.abrir_school_work()
            progreso = visor.abrir_progress()
            
            # Filtro de curso
            progreso.elegir_curso(libro_nombre, libro_nivel)
            progreso.presionar_go()

            # Descargar cada clase pedida
            clases_disponibles = progreso.clases()
            ubicacion = registrar_catalogo(progreso, libro_nombre, libro_nivel, clases_disponibles)
            todas_las_clases = list(ubicacion)      # las de TODAS las paginas del listado

            if todas_clases:
                clases_a_procesar = todas_las_clases
            else:
                pedidas = {progreso.normalizar(c) for c in clases}
                clases_a_procesar = [c for c in todas_las_clases if progreso.normalizar(c) in pedidas]
                faltan = [c for c in clases if progreso.normalizar(c) not in
                          {progreso.normalizar(x) for x in todas_las_clases}]
                if faltan:
                    print(f"Aviso: estas clases no existen en {libro_nombre} {libro_nivel or ''}: {faltan}")
                if not clases_a_procesar:
                    print(f"Aviso: No se encontraron las clases {clases} en la plataforma. Hay: {todas_las_clases}")
            
            # Linea interna que lee la ventana de progreso: "[[PROGRESO]] terminadas total"
            print(f"[[PROGRESO]] 0 {len(clases_a_procesar)}", flush=True)
            for i, clase in enumerate(clases_a_procesar, 1):
                if i > 1:
                    print(f"[[PROGRESO]] {i - 1} {len(clases_a_procesar)}", flush=True)
                print(f"Clase {i}/{len(clases_a_procesar)}: {clase}")
                print(f"   Scores: {perfil.get('scores_mode', 'Show all attempts')}")
                try:
                    ir_a_pagina_de(progreso, ubicacion.get(clase, 1))
                    detalle = progreso.abrir_clase(clase)
                    archivo_descargado = detalle.exportar()
                    
                    nombre_base = f"{libro_nombre}_{clase}"
                    destino = renombrar_descarga(archivo_descargado, nombre_base, ruta_descargas, perfil.get("formato", "CSV"))
                    
                    print(f"   ✔️ Guardado:\n{destino}")
                except Exception as error:
                    print(f"   FALLO al exportar la clase: {resumen(error)}")
                
                progreso.volver_a_clases()

            print(f"[[PROGRESO]] {len(clases_a_procesar)} {len(clases_a_procesar)}", flush=True)
            browser.close()
            print("\n✔️ Reporte generado exitosamente.")
            
    except Exception as e:
        print(f"Fallo critico: {resumen(e)}")
        sys.exit(1)

if __name__ == "__main__":
    ejecutar()
