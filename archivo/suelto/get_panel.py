with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
match = re.search(r'class PanelSettings\(PBase\):.*?def __init__.*?def get\(self\).*?def set\(self, d: dict\):.*?(?=\n\nclass|\Z)', text, re.DOTALL)
if match:
    print(match.group(0))
else:
    print("Not found")
