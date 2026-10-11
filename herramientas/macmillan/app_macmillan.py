"""
app_macmillan.py  -  Macmillan Education Everywhere - Configurador de Descargas
Centro Colombo Americano - Bogota

Interfaz por "Perfiles de descarga" (misma arquitectura que app_oxford.py)
para orquestar el bot Python + Playwright que extrae los reportes de
mee (School work > Progress).

- Perfiles guardados en  perfiles_macmillan.json  (junto a este archivo).
- Al ejecutar se escribe  config_macmillan_activo.json  para que el bot lo lea.
- Si existe  automatizar_macmillan.py  en la misma carpeta se ejecuta el bot
  real en un subproceso; si no, se corre una SIMULACION en un hilo.

Solo usa: Python 3.13, customtkinter, tkinter estandar, json, threading,
subprocess.
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

# La identidad visual vive en app_colombo/tema_colombo.py (compartida con Q10 y Oxford)
_APP_COLOMBO = Path(__file__).resolve().parents[2] / "aplicacion"
if str(_APP_COLOMBO) not in sys.path:
    sys.path.insert(0, str(_APP_COLOMBO))
from tema_colombo import Marca, tipografia  # noqa: E402

_TIPO = tipografia()

# ──────────────────────────────────────────────────────────── Rutas
if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).parent

PERFILES_JSON   = BASE / "perfiles_macmillan.json"
CONFIG_BOT_JSON = BASE / "config_macmillan_activo.json"
CATALOGO_JSON   = BASE / "catalogo_clases_macmillan.json"   # lo escribe el bot
# herramientas/macmillan/ -> raiz del proyecto; el robot esta en bots/macmillan/
RAIZ            = BASE.parents[1]
BOT_SCRIPT      = RAIZ / "bots" / "macmillan" / "automatizar_macmillan.py"
VENV_PYTHON     = RAIZ / ".venv" / "Scripts" / "python.exe"
MEE_URL         = "https://www.macmillaneducationeverywhere.com"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


# ──────────────────────────────────────────────────────────── Tema
class T:
    """Identidad Colombo Americano (valores en tema_colombo.py)."""
    PRIM     = Marca.AZUL
    PRIM_H   = Marca.AZUL_H
    PRIM_OSC = Marca.AZUL_OSC
    PRIM_BG  = Marca.AZUL_CLARO
    ACC      = Marca.ROJO
    ACC_H    = Marca.ROJO_H
    # Acciones
    VERDE    = Marca.OK
    VERDE_H  = "#166534"
    VERDE_D  = "#7FB595"
    # Neutros
    FONDO    = Marca.FONDO
    SUP      = Marca.BLANCO
    GRIS     = Marca.FONDO
    BORDE    = Marca.BORDE
    BORDE_B  = Marca.BORDE_FUERTE
    TEXTO    = Marca.TEXTO
    TEXTO2   = Marca.TEXTO
    SUAVE    = Marca.TEXTO_SUAVE
    SB_TXT   = "#C9D8EA"
    # Estados
    ERR      = Marca.ERROR
    ERR_H    = Marca.ROJO_H
    ERR_BG   = Marca.ERROR_FONDO
    ERR_BG_H = "#F6CDD1"
    ERR_DIS  = "#E9929B"
    OK       = Marca.OK
    OK_BG    = Marca.OK_FONDO
    WARN     = Marca.AVISO
    # Tipografia
    F     = _TIPO["F"]
    H1    = _TIPO["H1"]
    H2    = (F, 15, "bold")
    SUB   = _TIPO["SUBTITULO"]
    ETQ   = _TIPO["ETIQUETA"]
    NRM   = _TIPO["NORMAL"]
    AYD   = (F, 11)
    MINI  = _TIPO["MINI"]
    BTN   = _TIPO["BOTON"]
    BTNG  = _TIPO["BOTON_G"]
    R     = 10


# ──────────────────────────────────────────────── Catalogo Macmillan
LIBROS: dict[str, list[str]] = {
    "Get Involved! American Edition": [
        "INTRO - Level Intro - Class 5",
        "Level 1 - Class 2",
        "Level 1 - Class 4",
        "Level 2 - Class 1",
        "Level 3 - Class 3",
        "Level 4 - Class 6",
    ],
    "Learning Well": [
        "Level 1 - Class A",
        "Level 2 - Class B",
        "Level 3 - Class C",
        "Level 4 - Class D",
    ],
    "Speak Your Mind": [
        "Starter - Class 1",
        "Level 1 - Class 3",
        "Level 2 - Class 2",
        "Level 3 - Class 5",
        "Level 4 - Class 1",
    ],
    "Open Mind 2nd Edition": [
        "Level 1 - Class 7",
        "Level 2 - Class 8",
        "Level 3 - Class 9",
    ],
}

ABREV = {
    "Get Involved! American Edition": "Get Involved! AM",
    "Learning Well": "Learning Well",
    "Speak Your Mind": "Speak Your Mind",
    "Open Mind 2nd Edition": "Open Mind 2E",
}

NIVELES_BASE = ["Starter", "Level 1", "Level 2", "Level 3", "Level 4"]

SCORES   = ["First attempt", "Best attempt", "Show all attempts"]
FORMATOS = ["CSV"]  # el botón Export de Macmillan descarga CSV; no se convierte a Excel


def abrev(libro: str) -> str:
    return ABREV.get(libro, libro)


def nuevo_id() -> str:
    return uuid.uuid4().hex[:5]


def leer_catalogo() -> dict:
    """Clases que el bot vio en Macmillan: {libro: {nivel: [clases]}}. Se lee del disco cada vez
    porque lo escribe el bot (otro proceso) al ejecutarse."""
    try:
        datos = json.loads(CATALOGO_JSON.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


# ─────────────────────────────────────────────── Persistencia JSON
def perfil_nuevo(libro: str, nivel: str, recurso: str, clases: list, scores: str, formato: str,
                 nombre: str | None = None, id_: str | None = None) -> dict:
    return {
        "id": id_ or nuevo_id(),
        "nombre_perfil": nombre or f"{abrev(libro)} {nivel}".strip(),
        "libro": libro,
        "nivel": nivel,
        "recurso": recurso,
        "clases": list(clases),
        "scores_mode": scores if scores in SCORES else SCORES[-1],
        "formato": formato if formato in FORMATOS else "CSV",
        "todas_clases": False,
        "ultima_ejecucion": "",
    }


def _normalizar(p: dict) -> dict:
    base = perfil_nuevo(p.get("libro", "Speak Your Mind"),
                        p.get("nivel", "Level 1"),
                        p.get("recurso", "Macmillan Education Everywhere App"),
                        p.get("clases", []),
                        p.get("scores_mode", SCORES[-1]),
                        p.get("formato", "CSV"),
                        p.get("nombre_perfil"),
                        str(p.get("id") or nuevo_id()))
    base["todas_clases"] = bool(p.get("todas_clases", False))
    base["ultima_ejecucion"] = p.get("ultima_ejecucion", "")
    return base


def texto_clases(p: dict) -> str:
    if p.get("todas_clases"):
        return "TODAS las clases"
    n = len(p["clases"])
    return f"{n} clase{'s' if n != 1 else ''}"


def datos_defecto() -> dict:
    return {
        "version": 1,
        "activo": None,
        "perfiles": [],
        "credenciales": {"usuario": "", "password": "", "url": MEE_URL},
        "ajustes": {
            "ruta_descargas": str(Path.home() / "Downloads" / "Macmillan"),
            "navegador_visible": True,
            "pausa_entre_clases": 1.0,
        },
    }


def cargar_datos() -> dict:
    d = datos_defecto()
    if not PERFILES_JSON.exists():
        # Primer arranque: perfil de ejemplo
        demo = perfil_nuevo("Get Involved! American Edition",
                            ["INTRO - Level Intro - Class 5",
                             "Level 1 - Class 2", "Level 2 - Class 1"],
                            "Show all attempts", "CSV", id_="554bc")
        d["perfiles"] = [demo]
        d["activo"] = demo["id"]
        return d
    try:
        raw = json.loads(PERFILES_JSON.read_text(encoding="utf-8"))
    except Exception:
        return d
    if isinstance(raw, list):              # formato antiguo: solo perfiles
        raw = {"perfiles": raw}
    if isinstance(raw, dict):
        d["perfiles"] = [_normalizar(p) for p in raw.get("perfiles", [])
                         if isinstance(p, dict)]
        d["credenciales"].update(raw.get("credenciales", {}) or {})
        d["ajustes"].update(raw.get("ajustes", {}) or {})
        ids = [p["id"] for p in d["perfiles"]]
        act = raw.get("activo")
        d["activo"] = act if act in ids else (ids[0] if ids else None)
    return d


def guardar_datos(d: dict) -> None:
    tmp = PERFILES_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(PERFILES_JSON)


def escribir_config_bot(perfil: dict, cred: dict, ajustes: dict) -> None:
    CONFIG_BOT_JSON.write_text(json.dumps({
        "generado": datetime.now().isoformat(timespec="seconds"),
        "plataforma": "Macmillan Education Everywhere",
        "seccion": "School work > Progress",
        "perfil": perfil,
        "credenciales": cred,
        "ajustes": ajustes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────── Helpers UI
def centrar(win, master, w: int, h: int) -> None:
    master.update_idletasks()
    x = master.winfo_rootx() + (master.winfo_width() - w) // 2
    y = master.winfo_rooty() + (master.winfo_height() - h) // 3
    win.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")


def boton_primario(master, texto, cmd, color=T.PRIM, hover=T.PRIM_H,
                   **kw) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=texto, command=cmd, font=kw.pop("font", T.BTN),
                         fg_color=kw.pop("fg_color", color), hover_color=kw.pop("hover_color", hover),
                         text_color=kw.pop("text_color", "white"), corner_radius=kw.pop("corner_radius", 8),
                         height=kw.pop("height", 36), **kw)


def boton_secundario(master, texto, cmd, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=texto, command=cmd, font=kw.pop("font", T.BTN),
                         fg_color=kw.pop("fg_color", T.SUP), hover_color=kw.pop("hover_color", T.GRIS),
                         text_color=kw.pop("text_color", T.TEXTO2), border_width=kw.pop("border_width", 1),
                         border_color=kw.pop("border_color", T.BORDE_B), corner_radius=kw.pop("corner_radius", 8),
                         height=kw.pop("height", 36), **kw)


def entrada(master, var=None, **kw) -> ctk.CTkEntry:
    return ctk.CTkEntry(master, textvariable=var, font=kw.pop("font", T.NRM), height=kw.pop("height", 36),
                        fg_color=kw.pop("fg_color", T.SUP), text_color=kw.pop("text_color", T.TEXTO),
                        border_color=kw.pop("border_color", T.BORDE_B), corner_radius=kw.pop("corner_radius", 8), **kw)


def selector_libro(master, var, cmd=None, **kw) -> ctk.CTkComboBox:
    return ctk.CTkComboBox(
        master, values=list(LIBROS), variable=var, command=cmd,
        font=kw.pop("font", T.NRM), dropdown_font=kw.pop("dropdown_font", T.NRM), height=kw.pop("height", 36),
        fg_color=kw.pop("fg_color", T.SUP), border_color=kw.pop("border_color", T.BORDE_B), button_color=kw.pop("button_color", T.PRIM), button_hover_color=kw.pop("button_hover_color", T.PRIM_H),
        text_color=kw.pop("text_color", T.TEXTO), dropdown_fg_color=kw.pop("dropdown_fg_color", T.SUP),
        dropdown_text_color=kw.pop("dropdown_text_color", T.TEXTO), dropdown_hover_color=kw.pop("dropdown_hover_color", T.PRIM_BG),
        corner_radius=kw.pop("corner_radius", 8), **kw)


class GrupoRadio(ctk.CTkFrame):
    """Opciones excluyentes en linea (mas legibles que un segmented)."""

    def __init__(self, master, opciones: list, valor: str,
                 al_cambiar: Callable | None = None):
        super().__init__(master, fg_color="transparent")
        self.var = ctk.StringVar(value=valor)
        for op in opciones:
            ctk.CTkRadioButton(
                self, text=op, value=op, variable=self.var, font=T.NRM,
                text_color=T.TEXTO, fg_color=T.PRIM, hover_color=T.PRIM_H,
                border_color=T.BORDE_B,
                command=(lambda: al_cambiar()) if al_cambiar else None,
            ).pack(side="left", padx=(0, 22))

    def get(self) -> str:
        return self.var.get()

    def set(self, v: str) -> None:
        self.var.set(v)

    def habilitar(self, on: bool) -> None:
        for w in self.winfo_children():
            w.configure(state="normal" if on else "disabled")


# ─────────────────────────────────── Importar clases (Excel / CSV)
_ENCABEZADOS = {"clase", "clases", "class", "classes", "class name",
                "nombre", "name", "curso", "grupo", "group"}


def _limpiar_lista(valores) -> list:
    """Quita vacios, encabezados y duplicados conservando el orden."""
    vistos, out = set(), []
    for v in valores:
        t = str(v).strip() if v is not None else ""
        if t and t.lower() not in _ENCABEZADOS and t not in vistos:
            vistos.add(t)
            out.append(t)
    return out


def parsear_texto_clases(raw: str) -> list:
    """Una clase por linea, o separadas por coma / punto y coma / tab."""
    return _limpiar_lista(re.split(r"[\n\r,;\t]+", raw))


def leer_clases_archivo(ruta: str) -> list:
    """Lee la columna A de un .xlsx/.xlsm (openpyxl) o la 1a columna de un .csv."""
    ext = Path(ruta).suffix.lower()
    if ext == ".csv":
        import csv
        with open(ruta, newline="", encoding="utf-8-sig") as f:
            muestra = f.read(2048)
            f.seek(0)
            try:
                dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
            except csv.Error:
                dialecto = csv.excel
            vals = [fila[0] for fila in csv.reader(f, dialecto) if fila]
    else:
        from openpyxl import load_workbook          # import perezoso
        libro = load_workbook(ruta, read_only=True, data_only=True)
        hoja = libro.worksheets[0]
        vals = [fila[0] for fila in hoja.iter_rows(min_col=1, max_col=1,
                                                    values_only=True)]
        libro.close()
    clases = _limpiar_lista(vals)
    if not clases:
        raise ValueError("No se encontraron clases en la primera columna.\n"
                         "Verifica que la planilla tenga las clases en la "
                         "columna A (encabezado: Clase).")
    return clases


def generar_plantilla(destino: str, ejemplos: list) -> None:
    """Crea la plantilla de clases (.xlsx con openpyxl, o .csv)."""
    if Path(destino).suffix.lower() == ".csv":
        import csv
        with open(destino, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Clase"])
            w.writerows([c] for c in ejemplos)
        return
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Clases"
    ws["A1"] = "Clase"
    ws["A1"].font = Font(bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=T.PRIM.lstrip("#"))
    for i, c in enumerate(ejemplos, start=2):
        ws.cell(row=i, column=1, value=c)
    ws.column_dimensions["A"].width = 48
    ws.freeze_panes = "A2"
    info = wb.create_sheet("Instrucciones")
    for i, t in enumerate([
        "Plantilla de clases - Macmillan Education Everywhere",
        "1. Escribe una clase por fila en la columna A de la hoja 'Clases'.",
        "2. Usa el nombre EXACTO como aparece en mee (School work > Progress).",
        "3. Guarda y usa el boton 'Excel' en el configurador para cargarla.",
    ], start=1):
        info.cell(row=i, column=1, value=t)
    info["A1"].font = Font(bold=True)
    info.column_dimensions["A"].width = 80
    wb.save(destino)


# ─────────────────────────────────────────── Selector de clases
class SelectorClases(ctk.CTkFrame):
    """Lista de clases estilo Oxford: caja de texto (una clase por linea),
    check 'TODAS las clases' y botones Limpiar / Pegar lista / Excel /
    Descargar plantilla."""

    def __init__(self, master, altura: int = 200):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._libro = ""

        # Toolbar (igual que Oxford)
        self.tb = ctk.CTkFrame(self, fg_color="transparent")
        self.tb.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.lbl_n = ctk.CTkLabel(self.tb, text="0 clases", font=T.ETQ,
                                  text_color=T.TEXTO, anchor="w")
        self.lbl_n.pack(side="left")
        self._botones: list[ctk.CTkButton] = []
        for txt, cmd in [("Descargar plantilla", self._plantilla),
                         ("Excel", self._excel),
                         ("Pegar lista", self._pegar)]:
            b = ctk.CTkButton(self.tb, text=txt, command=cmd, font=T.AYD,
                              height=30, width=0, corner_radius=6,
                              fg_color=T.SUP,
                              hover_color=T.PRIM_BG,
                              text_color=T.TEXTO2,
                              border_width=1, border_color=T.BORDE_B)
            b.pack(side="right", padx=(6, 0))
            self._botones.append(b)

        # Caja de texto con las clases
        self.caja = ctk.CTkTextbox(self, fg_color=T.SUP, text_color=T.TEXTO,
                                   border_width=1, border_color=T.BORDE_B,
                                   corner_radius=8, font=T.NRM, height=altura)
        self.caja.grid(row=1, column=0, sticky="nsew")
        self.caja.bind("<KeyRelease>", lambda _: self._refresh())
        self.caja.bind("<<Paste>>", lambda _: self.after(10, self._refresh))

        # Check Todas las clases
        self.var_todas = ctk.BooleanVar(value=False)
        self.chk_todas = ctk.CTkCheckBox(self.tb, text="TODAS las clases", font=T.ETQ,
                                         text_color=T.TEXTO, variable=self.var_todas,
                                         command=self._on_todas)
        self.chk_todas.pack(side="left", padx=(12, 0))

    def _on_todas(self):
        estado = "disabled" if self.var_todas.get() else "normal"
        self.caja.configure(state=estado)
        for b in self._botones:
            b.configure(state=estado)

    # API
    def set(self, libro: str, clases: list, todas: bool = False) -> None:
        self._libro = libro
        self._escribir(clases)
        self.var_todas.set(bool(todas))
        self._on_todas()

    def get(self) -> list:
        return parsear_texto_clases(self.caja.get("1.0", "end-1c"))
        
    def todas(self) -> bool:
        return bool(self.var_todas.get())

    def cargar_lista(self, clases: list) -> None:
        """Reemplaza la lista (como Oxford)."""
        self._escribir(clases)

    # Internos
    def _escribir(self, clases: list) -> None:
        estado = self.caja.cget("state")
        self.caja.configure(state="normal")
        self.caja.delete("1.0", "end")
        if clases:
            self.caja.insert("1.0", "\n".join(clases))
        self.caja.configure(state=estado)
        self._refresh()

    def _refresh(self) -> None:
        n = len(self.get())
        self.lbl_n.configure(text=f"{n} clase{'s' if n != 1 else ''}")

    # Importacion
    def _pegar(self) -> None:
        DlgPegarClases(self, self.get(), al_ok=self.cargar_lista)

    def _excel(self) -> None:
        ruta = filedialog.askopenfilename(
            parent=self.winfo_toplevel(), title="Planilla con clases",
            filetypes=[("Excel o CSV", "*.xlsx *.xlsm *.csv"),
                       ("Excel", "*.xlsx *.xlsm"), ("CSV", "*.csv"),
                       ("Todos", "*.*")])
        if not ruta:
            return
        try:
            clases = leer_clases_archivo(ruta)
        except ImportError:
            messagebox.showerror("Falta openpyxl",
                                 "Para leer Excel instala openpyxl:\n"
                                 "pip install openpyxl\n\n"
                                 "O guarda la planilla como .csv.",
                                 parent=self.winfo_toplevel())
            return
        except Exception as e:                        # noqa: BLE001
            messagebox.showerror("Error en la planilla", str(e),
                                 parent=self.winfo_toplevel())
            return
        self.cargar_lista(clases)

    def _plantilla(self) -> None:
        destino = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), title="Guardar plantilla como...",
            defaultextension=".xlsx",
            initialfile="Plantilla_Clases_Macmillan.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
        if not destino:
            return
        ejemplos = LIBROS.get(self._libro) or ["Level 1 - Class 2"]
        try:
            generar_plantilla(destino, ejemplos)
        except ImportError:
            messagebox.showerror("Falta openpyxl",
                                 "pip install openpyxl\n\n"
                                 "O guarda la plantilla como .csv.",
                                 parent=self.winfo_toplevel())
            return
        except Exception as e:                        # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}",
                                 parent=self.winfo_toplevel())
            return
        messagebox.showinfo("Plantilla guardada", destino,
                            parent=self.winfo_toplevel())


# ─────────────────────────────────────────────────── Modales
class ModalBase(ctk.CTkToplevel):
    def __init__(self, master, titulo: str, w: int, h: int):
        super().__init__(master)
        self.title(titulo)
        self.configure(fg_color=T.FONDO)
        self.resizable(False, False)
        raiz = master.winfo_toplevel()
        self.transient(raiz)
        centrar(self, raiz, w, h)
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.bind("<Escape>", lambda _: self.cerrar())
        self.after(150, self._activar)

    def _activar(self) -> None:
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def cerrar(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        padre = self.master.winfo_toplevel()
        self.destroy()
        if isinstance(padre, ModalBase):      # modal anidado: devolver el foco
            try:
                padre.grab_set()
                padre.focus_force()
            except Exception:
                pass

    def cabecera(self, titulo: str, sub: str) -> None:
        cab = ctk.CTkFrame(self, fg_color=T.PRIM_OSC, corner_radius=0, height=74)
        cab.pack(fill="x")
        cab.pack_propagate(False)
        ctk.CTkLabel(cab, text=titulo, font=T.H2, text_color="white",
                     anchor="w").pack(fill="x", padx=24, pady=(14, 0))
        ctk.CTkLabel(cab, text=sub, font=T.AYD, text_color=T.SB_TXT,
                     anchor="w").pack(fill="x", padx=24)

    def pie(self, texto_ok: str, cmd_ok: Callable) -> None:
        p = ctk.CTkFrame(self, fg_color="transparent")
        p.pack(side="bottom", fill="x", padx=24, pady=(8, 20))
        p.grid_columnconfigure((0, 1), weight=1)
        boton_secundario(p, "Cancelar", self.cerrar
                         ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        boton_primario(p, texto_ok, cmd_ok
                       ).grid(row=0, column=1, sticky="ew", padx=(6, 0))


class DlgPegarClases(ModalBase):
    """Pegar una lista de clases (igual que en Oxford)."""

    def __init__(self, master, actuales: list, al_ok: Callable):
        super().__init__(master, "Pegar lista de clases", 620, 520)
        self.al_ok = al_ok
        self.cabecera("Pegar lista de clases",
                      "Una clase por linea, o separadas por coma (,) o punto "
                      "y coma (;). Puedes copiar una columna de Excel.")
        self.pie("Aceptar", self._ok)
        c = ctk.CTkFrame(self, fg_color="transparent")
        c.pack(fill="both", expand=True, padx=24, pady=(14, 0))
        self.txt = ctk.CTkTextbox(c, fg_color=T.SUP, text_color=T.TEXTO,
                                  border_width=1, border_color=T.BORDE_B,
                                  corner_radius=8, font=T.NRM)
        self.txt.pack(fill="both", expand=True)
        if actuales:
            self.txt.insert("1.0", "\n".join(actuales))
        self.txt.bind("<KeyRelease>", lambda _: self._contar())
        fila = ctk.CTkFrame(c, fg_color="transparent")
        fila.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(fila, text="Al aceptar reemplazara la lista actual.",
                     font=T.AYD, text_color=T.SUAVE).pack(side="left")
        self.lbl = ctk.CTkLabel(fila, text="", font=T.AYD, text_color=T.SUAVE)
        self.lbl.pack(side="right")
        self._contar()
        self.after(200, self.txt.focus_set)

    def _contar(self) -> None:
        n = len(parsear_texto_clases(self.txt.get("1.0", "end")))
        self.lbl.configure(text=f"{n} clase{'s' if n != 1 else ''} detectada"
                                f"{'s' if n != 1 else ''}")

    def _ok(self) -> None:
        clases = parsear_texto_clases(self.txt.get("1.0", "end"))
        if not clases:
            messagebox.showwarning("Lista vacia", "Pega al menos una clase.",
                                   parent=self)
            return
        self.cerrar()
        self.al_ok(clases)


class DlgNombre(ModalBase):
    def __init__(self, master, actual: str, al_ok: Callable):
        super().__init__(master, "Renombrar perfil", 460, 250)
        self.al_ok = al_ok
        self.cabecera("Renombrar perfil", "Nombre visible en la tarjeta.")
        self.pie("Aceptar", self._ok)
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=24, pady=(16, 0))
        self.ent = entrada(cuerpo)
        self.ent.insert(0, actual)
        self.ent.pack(fill="x")
        self.ent.bind("<Return>", lambda _: self._ok())
        self.after(200, lambda: (self.ent.focus_set(),
                                 self.ent.select_range(0, "end")))

    def _ok(self) -> None:
        n = self.ent.get().strip()
        if not n:
            messagebox.showwarning("Falta nombre", "Escribe un nombre.",
                                   parent=self)
            return
        self.al_ok(n)
        self.cerrar()


class DlgNuevoPerfil(ModalBase):
    def __init__(self, master, app, al_ok: Callable):
        super().__init__(master, "Nuevo perfil", 740, 740)
        self.app = app
        self.al_ok = al_ok
        self._nombre_editado = False
        self.cabecera("Nuevo perfil",
                      "Elige el libro, las clases y el tipo de reporte "
                      "de School work > Progress.")
        self.pie("Crear perfil", self._ok)

        c = ctk.CTkFrame(self, fg_color="transparent")
        c.pack(fill="both", expand=True, padx=24, pady=(14, 0))
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(9, weight=1)

        ctk.CTkLabel(c, text="1.  Libro / Curso", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=0, column=0, sticky="ew")
        self.ent_libro = entrada(c)
        self.ent_libro.insert(0, "Speak Your Mind")
        self.ent_libro.grid(row=1, column=0, sticky="ew", pady=(4, 10))

        ctk.CTkLabel(c, text="Nivel (Opcional)", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=2, column=0, sticky="ew")
        self.ent_nivel = entrada(c)
        self.ent_nivel.insert(0, "Level 1")
        self.ent_nivel.grid(row=3, column=0, sticky="ew", pady=(4, 10))
        
        ctk.CTkLabel(c, text="Recurso", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=4, column=0, sticky="ew")
        self.ent_recurso = entrada(c)
        self.ent_recurso.insert(0, "Macmillan Education Everywhere App")
        self.ent_recurso.grid(row=5, column=0, sticky="ew", pady=(4, 10))

        ctk.CTkLabel(c, text="Nombre del perfil (Opcional)", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=6, column=0, sticky="ew")
        self.ent_nombre = entrada(c)
        self.ent_nombre.grid(row=7, column=0, sticky="ew", pady=(4, 12))

        ctk.CTkLabel(c, text="2.  Clases asociadas", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=8, column=0, sticky="ew")
        self.sel = SelectorClases(c, altura=120)
        self.sel.grid(row=9, column=0, sticky="nsew", pady=(4, 12))

        ctk.CTkLabel(c, text="3.  Tipo de reporte / Attempt", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=10, column=0, sticky="ew")
        self.rad_sc = GrupoRadio(c, SCORES, SCORES[-1])
        self.rad_sc.grid(row=11, column=0, sticky="w", pady=(6, 12))

        ctk.CTkLabel(c, text="Formato de exportacion", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=12, column=0, sticky="ew")
        self.rad_fmt = GrupoRadio(c, FORMATOS, "CSV")
        self.rad_fmt.grid(row=13, column=0, sticky="w", pady=(6, 0))

    def _ok(self) -> None:
        clases = self.sel.get()
        todas = self.sel.todas()
        
        libro = self.ent_libro.get().strip()
        nivel = self.ent_nivel.get().strip()
        recurso = self.ent_recurso.get().strip()
        nombre = self.ent_nombre.get().strip()
        
        if not libro:
            messagebox.showwarning("Falta libro", "Escribe el nombre del libro.", parent=self)
            return
            
        if not todas and not clases:
            messagebox.showwarning(
                "Sin clases",
                "Agrega al menos una clase o activa 'TODAS las clases'.",
                parent=self)
            return
            
        p = perfil_nuevo(libro, nivel, recurso, clases, self.rad_sc.get(),
                         self.rad_fmt.get(), nombre)
        p["todas_clases"] = todas
        self.al_ok(p)
        self.cerrar()


# ──────────────────────────────────────────────────── Paneles base
class PBase(ctk.CTkFrame):
    def __init__(self, master, titulo: str, desc: str):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        ctk.CTkLabel(hdr, text=titulo, font=T.H1, text_color=T.TEXTO,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(hdr, text=desc, font=T.SUB, text_color=T.SUAVE,
                     anchor="w").pack(fill="x")
        self.cont = ctk.CTkFrame(self, fg_color="transparent")
        self.cont.grid(row=1, column=0, sticky="nsew")
        self.cont.grid_columnconfigure(0, weight=1)

    def tarjeta(self, master=None) -> ctk.CTkFrame:
        return ctk.CTkFrame(master or self.cont, fg_color=T.SUP,
                            corner_radius=T.R, border_width=1,
                            border_color=T.BORDE)


# ─────────────────────────────────────────────── Tarjeta de perfil
class TarjetaPerfil(ctk.CTkFrame):
    def __init__(self, master, p: dict, activo: bool,
                 ejecutando_id: str | None, acc: dict, barras: list):
        super().__init__(master, fg_color=T.SUP, corner_radius=T.R,
                         border_width=2 if activo else 1,
                         border_color=T.ACC if activo else T.BORDE)
        corriendo = ejecutando_id == p["id"]
        ocupado = ejecutando_id is not None
        self.grid_columnconfigure(0, weight=1)

        # ── Info
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=0, sticky="nsew", padx=(24, 12), pady=20)
        titulo = p["nombre_perfil"] + ("  -> Activo" if activo else "")
        ctk.CTkLabel(info, text=titulo, font=T.H2, text_color=T.TEXTO,
                     anchor="w").pack(fill="x")
        
        info_str = f"📘  {p['libro']}"
        if p.get('nivel'):
            info_str += f"   ·   Nivel: {p['nivel']}"
            
        ctk.CTkLabel(info, text=info_str, font=T.AYD,
                     text_color=T.TEXTO2, anchor="w"
                     ).pack(fill="x", pady=(2, 6))
        n = len(p["clases"])
        meta = (f"ID: {p['id']}    ·    {texto_clases(p)}"
                f"    ·    Scores: {p['scores_mode']}"
                f"    ·    Formato: {p['formato']}"
                f"    ·    Recurso: {p.get('recurso', 'App')}")
        ctk.CTkLabel(info, text=meta, font=T.AYD, text_color=T.SUAVE,
                     anchor="w").pack(fill="x")
        if p.get("todas_clases"):
            prev = "Se descargaran todas las clases del libro en mee."
        else:
            prev = ", ".join(p["clases"][:3]) + (f"  +{n - 3} mas" if n > 3 else "")
        ctk.CTkLabel(info, text=prev or "Sin clases configuradas",
                     font=T.AYD, text_color=T.SUAVE, anchor="w",
                     wraplength=520, justify="left").pack(fill="x", pady=(2, 0))
        if p.get("ultima_ejecucion"):
            ctk.CTkLabel(info, text=f"🕓  {p['ultima_ejecucion']}",
                         font=T.AYD, text_color=T.OK, anchor="w"
                         ).pack(fill="x", pady=(4, 0))

        # ── Ejecutar (solo perfil activo)
        if activo:
            centro = ctk.CTkFrame(self, fg_color="transparent")
            centro.grid(row=0, column=1, padx=12)
            ctk.CTkButton(
                centro,
                text="⏳  Ejecutando…" if corriendo else "▶  EJECUTAR BOT (Macmillan)",
                font=T.BTNG, width=250, height=46, corner_radius=8,
                fg_color=T.VERDE, hover_color=T.VERDE_H,
                text_color="white", text_color_disabled="white",
                state="disabled" if ocupado else "normal",
                command=lambda: acc["ejecutar"](p["id"]),
            ).pack()
            if corriendo:
                bar = ctk.CTkProgressBar(centro, mode="indeterminate",
                                         width=250, height=6,
                                         progress_color=T.VERDE,
                                         fg_color=T.BORDE)
                bar.pack(pady=(8, 0))
                bar.start()
                barras.append(bar)
            elif ocupado:
                ctk.CTkLabel(centro, text="Otro perfil se esta ejecutando",
                             font=T.AYD, text_color=T.SUAVE).pack(pady=(4, 0))

        # ── Botonera vertical
        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.grid(row=0, column=2, padx=(4, 20), pady=16)
        ctk.CTkButton(acciones, text="Cargar", font=T.BTN, width=120,
                      height=32, corner_radius=8, fg_color=T.PRIM,
                      hover_color=T.PRIM_H, text_color="white",
                      command=lambda: acc["cargar"](p["id"])
                      ).pack(pady=3)
        ctk.CTkButton(acciones, text="Renombrar", font=T.BTN, width=120,
                      height=32, corner_radius=8, fg_color=T.SUP,
                      hover_color=T.GRIS, text_color=T.TEXTO2,
                      border_width=1, border_color=T.BORDE_B,
                      command=lambda: acc["renombrar"](p["id"])
                      ).pack(pady=3)
        ctk.CTkButton(acciones, text="Eliminar", font=T.BTN, width=120,
                      height=32, corner_radius=8, fg_color=T.ERR_BG,
                      hover_color=T.ERR_BG_H, text_color=T.ERR,
                      text_color_disabled=T.ERR_DIS,
                      state="disabled" if corriendo else "normal",
                      command=lambda: acc["eliminar"](p["id"])
                      ).pack(pady=3)


# ─────────────────────────────────────── Vista: Gestor de Libros
# ─────────────────────────────────────── Vista: Libros y Perfiles
class PanelPerfiles(PBase):
    def __init__(self, master, acc: dict):
        super().__init__(master, "Libros y Perfiles de descarga",
                         "Selecciona un libro o perfil, o crea uno nuevo.")
        self.acc = acc
        self._barras: list[ctk.CTkProgressBar] = []
        self.cont.grid_rowconfigure(0, weight=1)
        self.scroll = ctk.CTkScrollableFrame(self.cont, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

    def actualizar(self, perfiles: list, activo_id: str | None,
                   ejecutando_id: str | None) -> None:
        for b in self._barras:
            try:
                b.stop()
            except Exception:
                pass
        self._barras.clear()
        for w in self.scroll.winfo_children():
            w.destroy()

        fila = 0
        if not perfiles:
            vacio = self.tarjeta(self.scroll)
            vacio.grid(row=0, column=0, sticky="ew", pady=(0, 12), padx=(0, 6))
            ctk.CTkLabel(vacio, text="📚", font=(T.F, 34)).pack(pady=(26, 0))
            ctk.CTkLabel(vacio, text="Aun no hay perfiles de descarga",
                         font=T.H2, text_color=T.TEXTO).pack()
            ctk.CTkLabel(vacio, text="Crea el primero con el boton de abajo.",
                         font=T.AYD, text_color=T.SUAVE).pack(pady=(0, 26))
            fila = 1

        for p in perfiles:
            TarjetaPerfil(self.scroll, p, p["id"] == activo_id,
                          ejecutando_id, self.acc, self._barras
                          ).grid(row=fila, column=0, sticky="ew",
                                 pady=(0, 12), padx=(0, 6))
            fila += 1

        ctk.CTkButton(self.scroll, text="+  Nuevo libro / perfil",
                      font=T.BTNG, height=44, corner_radius=8,
                      fg_color=T.PRIM, hover_color=T.PRIM_H,
                      text_color="white", command=self.acc["nuevo"]
                      ).grid(row=fila, column=0, sticky="ew",
                             pady=(2, 10), padx=(0, 6))


# ─────────────────────────────────────────── Vista: Credenciales
class PanelCredenciales(PBase):
    def __init__(self, master, al_guardar: Callable):
        super().__init__(master, "Credenciales Macmillan",
                         "Cuenta con la que el bot inicia sesion en "
                         "Macmillan Education Everywhere.")
        card = self.tarjeta()
        card.grid(row=0, column=0, sticky="ew")
        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=28, pady=24)
        f.grid_columnconfigure(0, weight=1)

        self.var_u = ctk.StringVar()
        self.var_p = ctk.StringVar()
        self.var_l = ctk.StringVar(value=MEE_URL)

        ctk.CTkLabel(f, text="Correo / usuario", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=0, column=0,
                                                          sticky="ew")
        entrada(f, self.var_u, placeholder_text="docente@colombo.edu.co"
                ).grid(row=1, column=0, sticky="ew", pady=(4, 14))

        ctk.CTkLabel(f, text="Contrasena", font=T.ETQ, text_color=T.TEXTO,
                     anchor="w").grid(row=2, column=0, sticky="ew")
        fila = ctk.CTkFrame(f, fg_color="transparent")
        fila.grid(row=3, column=0, sticky="ew", pady=(4, 14))
        fila.grid_columnconfigure(0, weight=1)
        self.ent_p = entrada(fila, self.var_p, show="•")
        self.ent_p.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.btn_ver = boton_secundario(fila, "👁  Mostrar", self._toggle,
                                        width=110)
        self.btn_ver.grid(row=0, column=1)

        ctk.CTkLabel(f, text="URL de la plataforma", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=4, column=0,
                                                          sticky="ew")
        entrada(f, self.var_l).grid(row=5, column=0, sticky="ew", pady=(4, 6))
        ctk.CTkLabel(f, text="🔒  Se guardan localmente en "
                             "perfiles_macmillan.json de este equipo.",
                     font=T.AYD, text_color=T.SUAVE, anchor="w"
                     ).grid(row=6, column=0, sticky="ew", pady=(0, 16))
        boton_primario(f, "Guardar credenciales", al_guardar, width=220
                       ).grid(row=7, column=0, sticky="w")

    def _toggle(self) -> None:
        oculto = self.ent_p.cget("show") == "•"
        self.ent_p.configure(show="" if oculto else "•")
        self.btn_ver.configure(text="🙈  Ocultar" if oculto else "👁  Mostrar")

    def get(self) -> dict:
        return {"usuario": self.var_u.get().strip(),
                "password": self.var_p.get(),
                "url": self.var_l.get().strip() or MEE_URL}

    def set(self, d: dict) -> None:
        self.var_u.set(d.get("usuario", ""))
        self.var_p.set(d.get("password", ""))
        self.var_l.set(d.get("url", MEE_URL))


# ───────────────────────────────────────── Vista: Organizacion
class PanelOrganizacion(PBase):
    """Elige un perfil y ajusta su libro, nivel y clases (las clases se escogen del nivel elegido)."""

    TXT_AGREGAR = "Agregar una clase de este nivel…"

    def __init__(self, master, al_guardar: Callable, app):
        super().__init__(master, "Organizacion y clases",
                         "Elige el perfil y ajusta su libro, nivel y clases "
                         "(School work > Progress).")
        self.al_guardar = al_guardar
        self.app = app
        self._mapa: dict[str, str] = {}   # texto del selector -> id del perfil
        self._pid: str | None = None
        self.cont.grid_rowconfigure(0, weight=1)

        self.vacio = self.tarjeta()
        ctk.CTkLabel(self.vacio, text="No hay perfiles.\n"
                                      "Crea uno en Perfiles.",
                     font=T.NRM, text_color=T.SUAVE).pack(pady=40)

        self.form = self.tarjeta()
        f = ctk.CTkFrame(self.form, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=28, pady=22)
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(8, weight=1)

        def etiqueta(texto, fila):
            ctk.CTkLabel(f, text=texto, font=T.ETQ, text_color=T.TEXTO,
                         anchor="w").grid(row=fila, column=0, sticky="w")

        etiqueta("Perfil", 0)
        self.var_perfil = ctk.StringVar()
        self.opt_perfil = selector_libro(f, self.var_perfil, self._on_perfil)
        self.opt_perfil.grid(row=1, column=0, sticky="ew", pady=(4, 12))

        etiqueta("Libro / Curso", 2)
        self.var_libro = ctk.StringVar()
        self.opt_libro = selector_libro(f, self.var_libro, self._on_libro)
        self.opt_libro.grid(row=3, column=0, sticky="ew", pady=(4, 12))

        etiqueta("Nivel", 4)
        self.var_nivel = ctk.StringVar()
        self.opt_nivel = selector_libro(f, self.var_nivel, self._on_nivel)
        self.opt_nivel.grid(row=5, column=0, sticky="ew", pady=(4, 12))

        etiqueta("Clases asociadas", 6)
        self.var_agregar = ctk.StringVar(value=self.TXT_AGREGAR)
        self.opt_agregar = selector_libro(f, self.var_agregar, self._on_agregar)
        self.opt_agregar.grid(row=7, column=0, sticky="ew", pady=(4, 8))

        self.sel = SelectorClases(f, altura=180)
        self.sel.grid(row=8, column=0, sticky="nsew", pady=(0, 14))
        self.sel.caja.bind("<KeyRelease>", lambda _e: self._refrescar_disponibles(), add="+")
        boton_primario(f, "Guardar cambios del perfil", self.al_guardar,
                       width=240).grid(row=9, column=0, sticky="w")

    # ── Selectores
    def _on_perfil(self, texto: str) -> None:
        # Se edita el perfil elegido, este o no activo: no se cambia el perfil activo
        pid = self._mapa.get(texto)
        if pid:
            self._llenar(self.app.perfil(pid))

    def _on_libro(self, libro: str) -> None:
        self.opt_nivel.configure(values=self.app.obtener_niveles(libro))
        if self.var_nivel.get() not in self.app.obtener_niveles(libro):
            self.var_nivel.set("")
        self._cargar_clases()

    def _on_nivel(self, _nivel: str = "") -> None:
        self._cargar_clases()

    def _cargar_clases(self) -> None:
        """Muestra las clases asociadas a ese libro y nivel: las del perfil si es su mismo nivel y, si no,
        las que ya se guardaron en perfiles de ese nivel. Así se pueden editar o quitar."""
        p = self.app.perfil(self._pid)
        libro, nivel = self.var_libro.get(), self.var_nivel.get()
        igual = bool(p) and p["libro"] == libro and p["nivel"] == nivel
        self.sel.set(libro, p["clases"] if igual else self.app.clases_guardadas(libro, nivel),
                     bool(igual and p.get("todas_clases")))
        self._refrescar_disponibles()

    def _refrescar_disponibles(self) -> None:
        elegidas = set(self.sel.get())
        libres = [c for c in self.app.obtener_clases_nivel(self.var_libro.get(), self.var_nivel.get())
                  if c not in elegidas]
        self.opt_agregar.configure(values=libres or ["(no hay más clases guardadas para este nivel)"])
        self.var_agregar.set(self.TXT_AGREGAR)

    def _on_agregar(self, clase: str) -> None:
        if clase and not clase.startswith("("):
            self.sel.cargar_lista(self.sel.get() + [clase])
        self._refrescar_disponibles()

    # ── API para la app
    @property
    def pid(self) -> str | None:
        """Id del perfil que se está editando en este panel."""
        return self._pid

    def set_perfil(self, activo: dict | None) -> None:
        """La app llama a esto al refrescar. Se sigue editando el perfil que ya estaba elegido
        en el panel (si todavía existe); si no, el activo."""
        p = self.app.perfil(self._pid) or activo
        if p is None or not self.app.perfiles:
            self.form.grid_forget()
            self.vacio.grid(row=0, column=0, sticky="new")
            return
        self._llenar(p)

    def _llenar(self, p: dict) -> None:
        perfiles = self.app.perfiles
        self.vacio.grid_forget()
        self.form.grid(row=0, column=0, sticky="nsew")
        self._pid = p["id"]

        nombres = [q["nombre_perfil"] for q in perfiles]
        self._mapa = {(q["nombre_perfil"] if nombres.count(q["nombre_perfil"]) == 1
                       else f"{q['nombre_perfil']} ({q['id']})"): q["id"] for q in perfiles}
        self.opt_perfil.configure(values=list(self._mapa))
        self.var_perfil.set(next(t for t, i in self._mapa.items() if i == p["id"]))

        libros = self.app.obtener_lista_libros()
        if p["libro"] not in libros:
            libros.append(p["libro"])
        self.opt_libro.configure(values=libros)
        self.var_libro.set(p["libro"])
        self.opt_nivel.configure(values=self.app.obtener_niveles(p["libro"]))
        self.var_nivel.set(p["nivel"])
        self.sel.set(p["libro"], p["clases"], p.get("todas_clases", False))
        self._refrescar_disponibles()

    def get(self) -> dict:
        return {"libro": self.var_libro.get().strip(),
                "nivel": self.var_nivel.get().strip(),
                "clases": self.sel.get(),
                "todas_clases": self.sel.todas()}


# ──────────────────────────────────────────────── Vista: Settings
class PanelSettings(PBase):
    def __init__(self, master, al_guardar: Callable):
        super().__init__(master, "Settings",
                         "Parametros de exportacion del perfil activo "
                         "y opciones generales del bot.")
        card = self.tarjeta()
        card.grid(row=0, column=0, sticky="ew")
        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=28, pady=22)
        f.grid_columnconfigure(0, weight=1)

        self.lbl_perfil = ctk.CTkLabel(f, text="PERFIL ACTIVO", font=T.MINI,
                                       text_color=T.PRIM, anchor="w")
        self.lbl_perfil.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(f, text="Scores (attempts)", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.rad_sc = GrupoRadio(f, SCORES, SCORES[-1])
        self.rad_sc.grid(row=2, column=0, sticky="w", pady=(6, 14))
        ctk.CTkLabel(f, text="Formato del reporte", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=3, column=0, sticky="ew")
        self.rad_fmt = GrupoRadio(f, FORMATOS, "CSV")
        self.rad_fmt.grid(row=4, column=0, sticky="w", pady=(6, 16))

        ctk.CTkFrame(f, fg_color=T.BORDE, height=1
                     ).grid(row=5, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkLabel(f, text="GENERAL", font=T.MINI, text_color=T.PRIM,
                     anchor="w").grid(row=6, column=0, sticky="ew")

        ctk.CTkLabel(f, text="Carpeta de descargas", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w"
                     ).grid(row=7, column=0, sticky="ew", pady=(6, 0))
        fila = ctk.CTkFrame(f, fg_color="transparent")
        fila.grid(row=8, column=0, sticky="ew", pady=(4, 14))
        fila.grid_columnconfigure(0, weight=1)
        self.var_ruta = ctk.StringVar()
        entrada(fila, self.var_ruta).grid(row=0, column=0, sticky="ew",
                                          padx=(0, 8))
        boton_secundario(fila, "📁  Examinar", self._examinar, width=120
                         ).grid(row=0, column=1)

        self.var_visible = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(f, text="Mostrar el navegador mientras el bot trabaja",
                      variable=self.var_visible, font=T.NRM,
                      text_color=T.TEXTO, progress_color=T.PRIM
                      ).grid(row=9, column=0, sticky="w", pady=(0, 14))

        pausa = ctk.CTkFrame(f, fg_color="transparent")
        pausa.grid(row=10, column=0, sticky="w", pady=(0, 18))
        ctk.CTkLabel(pausa, text="Pausa entre clases:", font=T.NRM,
                     text_color=T.TEXTO).pack(side="left")
        self.var_pausa = ctk.DoubleVar(value=1.0)
        self.lbl_pausa = ctk.CTkLabel(pausa, text="1.0 s", font=T.ETQ,
                                      text_color=T.PRIM, width=50)
        ctk.CTkSlider(pausa, from_=0, to=5, number_of_steps=10, width=220,
                      variable=self.var_pausa, button_color=T.PRIM,
                      button_hover_color=T.PRIM_H, progress_color=T.PRIM,
                      command=lambda v: self.lbl_pausa.configure(
                          text=f"{v:.1f} s")
                      ).pack(side="left", padx=12)
        self.lbl_pausa.pack(side="left")

        boton_primario(f, "Guardar ajustes", al_guardar, width=200
                       ).grid(row=11, column=0, sticky="w")

    def _examinar(self) -> None:
        d = filedialog.askdirectory(title="Carpeta de descargas")
        if d:
            self.var_ruta.set(d)

    def set(self, p: dict | None, ajustes: dict) -> None:
        on = p is not None
        self.rad_sc.habilitar(on)
        self.rad_fmt.habilitar(on)
        if on:
            self.lbl_perfil.configure(
                text=f"PERFIL ACTIVO  ·  {p['nombre_perfil']}  ({p['id']})")
            self.rad_sc.set(p["scores_mode"])
            self.rad_fmt.set(p["formato"])
        else:
            self.lbl_perfil.configure(text="PERFIL ACTIVO  ·  ninguno")
        self.var_ruta.set(ajustes.get("ruta_descargas", ""))
        self.var_visible.set(bool(ajustes.get("navegador_visible", True)))
        v = float(ajustes.get("pausa_entre_clases", 1.0))
        self.var_pausa.set(v)
        self.lbl_pausa.configure(text=f"{v:.1f} s")

    def get_perfil(self) -> dict:
        return {"scores_mode": self.rad_sc.get(), "formato": self.rad_fmt.get()}

    def get_ajustes(self) -> dict:
        return {"ruta_descargas": self.var_ruta.get().strip(),
                "navegador_visible": self.var_visible.get(),
                "pausa_entre_clases": round(self.var_pausa.get(), 1)}


# ──────────────────────────────────────────────────────── Sidebar
class Sidebar(ctk.CTkFrame):
    ITEMS = [("📑", "Perfiles"), ("🔐", "Credenciales"),
             ("🏛", "Organización"), ("⚙", "Settings")]

    def __init__(self, master, al_cambiar: Callable):
        super().__init__(master, fg_color=T.PRIM_OSC, width=100, corner_radius=0)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._al_cambiar = al_cambiar
        self._btns: list[ctk.CTkButton] = []

        # Marca de la herramienta: la estrella del logo Colombo
        logo = ctk.CTkFrame(self, fg_color=T.SUP, width=62, height=62,
                            corner_radius=14)
        logo.grid(row=0, column=0, pady=(20, 4))
        logo.grid_propagate(False)
        ctk.CTkLabel(logo, text="★", font=(T.F, 28, "bold"),
                     text_color=T.ACC).place(relx=.5, rely=.5,
                                             anchor="center")
        ctk.CTkLabel(self, text="Macmillan", font=T.MINI,
                     text_color=T.SB_TXT).grid(row=1, column=0, pady=(0, 18))

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=2, column=0, sticky="n")
        for i, (ico, txt) in enumerate(self.ITEMS):
            b = ctk.CTkButton(nav, text=ico, width=58, height=46,
                              font=(T.F, 20), corner_radius=10,
                              fg_color="transparent", hover_color=T.PRIM,
                              text_color="white",
                              command=lambda k=i: self.seleccionar(k))
            b.pack(pady=(6, 0))
            lbl = ctk.CTkLabel(nav, text=txt, font=T.MINI,
                               text_color=T.SB_TXT, cursor="hand2")
            lbl.pack(pady=(1, 6))
            lbl.bind("<Button-1>", lambda _e, k=i: self.seleccionar(k))
            self._btns.append(b)

        # Perfil activo (chip inferior)
        chip = ctk.CTkFrame(self, fg_color=T.PRIM, corner_radius=10)
        chip.grid(row=3, column=0, padx=10, pady=16, sticky="ew")
        ctk.CTkLabel(chip, text="Perfil activo", font=T.MINI,
                     text_color=T.SB_TXT).pack(pady=(6, 0))
        self.lbl_activo = ctk.CTkLabel(chip, text="—", font=(T.F, 12, "bold"),
                                       text_color="white")
        self.lbl_activo.pack(pady=(0, 6))
        self.marcar(0)

    def seleccionar(self, idx: int) -> None:
        self.marcar(idx)
        self._al_cambiar(idx)

    def marcar(self, idx: int) -> None:
        for i, b in enumerate(self._btns):
            b.configure(fg_color=T.SUP if i == idx else "transparent")

    def set_activo(self, pid: str | None) -> None:
        self.lbl_activo.configure(text=f"● {pid}" if pid else "—")


# ──────────────────────────────────────────────── Barra de estado
class BarraEstado(ctk.CTkFrame):
    def __init__(self, master, al_ver: Callable):
        super().__init__(master, fg_color=T.SUP, height=36, corner_radius=0,
                         border_width=1, border_color=T.BORDE)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)
        self.lbl_dot = ctk.CTkLabel(self, text="●", font=T.NRM,
                                    text_color=T.OK, width=20)
        self.lbl_dot.grid(row=0, column=0, padx=(16, 4), pady=4)
        self.lbl = ctk.CTkLabel(self, text="Listo", font=T.AYD,
                                text_color=T.TEXTO2, anchor="w")
        self.lbl.grid(row=0, column=1, sticky="ew")
        self.btn_ver = ctk.CTkButton(self, text="Ver progreso", font=T.AYD,
                                     width=100, height=24, corner_radius=6,
                                     fg_color=T.GRIS, hover_color=T.BORDE,
                                     text_color=T.TEXTO2, command=al_ver)
        self.lbl_perfil = ctk.CTkLabel(self, text="", font=T.AYD,
                                       text_color=T.SUAVE)
        self.lbl_perfil.grid(row=0, column=3, padx=16)

    def estado(self, texto: str, color: str = T.OK) -> None:
        self.lbl_dot.configure(text_color=color)
        self.lbl.configure(text=texto[:140])

    def perfil(self, texto: str) -> None:
        self.lbl_perfil.configure(text=texto)

    def mostrar_ver(self, on: bool) -> None:
        if on:
            self.btn_ver.grid(row=0, column=2, padx=6)
        else:
            self.btn_ver.grid_forget()


# ──────────────────────────────────────────────── Bot (hilo)
class BotRunner(threading.Thread):
    """Ejecuta el bot real (subproceso) o una simulacion, sin bloquear la UI.
    Comunica eventos a la interfaz a traves de una queue.Queue."""

    def __init__(self, perfil: dict, cred: dict, ajustes: dict,
                 cola: queue.Queue):
        super().__init__(daemon=True)
        self.perfil, self.cred, self.ajustes = perfil, cred, ajustes
        self.cola = cola
        self.cancelar = threading.Event()
        self._proc: subprocess.Popen | None = None

    def emit(self, *ev) -> None:
        self.cola.put(ev)

    def log(self, texto: str, nivel: str = "info") -> None:
        self.emit("log", f"[{datetime.now():%H:%M:%S}]  {texto}", nivel)

    def detener(self) -> None:
        self.cancelar.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def run(self) -> None:
        try:
            if BOT_SCRIPT.exists():
                self._run_real()
            else:
                self._run_simulacion()
        except Exception as e:                       # noqa: BLE001
            self.log(f"Error inesperado: {e}", "err")
            self.emit("fin", False, f"Error: {e}")

    # ── Bot real
    def _run_real(self) -> None:
        self.emit("indeterminado")
        py = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
        cmd = [py, str(BOT_SCRIPT), "--config", str(CONFIG_BOT_JSON)]
        self.log(f"Lanzando bot: {BOT_SCRIPT.name}")
        self._proc = subprocess.Popen(
            cmd, cwd=str(BASE), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        assert self._proc.stdout is not None
        for linea in self._proc.stdout:
            linea = linea.rstrip()
            if linea:
                low = linea.lower()
                nivel = ("err" if any(k in low for k in ("error", "fallo",
                                                          "exception"))
                         else "ok" if any(k in low for k in ("guardado",
                                                             "descargado", "✔"))
                         else "info")
                self.log(linea, nivel)
        rc = self._proc.wait()
        if self.cancelar.is_set():
            self.emit("fin", False, "Bot detenido por el usuario.")
        elif rc == 0:
            self.emit("fin", True, "Bot finalizado correctamente.")
        else:
            self.emit("fin", False, f"El bot termino con codigo {rc}.")

    # ── Simulacion
    def _esperar(self, seg: float) -> bool:
        """Duerme 'seg' segundos; devuelve True si se pidio cancelar."""
        return self.cancelar.wait(seg)

    def _run_simulacion(self) -> None:
        p = self.perfil
        clases = p["clases"]
        ext = p["formato"].lower()
        ruta = self.ajustes.get("ruta_descargas") or str(BASE)
        pausa = float(self.ajustes.get("pausa_entre_clases", 1.0))
        pasos_fijos = [
            ("Modo SIMULACION (no se encontro automatizar_macmillan.py)", "warn", .4),
            ("Iniciando Chromium con Playwright"
             f" ({'visible' if self.ajustes.get('navegador_visible') else 'headless'})…", "info", .9),
            (f"Abriendo {self.cred.get('url', MEE_URL)}", "info", .8),
            (f"Iniciando sesion como {self.cred.get('usuario')}", "info", 1.0),
            ("Sesion iniciada", "ok", .4),
            ("Navegando a School work › Progress", "info", .9),
            (f"Seleccionando libro: {p['libro']}", "info", .7),
        ]
        total = len(pasos_fijos) + len(clases) * 3
        hecho = 0
        for texto, nivel, t in pasos_fijos:
            if self._esperar(t):
                return self._cancelado()
            self.log(texto, nivel)
            hecho += 1
            self.emit("progreso", hecho / total)

        fecha = datetime.now().strftime("%Y%m%d")
        for i, clase in enumerate(clases, 1):
            self.log(f"Clase {i}/{len(clases)}: {clase}")
            if self._esperar(.6):
                return self._cancelado()
            self.log(f"   Scores: {p['scores_mode']}")
            hecho += 1
            self.emit("progreso", hecho / total)
            if self._esperar(.8):
                return self._cancelado()
            self.log(f"   Exportando reporte {p['formato']}…")
            hecho += 1
            self.emit("progreso", hecho / total)
            if self._esperar(.6 + pausa):
                return self._cancelado()
            nombre = re.sub(r"[^\w\-]+", "_",
                            f"{abrev(p['libro'])}_{clase}_{fecha}").strip("_")
            self.log(f"   ✔ Guardado: {ruta}\\{nombre}.{ext}", "ok")
            hecho += 1
            self.emit("progreso", hecho / total)

        self.emit("fin", True,
                  f"{len(clases)} reporte{'s' if len(clases) != 1 else ''} "
                  f"generado{'s' if len(clases) != 1 else ''} (simulacion).")

    def _cancelado(self) -> None:
        self.log("Bot detenido por el usuario.", "warn")
        self.emit("fin", False, "Bot detenido por el usuario.")


# ─────────────────────────────────────── Ventana de progreso
class VentanaProgreso(ctk.CTkToplevel):
    COLORES = {"ok": T.OK, "err": T.ERR, "warn": T.WARN, "info": T.TEXTO2}

    def __init__(self, master, perfil: dict, al_detener: Callable,
                 al_cerrar: Callable):
        super().__init__(master)
        self.title("Progreso del bot - Macmillan Education Everywhere")
        self.configure(fg_color=T.FONDO)
        self.minsize(640, 420)
        centrar(self, master, 760, 520)
        self._al_detener, self._al_cerrar = al_detener, al_cerrar
        self._corriendo = True

        cab = ctk.CTkFrame(self, fg_color=T.PRIM_OSC, corner_radius=0)
        cab.pack(fill="x")
        ctk.CTkLabel(cab, text="▶  Ejecutando bot Macmillan", font=T.H2,
                     text_color="white").pack(side="left", padx=20, pady=14)
        ctk.CTkLabel(cab, text=f"{perfil['nombre_perfil']}  ·  ID {perfil['id']}"
                               f"  ·  {len(perfil['clases'])} clases",
                     font=T.AYD, text_color=T.SB_TXT
                     ).pack(side="right", padx=20)

        self.bar = ctk.CTkProgressBar(self, height=8, progress_color=T.VERDE,
                                      fg_color=T.BORDE, mode="determinate")
        self.bar.set(0)
        self.bar.pack(fill="x", padx=16, pady=(14, 0))

        self.txt = ctk.CTkTextbox(self, fg_color=T.SUP, border_width=1,
                                  border_color=T.BORDE, corner_radius=8,
                                  font=("Consolas", 11), wrap="word")
        self.txt.pack(fill="both", expand=True, padx=16, pady=12)
        for tag, col in self.COLORES.items():
            self.txt.tag_config(tag, foreground=col)
        self.txt.configure(state="disabled")

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=16, pady=(0, 14))
        pie.grid_columnconfigure(0, weight=1)
        self.lbl = ctk.CTkLabel(pie, text="⏳  Iniciando…", font=T.NRM,
                                text_color=T.SUAVE, anchor="w")
        self.lbl.grid(row=0, column=0, sticky="ew")
        self.btn_det = boton_primario(pie, "■  Detener bot", self._detener,
                                      color=T.ERR, hover=T.ERR_H, width=140)
        self.btn_det.grid(row=0, column=1, padx=(8, 0))
        boton_secundario(pie, "Cerrar", self._cerrar, width=100
                         ).grid(row=0, column=2, padx=(8, 0))
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.after(150, self.lift)

    def log(self, texto: str, nivel: str = "info") -> None:
        self.txt.configure(state="normal")
        self.txt.insert("end", texto + "\n", nivel)
        self.txt.see("end")
        self.txt.configure(state="disabled")
        if nivel != "info":
            self.lbl.configure(text=texto.split("]  ", 1)[-1][:90],
                               text_color=self.COLORES[nivel])

    def progreso(self, v: float) -> None:
        if self.bar.cget("mode") != "determinate":
            self.bar.stop()
            self.bar.configure(mode="determinate")
        self.bar.set(max(0.0, min(1.0, v)))

    def indeterminado(self) -> None:
        self.bar.configure(mode="indeterminate")
        self.bar.start()

    def fin(self, ok: bool, msg: str) -> None:
        self._corriendo = False
        if self.bar.cget("mode") == "indeterminate":
            self.bar.stop()
            self.bar.configure(mode="determinate")
        self.bar.set(1 if ok else self.bar.get())
        self.lbl.configure(text=("✅  " if ok else "⚠️  ") + msg,
                           text_color=T.OK if ok else T.WARN)
        self.btn_det.configure(state="disabled")

    def _detener(self) -> None:
        if self._corriendo and messagebox.askyesno(
                "Detener bot", "¿Detener la ejecucion del bot?", parent=self):
            self._al_detener()

    def _cerrar(self) -> None:
        if self._corriendo:
            messagebox.showinfo(
                "Bot en segundo plano",
                "El bot seguira ejecutandose.\nPuedes reabrir esta ventana "
                "con 'Ver progreso' en la barra inferior.", parent=self)
        try:
            if self.bar.cget("mode") == "indeterminate":
                self.bar.stop()
        except Exception:
            pass
        self._al_cerrar()
        self.destroy()


# ───────────────────────────────────────────────── App principal
class VistaMacmillan(ctk.CTkFrame):
    """Configurador de Macmillan como vista embebible en la app unificada."""
    TITULO = "Macmillan Education Everywhere"
    SUBTITULO = "Configurador de descargas"

    def __init__(self, master):
        super().__init__(master, fg_color=T.FONDO, corner_radius=0)
        try:
            self.tk.call("encoding", "system", "utf-8")
        except Exception:
            pass

        self.datos = cargar_datos()
        self._cola: queue.Queue = queue.Queue()
        self._runner: BotRunner | None = None
        self._ejecutando_id: str | None = None
        self._ventana: VentanaProgreso | None = None
        self._log_buffer: list[tuple[str, str]] = []
        self._ultimo_progreso = 0.0
        self._modo_indet = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, al_cambiar=self.mostrar_vista)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")

        self.area = ctk.CTkFrame(self, fg_color=T.FONDO, corner_radius=0)
        self.area.grid(row=0, column=1, sticky="nsew", padx=32, pady=(26, 14))
        self.area.grid_columnconfigure(0, weight=1)
        self.area.grid_rowconfigure(0, weight=1)

        self.barra = BarraEstado(self, al_ver=self._abrir_ventana)
        self.barra.grid(row=1, column=1, sticky="ew")

        acc = {"cargar": self.cargar, "renombrar": self.renombrar,
               "eliminar": self.eliminar, "ejecutar": self.ejecutar,
               "nuevo": self.nuevo}
        self.p_perfiles = PanelPerfiles(self.area, acc)
        self.p_cred = PanelCredenciales(self.area, self._guardar_cred)
        self.p_org = PanelOrganizacion(self.area, self._guardar_org, self)
        self.p_set = PanelSettings(self.area, self._guardar_settings)
        # El orden debe coincidir con Sidebar.ITEMS
        self._vistas = [self.p_perfiles, self.p_cred, self.p_org, self.p_set]
        for v in self._vistas:
            v.grid(row=0, column=0, sticky="nsew")

        self.p_cred.set(self.datos["credenciales"])
        self.refrescar()
        self.mostrar_vista(0)
        self.after(100, self._bombear)

    # ── Utilidades de datos
    @property
    def perfiles(self) -> list:
        return self.datos["perfiles"]

    def perfil(self, pid: str | None) -> dict | None:
        return next((p for p in self.perfiles if p["id"] == pid), None)

    @property
    def activo(self) -> dict | None:
        return self.perfil(self.datos["activo"])

    def _guardar(self) -> bool:
        try:
            guardar_datos(self.datos)
            return True
        except Exception as e:                        # noqa: BLE001
            messagebox.showerror("Error al guardar", str(e))
            return False


    def obtener_lista_libros(self) -> list:
        """Libros conocidos: los fijos + los de los perfiles + los que vio el bot."""
        libros = list(LIBROS)
        extra = [p["libro"] for p in self.perfiles] + list(leer_catalogo())
        return libros + [l for i, l in enumerate(extra) if l and l not in libros and l not in extra[:i]]

    def obtener_niveles(self, libro: str) -> list:
        """Niveles de un libro: los base + los que vio el bot + los de los perfiles de ese libro."""
        niveles = list(NIVELES_BASE) + list(leer_catalogo().get(libro, {})) \
            + [p["nivel"] for p in self.perfiles if p["libro"] == libro]
        return [n for i, n in enumerate(niveles) if n and n not in niveles[:i]]

    def clases_guardadas(self, libro: str, nivel: str) -> list:
        """Clases asociadas a ese libro y nivel en los perfiles ya creados."""
        clases = [c for p in self.perfiles if p["libro"] == libro and p["nivel"] == nivel
                  for c in p["clases"]]
        return [c for i, c in enumerate(clases) if c not in clases[:i]]

    def obtener_clases_nivel(self, libro: str, nivel: str) -> list:
        """Clases de ese libro y nivel: las que vio el bot en Macmillan + las de los perfiles ya guardados."""
        clases = list(leer_catalogo().get(libro, {}).get(nivel, []))
        for p in self.perfiles:
            if p["libro"] == libro and p["nivel"] == nivel:
                clases += p["clases"]
        return [c for i, c in enumerate(clases) if c and c not in clases[:i]]

    def refrescar(self) -> None:
        act = self.activo
        self.p_perfiles.actualizar(self.perfiles, self.datos["activo"],
                                   self._ejecutando_id)
        self.p_org.set_perfil(act)
        self.p_set.set(act, self.datos["ajustes"])
        self.sidebar.set_activo(act["id"] if act else None)
        self.barra.perfil(f"Perfil activo: {act['nombre_perfil']}  ({act['id']})"
                          if act else "Sin perfil activo")

    # ── Navegacion
    def mostrar_vista(self, idx: int) -> None:
        self.sidebar.marcar(idx)
        self._vistas[idx].tkraise()

    # ── Acciones de perfiles
    def _bloqueado(self) -> bool:
        if self._ejecutando_id:
            messagebox.showinfo("Bot en ejecucion",
                                "Espera a que termine el bot o detenlo.")
            return True
        return False

    def cargar(self, pid: str) -> None:
        if pid != self.datos["activo"] and self._bloqueado():
            return
        self.datos["activo"] = pid
        self._guardar()
        self.refrescar()
        self.barra.estado(f"Perfil cargado: {self.activo['nombre_perfil']}")

    def renombrar(self, pid: str) -> None:
        p = self.perfil(pid)
        if p:
            DlgNombre(self, p["nombre_perfil"],
                      al_ok=lambda n: self._on_rename(pid, n))

    def _on_rename(self, pid: str, nombre: str) -> None:
        p = self.perfil(pid)
        if p:
            p["nombre_perfil"] = nombre
            self._guardar()
            self.refrescar()

    def eliminar(self, pid: str) -> None:
        p = self.perfil(pid)
        if not p or (pid == self._ejecutando_id and self._bloqueado()):
            return
        if not messagebox.askyesno("Eliminar perfil",
                                   f"¿Eliminar el perfil '{p['nombre_perfil']}'?\n"
                                   "Esta accion no se puede deshacer."):
            return
        self.perfiles.remove(p)
        if self.datos["activo"] == pid:
            self.datos["activo"] = self.perfiles[0]["id"] if self.perfiles else None
        self._guardar()
        self.refrescar()
        self.barra.estado(f"Perfil eliminado: {p['nombre_perfil']}", T.WARN)

    def nuevo(self) -> None:
        DlgNuevoPerfil(self, self, al_ok=self._crear)

    def _crear(self, p: dict) -> None:
        while self.perfil(p["id"]):
            p["id"] = nuevo_id()
        self.perfiles.append(p)
        if not self._ejecutando_id:
            self.datos["activo"] = p["id"]
        self._guardar()
        self.refrescar()
        self.barra.estado(f"Perfil creado: {p['nombre_perfil']}  ({p['id']})")

    # ── Guardado de vistas
    def _guardar_cred(self) -> None:
        self.datos["credenciales"] = self.p_cred.get()
        if self._guardar():
            self.barra.estado("Credenciales guardadas")
            messagebox.showinfo("Guardado", "Credenciales guardadas.")

    def _guardar_org(self) -> None:
        p = self.perfil(self.p_org.pid) or self.activo   # el perfil elegido en el panel, este o no activo
        if not p:
            return
        d = self.p_org.get()
        if not d["libro"]:
            messagebox.showwarning("Falta libro", "Elige el libro.")
            return
        if not d["clases"] and not d["todas_clases"]:
            messagebox.showwarning("Sin clases",
                                   "Selecciona al menos una clase o activa 'TODAS las clases'.")
            return
        p.update(d)
        if self._guardar():
            self.refrescar()
            self.barra.estado(f"Perfil actualizado: {p['nombre_perfil']}")
            messagebox.showinfo("Guardado", f"Cambios guardados en el perfil '{p['nombre_perfil']}'.")

    def _guardar_settings(self) -> None:
        p = self.activo
        if p:
            p.update(self.p_set.get_perfil())
        self.datos["ajustes"] = self.p_set.get_ajustes()
        if self._guardar():
            self.refrescar()
            self.barra.estado("Ajustes guardados")
            messagebox.showinfo("Guardado", "Ajustes guardados.")

    # ── Ejecucion del bot
    def ejecutar(self, pid: str) -> None:
        if self._bloqueado():
            return
        p = self.perfil(pid)
        if not p:
            return
        cred = self.datos["credenciales"]
        if not cred.get("usuario") or not cred.get("password"):
            if messagebox.askyesno("Faltan credenciales",
                                   "Configura el usuario y la contrasena de "
                                   "Macmillan.\n¿Ir a Credenciales?"):
                self.mostrar_vista(1)
            return
        if not p["clases"]:
            messagebox.showwarning("Sin clases",
                                   "El perfil no tiene clases. Editalo en "
                                   "Organización.")
            return
        try:
            escribir_config_bot(p, cred, self.datos["ajustes"])
        except Exception as e:                        # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo escribir la "
                                          f"configuracion del bot:\n{e}")
            return

        self._log_buffer.clear()
        self._ultimo_progreso, self._modo_indet = 0.0, False
        self._ejecutando_id = pid
        self._runner = BotRunner(dict(p), dict(cred),
                                 dict(self.datos["ajustes"]), self._cola)
        self._runner.start()
        self.refrescar()
        self.barra.estado(f"⏳ Ejecutando bot: {p['nombre_perfil']}", T.WARN)
        self._abrir_ventana()

    def _abrir_ventana(self) -> None:
        if self._ventana is not None:
            self._ventana.lift()
            return
        p = self.perfil(self._ejecutando_id) or self.activo
        if not p:
            return
        self._ventana = VentanaProgreso(self, p, al_detener=self._detener,
                                        al_cerrar=self._ventana_cerrada)
        for texto, nivel in self._log_buffer:
            self._ventana.log(texto, nivel)
        if self._modo_indet:
            self._ventana.indeterminado()
        else:
            self._ventana.progreso(self._ultimo_progreso)
        self.barra.mostrar_ver(False)

    def _ventana_cerrada(self) -> None:
        self._ventana = None
        self.barra.mostrar_ver(self._ejecutando_id is not None)

    def _detener(self) -> None:
        if self._runner:
            self._runner.detener()
            self.barra.estado("Deteniendo bot…", T.WARN)

    def _bombear(self) -> None:
        """Procesa en el hilo de Tk los eventos que envia el BotRunner."""
        try:
            while True:
                ev = self._cola.get_nowait()
                tipo = ev[0]
                if tipo == "log":
                    _, texto, nivel = ev
                    self._log_buffer.append((texto, nivel))
                    if self._ventana:
                        self._ventana.log(texto, nivel)
                    if nivel in ("ok", "err"):
                        self.barra.estado(texto.split("]  ", 1)[-1],
                                          T.OK if nivel == "ok" else T.ERR)
                elif tipo == "progreso":
                    self._ultimo_progreso = ev[1]
                    if self._ventana:
                        self._ventana.progreso(ev[1])
                elif tipo == "indeterminado":
                    self._modo_indet = True
                    if self._ventana:
                        self._ventana.indeterminado()
                elif tipo == "fin":
                    self._fin(ev[1], ev[2])
        except queue.Empty:
            pass
        self.after(100, self._bombear)

    def _fin(self, ok: bool, msg: str) -> None:
        p = self.perfil(self._ejecutando_id)
        if p:
            p["ultima_ejecucion"] = (f"Ultima ejecucion: "
                                     f"{datetime.now():%d/%m/%Y %H:%M}  ·  "
                                     f"{'OK' if ok else 'Incompleta'}")
            self._guardar()
        self._runner = None
        self._ejecutando_id = None
        self.barra.mostrar_ver(False)
        self.barra.estado(("✅ " if ok else "⚠️ ") + msg,
                          T.OK if ok else T.WARN)
        if self._ventana:
            self._ventana.fin(ok, msg)
        else:
            (messagebox.showinfo if ok else messagebox.showwarning)(
                "Bot Macmillan", msg)
        self.refrescar()

    # ── Integracion con la app unificada
    def hay_proceso_activo(self) -> bool:
        return self._ejecutando_id is not None

    def cerrar(self) -> None:
        """La app unificada la llama al salir (ya confirmo con el usuario)."""
        if self._ejecutando_id:
            self._detener()
        self.p_perfiles.actualizar([], None, None)   # detiene animaciones


if __name__ == "__main__":
    raiz = ctk.CTk()
    raiz.title("Macmillan Education Everywhere - Configurador de Descargas")
    raiz.geometry("1280x720")
    raiz.minsize(1100, 680)
    vista = VistaMacmillan(raiz)
    vista.pack(fill="both", expand=True)

    def _salir():
        if vista.hay_proceso_activo():
            if not messagebox.askyesno("Bot en ejecucion",
                                       "El bot sigue ejecutandose.\n¿Detenerlo y salir?"):
                return
        vista.cerrar()
        raiz.destroy()

    raiz.protocol("WM_DELETE_WINDOW", _salir)
    raiz.mainloop()
