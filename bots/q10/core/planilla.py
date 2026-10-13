"""La planilla de Excel 'Bot Descargas.xlsx': reemplaza a los Config y Credenciales .txt de la v3.

Una sola definicion (HOJAS) sirve para las dos cosas:
  - crear la planilla con sus tablas, listas desplegables y ayudas (crear()), y
  - leerla y devolver el mismo diccionario que devolvia leer_txt() (leer_hoja()), asi las clases
    de configuracion de cada sistema no cambian.

Cada hoja de sistema tiene tablas de Excel una al lado de la otra (cada una en sus columnas, para
que al agregar filas no se pisen):
  Ajustes  ->  un valor por fila (Ajuste | Valor | Que escribo)
  Listas   ->  un elemento por fila (Clases, Informes, Libros...), con "Usar" Si/No y una nota
  Filtros  ->  pares nombre/valor en orden (solo Q10)
"Usar = No" reemplaza al "#" de los .txt: la fila se queda escrita pero el bot la salta.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

NOMBRE = "Bot Descargas.xlsx"
SI_NO = ("Sí", "No")

# Colores de la planilla
AZUL = "1F4E79"
AZUL_CLARO = "DDEBF7"
GRIS = "595959"
AMARILLO = "FFF2CC"


@dataclass
class Campo:
    """Un ajuste de un solo valor."""
    clave: str                  # la clave que entienden las clases de config (como en el .txt)
    etiqueta: str               # lo que ve el usuario en la columna "Ajuste"
    ayuda: str
    opciones: tuple = ()        # lista desplegable
    valor: str = ""             # valor de ejemplo en la plantilla
    estricto: bool = True       # False: la lista sugiere, pero se puede escribir otra cosa


@dataclass
class Lista:
    """Una columna de elementos, uno por fila. Se entrega como texto separado por comas."""
    clave: str
    titulo: str                 # encabezado de la columna (una palabra: tambien nombra la tabla)
    grupo: str                  # como se llama el grupo en la ayuda (CLASES, NIVELES...)
    ayuda: str
    valores: tuple = ()         # ejemplos: (valor, usar, nota)


@dataclass
class Pares:
    """Tabla informe/nombre -> valor en orden (los filtros de Q10).

    La columna 'Informe' dice a cual informe aplica esa fila; vacia = aplica a TODOS los
    informes de la hoja. Asi una configuracion de un solo grupo de filtros (como siempre se
    uso) sigue funcionando igual: basta con dejar esa columna en blanco.
    """
    titulo_nombre: str
    titulo_valor: str
    ayuda: str
    filas: tuple = ()           # ejemplos: (informe, nombre, valor, usar, nota)


@dataclass
class Hoja:
    nombre: str
    titulo: str
    explicacion: str
    campos: list = field(default_factory=list)
    listas: list = field(default_factory=list)
    pares: Pares | None = None


HOJAS = {
    "Oxford": Hoja(
        "Oxford", "Oxford English Hub",
        "Qué organización abrir, qué clases descargar y cómo configurar 'Progress settings'.",
        campos=[
            Campo("id", "ID de la organización",
                  "La columna 'ID' de 'My Organizations'. Respeta mayúsculas y minúsculas. "
                  "Ej: f9nfc = Cohorte 1 AM SDDE 2026", valor="18xaf"),
            Campo("scores", "Scores", "Progress settings > Scores",
                  ("Show best attempt", "Show latest attempt"), "Show best attempt", estricto=False),
            Campo("show figures as", "Show figures as", "Progress settings > Show figures as",
                  ("Percentages", "Fractions"), "Percentages"),
            Campo("show scores for", "Show scores for", "Progress settings > Show scores for",
                  ("All activities", "Completed activities"), "All activities"),
        ],
        listas=[Lista("clases", "Clase", "CLASES",
                      "Una clase por fila, tal como aparece en la lista 'Classes'. "
                      "Para saltar una sin borrarla, pon 'No' en Usar.",
                      (("B1.1-5PM87 SDDE_2026-2", "Sí", ""),))],
    ),
    "Q10": Hoja(
        "Q10", "Q10",
        "Qué informes descargar y con qué filtros. Cada fila de 'Informes' se descarga con TODOS "
        "los filtros de la tabla 'Filtros'.",
        campos=[
            Campo("rol", "Rol",
                  "La opción de la ventana 'Seleccione el rol' que sale después de la contraseña.",
                  ("Administrativo",), "Administrativo", estricto=False),
            Campo("formato", "Formato",
                  "Formato para exportar desde el visor. Los informes que bajan Excel directo lo ignoran.",
                  ("XLSX", "XLS", "PDF", "CSV", "DOC", "HTML", "IMAGEN"), "XLSX"),
            Campo("menu", "Menú",
                  "Por dónde entra el bot. Déjalo en 'Informes' para descargar informes. "
                  "Los otros menús solo sirven con 'Submenú'.",
                  ("Informes", "Académico", "Institucional", "Tesorería"), "Informes"),
            Campo("submenu", "Submenú",
                  "Solo si Menú NO es Informes. Los niveles se separan con '>'. "
                  "Ej: Educación virtual v2 > Cursos virtuales"),
            Campo("buscar", "Buscar",
                  "Solo para pantallas con buscador (Cursos virtuales). Vacío = la lista completa."),
            Campo("accion", "Acción",
                  "Vacío = guardar la tabla en CSV. 'Usuarios' = bajar los usuarios de cada curso.",
                  ("Usuarios",)),
        ],
        listas=[Lista("informes", "Informe", "INFORMES",
                      "Uno por fila: el nombre tal cual sale en la página Informes, "
                      "'Nombre (Sección)' si se repite, o su dirección (ListadoCursos), que es lo más seguro.",
                      (("Inasistencias por curso", "Sí", ""),
                       ("ListadoCursos", "No", "Visor: exporta en el Formato de arriba")))],
        pares=Pares(
            "Filtro", "Valor",
            "En el MISMO orden de la pantalla (cada lista carga según la anterior). "
            "Informe: vacío = aplica a TODOS los informes de arriba; con un nombre, solo a ese. "
            "Filtro = el nombre como sale en Q10, sin el *. "
            "Valor: COMA = un reporte por cada valor. 'Todos' = uno por cada opción. "
            "PUNTO Y COMA = varias opciones en el MISMO reporte. "
            "Fechas: 01/09/2026 - 30/09/2026 o Hoy, Este mes... Interruptores: Sí / No.",
            (("", "Sede - jornada", "B2B - Única", "Sí", ""),
             ("", "Programa", "Todos", "Sí", ""),
             ("", "Período", "Todos", "Sí", "Un reporte por cada período"),
             ("", "Incluir archivados", "No", "No", "Ejemplo de interruptor"),
             ("", "Campos", "Documento; Nombre; Correo", "No", "Ejemplo: varias opciones en un reporte"))),
    ),
    "Macmillan": Hoja(
        "Macmillan", "Macmillan Education Everywhere (MEE)",
        "Qué libros, niveles y clases recorrer.",
        campos=[
            Campo("recurso", "Recurso",
                  "La opción del nivel a la que entra el bot.",
                  ("Macmillan Education Everywhere App", "Teacher's Resource Centre",
                   "Test Generator", "ePlanner"), "Macmillan Education Everywhere App", estricto=False),
        ],
        listas=[
            Lista("libros", "Libro", "LIBROS", "Uno por fila, tal como aparece debajo de la portada en 'Mi Estantería'.",
                  (("Speak Your Mind", "Sí", ""),)),
            Lista("niveles", "Nivel", "NIVELES",
                  "Las pestañas del libro (Level 1, Level 2...). 'Todos' = todas. "
                  "Vacío si el libro no tiene niveles.",
                  (("Level 1", "Sí", ""),)),
            Lista("clases", "Clase", "CLASES",
                  "Como se ven en cada tarjeta de Progress. 'Todas' = todas las que aparezcan.",
                  (("Todas", "Sí", ""),)),
        ],
    ),
}

ACCESOS = "Accesos"
COLUMNAS_ACCESOS = ("Sistema", "Usar", "Usuario", "Contraseña", "Link de ingreso")


# ------------------------------------------------------------------------------ leer ---
def normalizar(texto):
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[*?:¿]", "", sin_tildes).lower().split())


def texto(valor):
    """Lo que hay en una celda, como texto. Excel convierte solo fechas y numeros: se deshace."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def se_usa(valor):
    """'Usar' vacio cuenta como Si: asi una fila recien escrita funciona sin tocar esa columna."""
    return normalizar(texto(valor)) not in ("no", "n", "0", "false")


