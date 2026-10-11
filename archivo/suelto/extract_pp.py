import re, json

with open("transcript_PanelPerfiles.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Try to extract the PanelPerfiles code from transcript log
# The output was from Select-String -Context 0,70.
lines = text.splitlines()
code_lines = []
for line in lines:
    if line.startswith("  ") or line.startswith("> "):
        line = line[2:] # strip prefix
        if "\r" in line:
            line = line.replace("\r", "")
        code_lines.append(line)

code = "\n".join(code_lines)
with open("panel_perfiles.py", "w", encoding="utf-8") as f:
    f.write(code)
