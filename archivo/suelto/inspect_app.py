with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

import re

# 1. Fix escribir_config to accept ruta_descarga if it doesn't already, or check what it accepts.
# Actually, let's just make the calls to escribir_config pass ruta_descarga correctly.
# Where is escribir_config defined? Let's check:
match = re.search(r"def escribir_config\([^)]*\):", text)
if match:
    print("Found:", match.group(0))

# 2. Fix PanelSettings to include ruta_descarga
# Where is PanelSettings defined?
if "ruta_descarga" not in text.split("class PanelSettings")[1]:
    print("ruta_descarga missing in PanelSettings")

