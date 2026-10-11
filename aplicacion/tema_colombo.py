"""Identidad visual del Centro Colombo Americano, compartida por Q10, Macmillan y Oxford.

Fuente de los valores: presentacion corporativa (Template1.pptx).
  - Azul del logo   #004994   - Rojo del logo  #D2081D   (muestreados del logo oficial)
  - Texto           #0E2841   (color "oscuro 2" del tema de la plantilla)
  - Tipografia      Aptos (fuente del tema de la plantilla); si el equipo no la tiene
                    instalada se usa Segoe UI, que viene con Windows.
Cualquier cambio de marca se hace SOLO aqui.
"""
from __future__ import annotations

import sys
from pathlib import Path

RECURSOS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "recursos"
if not RECURSOS.exists():                      # ejecutable PyInstaller con recursos al lado
    RECURSOS = Path(__file__).parent / "recursos"

LOGO = RECURSOS / "logo_colombo.png"
FONDO_ESTRELLAS = RECURSOS / "fondo_estrellas.png"
ALIADOS = RECURSOS / "aliados.png"


class Marca:
    # Colores de marca
    AZUL = "#004994"
    AZUL_H = "#003A78"          # hover / pulsado (azul mas oscuro)
    AZUL_OSC = "#00305F"        # barras laterales, cabeceras
    AZUL_CLARO = "#E6EEF7"      # fondos suaves, selecciones
    ROJO = "#D2081D"
    ROJO_H = "#A80617"
    ROJO_CLARO = "#FBE7E9"
    BLANCO = "#FFFFFF"

    # Neutros (derivados del azul de la plantilla)
    TEXTO = "#0E2841"
    TEXTO_SUAVE = "#5A6F82"
    FONDO = "#F3F6F9"
    BORDE = "#D3DCE5"
    BORDE_FUERTE = "#B7C4D1"
    DESHABILITADO = "#9AA9B8"

    # Estados (el verde y el ambar no son de marca: se conservan por su significado)
    OK = "#15803D"
    OK_FONDO = "#DCFCE7"
    AVISO = "#B45309"
    AVISO_FONDO = "#FEF3C7"
    ERROR = ROJO
    ERROR_FONDO = ROJO_CLARO

    RADIO = 8


def fuente() -> str:
    """Aptos si esta instalada; si no, Segoe UI. Se mira en las carpetas de fuentes de Windows
    (no en Tk) para poder llamarla al importar, antes de que exista la ventana."""
    import os
    carpetas = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"]
    for c in carpetas:
        try:
            if c.is_dir() and any(c.glob("Aptos*.tt[fc]")):
                return "Aptos"
        except OSError:
            pass
    return "Segoe UI"


def tipografia(familia: str | None = None) -> dict:
    f = familia or fuente()
    return {
        "F": f,
        "H1": (f, 22, "bold"), "H2": (f, 16, "bold"), "SECCION": (f, 13, "bold"),
        "SUBTITULO": (f, 12), "ETIQUETA": (f, 12, "bold"), "NORMAL": (f, 12),
        "AYUDA": (f, 10), "MINI": (f, 9), "BOTON": (f, 12, "bold"), "BOTON_G": (f, 13, "bold"),
    }