def _columna(encabezados, fila, nombre_columna, por_defecto=""):
    """El valor de esa columna EN ESA FILA, buscando el encabezado por nombre (no por posicion).

    Asi una planilla vieja que no tenga una columna nueva (como 'Informe') no se desalinea:
    simplemente no la encuentra y devuelve el valor por defecto.
    """
    buscado = normalizar(nombre_columna)
    for indice, encabezado in enumerate(encabezados):
        if normalizar(encabezado) == buscado:
            return fila[indice] if indice < len(fila) else por_defecto
    return por_defecto


class Planilla:
    """La planilla abierta (solo lectura)."""

    def __init__(self, ruta):
        from openpyxl import load_workbook

        if not ruta.exists():
            raise FileNotFoundError(f"No encontre '{ruta.name}' en {ruta.parent}")
        try:
            self.libro = load_workbook(ruta, data_only=True)
        except PermissionError:
            raise PermissionError(f"No pude abrir '{ruta.name}'. Si esta abierto en Excel, "
                                  "guardalo y cierralo, y vuelve a intentar.")
        self.ruta = ruta

    def tablas(self, hoja):
        """{nombre de la tabla: {"encabezados": [...], "filas": [...]}}, sin filas vacias.

        Se lee hasta el final de la hoja, no solo hasta donde dice la tabla: si alguien escribe
        justo debajo y Excel no la agrando, la fila igual cuenta. Se devuelven los encabezados
        para que quien lea busque cada columna POR NOMBRE, no por posicion: asi una columna
        nueva (como 'Informe') no desalinea una planilla que no la tiene.
        """
        from openpyxl.utils import range_boundaries

        if hoja not in self.libro.sheetnames:
            raise ValueError(f"Falta la hoja '{hoja}' en {self.ruta.name}")
        ws = self.libro[hoja]
        resultado = {}
        for nombre, tabla in ws.tables.items():
            primera_col, fila_titulos, ultima_col, _ = range_boundaries(
                tabla.ref if hasattr(tabla, "ref") else tabla)
            encabezados = [texto(v) for v in next(ws.iter_rows(
                min_row=fila_titulos, max_row=fila_titulos,
                min_col=primera_col, max_col=ultima_col, values_only=True))]
            filas = []
            for fila in ws.iter_rows(min_row=fila_titulos + 1, max_row=ws.max_row,
                                     min_col=primera_col, max_col=ultima_col, values_only=True):
                celdas = [texto(v) for v in fila]
                if any(celdas):
                    filas.append(celdas)
            resultado[nombre] = {"encabezados": encabezados, "filas": filas}
        return resultado

    def leer_hoja(self, sistema):
        """Devuelve {clave: valor} como leer_txt(): claves en minuscula y listas separadas por coma.

        Ademas, si la hoja tiene tabla de filtros (Q10), agrega "_pares": la lista cruda
        (informe, nombre, valor) de cada fila en uso, para que quien la necesite pueda
        agrupar los filtros propios de cada informe (vease sistemas/q10/config.py).
        """
        definicion = HOJAS[sistema]
        tablas = self.tablas(definicion.nombre)
        datos = {}
        VACIA = {"encabezados": [], "filas": []}

        por_etiqueta = {normalizar(c.etiqueta): c.clave for c in definicion.campos}
        tabla_ajustes = tablas.get(f"{sistema}_Ajustes", VACIA)
        for fila in tabla_ajustes["filas"]:
            ajuste = _columna(tabla_ajustes["encabezados"], fila, "Ajuste")
            clave = por_etiqueta.get(normalizar(ajuste))
            if clave:
                datos[clave] = _columna(tabla_ajustes["encabezados"], fila, "Valor")

        for lista in definicion.listas:
            tabla_lista = tablas.get(f"{sistema}_{lista.titulo}", VACIA)
            elementos = []
            for fila in tabla_lista["filas"]:
                valor = _columna(tabla_lista["encabezados"], fila, lista.titulo)
                usar = _columna(tabla_lista["encabezados"], fila, "Usar")
                if valor and se_usa(usar):
                    elementos.append(valor)
            datos[lista.clave] = ", ".join(elementos)

        if definicion.pares:
            p = definicion.pares
            tabla_pares = tablas.get(f"{sistema}_Filtros", VACIA)
            crudas = []
            for fila in tabla_pares["filas"]:
                informe = _columna(tabla_pares["encabezados"], fila, "Informe").strip()
                nombre = _columna(tabla_pares["encabezados"], fila, p.titulo_nombre).strip()
                valor = _columna(tabla_pares["encabezados"], fila, p.titulo_valor)
                usar = _columna(tabla_pares["encabezados"], fila, "Usar")
                if nombre and valor and se_usa(usar):
                    crudas.append((informe, nombre, valor))
                    if not informe:            # sin informe = aplica a todos (como siempre)
                        datos[nombre.lower()] = valor
            datos["_pares"] = crudas
        return datos

    def accesos(self):
        """{sistema en minuscula: {'usar', 'user', 'password', 'link'}} de la hoja Accesos."""
        resultado = {}
        tabla = self.tablas(ACCESOS).get(ACCESOS, {"encabezados": [], "filas": []})
        for fila in tabla["filas"]:
            sistema = _columna(tabla["encabezados"], fila, "Sistema").strip()
            if sistema:
                resultado[sistema.lower()] = {
                    "usar": se_usa(_columna(tabla["encabezados"], fila, "Usar")),
                    "user": _columna(tabla["encabezados"], fila, "Usuario"),
                    "password": _columna(tabla["encabezados"], fila, "Contraseña"),
                    "link": _columna(tabla["encabezados"], fila, "Link de ingreso")}
        return resultado


