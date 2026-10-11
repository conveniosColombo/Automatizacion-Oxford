with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
text = re.sub(
    r"self\.pp\s*=\s*PanelPerfiles\(self\.area,[\s\S]*?al_ejecutar=self\._ejecutar\)",
    "self.pp = PanelPerfiles(self.area,\n                                 al_cargar=self._cargar,\n                                 al_del=self._del_perfil,\n                                 al_nuevo=self._nuevo,\n                                 al_ejecutar=self._ejecutar,\n                                 al_renombrar=self._renombrar)",
    text
)

with open("practica/app_oxford.py", "w", encoding="utf-8") as f:
    f.write(text)
