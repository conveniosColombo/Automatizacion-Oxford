import re
with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

# find escribir_config usage
for line in text.splitlines():
    if "escribir_config" in line:
        print(line.strip())