# ----------------------------------------------------------------------------- crear ---
def crear(ruta, valores=None):
    """Crea la planilla. 'valores' permite llenarla (por ejemplo con lo que habia en los .txt):

        {"Accesos": [(sistema, usar, usuario, clave, link)],
         "Oxford": {"campos": {clave: valor}, "listas": {clave: [(valor, usar, nota)]},
                    "pares": [(nombre, valor, usar, nota)]}}
    Lo que no venga en 'valores' se llena con los ejemplos de HOJAS.
    """
    from openpyxl import Workbook

    valores = valores or {}
    libro = Workbook()
    _hoja_inicio(libro.active)
    _hoja_accesos(libro.create_sheet(ACCESOS), valores.get(ACCESOS))
    for definicion in HOJAS.values():
        _hoja_sistema(libro.create_sheet(definicion.nombre), definicion,
                      valores.get(definicion.nombre, {}))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    libro.save(ruta)
    return ruta


def actualizar_hoja_sistema(ruta, sistema, valores):
    """Reescribe SOLO la hoja de 'sistema' en una planilla que ya existe; el resto no se toca.

    La usa el formulario "Configurar Q10" para guardar lo que arma el usuario (informes y
    filtros) sin borrar Accesos ni las otras hojas. Si la planilla no existe todavia, la crea.
    """
    from openpyxl import Workbook, load_workbook

    if ruta.exists():
        try:
            libro = load_workbook(ruta)
        except PermissionError:
            raise PermissionError(f"No pude abrir '{ruta.name}'. Si esta abierto en Excel, "
                                  "guardalo y cierralo, y vuelve a intentar.")
    else:
        libro = Workbook()
        _hoja_inicio(libro.active)
        _hoja_accesos(libro.create_sheet(ACCESOS), None)
        for otro in HOJAS.values():
            if otro.nombre != sistema:
                _hoja_sistema(libro.create_sheet(otro.nombre), otro, {})

    if sistema in libro.sheetnames:
        indice = libro.sheetnames.index(sistema)
        del libro[sistema]
        ws = libro.create_sheet(sistema, indice)
    else:
        ws = libro.create_sheet(sistema)
    _hoja_sistema(ws, HOJAS[sistema], valores)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    libro.save(ruta)
    return ruta


