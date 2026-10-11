"""Bot de descargas: pregunta que sistema ejecutar (segun los 'Config <Sistema>.txt' de la carpeta) y lo corre.

Uso: doble clic muestra el menu. 'bot.py Q10' o 'bot.py Todos' ejecuta sin preguntar (para programarlo).
"""
import subprocess
import sys
from pathlib import Path

ES_EXE = getattr(sys, "frozen", False)
VENV = Path(__file__).resolve().parent / ".venv"

# Con doble clic se abre con el Python global, que no tiene Playwright: relanzar con el del proyecto
if not ES_EXE and (VENV / "Scripts" / "python.exe").exists() and Path(sys.prefix).resolve() != VENV.resolve():
    sys.exit(subprocess.call([str(VENV / "Scripts" / "python.exe"), __file__, *sys.argv[1:]]))

from playwright.sync_api import sync_playwright

import nucleo
from sistemas import oxford, q10

# Para agregar un sistema: crear sistemas/<nombre>.py con ejecutar() y registrarlo aqui
SISTEMAS = {modulo.NOMBRE.lower(): modulo for modulo in (oxford, q10)}


def sistemas_disponibles():
    """Sistemas que tienen 'Config <Sistema>.txt' en la carpeta y estan programados."""
    disponibles = []
    for ruta in sorted(nucleo.CARPETA.glob("Config *.txt")):
        clave = ruta.stem[len("Config "):].strip().lower()
        if clave in SISTEMAS:
            disponibles.append(SISTEMAS[clave].NOMBRE)
        else:
            print(f"Aviso: '{ruta.name}' no corresponde a ningun sistema programado; se ignora.")
    if not disponibles:
        programados = ", ".join(m.NOMBRE for m in SISTEMAS.values())
        raise FileNotFoundError(f"No hay ningun 'Config <Sistema>.txt' en {nucleo.CARPETA}. "
                                f"Sistemas programados: {programados}")
    return disponibles


def elegir(disponibles):
    """Devuelve la lista de sistemas a ejecutar: por argumento, directo si hay uno solo, o con el menu."""
    if len(sys.argv) > 1:
        pedido = " ".join(sys.argv[1:]).strip().lower()
        if pedido == "todos":
            return disponibles
        elegidos = [n for n in disponibles if n.lower() == pedido]
        if not elegidos:
            raise ValueError(f"No hay 'Config {pedido}.txt'. Disponibles: {', '.join(disponibles)}, Todos")
        return elegidos
    if len(disponibles) == 1:
        return disponibles

    print("\nQue sistema quieres ejecutar?")
    for numero, nombre in enumerate(disponibles, start=1):
        print(f"  {numero}. {nombre}")
    print(f"  {len(disponibles) + 1}. Todos")
    while True:
        # ﻿: marca invisible (BOM) que llega si la respuesta viene de otro programa en vez del teclado
        respuesta = input("Escribe el numero y presiona Enter: ").replace("﻿", "").strip()
        if respuesta.isdigit() and 1 <= int(respuesta) <= len(disponibles) + 1:
            numero = int(respuesta)
            return disponibles if numero == len(disponibles) + 1 else [disponibles[numero - 1]]
        print("Opcion no valida.")


def main():
    elegidos = elegir(sistemas_disponibles())

    with sync_playwright() as p:
        navegador = nucleo.abrir_navegador(p)
        for nombre in elegidos:
            print(f"\n===== {nombre} =====")
            # Cada sistema en su propia ventana: no comparte cookies ni sesion con los demas
            contexto = navegador.new_context(viewport={"width": 1400, "height": 900})
            page = contexto.new_page()
            page.set_default_timeout(30_000)
            try:
                config = nucleo.leer_archivo(f"Config {nombre}.txt")
                credenciales = nucleo.leer_credenciales(nombre)
                SISTEMAS[nombre.lower()].ejecutar(page, config, credenciales)
                print(f"{nombre}: terminado.")
            except Exception as error:
                print(f"FALLO en {nombre}: {nucleo.resumen(error)}")

            for numero, pestana in enumerate(contexto.pages, start=1):
                ruta = nucleo.captura(pestana, f"resultado_{nombre}_{numero}.png")
                print(f"Pestana {numero}: {pestana.url}  -> captura en {ruta.name}")

        input("\nPresiona Enter para cerrar el navegador...")
        navegador.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Sin esto la consola se cierra sola y no se alcanza a leer el error
        print(f"FALLO: {nucleo.resumen(error) if 'nucleo' in globals() else error}")
        input("Presiona Enter para cerrar...")
