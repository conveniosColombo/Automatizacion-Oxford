import re

with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update PanelSettings.__init__ to include ruta_descarga
# Find PanelSettings.__init__ and the get/set methods
panel_settings_old = """class PanelSettings(PBase):
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
                     font=T.AYD, text_color=T.SUAVE, anchor="w").grid(row=1, column=0, sticky="ew")
        self.c_sco = ctk.CTkOptionMenu(inner, values=self.SCORES,
                                       font=T.NRM, fg_color=T.SUP,
                                       text_color=T.TEXTO, button_color=T.NAVY,
                                       button_hover_color=T.NAVY_H,
                                       command=lambda _: al_cambiar())
        self.c_sco.grid(row=2, column=0, sticky="ew", pady=(4, 16))

        # Figures
        ctk.CTkLabel(inner, text="Figures", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=3, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="Porcentaje (80%) o Fraccion (4/5).",
                     font=T.AYD, text_color=T.SUAVE, anchor="w").grid(row=4, column=0, sticky="ew")
        self.c_fig = ctk.CTkOptionMenu(inner, values=self.FIGS,
                                       font=T.NRM, fg_color=T.SUP,
                                       text_color=T.TEXTO, button_color=T.NAVY,
                                       button_hover_color=T.NAVY_H,
                                       command=lambda _: al_cambiar())
        self.c_fig.grid(row=5, column=0, sticky="ew", pady=(4, 16))

        # Show
        ctk.CTkLabel(inner, text="Show", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=6, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="Todas o solo completadas.",
                     font=T.AYD, text_color=T.SUAVE, anchor="w").grid(row=7, column=0, sticky="ew")
        self.c_sho = ctk.CTkOptionMenu(inner, values=self.SHOW,
                                       font=T.NRM, fg_color=T.SUP,
                                       text_color=T.TEXTO, button_color=T.NAVY,
                                       button_hover_color=T.NAVY_H,
                                       command=lambda _: al_cambiar())
        self.c_sho.grid(row=8, column=0, sticky="ew", pady=(4, 0))

    def get(self) -> dict:
        return {
            "scores": self.c_sco.get(),
            "figuras": self.c_fig.get(),
            "mostrar": self.c_sho.get()
        }

    def set(self, d: dict):
        self.c_sco.set(d.get("scores", self.SCORES[0]))
        self.c_fig.set(d.get("figuras", self.FIGS[0]))
        self.c_sho.set(d.get("mostrar", self.SHOW[0]))"""

panel_settings_new = """class PanelSettings(PBase):
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
                     font=T.AYD, text_color=T.SUAVE, anchor="w").grid(row=1, column=0, sticky="ew")
        self.c_sco = ctk.CTkOptionMenu(inner, values=self.SCORES,
                                       font=T.NRM, fg_color=T.SUP,
                                       text_color=T.TEXTO, button_color=T.NAVY,
                                       button_hover_color=T.NAVY_H,
                                       command=lambda _: al_cambiar())
        self.c_sco.grid(row=2, column=0, sticky="ew", pady=(4, 16))

        # Figures
        ctk.CTkLabel(inner, text="Figures", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=3, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="Porcentaje (80%) o Fraccion (4/5).",
                     font=T.AYD, text_color=T.SUAVE, anchor="w").grid(row=4, column=0, sticky="ew")
        self.c_fig = ctk.CTkOptionMenu(inner, values=self.FIGS,
                                       font=T.NRM, fg_color=T.SUP,
                                       text_color=T.TEXTO, button_color=T.NAVY,
                                       button_hover_color=T.NAVY_H,
                                       command=lambda _: al_cambiar())
        self.c_fig.grid(row=5, column=0, sticky="ew", pady=(4, 16))

        # Show
        ctk.CTkLabel(inner, text="Show", font=T.ETQ,
                     text_color=T.TEXTO, anchor="w").grid(row=6, column=0, sticky="ew")
        ctk.CTkLabel(inner, text="Todas o solo completadas.",
                     font=T.AYD, text_color=T.SUAVE, anchor="w").grid(row=7, column=0, sticky="ew")
        self.c_sho = ctk.CTkOptionMenu(inner, values=self.SHOW,
                                       font=T.NRM, fg_color=T.SUP,
                                       text_color=T.TEXTO, button_color=T.NAVY,
                                       button_hover_color=T.NAVY_H,
                                       command=lambda _: al_cambiar())
        self.c_sho.grid(row=8, column=0, sticky="ew", pady=(4, 16))

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
            self.var_ruta.set(d)

    def get(self) -> dict:
        return {
            "scores": self.c_sco.get(),
            "figuras": self.c_fig.get(),
            "mostrar": self.c_sho.get(),
            "ruta_descarga": self.var_ruta.get()
        }

    def set(self, d: dict):
        self.c_sco.set(d.get("scores", self.SCORES[0]))
        self.c_fig.set(d.get("figuras", self.FIGS[0]))
        self.c_sho.set(d.get("mostrar", self.SHOW[0]))
        self.var_ruta.set(d.get("ruta_descarga", ""))"""

text = text.replace(panel_settings_old, panel_settings_new)

# 2. Update calls to escribir_config
# In _guardar:
text = re.sub(
    r"escribir_config\(\s*p\[\"id_org\"\]\,\s*clases_guardar\,\s*p\[\"scores\"\]\,\s*p\[\"figuras\"\]\,\s*p\[\"mostrar\"\]\s*\)",
    "escribir_config(p[\"id_org\"], clases_guardar, p[\"scores\"], p[\"figuras\"], p[\"mostrar\"], p.get(\"ruta_descarga\", \"\"))",
    text
)

with open("practica/app_oxford.py", "w", encoding="utf-8") as f:
    f.write(text)

