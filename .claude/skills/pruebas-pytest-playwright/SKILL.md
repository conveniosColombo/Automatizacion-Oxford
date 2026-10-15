---
name: pruebas-pytest-playwright
description: Usa esta skill siempre que el usuario pida crear, escribir, agregar o modificar pruebas (tests) automatizadas con pytest y/o Playwright para este proyecto (bots de Oxford, Q10, Macmillan o la app unificada en aplicacion/). Asegura que las pruebas queden guardadas en la carpeta tests/ en la raiz del proyecto, dentro de la subcarpeta del sistema correspondiente, y nunca dentro de bots/<sistema>/. Dispara con frases como "crea un test para...", "agrega una prueba de...", "escribe un test con playwright para el login", "testea la funcion X", "prueba que el bot haga Y", aunque el usuario no mencione pytest explicitamente.
---

# Pruebas con pytest y Playwright

Este proyecto tiene varios bots (Oxford, Q10, Macmillan) que viven en `bots/<sistema>/` y
**colisionan entre si en los nombres de sus paquetes** (`core`, `sistemas`), por eso cada uno
es un .exe separado y manipula `sys.path` por su cuenta. Meter pruebas dentro de esas carpetas
rompe esa separacion y puede arrastrar archivos de test al empaquetado con PyInstaller.

Por eso: **toda prueba nueva va en `tests/`, en la raiz del proyecto, nunca junto al codigo del bot.**

## Donde guardar cada prueba

```
tests/
├── conftest.py              # fixtures compartidas por todos los sistemas
├── oxford/
│   ├── conftest.py          # fixtures propias de Oxford (ej. credenciales de prueba, pagina logueada)
│   ├── test_usuarios.py
│   └── test_<algo>.py
├── q10/                      # crear igual que oxford/ cuando haga falta
│   └── conftest.py
└── macmillan/                 # idem
    └── conftest.py
```

Reglas:
- Una subcarpeta por sistema (`oxford`, `q10`, `macmillan`); si la prueba es de la app
  unificada (`aplicacion/`), va en `tests/aplicacion/`.
- Nombre de archivo: `test_<tema>.py` (ej. `test_usuarios.py`, `test_descarga_csv.py`,
  `test_login.py`), todo en minusculas y snake_case, igual que el resto del codigo.
- Fixtures que solo aplican a un sistema van en el `conftest.py` de esa subcarpeta;
  fixtures genericas (ej. una fixture de navegador reutilizable) van en `tests/conftest.py`.
- Si una prueba necesita importar algo de `bots/<sistema>/`, hazlo con una importacion
  explicita del archivo (ej. `importlib` o agregando esa ruta puntual con `sys.path.insert`
  dentro del `conftest.py` de esa subcarpeta) en vez de depender de que pytest descubra
  ambos bots a la vez — asi se evita el choque de paquetes `core`/`sistemas`.
- Nunca crear archivos `test_*.py` ni `conftest.py` dentro de `bots/`, `aplicacion/`,
  `herramientas/`, `botv4/` o `empaquetado/`.

## Como correr las pruebas

Siempre con el Python del venv del proyecto (igual que el resto del repo):

```
.venv\Scripts\python.exe -m pytest tests/                  # todas las pruebas
.venv\Scripts\python.exe -m pytest tests/oxford/ -v         # solo Oxford, detallado
.venv\Scripts\python.exe -m pytest tests/oxford/test_usuarios.py::test_algo
```

Si `pytest` o `pytest-playwright` no estan instalados en `.venv`, instalarlos ahi mismo
(`.venv\Scripts\python.exe -m pip install pytest pytest-playwright`) — nunca con el Python
global del sistema (es el stub de Microsoft Store, sin Playwright).

## Estilo de las pruebas

- Comentarios, nombres de funciones y mensajes en **espanol**, igual que el resto del
  proyecto (ver CLAUDE.md).
- Las pruebas que dependen de credenciales reales (login a Oxford/Q10/Macmillan) deben
  usar variables de entorno o un archivo de prueba separado, nunca las credenciales de
  produccion (`Credenciales Oxford.txt`) ni commitear secretos.
- Si la prueba usa Playwright para interactuar con la pagina real, documentar en un
  comentario corto que requiere conexion/credenciales validas, para que quien la corra
  sepa que no es una prueba puramente local.

## Al terminar

Despues de crear o modificar una prueba, correrla para confirmar que pasa (o que falla
por la razon esperada, si es TDD) antes de darla por terminada.
