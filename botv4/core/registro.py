"""Registro de la corrida: todo lo que se imprime queda tambien en un archivo.

En la maquina virtual nadie esta mirando la consola, asi que el archivo es la unica forma de
saber que paso. Se guarda uno por corrida en la carpeta 'Registros', al lado de 'Descargas'.
"""
import os
import sys
from datetime import datetime

from core import archivos

CARPETA = archivos.CARPETA / "Registros"


class DobleSalida:
    """Escribe en la consola y en el archivo a la vez, con la hora al inicio de cada linea."""

    def __init__(self, consola, archivo):
        self.consola = consola
        self.archivo = archivo
        self.linea_nueva = True

    def write(self, texto):
        try:
            self.consola.write(texto)
        except Exception:
            pass          # como tarea programada puede no haber consola; el archivo es lo que importa
        for parte in texto.splitlines(keepends=True):
            if self.linea_nueva and parte.strip():
                self.archivo.write(f"{datetime.now():%H:%M:%S}  ")
            self.archivo.write(parte)
            self.linea_nueva = parte.endswith("\n")
        self.archivo.flush()
        return len(texto)

    def flush(self):
        for salida in (self.consola, self.archivo):
            try:
                salida.flush()
            except Exception:
                pass


def abrir(nombre="bot"):
    """Empieza a guardar todo lo que se imprima. Devuelve la ruta del archivo."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA / f"{datetime.now():%Y-%m-%d_%H%M}_{archivos.nombre_archivo(nombre)}.log"
    archivo = open(ruta, "a", encoding="utf-8")
    vacia = open(os.devnull, "w")
    sys.stdout = DobleSalida(sys.stdout or vacia, archivo)
    sys.stderr = DobleSalida(sys.stderr or vacia, archivo)
    return ruta


def limpiar(dias=30):
    """Borra los registros viejos para que la carpeta no crezca sin control."""
    if not CARPETA.exists():
        return 0
    limite = datetime.now().timestamp() - dias * 86_400
    borrados = 0
    for viejo in CARPETA.glob("*.log"):
        try:
            if viejo.stat().st_mtime < limite:
                viejo.unlink()
                borrados += 1
        except OSError:
            pass
    return borrados
