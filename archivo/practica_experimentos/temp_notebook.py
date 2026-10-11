import pandas as pd
import os
import re
import pyodbc
from pathlib import Path

# Definir la fecha de corte para este proceso (formato AAAA-MM-DD)
FECHA_CORTE = "2026-10-20"  # <-- Cambia esta fecha segÃºn necesites

ORIGEN = Path.cwd() / 'Descargas' / 'Oxford'
TABLA_STAGE = 'dbo.avance_oxford_stage_new'
CONN_STR = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=CCA-CENT-R5186;DATABASE=rendimiento_academico;Trusted_Connection=yes;'

# Mensajes de confirmaciÃ³n visual
print("âœ… ConfiguraciÃ³n inicial y variables cargadas correctamente.")
print(f"ðŸ“… Fecha de corte definida: {FECHA_CORTE}")
print(f"ðŸ“ Ruta de origen configurada: {ORIGEN}")

# Buscar y mostrar los archivos que estÃ¡n en la carpeta
if ORIGEN.exists():
    archivos_csv = list(ORIGEN.glob("*.csv")) # Busca archivos que terminen en .csv
    if len(archivos_csv) > 0:
        print(f"\nðŸ“„ Se encontraron {len(archivos_csv)} archivo(s) CSV listos para procesar:")
        for archivo in archivos_csv:
            print(f"   - {archivo.name}")
    else:
        print("\nâš ï¸ La carpeta existe, pero actualmente no hay ningÃºn archivo .csv adentro.")
else:
    print("\nâŒ La carpeta de origen NO existe en tu computador. Por favor revisa la ruta.")

PATRON_CURSO = re.compile(r"""(?ix)
    (?P<clase>[a-z]{1,3}\s*\d+(?:[.\-_]\d+)?)    
    [\s\-_]*
    (?P<grupo>\d{1,2}\s*[ap]\.?m\.?)             
    [\s\-_]*
    (?P<codigo>\d+)                              
    (?:[\s\-_]+(?P<segmento>[a-z]{2,10}))?       
""")
MESES = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
         "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
def partes_del_nombre(nombre_archivo):
    nombre = Path(nombre_archivo).stem
    nombre = re.sub(r"^\d{4}-\d{2}-\d{2}_\d{3,4}_", "", nombre)
    hallado = PATRON_CURSO.search(nombre)
    if not hallado: return {"clase": None, "codigo": None, "grupo": None, "segmento": None}
    return {
        "clase": re.sub(r"[\s_\-]", ".", hallado["clase"].strip()).upper(),
        "codigo": hallado["codigo"],
        "grupo": re.sub(r"[\s.]", "", hallado["grupo"]).upper(),
        "segmento": (hallado["segmento"] or "").upper() or None,
    }
def a_porcentaje(val):
    val = str(val).strip(' \"')
    if val in ("", "-", "Never"): return None
    try: return float(val.replace("%", ""))
    except ValueError: return None
def a_fecha(val):
    val = str(val).strip(' \"')
    if val in ("", "-", "Never"): return None
    try:
        dia, mes, anio = val.split()
        return f"{anio}-{MESES[mes]}-{dia.zfill(2)}"
    except Exception: return None
def validar_estructura(row1, nombre_archivo):
    if len(row1) < 54: pass
    if not row1[4].strip(' \"').startswith("Total"):
        raise ValueError("La columna Ã­ndice 4 no es 'Total'.")
    categorias_dinamicas = []
    num_blocks = (len(row1) - 6) // 4
    for i in range(num_blocks):
        base = 6 + i * 4
        val_base = row1[base].strip(' \"')
        val_base_norm = " ".join(val_base.split())
        if not val_base_norm: break
        match = re.match(r"(?i)^Unit\s+(\d+)\s+(.+)$", val_base_norm)
        if match:
            categorias_dinamicas.append({'unit': int(match.group(1)), 'category': match.group(2).strip().lower().replace(" ", "_")})
        else:
            raise ValueError(f"Error formato columna: '{val_base}'")
    return categorias_dinamicas
