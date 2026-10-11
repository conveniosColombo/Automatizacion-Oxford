"""Carpeta de trabajo, lectura de los .txt (Config y Credenciales) y guardado de descargas y capturas."""
import csv
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ES_EXE = getattr(sys, "frozen", False)
# Como .exe: los .txt, las descargas y las capturas van junto al ejecutable.
# En desarrollo: la carpeta del proyecto (la que contiene a botv3), asi todas las versiones usan los mismos .txt
CARPETA = Path(sys.executable).resolve().parent if ES_EXE else Path(__file__).resolve().parents[2]

# Comienzo de los textos de ejemplo de las plantillas sin llenar
PLANTILLAS = ("escribe_aqui", "coloca aqu")


def leer_txt(nombre):
    """Lee un .txt con lineas 'Clave : valor' y devuelve un diccionario (claves en minuscula, en orden)."""
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


def es_plantilla(valor):
    return valor.lower().startswith(PLANTILLAS)


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
        """Lee 'Credenciales <sistema>.txt' y avisa si falta algo o quedo la plantilla sin llenar."""
        nombre = f"Credenciales {sistema}.txt"
        datos = leer_txt(nombre)
        faltan = [c for c in ("user", "password", "link") if not datos.get(c) or es_plantilla(datos[c])]
        if faltan:
            raise ValueError(f"Completa {', '.join(faltan)} en '{nombre}'")
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


def guardar_tabla(encabezados, filas, sistema, prefijo):
    """Guarda en Descargas/<sistema>/ una tabla leida de la pantalla, en CSV.

    Es para las pantallas que no tienen boton de exportar: el archivo lo arma el bot.
    utf-8-sig para que Excel abra bien las tildes al hacer doble clic.
    """
    destino = (CARPETA / "Descargas" / sistema
               / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre_archivo(prefijo)}.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        if encabezados:
            escritor.writerow(encabezados)
        escritor.writerows(filas)
    return destino


def captura(page, nombre):
    ruta = CARPETA / "Capturas" / nombre
    page.screenshot(path=str(ruta))
    return ruta