def campos_actuales(ruta, sistema):
    """Los Ajustes que ya tenia guardados esa hoja (Rol, Menu...), para no perderlos al
    actualizar solo Informes/Filtros. {} si la planilla o la hoja todavia no existen."""
    if not ruta.exists():
        return {}
    try:
        return Planilla(ruta).leer_hoja(sistema)
    except Exception:
        return {}


def acceso_de(ruta, sistema):
    """{'user', 'password', 'link'} guardados en la hoja Accesos para ese sistema; {} si no hay."""
    if not ruta.exists():
        return {}
    try:
        return Planilla(ruta).accesos().get(sistema.lower(), {})
    except Exception:
        return {}


def guardar_acceso(ruta, sistema, usuario, clave, link):
    """Escribe Usuario, Contrasena y Link de ese sistema en la hoja Accesos, sin tocar lo demas.

    La usa el formulario "Configurar Q10" para que nadie tenga que abrir el Excel a mano.
    Si la planilla no existe, la crea; si el sistema no tiene fila, la agrega.
    """
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    from openpyxl.utils.cell import range_boundaries

    if not ruta.exists():
        crear(ruta)
    try:
        libro = load_workbook(ruta)
    except PermissionError:
        raise PermissionError(f"No pude abrir '{ruta.name}'. Si esta abierto en Excel, "
                              "guardalo y cierralo, y vuelve a intentar.")
    if ACCESOS not in libro.sheetnames:
        _hoja_accesos(libro.create_sheet(ACCESOS, 1), None)
    ws = libro[ACCESOS]

    # Los encabezados estan en la fila 5; se buscan por nombre, no por posicion
    columnas = {normalizar(ws.cell(row=5, column=c).value): c
                for c in range(1, ws.max_column + 1) if ws.cell(row=5, column=c).value}
    c_sistema, c_usar, c_usuario, c_clave, c_link = (columnas[normalizar(n)] for n in COLUMNAS_ACCESOS)

    fila = next((f for f in range(6, ws.max_row + 1)
                 if normalizar(texto(ws.cell(row=f, column=c_sistema).value)) == normalizar(sistema)), None)
    if fila is None:
        fila = next((f for f in range(6, ws.max_row + 2)
                     if not texto(ws.cell(row=f, column=c_sistema).value)), ws.max_row + 1)
        ws.cell(row=fila, column=c_sistema, value=sistema)
        tabla = ws.tables.get(ACCESOS)
        if tabla:                                   # que la fila nueva quede dentro de la tabla
            c1, f1, c2, f2 = range_boundaries(tabla.ref)
            tabla.ref = f"{get_column_letter(c1)}{f1}:{get_column_letter(c2)}{max(f2, fila)}"

    if not texto(ws.cell(row=fila, column=c_usar).value):
        ws.cell(row=fila, column=c_usar, value="Sí")
    for columna, valor in ((c_usuario, usuario), (c_clave, clave), (c_link, link)):
        celda = ws.cell(row=fila, column=columna, value=valor or None)
        celda.number_format = "@"                   # texto: que Excel no cambie nada
    libro.save(ruta)
    return ruta


