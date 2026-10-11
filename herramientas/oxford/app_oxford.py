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
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog, messagebox
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
                    figuras: str, mostrar: str, ruta_descarga: str) -> None:
    texto_ruta = f"Ruta Descargas : {ruta_descarga}\n" if ruta_descarga else ""
    CONFIG_TXT.write_text(
        f"# ID del convenio en My Organizations\n"
        f"ID : {id_org}\n\n"
        f"# Clases separadas por coma\n"
        f"Clases : {', '.join(clases)}\n\n"
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


# ─────────────────────────────────────────── Perfiles JSON
PERFIL_VACIO = {
    "nombre": "Nuevo perfil",
    "id_org": "",
    "clases": [],
    "scores": "Show best attempt",
    "show_figures_as": "Percentages",
    "show_scores_for": "All activities",
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
            btns.grid_columnconfigure((0, 1, 2), weight=1, uniform="b")

            ctk.CTkButton(btns, text="Cargar", font=T.BTN, height=30, width=60, fg_color=T.ACC if es_activo else T.PRIM, hover_color=T.ACC_H if es_activo else T.PRIM_H, text_color="white" if es_activo else "white", corner_radius=T.R, command=lambda i=idx: self.al_cargar(i)).grid(row=0, column=0, sticky="ew", padx=(0, 4))
            ctk.CTkButton(btns, text="Renombrar", font=T.BTN, height=30, width=60, fg_color=T.SUP, hover_color=T.FONDO, text_color=T.TEXTO, border_width=1, border_color=T.BORDE, corner_radius=T.R, command=lambda i=idx: self.al_renombrar(i)).grid(row=0, column=1, sticky="ew", padx=4)
            ctk.CTkButton(btns, text="Eliminar", font=T.BTN, height=30, width=60, fg_color=T.ERR_BG, hover_color=T.ERR_BG_H, text_color=T.ERR, corner_radius=T.R, command=lambda i=idx: self.al_del(i)).grid(row=0, column=2, sticky="ew", padx=(4, 0))

            if es_activo:
                ctk.CTkButton(btns, text="EJECUTAR BOT", font=T.BTNG, height=34, fg_color=T.OK, hover_color="#166534", text_color="white", corner_radius=T.R, command=self.al_ejecutar).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))

class PanelSettings(PBase):
    SCORES  = ["Show best attempt", "Show latest attempt"]
    FIGS    = ["Percentages", "Fractions"]
    SHOW    = ["All activities", "Completed activities"]

    def __init__(self, master, al_cambiar: Callable):
        super().__init__(master, "Progress Settings",
                         "Parametros de la ventana Progress settings en cada clase.")
        card = ctk.CTkFrame(self.cont, fg_color=T.SUP,
                             corner_radius=T.R,
                             border_width=1, border_color=T.BORDE)
        card.grid(row=0, column=0, sticky="ew")
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

        # Ruta Descarga
        ctk.CTkLabel(inner, text="Ruta de Descargas", font=T.ETQ, text_color=T.TEXTO, anchor="w").grid(row=9, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="Carpeta donde se guardaran los Excels descargados.", font=T.AYD, text_color=T.SUAVE, anchor="w").grid(row=10, column=0, sticky="ew")
        
        box_ruta = ctk.CTkFrame(inner, fg_color="transparent")
        box_ruta.grid(row=11, column=0, sticky="ew", pady=(4, 0))
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
            "ruta_descarga":   self.var_ruta.get(),
        }

    def set(self, d: dict):
        sc = d.get("scores", self.SCORES[0])
        self.var_sc.set(sc if sc in self.SCORES else self.SCORES[0])
        fi = d.get("show_figures_as", self.FIGS[0])
        self.seg_fig.set(fi if fi in self.FIGS else self.FIGS[0])
        sh = d.get("show_scores_for", self.SHOW[0])
        self.seg_show.set(sh if sh in self.SHOW else self.SHOW[0])
        self.var_ruta.set(d.get("ruta_descarga", ""))


