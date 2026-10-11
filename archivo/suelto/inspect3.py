with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "def escribir_config(" in line:
        for j in range(i, i+10):
            print(lines[j].strip())
        break
