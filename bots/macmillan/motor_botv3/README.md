# Bot de descargas v3 (POO + Page Object)

Misma estructura de la v2, con Q10 rehecho según el relevamiento de los **71 informes** del menú
Informes (`q10_catalogo_completo_informes.md`). Usa los mismos `Config`, `Credenciales`,
`Descargas` y `Capturas` de la carpeta del proyecto.

## Qué cambió frente a la v2 (solo Q10)

| Antes (v2) | Ahora (v3) |
|---|---|
| Después de abrir el informe, esperaba un tiempo fijo | Espera el formulario real (`#formReportes` / `#form0`), que Q10 inyecta por AJAX sin cambiar la URL |
| El informe se buscaba solo por su texto | También por su dirección (`Informes : ListadoCursos`), que no cambia, y `Estudiantes (Comunidad en Excel)` para los nombres repetidos |
| Botón de pedir el reporte: `#generar-reporte-btn` | Por orden: `#generar-excel-btn`, `#generar-reporte-btn`, `#programar-reporte-btn` y los botones por título |
| Al cambiar una lista, esperaba un tiempo fijo | Espera a que terminen las llamadas AJAX que recargan la lista dependiente |
| Solo manejaba listas desplegables | Listas simples y **múltiples**, **radios**, **interruptores**, **grupos de casillas**, **rangos de fechas** (con presets) y **autocompletados de personas** |
| Solo entendía una forma de recibir el archivo | Las cuatro familias de Q10: **A** visor PDF (lista `#exportSelect` → XLSX, espera a que el PDF tenga páginas y cierra el visor), **B** tarea en segundo plano (Generando → "se ha generado exitosamente" → Abrir reporte), **C** descarga directa y **D** informes que solo pintan el resultado en pantalla (avisa que no generan archivo) |
| — | Las fechas se ven DD/MM/YYYY pero Q10 las guarda MM/DD/YYYY: el bot hace la conversión |
| — | Si el "Filtrar por" tiene opciones llamadas igual que un filtro (Programa, Curso), ya no las confunde |
| Con varios informes seguidos, solo salía el primero: el formulario se inyecta dentro de `/Informes` y el bot creía que seguía en el menú | Para saber si está en el menú mira que haya enlaces `a.reportes`, no la dirección; y si el botón "Informes" de la barra no lo devuelve (por ejemplo tapado por el visor), entra directo a `/Informes` |
| Tras "Abrir reporte" esperaba un archivo que a veces no llega, porque lo que abre es el visor | Da el clic una sola vez y sigue vigilando: si aparece el visor, exporta desde ahí |
| Si el informe abría con el resultado de una corrida anterior, se habría bajado ese reporte viejo (con otros filtros) | Al abrir el informe, si aparece "El reporte se ha generado exitosamente" en vez del formulario, da clic en "Volver a generar" y espera el formulario limpio |
| Con varios valores, si el botón de pedir el informe quedaba bloqueado por el reporte anterior, ese valor se perdía | Espera a que aparezca "Volver a generar" (llega después del archivo) y, si aun así la pantalla no queda lista, reabre el informe antes del siguiente valor |
| Al final no se sabía qué faltó | Resumen por informe: descargados, los que Q10 devolvió sin datos y los que fallaron con el motivo |

Lo que ya funcionaba se mantiene igual: reponer los filtros después de "Volver a generar", el
menú **Exportar → XLSX** de los visores viejos (con teclado y clic por posición como respaldo),
**Sin resultados**, y la opción "Todos" (literal si existe en la lista, campo vacío si Q10 la toma
como todos, o uno por uno si no hay ninguna de las dos).

## Cómo se escriben los filtros en `Config Q10.txt`

