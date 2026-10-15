# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Download automation for Centro Colombo Americano (Bogotá): Playwright bots that log into
**Oxford English Hub**, **Q10 Académico** and **Macmillan Education Everywhere**, download
progress/report files, and (separately) Jupyter notebooks that transform them with pandas and load
them into SQL Server (`rendimiento_academico`). End users are non-developers without Python; they
use PyInstaller `.exe` files. Code, comments, UI text and log messages are in **Spanish** — keep it that way.

## Commands

The global `python` is the Microsoft Store stub — always use the project venv (Python 3.13).
There is no test suite, linter config or `requirements.txt`; verify changes by running the app/bot.

```
.venv\Scripts\python.exe aplicacion\main.py                  # unified desktop app (or "Abrir herramientas Colombo.bat")
.venv\Scripts\python.exe herramientas\oxford\app_oxford.py    # each tool UI also runs standalone
.venv\Scripts\python.exe bots\q10\bot.py Q10                 # a bot directly (system name as arg)
.venv\Scripts\python.exe bots\oxford\automatizar_oxford.py [--todas]
.venv\Scripts\python.exe empaquetado\construir_exe.py [app bot_q10 bot_macmillan bot_oxford]   # build .exe into .exe\
"Descargar y cargar.bat" [verificar|transformacion]           # unattended pipeline: botv4 + notebooks -> SQL
.venv\Scripts\python.exe botv4\bot.py --auto                 # botv4 alone, reads "Config Bot.txt"
```

Bot scripts re-launch themselves with `.venv\Scripts\python.exe` if started with another interpreter.
`construir_exe.py` builds in `%TEMP%\colombo_construccion` on purpose (OneDrive locks thousands of temp files).
`git` is not on PATH in PowerShell here.

## Architecture

Three layers, each per system (q10 / macmillan / oxford):

1. **`aplicacion/main.py`** — CustomTkinter shell: header with logo, Home with one card per entry in
   `HERRAMIENTAS`, navigation. Views are created lazily and kept alive (going back to the menu does
   not stop a running bot). Brand colors/fonts live **only** in `aplicacion/tema_colombo.py` (`Marca`).
2. **`herramientas/<sistema>/`** — config UIs, each a Frame (`VistaQ10`, `VistaMacmillan`,
   `VistaOxford`) honoring the contract `TITULO`, `SUBTITULO`, `hay_proceso_activo()`, `cerrar()`.
   Adding a tool = new `Vista*` class with that contract + an entry in `HERRAMIENTAS` (and a
   `--hidden-import`/`--paths` in `construir_exe.py`). Each UI writes the bot's config, then launches
   the bot via `subprocess`: `Bot <Sistema>.exe` next to the app when frozen, else the script in `bots/`.
3. **`bots/<sistema>/`** — the Playwright bots. They are **separate engines with colliding package
   names** (`core`, `sistemas`), which is why each is a separate `.exe` and why `sys.path` is set per bot:
   - `bots/q10/` = the "v5" engine (POO + Page Object). Config comes from the Excel workbook
     `datos/Bot Descargas.xlsx`; sheet layout is defined once in `core/planilla.py` (`HOJAS`). The Q10
     UI writes only the Q10 sheet.
   - `bots/macmillan/automatizar_macmillan.py` imports the v3 engine from `motor_botv3/`; profiles
     come from `herramientas/macmillan/*.json` (`config_macmillan_activo.json`).
   - `bots/oxford/automatizar_oxford.py` is a single script reading `Config Oxford.txt` /
     `Credenciales Oxford.txt` from the **project root**.

Path convention used everywhere: `ES_EXE = getattr(sys, "frozen", False)`; when frozen, all files
(config, `Descargas/`, `Capturas/`) resolve next to the `.exe`, otherwise relative to the project
root. Frozen bots set `PLAYWRIGHT_BROWSERS_PATH` / use installed Chrome→Edge channels so the exe
does not bundle a browser. Downloads go to `Descargas/<Sistema>/`, failure screenshots to `Capturas/`.

### Root-level files that must stay where they are

`Descargar y cargar.bat`, `botv4/`, `Config *.txt`, `Credenciales *.txt`, `Config Bot.txt`,
`Validacion Oxford.ipynb`, `Validacion Macmillan.ipynb`, `Registros/`, `avance_*.csv` form the
unattended pipeline (possibly run by Windows Task Scheduler) — don't move them. botv4 exit codes:
0 ok / 1 some system failed / 2 bad config; the .bat adds 3 = notebook/SQL load failed. Its Q10 is
older than `bots/q10` (missing the "Informes" dropdown fix). `archivo/` holds old versions;
`archivo/MOVIMIENTOS.csv` logs every file move — append to it if you relocate files.

## Gotchas

- Oxford's Progress Tracker ".csv" is **UTF-16 LE with BOM, tab-separated**, two header rows; teacher/material only on the "Class Average" row.
- `.txt` configs are `Clave : valor` lines read with `utf-8-sig`; `#` comments out a line.
- `Bot Descargas.xlsx` must be saved and closed while a bot runs.
- Q10 list screens: `»` pagination jumps a block of 5 pages; rows have two links to `/Detalle` (use `td:first-child a`); search box is `#texto`; AJAX sections need waits on an element, never fixed sleeps. Q10 may show a captcha (fails fast in unattended mode via `core/modo.py::AUTOMATICO`).
- SQL load (notebooks): choose the newest "ODBC Driver NN for SQL Server" by preference list, not alphabetically; `fast_executemany` only works with those drivers.
