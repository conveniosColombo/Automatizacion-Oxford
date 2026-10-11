"""Funciones comunes a todos los sistemas: rutas, archivos .txt, navegador, capturas y descargas."""
import re
import sys
from datetime import datetime
from pathlib import Path

ES_EXE = getattr(sys, "frozen", False)
# Como .exe, los .txt y las descargas van junto al ejecutable (no en la carpeta temporal donde se descomprime)
CARPETA = Path(sys.executable if ES_EXE else __file__).resolve().parent


def leer_archivo(nombre):
    """Lee un .txt con lineas 'Clave : valor' y devuelve un diccionario."""
    ruta = CARPETA / nombre
    if not ruta.exists():
        raise FileNotFoundError(f"No encontre '{nombre}' en {CARPETA}")
    datos = {}
    # utf-8-sig: el Bloc de notas a veces guarda con BOM y dañaria la primera clave
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        if ":" in linea and not linea.strip().startswith("#"):
            clave, valor = linea.split(":", 1)
            datos[clave.strip().lower()] = valor.strip()
    return datos


def leer_credenciales(sistema):
    """Lee 'Credenciales <sistema>.txt' y avisa si falta algo o quedo la plantilla sin llenar."""
    nombre = f"Credenciales {sistema}.txt"
    datos = leer_archivo(nombre)
    faltan = [c for c in ("user", "password", "link")
              if not datos.get(c) or datos[c].startswith("escribe_aqui")]
    if faltan:
        raise ValueError(f"Completa {', '.join(faltan)} en '{nombre}'")
    return datos


def resumen(error):
    return f"{type(error).__name__}: {str(error).splitlines()[0]}"


def nombre_archivo(texto):
    return re.sub(r"[^\w.-]+", "_", texto)


def abrir_navegador(p):
    """Usa Edge (viene con Windows) o Chrome, asi el .exe no tiene que traer su propio navegador."""
    for canal in ("msedge", "chrome"):
        try:
            return p.chromium.launch(channel=canal, headless=False, slow_mo=300)
        except Exception:
            pass
    return p.chromium.launch(headless=False, slow_mo=300)


def captura(page, nombre):
    ruta = CARPETA / "Capturas" / nombre
    page.screenshot(path=str(ruta))
    return ruta


def guardar_descarga(descarga, sistema, prefijo):
    """Guarda la descarga en Descargas/<sistema>/ con fecha y hora al inicio del nombre."""
    # Del nombre que da el sistema solo se usa la extension: lo demas ya va en el prefijo y alarga
    # la ruta, que en Windows no puede pasar de 260 caracteres
    extension = Path(descarga.suggested_filename).suffix
    destino = (CARPETA / "Descargas" / sistema
               / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre_archivo(prefijo)}{extension}")
    destino.parent.mkdir(parents=True, exist_ok=True)  # save_as no crea la carpeta del sistema
    descarga.save_as(destino)
    return destino
