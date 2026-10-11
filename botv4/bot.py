"""Bot de descargas v4 (POO + Page Object), preparado para correr solo.

Tres formas de usarlo:
  'Ejecutar botv4.bat'             menu de siempre, con una persona mirando.
  'Ejecutar botv4 automatico.bat'  corre lo que diga 'Config Bot.txt' y se cierra solo.
  'bot.py Oxford'                  un sistema puntual.

Cuando corre solo (--auto):
  - nada pregunta nada: si algo necesita una mano, se reporta como falla y sigue con lo demas;
  - cada sistema corre en su propio proceso, con un tope de tiempo, asi uno colgado no se
    lleva a los demas;
  - todo queda escrito en 'Registros\\<fecha>_<sistema>.log';
  - el codigo de salida dice como fue, que es lo que mira el Programador de tareas:
        0 = todo bien | 1 = algun sistema fallo | 2 = problema de configuracion
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ES_EXE = getattr(sys, "frozen", False)
VENV = Path(__file__).resolve().parents[1] / ".venv"  # entorno virtual del proyecto (carpeta de arriba)

# Con doble clic se abre con el Python global, que no tiene Playwright: relanzar con el del proyecto
if not ES_EXE and (VENV / "Scripts" / "python.exe").exists() and Path(sys.prefix).resolve() != VENV.resolve():
    sys.exit(subprocess.call([str(VENV / "Scripts" / "python.exe"), __file__, *sys.argv[1:]]))

from playwright.sync_api import sync_playwright

from core import archivos, modo, registro
from core.config_bot import ConfigBot
from core.errores import resumen
from core.navegador import abrir_navegador
from sistemas import SISTEMAS

BIEN, FALLO, MALA_CONFIGURACION, SE_PASO_DE_TIEMPO = 0, 1, 2, 3


def disponibles():
    """Sistemas programados que tienen su 'Config <Sistema>.txt' en la carpeta."""
    encontrados = []
    for ruta in sorted(archivos.CARPETA.glob("Config *.txt")):
        clave = ruta.stem[len("Config "):].strip().lower()
        if clave in SISTEMAS:
            encontrados.append(SISTEMAS[clave])
        elif clave != "bot":          # 'Config Bot.txt' es la configuracion del propio bot
            print(f"Aviso: '{ruta.name}' no corresponde a ningun sistema programado; se ignora.")
    if not encontrados:
        programados = ", ".join(s.NOMBRE for s in SISTEMAS.values())
        raise FileNotFoundError(f"No hay ningun 'Config <Sistema>.txt' en {archivos.CARPETA}. "
                                f"Sistemas programados: {programados}")
    return encontrados


def buscar(nombre, lista):
    """El sistema que se llama asi (sin importar mayusculas), o None."""
    return next((s for s in lista if s.NOMBRE.lower() == nombre.strip().lower()), None)


def contar_descargas(nombre, desde):
    """Cuantos archivos dejo ese sistema en 'Descargas' desde que empezo la corrida."""
    carpeta = archivos.CARPETA / "Descargas" / nombre
    if not carpeta.exists():
        return 0
    return sum(1 for archivo in carpeta.iterdir()
               if archivo.is_file() and archivo.stat().st_mtime >= desde)


# --------------------------------------------------------------------- un solo sistema ---
def correr_uno(nombre, sin_ventana=False, con_registro=True):
    """Ejecuta un sistema de principio a fin. Devuelve el codigo de salida."""
    sistema = buscar(nombre, disponibles())
    if sistema is None:
        print(f"FALLO: no hay 'Config {nombre}.txt'")
        return MALA_CONFIGURACION

    modo.AUTOMATICO = True
    if con_registro:
        print(f"registro: {registro.abrir(nombre).name}")
    print(f"===== {sistema.NOMBRE} =====   {datetime.now():%Y-%m-%d %H:%M:%S}"
          + ("   (sin ventana)" if sin_ventana else ""))

    codigo = BIEN
    with sync_playwright() as p:
        navegador = abrir_navegador(p, visible=not sin_ventana)
        contexto = navegador.new_context(viewport={"width": 1400, "height": 900})
        page = contexto.new_page()
        page.set_default_timeout(30_000)
        try:
            sistema(page).ejecutar()
            print(f"{sistema.NOMBRE}: terminado.")
        except Exception as error:
            print(f"FALLO en {sistema.NOMBRE}: {resumen(error)}")
            codigo = FALLO
        # La captura deja ver en que pantalla quedo, que es lo unico que se puede mirar despues
        for numero, pestana in enumerate(contexto.pages, start=1):
            try:
                ruta = archivos.captura(pestana, f"resultado_{sistema.NOMBRE}_{numero}.png")
                print(f"Pestana {numero}: {pestana.url}  -> captura en {ruta.name}")
            except Exception:
                pass
        navegador.close()
    return codigo


# ------------------------------------------------------------------- todos, sin preguntar ---
def correr_automatico(pedidos):
    """Corre los sistemas del 'Config Bot.txt' (o los que se pasen), cada uno en su proceso."""
    configuracion = ConfigBot.desde_txt()
    ruta_registro = registro.abrir("resumen")
    print(f"===== BOT AUTOMATICO =====   {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"carpeta: {archivos.CARPETA}")
    print(configuracion.resumen()
          + ("" if configuracion.existe else "   (no hay 'Config Bot.txt', uso lo de siempre)"))

    try:
        lista = disponibles()
    except Exception as error:
        print(f"FALLO: {resumen(error)}")
        return MALA_CONFIGURACION

    pedidos = pedidos or configuracion.sistemas
    if any(p.strip().lower() == "todos" for p in pedidos):
        elegidos = [s.NOMBRE for s in lista]
    else:
        elegidos = []
        for pedido in pedidos:
            sistema = buscar(pedido, lista)
            if sistema is None:
                print(f"Aviso: '{pedido}' no tiene 'Config {pedido}.txt'; se salta.")
            else:
                elegidos.append(sistema.NOMBRE)
    if not elegidos:
        print("FALLO: ningun sistema para ejecutar. Revisa 'Sistemas' en Config Bot.txt")
        return MALA_CONFIGURACION
    print(f"a ejecutar: {', '.join(elegidos)}\n")

    resultados = []
    for nombre in elegidos:
        for intento in range(1, configuracion.reintentos + 2):
            comienzo, marca = time.time(), time.time()
            print(f"--- {nombre} (intento {intento}) ---")
            codigo = ejecutar_aparte(nombre, configuracion)
            minutos = (time.time() - comienzo) / 60
            bajados = contar_descargas(nombre, marca)
            print(f"--- {nombre}: {'OK' if codigo == BIEN else 'FALLO'}, "
                  f"{bajados} archivo(s), {minutos:.1f} min ---\n")
            if codigo == BIEN or intento > configuracion.reintentos:
                resultados.append((nombre, codigo, bajados, minutos, intento))
                break

    print("===== RESUMEN =====")
    for nombre, codigo, bajados, minutos, intento in resultados:
        estado = {BIEN: "OK", SE_PASO_DE_TIEMPO: "SE PASO DE TIEMPO"}.get(codigo, "FALLO")
        print(f"  {nombre:<12} {estado:<18} {bajados:>3} archivo(s)   {minutos:>5.1f} min"
              + (f"   (intentos: {intento})" if intento > 1 else ""))
    borrados = registro.limpiar()
    print(f"\nregistro: {ruta_registro}" + (f"   ({borrados} registros viejos borrados)" if borrados else ""))
    return BIEN if all(codigo == BIEN for _, codigo, *_ in resultados) else FALLO


def ejecutar_aparte(nombre, configuracion):
    """Lanza el sistema en otro proceso con un tope de tiempo: si se cuelga, no bloquea el resto."""
    orden = [sys.executable, str(Path(__file__).resolve()), nombre, "--hijo"]
    if configuracion.sin_ventana:
        orden.append("--sin-ventana")
    try:
        return subprocess.run(orden, timeout=configuracion.minutos_por_sistema * 60).returncode
    except subprocess.TimeoutExpired:
        print(f"{nombre}: paso de {configuracion.minutos_por_sistema} minutos; se corta el intento")
        return SE_PASO_DE_TIEMPO


# ------------------------------------------------------------------------------- el menu ---
class Bot:
    """Modo de siempre: pregunta que sistema correr y deja el navegador abierto al final."""

    def __init__(self, argumentos):
        self.pedido = " ".join(argumentos).strip().lower()

    def elegir(self, lista):
        if self.pedido:
            if self.pedido == "todos":
                return lista
            sistema = buscar(self.pedido, lista)
            if sistema is None:
                nombres = ", ".join(s.NOMBRE for s in lista)
                raise ValueError(f"No hay 'Config {self.pedido}.txt'. Disponibles: {nombres}, Todos")
            return [sistema]
        if len(lista) == 1:
            return lista

        print("\nQue sistema quieres ejecutar?")
        for numero, sistema in enumerate(lista, start=1):
            print(f"  {numero}. {sistema.NOMBRE}")
        print(f"  {len(lista) + 1}. Todos")
        while True:
            # Solo los digitos: descarta marcas invisibles (BOM) si la respuesta viene de otro programa
            respuesta = "".join(c for c in input("Escribe el numero y presiona Enter: ") if c.isdigit())
            if respuesta and 1 <= int(respuesta) <= len(lista) + 1:
                numero = int(respuesta)
                return lista if numero == len(lista) + 1 else [lista[numero - 1]]
            print("Opcion no valida.")

    def ejecutar(self):
        elegidos = self.elegir(disponibles())

        with sync_playwright() as p:
            navegador = abrir_navegador(p)
            for sistema in elegidos:
                print(f"\n===== {sistema.NOMBRE} =====")
                # Cada sistema en su propia ventana: no comparte cookies ni sesion con los demas
                contexto = navegador.new_context(viewport={"width": 1400, "height": 900})
                page = contexto.new_page()
                page.set_default_timeout(30_000)
                try:
                    sistema(page).ejecutar()
                    print(f"{sistema.NOMBRE}: terminado.")
                except Exception as error:
                    print(f"FALLO en {sistema.NOMBRE}: {resumen(error)}")

                for numero, pestana in enumerate(contexto.pages, start=1):
                    ruta = archivos.captura(pestana, f"resultado_{sistema.NOMBRE}_{numero}.png")
                    print(f"Pestana {numero}: {pestana.url}  -> captura en {ruta.name}")

            input("\nPresiona Enter para cerrar el navegador...")
            navegador.close()


def leer_argumentos():
    analizador = argparse.ArgumentParser(description="Bot de descargas v4")
    analizador.add_argument("sistemas", nargs="*", help="Oxford, Macmillan, Q10 o Todos")
    analizador.add_argument("--auto", action="store_true",
                            help="corre solo, segun 'Config Bot.txt', sin preguntar nada")
    analizador.add_argument("--sin-ventana", action="store_true",
                            help="el navegador no se muestra")
    analizador.add_argument("--hijo", action="store_true", help=argparse.SUPPRESS)
    return analizador.parse_args()


if __name__ == "__main__":
    opciones = leer_argumentos()
    if opciones.hijo:                       # uso interno: un solo sistema, lanzado por --auto
        if not opciones.sistemas:
            print("FALLO: hay que decir que sistema ejecutar")
            sys.exit(MALA_CONFIGURACION)
        sys.exit(correr_uno(opciones.sistemas[0], opciones.sin_ventana))
    if opciones.auto:
        sys.exit(correr_automatico(opciones.sistemas))
    try:
        Bot(opciones.sistemas).ejecutar()
    except Exception as error:
        # Sin esto la consola se cierra sola y no se alcanza a leer el error
        print(f"FALLO: {resumen(error)}")
        input("Presiona Enter para cerrar...")
        sys.exit(FALLO)
