import re

with open("automatizar_oxford.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace descargar_csv definition
old_descargar = """def descargar_csv(page, clase):
    \"\"\"Da clic en Download CSV y guarda el archivo en la carpeta Descargas.\"\"\"
    with page.expect_download(timeout=60_000) as info:
        page.get_by_role("button", name=re.compile(r"^\\s*download csv\\s*$", re.I)).click()
    descarga = info.value
    destino = (CARPETA / "Descargas"
               / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre_archivo(clase)}_{descarga.suggested_filename}")
    descarga.save_as(destino)
    return destino"""

new_descargar = """def descargar_csv(page, clase, ruta_descargas=""):
    \"\"\"Da clic en Download CSV y guarda el archivo en la carpeta seleccionada o Descargas.\"\"\"
    with page.expect_download(timeout=60_000) as info:
        page.get_by_role("button", name=re.compile(r"^\\s*download csv\\s*$", re.I)).click()
    descarga = info.value
    
    if ruta_descargas:
        base_dir = Path(ruta_descargas)
    else:
        base_dir = CARPETA / "Descargas"
        
    destino = (base_dir / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre_archivo(clase)}_{descarga.suggested_filename}")
    descarga.save_as(destino)
    return destino"""

text = text.replace(old_descargar, new_descargar)

# Update call to descargar_csv
old_call = "archivo = descargar_csv(page, clase)"
new_call = "archivo = descargar_csv(page, clase, config.get('ruta descargas', '').strip())"
text = text.replace(old_call, new_call)

with open("automatizar_oxford.py", "w", encoding="utf-8") as f:
    f.write(text)

print("automatizar_oxford.py modificado con éxito.")
