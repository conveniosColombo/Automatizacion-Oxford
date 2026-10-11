"""Crea 'Bot Descargas.xlsx' con lo que ya hay en los Config y Credenciales .txt de una carpeta.

    python pasar_txt_a_excel.py                       -> carpeta del proyecto
    python pasar_txt_a_excel.py "<carpeta>"           -> otra carpeta (ej. la de compartir)
    python pasar_txt_a_excel.py "<carpeta>" --sin-claves   -> deja usuario y contraseña vacios

Solo se pasan las lineas activas: lo comentado con '#' no se pasa. Los .txt no se tocan.
"""
import sys
from pathlib import Path

from core import planilla
from core.archivos import separar_lista


def leer_txt(ruta):
    """Lineas 'Clave : valor' que no estan comentadas, en orden (claves como estan escritas)."""
    if not ruta.exists():
        return {}
    datos = {}
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        if ":" in linea and not linea.strip().startswith("#"):
            clave, valor = linea.split(":", 1)
            datos[clave.strip()] = valor.strip()
    return datos


def sin_mayusculas(datos):
    return {clave.lower(): valor for clave, valor in datos.items()}


def filas_de(valor):
    """'a, b, a' -> [(a, Sí, ''), (b, Sí, '')] (sin repetidos, en orden)."""
    vistos = []
    for elemento in separar_lista(valor or ""):
        if elemento not in vistos:
            vistos.append(elemento)
    return [(e, "Sí", "") for e in vistos]


def valores_de(carpeta, sin_claves=False):
    valores = {planilla.ACCESOS: []}
    for nombre, hoja in planilla.HOJAS.items():
        config_txt = carpeta / f"Config {nombre}.txt"
        credenciales = sin_mayusculas(leer_txt(carpeta / f"Credenciales {nombre}.txt"))
        usuario, clave = credenciales.get("user", ""), credenciales.get("password", "")
        if sin_claves or usuario.lower().startswith(("escribe_aqui", "coloca aqu")):
            usuario = clave = ""
        valores[planilla.ACCESOS].append(
            (nombre, "Sí" if config_txt.exists() else "No", usuario, clave, credenciales.get("link", "")))

        if not config_txt.exists():
            continue
        crudo = leer_txt(config_txt)
        datos = sin_mayusculas(crudo)
        claves_de_campos = {c.clave for c in hoja.campos}
        # En el .txt "Tipo" era otro nombre de "Menu"
        if "tipo" in datos and "menu" not in datos:
            datos["menu"] = datos["tipo"]
        campos = {c.clave: datos[c.clave] for c in hoja.campos if datos.get(c.clave)}
        listas = {l.clave: filas_de(datos.get(l.clave)) for l in hoja.listas}
        entrada = {"campos": campos, "listas": listas}
        if hoja.pares:
            generales = claves_de_campos | {l.clave for l in hoja.listas} | {"tipo"}
            entrada["pares"] = [(clave, valor, "Sí", "") for clave, valor in crudo.items()
                                if clave.lower() not in generales and valor]
        valores[nombre] = entrada
    return valores


if __name__ == "__main__":
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    carpeta = Path(argumentos[0]) if argumentos else Path(__file__).resolve().parents[1]
    destino = carpeta / planilla.NOMBRE
    if destino.exists():
        sys.exit(f"Ya existe {destino}. Borrala o renombrala si quieres crearla de nuevo.")
    planilla.crear(destino, valores_de(carpeta, "--sin-claves" in sys.argv))
    print(f"Planilla creada: {destino}")
