import re

with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

old_loop = """        for txt, cmd in [("Excel", self._excel),
                          ("Pegar lista", self._pegar),
                          ("Limpiar", self._limpiar)]:"""
                          
new_loop = """        for txt, cmd in [("Descargar plantilla", self._descargar_plantilla),
                          ("Excel", self._excel),
                          ("Pegar lista", self._pegar),
                          ("Limpiar", self._limpiar)]:"""
text = text.replace(old_loop, new_loop)

old_pegar = """    def _pegar(self):
        DlgPegarClases(self, self.get_clases(),
                        al_ok=lambda cls: [self.set_clases(cls),
                                           self._al_cambiar()])"""
                                           
new_pegar = """    def _descargar_plantilla(self):
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
                                           self._al_cambiar()])"""
text = text.replace(old_pegar, new_pegar)

with open("practica/app_oxford.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Modificado!")
