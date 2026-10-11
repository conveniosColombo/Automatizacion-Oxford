with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    "self.pp = PanelPerfiles(self.area,\n                             al_cargar=self._cargar,\n                             al_del=self._del_perfil,\n                             al_nuevo=self._nuevo,\n                             al_ejecutar=self._ejecutar)",
    "self.pp = PanelPerfiles(self.area,\n                             al_cargar=self._cargar,\n                             al_del=self._del_perfil,\n                             al_nuevo=self._nuevo,\n                             al_ejecutar=self._ejecutar,\n                             al_renombrar=self._renombrar)"
)

# And make sure _renombrar and _on_rename are the new ones
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

with open("practica/app_oxford.py", "w", encoding="utf-8") as f:
    f.write(text)
