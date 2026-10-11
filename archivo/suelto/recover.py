with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

# Verify if PBase is already in text, if so, we don't need to append.
if "class PBase" not in text:
    pbase_code = """
class PBase(ctk.CTkFrame):
    def __init__(self, master, titulo: str, desc: str):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        ctk.CTkLabel(hdr, text=titulo, font=T.TIT, text_color=T.NAVY, anchor="w").pack(fill="x")
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
        
        self.scroll = ctk.CTkScrollableFrame(self.cont, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        
        ctk.CTkButton(self.cont, text="+ Nuevo perfil", font=T.BTN, height=36, fg_color=T.NAVY, hover_color=T.NAVY_H, text_color=T.SUP, command=self.al_nuevo).grid(row=1, column=0, pady=(10,0), sticky="ew")
        
    def actualizar(self, perfiles: list, activo: int | None):
        for w in self.scroll.winfo_children():
            w.destroy()
            
        if not perfiles:
            ctk.CTkLabel(self.scroll, text="No hay perfiles.\\nCrea uno nuevo abajo.", font=T.NRM, text_color=T.SUAVE).pack(pady=30)
            
        for idx, p in enumerate(perfiles):
            es_activo = (idx == activo)
            borde_col = T.YELL if es_activo else T.BORDE
            
            card = ctk.CTkFrame(self.scroll, fg_color=T.SUP, corner_radius=T.R, border_width=2 if es_activo else 1, border_color=borde_col)
            card.pack(fill="x", pady=4, padx=2)
            card.grid_columnconfigure(1, weight=1)
            
            ctk.CTkFrame(card, fg_color=T.YELL if es_activo else T.NAVY, width=6, corner_radius=0).grid(row=0, column=0, sticky="ns")
            
            info = ctk.CTkFrame(card, fg_color="transparent")
            info.grid(row=0, column=1, sticky="ew", padx=12, pady=(10, 8))
            info.grid_columnconfigure(0, weight=1)
            
            badge = "  <- Activo" if es_activo else ""
            ctk.CTkLabel(info, text=f"{p['nombre']}{badge}", font=T.SEC, text_color=T.NAVY if es_activo else T.TEXTO, anchor="w").grid(row=0, column=0, sticky="ew")
            
            nc = len(p.get("clases", []))
            det = f"ID: {p.get('id_org') or '-'}   {nc} clase{'s' if nc != 1 else ''}   Scores: {p.get('scores', '-')}"
            ctk.CTkLabel(info, text=det, font=T.AYD, text_color=T.SUAVE, anchor="w").grid(row=1, column=0, sticky="ew")
            
            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.grid(row=0, column=2, padx=10)
            
            if es_activo:
                ctk.CTkButton(btns, text="EJECUTAR BOT", font=T.BTNG, height=40, fg_color=T.OK, hover_color="#166534", text_color="white", corner_radius=T.R, command=self.al_ejecutar).pack(side="left", padx=(0, 16))
                
            sec_btns = ctk.CTkFrame(btns, fg_color="transparent")
            sec_btns.pack(side="left")
            
            ctk.CTkButton(sec_btns, text="Cargar", font=T.BTN, height=32, width=84, fg_color=T.YELL if es_activo else T.NAVY, hover_color=T.YELL_H if es_activo else T.NAVY_H, text_color=T.YTXT if es_activo else "white", corner_radius=T.R, command=lambda i=idx: self.al_cargar(i)).pack(pady=(0, 4))
            ctk.CTkButton(sec_btns, text="Renombrar", font=T.BTN, height=32, width=84, fg_color=T.SUP, hover_color=T.FONDO, text_color=T.TEXTO, border_width=1, border_color=T.BORDE, corner_radius=T.R, command=lambda i=idx: self.al_renombrar(i)).pack(pady=(0, 4))
            ctk.CTkButton(sec_btns, text="Eliminar", font=T.BTN, height=32, width=84, fg_color=T.ERR_BG, hover_color="#fecaca", text_color=T.ERR, corner_radius=T.R, command=lambda i=idx: self.al_del(i)).pack(pady=(0, 0))
"""
    
    with open("panel_settings.txt", "r", encoding="utf-8") as ps:
        settings_code = ps.read()
        
    full_text = text + "\n" + pbase_code + "\n" + settings_code
    with open("practica/app_oxford.py", "w", encoding="utf-8") as f:
        f.write(full_text)
    print("Recovered!")
else:
    print("Already there")
