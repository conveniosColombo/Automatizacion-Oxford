"""Cruza una lista de documentos contra los archivos descargados de Q10.

Uso:  .venv\\Scripts\\python.exe cruzar_estudiantes.py Estudiantes.txt

Lee los .xlsx de Descargas/Q10 sin librerias extra (un .xlsx es un zip con XML adentro),
arma un indice de todos los documentos que aparecen y lo cruza con la lista.
Deja el resultado en 'Cruce estudiantes Q10.csv', que se abre con Excel.
"""
import csv
import re
import sys
import zipfile
from pathlib import Path

CARPETA_Q10 = Path("Descargas/Q10")
SALIDA = Path("Cruce estudiantes Q10.csv")
ESPACIO = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
# Documentos: numeros de 5 a 12 digitos (cedulas colombianas, con o sin "C.C." adelante)
NUMERO = re.compile(r"\d{5,12}")


def curso_de_archivo(nombre):
    """Del nombre del archivo saca el curso: 2026-09-17_1542_Inasistencias_por_curso_B1.2-5PM109_... """
    partes = nombre.replace(".xlsx", "").split("_")
    return " ".join(partes[5:]).strip("_ ") if len(partes) > 5 else nombre


def indice_de_documentos():
    """Devuelve {documento: [(archivo, curso), ...]} con todo lo que hay en Descargas/Q10."""
    indice = {}
    archivos = sorted(CARPETA_Q10.glob("*.xlsx"))
    bloqueados = []
    for archivo in archivos:
        try:
            with zipfile.ZipFile(archivo) as zip_:
                texto = b" ".join(zip_.read(n) for n in zip_.namelist()
                                  if n.endswith(".xml")).decode("utf-8", "ignore")
        except Exception:
            bloqueados.append(archivo.name)
            continue
        curso = curso_de_archivo(archivo.name)
        for documento in set(NUMERO.findall(texto)):
            indice.setdefault(documento, []).append((archivo.name, curso))
    return indice, len(archivos), bloqueados


def leer_lista(ruta):
    """Un documento por linea; ignora vacios, espacios y puntos de miles."""
    documentos = []
    for linea in Path(ruta).read_text(encoding="utf-8-sig").splitlines():
        limpio = re.sub(r"[.\s]", "", linea)
        if limpio.isdigit():
            documentos.append(limpio)
    return documentos


def main():
    if not CARPETA_Q10.exists():
        raise SystemExit(f"No encontre la carpeta {CARPETA_Q10}")

    print("Leyendo los archivos de Q10...")
    indice, total_archivos, bloqueados = indice_de_documentos()
    print(f"  {total_archivos} archivos leidos | {len(indice)} documentos distintos encontrados")
    if bloqueados:
        print(f"  Aviso: {len(bloqueados)} archivo(s) no se pudieron leer (abiertos o sincronizando)")

    if len(sys.argv) < 2:
        print("\nFalta la lista de documentos. Uso: cruzar_estudiantes.py Estudiantes.txt")
        return

    documentos = leer_lista(sys.argv[1])
    print(f"\nCruzando {len(documentos)} documentos de la lista...")

    filas, aparecen = [], 0
    for documento in documentos:
        coincidencias = indice.get(documento, [])
        if coincidencias:
            aparecen += 1
        filas.append({
            "documento": documento,
            "aparece": "SI" if coincidencias else "NO",
            "veces": len(coincidencias),
            "cursos": " | ".join(sorted({curso for _, curso in coincidencias})),
            "archivos": " | ".join(sorted({archivo for archivo, _ in coincidencias})),
        })

    with SALIDA.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=["documento", "aparece", "veces", "cursos", "archivos"])
        escritor.writeheader()
        escritor.writerows(filas)

    repetidos = len(documentos) - len(set(documentos))
    print(f"\n  Aparecen:    {aparecen}")
    print(f"  No aparecen: {len(documentos) - aparecen}")
    if repetidos:
        print(f"  (la lista traia {repetidos} documento(s) repetido(s))")
    print(f"\nResultado en: {SALIDA}")


if __name__ == "__main__":
    main()
