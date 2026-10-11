import re

with open("practica/app_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

match = re.search(r'for txt, cmd in \[\("Excel", self._excel\),.*?def _excel\(self\):.*?(?=def _pegar)', text, re.DOTALL)
if match:
    print(match.group(0))
else:
    print("Not found")
