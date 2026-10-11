"""La plantilla de Excel para subir un listado de cursos al filtro 'Curso' (ControlVarios,
boton "Subir listado (Excel)" en configurar_q10.py).

Una sola columna a proposito: es lo que el lector de configurar_q10.py entiende (primera
columna de la hoja activa, encabezado opcional). Nada que el usuario tenga que interpretar,
y nada ambiguo que Python tenga que adivinar.
"""
from pathlib import Path

NOMBRE_ARCHIVO = "Plantilla cursos.xlsx"
ENCABEZADO = "Curso"

# Mismos colores del resto de la app (formulario/configurar_q10.py::Tema), repetidos aqui
# para no tener que importar todo customtkinter solo por esta plantilla.
PRIMARIO = "005697"
FONDO_AYUDA = "DDEBF7"
GRIS = "595959"


def crear(ruta: Path | str) -> Path:
    """Crea la plantilla en 'ruta' (la sobreescribe si ya existia) y la devuelve."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.table import Table, TableStyleInfo

    ruta = Path(ruta)
    libro = Workbook()
    ws = libro.active
    ws.title = "Cursos"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 40

    ws["A1"] = "Listado de cursos"
    ws["A1"].font = Font(size=16, bold=True, color=PRIMARIO)

    ws.merge_cells("A2:C2")
    ws["A2"] = ('Un curso por fila, en la columna "Curso", tal como aparece en Q10. '
               "Para usarlo: en Configurar Q10, en el filtro Curso, dale clic a "
               '"Subir listado (Excel)" y escoge este archivo. '
               "Ejemplo de como se ve un curso: B2G-A1")
    ws["A2"].font = Font(size=9, italic=True, color=GRIS)
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["A2"].fill = PatternFill("solid", fgColor=FONDO_AYUDA)
    ws.row_dimensions[2].height = 45

    FILA_TABLA = 4
    ws.cell(row=FILA_TABLA, column=1, value=ENCABEZADO)
    # La tabla arranca vacia (sin cursos de ejemplo a proposito): un curso de "ejemplo" que
    # alguien olvide borrar terminaria subiendose como si fuera real.
    celda_vacia = ws.cell(row=FILA_TABLA + 1, column=1)
    celda_vacia.number_format = "@"     # texto: que Excel no intente adivinar un tipo de dato

    tabla = Table(displayName="Cursos", ref=f"A{FILA_TABLA}:A{FILA_TABLA + 1}")
    tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tabla)

    ws.freeze_panes = f"A{FILA_TABLA + 1}"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    libro.save(ruta)
    return ruta


if __name__ == "__main__":
    import sys
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "datos" / NOMBRE_ARCHIVO
    print(f"Creada: {crear(destino)}")
