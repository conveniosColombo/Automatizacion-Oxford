# Herramientas de automatización - Centro Colombo Americano

Para abrir la aplicación: doble clic en **`Abrir herramientas Colombo.bat`**.

## Qué hay en cada carpeta

| Carpeta | Para qué sirve |
|---|---|
| `aplicacion/` | Menú principal, encabezado con logo, colores y tipografía de la marca (`tema_colombo.py`). |
| `herramientas/` | Las pantallas de configuración: `q10/`, `macmillan/` y `oxford/` (con sus perfiles guardados). |
| `bots/` | Los robots que entran a cada sistema y descargan: `q10/`, `macmillan/` y `oxford/`. |
| `datos/` | Lo que leen los robots: `Bot Descargas.xlsx`, `catalogo_q10.json` y las plantillas. |
| `Descargas/` · `Capturas/` | Lo que bajan los robots y las capturas cuando algo falla. |
| `analisis/` | Cuadernos y reportes de transformación y validación, e insumos. |
| `otras_herramientas/` | Herramientas aparte, como la activación de códigos de Oxford. |
| `.exe/` | Los ejecutables listos para usar: la aplicación unificada y los tres robots (ver su `LEEME.txt`). |
| `empaquetado/` | Script que genera los `.exe`: `.venv\Scripts\python.exe empaquetado\construir_exe.py`. |
| `archivo/` | Versiones viejas y pruebas. Nada se borró; `MOVIMIENTOS.csv` lista cada cambio de lugar. |

## Proceso automático (se dejó en la raíz a propósito)

Estos elementos trabajan juntos y esperan estar en la raíz, así que **no se movieron**:
`Descargar y cargar.bat`, `botv4/`, `Config Bot.txt`, `Config *.txt`, `Credenciales *.txt`,
`Validacion Oxford.ipynb`, `Validacion Macmillan.ipynb`, `Registros/`, `avance_*.csv`.
Si ya no se usan, se pueden mover a `archivo/`. Si se usan en una tarea programada de Windows,
hay que revisar esa tarea antes de moverlos.

## Dónde cambiar la marca
Colores y tipografía: solo en `aplicacion/tema_colombo.py`.