```
Rol : Administrativo
Informes : Listado de cursos, Estudiantes (Comunidad en Excel), ListadoMatriculas
Formato : XLSX                     -> con qué formato exportar desde el visor (XLSX por defecto)

Sede - jornada : B2B - Única       -> lista: el texto tal como aparece en Q10
Programa : Todos                   -> Todos = un reporte por opción (o la opción "Todos" si existe)
Períodos : 2026-1; 2026-2          -> lista múltiple: varias opciones en un mismo reporte
Filtrar por : Curso                -> radios; escríbelo ANTES de los filtros que hace aparecer
Estado : Activos                   -> radios: el texto de la opción
¿Incluir archivados? : No          -> interruptor: Sí / No
Campos : Todos                     -> casillas: Todos, Ninguno, o lista separada con ';'
Campos : Documento; Nombre; Correo
Fechas : 01/09/2026 - 30/09/2026   -> rango escrito a mano (DD/MM/YYYY)
Fechas : Este mes                  -> o un preset del calendario (Hoy, Ayer, Últimos 7 días, Todas…)
Docente : JUAN PEREZ               -> autocompletar: escribe y el bot escoge de la lista
```

Reglas:

- El nombre del filtro es la etiqueta que se ve en el formulario (no importan mayúsculas, tildes ni el `*`).
- Un filtro que no exista en ese informe, o que esté escondido por el "Filtrar por", se salta con un aviso.
- La **coma** separa valores que generan **un reporte cada uno**; el **punto y coma** son varias
  opciones dentro de un mismo reporte (listas múltiples y `Campos`).
- Escribe los filtros en el mismo orden de la pantalla: cada lista carga sus opciones según la anterior.

## Estructura

```
botv3\
├── bot.py                 Clase Bot: menú, escoger sistemas y ejecutarlos
├── core\                  Piezas comunes
│   ├── archivos.py        Carpeta de trabajo, leer .txt, Credenciales, guardar descargas y capturas
│   ├── navegador.py       Abrir Chrome (o Edge)
│   ├── errores.py         Formato de los mensajes FALLO
│   ├── pagina.py          Clase base Pagina (Page Object)
│   └── sistema.py         Clase base Sistema
└── sistemas\
    ├── __init__.py        Registro de sistemas (SISTEMAS)
    ├── oxford\
    │   ├── config.py      QUÉ pide "Config Oxford.txt"      (ConfigOxford)
    │   ├── paginas.py     DÓNDE hacer clic, una clase por pantalla
    │   └── sistema.py     EN QUÉ ORDEN se hacen los pasos    (Oxford)
    ├── macmillan\         (ConfigMacmillan, páginas del MEE, Macmillan)
    └── q10\
        ├── config.py      (ConfigQ10)
        ├── paginas.py     LoginQ10, BarraQ10, PaginaInformes, FormularioInforme
        └── sistema.py     (Q10)
```

## Dónde tocar según el cambio

| Cambio | Archivo |
|---|---|
| Q10, Macmillan u Oxford cambió un botón o un campo | `sistemas\<sistema>\paginas.py`, en la clase de esa pantalla (constantes en MAYÚSCULAS) |
| Un tipo de filtro nuevo en Q10 | `sistemas\q10\paginas.py`, método `llenar()` |
| Agregar o quitar un paso | `sistemas\<sistema>\sistema.py`, método `ejecutar()` |
| Un dato nuevo en el Config | `sistemas\<sistema>\config.py` |
| Algo común a todos (descargas, navegador, .txt) | `core\` |
| Un sistema nuevo | Crear `sistemas\<nuevo>\` con los 3 archivos y registrarlo en `sistemas\__init__.py` |

## Agregar un sistema nuevo

1. `config.py`: una `@dataclass` con lo que pide su `Config <Nuevo>.txt` y un `desde_txt(datos)` que lo valide.
2. `paginas.py`: una clase por pantalla que herede de `Pagina`, con sus selectores y acciones.
   Cada acción que cambia de pantalla devuelve la clase de la pantalla siguiente.
3. `sistema.py`: una clase que herede de `Sistema` con `NOMBRE`, `leer_config()` y `ejecutar()`.
4. Sumarla en `sistemas\__init__.py` y crear `Config <Nuevo>.txt` y `Credenciales <Nuevo>.txt`.

## Ejecutar

- Doble clic en `Ejecutar botv3.bat` (usa el `.venv` del proyecto).
- `.exe`: `..\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name "Bot Descargas v3" bot.py`
  desde esta carpeta.
