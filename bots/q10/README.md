# Bot de descargas v5 (configuración en Excel)

Es la **v3** (Oxford, Q10 y Macmillan, con el arreglo de la barra nueva de Q10) con un solo cambio:
los `Config <Sistema>.txt` y `Credenciales <Sistema>.txt` se reemplazan por **una planilla**,
`Bot Descargas.xlsx`, que va en la carpeta del proyecto (o al lado del `.exe`). Lo que hace el bot en
cada sistema no cambió; el historial de Q10 está en `botv3/README.md`.

## La planilla

| Hoja | Qué tiene |
|---|---|
| Inicio | Instrucciones para el usuario |
| Accesos | Una fila por sistema: `Usar` (Sí/No = aparece en el menú), Usuario, Contraseña, Link |
| Oxford | Ajustes (ID, Scores, Show figures as, Show scores for) + tabla **Clase** |
| Q10 | Ajustes (Rol, Formato, Menú, Submenú, Buscar, Acción) + tablas **Informe** y **Filtros** |
| Macmillan | Ajuste Recurso + tablas **Libro**, **Nivel** y **Clase** |

- Cada tabla es una tabla de Excel en sus propias columnas: al agregar filas no se pisan.
- `Usar = No` reemplaza al `#` de los `.txt`: la fila queda escrita pero el bot la salta. Vacío = Sí.
- Las listas (clases, informes, libros) van **una por fila**, no separadas por coma.
- En los **valores** de los filtros de Q10 siguen las mismas reglas: coma = un reporte por valor,
  `Todos`, punto y coma = varias opciones en el mismo reporte.
- Las celdas se guardan como texto, para que Excel no convierta fechas ni quite ceros.

`core/planilla.py` define las hojas una sola vez (`HOJAS`) y de ahí salen la plantilla (`crear`)
y la lectura (`Planilla.leer_hoja`), que devuelve el mismo diccionario que devolvía `leer_txt`. Por
eso las clases de configuración de cada sistema solo cambiaron sus mensajes (`desde_txt` → `desde_hoja`).

## Pasar los .txt a la planilla

```
..\.venv\Scripts\python.exe pasar_txt_a_excel.py                         # carpeta del proyecto
..\.venv\Scripts\python.exe pasar_txt_a_excel.py "<carpeta>" --sin-claves   # para compartir
```

Solo pasa las líneas activas (lo comentado con `#` no). Quita las clases repetidas. No toca los `.txt`.
Si la planilla no existe, el bot la crea vacía y explica qué llenar.

## Ejecutar

- Doble clic en `Ejecutar botv5.bat` (usa el `.venv` del proyecto; necesita `openpyxl`).
- `.exe`: `..\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name "Bot Descargas v5" bot.py`
  desde esta carpeta.
- El Excel tiene que estar **guardado y cerrado** al correr el bot.