def _estilos():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    return {
        "titulo": Font(size=18, bold=True, color=AZUL),
        "subtitulo": Font(size=11, color=GRIS),
        "seccion": Font(size=13, bold=True, color=AZUL),
        "ayuda": Font(size=9, italic=True, color=GRIS),
        "normal": Font(size=11),
        "envolver": Alignment(wrap_text=True, vertical="top"),
        "medio": Alignment(vertical="center", wrap_text=True),
        "fondo_ayuda": PatternFill("solid", fgColor=AZUL_CLARO),
        "fondo_valor": PatternFill("solid", fgColor=AMARILLO),
        "borde": Border(bottom=Side(style="thin", color="BFBFBF")),
    }


def _tabla(ws, nombre, primera_col, fila, encabezados, filas, anchos, estilo="TableStyleMedium2"):
    """Escribe una tabla de Excel con encabezados y filas. Devuelve el rango de datos (col, desde, hasta)."""
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo

    for desplazamiento, (titulo, ancho) in enumerate(zip(encabezados, anchos)):
        col = primera_col + desplazamiento
        ws.cell(row=fila, column=col, value=titulo)
        ws.column_dimensions[get_column_letter(col)].width = ancho
    # Una tabla necesita al menos una fila de datos; se dejan varias vacias para escribir
    filas = list(filas) or [[""] * len(encabezados)]
    for n, datos in enumerate(filas, start=1):
        for desplazamiento, valor in enumerate(datos):
            celda = ws.cell(row=fila + n, column=primera_col + desplazamiento, value=valor or None)
            celda.number_format = "@"      # texto: que Excel no cambie fechas, ceros ni numeros
            celda.alignment = Alignment(vertical="center", wrap_text=True)
    ultima = fila + max(len(filas), 1)
    ref = (f"{get_column_letter(primera_col)}{fila}:"
           f"{get_column_letter(primera_col + len(encabezados) - 1)}{ultima}")
    tabla = Table(displayName=nombre, ref=ref)
    tabla.tableStyleInfo = TableStyleInfo(name=estilo, showRowStripes=True)
    ws.add_table(tabla)
    return ultima


