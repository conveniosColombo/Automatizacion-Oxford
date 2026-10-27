"""Genera los ejecutables en la carpeta '.exe' de la raiz del proyecto.

    .venv\\Scripts\\python.exe empaquetado\\construir_exe.py            (todos)
    .venv\\Scripts\\python.exe empaquetado\\construir_exe.py app bot_q10  (solo algunos)

Salen cuatro archivos que deben quedar JUNTOS en la misma carpeta:
    Herramientas Colombo.exe   la aplicacion (menu + las tres pantallas)
    Bot Q10.exe / Bot Macmillan.exe / Bot Oxford.exe   los robots que lanza cada pantalla
Cada robot lleva su propio 'core'/'sistemas' (los de Q10 y Macmillan se llaman igual pero son
distintos), por eso son ejecutables separados.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# Fuera de OneDrive: sincronizar miles de archivos temporales bloquea la carpeta y falla la compilacion
TRABAJO = Path(tempfile.gettempdir()) / "colombo_construccion"
SALIDA = RAIZ / ".exe"
PY = sys.executable
ICONO = RAIZ / "aplicacion" / "recursos" / "icono.ico"


def rutas(*partes):
    return str(RAIZ.joinpath(*partes))


# Cada objetivo: nombre del .exe, script de entrada y opciones de PyInstaller
OBJETIVOS = {
    "app": ("Herramientas Colombo", rutas("aplicacion", "main.py"), [
        "--windowed", "--icon", str(ICONO),
        "--paths", rutas("aplicacion"), "--paths", rutas("herramientas", "q10"),
        "--paths", rutas("herramientas", "macmillan"), "--paths", rutas("herramientas", "oxford"),
        "--paths", rutas("bots", "q10"),
        "--hidden-import", "configurar_q10", "--hidden-import", "app_macmillan",
        "--hidden-import", "app_oxford",
        "--collect-data", "customtkinter",
        "--add-data", f"{rutas('aplicacion', 'recursos')};recursos",
        "--add-data", f"{rutas('datos', 'Plantilla_Clases_Oxford.xlsx')};.",
        "--exclude-module", "playwright",
    ]),
    "bot_q10": ("Bot Q10", rutas("bots", "q10", "bot.py"), [
        "--paths", rutas("bots", "q10"), "--collect-all", "playwright",
    ]),
    "bot_macmillan": ("Bot Macmillan", rutas("bots", "macmillan", "automatizar_macmillan.py"), [
        "--paths", rutas("bots", "macmillan", "motor_botv3"), "--collect-all", "playwright",
    ]),
    "bot_oxford": ("Bot Oxford", rutas("empaquetado", "entrada_bot_oxford.py"), [
        "--paths", rutas("bots", "oxford"), "--collect-all", "playwright",
    ]),
    # Pruebas de Wide Angle (pantalla "Usuarios" de Oxford): pytest + los archivos de tests/ dentro del .exe
    "bot_pruebas_oxford": ("Bot Pruebas Oxford", rutas("empaquetado", "entrada_pruebas_oxford.py"), [
        "--collect-all", "playwright", "--collect-submodules", "pytest",
        "--add-data", f"{rutas('tests', 'oxford')};tests/oxford",
        "--add-data", f"{rutas('tests', 'pytest.ini')};tests",
        "--add-data", f"{rutas('tests', 'conftest.py')};tests",
    ]),
}


def construir(clave):
    nombre, script, extra = OBJETIVOS[clave]
    print(f"\n=== {nombre} ===", flush=True)
    comando = [PY, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", nombre,
               "--distpath", str(TRABAJO / "dist"), "--workpath", str(TRABAJO / "build" / clave),
               "--specpath", str(TRABAJO / "spec"), *extra, script]
    subprocess.run(comando, check=True)
    SALIDA.mkdir(exist_ok=True)
    shutil.copy2(TRABAJO / "dist" / f"{nombre}.exe", SALIDA / f"{nombre}.exe")
    print(f"-> {SALIDA / (nombre + '.exe')}")


if __name__ == "__main__":
    pedidos = sys.argv[1:] or list(OBJETIVOS)
    for clave in pedidos:
        construir(clave)
