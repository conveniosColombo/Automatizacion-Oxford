"""Configurar Q10 - formulario de escritorio para armar las descargas del bot.

Reemplaza el llenado manual de la hoja Q10 de 'Bot Descargas.xlsx' por un formulario guiado.
El catalogo de informes (que filtros tiene cada uno, en que orden y con que opciones) se lee y
se guarda en 'catalogo_q10.json' (core/catalogo.py); "Guardar configuracion" escribe la hoja Q10
de la planilla sin tocar Accesos ni las otras hojas (core/planilla.py); "Ejecutar bot" guarda y
lanza 'bot.py Q10' en su propia consola, igual que el .bat de siempre.

Solo usa customtkinter, tkinter y la libreria estandar. Python 3.13 + Windows 11.
"""
from __future__ import annotations

import re
import subprocess
import sys
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

import customtkinter as ctk

# herramientas/q10/configurar_q10.py -> raiz del proyecto. El motor (core/, sistemas/, bot.py)
# vive en bots/q10/ y hace falta en sys.path para "from core import ..."
RAIZ = Path(__file__).resolve().parents[2]
MOTOR_Q10 = RAIZ / "bots" / "q10"
sys.path.insert(0, str(MOTOR_Q10))

from core import archivos, catalogo as cat, planilla as planilla_excel  # noqa: E402
from core.catalogo import FiltroDef, InformeDef  # noqa: E402

# La identidad visual vive en app_colombo/tema_colombo.py (compartida con Macmillan y Oxford)
_APP_COLOMBO = RAIZ / "aplicacion"
if str(_APP_COLOMBO) not in sys.path:
    sys.path.insert(0, str(_APP_COLOMBO))
from tema_colombo import Marca, tipografia  # noqa: E402

_TIPO = tipografia()

ctk.set_appearance_mode("light")

# --------------------------------------------------------------------------- tema ---
class Tema:
    """Identidad Colombo Americano (valores en tema_colombo.py)."""
    PRIMARIO = Marca.AZUL
    PRIMARIO_HOVER = Marca.AZUL_H
    ACENTO = Marca.ROJO
    SUPERFICIE = Marca.BLANCO
    FONDO = Marca.FONDO
    TEXTO = Marca.TEXTO
    TEXTO_SUAVE = Marca.TEXTO_SUAVE
    BORDE = Marca.BORDE
    EXITO = Marca.OK
    EXITO_FONDO = Marca.OK_FONDO
    ADVERTENCIA = Marca.AVISO
    ADVERTENCIA_FONDO = Marca.AVISO_FONDO
    ERROR = Marca.ERROR
    ERROR_HOVER = Marca.ROJO_H
    ERROR_FONDO = Marca.ERROR_FONDO
    DESHABILITADO = Marca.DESHABILITADO
    DESHABILITADO_FONDO = Marca.FONDO
    SIDEBAR = Marca.AZUL_OSC
    SIDEBAR_HOVER = Marca.AZUL

    FUENTE = _TIPO["F"]
    TITULO = (FUENTE, 18, "bold")
    SUBTITULO = _TIPO["SUBTITULO"]
    SECCION = _TIPO["SECCION"]
    ETIQUETA = _TIPO["ETIQUETA"]
    TEXTO_NORMAL = _TIPO["NORMAL"]
    AYUDA = _TIPO["AYUDA"]
    BOTON = _TIPO["BOTON"]
    BOTON_GRANDE = _TIPO["BOTON_G"]

    RADIO = Marca.RADIO
    ESPACIO = 8