def _desplegable(ws, rango, opciones, estricto=True):
    """Lista desplegable en un rango. estricto=False solo sugiere: se puede escribir otra cosa."""
    from openpyxl.worksheet.datavalidation import DataValidation

    validacion = DataValidation(type="list", formula1='"' + ",".join(opciones) + '"',
                                allow_blank=True, showErrorMessage=estricto)
    if estricto:
        validacion.error = "Escoge una opción de la lista."
        validacion.errorTitle = "Valor no válido"
    ws.add_data_validation(validacion)
    validacion.add(rango)
    return validacion


def _ayuda(ws, fila, primera_col, ultima_col, contenido, e):
    from openpyxl.utils import get_column_letter

    ws.merge_cells(f"{get_column_letter(primera_col)}{fila}:{get_column_letter(ultima_col)}{fila}")
    celda = ws.cell(row=fila, column=primera_col, value=contenido)
    celda.font, celda.alignment, celda.fill = e["ayuda"], e["envolver"], e["fondo_ayuda"]


def _encabezado(ws, titulo, explicacion, e):
    ws["A1"], ws["A2"] = titulo, explicacion
    ws["A1"].font, ws["A2"].font = e["titulo"], e["subtitulo"]
    ws.row_dimensions[1].height = 30
    ws.sheet_view.showGridLines = False


def _hoja_sistema(ws, definicion, valores):
    from openpyxl.utils import get_column_letter

    e = _estilos()
    ws.title = definicion.nombre
    _encabezado(ws, definicion.titulo, definicion.explicacion, e)
    FILA_AYUDA, FILA_TABLA = 4, 5
    ws.row_dimensions[FILA_AYUDA].height = 70

    # Ajustes (columnas A-C)
    campos = valores.get("campos", {})
    filas = [(c.etiqueta, campos.get(c.clave, c.valor), c.ayuda) for c in definicion.campos]
    ultima = _tabla(ws, f"{definicion.nombre}_Ajustes", 1, FILA_TABLA,
                    ("Ajuste", "Valor", "¿Qué escribo?"), filas, (24, 34, 60))
    _ayuda(ws, FILA_AYUDA, 1, 3, "AJUSTES: escribe solo en la columna amarilla 'Valor'. "
           "Donde aparece una flechita, escoge de la lista.", e)
    for n, campo in enumerate(definicion.campos, start=FILA_TABLA + 1):
        ws.cell(row=n, column=1).font = e["normal"]
        ws.cell(row=n, column=2).fill = e["fondo_valor"]
        ws.cell(row=n, column=3).font = e["ayuda"]
        for col in (1, 2, 3):
            ws.cell(row=n, column=col).alignment = e["medio"]
        ws.row_dimensions[n].height = 32
        if campo.opciones:
            _desplegable(ws, f"B{n}", campo.opciones, campo.estricto)

    col = 5
    listas = valores.get("listas", {})
    for lista in definicion.listas:
        filas = listas.get(lista.clave, lista.valores)
        _tabla(ws, f"{definicion.nombre}_{lista.titulo}", col, FILA_TABLA,
               (lista.titulo, "Usar", "Nota"), filas, (36, 8, 30), "TableStyleMedium9")
        _ayuda(ws, FILA_AYUDA, col, col + 2, f"{lista.grupo}: {lista.ayuda}", e)
        letra = get_column_letter(col + 1)
        _desplegable(ws, f"{letra}{FILA_TABLA + 1}:{letra}{FILA_TABLA + 400}", SI_NO)
        col += 4

    if definicion.pares:
        p = definicion.pares
        filas = valores.get("pares", p.filas)
        _tabla(ws, f"{definicion.nombre}_Filtros", col, FILA_TABLA,
               ("Informe", p.titulo_nombre, p.titulo_valor, "Usar", "Nota"), filas, (20, 26, 34, 8, 32),
               "TableStyleMedium7")
        _ayuda(ws, FILA_AYUDA, col, col + 4, f"FILTROS: {p.ayuda}", e)
        letra = get_column_letter(col + 3)
        _desplegable(ws, f"{letra}{FILA_TABLA + 1}:{letra}{FILA_TABLA + 400}", SI_NO)

    ws.freeze_panes = f"A{FILA_TABLA + 1}"


