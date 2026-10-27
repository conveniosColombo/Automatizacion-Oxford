"""Carpeta de trabajo, lectura de la planilla 'Bot Descargas.xlsx' y guardado de descargas y capturas."""
import csv
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from core import planilla as planilla_excel

ES_EXE = getattr(sys, "frozen", False)
# Como .exe: la planilla, las descargas y las capturas van junto al ejecutable.
# En desarrollo: la raiz del proyecto (bots/q10/core/archivos.py -> 3 niveles arriba).
# Descargas/ y Capturas/ cuelgan de la raiz; la planilla y el catalogo viven en datos/.
CARPETA = Path(sys.executable).resolve().parent if ES_EXE else Path(__file__).resolve().parents[3]
DATOS = CARPETA if ES_EXE else CARPETA / "datos"
PLANILLA = DATOS / planilla_excel.NOMBRE


@lru_cache(maxsize=1)
def planilla():
    """La planilla se abre una sola vez por ejecucion."""
    return planilla_excel.Planilla(PLANILLA)


def separar_lista(valor):
    """'a, b , c' -> ['a', 'b', 'c']"""
    return [v.strip() for v in valor.split(",") if v.strip()]


@dataclass(frozen=True)
class Credenciales:
    usuario: str
    clave: str
    link: str

    @classmethod
    def de_sistema(cls, sistema):
        """Lee la fila del sistema en la hoja 'Accesos' y avisa si falta algo."""
        datos = planilla().accesos().get(sistema.lower())
        if datos is None:
            raise ValueError(f"Falta la fila '{sistema}' en la hoja Accesos de {PLANILLA.name}")
        nombres = {"user": "Usuario", "password": "Contraseña", "link": "Link de ingreso"}
        faltan = [nombres[c] for c in nombres if not datos.get(c)]
        if faltan:
            raise ValueError(f"Completa {', '.join(faltan)} de {sistema} en la hoja Accesos de {PLANILLA.name}")
        return cls(usuario=datos["user"], clave=datos["password"], link=datos["link"])


def nombre_archivo(texto):
    return re.sub(r"[^\w.-]+", "_", texto)


def guardar_descarga(descarga, sistema, prefijo):
    """Guarda en Descargas/<sistema>/ con fecha y hora al inicio. Del nombre que da el sistema solo se usa
    la extension: lo demas ya va en el prefijo y alarga la ruta (en Windows no puede pasar de 260 caracteres)."""
    extension = Path(descarga.suggested_filename).suffix
    destino = (CARPETA / "Descargas" / sistema
               / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre_archivo(prefijo)}{extension}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    descarga.save_as(destino)
    return destino


def guardar_tabla(encabezados, filas, sistema, prefijo, carpeta=""):
    """Guarda en Descargas/<sistema>/ una tabla leida de la pantalla, en CSV.

    Es para las pantallas que no tienen boton de exportar: el archivo lo arma el bot.
    utf-8-sig para que Excel abra bien las tildes al hacer doble clic.
    """
    base = Path(carpeta) if carpeta else CARPETA / "Descargas" / sistema
    destino = base / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre_archivo(prefijo)}.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        if encabezados:
            escritor.writerow(encabezados)
        escritor.writerows(filas)
    return destino


def captura(page, nombre):
    ruta = CARPETA / "Capturas" / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ruta))
    return ruta
