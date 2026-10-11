import re

with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

# Buscamos la clase TablaClases
match = re.search(r'class TablaClases\(ctk\.CTkFrame\):.*?(?=\n\nclass |\Z)', text, re.DOTALL)
if match:
    old_tabla_clases = match.group(0)
else:
    print("TablaClases no encontrada!")
    exit(1)

new_tabla_clases = """class TablaClases(ctk.CTkFrame):
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
            font=T.BTN, text_color=T.NAVY,
            fg_color=T.NAVY, hover_color=T.NAVY_H,
            border_color=T.NAVY, corner_radius=4,
            command=self._toggle_todas)
        self._chk_todas.pack(side="left", padx=(16, 0))
        
        for txt, cmd in [("Descargar plantilla", self._descargar_plantilla),
                          ("Excel", self._excel),
                          ("Pegar lista", self._pegar),
                          ("Limpiar", self._limpiar)]:
            col = T.ERR if txt == "Limpiar" else T.NAVY
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
            self.caja_texto.insert("1.0", "\\n".join(clases))
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
        plantilla_src = ROOT / "Plantilla_Clases_Oxford.xlsx"
        if not plantilla_src.exists():
            messagebox.showerror("Error", f"No se encontró la plantilla en:\\n{plantilla_src}")
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
            messagebox.showinfo("Éxito", f"Plantilla guardada en:\\n{destino}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la plantilla:\\n{e}")

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
            self._al_cambiar()"""

text = text.replace(old_tabla_clases, new_tabla_clases)

with open("practica/app_oxford.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Patch applied")
