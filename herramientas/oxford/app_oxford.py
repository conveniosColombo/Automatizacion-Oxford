"""
app_oxford.py  -  Configurar Oxford English Hub
Centro Colombo Americano - Bogota

Reemplaza la edicion manual de 'Config Oxford.txt' y 'Credenciales Oxford.txt'
por una interfaz guiada con perfiles guardables, tabla editable de clases y
escritura directa a los .txt que lee automatizar_oxford.py.

Solo usa: Python 3.13, customtkinter, tkinter estandar, json, subprocess.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

import customtkinter as ctk

# La identidad visual vive en app_colombo/tema_colombo.py (compartida con Q10 y Macmillan)
_APP_COLOMBO = Path(__file__).resolve().parents[2] / "aplicacion"
if str(_APP_COLOMBO) not in sys.path:
    sys.path.insert(0, str(_APP_COLOMBO))
from tema_colombo import Marca, tipografia  # noqa: E402

_TIPO = tipografia()

# ──────────────────────────────────────────────────── Rutas
if getattr(sys, "frozen", False):
    # Ejecutable PyInstaller: __file__ apunta a una carpeta temporal,
    # asi que usamos la carpeta donde vive el .exe.
    PRACTICA = Path(sys.executable).parent
    ROOT = PRACTICA   # el bot va integrado en el .exe; los .txt viven junto a el
    RECURSOS = Path(getattr(sys, "_MEIPASS", PRACTICA))
else:
    PRACTICA = Path(__file__).parent       # herramientas/oxford/ (perfiles_oxford.json)
    ROOT = PRACTICA.parents[1]             # raiz del proyecto
    RECURSOS = ROOT / "datos"              # plantilla de clases
PERFILES_JSON    = PRACTICA / "perfiles_oxford.json"
CREDENCIALES_TXT = ROOT / "Credenciales Oxford.txt"
CONFIG_TXT       = ROOT / "Config Oxford.txt"
BOT_EXE          = ROOT / "Bot Oxford.exe"        # empaquetado: junto a esta aplicacion
BOT_SCRIPT       = ROOT / "bots" / "oxford" / "automatizar_oxford.py"
VENV_PYTHON      = ROOT / ".venv" / "Scripts" / "python.exe"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


# ─────────────────────────────────────────────────────── Tema
class T:
    """Identidad Colombo Americano (valores en tema_colombo.py)."""
    PRIM     = Marca.AZUL
    PRIM_H   = Marca.AZUL_H
    PRIM_OSC = Marca.AZUL_OSC
    SB_TXT   = "#C9D8EA"
    ACC      = Marca.ROJO
    ACC_H    = Marca.ROJO_H
    FONDO    = Marca.FONDO
    SUP      = Marca.BLANCO
    BORDE    = Marca.BORDE
    TEXTO    = Marca.TEXTO
    SUAVE    = Marca.TEXTO_SUAVE
    OK       = Marca.OK
    OK_BG    = Marca.OK_FONDO
    WARN     = Marca.AVISO
    WRN_BG   = Marca.AVISO_FONDO
    ERR      = Marca.ERROR
    ERR_H    = Marca.ROJO_H
    ERR_BG   = Marca.ERROR_FONDO
    ERR_BG_H = "#F6CDD1"
    DIS      = Marca.DESHABILITADO
    F      = _TIPO["F"]
    TIT    = _TIPO["H2"]
    SUB    = (F, 11)
    SEC    = (F, 12, "bold")
    ETQ    = _TIPO["ETIQUETA"]
    NRM    = _TIPO["NORMAL"]
    AYD    = _TIPO["AYUDA"]
    BTN    = _TIPO["BOTON"]
    BTNG   = _TIPO["BOTON_G"]
    R      = Marca.RADIO


# ─────────────────────────────────────────────────── Helpers
def leer_txt(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    out = {}
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        if ":" in linea and not linea.strip().startswith("#"):
            k, v = linea.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def escribir_credenciales(user: str, pw: str, link: str) -> None:
    CREDENCIALES_TXT.write_text(
        f"User : {user}\nPassword : {pw}\nLink : {link}\n",
        encoding="utf-8")


def escribir_config(id_org: str, clases: list, scores: str,
                    figuras: str, mostrar: str, ruta_descarga: str,
                    version: str = "Closing soon") -> None:
    texto_ruta = f"Ruta Descargas : {ruta_descarga}\n" if ruta_descarga else ""
    CONFIG_TXT.write_text(
        f"# ID del convenio en My Organizations\n"
        f"ID : {id_org}\n\n"
        f"# Clases separadas por coma\n"
        f"Clases : {', '.join(clases)}\n\n"
        f"# Version del libro a descargar: Closing soon o Upgraded version\n"
        f"Version : {version}\n\n"
        f"# Progress settings\n"
        f"Scores : {scores}\n"
        f"Show figures as : {figuras}\n"
        f"Show scores for : {mostrar}\n"
        f"{texto_ruta}",
        encoding="utf-8")


# Columnas validas que pueden contener IDs de clase
_ENCABEZADOS_VALIDOS = {"clase", "clases", "class", "nombre", "name", "id", "class id",
                        "class name", "codigo", "code", "id clase"}
# Si la primera celda NO es nula y NO coincide con ningun encabezado conocido
# ni parece un ID de clase (alfanumerico), mostramos advertencia
_PLANTILLA_INCORRECTA_HINT = (
    "El archivo seleccionado puede no ser la planilla correcta.\n"
    "Asegurate de que la primera columna contenga los IDs de clase\n"
    "(columna con encabezado: Clase, Class, ID, Nombre, etc.).\n\n"
    "Continuar de todas formas?"
)

def _parece_id_clase(texto: str) -> bool:
    """Heuristica: un ID de clase es alfanumerico, puede tener guiones/puntos/espacios."""
    import re
    return bool(re.match(r"^[\w\s.\-]{3,60}$", texto))

def leer_excel_col1(ruta: str) -> list:
    from openpyxl import load_workbook
    libro = load_workbook(ruta, data_only=True)
    hoja  = libro.active
    SKIP  = _ENCABEZADOS_VALIDOS
    vals  = []

    primera_celda = None
    for i, fila in enumerate(hoja.iter_rows(min_col=1, max_col=1, values_only=True)):
        t = str(fila[0]).strip() if fila[0] is not None else ""
        if not t:
            continue
        if i == 0:
            primera_celda = t
        if t.lower() not in SKIP:
            vals.append(t)

    libro.close()

    # Validacion de plantilla: si la columna no tiene encabezado reconocido
    # y los valores no parecen IDs de clase, advertir al usuario
    if primera_celda and primera_celda.lower() not in SKIP:
        # La primera fila es un dato, no un encabezado -> validar contenido
        if vals and not all(_parece_id_clase(v) for v in vals[:5]):
            raise ValueError(
                "Plantilla no reconocida: la primera columna no parece contener "
                "IDs de clase.\nRevisa que hayas seleccionado el archivo correcto."
            )
    elif not vals:
        raise ValueError(
            "No se encontraron clases en la primera columna del archivo.\n"
            "Verifica que la planilla tenga los IDs en la columna A."
        )

    return vals


# ─────────────────────────────────────────── Excel de usuarios (pruebas Wide Angle)
USUARIOS_XLSX    = ROOT / "Usuarios Oxford.xlsx"
PRUEBAS_EXE      = ROOT / "Bot Pruebas Oxford.exe"
PRUEBAS_SCRIPT   = ROOT / "empaquetado" / "entrada_pruebas_oxford.py"
NIVELES_WIDE_ANGLE = (3, 4, 5)
UNIDADES_POR_DEFECTO = "1,2,3"
UNIDADES_TODAS = "1,2,3,4,5,6,7,8,9,10,11,12"   # defecto de las fórmulas (libro completo)
COLUMNAS_USUARIOS = ("Usuario", "Contraseña", "Nivel", "Unidades", "Usar", "Código organización", "Estado",
                     "Online Practice", "Ebook")
COL_ESTADO = COLUMNAS_USUARIOS.index("Estado") + 1

# ── Directorio ('Hoja1'): roster que se pega una vez; la hoja 'Usuarios' trae todo desde aquí por username.
# Columnas de la plantilla nueva (si se crea desde cero). Un roster ya existente se usa tal cual: las
# columnas se localizan por su encabezado, no por su posición (ver _idx_columnas / _detectar_columnas).
COLUMNAS_DIRECTORIO = ("Usuario", "Contraseña", "Nivel de inglés", "Código organización",
                       "Online Practice", "Ebook")
HOJAS_DIRECTORIO = ("Hoja1", "Base", "Directorio")   # nombres aceptados para la hoja del roster
FILAS_FORMULA = 1500                                 # cuántas filas de 'Usuarios' llevan fórmulas listas
INTERVALO_VOLCADO_MS = 30_000                        # cada cuánto se escriben al Excel los Estados acumulados

# Lecturas/escrituras del Excel de usuarios: corren en hilos (para no congelar la ventana), nunca dos a la vez.
_LOCK_EXCEL = threading.RLock()


def en_hilo(widget, trabajo: Callable, al_terminar: Callable) -> None:
    """Corre trabajo() en un hilo y luego llama al_terminar(resultado, error) en el hilo de Tk.

    El hilo no toca la interfaz: el hilo de Tk revisa cada 50 ms si ya terminó (after), que es lo seguro en Tkinter.
    """
    caja: dict = {}

    def correr():
        try:
            caja["res"] = trabajo()
        except Exception as e:          # se entrega a al_terminar
            caja["err"] = e

    hilo = threading.Thread(target=correr, daemon=True)
    hilo.start()

    def revisar():
        if hilo.is_alive():
            widget.after(50, revisar)
        else:
            al_terminar(caja.get("res"), caja.get("err"))
    widget.after(50, revisar)
# Nivel de inglés (curso/clase) → libro Wide Angle. En el roster el curso viene como 'B2.1-6AM57…'.
NIVEL_POR_CLASE = (("B1.1", 3), ("B1.2", 4), ("B2.1", 5))


def nivel_desde_clase(texto: str) -> int:
    """'B1.1…' → 3, 'B1.2…' → 4, 'B2.1…' → 5 (busca el código dentro del texto; sirve 'B1.1' o 'B1.1-8AM64'). 0 si no aparece."""
    t = (texto or "").upper()
    for codigo, libro in NIVEL_POR_CLASE:
        if codigo in t:
            return libro
    return 0


def clase_desde_nivel(nivel) -> str:
    """Inverso: 3 → 'B1.1', 4 → 'B1.2', 5 → 'B2.1' (para migrar datos existentes al directorio). '' si no coincide."""
    objetivo = str(nivel).strip().replace(".0", "")
    for codigo, libro in NIVEL_POR_CLASE:
        if objetivo == str(libro):
            return codigo
    return ""


def _idx_columnas(encabezados: list) -> dict:
    """Ubica las columnas del roster por su encabezado (en minúsculas). Devuelve índices 0-based (o None).

    Las claves se prueban EN ORDEN: la primera palabra clave que aparezca gana. Así 'Curso' se prefiere
    antes que caer en 'Codigo clase Oxford' para el nivel de inglés.
    """
    def idx(*claves):
        for clave in claves:
            for i, h in enumerate(encabezados):
                if clave in h:
                    return i
        return None

    return {
        "key":   idx("usuario", "user"),                         # 'Usuario Oxford'
        "clave": idx("contrase", "password"),                    # 'Contraseña'
        "curso": idx("curso", "nivel de ingl", "nivel", "ingl"),  # 'Curso' (B2.1-…) / 'Nivel de inglés'
        "org":   idx("organiz"),                                 # 'Codigo Organización'
        "op":    idx("online practice", "practice", "práctica", "practica"),
        "ebook": idx("ebook", "e-book"),
    }


def _detectar_columnas(hoja) -> dict | None:
    """Columnas del roster en 'hoja' (índices 0-based por encabezado). None si no hay columna de usuario."""
    primera = next(hoja.iter_rows(min_row=1, max_row=1, values_only=True), ())   # sirve también en read_only
    encabezados = [(str(v).strip().lower() if v is not None else "") for v in primera]
    cols = _idx_columnas(encabezados)
    return cols if cols["key"] is not None else None


def _formulas_fila(fila: int, cols: dict, hoja_dir: str = "Hoja1") -> dict:
    """Fórmulas de una fila de 'Usuarios'. El username va en A; el resto se trae de 'hoja_dir' con INDEX/MATCH
    (el username puede estar en cualquier columna del roster, no solo la primera). 'cols' = _detectar_columnas."""
    from openpyxl.utils import get_column_letter

    a = f"$A{fila}"
    key = get_column_letter(cols["key"] + 1)
    m = f"MATCH({a},{hoja_dir}!${key}:${key},0)"

    def trae(nombre_col: str) -> str:
        i = cols.get(nombre_col)
        if i is None:
            return f'=IF({a}="","","")'
        L = get_column_letter(i + 1)
        return f'=IFERROR(INDEX({hoja_dir}!${L}:${L},{m}),"")'

    curso = cols.get("curso")
    if curso is None:
        nivel_formula = f'=IF({a}="","","")'
    else:
        clz = f"INDEX({hoja_dir}!${get_column_letter(curso + 1)}:${get_column_letter(curso + 1)},{m})"
        # IFS (SI.CONJUNTO): más legible que SI anidados. Requiere Excel 2019/365. OJO: las funciones
        # posteriores a 2007 se guardan en el XML con el prefijo '_xlfn.'; sin él Excel la lee como
        # desconocida ('_xludf.IFS' / #¿NOMBRE?). Excel la muestra igual como 'SI.CONJUNTO'. Si ninguno
        # coincide IFS da #N/A → IFERROR lo deja en "" (como el 'else' vacío de la versión con IF anidado).
        nivel_formula = (f'=IFERROR(_xlfn.IFS(ISNUMBER(SEARCH("B1.1",{clz})),3,'
                         f'ISNUMBER(SEARCH("B1.2",{clz})),4,'
                         f'ISNUMBER(SEARCH("B2.1",{clz})),5),"")')
    return {
        "B": trae("clave"),                             # Contraseña
        "C": nivel_formula,                             # Nivel (libro) desde el curso
        "D": f'=IF({a}="","","{UNIDADES_TODAS}")',      # Unidades (libro completo)
        "E": f'=IF({a}="","","Sí")',                    # Usar
        "F": trae("org"),                               # Código organización
        "H": trae("op"),                                # Online Practice
        "I": trae("ebook"),                             # Ebook
    }


def _leer_directorio(libro) -> dict:
    """Lee el roster ('Hoja1'/'Base'/'Directorio') como {usuario_minúsculas: {clave, clase, codigo, op, ebook}}.

    Localiza las columnas por su encabezado (tolerante al orden). {} si no hay hoja o no tiene columna de usuario.
    """
    nombre = next((h for h in HOJAS_DIRECTORIO if h in libro.sheetnames), None)
    if not nombre:
        return {}
    hoja = libro[nombre]
    if hasattr(hoja, "reset_dimensions"):   # read_only: no confiar en la dimensión guardada en el archivo
        hoja.reset_dimensions()
    cols = _detectar_columnas(hoja)
    if not cols:
        return {}
    directorio = {}
    for fila in hoja.iter_rows(min_row=2, values_only=True):
        def g(nombre_col):
            i = cols.get(nombre_col)
            return "" if i is None or i >= len(fila) or fila[i] is None else str(fila[i]).strip()
        usuario = g("key")
        if not usuario:
            continue
        directorio[usuario.lower()] = {"clave": g("clave"), "clase": g("curso"), "codigo": g("org"),
                                       "op": g("op"), "ebook": g("ebook")}
    return directorio


def _preparar_hoja_usuarios(hoja, cols: dict) -> None:
    """Deja la hoja 'Usuarios' con encabezados y las fórmulas de FILAS_FORMULA filas (A = username; B..I desde el roster)."""
    from openpyxl.styles import Alignment, Font, PatternFill

    hoja.append(COLUMNAS_USUARIOS)
    for c in hoja[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="004C97")
        c.alignment = Alignment(horizontal="center")
    for col, ancho in zip("ABCDEFGHI", (34, 22, 9, 24, 8, 20, 70, 22, 22)):
        hoja.column_dimensions[col].width = ancho
    gris = Font(color="808080")
    for fila in range(2, FILAS_FORMULA + 2):
        for col, formula in _formulas_fila(fila, cols).items():
            celda = hoja[f"{col}{fila}"]
            celda.value = formula
            celda.font = gris          # en gris: recuerda que es automático (no lo escribas a mano)


def _preparar_hoja_directorio(libro):
    """Crea/devuelve la hoja 'Hoja1' (directorio) con encabezados y validación de 'Nivel de inglés'."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    base = libro["Hoja1"] if "Hoja1" in libro.sheetnames else libro.create_sheet("Hoja1")
    primera = next(base.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not primera or all(v in (None, "") for v in primera):   # sin encabezados: escribirlos en la fila 1
        for col, titulo in enumerate(COLUMNAS_DIRECTORIO, start=1):
            base.cell(row=1, column=col, value=titulo)
    for c in base[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="007A33")
        c.alignment = Alignment(horizontal="center")
    for col, ancho in zip("ABCDEF", (34, 22, 16, 22, 24, 24)):
        base.column_dimensions[col].width = ancho
    clases = DataValidation(type="list", formula1='"B1.1,B1.2,B2.1"', allow_blank=True)
    base.add_data_validation(clases)
    clases.add("C2:C1000")
    return base


def crear_plantilla_usuarios(ruta: Path = USUARIOS_XLSX) -> None:
    """Crea 'Usuarios Oxford.xlsx': hoja 'Usuarios' (solo se escribe el username; B..I por fórmula) +
    'Hoja1' (directorio que se pega una vez) + 'Cómo se usa'."""
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Usuarios"

    base = _preparar_hoja_directorio(libro)
    base.append(("usuario.ejemplo", "ClaveDelUsuario", "B1.1", "6l12z", "S-000-000-0000", "XXXX-XXXX-XXXX"))
    _preparar_hoja_usuarios(hoja, _detectar_columnas(base))   # las fórmulas apuntan a las columnas del roster

    ayuda = libro.create_sheet("Cómo se usa")
    for linea in (
        "FLUJO: pega el roster en la hoja 'Hoja1' UNA sola vez. Luego, en la hoja 'Usuarios', escribe solo el "
        "USERNAME en la columna A; las columnas B a I se llenan solas con fórmulas (en gris).",
        "",
        "Hoja 'Hoja1' (directorio): una fila por usuario con Usuario, Contraseña, Nivel de inglés, "
        "Código organización, Online Practice y Ebook.",
        "  • Nivel de inglés: escribe la clase o el nivel. B1.1 = libro Level 3, B1.2 = Level 4, B2.1 = Level 5. "
        "Sirve 'B1.1' o la clase completa 'B1.1-8AM64' (se detecta el código).",
        "",
        "Hoja 'Usuarios' (lo que corre el bot):",
        "  • Usuario (A): el username. Es lo ÚNICO que escribes.",
        "  • Contraseña, Nivel, Unidades, Usar, Código organización, Online Practice, Ebook (B..I): fórmulas. "
        "No las escribas; si un username no está en 'Hoja1' salen vacías.",
        f"  • Unidades por defecto = {UNIDADES_TODAS} (libro completo). Puedes sobrescribir una celda escribiéndola.",
        "  • Usar: sale 'Sí' automático cuando hay username. Escribe 'No' en la celda para saltar esa fila.",
        "  • Estado: lo escribe la aplicación (no lo llenes).",
        "",
        "Contraseña/Código organización vacíos = se usan los de 'Credenciales Oxford.txt'.",
        "Online Practice y Ebook: solo se usan si el libro sale con candado (sin licencia); vacío = queda BLOQUEADO.",
        "Guarda y cierra el Excel antes de ejecutar las pruebas.",
        "Las pruebas ESCRIBEN intentos reales en la cuenta: usa cuentas de prueba, no de alumnos.",
    ):
        ayuda.append((linea,))
    ayuda.column_dimensions["A"].width = 115
    ruta.parent.mkdir(parents=True, exist_ok=True)
    libro.save(ruta)


def completar_columnas_usuarios(ruta: Path = USUARIOS_XLSX) -> None:
    """Agrega los encabezados que falten (Excel creado por una version anterior, sin 'Código organización').

    Si el archivo esta abierto en Excel no se puede guardar: se deja como esta (PermissionError).
    """
    from copy import copy
    from openpyxl import load_workbook

    libro = load_workbook(ruta)
    hoja = libro["Usuarios"] if "Usuarios" in libro.sheetnames else libro.worksheets[0]
    cambio = False
    for n, nombre in enumerate(COLUMNAS_USUARIOS, start=1):
        celda = hoja.cell(row=1, column=n)
        if celda.value in (None, ""):
            celda.value = nombre
            modelo = hoja.cell(row=1, column=min(n, 5))
            celda.font, celda.fill, celda.alignment = copy(modelo.font), copy(modelo.fill), copy(modelo.alignment)
            hoja.column_dimensions[celda.column_letter].width = 70 if nombre == "Estado" else 22
            cambio = True
    if cambio:
        libro.save(ruta)
    libro.close()


def texto_estado(resultado: str, motivo: str) -> str:
    """Texto de la columna 'Estado' para el resultado de un usuario (OK / BLOQUEADO / FALLO)."""
    marca = datetime.now().strftime("%d/%m %H:%M")
    if resultado == "OK":
        return f"OK {marca}" + (f" ({motivo})" if motivo else "")
    if resultado == "BLOQUEADO":
        return f"BLOQUEADO {marca}: {motivo}"
    return f"ERROR {marca}: {motivo or 'revisa el log y las capturas'}"


def color_estado(texto: str) -> str:
    """Color de la UI segun como empieza el 'Estado' del Excel."""
    if texto.startswith("OK"):
        return T.OK
    if texto.startswith(("BLOQUEADO", "EJECUTANDO")):
        return T.WARN
    return T.ERR if texto.startswith("ERROR") else T.TEXTO


def escribir_estados_usuarios(estados: dict[int, str], ruta: Path = USUARIOS_XLSX) -> None:
    """Escribe en la columna 'Estado' el resultado de cada fila ({numero de fila del Excel: texto}).

    Verde si empieza con 'OK', rojo si empieza con 'ERROR'. Lanza PermissionError si el Excel esta abierto.
    """
    from openpyxl import load_workbook
    from openpyxl.styles import Font

    libro = load_workbook(ruta)
    hoja = libro["Usuarios"] if "Usuarios" in libro.sheetnames else libro.worksheets[0]
    if hoja.cell(row=1, column=COL_ESTADO).value in (None, ""):
        hoja.cell(row=1, column=COL_ESTADO).value = "Estado"
    for fila, texto in estados.items():
        celda = hoja.cell(row=fila, column=COL_ESTADO)
        celda.value = texto
        color = "007A33" if texto.startswith("OK") else "B36B00" if texto.startswith("EJECUTANDO") else "C00000"
        celda.font = Font(color=color, bold=True)
    libro.save(ruta)
    libro.close()


def leer_usuarios(ruta: Path = USUARIOS_XLSX) -> list[dict]:
    """Filas de la hoja 'Usuarios': {usuario, clave, nivel, unidades, usar, error}.

    'error' es "" si la fila se puede ejecutar. La contraseña vacía se completa con la de
    'Credenciales Oxford.txt'. Las filas sin usuario se ignoran.
    """
    from openpyxl import load_workbook

    cred = leer_txt(CREDENCIALES_TXT)
    clave_comun = cred.get("password", "")
    codigo_comun = next((v for k, v in cred.items() if k.startswith("codigo")), "")
    # read_only: lectura en streaming, mucho más rápida con cientos de filas (las filas vacías se rellenan,
    # así que n_fila sigue siendo el número real de fila del Excel).
    libro = load_workbook(ruta, data_only=True, read_only=True)
    hoja = libro["Usuarios"] if "Usuarios" in libro.sheetnames else libro.worksheets[0]
    hoja.reset_dimensions()
    directorio = _leer_directorio(libro)   # roster de 'Hoja1' (respaldo cuando la celda-fórmula viene vacía)
    filas = []
    for n_fila, fila in enumerate(hoja.iter_rows(min_row=2, values_only=True), start=2):
        celdas = [("" if v is None else str(v).strip()) for v in (list(fila) + [None] * 9)[:9]]
        usuario, clave, nivel, unidades, usar, codigo, estado = celdas[:7]
        cod_practica, cod_ebook = celdas[7], celdas[8]
        if not usuario:
            continue
        # Respaldo: si las columnas de fórmula vienen vacías (p.ej. el caché se perdió al escribir 'Estado'),
        # se resuelven desde el directorio 'Hoja1' por username. No pisa lo que esté escrito a mano.
        ref = directorio.get(usuario.lower())
        if ref:
            clave = clave or ref["clave"]
            codigo = codigo or ref["codigo"]
            cod_practica = cod_practica or ref["op"]
            cod_ebook = cod_ebook or ref["ebook"]
            if not nivel:
                nivel_ref = nivel_desde_clase(ref["clase"])
                nivel = str(nivel_ref) if nivel_ref else ""
            if not unidades:
                unidades = UNIDADES_TODAS
        error = ""
        try:
            nivel_n = int(float(nivel))
            if nivel_n not in NIVELES_WIDE_ANGLE:
                error = f"Nivel {nivel_n} no existe (usa {' o '.join(map(str, NIVELES_WIDE_ANGLE))})"
        except ValueError:
            nivel_n, error = 0, "Falta el Nivel (3, 4 o 5)"
        unidades = unidades.replace(".0", "") or UNIDADES_POR_DEFECTO
        if not re.fullmatch(r"\d+(\s*,\s*\d+)*", unidades):
            error = error or f"Unidades '{unidades}' no válidas (ej: 1,2,3)"
        clave = clave or clave_comun
        if not clave and not error:
            error = "Sin contraseña (ponla en el Excel o en 'Credenciales Oxford.txt')"
        filas.append({"fila": n_fila, "usuario": usuario, "clave": clave, "nivel": nivel_n,
                      "codigo": codigo or codigo_comun,
                      "cod_practica": cod_practica, "cod_ebook": cod_ebook,
                      "unidades": re.sub(r"\s+", "", unidades),
                      "usar": usar.lower() not in ("no", "n", "false", "0"), "error": error,
                      "estado": estado})
    libro.close()
    return filas


# ─────────────────────────────────────────── Perfiles JSON
PERFIL_VACIO = {
    "nombre": "Nuevo perfil",
    "id_org": "",
    "clases": [],
    "scores": "Show best attempt",
    "show_figures_as": "Percentages",
    "show_scores_for": "All activities",
    "version": "Closing soon",
    "ruta_descarga": "",
    "user": "",
    "password": "",
    "link": "https://englishhub.oup.com",
}


def cargar_perfiles() -> list:
    if PERFILES_JSON.exists():
        try:
            d = json.loads(PERFILES_JSON.read_text(encoding="utf-8"))
            if isinstance(d, list):
                return d
        except Exception:
            pass
    return []


def guardar_perfiles(ps: list) -> None:
    PERFILES_JSON.write_text(
        json.dumps(ps, ensure_ascii=False, indent=2), encoding="utf-8")


# ───────────────────────────── Dialogo pegar clases
class DlgPegarClases(ctk.CTkToplevel):
    def __init__(self, master, actuales: list, al_ok: Callable):
        super().__init__(master)
        self.al_ok = al_ok
        self.title("Pegar lista de clases")
        self.geometry("620x500")
        self.configure(fg_color=T.FONDO)
        self.grab_set()

        ctk.CTkLabel(self, text="Pegar lista de clases",
                     font=T.TIT, text_color=T.PRIM
                     ).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(self,
                     text="Pega las clases separadas por coma (,) o una por linea.\n"
                          "Al aceptar reemplazara la lista actual.",
                     font=T.AYD, text_color=T.SUAVE, justify="left"
                     ).pack(anchor="w", padx=20, pady=(0, 10))

        self.txt = ctk.CTkTextbox(self, fg_color=T.SUP,
                                   border_color=T.BORDE, border_width=1,
                                   font=T.NRM)
        self.txt.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        if actuales:
            self.txt.insert("1.0", "\n".join(actuales))

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=20, pady=(0, 18))
        pie.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(pie, text="Cancelar", font=T.BTN, height=36,
                      fg_color=T.SUP, hover_color=T.FONDO,
                      text_color=T.TEXTO, border_width=1, border_color=T.BORDE,
                      command=self.destroy
                      ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(pie, text="Aceptar", font=T.BTN, height=36,
                      fg_color=T.PRIM, hover_color=T.PRIM_H, text_color="white",
                      command=self._ok
                      ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _ok(self):
        raw = self.txt.get("1.0", "end")
        clases = [c.strip()
                  for parte in raw.replace(",", "\n").splitlines()
                  for c in [parte.strip()] if c]
        self.al_ok(clases)
        self.destroy()


# ───────────────────────────── Dialogo nombre perfil
class DlgNombre(ctk.CTkToplevel):
    def __init__(self, master, actual: str, al_ok: Callable):
        super().__init__(master)
        self.al_ok = al_ok
        self.title("Nombre del perfil")
        self.geometry("400x170")
        self.configure(fg_color=T.FONDO)
        self.grab_set()
        ctk.CTkLabel(self, text="Nombre del perfil:", font=T.ETQ,
                     text_color=T.TEXTO).pack(anchor="w", padx=20, pady=(20, 4))
        self.ent = ctk.CTkEntry(self, fg_color=T.SUP, border_color=T.BORDE,
                                 height=34, font=T.NRM)
        self.ent.insert(0, actual)
        self.ent.pack(fill="x", padx=20)
        self.ent.bind("<Return>", lambda _: self._ok())
        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=20, pady=14)
        pie.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(pie, text="Cancelar", font=T.BTN, height=34,
                      fg_color=T.SUP, hover_color=T.FONDO,
                      text_color=T.TEXTO, border_width=1, border_color=T.BORDE,
                      command=self.destroy
                      ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(pie, text="Aceptar", font=T.BTN, height=34,
                      fg_color=T.PRIM, hover_color=T.PRIM_H, text_color="white",
                      command=self._ok
                      ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _ok(self):
        n = self.ent.get().strip()
        if n:
            self.al_ok(n)
            self.destroy()


# ───────────────────────────── Dialogo nuevo perfil
class DlgNuevoPerfil(ctk.CTkToplevel):
    def __init__(self, master, al_ok: Callable):
        super().__init__(master)
        self.al_ok = al_ok
        self.title("Nuevo perfil")
        self.geometry("420x260")
        self.configure(fg_color=T.FONDO)
        self.grab_set()
        ctk.CTkLabel(self, text="Nombre del perfil:", font=T.ETQ,
                     text_color=T.TEXTO).pack(anchor="w", padx=20, pady=(20, 4))
        self.ent_n = ctk.CTkEntry(self, fg_color=T.SUP, border_color=T.BORDE,
                                   height=34, font=T.NRM)
        self.ent_n.pack(fill="x", padx=20)
        ctk.CTkLabel(self, text="ID de la organizacion (My Organizations):",
                     font=T.ETQ, text_color=T.TEXTO
                     ).pack(anchor="w", padx=20, pady=(14, 4))
        self.ent_id = ctk.CTkEntry(self, fg_color=T.SUP, border_color=T.BORDE,
                                    height=34, font=T.NRM,
                                    placeholder_text="Ej: 18xaf")
        self.ent_id.pack(fill="x", padx=20)
        self.ent_id.bind("<Return>", lambda _: self._ok())
        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=20, pady=16)
        pie.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(pie, text="Cancelar", font=T.BTN, height=34,
                      fg_color=T.SUP, hover_color=T.FONDO,
                      text_color=T.TEXTO, border_width=1, border_color=T.BORDE,
                      command=self.destroy
                      ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(pie, text="Guardar perfil", font=T.BTN, height=34,
                      fg_color=T.PRIM, hover_color=T.PRIM_H, text_color="white",
                      command=self._ok
                      ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.after(100, self.ent_n.focus)

    def _ok(self):
        n = self.ent_n.get().strip()
        i = self.ent_id.get().strip()
        if not n:
            messagebox.showwarning("Falta nombre", "Escribe el nombre del perfil.", parent=self)
            return
        if not i:
            messagebox.showwarning("Falta ID", "Escribe el ID de la organizacion.", parent=self)
            return
        self.al_ok(n, i)
        self.destroy()


# ───────────────────────────── Dialogo confirmar pruebas Wide Angle
class DlgConfirmarPruebas(ctk.CTkToplevel):
    """Confirma las pruebas antes de lanzarlas: resumen arriba y, abajo, la lista de usuarios
    agrupada por proceso (nivel + unidades) con su propio scroll, para que con muchos usuarios
    no quede un parrafo enorme como en un messagebox.

    Uso:  dlg = DlgConfirmarPruebas(master, grupos); master.wait_window(dlg); dlg.aceptado
    """
    def __init__(self, master, grupos: list):
        super().__init__(master)
        self.aceptado = False
        self.paralelas = 3                       # cuentas corriendo a la vez (lo fija el usuario abajo)
        self._var_paralelas = ctk.StringVar(value="3")
        total = sum(len(us) for _, _, us in grupos)
        niveles = sorted({str(n) for n, _, _ in grupos}, key=lambda s: (len(s), s))
        self.title("Ejecutar pruebas")
        # Alto segun lo que haya que mostrar (~26 px por grupo), con tope: si son muchos, la lista hace scroll
        alto = 560 if len(grupos) <= 5 else 640
        self.geometry(f"640x{alto}")
        self.minsize(520, 480)
        self.configure(fg_color=T.FONDO)
        # Ventana normal (sin transient ni grab_set) para que Windows muestre minimizar/maximizar/cerrar.
        # Que no se abran dos a la vez lo controla VistaOxford (_preparando).
        self.after(50, lambda: self._centrar(master.winfo_toplevel()))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _: self.destroy())

        ctk.CTkLabel(self, text="¿Ejecutar las pruebas?", font=T.TIT, text_color=T.PRIM
                     ).pack(anchor="w", padx=20, pady=(18, 0))
        ctk.CTkLabel(self, text="Revisa a quién se le harán las pruebas antes de empezar.",
                     font=T.AYD, text_color=T.SUAVE).pack(anchor="w", padx=20, pady=(0, 12))

        # Resumen: tres cifras que se leen de un vistazo
        resumen = ctk.CTkFrame(self, fg_color="transparent")
        resumen.pack(fill="x", padx=20)
        resumen.grid_columnconfigure((0, 1, 2), weight=1, uniform="r")
        for col, (cifra, texto) in enumerate((
                (str(total), "usuario" if total == 1 else "usuarios"),
                (str(len(grupos)), "proceso" if len(grupos) == 1 else "procesos"),
                (", ".join(niveles), "nivel" if len(niveles) == 1 else "niveles"))):
            caja = ctk.CTkFrame(resumen, fg_color=T.SUP, corner_radius=T.R,
                                border_width=1, border_color=T.BORDE)
            caja.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))
            ctk.CTkLabel(caja, text=cifra, font=(T.F, 20, "bold"), text_color=T.PRIM
                         ).pack(pady=(8, 0))
            ctk.CTkLabel(caja, text=texto, font=T.AYD, text_color=T.SUAVE).pack(pady=(0, 8))

        # Lista agrupada: un solo ttk.Treeview (un grupo por fila; sus usuarios se ven al desplegarlo).
        # Antes era una etiqueta por usuario y con cientos de usuarios la ventana se congelaba.
        # (se empaca al final: así la lista se encoge y los botones de abajo nunca quedan cortados)
        marco = ctk.CTkFrame(self, fg_color=T.SUP, corner_radius=T.R, border_width=1, border_color=T.BORDE)
        marco.grid_rowconfigure(0, weight=1)
        marco.grid_columnconfigure(0, weight=1)
        estilo = ttk.Style(self)
        estilo.configure("Grupos.Treeview", font=T.NRM, rowheight=24, background=T.SUP,
                         fieldbackground=T.SUP, foreground=T.TEXTO, borderwidth=0)
        estilo.configure("Grupos.Treeview.Heading", font=T.ETQ, foreground=T.PRIM)
        arbol = ttk.Treeview(marco, columns=("usuarios",), style="Grupos.Treeview", selectmode="none", height=5)
        arbol.heading("#0", text="Proceso  ·  libro  ·  unidades (despliega para ver los usuarios)", anchor="w")
        arbol.heading("usuarios", text="Usuarios", anchor="e")
        arbol.column("#0", width=440, stretch=True, anchor="w")
        arbol.column("usuarios", width=90, stretch=False, anchor="e")
        arbol.tag_configure("grupo", foreground=T.PRIM)
        for i, (nivel, unidades, usuarios) in enumerate(grupos, start=1):
            padre = arbol.insert("", "end", text=f"{i}.  Wide Angle {nivel}  ·  Unidades {unidades}",
                                 values=(len(usuarios),), tags=("grupo",), open=len(grupos) == 1 and len(usuarios) <= 30)
            for u in usuarios:
                arbol.insert(padre, "end", text=f"    {u['usuario']}", values=("",))
        barra_y = ctk.CTkScrollbar(marco, command=arbol.yview)
        arbol.configure(yscrollcommand=barra_y.set)
        arbol.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        barra_y.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=6)

        # Cuantas cuentas trabajan a la vez (pool). Mas = mas rapido, pero mas memoria/CPU y mas
        # sesiones simultaneas contra Oxford: por eso el tope razonable es 3-4.
        velo = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(velo, text="Cuentas en paralelo:", font=T.SEC, text_color=T.TEXTO
                     ).pack(side="left")
        ctk.CTkOptionMenu(velo, width=72, variable=self._var_paralelas,
                          values=["1", "2", "3", "4", "5"], font=T.NRM,
                          fg_color=T.SUP, button_color=T.PRIM, button_hover_color=T.PRIM_H,
                          text_color=T.TEXTO).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(velo, text="(más rápido, pero usa más memoria)", font=T.AYD,
                     text_color=T.SUAVE).pack(side="left", padx=(8, 0))

        aviso = ctk.CTkFrame(self, fg_color=T.WRN_BG, corner_radius=T.R)
        ctk.CTkLabel(aviso, text="⚠  Se escribirán intentos REALES en cada cuenta. Trabaja en segundo "
                                 "plano: el avance se ve en la ventana de progreso. Varias cuentas "
                                 "corren a la vez, así que las líneas del log se intercalan y el "
                                 "Estado se anota a medida que cada una termina.",
                     font=T.AYD, text_color=T.WARN, justify="left", wraplength=560, anchor="w"
                     ).pack(fill="x", padx=12, pady=8)

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(pie, text="Cancelar", font=T.BTN, height=38,
                      fg_color=T.SUP, hover_color=T.FONDO,
                      text_color=T.TEXTO, border_width=1, border_color=T.BORDE,
                      command=self.destroy
                      ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(pie, text=f"▶  Ejecutar pruebas ({total})", font=T.BTN, height=38,
                      fg_color=T.OK, hover_color=T.PRIM_H, text_color="white",
                      command=self._ok
                      ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Abajo primero (de abajo hacia arriba) y la lista al final: si la ventana es baja, se encoge la lista.
        pie.pack(side="bottom", fill="x", padx=20, pady=(12, 18))
        aviso.pack(side="bottom", fill="x", padx=20)
        velo.pack(side="bottom", fill="x", padx=20, pady=(0, 10))
        marco.pack(fill="both", expand=True, padx=20, pady=12)

    def _centrar(self, ventana):
        """Centra el dialogo sobre la ventana principal (sin salirse de la pantalla) y lo trae al frente."""
        import tkinter as tk
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()           # pixeles reales (ya con el escalado)
        h = min(h, self.winfo_screenheight() - 120)               # que quepa sobre la barra de tareas
        x = ventana.winfo_rootx() + (ventana.winfo_width() - w) // 2
        y = ventana.winfo_rooty() + (ventana.winfo_height() - h) // 2
        x = max(0, min(x, self.winfo_screenwidth() - w))
        y = max(0, min(y, self.winfo_screenheight() - h - 90))    # 90 ~ barra de tareas + titulo
        tk.Toplevel.wm_geometry(self, f"{w}x{h}+{x}+{y}")       # crudo (sin el escalado de CTk)
        # Sin transient Windows puede dejarlo detras de la principal: se pone encima un momento y se suelta
        # (si se deja 'topmost' fijo, taparia otras aplicaciones)
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.after(400, lambda: self.winfo_exists() and self.attributes("-topmost", False))

    def _ok(self):
        try:
            self.paralelas = max(1, int(self._var_paralelas.get()))
        except (TypeError, ValueError):
            self.paralelas = 3
        self.aceptado = True
        self.destroy()


# ────────────────────────────── Tabla editable de clases
class FilaClase(ctk.CTkFrame):
    def __init__(self, master, num: int, nombre: str,
                 al_cambiar: Callable, al_del: Callable):
        super().__init__(master, fg_color="transparent")
        self._al_del = al_del
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=f"{num}.", font=T.AYD,
                     text_color=T.SUAVE, width=30, anchor="e"
                     ).grid(row=0, column=0, padx=(2, 4))
        self.var = ctk.StringVar(value=nombre)
        self.var.trace_add("write", lambda *_: al_cambiar())
        self._entry = ctk.CTkEntry(self, textvariable=self.var,
                     fg_color=T.SUP, border_color=T.BORDE,
                     height=28, font=T.NRM)
        self._entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self._btn_del = ctk.CTkButton(self, text="x", width=28, height=28, font=T.AYD,
                      fg_color="transparent", hover_color=T.ERR_BG,
                      text_color=T.ERR,
                      command=lambda: al_del(self))
        self._btn_del.grid(row=0, column=2)

    @property
    def nombre(self) -> str:
        return self.var.get().strip()

    def set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self._entry.configure(state=state)
        self._btn_del.configure(state=state)


class TablaClases(ctk.CTkFrame):
    def __init__(self, master, al_cambiar: Callable):
        super().__init__(master, fg_color="transparent")
        self._al_cambiar = al_cambiar
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar
        self.tb = ctk.CTkFrame(self, fg_color="transparent")
        self.tb.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.lbl_n = ctk.CTkLabel(self.tb, text="0 clases", font=T.ETQ,
                                   text_color=T.TEXTO, anchor="w")
        self.lbl_n.pack(side="left")
        
        # Checkbox "Todas las clases"
        self._var_todas = ctk.BooleanVar(value=False)
        self._chk_todas = ctk.CTkCheckBox(
            self.tb, text="TODAS las clases",
            variable=self._var_todas,
            font=T.BTN, text_color=T.PRIM,
            fg_color=T.PRIM, hover_color=T.PRIM_H,
            border_color=T.PRIM, corner_radius=4,
            command=self._toggle_todas)
        self._chk_todas.pack(side="left", padx=(16, 0))
        
        for txt, cmd in [("Descargar plantilla", self._descargar_plantilla),
                          ("Excel", self._excel),
                          ("Pegar lista", self._pegar),
                          ("Limpiar", self._limpiar)]:
            col = T.ERR if txt == "Limpiar" else T.PRIM
            cbg = T.ERR_BG if txt == "Limpiar" else T.FONDO
            ctk.CTkButton(self.tb, text=txt, font=T.AYD, height=28,
                          fg_color=T.SUP, hover_color=cbg,
                          text_color=col, border_width=1, border_color=T.BORDE,
                          corner_radius=6, command=cmd
                          ).pack(side="right", padx=(6, 0))

        # Textbox for classes
        self.caja_texto = ctk.CTkTextbox(
            self, fg_color=T.SUP, text_color=T.TEXTO,
            border_color=T.BORDE, border_width=1, corner_radius=T.R,
            font=T.NRM)
        self.caja_texto.grid(row=1, column=0, sticky="nsew")
        self.caja_texto.bind("<KeyRelease>", self._on_cambio)

    # API publica
    def get_clases(self) -> list:
        # Obtenemos el texto y limpiamos
        texto = self.caja_texto.get("1.0", "end-1c")
        return [c.strip() for c in texto.splitlines() if c.strip()]

    def set_clases(self, clases: list):
        self.caja_texto.configure(state="normal")
        self.caja_texto.delete("1.0", "end")
        if clases:
            self.caja_texto.insert("1.0", "\n".join(clases))
        self._refresh_n()
        self._toggle_todas()

    # Internos
    def _refresh_n(self):
        n = len(self.get_clases())
        self.lbl_n.configure(
            text=f"{n} clase{'s' if n != 1 else ''}")

    def _on_cambio(self, event=None):
        self._refresh_n()
        self._al_cambiar()

    def todas_activadas(self) -> bool:
        return self._var_todas.get()

    def _toggle_todas(self):
        todas = self._var_todas.get()
        state = "disabled" if todas else "normal"
        self.caja_texto.configure(state=state)
        for widget in self.tb.winfo_children():
            if isinstance(widget, ctk.CTkButton):
                widget.configure(state=state)
        self._al_cambiar()

    def _descargar_plantilla(self):
        import shutil
        plantilla_src = RECURSOS / "Plantilla_Clases_Oxford.xlsx"
        if not plantilla_src.exists():
            plantilla_src = RECURSOS / "Plantilla_Clases_Oxford.xlsx"
        if not plantilla_src.exists():
            messagebox.showerror("Error", f"No se encontró la plantilla en:\n{plantilla_src}")
            return
            
        destino = filedialog.asksaveasfilename(
            title="Guardar plantilla como...",
            defaultextension=".xlsx",
            initialfile="Plantilla_Clases_Oxford.xlsx",
            filetypes=[("Excel", "*.xlsx")])
            
        if not destino:
            return
            
        try:
            shutil.copy2(plantilla_src, destino)
            messagebox.showinfo("Éxito", f"Plantilla guardada en:\n{destino}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la plantilla:\n{e}")

    def _pegar(self):
        DlgPegarClases(self, self.get_clases(),
                        al_ok=lambda cls: [self.set_clases(cls),
                                           self._al_cambiar()])

    def _excel(self):
        ruta = filedialog.askopenfilename(
            title="Excel con clases",
            filetypes=[("Excel", "*.xlsx *.xlsm"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            clases = leer_excel_col1(ruta)
        except ImportError:
            messagebox.showerror("Falta openpyxl",
                                  "pip install openpyxl")
            return
        except Exception as e:
            messagebox.showerror("Error Excel", str(e))
            return

        if not clases:
            messagebox.showwarning("Vacio", "No se encontraron clases en el Excel.")
            return
        self.set_clases(clases)
        self._al_cambiar()

    def _limpiar(self):
        if not self.get_clases():
            return
        if messagebox.askyesno("Limpiar", "¿Borrar todas las clases de la lista?"):
            self.set_clases([])
            self._al_cambiar()

class PBase(ctk.CTkFrame):
    def __init__(self, master, titulo: str, desc: str):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        ctk.CTkLabel(hdr, text=titulo, font=T.TIT, text_color=T.PRIM, anchor="w").pack(fill="x")
        ctk.CTkLabel(hdr, text=desc, font=T.AYD, text_color=T.SUAVE, anchor="w").pack(fill="x")
        
        self.cont = ctk.CTkFrame(self, fg_color="transparent")
        self.cont.grid(row=1, column=0, sticky="nsew")
        self.cont.grid_columnconfigure(0, weight=1)

class PanelCred(PBase):
    def __init__(self, master):
        super().__init__(master, "Credenciales Oxford", "Escribe tu correo y tu clave de Oxford.")
        self.var_u = ctk.StringVar()
        self.var_p = ctk.StringVar()
        self.var_l = ctk.StringVar(value="https://englishhub.oup.com")
        
        ctk.CTkLabel(self.cont, text="Correo:", anchor="w", font=T.ETQ, text_color=T.TEXTO).grid(row=0, column=0, sticky="ew", pady=(10,0))
        ctk.CTkEntry(self.cont, textvariable=self.var_u, font=T.NRM, fg_color=T.SUP, text_color=T.TEXTO, border_color=T.BORDE).grid(row=1, column=0, sticky="ew", pady=(4,10))
        
        ctk.CTkLabel(self.cont, text="Clave:", anchor="w", font=T.ETQ, text_color=T.TEXTO).grid(row=2, column=0, sticky="ew", pady=(10,0))
        ctk.CTkEntry(self.cont, textvariable=self.var_p, show="*", font=T.NRM, fg_color=T.SUP, text_color=T.TEXTO, border_color=T.BORDE).grid(row=3, column=0, sticky="ew", pady=(4,10))
        
        ctk.CTkLabel(self.cont, text="Enlace:", anchor="w", font=T.ETQ, text_color=T.TEXTO).grid(row=4, column=0, sticky="ew", pady=(10,0))
        ctk.CTkEntry(self.cont, textvariable=self.var_l, font=T.NRM, fg_color=T.SUP, text_color=T.TEXTO, border_color=T.BORDE).grid(row=5, column=0, sticky="ew", pady=(4,10))
        
    def get(self) -> dict:
        return {"user": self.var_u.get(), "password": self.var_p.get(), "link": self.var_l.get()}
        
    def set(self, d: dict):
        self.var_u.set(d.get("user", ""))
        self.var_p.set(d.get("password", ""))
        self.var_l.set(d.get("link", "https://englishhub.oup.com"))

class PanelOrg(PBase):
    def __init__(self, master, al_cambiar: Callable):
        super().__init__(master, "Organizacion y Clases", "El ID aparece en la columna 'ID' de My Organizations.")
        self.var_id = ctk.StringVar()
        self.var_id.trace_add("write", lambda *_: al_cambiar())
        
        ctk.CTkLabel(self.cont, text="ID de la organizacion (My Organizations)", anchor="w", font=T.ETQ, text_color=T.TEXTO).grid(row=0, column=0, sticky="ew", pady=(10,0))
        ctk.CTkLabel(self.cont, text="Ej: 18xaf (codigo de la columna ID)", anchor="w", font=T.AYD, text_color=T.SUAVE).grid(row=1, column=0, sticky="ew")
        ctk.CTkEntry(self.cont, textvariable=self.var_id, font=T.NRM, fg_color=T.SUP, text_color=T.TEXTO, border_color=T.BORDE).grid(row=2, column=0, sticky="ew", pady=(4,20))
        
        self.tabla = TablaClases(self.cont, al_cambiar=al_cambiar)
        self.tabla.grid(row=3, column=0, sticky="nsew")
        self.cont.grid_rowconfigure(3, weight=1)
        
    def get(self) -> dict:
        return {"id_org": self.var_id.get(), "clases": self.tabla.get_clases()}
        
    def set(self, d: dict):
        self.var_id.set(d.get("id_org", ""))
        self.tabla.set_clases(d.get("clases", []))

class PanelPerfiles(PBase):
    def __init__(self, master, al_cargar: Callable, al_del: Callable, al_nuevo: Callable, al_ejecutar: Callable, al_renombrar: Callable):
        super().__init__(master, "Perfiles de descarga", "Selecciona un perfil o crea uno nuevo.")
        self.al_cargar = al_cargar
        self.al_del = al_del
        self.al_nuevo = al_nuevo
        self.al_ejecutar = al_ejecutar
        self.al_renombrar = al_renombrar
        
        self._perfiles = []
        self._activo = None
        self._cols = 0
        self._job = None
        self.cont.grid_rowconfigure(0, weight=1)
        self.scroll = ctk.CTkScrollableFrame(self.cont, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew")

        ctk.CTkButton(self.cont, text="+ Nuevo perfil", font=T.BTN, height=36, fg_color=T.PRIM, hover_color=T.PRIM_H, text_color=T.SUP, command=self.al_nuevo).grid(row=1, column=0, pady=(10,0), sticky="ew")
        self.cont.bind("<Configure>", self._on_resize)

    # ── Responsive: recalcula columnas segun el ancho disponible
    ANCHO_TARJETA = 380

    def _calc_cols(self) -> int:
        ancho = self.cont.winfo_width()
        return max(1, min(4, ancho // self.ANCHO_TARJETA))

    def _on_resize(self, event=None):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(120, self._relayout)

    def _relayout(self):
        self._job = None
        if self._calc_cols() != self._cols:
            self.actualizar(self._perfiles, self._activo)

    def actualizar(self, perfiles: list, activo: int | None):
        self._perfiles = perfiles
        self._activo = activo
        for w in self.scroll.winfo_children():
            w.destroy()

        cols = self._calc_cols()
        self._cols = cols
        for c in range(4):
            self.scroll.grid_columnconfigure(c, weight=1 if c < cols else 0, uniform="perfil" if c < cols else "")

        if not perfiles:
            ctk.CTkLabel(self.scroll, text="No hay perfiles.\nCrea uno nuevo abajo.", font=T.NRM, text_color=T.SUAVE).grid(row=0, column=0, columnspan=cols, pady=30)

        for idx, p in enumerate(perfiles):
            es_activo = (idx == activo)
            borde_col = T.ACC if es_activo else T.BORDE

            card = ctk.CTkFrame(self.scroll, fg_color=T.SUP, corner_radius=T.R, border_width=2 if es_activo else 1, border_color=borde_col)
            card.grid(row=idx // cols, column=idx % cols, sticky="nsew", padx=6, pady=6)
            card.grid_columnconfigure(1, weight=1)

            ctk.CTkFrame(card, fg_color=T.ACC if es_activo else T.PRIM, width=6, corner_radius=0).grid(row=0, column=0, rowspan=2, sticky="ns")

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.grid(row=0, column=1, sticky="ew", padx=12, pady=(10, 4))
            info.grid_columnconfigure(0, weight=1)

            badge = "  <- Activo" if es_activo else ""
            ctk.CTkLabel(info, text=f"{p['nombre']}{badge}", font=T.SEC, text_color=T.PRIM if es_activo else T.TEXTO, anchor="w").grid(row=0, column=0, sticky="ew")

            nc = len(p.get("clases", []))
            det = f"ID: {p.get('id_org') or '-'}   |   {nc} clase{'s' if nc != 1 else ''}\n{p.get('scores', '-')}"
            ctk.CTkLabel(info, text=det, font=T.AYD, text_color=T.SUAVE, anchor="w", justify="left").grid(row=1, column=0, sticky="ew")

            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.grid(row=1, column=1, sticky="ew", padx=12, pady=(4, 10))
            # Sin uniform: con columnas iguales "Renombrar" no cabia y se cortaba
            btns.grid_columnconfigure((0, 1, 2), weight=1)

            ctk.CTkButton(btns, text="Cargar", font=T.BTN, height=30, width=60, fg_color=T.ACC if es_activo else T.PRIM, hover_color=T.ACC_H if es_activo else T.PRIM_H, text_color="white" if es_activo else "white", corner_radius=T.R, command=lambda i=idx: self.al_cargar(i)).grid(row=0, column=0, sticky="ew", padx=(0, 4))
            ctk.CTkButton(btns, text="Renombrar", font=T.BTN, height=30, width=60, fg_color=T.SUP, hover_color=T.FONDO, text_color=T.TEXTO, border_width=1, border_color=T.BORDE, corner_radius=T.R, command=lambda i=idx: self.al_renombrar(i)).grid(row=0, column=1, sticky="ew", padx=4)
            ctk.CTkButton(btns, text="Eliminar", font=T.BTN, height=30, width=60, fg_color=T.ERR_BG, hover_color=T.ERR_BG_H, text_color=T.ERR, corner_radius=T.R, command=lambda i=idx: self.al_del(i)).grid(row=0, column=2, sticky="ew", padx=(4, 0))

            if es_activo:
                ctk.CTkButton(btns, text="EJECUTAR BOT", font=T.BTNG, height=34, fg_color=T.OK, hover_color="#166534", text_color="white", corner_radius=T.R, command=self.al_ejecutar).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))

class PanelSettings(PBase):
    SCORES  = ["Show best attempt", "Show latest attempt"]
    FIGS    = ["Percentages", "Fractions"]
    SHOW    = ["All activities", "Completed activities"]
    VERSIONES = ["Closing soon", "Upgraded version"]

    def __init__(self, master, al_cambiar: Callable):
        super().__init__(master, "Progress Settings",
                         "Parametros de la ventana Progress settings en cada clase.")
        # Con scroll: en pantallas pequeñas la "Ruta de Descargas" quedaba cortada abajo, sin forma de llegar
        desplazable = ctk.CTkScrollableFrame(self.cont, fg_color="transparent")
        desplazable.grid(row=0, column=0, sticky="nsew")
        desplazable.grid_columnconfigure(0, weight=1)
        self.cont.grid_rowconfigure(0, weight=1)
        card = ctk.CTkFrame(desplazable, fg_color=T.SUP,
                             corner_radius=T.R,
                             border_width=1, border_color=T.BORDE)
        card.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        inner.grid_columnconfigure(0, weight=1)

        # Scores
        ctk.CTkLabel(inner, text="Scores", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="El mejor intento o el ultimo.",
                     font=T.AYD, text_color=T.SUAVE, anchor="w"
                     ).grid(row=1, column=0, sticky="ew")
        self.var_sc = ctk.StringVar(value=self.SCORES[0])
        ctk.CTkOptionMenu(
            inner, values=self.SCORES, variable=self.var_sc,
            fg_color=T.FONDO, button_color=T.PRIM,
            button_hover_color=T.PRIM_H, text_color=T.TEXTO,
            height=36, font=T.NRM,
            command=lambda _: al_cambiar()
        ).grid(row=2, column=0, sticky="w", pady=(4, 18))

        # Show figures as
        ctk.CTkLabel(inner, text="Show figures as", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=3, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="Porcentaje o fraccion.",
                     font=T.AYD, text_color=T.SUAVE, anchor="w"
                     ).grid(row=4, column=0, sticky="ew")
        self.seg_fig = ctk.CTkSegmentedButton(
            inner, values=self.FIGS,
            fg_color=T.FONDO, selected_color=T.PRIM,
            selected_hover_color=T.PRIM_H,
            unselected_color=T.SUP, text_color=T.TEXTO,
            font=T.NRM, command=lambda _: al_cambiar())
        self.seg_fig.set(self.FIGS[0])
        self.seg_fig.grid(row=5, column=0, sticky="w", pady=(4, 18))

        # Show scores for
        ctk.CTkLabel(inner, text="Show scores for", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=6, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="Todas las actividades o solo las completadas.",
                     font=T.AYD, text_color=T.SUAVE, anchor="w"
                     ).grid(row=7, column=0, sticky="ew")
        self.seg_show = ctk.CTkSegmentedButton(
            inner, values=self.SHOW,
            fg_color=T.FONDO, selected_color=T.PRIM,
            selected_hover_color=T.PRIM_H,
            unselected_color=T.SUP, text_color=T.TEXTO,
            font=T.NRM, command=lambda _: al_cambiar())
        self.seg_show.set(self.SHOW[0])
        self.seg_show.grid(row=8, column=0, sticky="w", pady=(4, 18))

        # Version del libro (Oxford puede mostrar dos ediciones del mismo libro)
        ctk.CTkLabel(inner, text="Version del libro", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=9, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="Cual edicion descargar: la que esta por cerrar o la actualizada.",
                     font=T.AYD, text_color=T.SUAVE, anchor="w"
                     ).grid(row=10, column=0, sticky="ew")
        self.seg_ver = ctk.CTkSegmentedButton(
            inner, values=self.VERSIONES,
            fg_color=T.FONDO, selected_color=T.PRIM,
            selected_hover_color=T.PRIM_H,
            unselected_color=T.SUP, text_color=T.TEXTO,
            font=T.NRM, command=lambda _: al_cambiar())
        self.seg_ver.set(self.VERSIONES[0])
        self.seg_ver.grid(row=11, column=0, sticky="w", pady=(4, 18))

        # Ruta Descarga
        ctk.CTkLabel(inner, text="Ruta de Descargas", font=T.ETQ, text_color=T.TEXTO, anchor="w").grid(row=12, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="Carpeta donde se guardaran los Excels descargados.", font=T.AYD, text_color=T.SUAVE, anchor="w").grid(row=13, column=0, sticky="ew")

        box_ruta = ctk.CTkFrame(inner, fg_color="transparent")
        box_ruta.grid(row=14, column=0, sticky="ew", pady=(4, 0))
        box_ruta.grid_columnconfigure(0, weight=1)
        
        self.var_ruta = ctk.StringVar()
        self.var_ruta.trace_add("write", lambda *_: al_cambiar())
        self.ent_ruta = ctk.CTkEntry(box_ruta, textvariable=self.var_ruta, font=T.NRM, fg_color=T.SUP, text_color=T.TEXTO, border_color=T.BORDE)
        self.ent_ruta.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        btn_exam = ctk.CTkButton(box_ruta, text="Examinar", font=T.BTN, fg_color=T.PRIM, hover_color=T.PRIM_H, text_color=T.SUP, width=80, command=self._examinar)
        btn_exam.grid(row=0, column=1)

    def _examinar(self):
        d = filedialog.askdirectory(title="Seleccionar carpeta de descargas")
        if d:
            self.var_ruta.set(d)

    def get(self) -> dict:
        return {
            "scores":          self.var_sc.get(),
            "show_figures_as": self.seg_fig.get(),
            "show_scores_for": self.seg_show.get(),
            "version":         self.seg_ver.get(),
            "ruta_descarga":   self.var_ruta.get(),
        }

    def set(self, d: dict):
        sc = d.get("scores", self.SCORES[0])
        self.var_sc.set(sc if sc in self.SCORES else self.SCORES[0])
        fi = d.get("show_figures_as", self.FIGS[0])
        self.seg_fig.set(fi if fi in self.FIGS else self.FIGS[0])
        sh = d.get("show_scores_for", self.SHOW[0])
        self.seg_show.set(sh if sh in self.SHOW else self.SHOW[0])
        ve = d.get("version", self.VERSIONES[0])
        self.seg_ver.set(ve if ve in self.VERSIONES else self.VERSIONES[0])
        self.var_ruta.set(d.get("ruta_descarga", ""))


# ───────────────────────────────────────────── Usuarios (pruebas Wide Angle)
class PanelUsuarios(PBase):
    """Lee 'Usuarios Oxford.xlsx' (usuario + nivel) y corre las pruebas de Wide Angle con cada uno."""

    COLUMNAS = ("Usuario", "Nivel", "Unidades", "Código org.", "Códigos", "Estado")

    def __init__(self, master, al_ejecutar: Callable):
        super().__init__(master, "Usuarios — pruebas de Wide Angle",
                         "Un Excel con el usuario y el nivel (3, 4 o 5). El bot resuelve las unidades "
                         "del libro de cada usuario.")
        self._al_ejecutar = al_ejecutar
        self.cont.grid_rowconfigure(2, weight=1)

        barra = ctk.CTkFrame(self.cont, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for txt, fn in (("📄 Abrir Excel", self._abrir_excel), ("🔄 Recargar", self.recargar)):
            ctk.CTkButton(barra, text=txt, font=T.BTN, height=34, width=130,
                          fg_color=T.SUP, hover_color=T.FONDO, text_color=T.PRIM,
                          border_width=1, border_color=T.PRIM, corner_radius=T.R,
                          command=fn).pack(side="left", padx=(0, 8))
        self.lbl_resumen = ctk.CTkLabel(barra, text="", font=T.AYD, text_color=T.SUAVE, anchor="e")
        self.lbl_resumen.pack(side="right")

        self.lbl_ruta = ctk.CTkLabel(self.cont, text=f"Archivo: {USUARIOS_XLSX}", font=T.AYD,
                                     text_color=T.SUAVE, anchor="w", wraplength=700, justify="left")
        self.lbl_ruta.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        # Tabla: un solo ttk.Treeview (aguanta miles de filas). Antes eran 6 CTkLabel por usuario y con
        # cientos de usuarios la ventana se congelaba al crearlos/destruirlos.
        marco = ctk.CTkFrame(self.cont, fg_color=T.SUP, border_width=1, border_color=T.BORDE, corner_radius=T.R)
        marco.grid(row=2, column=0, sticky="nsew")
        marco.grid_rowconfigure(0, weight=1)
        marco.grid_columnconfigure(0, weight=1)
        estilo = ttk.Style(self)
        estilo.configure("Usuarios.Treeview", font=T.NRM, rowheight=26, background=T.SUP,
                         fieldbackground=T.SUP, foreground=T.TEXTO, borderwidth=0)
        estilo.configure("Usuarios.Treeview.Heading", font=T.ETQ, foreground=T.PRIM)
        estilo.map("Usuarios.Treeview", background=[("selected", T.PRIM)], foreground=[("selected", "white")])
        self.tabla = ttk.Treeview(marco, columns=self.COLUMNAS, show="headings",
                                  style="Usuarios.Treeview", selectmode="browse")
        for col, ancho, estirar in zip(self.COLUMNAS, (240, 110, 150, 110, 170, 380),
                                       (True, False, False, False, False, True)):
            self.tabla.heading(col, text=col, anchor="w")
            self.tabla.column(col, width=ancho, minwidth=60, stretch=estirar, anchor="w")
        for tag, color in (("ok", T.OK), ("warn", T.WARN), ("err", T.ERR), ("suave", T.SUAVE)):
            self.tabla.tag_configure(tag, foreground=color)
        barra_y = ctk.CTkScrollbar(marco, command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra_y.set)
        self.tabla.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        barra_y.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=6)
        self.tabla.bind("<Double-1>", self._ver_detalle)   # el Estado largo no cabe: doble clic lo muestra

        self.usuarios: list[dict] = []
        self._por_fila: dict[int, dict] = {}       # fila del Excel -> usuario (para actualizar una sola fila)
        self._cargando = False
        self._callbacks: list[Callable] = []        # quienes esperan que termine la carga en curso
        self._repetir = False

        self.btn_ejecutar = ctk.CTkButton(
            self.cont, text="EJECUTAR PRUEBAS WIDE ANGLE", font=T.BTNG, height=40,
            fg_color=T.PRIM, hover_color=T.PRIM_H, text_color="white", corner_radius=T.R,
            command=self._al_ejecutar)
        self.btn_ejecutar.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        # recargar() corre al abrir esta pantalla (VistaOxford._mostrar), no al arrancar la app

    def _abrir_excel(self):
        import os
        if not USUARIOS_XLSX.exists():
            self._crear()
        try:
            completar_columnas_usuarios()   # antes de abrirlo: ya no esta bloqueado por Excel
        except Exception:
            pass
        os.startfile(USUARIOS_XLSX)

    def _crear(self):
        try:
            crear_plantilla_usuarios()
        except Exception as e:
            messagebox.showerror("No se pudo crear el Excel", str(e))

    # Lo pone VistaOxford: escribe los Estados que quedaron pendientes. Corre DENTRO del hilo de carga,
    # así que no debe tocar la interfaz.
    antes_de_recargar: Callable | None = None

    def recargar(self, al_terminar: Callable[[bool], None] | None = None):
        """Relee el Excel en un hilo (la ventana sigue respondiendo) y repinta la tabla.

        al_terminar(ok) se llama en el hilo de Tk cuando self.usuarios ya está al día (ok=False si no se pudo leer).
        Si ya hay una carga en curso, se encadena otra al final en vez de correr dos a la vez.
        """
        if al_terminar:
            self._callbacks.append(al_terminar)
        if self._cargando:
            self._repetir = True
            return
        self._cargando = True
        self._repetir = False
        self.lbl_resumen.configure(text="Cargando usuarios…", text_color=T.SUAVE)
        antes = self.antes_de_recargar

        def trabajo():
            with _LOCK_EXCEL:
                if antes:
                    antes()
                if not USUARIOS_XLSX.exists():
                    crear_plantilla_usuarios()
                return leer_usuarios()

        en_hilo(self, trabajo, self._fin_carga)

    def _fin_carga(self, usuarios, error):
        self._cargando = False
        if self._repetir:                       # alguien pidió recargar mientras leíamos: leer de nuevo
            self.recargar()
            return
        callbacks, self._callbacks = self._callbacks, []
        ok = error is None
        if isinstance(error, PermissionError):
            self.lbl_resumen.configure(text="Cierra el Excel y pulsa Recargar", text_color=T.ERR)
        elif error is not None:
            self.lbl_resumen.configure(text=f"No se pudo leer el Excel: {error}", text_color=T.ERR)
        if ok:
            self._pintar(usuarios)
        else:
            self.usuarios, self._por_fila = [], {}
            self.tabla.delete(*self.tabla.get_children())
        for cb in callbacks:
            cb(ok)

    @staticmethod
    def _estado_y_tag(u: dict) -> tuple[str, str]:
        if u["error"]:
            return f"⚠ {u['error']}", "err"
        if u["estado"]:                         # lo que dice la columna 'Estado' del Excel (ultimo resultado)
            color = color_estado(u["estado"])
            return u["estado"], {T.OK: "ok", T.WARN: "warn", T.ERR: "err"}.get(color, "")
        if not u["usar"]:
            return "Omitido (Usar = No)", "suave"
        return "Listo", ""

    def _valores(self, u: dict) -> tuple:
        estado, _ = self._estado_y_tag(u)
        codigos = ", ".join(n for n, c in (("Online Practice", u["cod_practica"]), ("Ebook", u["cod_ebook"])) if c)
        return (u["usuario"], f"Wide Angle {u['nivel']}" if u["nivel"] else "—",
                u["unidades"], u["codigo"] or "—", codigos or "—", estado)

    pendientes: Callable[[], dict] | None = None   # lo pone VistaOxford: Estados aun no escritos al Excel

    def _pintar(self, usuarios: list[dict]):
        extra = self.pendientes() if self.pendientes else {}
        for u in usuarios:                             # si el Excel estaba abierto, mostrar el Estado mas nuevo
            if u["fila"] in extra:
                u["estado"] = extra[u["fila"]]
        self.usuarios = usuarios
        self._por_fila = {u["fila"]: u for u in usuarios}
        self.tabla.delete(*self.tabla.get_children())
        for u in usuarios:
            _, tag = self._estado_y_tag(u)
            self.tabla.insert("", "end", iid=str(u["fila"]), values=self._valores(u), tags=(tag,) if tag else ())
        self._actualizar_resumen()

    def _actualizar_resumen(self):
        listos = sum(1 for u in self.usuarios if u["usar"] and not u["error"])
        self.lbl_resumen.configure(
            text=f"{listos} usuario(s) listo(s) de {len(self.usuarios)}",
            text_color=T.OK if listos else T.WARN)

    def actualizar_estado(self, fila: int, texto: str):
        """Cambia el Estado de UNA fila en la tabla (sin releer el Excel). Se usa mientras corren las pruebas."""
        u = self._por_fila.get(fila)
        if not u:
            return
        u["estado"] = texto
        iid = str(fila)
        if self.tabla.exists(iid):
            _, tag = self._estado_y_tag(u)
            self.tabla.item(iid, values=self._valores(u), tags=(tag,) if tag else ())

    def _ver_detalle(self, _evento=None):
        sel = self.tabla.selection()
        u = self._por_fila.get(int(sel[0])) if sel else None
        if u:
            estado, _ = self._estado_y_tag(u)
            messagebox.showinfo(u["usuario"], f"Fila {u['fila']} del Excel\n\nEstado:\n{estado}", parent=self)


# ───────────────────────────────────────────── Sidebar
class Sidebar(ctk.CTkFrame):
    SECS = [("H", "Perfiles"), ("C", "Credenciales"),
            ("O", "Organizacion"), ("S", "Settings"), ("U", "Usuarios")]

    def __init__(self, master, al_cambiar: Callable):
        super().__init__(master, fg_color=T.PRIM_OSC, width=72, corner_radius=0)
        self.grid_propagate(False)
        self.grid_rowconfigure(1, weight=1)
        self._al_cambiar = al_cambiar
        self._btns: list[ctk.CTkButton] = []

        # Marca de la herramienta (la estrella del logo + nombre)
        self.logo = logo = ctk.CTkFrame(self, fg_color="transparent")
        logo.grid(row=0, column=0, pady=(14, 8))
        ctk.CTkLabel(logo, text="★", font=(T.F, 24, "bold"),
                     text_color="white").pack()
        ctk.CTkLabel(logo, text="Oxford", font=(T.F, 9, "bold"),
                     text_color=T.SB_TXT).pack()

        self.nav = nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=1, column=0)
        self._etiquetas: list[ctk.CTkLabel] = []
        ICONOS = ["🏠", "🔐", "🏛", "⚙", "👥"]
        for i, (ico, lbl) in enumerate(zip(ICONOS, [s[1] for s in self.SECS])):
            btn = ctk.CTkButton(
                nav, text=ico, width=48, height=48,
                font=(T.F, 20),
                fg_color="transparent", hover_color=T.PRIM,
                text_color="white", corner_radius=10,
                command=lambda idx=i: self._sel(idx))
            btn.pack(pady=3)
            self._btns.append(btn)
            etiqueta = ctk.CTkLabel(nav, text=lbl, font=(T.F, 9), text_color=T.SB_TXT)
            etiqueta.pack(pady=(0, 5))
            self._etiquetas.append(etiqueta)
        self._mark(0)
        # En pantallas bajas los botones de abajo (Usuarios) quedaban cortados: se compacta
        self._compacta = False
        self._alto_normal = 0
        self.bind("<Configure>", self._acomodar, add="+")

    def _acomodar(self, _evento=None):
        if not self._compacta:              # lo que pide en tamaño normal (se mide una sola vez)
            self._alto_normal = max(self._alto_normal,
                                    self.logo.winfo_reqheight() + self.nav.winfo_reqheight() + 30)
        compacta = self.winfo_height() < self._alto_normal
        if compacta == self._compacta or not self._alto_normal:
            return
        self._compacta = compacta
        lado = 38 if compacta else 48
        for btn, etiqueta in zip(self._btns, self._etiquetas):
            btn.configure(width=lado, height=lado, font=(T.F, 16 if compacta else 20))
            btn.pack_configure(pady=1 if compacta else 3)
            etiqueta.pack_configure(pady=(0, 2 if compacta else 5))
        self.logo.grid_configure(pady=(6, 2) if compacta else (14, 8))

    def _sel(self, idx: int):
        self._mark(idx)
        self._al_cambiar(idx)

    def _mark(self, idx: int):
        for i, b in enumerate(self._btns):
            b.configure(fg_color=T.SUP if i == idx else "transparent",
                        text_color=T.PRIM if i == idx else "white")

    def set_active(self, idx: int):
        self._mark(idx)


# ─────────────────────────── Barra inferior
class BarraInf(ctk.CTkFrame):
    def __init__(self, master,
                 al_guardar:   Callable,
                 al_renombrar: Callable):
        super().__init__(master, fg_color=T.SUP, height=62,
                         corner_radius=0,
                         border_width=1, border_color=T.BORDE)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # height=1: sin el, la franja toma el alto por defecto de CTk (200) y estira la fila mas que
        # la barra (62): el perfil y los botones quedaban centrados abajo, fuera de la vista
        ctk.CTkFrame(self, fg_color=T.PRIM, width=6, height=1, corner_radius=0
                     ).grid(row=0, column=0, sticky="ns")

        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew", padx=14)
        self.lbl_p = ctk.CTkLabel(info, text="Sin perfil activo",
                                   font=T.SEC, text_color=T.PRIM, anchor="w")
        self.lbl_p.pack(anchor="w")
        self.lbl_c = ctk.CTkLabel(info, text="Crea o carga un perfil.",
                                   font=T.AYD, text_color=T.SUAVE, anchor="w")
        self.lbl_c.pack(anchor="w")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=0, column=2, padx=12)
        for txt, col, chov, tc, fn, w in [
            ("Renombrar", T.SUP, T.FONDO, T.TEXTO, al_renombrar, 110),
            ("Guardar Config", T.SUP, T.FONDO, T.PRIM, al_guardar, 140),
        ]:
            ctk.CTkButton(btns, text=txt, font=T.BTN, height=36, width=w,
                          fg_color=col, hover_color=chov, text_color=tc,
                          border_width=1, border_color=T.BORDE if tc == T.TEXTO else T.PRIM,
                          corner_radius=T.R, command=fn
                          ).pack(side="left", padx=(0, 6))
        # Sin "Ejecutar" aqui: el bot se lanza desde el boton verde de la tarjeta del perfil activo

    def update(self, nombre: str, n: int):
        self.lbl_p.configure(text=f"Perfil activo: {nombre}")
        self.lbl_c.configure(text=f"{n} clase{'s' if n != 1 else ''}  |  "
                                   f"Guarda antes de ejecutar.")


# ─────────────────────────────────────── Ventana de progreso del bot
class VentanaProgreso(ctk.CTkToplevel):
    """Ventana que muestra el log del bot en tiempo real."""

    MAX_LINEAS_LOG = 5000   # el log visible guarda solo las ultimas N lineas

    def __init__(self, master, perfil: str, n_clases: str, carpeta: Path,
                 titulo: str = "Ejecutando bot Oxford", unidad: str = "clases",
                 info: str | None = None, total: int = 0,
                 texto_carpeta: str = "📂 Abrir descargas",
                 al_resultado: Callable | None = None, al_inicio: Callable | None = None):
        super().__init__(master)
        self.al_inicio = al_inicio              # (usuario) cuando el bot empieza con una cuenta
        self.al_resultado = al_resultado        # (usuario, texto_estado, es_el_ultimo) por cada cuenta que termina
        self.carpeta = carpeta
        self.unidad = unidad
        self.title("Progreso del bot - Oxford English Hub")
        self.geometry("700x480")
        self.minsize(600, 360)
        self.configure(fg_color=T.FONDO)
        self.resizable(True, True)
        import threading
        self._procesos = []                      # procesos en curso (modo paralelo)
        self._procs_lock = threading.Lock()
        self._log_lock = threading.Lock()        # exitosas/fallos los tocan varios hilos lectores
        self._paralelas = 1
        self._codigos = []
        self._corriendo = False

        # Cabecera
        cab = ctk.CTkFrame(self, fg_color=T.PRIM, corner_radius=0)
        cab.pack(fill="x")
        ctk.CTkLabel(cab, text=f"▶  {titulo}",
                     font=T.TIT, text_color="white", anchor="w"
                     ).pack(side="left", padx=16, pady=10)
        self.lbl_info = ctk.CTkLabel(cab,
                     text=info or f"Perfil: {perfil}  |  Clases: {n_clases}",
                     font=T.AYD, text_color=T.SB_TXT, anchor="e")
        self.lbl_info.pack(side="right", padx=16)

        # Avance: barra + contadores (clases terminadas de las que hay en total)
        self.hechos, self.total = 0, total
        self.exitosas = self.fallos = 0
        self._detenido = False
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=(10, 0))
        fila.grid_columnconfigure(0, weight=1)
        self.barra = ctk.CTkProgressBar(fila, mode="indeterminate", height=8,
                                        progress_color=T.PRIM, fg_color=T.BORDE)
        self.barra.grid(row=0, column=0, sticky="ew", padx=(0, 16))
        if total:
            self.barra.configure(mode="determinate")
            self.barra.set(0)
        else:
            self.barra.start()
        self.lbl_cont = ctk.CTkLabel(fila, text=self._texto_contadores(),
                                     font=T.NRM, text_color=T.TEXTO)
        self.lbl_cont.grid(row=0, column=1)

        # Texto de log
        self.txt = ctk.CTkTextbox(
            self, fg_color=T.SUP, border_color=T.BORDE, border_width=1,
            font=("Consolas", 11), wrap="word", corner_radius=T.R)
        self.txt.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        self.txt.configure(state="disabled")

        # Barra inferior
        bar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        bar.pack(fill="x", padx=12, pady=8)
        bar.grid_columnconfigure(0, weight=1)
        self.lbl_estado = ctk.CTkLabel(bar, text="⏳ Iniciando...",
                                        font=T.NRM, text_color=T.SUAVE, anchor="w")
        self.lbl_estado.grid(row=0, column=0, sticky="w")
        self.btn_carpeta = ctk.CTkButton(bar, text=texto_carpeta,
                                          font=T.BTN, height=34,
                                          fg_color=T.SUP, hover_color=T.FONDO,
                                          text_color=T.PRIM, border_width=1,
                                          border_color=T.PRIM, corner_radius=T.R,
                                          command=self._abrir_carpeta)
        self.btn_carpeta.grid(row=0, column=1, padx=(8, 0))
        self.btn_cerrar = ctk.CTkButton(bar, text="Cerrar",
                                         font=T.BTN, height=34, width=100,
                                         fg_color=T.SUP, hover_color=T.FONDO,
                                         text_color=T.TEXTO, border_width=1,
                                         border_color=T.BORDE, corner_radius=T.R,
                                         command=self._cerrar, state="disabled")
        self.btn_cerrar.grid(row=0, column=2, padx=(8, 0))
        self.btn_detener = ctk.CTkButton(bar, text="Detener bot",
                                          font=T.BTN, height=34, width=120,
                                          fg_color=T.ERR, hover_color=T.ERR_H,
                                          text_color="white", corner_radius=T.R,
                                          command=self._detener)
        self.btn_detener.grid(row=0, column=3, padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        # Sin grab_set(): con el modo exclusivo Windows no deja minimizar la ventana, y una prueba
        # puede tardar mucho. Que no se lancen dos bots a la vez lo controla VistaOxford.

    @property
    def corriendo(self) -> bool:
        return self._corriendo

    def mostrar(self):
        """La trae al frente (tambien si estaba minimizada)."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def iniciar(self, cmd: list, cwd: str, env: dict | None = None):
        """Lanza el proceso y empieza a leer stdout."""
        self.iniciar_trabajos([(cmd, env)], cwd)

    def iniciar_trabajos(self, trabajos: list, cwd: str, paralelas: int = 1):
        """Lanza los procesos [(cmd, env)] con hasta `paralelas` a la vez (pool). Para al detener."""
        import threading
        self._corriendo = True
        self._paralelas = max(1, int(paralelas))
        self._codigos = []
        threading.Thread(target=self._despachar, args=(trabajos, cwd), daemon=True).start()

    def _despachar(self, trabajos: list, cwd: str):
        """Mantiene hasta `_paralelas` procesos vivos a la vez; cada uno se lee en su propio hilo."""
        import threading
        libres = threading.Semaphore(self._paralelas)
        hilos = []
        for cmd, env in trabajos:
            if self._detenido:
                break
            libres.acquire()                     # espera a que se libere un cupo del pool
            if self._detenido:
                libres.release()
                break
            h = threading.Thread(target=self._correr_uno, args=(cmd, env, cwd, libres), daemon=True)
            h.start()
            hilos.append(h)
        for h in hilos:
            h.join()
        self._finalizar()

    def _correr_uno(self, cmd: list, env: dict | None, cwd: str, libres):
        import os, subprocess
        try:
            # COLOMBO_INTERFAZ: los bots trabajan en segundo plano (sin ventana del navegador) porque
            # el avance ya se ve aqui, y no esperan un Enter al terminar
            env = {**(env or os.environ), "COLOMBO_INTERFAZ": "1"}
            proceso = subprocess.Popen(
                cmd, cwd=cwd, stdin=subprocess.DEVNULL, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW)
            with self._procs_lock:
                self._procesos.append(proceso)
            if self._detenido:                   # llego la orden de parar entre el cupo y el arranque
                self._matar(proceso)
            for linea in proceso.stdout:
                self._log(linea.rstrip())
            proceso.wait()
            with self._procs_lock:
                self._codigos.append(proceso.returncode)
                if proceso in self._procesos:
                    self._procesos.remove(proceso)
        finally:
            libres.release()

    def _matar(self, proceso):
        """taskkill /T /F cierra todo el arbol (el .exe onefile / python hijo y su navegador)."""
        import subprocess
        try:
            subprocess.run(["taskkill", "/PID", str(proceso.pid), "/T", "/F"],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass

    def _finalizar(self):
        rc = next((c for c in self._codigos if c), 0)
        if self._detenido:
            self._set_estado("⏹ Bot detenido por el usuario.", T.WARN)
        elif rc == 0:
            self._set_estado("✅ Bot finalizado correctamente.", T.OK)
        else:
            self._set_estado(f"⚠️ Bot terminó con código {rc}. Revisa el log.", T.WARN)
        self._corriendo = False

        def _fin():
            self.barra.stop()
            self.barra.configure(mode="determinate")
            self.barra.set(min(self.hechos / self.total, 1) if self.total else 0)
            self.btn_cerrar.configure(state="normal")
            self.btn_detener.configure(state="disabled")
        self.after(0, _fin)

    def _texto_contadores(self) -> str:
        avance = f"{self.hechos} de {self.total} {self.unidad}    " if self.total else ""
        return f"{avance}✔ {self.exitosas} descargada(s)    ✖ {self.fallos} con error"

    def _mostrar_avance(self, hechos: int, total: int):
        self.hechos, self.total = hechos, total
        if total <= 0:
            return
        if self.barra.cget("mode") != "determinate":
            self.barra.stop()
            self.barra.configure(mode="determinate")
        self.barra.set(min(hechos / total, 1))
        self.lbl_cont.configure(text=self._texto_contadores())

    def _log(self, texto: str):
        m = re.match(r"\[\[PROGRESO\]\]\s+(\d+)\s+(\d+)", texto)
        if m:                       # linea interna del bot: alimenta el avance, no se muestra
            self.after(0, lambda: self._mostrar_avance(int(m.group(1)), int(m.group(2))))
            return
        actual = re.search(r"\[\[USUARIO\]\]\s+(\S+)\s+nivel\s+(\d+)", texto)
        if actual:                  # empieza un usuario: se deja a la vista cual es (cabecera + separador en el log)
            usuario, nivel = actual.group(1), actual.group(2)
            if self.al_inicio:
                self.after(0, lambda: self.al_inicio(usuario))
            with self._log_lock:
                numero = self.exitosas + self.fallos + 1
            cabecera = f"Probando {usuario}  ·  {numero} de {self.total}  ·  Wide Angle {nivel}"
            self.after(0, lambda: self.lbl_info.configure(text=cabecera))
            self.after(0, lambda: self.title(f"{numero}/{self.total} {usuario} - Pruebas Wide Angle"))
            texto = f"\n===== Usuario {numero} de {self.total}: {usuario}  (Wide Angle {nivel}) ====="
        prueba = re.search(r"\[\[PRUEBA\]\]\s+(\S+)\s+(OK|FALLO|BLOQUEADO)\s*(.*)", texto)
        tag_forzado = None
        if prueba:                  # una cuenta de la prueba de Wide Angle termino
            resultado = prueba.group(2)
            ok = resultado == "OK"
            usuario, motivo = prueba.group(1), prueba.group(3).strip()
            estado = texto_estado(resultado, motivo)    # el MISMO texto que se anota en el Excel
            with self._log_lock:                 # varios lectores terminan a la vez en modo paralelo
                self.exitosas += ok
                self.fallos += not ok
                terminadas = self.exitosas + self.fallos
            self.after(0, lambda t=terminadas: self._mostrar_avance(t, self.total))
            if self.al_resultado:
                ultimo = terminadas >= self.total
                self.after(0, lambda u=ultimo: self.al_resultado(usuario, estado, u))
            texto = f"{'✔' if ok else '✖'} Usuario {usuario} → Estado: {estado}"
            tag_forzado = "ok" if ok else "err"   # se colorea por el resultado, no por palabras del motivo
        low = texto.lower()
        if low.startswith(("paso 12:", "fallo en la clase")):
            with self._log_lock:
                if low.startswith("paso 12:"):
                    self.exitosas += 1
                else:
                    self.fallos += 1
            self.after(0, lambda: self.lbl_cont.configure(text=self._texto_contadores()))

        def _do():
            self.txt.configure(state="normal")
            # Colorear errores y exitos
            tag = None
            t_lower = texto.lower()
            if tag_forzado:
                tag = tag_forzado
                self.txt.tag_config(tag, foreground=T.OK if tag == "ok" else T.ERR)
                self.lbl_estado.configure(text=texto[:90], text_color=T.OK if tag == "ok" else T.ERR)
            elif "fallo" in t_lower or "error" in t_lower or "exception" in t_lower:
                tag = "err"
                self.txt.tag_config("err", foreground=T.ERR)
                self.lbl_estado.configure(
                    text=f"⚠️ {texto[:80]}", text_color=T.WARN)
            elif "paso" in t_lower or "guardado" in t_lower or "csv" in t_lower:
                tag = "ok"
                self.txt.tag_config("ok", foreground=T.OK)
                self.lbl_estado.configure(
                    text=f"✔ {texto[:80]}", text_color=T.OK)
            self.txt.insert("end", texto + "\n", tag or "")
            # Tope del log: en corridas largas (cientos de usuarios) el texto crece sin fin y Tk se vuelve
            # lento. Se dejan las ultimas lineas (el resultado de cada usuario queda en el 'Estado' del Excel).
            lineas = int(self.txt.index("end-1c").split(".")[0])
            if lineas > self.MAX_LINEAS_LOG:
                self.txt.delete("1.0", f"{lineas - self.MAX_LINEAS_LOG + 1}.0")
            self.txt.see("end")
            self.txt.configure(state="disabled")
        self.after(0, _do)

    def _set_estado(self, msg: str, color: str):
        self.after(0, lambda: self.lbl_estado.configure(
            text=msg, text_color=color))

    def _detener(self):
        if self._corriendo and not self._detenido:
            self._detenido = True              # corta el despachador y evita relanzar mas procesos
            with self._procs_lock:
                procesos = list(self._procesos)
            for proceso in procesos:           # mata TODO lo que este corriendo en el pool
                self._matar(proceso)
            self._log(">>> Bot detenido por el usuario.")
            self.btn_detener.configure(state="disabled")

    def _abrir_carpeta(self):
        """Abre la carpeta donde el bot guarda los CSV (o la de arriba si aun no existe)."""
        import os
        carpeta = self.carpeta
        while not carpeta.exists() and carpeta != carpeta.parent:
            carpeta = carpeta.parent
        os.startfile(carpeta)

    def _cerrar(self):
        if self._corriendo:
            if not messagebox.askyesno(
                    "Bot activo",
                    "El bot todavia está corriendo.\n¿Deseas detenerlo y cerrar?",
                    parent=self):
                return
            self._detener()
        self.destroy()


# ─────────────────────────────────────── App principal
class VistaOxford(ctk.CTkFrame):
    """Configurador de Oxford English Hub como vista embebible en la app unificada."""
    TITULO = "Oxford English Hub"
    SUBTITULO = "Configurador de descargas"

    def __init__(self, master):
        super().__init__(master, fg_color=T.FONDO, corner_radius=0)
        try:
            self.tk.call("encoding", "system", "utf-8")
        except Exception:
            pass

        self._perfiles: list = cargar_perfiles()
        self._activo:   int | None = 0 if self._perfiles else None
        self._ventana_bot: VentanaProgreso | None = None     # la del bot que este corriendo

        # 1. Barra inferior (siempre visible en el fondo, ocupa todo el ancho)
        self.barra = BarraInf(self,
                               al_guardar=self._guardar,
                               al_renombrar=self._renombrar)
        self.barra.pack(side="bottom", fill="x")

        # 2. Contenedor principal para el resto (Sidebar + Paneles)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(side="top", fill="both", expand=True)

        # 3. Sidebar (izquierda)
        self.sb = Sidebar(self.main_container, al_cambiar=self._cambiar)
        self.sb.pack(side="left", fill="y")

        # 4. Area de paneles (derecha, toma el resto del espacio)
        self.area = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.area.pack(side="right", fill="both", expand=True, padx=16, pady=12)
        self.area.grid_columnconfigure(0, weight=1)
        self.area.grid_rowconfigure(0, weight=1)

        self.pp = PanelPerfiles(self.area,
                                 al_cargar=self._cargar,
                                 al_del=self._del_perfil,
                                 al_nuevo=self._nuevo,
                                 al_ejecutar=self._ejecutar,
                                 al_renombrar=self._renombrar)
        self.pc = PanelCred(self.area)
        self.po = PanelOrg(self.area, al_cambiar=self._on_edit)
        self.ps = PanelSettings(self.area, al_cambiar=self._on_edit)

        self._estados_pendientes: dict[int, str] = {}
        self.pu = PanelUsuarios(self.area, al_ejecutar=self._ejecutar_pruebas)
        self._id_volcado = None                  # after() programado para escribir los Estados acumulados
        self.pu.antes_de_recargar = self._volcar_pendientes   # corre en el hilo de carga (sin interfaz)
        self.pu.pendientes = lambda: dict(self._estados_pendientes)
        self._panels = [self.pp, self.pc, self.po, self.ps, self.pu]
        for p in self._panels:
            p.grid(row=0, column=0, sticky="nsew")

        self._mostrar(0)
        if self._activo is not None:
            self._cargar(self._activo)

    # ── Integracion con la app unificada
    def hay_proceso_activo(self) -> bool:
        v = self._ventana_bot
        return bool(v is not None and v.winfo_exists() and v.corriendo)

    def cerrar(self) -> None:
        if self.hay_proceso_activo():
            self._ventana_bot._detener()       # la app ya pregunto si detenerlo antes de salir
        if self._estados_pendientes:           # no perder los Estados que aun no se escribieron al Excel
            self._volcar_pendientes()

    def _bot_en_curso(self) -> bool:
        """Si ya hay un bot corriendo, trae su ventana al frente y avisa (no se lanzan dos a la vez)."""
        if not self.hay_proceso_activo():
            return False
        self._ventana_bot.mostrar()
        messagebox.showinfo("Bot en curso",
                            "Ya hay un bot de Oxford trabajando. Espera a que termine o detenlo "
                            "desde su ventana de progreso.", parent=self._ventana_bot)
        return True

    # ── Navegacion
    def _cambiar(self, idx: int):
        self._mostrar(idx)

    def _mostrar(self, idx: int):
        self._panels[idx].tkraise()
        if idx == 0:
            self.pp.actualizar(self._perfiles, self._activo)
        elif self._panels[idx] is self.pu:
            self.pu.recargar()          # el Excel pudo cambiar mientras estaba en otra pantalla

    # ── Pruebas de Wide Angle (menu Usuarios)
    def _volcar_pendientes(self) -> str:
        """Escribe en el Excel los Estados acumulados. No toca la interfaz (puede correr en un hilo).

        Devuelve "" si quedo todo escrito (o no habia nada), "abierto" si el Excel esta abierto, u otro texto de error.
        Los que no se pudieron escribir siguen en _estados_pendientes para el siguiente intento.
        """
        with _LOCK_EXCEL:
            lote = dict(self._estados_pendientes)
            if not lote:
                return ""
            try:
                escribir_estados_usuarios(lote)
            except PermissionError:
                return "abierto"
            except Exception as e:
                return str(e) or e.__class__.__name__
            for fila, texto in lote.items():       # quitar solo lo escrito (pudo llegar uno nuevo mientras tanto)
                if self._estados_pendientes.get(fila) == texto:
                    del self._estados_pendientes[fila]
            return ""

    def _anotar_estados(self, estados: dict[int, str]) -> bool:
        """Anota YA en la columna 'Estado' del Excel (una sola escritura). Si esta abierto lo deja pendiente."""
        self._estados_pendientes.update(estados)
        error = self._volcar_pendientes()
        if error and error != "abierto":
            messagebox.showerror("No se pudo anotar el Estado", error)
        return not error

    def _encolar_estado(self, fila: int, texto: str):
        """Durante las pruebas: acumula el Estado y lo escribe al Excel por lotes (cada INTERVALO_VOLCADO_MS)."""
        self._estados_pendientes[fila] = texto
        if self._id_volcado is None:
            self._id_volcado = self.after(INTERVALO_VOLCADO_MS, self._volcar_en_hilo)

    def _volcar_en_hilo(self, al_terminar: Callable[[str], None] | None = None):
        """Escribe los Estados acumulados en un hilo; al_terminar(error) en el hilo de Tk."""
        if self._id_volcado is not None:
            self.after_cancel(self._id_volcado)
            self._id_volcado = None

        def fin(error, excepcion):
            error = error or (str(excepcion) if excepcion else "")
            if error and self._estados_pendientes and self.hay_proceso_activo() and self._id_volcado is None:
                self._id_volcado = self.after(INTERVALO_VOLCADO_MS, self._volcar_en_hilo)   # reintentar luego
            if al_terminar:
                al_terminar(error)
        en_hilo(self, self._volcar_pendientes, fin)

    def _ejecutar_pruebas(self):
        if self._bot_en_curso() or getattr(self, "_preparando", False):
            return
        self._preparando = True                 # evita doble clic mientras se lee el Excel
        self.pu.btn_ejecutar.configure(state="disabled")

        def listo(ok: bool):
            try:
                if ok:                          # incluye el dialogo de confirmacion (no se abren dos)
                    self._ejecutar_pruebas_cargado()
            finally:
                self._preparando = False
                self.pu.btn_ejecutar.configure(state="normal")
        self.pu.recargar(al_terminar=listo)

    def _ejecutar_pruebas_cargado(self):
        """Segunda parte de Ejecutar: self.pu.usuarios ya esta recien leido del Excel."""
        self._estados_pendientes = {}
        ahora = datetime.now().strftime("%d/%m %H:%M")
        con_error = {u["fila"]: f"ERROR {ahora}: {u['error']}" for u in self.pu.usuarios
                     if u["usar"] and u["error"]}
        if con_error and not self._anotar_estados(con_error):
            messagebox.showwarning(
                "Excel abierto",
                "Hay usuarios con error en el Excel pero está abierto y no pude anotar su 'Estado'.\n"
                "Ciérralo y pulsa Ejecutar de nuevo para dejar el registro.")
            return
        for fila, texto in con_error.items():   # ya quedo escrito en el Excel: solo reflejarlo en la tabla
            self.pu.actualizar_estado(fila, texto)
        listos =[u for u in self.pu.usuarios if u["usar"] and not u["error"]]
        if not listos:
            messagebox.showinfo("Sin usuarios",
                                "No hay usuarios listos: revisa el Excel (Usar, Nivel y contraseña).")
            return
        es_exe = getattr(sys, "frozen", False)
        if es_exe and not PRUEBAS_EXE.exists():
            messagebox.showerror("Bot no encontrado",
                                 f"No se encontro '{PRUEBAS_EXE.name}' junto a la aplicacion:\n{ROOT}")
            return
        if not es_exe and not PRUEBAS_SCRIPT.exists():
            messagebox.showerror("Bot no encontrado", f"No se encontro:\n{PRUEBAS_SCRIPT}")
            return
        cred = leer_txt(CREDENCIALES_TXT)
        link = cred.get("link") or "https://englishhub.oup.com"

        # Un grupo por combinacion (nivel, unidades): el nivel se lee al importar y no cambia dentro de un
        # proceso. Se junta a TODOS los de la misma combinacion aunque esten mezclados en el Excel (si no, un
        # Excel con niveles intercalados daba cientos de grupos = cientos de arranques del bot/navegador).
        # Los grupos van en el orden en que aparece su primera fila, y dentro de cada grupo se respeta el
        # orden del Excel.
        por_combinacion: dict = {}                  # (nivel, unidades) -> [usuarios], en orden de fila
        for u in listos:
            por_combinacion.setdefault((u["nivel"], u["unidades"]), []).append(u)
        grupos: list = [(nivel, unidades, us) for (nivel, unidades), us in por_combinacion.items()]
        confirmar = DlgConfirmarPruebas(self, grupos)
        self.wait_window(confirmar)
        if not confirmar.aceptado:
            return

        paralelas = confirmar.paralelas
        import os, tempfile
        carpeta_tmp = Path(tempfile.mkdtemp(prefix="oxford_cuentas_"))
        py = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
        # Cada grupo (nivel+unidades) se parte en hasta `paralelas` subprocesos para que corran a la
        # vez; cada subproceso reusa su navegador entre las cuentas que le tocan. El tope REAL de
        # concurrencia lo impone la ventana de progreso (pool), aunque haya mas subprocesos.
        trabajos = []
        t = 0
        for nivel, unidades, usuarios in grupos:
            n_lotes = min(paralelas, len(usuarios))
            lotes = [usuarios[j::n_lotes] for j in range(n_lotes)]       # reparto redondo (equilibra)
            for lote in lotes:
                archivo = carpeta_tmp / f"cuentas_{t}.json"
                t += 1
                archivo.write_text(json.dumps(
                    [{"user": u["usuario"], "password": u["clave"], "link": link, "codigo": u["codigo"],
                      "codigo_practica": u["cod_practica"], "codigo_ebook": u["cod_ebook"]}
                     for u in lote], ensure_ascii=False), encoding="utf-8")
                env = {**os.environ, "OXFORD_NIVEL": str(nivel), "OXFORD_UNIDADES": unidades,
                       "OXFORD_CUENTAS": str(archivo), "OXFORD_RAIZ": str(ROOT),
                       "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
                cmd = [str(PRUEBAS_EXE)] if es_exe else [py, str(PRUEBAS_SCRIPT)]
                trabajos.append((cmd, env))
        filas = {u["usuario"]: u["fila"] for u in reversed(listos)}      # usuario -> fila del Excel

        def al_inicio(usuario: str):
            fila = filas.get(usuario)
            if fila:
                texto = f"EJECUTANDO {datetime.now().strftime('%d/%m %H:%M')}..."
                self._encolar_estado(fila, texto)
                self.pu.actualizar_estado(fila, texto)

        def al_resultado(usuario: str, estado: str, ultimo: bool):
            # Solo se actualiza esa fila de la tabla (instantaneo) y el Estado se acumula: el Excel se
            # escribe por lotes cada INTERVALO_VOLCADO_MS en un hilo, y una ultima vez al terminar.
            fila = filas.get(usuario)
            if fila:
                self._encolar_estado(fila, estado)
                self.pu.actualizar_estado(fila, estado)
            if ultimo:
                self._volcar_en_hilo(al_terminar=avisar_si_falta)

        def avisar_si_falta(error: str):
            if not self._estados_pendientes:
                return
            padre = ven if ven.winfo_exists() else self
            if error == "abierto":
                messagebox.showwarning(
                    "Excel abierto",
                    "No pude anotar el 'Estado' de algunos usuarios porque el Excel está abierto.\n"
                    "Ciérralo y pulsa Recargar en Usuarios para guardarlos.", parent=padre)
            else:
                messagebox.showerror("No se pudo anotar el Estado", error, parent=padre)
        try:
            ven = VentanaProgreso(self, "", "", ROOT / "Capturas",
                                  titulo="Pruebas Wide Angle", unidad="usuarios",
                                  info=f"{len(listos)} usuario(s)  |  {len(grupos)} grupo(s)",
                                  total=len(listos), texto_carpeta="📂 Abrir capturas",
                                  al_resultado=al_resultado, al_inicio=al_inicio)
            ven.iniciar_trabajos(trabajos, str(ROOT), paralelas=paralelas)
            self._ventana_bot = ven
        except Exception as e:
            messagebox.showerror("Error al ejecutar", str(e))

    # ── Perfiles
    def _cargar(self, idx: int):
        self._activo = idx
        p = self._perfiles[idx]
        self._cargando = True
        try:
            self.pc.set(p)
            self.po.set(p)
            self.ps.set(p)
        finally:
            self._cargando = False
        self._upd_barra()
        self.pp.actualizar(self._perfiles, idx)

    def _nuevo(self):
        DlgNuevoPerfil(self, al_ok=self._crear_perfil)

    def _crear_perfil(self, nombre: str, id_org: str):
        n = dict(PERFIL_VACIO)
        n["clases"] = []
        n["nombre"] = nombre
        n["id_org"] = id_org
        if self._activo is not None:
            src = self._perfiles[self._activo]
            n["user"]     = src.get("user", "")
            n["password"] = src.get("password", "")
            n["link"]     = src.get("link", "https://englishhub.oup.com")
        self._perfiles.append(n)
        guardar_perfiles(self._perfiles)
        self.pp.actualizar(self._perfiles, self._activo)

    def _del_perfil(self, idx: int):
        nombre = self._perfiles[idx]["nombre"]
        if not messagebox.askyesno("Eliminar",
                                    f"Eliminar perfil '{nombre}'?"):
            return
        self._perfiles.pop(idx)
        guardar_perfiles(self._perfiles)
        if self._activo == idx:
            self._activo = 0 if self._perfiles else None
        elif self._activo is not None and self._activo > idx:
            self._activo -= 1
        if self._activo is not None and self._perfiles:
            self._cargar(self._activo)
        self.pp.actualizar(self._perfiles, self._activo)

    def _renombrar(self, idx: int):
        DlgNombre(self, self._perfiles[idx]["nombre"],
                   al_ok=lambda n: self._on_rename(idx, n))

    def _on_rename(self, idx: int, nombre: str):
        self._perfiles[idx]["nombre"] = nombre
        if self._activo == idx:
            self._sync_mem()
            self._upd_barra()
        guardar_perfiles(self._perfiles)
        self.pp.actualizar(self._perfiles, self._activo)

    # ── Datos
    def _on_edit(self):
        if getattr(self, "_cargando", False):
            return
        if self._activo is not None:
            self._sync_mem()
            self._upd_barra()

    def _sync_mem(self):
        if self._activo is None:
            return
        p = self._perfiles[self._activo]
        p.update(self.pc.get())
        p.update(self.po.get())
        p.update(self.ps.get())

    def _upd_barra(self):
        if self._activo is None:
            return
        p = self._perfiles[self._activo]
        self.barra.update(p.get("nombre", "-"), len(p.get("clases", [])))

    # ── Guardar / Ejecutar
    def _guardar(self):
        if self._activo is None:
            messagebox.showinfo("Sin perfil", "Crea o carga un perfil.")
            return
        self._sync_mem()
        p = self._perfiles[self._activo]
        if not p.get("user"):
            messagebox.showwarning("Falta correo",
                                    "Ve a Credenciales y escribe el correo.")
            return
        if not p.get("id_org"):
            messagebox.showwarning("Falta ID",
                                    "Ve a Organizacion y escribe el ID.")
            return
        todas = self.po.tabla.todas_activadas()
        if not todas and not p.get("clases"):
            messagebox.showwarning("Sin clases",
                "Agrega al menos una clase o activa 'TODAS las clases'.")
            return
        try:
            escribir_credenciales(p["user"], p["password"], p["link"])
            clases_guardar = p["clases"] if not todas else ["__TODAS__"]
            escribir_config(p["id_org"], clases_guardar, p["scores"], p["show_figures_as"], p["show_scores_for"], p.get("ruta_descarga", ""), p.get("version", "Closing soon"))
            guardar_perfiles(self._perfiles)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        n_txt = "TODAS las clases" if todas else f"{len(p['clases'])} clases"
        messagebox.showinfo(
            "Guardado",
            f"Escritos:\n  {CREDENCIALES_TXT.name}\n  {CONFIG_TXT.name}\n"
            f"  perfiles_oxford.json\n\n"
            f"Perfil: {p['nombre']}  |  {n_txt}")

    def _ejecutar(self):
        if self._bot_en_curso():
            return
        if self._activo is None:
            messagebox.showinfo("Sin perfil", "Crea o carga un perfil.")
            return
        # Verificar modo TODAS antes de guardar (para no bloquear)
        todas = self.po.tabla.todas_activadas()
        self._guardar()
        # Si _guardar fallo (campos vacios), los perfiles no cambiaron; checar
        p = self._perfiles[self._activo] if self._activo is not None else {}
        if not p.get("user") or not p.get("id_org"):
            return
        if not todas and not p.get("clases"):
            return  # _guardar ya mostro el mensaje
        es_exe = getattr(sys, "frozen", False)
        if es_exe and not BOT_EXE.exists():
            messagebox.showerror("Bot no encontrado",
                                 f"No se encontro '{BOT_EXE.name}' junto a la aplicacion:\n{ROOT}")
            return
        if not es_exe and not BOT_SCRIPT.exists():
            messagebox.showerror(
                "Bot no encontrado",
                f"No se encontro:\n{BOT_SCRIPT}\n\n"
                "Asegurate de que \'automatizar_oxford.py\' este en:\n"
                f"{ROOT}")
            return
        py = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
        n_clases = "TODAS" if todas else str(len(p["clases"]))
        nombre_p = p["nombre"]
        id_org_p = p["id_org"]
        det = (f"Perfil: {nombre_p}\n"
               f"ID org: {id_org_p}\n"
               f"Version: {p.get('version', 'Closing soon')}\n"
               f"Clases: {n_clases}")
        if not messagebox.askyesno("Ejecutar bot?",
                                    f"{det}\n\n"
                                    "Se abrira una ventana con el progreso en tiempo real."):
            return
        try:
            cmd = [str(BOT_EXE)] if es_exe else [py, str(BOT_SCRIPT)]
            if todas:
                cmd.append("--todas")
            ruta = (p.get("ruta_descarga") or "").strip()
            ven = VentanaProgreso(self, p["nombre"], n_clases,
                                  Path(ruta) if ruta else ROOT / "Descargas")
            ven.iniciar(cmd, str(ROOT))
            self._ventana_bot = ven
        except Exception as e:
            messagebox.showerror("Error al ejecutar", str(e))


if __name__ == "__main__":
    if "--bot" in sys.argv:
        # Modo bot: el propio .exe ejecuta la automatizacion (sin interfaz)
        sys.argv.remove("--bot")
        import automatizar_oxford
        try:
            automatizar_oxford.main()
        except (EOFError, RuntimeError):
            pass   # input() final sin consola: es esperado
        except Exception as e:
            print(f"FALLO: {automatizar_oxford.resumen(e)}")
        sys.exit(0)
    raiz = ctk.CTk()
    raiz.title("Oxford English Hub - Configurador de Descargas")
    raiz.geometry("1024x680")
    raiz.minsize(720, 520)
    VistaOxford(raiz).pack(fill="both", expand=True)
    raiz.mainloop()