def crear_consolidado(origen_dir, fecha_corte):
    archivos = list(Path(origen_dir).glob("*.csv"))
    lista_dfs = []
    errores_locales = []
    print("â³ Extrayendo datos de los archivos CSV...")
    
    for archivo in archivos:
        try:
            with open(archivo, "r", encoding="utf-16", errors="replace") as f:
                lineas = [l.rstrip('\r\n') for l in f if l.strip()]
                if len(lineas) < 4: raise ValueError("Archivo muy corto.")
                
                rows = [line.split('\t') for line in lineas]
                categorias_dinamicas = validar_estructura(rows[0], archivo.name)
                
                nombres_columnas = ['teacher', 'learning_material', 'student', 'last_opened', 'clase', 'codigo', 'grupo', 'segmento', 'fecha_corte', 'total_completed_pct', 'total_score_pct']
                for cat in categorias_dinamicas:
                    u = f"u{cat['unit']:02d}"
                    c = cat['category']
                    nombres_columnas.extend([f"{u}_{c}_completed_pct", f"{u}_{c}_score_pct", f"{u}_{c}_test_completed_pct", f"{u}_{c}_test_score_pct"])
                
                teacher_val = rows[2][0].strip(' \"') if len(rows[2]) > 0 else None
                material_val = rows[2][1].strip(' \"') if len(rows[2]) > 1 else None
                meta = partes_del_nombre(archivo.name)
                datos_archivo = []
                
                for row in rows[3:]:
                    if not any(c.strip() for c in row): continue
                    req_len = 6 + (len(categorias_dinamicas) * 4)
                    if len(row) < req_len: row.extend([""] * (req_len - len(row)))
                    
                    # AQUI SE ASIGNA EL PARÃMETRO fecha_corte AL DATAFRAME
                    param_row = [
                        teacher_val, material_val, row[2].strip(' \"'), a_fecha(row[3]),
                        meta["clase"], meta["codigo"], meta["grupo"], meta["segmento"], fecha_corte,
                        a_porcentaje(row[4]), a_porcentaje(row[5])
                    ]
                    for i in range(len(categorias_dinamicas)):
                        base = 6 + i * 4
                        param_row.extend([a_porcentaje(row[base]), a_porcentaje(row[base+1]), a_porcentaje(row[base+2]), a_porcentaje(row[base+3])])
                    datos_archivo.append(param_row)
                
                if datos_archivo:
                    df = pd.DataFrame(datos_archivo, columns=nombres_columnas)
                    df['archivo_origen'] = archivo.name # Ãštil para rastrear errores
                    lista_dfs.append(df)
        except Exception as e:
            errores_locales.append(f"{archivo.name} -> {e}")
            
    if errores_locales:
        print("\nâš ï¸ HUBO ERRORES AL LEER ESTOS ARCHIVOS (Fueron saltados):")
        for e in errores_locales: print(f" - {e}")
            
    return pd.concat(lista_dfs, ignore_index=True) if lista_dfs else pd.DataFrame()

df_excel = crear_consolidado(ORIGEN, FECHA_CORTE)

if not df_excel.empty:
    print(f"\nâœ… Â¡Ã‰xito! Se consolidaron {len(df_excel)} estudiantes.")
    display(df_excel) # Muestra a los estudiantes como tabla
else:
    print("\nâŒ No se encontraron datos para consolidar.")

import pyodbc
import pandas as pd
import numpy as np
from datetime import datetime

