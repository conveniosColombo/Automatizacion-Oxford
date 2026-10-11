"""Herramientas de automatizacion - Centro Colombo Americano.

Una sola aplicacion con tres herramientas (Q10, Macmillan y Oxford). Cada herramienta es un
Frame ("vista") definido en su propio script; aqui solo se arma el menu, el encabezado con el
logo y la navegacion. Las vistas se crean al abrirlas por primera vez y se conservan: volver al
menu NO las cierra (un bot que este corriendo sigue su curso).

Contrato de cada vista (ver VistaQ10, VistaMacmillan, VistaOxford):
    TITULO, SUBTITULO        textos del encabezado
    hay_proceso_activo()     True si hay un bot corriendo
    cerrar()                 limpieza al salir de la aplicacion

Ejecutar:  .venv\\Scripts\\python.exe aplicacion\\main.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk
from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
# Las pantallas de configuracion viven en herramientas/<sistema>/ (con sus perfiles y datos);
# los robots que descargan estan en bots/<sistema>/. Aqui solo se importan las pantallas.
for ruta in (AQUI, RAIZ / "herramientas" / "q10", RAIZ / "herramientas" / "macmillan",
             RAIZ / "herramientas" / "oxford"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

from tema_colombo import ALIADOS, FONDO_ESTRELLAS, LOGO, Marca, tipografia  # noqa: E402

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
TIPO = tipografia()
F = TIPO["F"]


# ------------------------------------------------------------------ herramientas ---
def _cargar_q10():
    from configurar_q10 import VistaQ10
    return VistaQ10


def _cargar_macmillan():
    from app_macmillan import VistaMacmillan
    return VistaMacmillan


def _cargar_oxford():
    from app_oxford import VistaOxford
    return VistaOxford


HERRAMIENTAS = [
    # clave, insignia, nombre, descripcion, cargador de la clase de la vista
    ("q10", "Q10", "Q10 Académico",
     "Arma la lista de informes y filtros y lanza la descarga desde Q10.", _cargar_q10),
    ("macmillan", "MEE", "Macmillan",
     "Perfiles de descarga del progreso por libro, nivel y clase en Macmillan Education Everywhere.",
     _cargar_macmillan),
    ("oxford", "OX", "Oxford",
     "Perfiles y clases para descargar el avance de los estudiantes en Oxford English Hub.",
     _cargar_oxford),
]


def _imagen(ruta: Path, ancho: int) -> ctk.CTkImage:
    img = Image.open(ruta).convert("RGBA")
    alto = round(ancho * img.height / img.width)
    return ctk.CTkImage(light_image=img, size=(ancho, alto))


# ------------------------------------------------------------------------ encabezado ---
class Encabezado(ctk.CTkFrame):
    """Barra superior de las herramientas: logo, nombre de la herramienta y boton Volver."""

    def __init__(self, master, al_volver: Callable[[], None]):
        super().__init__(master, fg_color=Marca.BLANCO, corner_radius=0, height=68)
        self.grid_propagate(False)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(self, text="", image=_imagen(LOGO, 118)).grid(row=0, column=0, padx=(20, 16))
        ctk.CTkFrame(self, fg_color=Marca.BORDE, width=1, corner_radius=0
                     ).grid(row=0, column=1, sticky="ns", pady=16)

        textos = ctk.CTkFrame(self, fg_color="transparent")
        textos.grid(row=0, column=2, sticky="w", padx=16)
        self.titulo = ctk.CTkLabel(textos, text="", font=TIPO["H2"], text_color=Marca.AZUL, anchor="w")
        self.titulo.pack(anchor="w")
        self.subtitulo = ctk.CTkLabel(textos, text="", font=TIPO["AYUDA"],
                                      text_color=Marca.TEXTO_SUAVE, anchor="w")
        self.subtitulo.pack(anchor="w")

        ctk.CTkButton(self, text="←  Volver al menú", font=TIPO["BOTON"], height=38, width=160,
                      corner_radius=Marca.RADIO, fg_color=Marca.BLANCO, hover_color=Marca.AZUL_CLARO,
                      text_color=Marca.AZUL, border_width=2, border_color=Marca.AZUL,
                      command=al_volver).grid(row=0, column=3, padx=20)

    def poner(self, titulo: str, subtitulo: str) -> None:
        self.titulo.configure(text=titulo)
        self.subtitulo.configure(text=subtitulo)


# ----------------------------------------------------------------------------- menu ---
class TarjetaHerramienta(ctk.CTkFrame):
    ANCHO, ALTO = 300, 300

    def __init__(self, master, insignia: str, nombre: str, descripcion: str,
                 al_abrir: Callable[[], None]):
        super().__init__(master, fg_color=Marca.BLANCO, corner_radius=16, border_width=2,
                         border_color=Marca.BORDE, width=self.ANCHO, height=self.ALTO)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self._al_abrir = al_abrir

        franja = ctk.CTkFrame(self, fg_color=Marca.ROJO, height=5, corner_radius=0)
        franja.grid(row=0, column=0, sticky="ew", padx=40)

        chip = ctk.CTkFrame(self, fg_color=Marca.AZUL, width=72, height=72, corner_radius=18)
        chip.grid(row=1, column=0, pady=(22, 10))
        chip.grid_propagate(False)
        ctk.CTkLabel(chip, text=insignia, font=(F, 22 if len(insignia) < 3 else 19, "bold"),
                     text_color=Marca.BLANCO).place(relx=.5, rely=.5, anchor="center")

        ctk.CTkLabel(self, text=nombre, font=(F, 18, "bold"), text_color=Marca.TEXTO
                     ).grid(row=2, column=0)
        ctk.CTkLabel(self, text=descripcion, font=TIPO["AYUDA"], text_color=Marca.TEXTO_SUAVE,
                     wraplength=self.ANCHO - 50, justify="center"
                     ).grid(row=3, column=0, padx=24, pady=(6, 0), sticky="n")
        self.grid_rowconfigure(3, weight=1)

        self.boton = ctk.CTkButton(self, text="Abrir herramienta  →", font=TIPO["BOTON"], height=40,
                                   corner_radius=Marca.RADIO, fg_color=Marca.AZUL,
                                   hover_color=Marca.AZUL_H, text_color=Marca.BLANCO,
                                   command=al_abrir)
        self.boton.grid(row=4, column=0, padx=24, pady=(8, 8), sticky="ew")
        self.estado = ctk.CTkLabel(self, text=" ", font=TIPO["MINI"], text_color=Marca.OK)
        self.estado.grid(row=5, column=0, pady=(0, 10))

        for w in (self, chip, franja):
            w.bind("<Button-1>", lambda _e: al_abrir())
            w.bind("<Enter>", self._entrar)
            w.bind("<Leave>", self._salir)
        for w in self.winfo_children():
            if isinstance(w, ctk.CTkLabel):
                w.bind("<Button-1>", lambda _e: al_abrir())
                w.bind("<Enter>", self._entrar)
                w.bind("<Leave>", self._salir)
        self.boton.bind("<Enter>", self._entrar, add="+")

    def _entrar(self, _e=None):
        self.configure(border_color=Marca.AZUL)

    def _salir(self, _e=None):
        # evita parpadeo: solo se quita el resalte si el cursor salio de la tarjeta
        x, y = self.winfo_pointerxy()
        if self.winfo_containing(x, y) is None or not str(self.winfo_containing(x, y)).startswith(str(self)):
            self.configure(border_color=Marca.BORDE)

    def marcar_en_ejecucion(self, activo: bool) -> None:
        self.estado.configure(text="● Bot en ejecución" if activo else " ")


class Menu(ctk.CTkFrame):
    """Pantalla de inicio: fondo de estrellas de la marca, logo y las tres herramientas."""

    def __init__(self, master, al_abrir: Callable[[str], None]):
        super().__init__(master, fg_color=Marca.FONDO, corner_radius=0)
        self._fondo_orig = Image.open(FONDO_ESTRELLAS).convert("RGB")
        self._fondo = ctk.CTkLabel(self, text="", fg_color=Marca.FONDO)
        self._fondo.place(x=0, y=0, relwidth=1, relheight=1)
        self._tam_fondo: tuple[int, int] | None = None
        self._pendiente = None
        self.bind("<Configure>", self._al_redimensionar)

        centro = ctk.CTkFrame(self, fg_color="transparent")
        centro.place(relx=.5, rely=.47, anchor="center")

        ctk.CTkLabel(centro, text="", image=_imagen(LOGO, 300), fg_color="transparent"
                     ).pack(pady=(0, 14))
        ctk.CTkLabel(centro, text="Herramientas de automatización", font=(F, 26, "bold"),
                     text_color=Marca.AZUL, fg_color="transparent").pack()
        ctk.CTkLabel(centro, text="Elige con qué sistema quieres trabajar", font=(F, 14),
                     text_color=Marca.TEXTO, fg_color="transparent").pack(pady=(2, 26))

        fila = ctk.CTkFrame(centro, fg_color="transparent")
        fila.pack()
        self.tarjetas: dict[str, TarjetaHerramienta] = {}
        for i, (clave, insignia, nombre, desc, _) in enumerate(HERRAMIENTAS):
            t = TarjetaHerramienta(fila, insignia, nombre, desc, lambda k=clave: al_abrir(k))
            t.grid(row=0, column=i, padx=14)
            self.tarjetas[clave] = t

        pie = ctk.CTkFrame(self, fg_color=Marca.BLANCO, corner_radius=12)
        pie.place(relx=.5, rely=.97, anchor="s")
        ctk.CTkLabel(pie, text="", image=_imagen(ALIADOS, 400)).pack(padx=14, pady=6)

    def _al_redimensionar(self, e) -> None:
        if e.widget is not self:
            return
        if self._pendiente:
            self.after_cancel(self._pendiente)
        self._pendiente = self.after(60, self._pintar_fondo)

    def _pintar_fondo(self) -> None:
        self._pendiente = None
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50 or (w, h) == self._tam_fondo:
            return
        self._tam_fondo = (w, h)
        img = self._fondo_orig
        escala = max(w / img.width, h / img.height)          # "cover": llena y recorta
        nuevo = img.resize((max(1, round(img.width * escala)), max(1, round(img.height * escala))),
                           Image.BILINEAR)
        izq, arr = (nuevo.width - w) // 2, (nuevo.height - h) // 2
        nuevo = nuevo.crop((izq, arr, izq + w, arr + h))
        self._img_ref = ctk.CTkImage(light_image=nuevo, size=(w, h))   # referencia viva
        self._fondo.configure(image=self._img_ref)


# ------------------------------------------------------------------------ aplicacion ---
class AplicacionColombo(ctk.CTk):
    def __init__(self):
        super().__init__()
        try:
            self.tk.call("encoding", "system", "utf-8")
        except Exception:                                   # noqa: BLE001
            pass
        self.title("Herramientas de automatización - Centro Colombo Americano")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(fg_color=Marca.FONDO)
        self._poner_icono()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.encabezado = Encabezado(self, al_volver=self.mostrar_menu)
        self.encabezado.grid(row=0, column=0, sticky="ew")
        # Linea de marca bajo el encabezado: azul con un tramo rojo
        linea = ctk.CTkFrame(self, fg_color=Marca.AZUL, height=4, corner_radius=0)
        linea.grid(row=1, column=0, sticky="ew")
        ctk.CTkFrame(linea, fg_color=Marca.ROJO, width=140, height=4, corner_radius=0
                     ).pack(side="right")
        self._cabecera = (self.encabezado, linea)

        self.contenedor = ctk.CTkFrame(self, fg_color=Marca.FONDO, corner_radius=0)
        self.contenedor.grid(row=2, column=0, sticky="nsew")
        self.contenedor.grid_columnconfigure(0, weight=1)
        self.contenedor.grid_rowconfigure(0, weight=1)

        self.menu = Menu(self.contenedor, al_abrir=self.abrir)
        self.menu.grid(row=0, column=0, sticky="nsew")
        self.vistas: dict[str, ctk.CTkFrame] = {}
        self._actual: str | None = None

        self.mostrar_menu()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.after(1000, self._vigilar_bots)

    def _poner_icono(self) -> None:
        """Icono de la ventana a partir del logo (CTk pone el suyo ~200 ms despues de abrir)."""
        try:
            ico = AQUI / "recursos" / "icono.ico"
            if not ico.exists():
                logo = Image.open(LOGO).convert("RGBA")
                lado = max(logo.size)
                lienzo = Image.new("RGBA", (lado, lado), (255, 255, 255, 0))
                lienzo.paste(logo, (0, (lado - logo.height) // 2))
                lienzo.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            self.after(300, lambda: self.iconbitmap(str(ico)))
        except Exception:                                   # noqa: BLE001
            pass

    # ---------------------------------------------------------------- navegacion ---
    def mostrar_menu(self) -> None:
        for v in self.vistas.values():
            v.grid_remove()
        for w in self._cabecera:
            w.grid_remove()
        self.menu.grid()
        self._actual = None
        self.title("Herramientas de automatización - Centro Colombo Americano")

    def abrir(self, clave: str) -> None:
        if clave not in self.vistas:
            herramienta = next(h for h in HERRAMIENTAS if h[0] == clave)
            try:
                clase = herramienta[4]()
                self.config(cursor="watch")
                self.update_idletasks()
                vista = clase(self.contenedor)
            except Exception as e:                          # noqa: BLE001
                traceback.print_exc()
                messagebox.showerror(
                    "No se pudo abrir la herramienta",
                    f"{herramienta[2]} no se pudo cargar:\n\n{type(e).__name__}: {e}", parent=self)
                return
            finally:
                self.config(cursor="")
            vista.grid(row=0, column=0, sticky="nsew")
            self.vistas[clave] = vista
        self.menu.grid_remove()
        for k, v in self.vistas.items():
            if k == clave:
                v.grid()
            else:
                v.grid_remove()
        vista = self.vistas[clave]
        self.encabezado.poner(vista.TITULO, vista.SUBTITULO)
        self.encabezado.grid()
        self._cabecera[1].grid()
        self._actual = clave
        self.title(f"{vista.TITULO} - Centro Colombo Americano")

    # ------------------------------------------------------------------- estado ---
    def _vigilar_bots(self) -> None:
        for clave, tarjeta in self.menu.tarjetas.items():
            vista = self.vistas.get(clave)
            tarjeta.marcar_en_ejecucion(bool(vista and vista.hay_proceso_activo()))
        self.after(1000, self._vigilar_bots)

    def _al_cerrar(self) -> None:
        activos = [h[2] for h in HERRAMIENTAS
                   if h[0] in self.vistas and self.vistas[h[0]].hay_proceso_activo()]
        if activos and not messagebox.askyesno(
                "Bot en ejecución",
                "Hay un bot en ejecución (" + ", ".join(activos) + ").\n"
                "Si cierras la aplicación se detendrá.\n\n¿Detenerlo y salir?", parent=self):
            return
        for v in self.vistas.values():
            try:
                v.cerrar()
            except Exception:                               # noqa: BLE001
                traceback.print_exc()
        self.destroy()


if __name__ == "__main__":
    AplicacionColombo().mainloop()