# ───────────────────────────────────────────── Sidebar
class Sidebar(ctk.CTkFrame):
    SECS = [("H", "Perfiles"), ("C", "Credenciales"),
            ("O", "Organizacion"), ("S", "Settings")]

    def __init__(self, master, al_cambiar: Callable):
        super().__init__(master, fg_color=T.PRIM_OSC, width=72, corner_radius=0)
        self.grid_propagate(False)
        self.grid_rowconfigure(1, weight=1)
        self._al_cambiar = al_cambiar
        self._btns: list[ctk.CTkButton] = []

        # Marca de la herramienta (la estrella del logo + nombre)
        logo = ctk.CTkFrame(self, fg_color="transparent")
        logo.grid(row=0, column=0, pady=(14, 8))
        ctk.CTkLabel(logo, text="★", font=(T.F, 24, "bold"),
                     text_color="white").pack()
        ctk.CTkLabel(logo, text="Oxford", font=(T.F, 9, "bold"),
                     text_color=T.SB_TXT).pack()

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=1, column=0)
        ICONOS = ["🏠", "🔐", "🏛", "⚙"]
        for i, (ico, lbl) in enumerate(zip(ICONOS, [s[1] for s in self.SECS])):
            btn = ctk.CTkButton(
                nav, text=ico, width=48, height=48,
                font=(T.F, 20),
                fg_color="transparent", hover_color=T.PRIM,
                text_color="white", corner_radius=10,
                command=lambda idx=i: self._sel(idx))
            btn.pack(pady=3)
            self._btns.append(btn)
            ctk.CTkLabel(nav, text=lbl, font=(T.F, 9),
                         text_color=T.SB_TXT).pack(pady=(0, 5))
        self._mark(0)

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
                 al_ejecutar:  Callable,
                 al_renombrar: Callable):
        super().__init__(master, fg_color=T.SUP, height=62,
                         corner_radius=0,
                         border_width=1, border_color=T.BORDE)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(self, fg_color=T.PRIM, width=6, corner_radius=0
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
        ctk.CTkButton(btns, text="EJECUTAR BOT (Oxford)",
                      font=T.BTNG, height=36,
                      fg_color=T.PRIM, hover_color=T.PRIM_H,
                      text_color="white", corner_radius=T.R,
                      command=al_ejecutar
                      ).pack(side="left")

    def update(self, nombre: str, n: int):
        self.lbl_p.configure(text=f"Perfil activo: {nombre}")
        self.lbl_c.configure(text=f"{n} clase{'s' if n != 1 else ''}  |  "
                                   f"Guarda antes de ejecutar.")


# ─────────────────────────────────────── Ventana de progreso del bot
class VentanaProgreso(ctk.CTkToplevel):
    """Ventana que muestra el log del bot en tiempo real."""

    def __init__(self, master, perfil: str, n_clases: str):
        super().__init__(master)
        self.title("Progreso del bot - Oxford English Hub")
        self.geometry("700x480")
        self.minsize(600, 360)
        self.configure(fg_color=T.FONDO)
        self.resizable(True, True)
        self._proceso = None
        self._corriendo = False

        # Cabecera
        cab = ctk.CTkFrame(self, fg_color=T.PRIM, corner_radius=0)
        cab.pack(fill="x")
        ctk.CTkLabel(cab, text="▶  Ejecutando bot Oxford",
                     font=T.TIT, text_color="white", anchor="w"
                     ).pack(side="left", padx=16, pady=10)
        self.lbl_info = ctk.CTkLabel(cab,
                     text=f"Perfil: {perfil}  |  Clases: {n_clases}",
                     font=T.AYD, text_color=T.SB_TXT, anchor="e")
        self.lbl_info.pack(side="right", padx=16)

        # Texto de log
        self.txt = ctk.CTkTextbox(
            self, fg_color=T.SUP, border_color=T.BORDE, border_width=1,
            font=("Consolas", 11), wrap="word", corner_radius=T.R)
        self.txt.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        self.txt.configure(state="disabled")

        # Barra inferior
        bar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        bar.pack(fill="x", padx=12, pady=8)
        bar.grid_columnconfigure(0, weight=1)
        self.lbl_estado = ctk.CTkLabel(bar, text="⏳ Iniciando...",
                                        font=T.NRM, text_color=T.SUAVE, anchor="w")
        self.lbl_estado.grid(row=0, column=0, sticky="w")
        self.btn_cerrar = ctk.CTkButton(bar, text="Cerrar",
                                         font=T.BTN, height=34, width=100,
                                         fg_color=T.SUP, hover_color=T.FONDO,
                                         text_color=T.TEXTO, border_width=1,
                                         border_color=T.BORDE, corner_radius=T.R,
                                         command=self._cerrar, state="disabled")
        self.btn_cerrar.grid(row=0, column=1, padx=(8, 0))
        self.btn_detener = ctk.CTkButton(bar, text="Detener bot",
                                          font=T.BTN, height=34, width=120,
                                          fg_color=T.ERR, hover_color=T.ERR_H,
                                          text_color="white", corner_radius=T.R,
                                          command=self._detener)
        self.btn_detener.grid(row=0, column=2, padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.grab_set()

    def iniciar(self, cmd: list, cwd: str):
        """Lanza el proceso y empieza a leer stdout."""
        import subprocess, threading
        self._corriendo = True
        self._proceso = subprocess.Popen(
            cmd, cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW)
        threading.Thread(target=self._leer, daemon=True).start()

    def _leer(self):
        for linea in self._proceso.stdout:
            linea = linea.rstrip()
            self._log(linea)
        self._proceso.wait()
        rc = self._proceso.returncode
        if rc == 0:
            self._set_estado("✅ Bot finalizado correctamente.", T.OK)
        else:
            self._set_estado(f"⚠️ Bot terminó con código {rc}. Revisa el log.", T.WARN)
        self._corriendo = False
        self.after(0, lambda: self.btn_cerrar.configure(state="normal"))
        self.after(0, lambda: self.btn_detener.configure(state="disabled"))

    def _log(self, texto: str):
        def _do():
            self.txt.configure(state="normal")
            # Colorear errores y exitos
            tag = None
            t_lower = texto.lower()
            if "fallo" in t_lower or "error" in t_lower or "exception" in t_lower:
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
            self.txt.see("end")
            self.txt.configure(state="disabled")
        self.after(0, _do)

    def _set_estado(self, msg: str, color: str):
        self.after(0, lambda: self.lbl_estado.configure(
            text=msg, text_color=color))

    def _detener(self):
        if self._proceso and self._corriendo:
            self._proceso.terminate()
            self._log(">>> Bot detenido por el usuario.")

    def _cerrar(self):
        if self._corriendo:
            if not messagebox.askyesno(
                    "Bot activo",
                    "El bot todavia está corriendo.\n¿Deseas detenerlo y cerrar?",
                    parent=self):
                return
            self._detener()
        self.grab_release()
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

        # 1. Barra inferior (siempre visible en el fondo, ocupa todo el ancho)
        self.barra = BarraInf(self,
                               al_guardar=self._guardar,
                               al_ejecutar=self._ejecutar,
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

        self._panels = [self.pp, self.pc, self.po, self.ps]
        for p in self._panels:
            p.grid(row=0, column=0, sticky="nsew")

        self._mostrar(0)
        if self._activo is not None:
            self._cargar(self._activo)

    # ── Integracion con la app unificada
    def hay_proceso_activo(self) -> bool:
        return False        # el bot corre en una ventana modal de progreso; no se puede salir antes

    def cerrar(self) -> None:
        pass

    # ── Navegacion
    def _cambiar(self, idx: int):
        self._mostrar(idx)

    def _mostrar(self, idx: int):
        self._panels[idx].tkraise()
        if idx == 0:
            self.pp.actualizar(self._perfiles, self._activo)

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
            escribir_config(p["id_org"], clases_guardar, p["scores"], p["show_figures_as"], p["show_scores_for"], p.get("ruta_descarga", ""))
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
               f"Clases: {n_clases}")
        if not messagebox.askyesno("Ejecutar bot?",
                                    f"{det}\n\n"
                                    "Se abrira una ventana con el progreso en tiempo real."):
            return
        try:
            cmd = [str(BOT_EXE)] if es_exe else [py, str(BOT_SCRIPT)]
            if todas:
                cmd.append("--todas")
            ven = VentanaProgreso(self, p["nombre"], n_clases)
            ven.iniciar(cmd, str(ROOT))
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