def subir_directo_a_tablas_finales(df, fecha_corte):
    if df.empty:
        print("âŒ El DataFrame estÃ¡ vacÃ­o. No hay nada que subir.")
        return
        
    print("â³ Limpiando datos en memoria...")
    df_limpio = df.dropna(subset=['student', 'learning_material']).copy()
    
    df_limpio = df_limpio[df_limpio['student'].astype(str).str.strip() != ""]
    df_limpio = df_limpio[df_limpio['learning_material'].astype(str).str.strip() != ""]
    df_limpio = df_limpio[df_limpio['student'] != 'Class Average']
    
    df_limpio = df_limpio.sort_values(by='last_opened', ascending=False)
    df_limpio = df_limpio.drop_duplicates(subset=['student', 'learning_material'], keep='first')
    
    columnas_df = [c for c in df_limpio.columns if c != 'archivo_origen']
    df_limpio = df_limpio[columnas_df]
    
    df_limpio['created_at'] = datetime.now()
    df_limpio['updated_at'] = datetime.now()
    columnas_df.extend(['created_at', 'updated_at'])
    
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    cursor.fast_executemany = False 
    
    TABLA_HISTORICO = 'dbo.avance_oxford_historico_new'
    TABLA_OPERATIVA = 'dbo.avance_oxford_operativo_new'
    
    print("âš™ï¸ Creando columnas dinÃ¡micas en SQL (si faltan)...")
    for tabla in [TABLA_HISTORICO, TABLA_OPERATIVA]:
        for col in columnas_df:
            if col.startswith('u') and col.endswith('_pct'):
                alter_sql = f"""
                IF NOT EXISTS (
                    SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('{tabla}') AND name = '{col}'
                )
                BEGIN
                    ALTER TABLE {tabla} ADD {col} FLOAT;
                END
                """
                cursor.execute(alter_sql)
    conn.commit()
    
    print(f"ðŸ§¹ Borrando cortes antiguos ({fecha_corte}) para evitar duplicados...")
    cursor.execute(f"DELETE FROM {TABLA_HISTORICO} WHERE fecha_corte = '{fecha_corte}'")
    conn.commit()
    
    print(f"ðŸš€ Subiendo {len(df_limpio)} estudiantes validados al HISTÃ“RICO...")
    cols_str = ", ".join(columnas_df)
    placeholders = ", ".join(["?"] * len(columnas_df))
    sql_insert = f"INSERT INTO {TABLA_HISTORICO} ({cols_str}) VALUES ({placeholders})"
    
    df_para_sql = df_limpio.where(pd.notnull(df_limpio), None)
    params_lote_crudos = df_para_sql.values.tolist()
    
    params_lote = []
    for fila in params_lote_crudos:
        fila_limpia = []
        for val in fila:
            if isinstance(val, str) and val.strip() == "":
                fila_limpia.append(None)
            elif pd.isna(val):
                fila_limpia.append(None)
            else:
                fila_limpia.append(val)
        params_lote.append(fila_limpia)
    
    cursor.executemany(sql_insert, params_lote)
    conn.commit()
    
    print("ðŸ”„ Refrescando la tabla OPERATIVA...")
    cursor.execute(f"""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'avance_oxford_operativo_new' 
        AND COLUMNPROPERTY(OBJECT_ID(TABLE_SCHEMA + '.' + TABLE_NAME), COLUMN_NAME, 'IsIdentity') = 0
    """)
    cols_operativo = [row.COLUMN_NAME for row in cursor.fetchall()]
    
    # âš ï¸ AQUI ESTA LA MAGIA: Le agregamos "h." a cada columna para que SQL no se confunda
    cols_dinamicas_str = ", ".join(cols_operativo)
    cols_select_str = ", ".join([f"h.{col}" for col in cols_operativo])
    
    query_operativo = f"""
    TRUNCATE TABLE {TABLA_OPERATIVA};

    WITH UltimosCortes AS (
        SELECT TOP (2) fecha_corte
        FROM {TABLA_HISTORICO}
        GROUP BY fecha_corte
        ORDER BY fecha_corte DESC
    )
    INSERT INTO {TABLA_OPERATIVA} ({cols_dinamicas_str})
    SELECT {cols_select_str}
    FROM {TABLA_HISTORICO} AS h
    INNER JOIN UltimosCortes AS c ON c.fecha_corte = h.fecha_corte;
    """
    cursor.execute(query_operativo)
    conn.commit()
    
    print("ðŸŽ‰ Â¡Proceso finalizado con Ã©xito!")
    
    cursor.close()
    conn.close()

# ================================
# EJECUTAR CARGA FINAL
# ================================
subir_directo_a_tablas_finales(df_excel, FECHA_CORTE)

