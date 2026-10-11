import re

with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. BarraInf init
text = text.replace("""    def __init__(self, master,
                 al_guardar:   Callable,
                 al_ejecutar:  Callable,
                 al_renombrar: Callable):
        super().__init__(master, fg_color=T.SUP, height=62,""",
"""    def __init__(self, master,
                 al_guardar:   Callable,
                 al_ejecutar:  Callable):
        super().__init__(master, fg_color=T.SUP, height=62,""")

# 2. BarraInf buttons
text = text.replace("""        for txt, col, chov, tc, fn, w in [
            ("Renombrar", T.SUP, T.FONDO, T.TEXTO, al_renombrar, 110),
            ("Guardar Config", T.SUP, T.FONDO, T.NAVY, al_guardar, 140),
        ]:""",
"""        for txt, col, chov, tc, fn, w in [
            ("Guardar Config", T.SUP, T.FONDO, T.NAVY, al_guardar, 140),
        ]:""")

# 3. App BarraInf creation
text = text.replace("""        self.barra = BarraInf(self,
                               al_guardar=self._guardar,
                               al_ejecutar=self._ejecutar,
                               al_renombrar=self._renombrar)""",
"""        self.barra = BarraInf(self,
                               al_guardar=self._guardar,
                               al_ejecutar=self._ejecutar)""")

# 4. App PanelPerfiles creation
text = text.replace("""        self.pp = PanelPerfiles(self.area,
                                 al_cargar=self._cargar,
                                 al_del=self._del_perfil,
                                 al_nuevo=self._nuevo,
                                 al_ejecutar=self._ejecutar)""",
"""        self.pp = PanelPerfiles(self.area,
                                 al_cargar=self._cargar,
                                 al_del=self._del_perfil,
                                 al_nuevo=self._nuevo,
                                 al_ejecutar=self._ejecutar,
                                 al_renombrar=self._renombrar)""")

# 5. App _renombrar and _on_rename
old_renombrar = """    def _renombrar(self):
        if self._activo is None:
            return
        DlgNombre(self, self._perfiles[self._activo]["nombre"],
                   al_ok=self._on_rename)

    def _on_rename(self, nombre: str):
        if self._activo is None:
            return
        self._perfiles[self._activo]["nombre"] = nombre
        self._sync_mem()
        guardar_perfiles(self._perfiles)
        self._upd_barra()
        self.pp.actualizar(self._perfiles, self._activo)"""

new_renombrar = """    def _renombrar(self, idx: int):
        DlgNombre(self, self._perfiles[idx]["nombre"],
                   al_ok=lambda n: self._on_rename(idx, n))

    def _on_rename(self, idx: int, nombre: str):
        self._perfiles[idx]["nombre"] = nombre
        if self._activo == idx:
            self._sync_mem()
            self._upd_barra()
        guardar_perfiles(self._perfiles)
        self.pp.actualizar(self._perfiles, self._activo)"""
text = text.replace(old_renombrar, new_renombrar)

# 6. PanelPerfiles init
text = text.replace("""    def __init__(self, master, al_cargar: Callable,
                 al_del: Callable, al_nuevo: Callable, al_ejecutar: Callable):
        super().__init__(master, "Perfiles de descarga",
                         "Selecciona un perfil o crea uno nuevo.")
        self.al_cargar = al_cargar
        self.al_del    = al_del
        self.al_nuevo  = al_nuevo
        self.al_ejecutar = al_ejecutar""",
"""    def __init__(self, master, al_cargar: Callable,
                 al_del: Callable, al_nuevo: Callable, al_ejecutar: Callable, al_renombrar: Callable):
        super().__init__(master, "Perfiles de descarga",
                         "Selecciona un perfil o crea uno nuevo.")
        self.al_cargar = al_cargar
        self.al_del    = al_del
        self.al_nuevo  = al_nuevo
        self.al_ejecutar = al_ejecutar
        self.al_renombrar = al_renombrar""")

# 7. PanelPerfiles secondary buttons
old_sec_btns = """            ctk.CTkButton(sec_btns, text="Cargar",
                          font=T.BTN, height=32, width=84,
                          fg_color=T.YELL if es_activo else T.NAVY,
                          hover_color=T.YELL_H if es_activo else T.NAVY_H,
                          text_color=T.YTXT if es_activo else "white",
                          corner_radius=T.R,
                          command=lambda i=idx: self.al_cargar(i)
                          ).pack(pady=(0, 4))
            ctk.CTkButton(sec_btns, text="Eliminar","""

new_sec_btns = """            ctk.CTkButton(sec_btns, text="Cargar",
                          font=T.BTN, height=32, width=84,
                          fg_color=T.YELL if es_activo else T.NAVY,
                          hover_color=T.YELL_H if es_activo else T.NAVY_H,
                          text_color=T.YTXT if es_activo else "white",
                          corner_radius=T.R,
                          command=lambda i=idx: self.al_cargar(i)
                          ).pack(pady=(0, 4))
            ctk.CTkButton(sec_btns, text="Renombrar",
                          font=T.BTN, height=32, width=84,
                          fg_color=T.SUP, hover_color=T.FONDO,
                          text_color=T.TEXTO, border_width=1, border_color=T.BORDE,
                          corner_radius=T.R,
                          command=lambda i=idx: self.al_renombrar(i)
                          ).pack(pady=(0, 4))
            ctk.CTkButton(sec_btns, text="Eliminar","""
text = text.replace(old_sec_btns, new_sec_btns)

with open("practica/app_oxford.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Modificación aplicada.")
