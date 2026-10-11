with open("transcript_PanelPerfiles.txt", "r", encoding="utf-16") as f:
    text = f.read()

import json
lines = text.splitlines()
code_lines = []
for line in lines:
    if "class PanelPerfiles" in line and "type\":\"PLANNER_RESPONSE" not in line:
        # try to parse json if it's the json line
        try:
            d = json.loads(line)
            content = d.get("content", "")
            # we need to find the lines that start with "> " or "  "
            for cl in content.splitlines():
                if cl.startswith("> ") or cl.startswith("  "):
                    code_lines.append(cl[2:])
        except:
            pass

code = "\n".join(code_lines)
with open("panel_perfiles.py", "w", encoding="utf-8") as f:
    f.write(code)
