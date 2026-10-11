import json
import re

with open('../Validacion Oxford_Nuevo.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'code':
        source = cell['source']
        if isinstance(source, list):
            src_str = "".join(source)
        else:
            src_str = source
            
        if "def a_porcentaje(" in src_str:
            new_src = re.sub(
                r'def a_porcentaje\(val\):.*?except ValueError: return None\n',
                '''def a_porcentaje(val):
    val = str(val).strip(' \"')
    if val in ("", "-", "Never"): return None
    
    val = val.replace("%", "").strip()
    try:
        return float(val)
    except ValueError:
        pass
        
    if "/" in val:
        try:
            num, den = val.split("/")
            if float(den) != 0:
                return round((float(num) / float(den)) * 100, 2)
            else:
                return 0.0
        except ValueError:
            return None
            
    return None\n''',
                src_str,
                flags=re.DOTALL
            )
            
            lines = []
            start = 0
            while start < len(new_src):
                end = new_src.find('\n', start)
                if end == -1:
                    lines.append(new_src[start:])
                    break
                lines.append(new_src[start:end+1])
                start = end + 1
            cell['source'] = lines

with open('../Validacion Oxford_Nuevo.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print("Modificado correctamente.")
