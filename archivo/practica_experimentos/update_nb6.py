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
            
        changed = False
        
        if "def a_porcentaje(" in src_str:
            src_str = re.sub(
                r'def a_porcentaje\(val\):.*?def a_fecha',
                '''def a_porcentaje(val):
    val = str(val).strip(' \"')
    if val in ("", "Never"): return None
    if val == "-": return "-"
    
    val_clean = val.replace("%", "").strip()
    
    # Si es una fraccion como "20/283", la devolvemos tal cual como texto
    if "/" in val_clean:
        return val_clean
        
    try:
        return float(val_clean)
    except ValueError:
        return val

def a_fecha''',
                src_str,
                flags=re.DOTALL
            )
            changed = True
            
        if "ALTER TABLE {tabla} ADD {col} FLOAT;" in src_str:
            src_str = src_str.replace("ALTER TABLE {tabla} ADD {col} FLOAT;", "ALTER TABLE {tabla} ADD {col} VARCHAR(50);")
            changed = True
            
        if changed:
            lines = []
            start = 0
            while start < len(src_str):
                end = src_str.find('\n', start)
                if end == -1:
                    lines.append(src_str[start:])
                    break
                lines.append(src_str[start:end+1])
                start = end + 1
            cell['source'] = lines

with open('../Validacion Oxford_Nuevo.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print("Modificado correctamente.")