def _hoja_accesos(ws, filas):
    e = _estilos()
    ws.title = ACCESOS
    _encabezado(ws, "Accesos", "Tus usuarios y contraseñas. No compartas este archivo con nadie.", e)
    ws.row_dimensions[4].height = 45
    if filas is None:
        filas = [(nombre, "Sí", "", "", "") for nombre in HOJAS]
    _tabla(ws, ACCESOS, 1, 5, COLUMNAS_ACCESOS, filas, (14, 8, 34, 26, 48))
    _ayuda(ws, 4, 1, 5, "Llena Usuario y Contraseña de cada sistema que uses. "
           "'Usar = No' quita ese sistema del menú del bot.", e)
    _desplegable(ws, "B6:B20", SI_NO)
    for fila in range(6, 6 + len(filas)):
        ws.cell(row=fila, column=3).fill = e["fondo_valor"]
        ws.cell(row=fila, column=4).fill = e["fondo_valor"]
    ws.freeze_panes = "A6"


def _hoja_inicio(ws):
    e = _estilos()
    ws.title = "Inicio"
    _encabezado(ws, "Bot Descargas", "Aquí se configura todo lo que hace el bot. No hay que tocar ningún .txt.", e)
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 110
    bloques = [
        ("PRIMERA VEZ", [
            "1. Hoja 'Accesos': escribe tu usuario y tu contraseña en cada sistema que uses.",
            "2. Si no usas un sistema, pon 'No' en la columna 'Usar' y no aparecerá en el menú.",
            "3. Revisa la hoja de cada sistema (Oxford, Q10, Macmillan).",
            "4. Guarda (Ctrl + G) y CIERRA el Excel antes de correr el bot.",
        ]),
        ("CÓMO SE LLENA", [
            "• Solo se escribe en las celdas de las tablas. Los títulos y las ayudas no se tocan.",
            "• Celdas amarillas = valores que tú escribes. Si la celda tiene una flechita, escoge de la lista.",
            "• Para agregar una fila (otra clase, otro informe...), escribe justo debajo de la última: la tabla crece sola.",
            "• Para saltar una fila sin borrarla, pon 'No' en la columna 'Usar'. Si 'Usar' queda vacío, cuenta como Sí.",
            "• Escribe los nombres tal como salen en la pantalla del sistema. Mayúsculas y tildes dan igual en Q10.",
        ]),
        ("Q10 - FILTROS", [
            "• Van en el mismo orden de la pantalla: cada lista carga sus opciones según la anterior.",
            "• COMA = un reporte por cada valor.  Ej: B2B - Única, B2G - Única  → 2 reportes.",
            "• Todos = un reporte por cada opción de la lista (o la opción 'Todos' si la lista la trae).",
            "• PUNTO Y COMA = varias opciones en el MISMO reporte.  Ej: Documento; Nombre; Correo",
            "• Fechas: 01/09/2026 - 30/09/2026, o Hoy, Este mes, Últimos 7 días, Todas.",
            "• Interruptores: Sí / No.   Personas (docente, asesor): escribe el nombre y el bot lo busca.",
            "• Si un filtro no existe en ese informe, el bot lo salta: se pueden dejar filtros de otros informes.",
        ]),
        ("CADA VEZ QUE LO USES", [
            "1. Doble clic en el bot. 2. Escribe el número del sistema y Enter. 3. No toques el navegador mientras trabaja.",
            "Los archivos quedan en la carpeta 'Descargas' y, si algo falla, las imágenes en 'Capturas'.",
        ]),
    ]
    fila = 4
    for titulo, lineas in bloques:
        ws.cell(row=fila, column=2, value=titulo).font = e["seccion"]
        fila += 1
        for linea in lineas:
            celda = ws.cell(row=fila, column=2, value=linea)
            celda.font, celda.alignment = e["normal"], e["envolver"]
            fila += 1
        fila += 1