def normalizar(texto: str) -> str:
    """Para buscar informes sin importar tildes ni mayusculas."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^\w\s]", " ", sin_tildes).lower().split())


# --------------------------------------------------------------- controles base ---
class BaseFiltroControl(ctk.CTkFrame, ABC):
    """Interfaz comun de todos los controles de filtro.

    El formulario dinamico solo conoce estos cinco metodos: valor(), limpiar(),
    poner_opciones(lista), habilitar() y deshabilitar(). Asi puede tratar cualquier tipo
    de filtro sin importar cual sea, y agregar un tipo nuevo no toca el resto del codigo.
    """

    def __init__(self, master, filtro: FiltroDef, numero: int,
                al_cambiar: Callable[[str], None] | None = None):
        super().__init__(master, fg_color="transparent")
        self.filtro = filtro
        self.al_cambiar = al_cambiar
        self.grid_columnconfigure(0, weight=1)
        self._habilitado = filtro.depende_de is None
        self._construir_encabezado(numero)
        self._widget = self._construir_control()
        if not self._habilitado:
            self.deshabilitar()

    def _construir_encabezado(self, numero: int):
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        marca = " *" if self.filtro.obligatorio else ""
        texto = f"{numero}. {self.filtro.nombre}{marca}"
        color = Tema.ERROR if self.filtro.obligatorio else Tema.TEXTO
        self.etiqueta = ctk.CTkLabel(fila, text=texto, font=Tema.ETIQUETA,
                                     text_color=color if self.filtro.obligatorio else Tema.TEXTO,
                                     anchor="w")
        self.etiqueta.pack(side="left")
        if self.filtro.obligatorio:
            ctk.CTkLabel(fila, text="Obligatorio", font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE,
                        fg_color=Tema.FONDO, corner_radius=4).pack(side="left", padx=(6, 0), ipadx=4)
        if self.filtro.ayuda:
            ctk.CTkLabel(self, text=self.filtro.ayuda, font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE,
                        anchor="w", justify="left", wraplength=320).grid(
                row=2, column=0, sticky="ew", pady=(2, 0))

    def _notificar_cambio(self):
        if self.al_cambiar:
            self.al_cambiar(self.filtro.nombre)

    # ------------------------------------------------------------ contrato comun ---
    @abstractmethod
    def _construir_control(self):
        """Crea el widget (fila 1) y lo devuelve. Debe llamar a self._notificar_cambio()."""

    @abstractmethod
    def valor(self) -> str:
        """Lo que se le pasa al bot: '' si esta vacio."""

    @abstractmethod
    def limpiar(self):
        ...

    @abstractmethod
    def poner_opciones(self, opciones: list[str]):
        ...

    def habilitar(self):
        self._habilitado = True
        self.etiqueta.configure(text_color=Tema.ERROR if self.filtro.obligatorio else Tema.TEXTO)
        self._cambiar_estado("normal")

    def deshabilitar(self):
        self._habilitado = False
        self.limpiar()
        self.etiqueta.configure(text_color=Tema.DESHABILITADO)
        self._cambiar_estado("disabled")

    def _cambiar_estado(self, estado: str):
        try:
            self._widget.configure(state=estado)
        except Exception:
            pass

    def valido(self) -> bool:
        return (not self.filtro.obligatorio) or bool(self.valor())


class ControlLista(BaseFiltroControl):
    """Lista desplegable (CTkComboBox), pero editable: las opciones son una ayuda, no una
    camisa de fuerza. El usuario puede escoger de la lista O escribir el valor el mismo
    (por ejemplo, cuando ya sabe el nombre exacto y no quiere esperar a que cargue la lista)."""

    def _construir_control(self):
        opciones = self.filtro.opciones or []
        self.variable = ctk.StringVar(value="")
        widget = ctk.CTkComboBox(
            self, values=opciones, variable=self.variable,
            fg_color=Tema.SUPERFICIE, border_color=Tema.BORDE, button_color=Tema.PRIMARIO,
            button_hover_color=Tema.PRIMARIO_HOVER, dropdown_hover_color=Tema.FONDO,
            command=lambda _=None: self._notificar_cambio())
        # Si solo hay UNA opcion guardada (como un filtro ya parametrizado con su valor de
        # siempre), se deja puesta: el formulario abre listo para usar, no vacio.
        widget.set(opciones[0] if len(opciones) == 1 else "")
        # Tambien avisar cuando el usuario ESCRIBE (no solo cuando escoge de la lista). El texto
        # lo recibe el Entry INTERNO del combobox, no el widget contenedor: hay que atarlo ahi.
        widget._entry.bind("<KeyRelease>", lambda _e: self._notificar_cambio())
        widget.grid(row=1, column=0, sticky="ew")
        return widget

    def valor(self) -> str:
        return self.variable.get().strip()

    def limpiar(self):
        self._widget.set("")

    def poner_opciones(self, opciones: list[str]):
        self._widget.configure(values=opciones)
        self.limpiar()


class ControlVarios(BaseFiltroControl):
    """'Todos' o varios valores especificos: un reporte por cada uno.

    Avisa ANTES de ejecutar cuantos reportes va a generar la seleccion actual, para que
    no sea una sorpresa despues de darle a "Ejecutar bot".
    """

    def _construir_control(self):
        self._opciones: list[str] = list(self.filtro.opciones)
        self._casillas: dict[str, ctk.CTkCheckBox] = {}
        self._actualizando = False

        contenedor = ctk.CTkFrame(self, fg_color=Tema.FONDO, corner_radius=Tema.RADIO)
        contenedor.grid(row=1, column=0, sticky="ew")
        contenedor.grid_columnconfigure(0, weight=1)

        self.var_todos = ctk.BooleanVar(value=False)
        self.check_todos = ctk.CTkCheckBox(
            contenedor, text="Todos", variable=self.var_todos, font=Tema.ETIQUETA,
            fg_color=Tema.PRIMARIO, hover_color=Tema.PRIMARIO_HOVER,
            command=self._marco_todos)
        self.check_todos.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        # Para cuando son varios cursos especificos (no Todos) y son demasiados para marcar
        # uno por uno a mano: se sube un Excel con la lista y la app marca esos.
        self.boton_subir = ctk.CTkButton(
            contenedor, text="📁 Subir listado (Excel)", font=Tema.AYUDA, height=24,
            fg_color=Tema.SUPERFICIE, hover_color=Tema.FONDO, text_color=Tema.PRIMARIO,
            border_width=1, border_color=Tema.BORDE, corner_radius=6,
            command=self._subir_excel)
        self.boton_subir.grid(row=0, column=1, sticky="e", padx=(0, 10), pady=(8, 4))

        self.lista = ctk.CTkScrollableFrame(contenedor, fg_color="transparent", height=90)
        self.lista.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 4))
        self.lista.grid_columnconfigure(0, weight=1)

        self.aviso = ctk.CTkLabel(contenedor, text="", font=Tema.AYUDA, anchor="w",
                                   corner_radius=4, wraplength=400, justify="left")
        self.aviso.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))

        self._dibujar_casillas()
        return contenedor

    def _dibujar_casillas(self):
        for casilla in self._casillas.values():
            casilla.destroy()
        self._casillas.clear()
        for fila, opcion in enumerate(self._opciones):
            var = ctk.BooleanVar(value=False)
            casilla = ctk.CTkCheckBox(
                self.lista, text=opcion, variable=var, font=Tema.TEXTO_NORMAL,
                fg_color=Tema.PRIMARIO, hover_color=Tema.PRIMARIO_HOVER,
                command=self._marco_individual)
            casilla.grid(row=fila, column=0, sticky="w", pady=2)
            casilla.variable = var
            self._casillas[opcion] = casilla
        self._actualizar_aviso()

    def _marco_todos(self):
        if self.var_todos.get():
            self._actualizando = True
            for casilla in self._casillas.values():
                casilla.variable.set(False)
                casilla.configure(state="disabled")
            self._actualizando = False
        else:
            for casilla in self._casillas.values():
                casilla.configure(state="normal")
        self._actualizar_aviso()
        self._notificar_cambio()

    def _marco_individual(self):
        if self._actualizando:
            return
        self._actualizar_aviso()
        self._notificar_cambio()

    def _seleccionados(self) -> list[str]:
        return [texto for texto, casilla in self._casillas.items() if casilla.variable.get()]

    ENCABEZADOS = {"curso", "cursos", "codigo", "codigo curso", "nombre", "course", "id"}

    @classmethod
    def _leer_primera_columna(cls, ruta: str) -> list[str]:
        """La lista de cursos de un Excel: uno por celda no vacia de la primera columna.

        Si el archivo tiene una tabla de Excel (como la "Plantilla cursos.xlsx"), se lee desde
        justo DEBAJO de su encabezado: asi un titulo o un texto de instrucciones que haya
        arriba de la tabla nunca se confunde con un curso. Sin tabla (un Excel cualquiera
        armado a mano), se lee toda la columna y se adivina el encabezado por su nombre.
        """
        from openpyxl import load_workbook
        from openpyxl.utils import range_boundaries

        libro = load_workbook(ruta, data_only=True)
        try:
            hoja, fila_inicio = libro.active, 1
            for candidata in libro.worksheets:
                tabla = next(iter(candidata.tables.values()), None)
                if tabla is not None:
                    _, fila_titulo, _, _ = range_boundaries(tabla.ref)
                    hoja, fila_inicio = candidata, fila_titulo + 1
                    break

            valores = []
            for fila in hoja.iter_rows(min_row=fila_inicio, min_col=1, max_col=1, values_only=True):
                celda = fila[0] if fila else None
                texto = str(celda).strip() if celda is not None else ""
                if texto:
                    valores.append(texto)
        finally:
            libro.close()

        if fila_inicio == 1 and valores and normalizar(valores[0]) in cls.ENCABEZADOS:
            valores = valores[1:]      # sin tabla: se adivina el encabezado por el texto
        return valores

    def _subir_excel(self):
        """Lee la primera columna de un Excel y deja marcados EXACTAMENTE esos cursos.

        Los que no estaban en la lista se agregan como casilla nueva (por ejemplo, un curso
        que Q10 tiene pero que todavia no se habia escrito en 'Opciones'). Nunca marca "Todos".
        """
        from tkinter import filedialog

        ruta = filedialog.askopenfilename(
            title="Escoja el Excel con el listado de cursos",
            filetypes=[("Excel", "*.xlsx *.xlsm"), ("Todos los archivos", "*.*")])
        if not ruta:
            return

        try:
            valores = self._leer_primera_columna(ruta)
        except Exception as error:
            self.aviso.configure(text=f"No pude leer ese Excel: {error}",
                                 text_color=Tema.ERROR, fg_color=Tema.ERROR_FONDO)
            return

        # Sin duplicados, pero respetando el orden en que aparecen en el Excel
        vistos, cursos = set(), []
        for valor in valores:
            clave = normalizar(valor)
            if clave and clave not in vistos:
                vistos.add(clave)
                cursos.append(valor)

        if not cursos:
            self.aviso.configure(text="Ese Excel no tiene ningun curso en la primera columna.",
                                 text_color=Tema.ERROR, fg_color=Tema.ERROR_FONDO)
            return

        nuevos = [c for c in cursos if normalizar(c) not in {normalizar(o) for o in self._opciones}]
        if nuevos:
            self._opciones.extend(nuevos)
            self._dibujar_casillas()          # reconstruye las casillas con las opciones nuevas

        self._actualizando = True
        self.var_todos.set(False)
        deseados = {normalizar(c) for c in cursos}
        for texto, casilla in self._casillas.items():
            casilla.configure(state="normal")
            casilla.variable.set(normalizar(texto) in deseados)
        self._actualizando = False

        self._actualizar_aviso()
        self.aviso.configure(text=f"Se cargaron {len(cursos)} curso(s) desde el Excel "
                                  f"({len(nuevos)} nuevo(s) en la lista).",
                             text_color=Tema.EXITO, fg_color=Tema.EXITO_FONDO)
        self._notificar_cambio()

    def _actualizar_aviso(self):
        if self.var_todos.get():
            total = len(self._opciones)
            if total:
                texto = f"Se generará un reporte por cada uno de los {total} cursos."
            else:
                # No hay lista cargada (por ejemplo, un informe parametrizado a mano): igual
                # se puede usar "Todos", solo que el bot no sabe de antemano cuantos va a bajar.
                texto = 'Se usará "Todos" (no se sabe de antemano cuántos cursos trae).'
            color, fondo = Tema.ADVERTENCIA, Tema.ADVERTENCIA_FONDO
        else:
            total = len(self._seleccionados())
            if total == 0:
                texto = "Seleccione al menos un curso, o marque \"Todos\"."
                color, fondo = Tema.TEXTO_SUAVE, Tema.FONDO
            elif total == 1:
                texto = "Se generará 1 reporte."
                color, fondo = Tema.EXITO, Tema.EXITO_FONDO
            else:
                texto = f"⚠ Se generarán {total} reportes individuales."
                color, fondo = Tema.ADVERTENCIA, Tema.ADVERTENCIA_FONDO
        self.aviso.configure(text=texto, text_color=color, fg_color=fondo)

    def valor(self) -> str:
        if self.var_todos.get():
            return "Todos"
        return ", ".join(self._seleccionados())

    def limpiar(self):
        self._actualizando = True
        self.var_todos.set(False)
        for casilla in self._casillas.values():
            casilla.variable.set(False)
            casilla.configure(state="normal")
        self._actualizando = False
        self._actualizar_aviso()

    def poner_opciones(self, opciones: list[str]):
        self._opciones = list(opciones)
        self._dibujar_casillas()

    def _cambiar_estado(self, estado: str):
        color = "normal" if estado == "normal" else "disabled"
        self.check_todos.configure(state=color)
        self.boton_subir.configure(state=color)
        for casilla in self._casillas.values():
            casilla.configure(state=color if not self.var_todos.get() else "disabled")


FABRICA_CONTROLES: dict[str, type[BaseFiltroControl]] = {
    "lista": ControlLista,
    "segmentado": ControlLista,  # antes eran botones fijos; ahora es el mismo campo editable
    "varios": ControlVarios,
}


# ---------------------------------------------------------- formulario dinamico ---
class FormularioDinamico(ctk.CTkFrame):
    """PASO 2: dibuja, en cascada, los filtros del informe que este seleccionado."""

    def __init__(self, master, al_cambiar_pendientes: Callable[[], None]):
        super().__init__(master, fg_color=Tema.SUPERFICIE, corner_radius=Tema.RADIO,
                         border_width=1, border_color=Tema.BORDE)
        self.al_cambiar_pendientes = al_cambiar_pendientes
        self.informe: InformeDef | None = None
        self.controles: dict[str, BaseFiltroControl] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.titulo = ctk.CTkLabel(self, text="PASO 2: CONFIGURAR FILTROS", font=Tema.SECCION,
                                   text_color=Tema.PRIMARIO, anchor="w")
        self.titulo.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
        self.subtitulo = ctk.CTkLabel(self, text="Escoja un informe en el Paso 1 para comenzar.",
                                      font=Tema.SUBTITULO, text_color=Tema.TEXTO_SUAVE, anchor="w")
        self.subtitulo.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=12)
        self.scroll.grid_columnconfigure(0, weight=1)

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid(row=3, column=0, sticky="ew", padx=16, pady=12)
        pie.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(pie, text="Formato de salida", font=Tema.ETIQUETA,
                    text_color=Tema.TEXTO).grid(row=0, column=0, sticky="w")
        self.formato = ctk.CTkSegmentedButton(
            pie, values=["XLSX", "PDF", "CSV"], fg_color=Tema.FONDO,
            selected_color=Tema.PRIMARIO, selected_hover_color=Tema.PRIMARIO_HOVER,
            unselected_color=Tema.SUPERFICIE, text_color=Tema.TEXTO)
        self.formato.set("XLSX")
        self.formato.grid(row=1, column=0, sticky="w", pady=(4, 10))

        ctk.CTkLabel(pie, text="Ubicación destino (opcional)", font=Tema.ETIQUETA,
                     text_color=Tema.TEXTO).grid(row=2, column=0, sticky="w")
        fila_destino = ctk.CTkFrame(pie, fg_color="transparent")
        fila_destino.grid(row=3, column=0, sticky="ew", pady=(4, 10))
        fila_destino.grid_columnconfigure(0, weight=1)
        self.destino_var = ctk.StringVar()
        ctk.CTkEntry(fila_destino, textvariable=self.destino_var, placeholder_text="Carpeta predeterminada", 
                     fg_color=Tema.SUPERFICIE, text_color=Tema.TEXTO, border_color=Tema.BORDE).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(fila_destino, text="Examinar", width=80, fg_color=Tema.PRIMARIO, text_color="white",
                      hover_color=Tema.PRIMARIO_HOVER, command=self._elegir_destino).grid(row=0, column=1)

        self.mensaje = ctk.CTkLabel(pie, text="", font=Tema.AYUDA, text_color=Tema.ERROR, anchor="w")
        self.mensaje.grid(row=4, column=0, sticky="ew")

        self.boton_agregar = ctk.CTkButton(
            pie, text="➕  Agregar a la lista de descargas", font=Tema.BOTON,
            fg_color=Tema.SUPERFICIE, hover_color=Tema.FONDO, text_color=Tema.PRIMARIO,
            border_width=1, border_color=Tema.PRIMARIO, corner_radius=Tema.RADIO, height=36,
            command=self._agregar, state="disabled")
        self.boton_agregar.grid(row=5, column=0, sticky="ew", pady=(6, 0))

    # ---------------------------------------------------------------- construir ---
    def mostrar_informe(self, informe: InformeDef):
        self.informe = informe
        self.controles.clear()
        for hijo in self.scroll.winfo_children():
            hijo.destroy()
        self.mensaje.configure(text="")

        self.titulo.configure(text=f"PASO 2: CONFIGURAR FILTROS ({informe.nombre})")
        self.subtitulo.configure(
            text=f"Complete los filtros en orden. {informe.direccion} — algunos dependen del anterior.")

        if not informe.activo:
            ctk.CTkLabel(self.scroll, text="Este informe todavía no tiene filtros parametrizados.\n"
                                           'Use "➕ Informe nuevo" para configurarlo.',
                        font=Tema.TEXTO_NORMAL, text_color=Tema.TEXTO_SUAVE,
                        justify="left").grid(row=0, column=0, sticky="w", pady=20)
            self.boton_agregar.configure(state="disabled")
            return

        fila = 0
        for numero, filtro in enumerate(informe.filtros, start=1):
            if numero > 1:
                ctk.CTkLabel(self.scroll, text="↓", font=(Tema.FUENTE, 16), text_color=Tema.BORDE
                            ).grid(row=fila, column=0, pady=0)
                fila += 1
            control = FABRICA_CONTROLES[filtro.tipo](
                self.scroll, filtro, numero, al_cambiar=self._al_cambiar_filtro)
            control.grid(row=fila, column=0, sticky="ew", pady=(0, 10))
            self.controles[filtro.nombre] = control
            fila += 1

        self.formato.configure(values=informe.formatos)
        self.formato.set(informe.formatos[0])
        self.boton_agregar.configure(state="normal")

    # -------------------------------------------------------------- la cascada ---
    def _hijos_directos(self, nombre_padre: str) -> list[FiltroDef]:
        return [f for f in self.informe.filtros if f.depende_de == nombre_padre]

    def _al_cambiar_filtro(self, nombre: str):
        """Regla de la cascada: limpiar y refiltrar TODO lo que depende de este, en cadena."""
        self.mensaje.configure(text="")
        filtro_padre = next(f for f in self.informe.filtros if f.nombre == nombre)
        valor_padre = self.controles[nombre].valor()

        for hijo in self._hijos_directos(nombre):
            control_hijo = self.controles[hijo.nombre]
            if valor_padre:
                opciones = hijo.opciones_por.get(valor_padre, [])
                control_hijo.poner_opciones(opciones)
                control_hijo.habilitar()
            else:
                control_hijo.deshabilitar()
            # Efecto cadena: al cambiar el padre, los nietos tambien se limpian
            self._al_cambiar_filtro(hijo.nombre)

    # ------------------------------------------------------------------ agregar ---
    def _agregar(self):
        faltan = [c.filtro.nombre for c in self.controles.values()
                 if c._habilitado and not c.valido()]
        if faltan:
            self.mensaje.configure(text=f"Falta completar: {', '.join(faltan)}")
            return
        resumen = {nombre: control.valor() for nombre, control in self.controles.items()
                  if control._habilitado and control.valor()}
        resumen["Formato"] = self.formato.get()
        if self.destino_var.get().strip():
            resumen["Destino"] = self.destino_var.get().strip()
        self.al_cambiar_pendientes()
        return {"informe": self.informe.nombre, "direccion": self.informe.direccion,
               "detalle": resumen}

    def _elegir_destino(self):
        from tkinter import filedialog
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if carpeta:
            self.destino_var.set(carpeta)


# --------------------------------------------------------------- lista informes ---
class SelectorInformes(ctk.CTkFrame):
    """PASO 1: buscador + lista jerarquica de informes por categoria."""

    def __init__(self, master, catalogo: list[InformeDef], al_elegir: Callable[[InformeDef], None]):
        super().__init__(master, fg_color=Tema.SUPERFICIE, corner_radius=Tema.RADIO,
                         border_width=1, border_color=Tema.BORDE)
        self.catalogo = catalogo
        self.al_elegir = al_elegir
        self.seleccionado: InformeDef | None = None
        self._botones: dict[str, ctk.CTkButton] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text="PASO 1: SELECCIONAR INFORME", font=Tema.SECCION,
                    text_color=Tema.PRIMARIO, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(14, 8))

        self.buscador = ctk.CTkEntry(
            self, placeholder_text="Buscar informe... p.ej. inasistencias",
            fg_color=Tema.FONDO, border_color=Tema.BORDE, height=34)
        self.buscador.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.buscador.bind("<KeyRelease>", lambda _e: self._filtrar())

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.scroll.grid_columnconfigure(0, weight=1)

        nuevo = ctk.CTkButton(
            self, text="➕  Informe nuevo (no está en la lista)", font=Tema.TEXTO_NORMAL,
            fg_color="transparent", hover_color=Tema.FONDO, text_color=Tema.PRIMARIO,
            border_width=1, border_color=Tema.BORDE, corner_radius=Tema.RADIO, height=34,
            command=self._informe_nuevo)
        nuevo.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))

        self._dibujar(self.catalogo)

    def _dibujar(self, informes: list[InformeDef]):
        for hijo in self.scroll.winfo_children():
            hijo.destroy()
        self._botones.clear()

        por_categoria: dict[str, list[InformeDef]] = {}
        for informe in informes:
            por_categoria.setdefault(informe.categoria, []).append(informe)

        fila = 0
        for categoria, items in por_categoria.items():
            ctk.CTkLabel(self.scroll, text=categoria.upper(), font=(Tema.FUENTE, 10, "bold"),
                        text_color=Tema.TEXTO_SUAVE, anchor="w").grid(
                row=fila, column=0, sticky="ew", padx=6, pady=(8, 2))
            fila += 1
            for informe in items:
                contenedor = ctk.CTkFrame(self.scroll, fg_color="transparent")
                contenedor.grid(row=fila, column=0, sticky="ew", padx=6, pady=1)
                contenedor.grid_columnconfigure(0, weight=1)

                boton = ctk.CTkButton(
                    contenedor, text=informe.nombre, font=Tema.TEXTO_NORMAL, anchor="w",
                    fg_color="transparent", hover_color=Tema.FONDO, text_color=Tema.TEXTO,
                    corner_radius=Tema.RADIO, height=32,
                    command=lambda i=informe: self._elegir(i))
                boton.grid(row=0, column=0, sticky="ew")
                self._botones[informe.nombre] = boton

                ctk.CTkButton(
                    contenedor, text="✏️", width=28, height=32, font=(Tema.FUENTE, 12),
                    fg_color="transparent", hover_color=Tema.FONDO, text_color=Tema.TEXTO_SUAVE,
                    corner_radius=Tema.RADIO,
                    command=lambda i=informe: self._editar_informe(i)).grid(
                    row=0, column=1, padx=(2, 0))
                fila += 1

        if not informes:
            ctk.CTkLabel(self.scroll, text="No hay informes con ese nombre.", font=Tema.TEXTO_NORMAL,
                        text_color=Tema.TEXTO_SUAVE).grid(row=0, column=0, pady=20)

    def _filtrar(self):
        buscado = normalizar(self.buscador.get())
        if not buscado:
            self._dibujar(self.catalogo)
            return
        self._dibujar([i for i in self.catalogo if buscado in normalizar(i.nombre)])

    def _elegir(self, informe: InformeDef):
        if self.seleccionado is not None and self.seleccionado.nombre in self._botones:
            self._botones[self.seleccionado.nombre].configure(fg_color="transparent", text_color=Tema.TEXTO)
        self.seleccionado = informe
        if informe.nombre in self._botones:
            self._botones[informe.nombre].configure(fg_color=Tema.FONDO, text_color=Tema.PRIMARIO)
        self.al_elegir(informe)

    def _informe_nuevo(self):
        DialogoInformeNuevo(self, self.catalogo, al_guardar=self._informe_creado)

    def _editar_informe(self, informe: InformeDef):
        DialogoInformeNuevo(self, self.catalogo, al_guardar=self._informe_creado,
                            informe_existente=informe)

    def _informe_creado(self, catalogo_nuevo: list[InformeDef], informe_creado: InformeDef):
        self.actualizar_catalogo(catalogo_nuevo)
        self._elegir(informe_creado)

    def actualizar_catalogo(self, catalogo_nuevo: list[InformeDef]):
        self.catalogo = catalogo_nuevo
        self._filtrar()


NOMBRE_TIPO = {"lista": "Campo de texto (con sugerencias)", "segmentado": "Campo de texto (con sugerencias)",
              "varios": "Varios / Todos"}
# En "Informe nuevo" solo se ofrecen estos dos: "segmentado" (botones) ya no se usa para crear
# informes nuevos, pero se deja reconocido para que los informes viejos lo sigan abriendo bien.
TIPOS_NUEVOS = ("lista", "varios")
SIN_PADRE = "(Ninguno)"


# ----------------------------------------------------------- dialogo informe nuevo ---
class FilaFiltro(ctk.CTkFrame):
    """Una fila editable de la tabla de filtros del dialogo 'Informe nuevo'."""

    def __init__(self, master, al_cambiar: Callable[[], None], al_quitar: Callable[["FilaFiltro"], None],
                mover: Callable[["FilaFiltro", int], None],
                buscar_padre: Callable[[str | None], "FilaFiltro | None"]):
        super().__init__(master, fg_color=Tema.FONDO, corner_radius=6)
        self.al_cambiar = al_cambiar
        self.buscar_padre = buscar_padre
        self.opciones: list[str] = []
        self.opciones_por: dict[str, list[str]] = {}

        for c, peso in enumerate((3, 2, 0, 2, 0, 0, 0, 0)):
            self.grid_columnconfigure(c, weight=peso)

        self.nombre_var = ctk.StringVar()
        entrada = ctk.CTkEntry(self, textvariable=self.nombre_var, placeholder_text="Nombre del filtro",
                               fg_color=Tema.SUPERFICIE, border_color=Tema.BORDE, height=30)
        entrada.grid(row=0, column=0, sticky="ew", padx=(6, 4), pady=6)
        self.nombre_var.trace_add("write", lambda *_: al_cambiar())

        self.tipo_var = ctk.StringVar(value=TIPOS_NUEVOS[0])
        ctk.CTkOptionMenu(self, values=[NOMBRE_TIPO[t] for t in TIPOS_NUEVOS], variable=self.tipo_var,
                          fg_color=Tema.SUPERFICIE, button_color=Tema.PRIMARIO,
                          button_hover_color=Tema.PRIMARIO_HOVER, text_color=Tema.TEXTO, height=30,
                          command=lambda _=None: al_cambiar()).grid(
            row=0, column=1, sticky="ew", padx=4, pady=6)
        self.tipo_var.set(NOMBRE_TIPO[TIPOS_NUEVOS[0]])

        self.obligatorio_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self, text="Oblig.", variable=self.obligatorio_var, font=Tema.AYUDA,
                        fg_color=Tema.PRIMARIO, width=20).grid(row=0, column=2, padx=4, pady=6)

        self.depende_var = ctk.StringVar(value=SIN_PADRE)
        self.menu_depende = ctk.CTkOptionMenu(
            self, values=[SIN_PADRE], variable=self.depende_var,
            fg_color=Tema.SUPERFICIE, button_color=Tema.PRIMARIO,
            button_hover_color=Tema.PRIMARIO_HOVER, text_color=Tema.TEXTO, height=30,
            command=lambda _=None: self._cambio_depende())
        self.menu_depende.grid(row=0, column=3, sticky="ew", padx=4, pady=6)

        ctk.CTkButton(self, text="Opciones…", width=76, height=30, font=Tema.AYUDA,
                     fg_color=Tema.SUPERFICIE, hover_color=Tema.FONDO, text_color=Tema.PRIMARIO,
                     border_width=1, border_color=Tema.PRIMARIO,
                     command=self._abrir_opciones).grid(row=0, column=4, padx=4, pady=6)

        ctk.CTkButton(self, text="↑", width=26, height=30, fg_color="transparent",
                     hover_color=Tema.BORDE, text_color=Tema.TEXTO,
                     command=lambda: mover(self, -1)).grid(row=0, column=5, padx=1)
        ctk.CTkButton(self, text="↓", width=26, height=30, fg_color="transparent",
                     hover_color=Tema.BORDE, text_color=Tema.TEXTO,
                     command=lambda: mover(self, 1)).grid(row=0, column=6, padx=1)
        ctk.CTkButton(self, text="✕", width=26, height=30, fg_color="transparent",
                     hover_color=Tema.ERROR_FONDO, text_color=Tema.ERROR,
                     command=lambda: al_quitar(self)).grid(row=0, column=7, padx=(1, 6))

    @property
    def nombre(self) -> str:
        return self.nombre_var.get().strip()

    @property
    def tipo(self) -> str:
        etiqueta = self.tipo_var.get()
        return next((t for t, n in NOMBRE_TIPO.items() if n == etiqueta), TIPOS_NUEVOS[0])

    @property
    def depende_de(self) -> str | None:
        valor = self.depende_var.get()
        return None if valor == SIN_PADRE else valor

    def _cambio_depende(self):
        # Cambiar el padre invalida las opciones que dependian del padre anterior
        self.opciones_por = {}
        self.al_cambiar()

    def refrescar_padres(self, nombres_anteriores: list[str]):
        """Solo se puede depender de un filtro que este MAS ARRIBA en la tabla."""
        actual = self.depende_var.get()
        opciones = [SIN_PADRE, *nombres_anteriores]
        self.menu_depende.configure(values=opciones)
        if actual not in opciones:
            self.depende_var.set(SIN_PADRE)
            self.opciones_por = {}

    def valores_propios(self) -> list[str]:
        """Los valores que puede tomar ESTE filtro (para que un hijo arme sus opciones_por)."""
        if self.depende_de is None:
            return list(self.opciones)
        return sorted({v for valores in self.opciones_por.values() for v in valores})

    def _abrir_opciones(self):
        DialogoOpciones(self, self, self.buscar_padre(self.depende_de))


class DialogoOpciones(ctk.CTkToplevel):
    """Las opciones de una fila: una lista simple, o una lista por cada valor del padre."""

    def __init__(self, master, fila: FilaFiltro, padre: "FilaFiltro | None"):
        super().__init__(master)
        self.fila = fila
        self.title(f"Opciones de \"{fila.nombre or 'este filtro'}\"")
        self.geometry("420x480")
        self.configure(fg_color=Tema.FONDO)
        self.grab_set()

        ctk.CTkLabel(self, text=f'Opciones de "{fila.nombre or "este filtro"}"', font=Tema.SECCION,
                    text_color=Tema.PRIMARIO).pack(anchor="w", padx=18, pady=(16, 4))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=18, pady=(4, 8))
        self.entradas: dict[str | None, ctk.CTkEntry | ctk.CTkTextbox] = {}

        if padre is None:
            ctk.CTkLabel(self.scroll, text="Una opción por línea, tal como aparece en Q10.",
                        font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE, anchor="w").pack(
                fill="x", pady=(0, 6))
            caja = ctk.CTkTextbox(self.scroll, height=320, fg_color=Tema.SUPERFICIE,
                                  border_color=Tema.BORDE, border_width=1)
            caja.insert("1.0", "\n".join(fila.opciones))
            caja.pack(fill="both", expand=True)
            self.entradas[None] = caja
        else:
            valores_padre = padre.valores_propios()
            if not valores_padre:
                ctk.CTkLabel(self.scroll, justify="left", font=Tema.TEXTO_NORMAL, text_color=Tema.TEXTO,
                            text=f'Primero configure las opciones de "{padre.nombre or "el filtro anterior"}".'
                            ).pack(anchor="w", pady=20)
            else:
                ctk.CTkLabel(self.scroll, anchor="w", justify="left", font=Tema.AYUDA,
                            text_color=Tema.TEXTO_SUAVE,
                            text=f'Para cada valor de "{padre.nombre}", escriba las opciones de '
                                 f'"{fila.nombre or "este filtro"}" separadas por punto y coma (;).'
                            ).pack(fill="x", pady=(0, 8))
                for valor in valores_padre:
                    ctk.CTkLabel(self.scroll, text=valor, font=Tema.ETIQUETA, text_color=Tema.TEXTO,
                                anchor="w").pack(fill="x", pady=(6, 0))
                    entrada = ctk.CTkEntry(self.scroll, fg_color=Tema.SUPERFICIE, border_color=Tema.BORDE,
                                           height=30, placeholder_text="Opción 1; Opción 2; …")
                    entrada.insert(0, "; ".join(fila.opciones_por.get(valor, [])))
                    entrada.pack(fill="x", pady=(0, 2))
                    self.entradas[valor] = entrada

        ctk.CTkButton(self, text="Guardar opciones", font=Tema.BOTON, fg_color=Tema.PRIMARIO,
                     hover_color=Tema.PRIMARIO_HOVER, height=36,
                     command=self._guardar).pack(fill="x", padx=18, pady=(0, 18))

    def _guardar(self):
        if None in self.entradas:
            texto = self.entradas[None].get("1.0", "end")
            self.fila.opciones = [linea.strip() for linea in texto.splitlines() if linea.strip()]
        elif self.entradas:
            self.fila.opciones_por = {
                valor: [v.strip() for v in entrada.get().split(";") if v.strip()]
                for valor, entrada in self.entradas.items()}
        self.destroy()


class DialogoInformeNuevo(ctk.CTkToplevel):
    """Parametrizar a mano un informe que el bot no puede leer solo.

    Se usa cuando Q10 no deja ver el informe (permisos) o cuando solo pinta el resultado en
    pantalla. El usuario arma el nombre, la direccion y los filtros EN EL ORDEN de la pantalla
    de Q10; cada filtro puede depender de uno de los que estan mas arriba en la tabla.
    """

    ANCHO_MIN, ALTO_MIN = 760, 560

    def __init__(self, master, catalogo_actual: list[InformeDef],
                al_guardar: Callable[[list[InformeDef], InformeDef], None],
                informe_existente: InformeDef | None = None):
        super().__init__(master)
        self.catalogo_actual = catalogo_actual
        self.al_guardar = al_guardar
        # Si se esta editando, hace falta recordar el nombre ORIGINAL: si el usuario lo cambia,
        # asi se sabe cual informe reemplazar en el catalogo (si no, quedarian los dos).
        self.nombre_original = informe_existente.nombre if informe_existente else None
        self.filas: list[FilaFiltro] = []
        editando = informe_existente is not None

        self.title("Editar informe" if editando else "Informe nuevo")
        self.geometry(f"{self.ANCHO_MIN}x{self.ALTO_MIN}")
        self.minsize(self.ANCHO_MIN, self.ALTO_MIN)
        self.configure(fg_color=Tema.FONDO)
        self.grab_set()

        ctk.CTkLabel(self, text="Editar informe" if editando else "Parametrizar informe",
                    font=Tema.TITULO, text_color=Tema.PRIMARIO).pack(anchor="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(self, text="Se usa cuando el bot no puede leer el informe solo "
                                "(permisos, o informes que solo muestran el resultado en pantalla).",
                    font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE, justify="left").pack(
            anchor="w", padx=20, pady=(0, 12))

        datos = ctk.CTkFrame(self, fg_color="transparent")
        datos.pack(fill="x", padx=20)
        datos.grid_columnconfigure((0, 1, 2), weight=1)
        self.nombre_informe = self._campo(datos, 0, "Nombre del informe *", "Como sale en Q10")
        self.categoria = self._campo(datos, 1, "Categoría", "Informes personalizados")
        self.direccion = self._campo(datos, 2, "Dirección en Q10 *", "Ej. ListadoCursos")

        fila_formatos = ctk.CTkFrame(self, fg_color="transparent")
        fila_formatos.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(fila_formatos, text="Formatos que ofrece:", font=Tema.ETIQUETA,
                    text_color=Tema.TEXTO).pack(side="left", padx=(0, 10))
        self.formatos_vars: dict[str, ctk.BooleanVar] = {}
        for formato in ("XLSX", "PDF", "CSV", "DOC", "HTML"):
            var = ctk.BooleanVar(value=(formato == "XLSX"))
            ctk.CTkCheckBox(fila_formatos, text=formato, variable=var, font=Tema.TEXTO_NORMAL,
                            fg_color=Tema.PRIMARIO, width=20).pack(side="left", padx=6)
            self.formatos_vars[formato] = var

        ctk.CTkLabel(self, text="Filtros, en el mismo orden de la pantalla de Q10:", font=Tema.ETIQUETA,
                    text_color=Tema.TEXTO, anchor="w").pack(fill="x", padx=20, pady=(14, 4))

        self.scroll_filas = ctk.CTkScrollableFrame(self, fg_color=Tema.SUPERFICIE, corner_radius=Tema.RADIO)
        self.scroll_filas.pack(fill="both", expand=True, padx=20)
        self.scroll_filas.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(self, text="➕  Agregar filtro", font=Tema.TEXTO_NORMAL,
                     fg_color="transparent", hover_color=Tema.FONDO, text_color=Tema.PRIMARIO,
                     border_width=1, border_color=Tema.BORDE, height=32,
                     command=self._agregar_fila).pack(fill="x", padx=20, pady=8)

        self.mensaje = ctk.CTkLabel(self, text="", font=Tema.AYUDA, text_color=Tema.ERROR, anchor="w")
        self.mensaje.pack(fill="x", padx=20)

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=20, pady=16)
        pie.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(pie, text="Cancelar", font=Tema.BOTON, height=38,
                     fg_color=Tema.SUPERFICIE, hover_color=Tema.FONDO, text_color=Tema.TEXTO,
                     border_width=1, border_color=Tema.BORDE,
                     command=self.destroy).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(pie, text="Guardar cambios" if editando else "Guardar informe", font=Tema.BOTON,
                     height=38, fg_color=Tema.PRIMARIO, hover_color=Tema.PRIMARIO_HOVER,
                     text_color="white",
                     command=self._guardar_informe).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        if informe_existente:
            self.nombre_informe.insert(0, informe_existente.nombre)
            self.categoria.insert(0, informe_existente.categoria)
            self.direccion.insert(0, informe_existente.direccion)
            for formato, var in self.formatos_vars.items():
                var.set(formato in informe_existente.formatos)
            self._cargar_filtros_existentes(informe_existente.filtros)
        if not self.filas:
            self._agregar_fila()  # arranca con un filtro listo para llenar

    def _cargar_filtros_existentes(self, filtros: list[FiltroDef]):
        """Reconstruye las filas de un informe ya parametrizado, para poder editarlo."""
        for filtro in filtros:
            fila = FilaFiltro(self.scroll_filas, al_cambiar=self._refrescar_dependencias,
                              al_quitar=self._quitar_fila, mover=self._mover_fila,
                              buscar_padre=self._padre_de_nombre)
            self.filas.append(fila)
            fila.nombre_var.set(filtro.nombre)
            fila.tipo_var.set(NOMBRE_TIPO.get(filtro.tipo, NOMBRE_TIPO["lista"]))
            fila.obligatorio_var.set(filtro.obligatorio)
            fila.opciones = list(filtro.opciones)
            fila.opciones_por = dict(filtro.opciones_por)
        self._redibujar_filas()
        self._refrescar_dependencias()
        # Las dependencias se restauran AL FINAL: antes, refrescar_dependencias() no conocia
        # todavia los nombres de las filas de mas abajo y las habria puesto en "(Ninguno)".
        for fila, filtro in zip(self.filas, filtros):
            if filtro.depende_de:
                fila.depende_var.set(filtro.depende_de)

    def _campo(self, master, columna, etiqueta, placeholder) -> ctk.CTkEntry:
        contenedor = ctk.CTkFrame(master, fg_color="transparent")
        contenedor.grid(row=0, column=columna, sticky="ew", padx=(0 if columna == 0 else 8, 0))
        ctk.CTkLabel(contenedor, text=etiqueta, font=Tema.ETIQUETA, text_color=Tema.TEXTO,
                    anchor="w").pack(fill="x")
        entrada = ctk.CTkEntry(contenedor, placeholder_text=placeholder, fg_color=Tema.SUPERFICIE,
                               border_color=Tema.BORDE, height=32)
        entrada.pack(fill="x", pady=(2, 0))
        return entrada

    def _agregar_fila(self):
        fila = FilaFiltro(self.scroll_filas, al_cambiar=self._refrescar_dependencias,
                          al_quitar=self._quitar_fila, mover=self._mover_fila,
                          buscar_padre=self._padre_de_nombre)
        self.filas.append(fila)
        self._redibujar_filas()
        self._refrescar_dependencias()

    def _padre_de_nombre(self, nombre: str | None) -> "FilaFiltro | None":
        return next((f for f in self.filas if f.nombre == nombre), None) if nombre else None

    def _quitar_fila(self, fila: FilaFiltro):
        if len(self.filas) <= 1:
            self.mensaje.configure(text="El informe necesita al menos un filtro.")
            return
        self.filas.remove(fila)
        fila.destroy()
        self._redibujar_filas()
        self._refrescar_dependencias()

    def _mover_fila(self, fila: FilaFiltro, direccion: int):
        indice = self.filas.index(fila)
        destino = indice + direccion
        if not (0 <= destino < len(self.filas)):
            return
        self.filas[indice], self.filas[destino] = self.filas[destino], self.filas[indice]
        self._redibujar_filas()
        self._refrescar_dependencias()

    def _redibujar_filas(self):
        for numero, fila in enumerate(self.filas):
            fila.grid(row=numero, column=0, sticky="ew", pady=3, padx=2)

    def _refrescar_dependencias(self):
        """Cada fila solo puede depender de los nombres de las filas que tiene ARRIBA."""
        self.mensaje.configure(text="")
        anteriores: list[str] = []
        for fila in self.filas:
            fila.refrescar_padres(list(anteriores))
            if fila.nombre:
                anteriores.append(fila.nombre)

    def _guardar_informe(self):
        nombre = self.nombre_informe.get().strip()
        direccion = self.direccion.get().strip()
        errores = []
        if not nombre:
            errores.append("Falta el nombre del informe.")
        if not direccion:
            errores.append("Falta la dirección en Q10.")

        filtros: list[FiltroDef] = []
        for fila in self.filas:
            if not fila.nombre:
                continue
            if fila.depende_de is None and not fila.opciones:
                errores.append(f'Configure las opciones de "{fila.nombre}".')
            if fila.depende_de is not None and not fila.opciones_por:
                errores.append(f'Configure las opciones de "{fila.nombre}" (depende de "{fila.depende_de}").')
            filtros.append(FiltroDef(
                nombre=fila.nombre, tipo=fila.tipo, obligatorio=fila.obligatorio_var.get(),
                opciones=list(fila.opciones), depende_de=fila.depende_de,
                opciones_por=dict(fila.opciones_por)))
        if not filtros:
            errores.append("Agregue al menos un filtro con nombre.")

        formatos = [f for f, var in self.formatos_vars.items() if var.get()] or ["XLSX"]

        if errores:
            self.mensaje.configure(text=" ".join(errores))
            return

        nuevo = InformeDef(nombre=nombre, categoria=(self.categoria.get().strip()
                                                      or "Informes personalizados"),
                           direccion=direccion, filtros=filtros, formatos=formatos, activo=True)
        catalogo_nuevo = cat.guardar_informe(self.catalogo_actual, nuevo,
                                             nombre_anterior=self.nombre_original)
        self.al_guardar(catalogo_nuevo, nuevo)
        self.destroy()


# ------------------------------------------------------------- ajustes generales ---
FORMATOS = ("XLSX", "XLS", "PDF", "CSV", "DOC", "HTML", "IMAGEN")
MENUS = ("Informes", "Académico", "Institucional", "Tesorería")
LINK_Q10_POR_DEFECTO = "https://site2.q10.com/User/Login"


class DialogoAjustesGenerales(ctk.CTkToplevel):
    """Lo que antes eran las primeras lineas de 'Config Q10.txt': Rol, Formato y por donde
    entra el bot (Menu/Submenu/Buscar/Accion). Aplica a TODOS los informes de la cola."""

    def __init__(self, master, campos_actuales: dict, al_guardar: Callable[[dict, dict], None],
                 acceso_actual: dict | None = None):
        super().__init__(master)
        self.al_guardar = al_guardar
        acceso_actual = acceso_actual or {}
        self.title("Ajustes generales")
        self.geometry("480x700")
        self.minsize(480, 600)
        self.configure(fg_color=Tema.FONDO)
        self.grab_set()

        ctk.CTkLabel(self, text="Ajustes generales", font=Tema.TITULO,
                    text_color=Tema.PRIMARIO).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(self, text="Se aplican a todos los informes de esta planilla.",
                    font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE).pack(anchor="w", padx=20, pady=(0, 14))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20)

        ctk.CTkLabel(scroll, text="Acceso a Q10", font=Tema.SECCION,
                    text_color=Tema.PRIMARIO, anchor="w").pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(scroll, text="Con estos datos entra el bot a Q10. Se guardan en la hoja "
                                  "'Accesos' de la planilla: no compartas ese archivo.",
                    font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE, justify="left",
                    wraplength=420).pack(anchor="w", pady=(0, 4))
        self.usuario = self._campo(scroll, "Usuario", "", acceso_actual.get("user", ""))
        self.clave = self._campo(scroll, "Contraseña", "", acceso_actual.get("password", ""),
                                 mostrar="•")
        self.link = self._campo(scroll, "Link de ingreso", "",
                                acceso_actual.get("link") or LINK_Q10_POR_DEFECTO)
        ctk.CTkFrame(scroll, fg_color=Tema.BORDE, height=1).pack(fill="x", pady=(14, 8))

        self.rol = self._campo(scroll, "Rol",
                               'La opción de la ventana "Seleccione el rol" que sale después '
                               "de la contraseña.", campos_actuales.get("rol") or "Administrativo")

        self.formato = self._menu(scroll, "Formato",
                                  "Para exportar desde el visor. Los informes que bajan Excel "
                                  "directo lo ignoran.", FORMATOS,
                                  campos_actuales.get("formato") or "XLSX")

        ctk.CTkLabel(scroll, text="Avanzado — por dónde entra el bot", font=Tema.SECCION,
                    text_color=Tema.PRIMARIO, anchor="w").pack(fill="x", pady=(18, 2))
        ctk.CTkLabel(scroll, text='Solo hace falta tocar esto para pantallas que NO son '
                                  '"Informes", como bajar los usuarios de cada curso.',
                    font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE, justify="left",
                    wraplength=420).pack(anchor="w", pady=(0, 8))

        self.menu = self._menu(scroll, "Menú",
                               'Déjalo en "Informes" para descargar informes.', MENUS,
                               campos_actuales.get("menu") or "Informes")
        self.submenu = self._campo(scroll, "Submenú",
                                   "Solo si Menú NO es Informes. Los niveles se separan con "
                                   '">". Ej: Educación virtual v2 > Cursos virtuales',
                                   campos_actuales.get("submenu", ""))
        self.buscar = self._campo(scroll, "Buscar",
                                  "Solo para pantallas con buscador (Cursos virtuales). "
                                  "Vacío = la lista completa.", campos_actuales.get("buscar", ""))
        self.accion = self._menu(scroll, "Acción",
                                 'Vacío = guardar la tabla en CSV. "Usuarios" = bajar los '
                                 "usuarios de cada curso.", ("", "Usuarios"),
                                 campos_actuales.get("accion", ""))

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=20, pady=16)
        pie.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(pie, text="Cancelar", font=Tema.BOTON, height=38,
                     fg_color=Tema.SUPERFICIE, hover_color=Tema.FONDO, text_color=Tema.TEXTO,
                     border_width=1, border_color=Tema.BORDE,
                     command=self.destroy).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(pie, text="Guardar", font=Tema.BOTON, height=38, fg_color=Tema.PRIMARIO,
                     hover_color=Tema.PRIMARIO_HOVER, text_color="white",
                     command=self._guardar).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _campo(self, master, etiqueta, ayuda, valor, mostrar: str | None = None) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=etiqueta, font=Tema.ETIQUETA, text_color=Tema.TEXTO,
                    anchor="w").pack(fill="x", pady=(6, 0))
        if ayuda:
            ctk.CTkLabel(master, text=ayuda, font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE,
                        anchor="w", justify="left", wraplength=420).pack(fill="x")
        entrada = ctk.CTkEntry(master, fg_color=Tema.SUPERFICIE, border_color=Tema.BORDE, height=32,
                               show=mostrar or "")
        entrada.insert(0, valor)
        entrada.pack(fill="x", pady=(2, 0))
        return entrada

    def _menu(self, master, etiqueta, ayuda, opciones, valor) -> ctk.StringVar:
        ctk.CTkLabel(master, text=etiqueta, font=Tema.ETIQUETA, text_color=Tema.TEXTO,
                    anchor="w").pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(master, text=ayuda, font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE,
                    anchor="w", justify="left", wraplength=420).pack(fill="x")
        variable = ctk.StringVar(value=valor if valor in opciones else (opciones[0] if opciones else ""))
        ctk.CTkOptionMenu(master, values=[o or "(vacío)" for o in opciones], variable=variable,
                          fg_color=Tema.SUPERFICIE, button_color=Tema.PRIMARIO,
                          button_hover_color=Tema.PRIMARIO_HOVER, text_color=Tema.TEXTO
                          ).pack(fill="x", pady=(2, 0))
        return variable

    def _guardar(self):
        self.al_guardar({
            "rol": self.rol.get().strip() or "Administrativo",
            "formato": self.formato.get(),
            "menu": self.menu.get(),
            "submenu": self.submenu.get().strip(),
            "buscar": self.buscar.get().strip(),
            "accion": "" if self.accion.get() == "(vacío)" else self.accion.get(),
        }, {
            "user": self.usuario.get().strip(),
            "password": self.clave.get(),
            "link": self.link.get().strip(),
        })
        self.destroy()


# --------------------------------------------------------------- bandeja pendientes ---
class BandejaPendientes(ctk.CTkFrame):
    """Cola de informes ya configurados, listos para guardar o ejecutar."""

    def __init__(self, master, al_guardar: Callable[[list[dict]], None],
                al_ejecutar: Callable[[list[dict]], None],
                al_intentar_agregar_actual: Callable[[], bool] | None = None):
        super().__init__(master, fg_color=Tema.SUPERFICIE, corner_radius=Tema.RADIO,
                         border_width=1, border_color=Tema.BORDE, height=170)
        self.al_guardar = al_guardar
        self.al_ejecutar = al_ejecutar
        # Si el usuario llena el Paso 2 y le da directo a Guardar/Ejecutar sin pasar por
        # "Agregar a la lista", se intenta agregar lo que tenga puesto antes de quejarse.
        self.al_intentar_agregar_actual = al_intentar_agregar_actual
        self.pendientes: list[dict] = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_propagate(False)

        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 4))
        self.titulo = ctk.CTkLabel(cabecera, text="Informes pendientes (0)", font=Tema.SECCION,
                                   text_color=Tema.PRIMARIO, anchor="w")
        self.titulo.pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", orientation="horizontal",
                                             height=64)
        self.scroll.grid(row=1, column=0, sticky="ew", padx=12)

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid(row=2, column=0, sticky="ew", padx=16, pady=12)
        pie.grid_columnconfigure(0, weight=1)
        pie.grid_columnconfigure(1, weight=0)

        ctk.CTkButton(
            pie, text="💾  Guardar configuración", font=Tema.BOTON, height=38,
            fg_color=Tema.SUPERFICIE, hover_color=Tema.FONDO, text_color=Tema.PRIMARIO,
            border_width=1, border_color=Tema.PRIMARIO, corner_radius=Tema.RADIO,
            command=self._guardar).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            pie, text="🤖  EJECUTAR BOT DE DESCARGA", font=Tema.BOTON_GRANDE, height=40,
            fg_color=Tema.PRIMARIO, hover_color=Tema.PRIMARIO_HOVER, text_color="white",
            corner_radius=Tema.RADIO,
            command=self._ejecutar).grid(row=0, column=1, sticky="e")

    def agregar(self, item: dict | None):
        if item is None:          # el formulario no dejo agregar (faltaba un obligatorio)
            return
        self.pendientes.append(item)
        self._dibujar()

    def _quitar(self, item: dict):
        self.pendientes.remove(item)
        self._dibujar()

    def _dibujar(self):
        for hijo in self.scroll.winfo_children():
            hijo.destroy()
        self.titulo.configure(text=f"Informes pendientes ({len(self.pendientes)})")

        if not self.pendientes:
            ctk.CTkLabel(self.scroll, text="Todavía no ha agregado ningún informe.",
                        font=Tema.TEXTO_NORMAL, text_color=Tema.TEXTO_SUAVE).pack(
                side="left", padx=8, pady=16)
            return

        for item in self.pendientes:
            tarjeta = ctk.CTkFrame(self.scroll, fg_color=Tema.FONDO, corner_radius=Tema.RADIO,
                                   width=230, height=58)
            tarjeta.pack(side="left", padx=6, pady=4)
            tarjeta.pack_propagate(False)

            fila = ctk.CTkFrame(tarjeta, fg_color="transparent")
            fila.pack(fill="x", padx=8, pady=(6, 0))
            ctk.CTkLabel(fila, text=item["informe"], font=Tema.ETIQUETA, text_color=Tema.TEXTO,
                        anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(fila, text="✕", width=20, height=20, font=Tema.AYUDA,
                         fg_color="transparent", hover_color=Tema.ERROR_FONDO, text_color=Tema.ERROR,
                         command=lambda i=item: self._quitar(i)).pack(side="right")

            formato = item["detalle"].get("Formato", "")
            resumen = " · ".join(f"{k}: {v}" for k, v in item["detalle"].items() if k != "Formato")
            texto = f"{resumen} · {self._reportes_de(item)} reporte(s) · [{formato}]"
            ctk.CTkLabel(tarjeta, text=texto, font=Tema.AYUDA, text_color=Tema.TEXTO_SUAVE,
                        anchor="w", wraplength=210).pack(fill="x", padx=8, pady=(0, 6))

    @staticmethod
    def _reportes_de(item: dict) -> str:
        """Cuantos reportes generaria este pendiente (un valor 'Todos', o una lista con comas)."""
        cantidad = 1
        for valor in item["detalle"].values():
            if valor == "Todos":
                return "varios: Todos"
            if ", " in valor:
                cantidad *= len(valor.split(", "))
        return str(cantidad)

    def _informes_repetidos(self) -> list[str]:
        """Nombres de informe que aparecen mas de una vez en la cola (el bot no los distingue)."""
        vistos, repetidos = set(), []
        for item in self.pendientes:
            clave = item["informe"].strip().lower()
            if clave in vistos and item["informe"] not in repetidos:
                repetidos.append(item["informe"])
            vistos.add(clave)
        return repetidos

    def _agregar_si_falta(self) -> bool:
        """Si la cola esta vacia, intenta agregar lo que haya en el Paso 2 antes de quejarse.

        Devuelve True si al final hay algo en la cola (ya sea porque ya habia, o porque se
        acaba de agregar), y False si sigue vacia (no habia informe elegido, o falta un
        obligatorio: en ese caso el propio Paso 2 ya marco que falta).
        """
        if self.pendientes:
            return True
        # No se avisa con un dialogo aparte: lo que se acaba de agregar ya queda a la vista
        # en el mensaje de exito de Guardar, o en la confirmacion antes de Ejecutar.
        return bool(self.al_intentar_agregar_actual and self.al_intentar_agregar_actual())

    def _guardar(self, avisar: bool = True) -> bool:
        if not self._agregar_si_falta():
            if avisar:
                self._mensaje_emergente(
                    "Nada para guardar",
                    "Escoja un informe en el Paso 1, complete sus filtros obligatorios y "
                    'de clic en "Agregar a la lista de descargas".')
            return False
        try:
            self.al_guardar(self.pendientes)
        except Exception as error:
            self._mensaje_emergente("No se pudo guardar", str(error), error=True)
            return False
        if avisar:
            self._mensaje_emergente(
                "Configuración guardada",
                f"Se guardaron {len(self.pendientes)} informe(s) en '{planilla_excel.NOMBRE}'.")
        return True

    def _ejecutar(self):
        if not self._agregar_si_falta():
            self._mensaje_emergente(
                "Nada para ejecutar",
                "Escoja un informe en el Paso 1, complete sus filtros obligatorios y "
                'de clic en "Agregar a la lista de descargas".')
            return
        repetidos = self._informes_repetidos()
        if repetidos:
            self._mensaje_emergente(
                "Revise la lista antes de continuar",
                "Hay más de un pendiente para el mismo informe:\n"
                + "\n".join(f"• {r}" for r in repetidos) +
                "\n\nPor ahora el bot solo admite UN grupo de filtros por informe: sus filtros "
                "se mezclarían. Quite los que sobran, o pida varios valores dentro del MISMO "
                'pendiente (marcando varios, o "Todos").', error=True)
            return
        self._confirmar_ejecutar()

    def _confirmar_ejecutar(self):
        detalle = "\n".join(f"• {i['informe']}: {self._reportes_de(i)} reporte(s)" for i in self.pendientes)
        ventana = ctk.CTkToplevel(self)
        ventana.title("Confirmar ejecución")
        ventana.geometry("420x260")
        ventana.configure(fg_color=Tema.FONDO)
        ventana.grab_set()
        ctk.CTkLabel(ventana, text="¿Ejecutar el bot ahora?", font=Tema.SECCION,
                    text_color=Tema.PRIMARIO).pack(anchor="w", padx=20, pady=(18, 6))
        ctk.CTkLabel(ventana, text="Se guardará la configuración, se abrirá el navegador y se "
                                   f"descargará:\n\n{detalle}\n\nNo cierre el navegador mientras trabaja.",
                    font=Tema.TEXTO_NORMAL, text_color=Tema.TEXTO, justify="left",
                    wraplength=380).pack(anchor="w", padx=20)
        pie = ctk.CTkFrame(ventana, fg_color="transparent")
        pie.pack(fill="x", padx=20, pady=18)
        pie.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(pie, text="Cancelar", font=Tema.BOTON, height=36,
                     fg_color=Tema.SUPERFICIE, hover_color=Tema.FONDO, text_color=Tema.TEXTO,
                     border_width=1, border_color=Tema.BORDE,
                     command=ventana.destroy).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        def confirmar():
            ventana.destroy()
            if not self._guardar(avisar=False):
                return
            try:
                self.al_ejecutar(self.pendientes)
            except Exception as error:
                self._mensaje_emergente("No se pudo iniciar el bot", str(error), error=True)

        ctk.CTkButton(pie, text="🤖 Ejecutar", font=Tema.BOTON, height=36, fg_color=Tema.PRIMARIO,
                     hover_color=Tema.PRIMARIO_HOVER, text_color="white",
                     command=confirmar).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    @staticmethod
    def _mensaje_emergente(titulo: str, texto: str, error: bool = False):
        ventana = ctk.CTkToplevel()
        ventana.title(titulo)
        ventana.geometry("380x180")
        ventana.configure(fg_color=Tema.FONDO)
        ventana.grab_set()
        color = Tema.ERROR if error else Tema.PRIMARIO
        ctk.CTkLabel(ventana, text=titulo, font=Tema.SECCION, text_color=color).pack(
            anchor="w", padx=20, pady=(18, 6))
        ctk.CTkLabel(ventana, text=texto, font=Tema.TEXTO_NORMAL, text_color=Tema.TEXTO,
                    justify="left", wraplength=340).pack(anchor="w", padx=20)
        ctk.CTkButton(ventana, text="Entendido", font=Tema.BOTON, fg_color=color,
                     hover_color=Tema.PRIMARIO_HOVER if not error else Tema.ERROR_HOVER, height=32,
                     command=ventana.destroy).pack(padx=20, pady=16, fill="x")


# --------------------------------------------------------------------- sidebar ---
class Sidebar(ctk.CTkFrame):
    """Barra de navegacion azul institucional (solo decorativa en esta demo)."""

    ICONOS_ARRIBA = ("★", "🏠", "📁", "📊")
    ICONOS_ABAJO = ("🔍", "⚙", "❓")

    def __init__(self, master, al_abrir_ajustes: Callable[[], None] | None = None):
        super().__init__(master, fg_color=Tema.SIDEBAR, width=56, corner_radius=0)
        self.grid_propagate(False)
        self.grid_rowconfigure(1, weight=1)
        # Solo "⚙" hace algo por ahora: abre Ajustes generales. Los demas quedan decorativos.
        comandos = {"⚙": al_abrir_ajustes}

        arriba = ctk.CTkFrame(self, fg_color="transparent")
        arriba.grid(row=0, column=0, pady=(16, 0))
        for icono in self.ICONOS_ARRIBA:
            self._boton(arriba, icono, comandos.get(icono)).pack(pady=6)

        abajo = ctk.CTkFrame(self, fg_color="transparent")
        abajo.grid(row=2, column=0, pady=(0, 16))
        for icono in self.ICONOS_ABAJO:
            self._boton(abajo, icono, comandos.get(icono)).pack(pady=6)

    def _boton(self, master, icono: str, comando=None) -> ctk.CTkButton:
        return ctk.CTkButton(
            master, text=icono, width=36, height=36, font=(Tema.FUENTE, 15),
            fg_color="transparent", hover_color=Tema.SIDEBAR_HOVER, text_color="white",
            corner_radius=8, command=comando)


# ------------------------------------------------------------------- ventana ---
class VistaQ10(ctk.CTkFrame):
    """Configurador de Q10 como vista embebible en la app unificada."""
    TITULO = "Q10 Académico"
    SUBTITULO = "Configurar descargas de informes"

    def __init__(self, master):
        super().__init__(master, fg_color=Tema.FONDO, corner_radius=0)
        # Defensivo: en un Windows sin UTF-8 como codepage del sistema, Tcl/Tk podria asumir
        # otra codificacion y danar los acentos de las listas. No cuesta nada dejarlo puesto.
        try:
            self.tk.call("encoding", "system", "utf-8")
        except Exception:
            pass

        self.catalogo = cat.cargar()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        Sidebar(self, al_abrir_ajustes=self._abrir_ajustes).grid(row=0, column=0, rowspan=2, sticky="ns")

        contenido = ctk.CTkFrame(self, fg_color="transparent")
        contenido.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        contenido.grid_columnconfigure(0, weight=2)
        contenido.grid_columnconfigure(1, weight=3)
        contenido.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(contenido, text="Configurar Q10", font=(Tema.FUENTE, 20, "bold"),
                    text_color=Tema.TEXTO, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self.formulario = FormularioDinamico(contenido, al_cambiar_pendientes=lambda: None)
        self.selector = SelectorInformes(contenido, self.catalogo, al_elegir=self.formulario.mostrar_informe)
        self.selector.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.formulario.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        # Reconectar el boton "Agregar" para que sepa a donde mandar el resultado
        self.formulario.boton_agregar.configure(command=self._agregar_a_bandeja)

        self.bandeja = BandejaPendientes(self, al_guardar=self._guardar_planilla,
                                         al_ejecutar=self._ejecutar_bot,
                                         al_intentar_agregar_actual=self._agregar_a_bandeja)
        self.bandeja.grid(row=1, column=1, sticky="ew", padx=16, pady=(0, 16))

        # Selecciona el primer informe activo para que la ventana no abra vacia
        primero = next((i for i in self.catalogo if i.activo), None)
        if primero:
            self.selector._elegir(primero)

    # ------------------------------------------------ integracion con la app unificada
    def hay_proceso_activo(self) -> bool:
        return False        # el bot se lanza en su propia consola; no depende de esta vista

    def cerrar(self) -> None:
        pass

    def _agregar_a_bandeja(self) -> bool:
        item = self.formulario._agregar()
        if not item:
            return False
        self.bandeja.agregar(item)
        return True

    # ------------------------------------------------------------- planilla y bot ---
    def _valores_q10(self, pendientes: list[dict]) -> dict:
        """Arma lo que necesita planilla.actualizar_hoja_sistema a partir de la cola.

        Conserva los Ajustes (Rol, Menu...) que ya hubiera en la planilla: este formulario
        todavia no los administra, y no hay que perderlos al guardar solo Informes/Filtros.
        """
        campos_previos = planilla_excel.campos_actuales(archivos.PLANILLA, "Q10")

        informes_unicos: list[str] = []
        for item in pendientes:
            if item["informe"] not in informes_unicos:
                informes_unicos.append(item["informe"])

        pares = [(item["informe"], filtro, valor, "Sí", "")
                for item in pendientes for filtro, valor in item["detalle"].items() if valor]

        return {
            "campos": {
                "rol": campos_previos.get("rol") or "Administrativo",
                "formato": campos_previos.get("formato") or "XLSX",
                "menu": campos_previos.get("menu") or "Informes",
                "submenu": campos_previos.get("submenu", ""),
                "buscar": campos_previos.get("buscar", ""),
                "accion": campos_previos.get("accion", ""),
            },
            "listas": {"informes": [(nombre, "Sí", "") for nombre in informes_unicos]},
            "pares": pares,
        }

    def _guardar_planilla(self, pendientes: list[dict]):
        """Escribe SOLO la hoja Q10 de 'Bot Descargas.xlsx'; Accesos y las demas quedan igual."""
        planilla_excel.actualizar_hoja_sistema(archivos.PLANILLA, "Q10", self._valores_q10(pendientes))

    # --------------------------------------------------------- ajustes generales ---
    def _abrir_ajustes(self):
        campos = planilla_excel.campos_actuales(archivos.PLANILLA, "Q10")
        acceso = planilla_excel.acceso_de(archivos.PLANILLA, "Q10")
        DialogoAjustesGenerales(self, campos, al_guardar=self._guardar_ajustes, acceso_actual=acceso)

    def _guardar_ajustes(self, nuevos_campos: dict, acceso: dict | None = None):
        """Guarda Rol/Formato/Menu... sin tocar los Informes y Filtros que ya estuvieran guardados,
        y el acceso (usuario, contraseña y link) en la hoja Accesos."""
        valores = self._valores_de_la_planilla()
        valores["campos"] = nuevos_campos
        planilla_excel.actualizar_hoja_sistema(archivos.PLANILLA, "Q10", valores)
        if acceso is not None:
            planilla_excel.guardar_acceso(archivos.PLANILLA, "Q10", acceso.get("user", ""),
                                          acceso.get("password", ""), acceso.get("link", ""))

    @staticmethod
    def _valores_de_la_planilla() -> dict:
        """Lo que YA esta guardado (Informes y Filtros), leido tal cual de la planilla actual."""
        if not archivos.PLANILLA.exists():
            return {"campos": {}, "listas": {"informes": []}, "pares": []}
        datos = planilla_excel.Planilla(archivos.PLANILLA).leer_hoja("Q10")
        informes = [(nombre, "Sí", "") for nombre in archivos.separar_lista(datos.get("informes", ""))]
        pares = [(informe, nombre, valor, "Sí", "") for informe, nombre, valor in datos.get("_pares", [])]
        return {"campos": {}, "listas": {"informes": informes}, "pares": pares}

    def _ejecutar_bot(self, pendientes: list[dict]):
        """Lanza 'bot.py Q10' en su propia consola, igual que 'Ejecutar botv5.bat'.

        OJO: 'bot.py' es propio de CADA version (botv3/bot.py, botv5/bot.py...), pero
        archivos.CARPETA apunta a la carpeta compartida del proyecto (donde viven la planilla
        y el .venv), no a botv5/. Por eso la ruta de bot.py se calcula desde este mismo
        archivo, no desde archivos.CARPETA: si no, se termina lanzando el bot.py de OTRA
        version (o el de la raiz del proyecto).
        """
        acceso = planilla_excel.acceso_de(archivos.PLANILLA, "Q10")
        if not (acceso.get("user") and acceso.get("password") and acceso.get("link")):
            self.after(300, self._abrir_ajustes)       # abre la ventana donde se escriben
            raise ValueError("Faltan tus datos de acceso a Q10 (usuario, contraseña y link). "
                             "Se abrió 'Ajustes generales': escríbelos en 'Acceso a Q10', guarda "
                             "y vuelve a ejecutar.")
        if getattr(sys, "frozen", False):
            # Empaquetado: el bot es "Bot Q10.exe", junto a esta aplicacion
            bot_exe = Path(sys.executable).resolve().parent / "Bot Q10.exe"
            if not bot_exe.exists():
                raise FileNotFoundError(f"No encontre '{bot_exe.name}' junto a la aplicacion ({bot_exe.parent})")
            subprocess.Popen([str(bot_exe), "Q10"], cwd=str(bot_exe.parent),
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
            return
        raiz_botv5 = MOTOR_Q10
        bot_py = raiz_botv5 / "bot.py"
        if not bot_py.exists():
            raise FileNotFoundError(f"No encontre '{bot_py}'")
        subprocess.Popen([self._python_para_bot(), str(bot_py), "Q10"],
                         cwd=str(raiz_botv5), creationflags=subprocess.CREATE_NEW_CONSOLE)

    @staticmethod
    def _python_para_bot() -> str:
        """El python del .venv del proyecto, si existe; si no, el que esta corriendo este formulario."""
        venv_python = archivos.CARPETA / ".venv" / "Scripts" / "python.exe"
        return str(venv_python) if venv_python.exists() else sys.executable


if __name__ == "__main__":
    raiz = ctk.CTk()
    raiz.title("Configurar Descarga Q10 - Colombo Americano (Bogotá)")
    raiz.geometry("1180x760")
    raiz.minsize(1024, 680)
    VistaQ10(raiz).pack(fill="both", expand=True)
    raiz.mainloop()
