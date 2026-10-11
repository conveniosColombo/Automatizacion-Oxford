with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

import re

# Insert Ruta Descarga UI into PanelSettings
old_init_end = """        self.seg_show.set(self.SHOW[0])
        self.seg_show.grid(row=8, column=0, sticky="w", pady=(4, 0))"""

new_init_end = """        self.seg_show.set(self.SHOW[0])
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
        
        btn_exam = ctk.CTkButton(box_ruta, text="Examinar", font=T.BTN, fg_color=T.NAVY, hover_color=T.NAVY_H, text_color=T.SUP, width=80, command=self._examinar)
        btn_exam.grid(row=0, column=1)

    def _examinar(self):
        d = filedialog.askdirectory(title="Seleccionar carpeta de descargas")
        if d:
            self.var_ruta.set(d)"""

text = text.replace(old_init_end, new_init_end)

# Update PanelSettings get and set
old_get = """    def get(self) -> dict:
        return {
            "scores":          self.var_sc.get(),
            "show_figures_as": self.seg_fig.get(),
            "show_scores_for": self.seg_show.get(),
        }"""
new_get = """    def get(self) -> dict:
        return {
            "scores":          self.var_sc.get(),
            "show_figures_as": self.seg_fig.get(),
            "show_scores_for": self.seg_show.get(),
            "ruta_descarga":   self.var_ruta.get(),
        }"""
text = text.replace(old_get, new_get)

old_set = """    def set(self, d: dict):
        sc = d.get("scores", self.SCORES[0])
        self.var_sc.set(sc if sc in self.SCORES else self.SCORES[0])
        fi = d.get("show_figures_as", self.FIGS[0])
        self.seg_fig.set(fi if fi in self.FIGS else self.FIGS[0])
        sh = d.get("show_scores_for", self.SHOW[0])
        self.seg_show.set(sh if sh in self.SHOW else self.SHOW[0])"""
new_set = """    def set(self, d: dict):
        sc = d.get("scores", self.SCORES[0])
        self.var_sc.set(sc if sc in self.SCORES else self.SCORES[0])
        fi = d.get("show_figures_as", self.FIGS[0])
        self.seg_fig.set(fi if fi in self.FIGS else self.FIGS[0])
        sh = d.get("show_scores_for", self.SHOW[0])
        self.seg_show.set(sh if sh in self.SHOW else self.SHOW[0])
        self.var_ruta.set(d.get("ruta_descarga", ""))"""
text = text.replace(old_set, new_set)

# Update escribir_config calls. We'll find all instances of escribir_config( and replace them.
# The definition of escribir_config is:
# def escribir_config(id_org: str, clases: list, scores: str, figuras: str, mostrar: str, ruta_descarga: str) -> None:
text = re.sub(
    r"escribir_config\(\s*p\[\"id_org\"\]\,\s*clases_guardar\,\s*p\[\"scores\"\]\,\s*p\[\"show_figures_as\"\]\,\s*p\[\"show_scores_for\"\]\s*\)",
    "escribir_config(p[\"id_org\"], clases_guardar, p[\"scores\"], p[\"show_figures_as\"], p[\"show_scores_for\"], p.get(\"ruta_descarga\", \"\"))",
    text
)

text = re.sub(
    r"escribir_config\(\s*p\[\"id_org\"\]\,\s*clases_guardar\,\s*p\[\"scores\"\]\,\s*p\[\"figuras\"\]\,\s*p\[\"mostrar\"\]\s*\)",
    "escribir_config(p[\"id_org\"], clases_guardar, p[\"scores\"], p[\"show_figures_as\"], p[\"show_scores_for\"], p.get(\"ruta_descarga\", \"\"))",
    text
)


with open("practica/app_oxford.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated successfully.")
