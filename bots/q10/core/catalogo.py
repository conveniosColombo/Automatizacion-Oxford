"""Catalogo de informes de Q10 parametrizados a mano con 'Informe nuevo'.

Se usa cuando el bot no puede leer un informe solo (permisos, o informes que solo muestran el
resultado en pantalla). El usuario arma una vez el nombre, la direccion y los filtros (en orden,
con sus dependencias), y queda guardado en 'catalogo_q10.json', junto a la planilla, para no
tener que repetirlo despues.

Este catalogo lo usa el formulario "Configurar Q10" (formulario/configurar_q10.py). Todavia no
lo lee el bot: el bot sigue leyendo unicamente 'Bot Descargas.xlsx', que es lo que el formulario
escribe al darle a "Guardar configuracion".
"""
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core import archivos

NOMBRE_ARCHIVO = "catalogo_q10.json"
RUTA = archivos.DATOS / NOMBRE_ARCHIVO

TIPOS = ("lista", "segmentado", "varios")


@dataclass
class FiltroDef:
    """Un filtro del informe, tal como se ve en la pantalla de Q10, en orden."""
    nombre: str
    tipo: str                                   # una clave de TIPOS
    obligatorio: bool = True
    ayuda: str = ""
    opciones: list[str] = field(default_factory=list)          # si no depende de otro filtro
    depende_de: str | None = None               # nombre de un filtro ANTERIOR en la lista
    opciones_por: dict[str, list[str]] = field(default_factory=dict)  # si depende de otro


@dataclass
class InformeDef:
    """Un informe de Q10 y sus filtros, en el orden en que se llenan en la pantalla."""
    nombre: str
    categoria: str = "Informes personalizados"
    direccion: str = ""
    filtros: list[FiltroDef] = field(default_factory=list)
    formatos: list[str] = field(default_factory=lambda: ["XLSX"])
    activo: bool = True                          # False: solo aparece en la lista, sin filtros


def _informe_de_ejemplo() -> InformeDef:
    """El informe de muestra: Sede -> Jornada -> Programa -> Periodo -> Curso."""
    return InformeDef(
        nombre="Inasistencias por curso", categoria="Gestión Académica",
        direccion="InasistenciasJustificacion",
        filtros=[
            FiltroDef("Sede", "lista", ayuda="La sede donde se dicta el curso.",
                      opciones=["Centro", "Norte", "Kennedy"]),
            FiltroDef("Jornada", "segmentado", ayuda="Jornada disponible en esa sede.",
                      depende_de="Sede", opciones_por={
                          "Centro": ["Mañana", "Tarde", "Noche"],
                          "Norte": ["Mañana", "Tarde"],
                          "Kennedy": ["Tarde", "Noche"]}),
            FiltroDef("Programa", "lista", ayuda="Programa activo en esa jornada.",
                      depende_de="Jornada", opciones_por={
                          "Mañana": ["Inglés Adultos - B2G", "Inglés Adultos - B2B"],
                          "Tarde": ["Inglés Kids", "Inglés Adultos - B2G"],
                          "Noche": ["Inglés Adultos - B2B"]}),
            FiltroDef("Período", "lista", ayuda="Periodo académico del programa.",
                      depende_de="Programa", opciones_por={
                          "Inglés Adultos - B2G": ["2026-8", "2026-7"],
                          "Inglés Adultos - B2B": ["2026-8", "2026-6"],
                          "Inglés Kids": ["2026-8"]}),
            FiltroDef("Curso", "varios",
                      ayuda='Seleccione "Todos" o cursos específicos. Genera un reporte por curso.',
                      depende_de="Período", opciones_por={
                          "2026-8": ["B2G-A1", "B2G-A2", "B2G-B1", "B2G-B2", "B2G-B3"],
                          "2026-7": ["B2G-A1", "B2G-A2"],
                          "2026-6": ["B2B-01", "B2B-02"]}),
        ],
    )


def _catalogo_de_ejemplo() -> list[InformeDef]:
    return [_informe_de_ejemplo()]


def _informe_desde_dict(datos: dict) -> InformeDef:
    filtros = [FiltroDef(**f) for f in datos.get("filtros", [])]
    return InformeDef(
        nombre=datos["nombre"], categoria=datos.get("categoria", "Informes personalizados"),
        direccion=datos.get("direccion", ""), filtros=filtros,
        formatos=datos.get("formatos") or ["XLSX"], activo=datos.get("activo", True))


def cargar() -> list[InformeDef]:
    """Los informes guardados. Si todavia no hay catalogo, lo crea con el informe de ejemplo."""
    if not RUTA.exists():
        informes = _catalogo_de_ejemplo()
        guardar(informes)
        return informes
    try:
        datos = json.loads(RUTA.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise ValueError(f"No pude leer '{RUTA.name}': {error}") from error
    return [_informe_desde_dict(d) for d in datos.get("informes", [])]


def guardar(informes: list[InformeDef]) -> Path:
    RUTA.parent.mkdir(parents=True, exist_ok=True)
    datos = {"informes": [asdict(informe) for informe in informes]}
    RUTA.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return RUTA


def guardar_informe(informes: list[InformeDef], nuevo: InformeDef,
                    nombre_anterior: str | None = None) -> list[InformeDef]:
    """Agrega o actualiza 'nuevo' en la lista, y guarda.

    'nombre_anterior' es el nombre que tenia ANTES de editarlo (por si se le cambio el nombre
    al informe): sin esto, editar y renombrar dejaria dos copias (la vieja y la nueva) en vez
    de reemplazar la original. Sin 'nombre_anterior' (informe nuevo, o edicion sin renombrar),
    simplemente reemplaza cualquier informe que ya tuviera ese mismo nombre.
    """
    quitar = {nuevo.nombre.strip().lower()}
    if nombre_anterior:
        quitar.add(nombre_anterior.strip().lower())
    resultado = [i for i in informes if i.nombre.strip().lower() not in quitar]
    resultado.append(nuevo)
    guardar(resultado)
    return resultado
