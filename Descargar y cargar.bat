@echo off
REM ===========================================================================
REM  PROCESO COMPLETO: descarga (bot v4) y carga a SQL Server (cuadernos)
REM
REM  1. Bot v4     -> baja lo que diga "Config Bot.txt" (Oxford y Macmillan)
REM  2. Cuadernos  -> "Validacion Oxford" y "Validacion Macmillan" transforman
REM                   lo bajado y lo cargan en la base rendimiento_academico
REM
REM  Uso:
REM     doble clic                                todo el proceso
REM     "Descargar y cargar.bat" verificar        solo revisa que este todo listo
REM     "Descargar y cargar.bat" transformacion   solo carga (sin descargar)
REM
REM  Codigos de salida (los lee el Programador de tareas):
REM     0 = todo bien
REM     1 = algun sistema no se pudo descargar (la carga si se hizo)
REM     2 = falta algo para poder trabajar (python, nbconvert, cuadernos)
REM     3 = fallo la transformacion o la carga a SQL
REM ===========================================================================
setlocal
cd /d "%~dp0"

REM Si se abrio con doble clic hay que esperar al final; si no, la ventana se
REM cierra sola y no se alcanza a leer nada. Lanzado por el Programador de
REM tareas o desde una consola, no espera.
set "ESPERAR="
echo "%cmdcmdline%" | find /i "%~nx0" >nul 2>&1 && set "ESPERAR=1"

set "PY_BOT=.venv\Scripts\python.exe"
set "PY_DATOS=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
set "SEGUNDOS_POR_CELDA=1800"
set "CODIGO_BOT=0"
set "CODIGO_DATOS=0"
set "SALIDA=0"

echo ============================================================
echo   DESCARGAR Y CARGAR
echo ============================================================
echo Carpeta: %CD%
echo.

REM ------------------------------------------------ revisar que este todo ---
if not exist "%PY_BOT%" (
    echo FALTA el entorno del bot: %PY_BOT%
    echo    py -3.13 -m venv .venv
    echo    .venv\Scripts\python.exe -m pip install playwright
    set "SALIDA=2"
    goto :fin
)

if not exist "%PY_DATOS%" for /f "usebackq delims=" %%p in (`py -3.13 -c "import sys;print(sys.executable)" 2^>nul`) do set "PY_DATOS=%%p"
if not exist "%PY_DATOS%" (
    echo FALTA el Python de los cuadernos ^(el que tiene pandas y pyodbc^).
    set "SALIDA=2"
    goto :fin
)

"%PY_DATOS%" -c "import nbconvert" 2>nul
if errorlevel 1 (
    echo FALTA nbconvert, que es lo que ejecuta los cuadernos sin abrirlos.
    echo Instalalo UNA sola vez, copiando esta linea en una consola:
    echo.
    echo    "%PY_DATOS%" -m pip install nbconvert
    echo.
    set "SALIDA=2"
    goto :fin
)

for %%C in ("Validacion Oxford.ipynb" "Validacion Macmillan.ipynb") do if not exist "%%~C" (
    echo FALTA el cuaderno %%~C
    set "SALIDA=2"
    goto :fin
)

if not exist "Registros" mkdir "Registros"
for /f "usebackq delims=" %%s in (`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"`) do set "SELLO=%%s"
set "RESUMEN=Registros\%SELLO%_proceso.log"

if /i "%~1"=="verificar" (
    echo TODO LISTO para correr el proceso completo.
    echo    bot:       %PY_BOT%
    echo    cuadernos: %PY_DATOS%
    echo    registros: %CD%\Registros
    goto :fin
)

echo Registro de esta corrida: %RESUMEN%
echo PROCESO COMPLETO %DATE% %TIME% > "%RESUMEN%"

REM ----------------------------------------------------- 1. las descargas ---
if /i "%~1"=="transformacion" goto :sin_descargas

echo.
echo --- 1 de 3: descargando con el bot v4 ---
"%PY_BOT%" botv4\bot.py --auto
set "CODIGO_BOT=%ERRORLEVEL%"
echo Bot v4: codigo %CODIGO_BOT% >> "%RESUMEN%"

if "%CODIGO_BOT%"=="2" goto :bot_mal
if not "%CODIGO_BOT%"=="0" echo AVISO: algun sistema no se descargo bien. Se sigue con lo que si llego.
goto :transformar

:bot_mal
echo El bot no pudo arrancar ^(problema de configuracion^). No se sigue con la carga.
echo ABORTADO: configuracion del bot >> "%RESUMEN%"
set "SALIDA=2"
goto :fin

:sin_descargas
echo.
echo --- Descargas SALTADAS ^(se pidio solo la transformacion^) ---
echo Descargas: saltadas >> "%RESUMEN%"

REM ------------------------------------------- 2 y 3. transformar y cargar ---
:transformar
call :cuaderno "Validacion Oxford.ipynb"    "2 de 3"
call :cuaderno "Validacion Macmillan.ipynb" "3 de 3"

echo.
echo ============================================================
echo   RESUMEN
echo ============================================================
if "%CODIGO_BOT%"=="0"   (echo    descargas:    OK) else (echo    descargas:    con fallas ^(codigo %CODIGO_BOT%^))
if "%CODIGO_DATOS%"=="0" (echo    carga a SQL:  OK) else (echo    carga a SQL:  CON ERRORES)
echo    detalle:      %RESUMEN%
echo    registros en: %CD%\Registros
echo.
type "%RESUMEN%"

if not "%CODIGO_DATOS%"=="0" set "SALIDA=3"
if "%SALIDA%"=="0" if not "%CODIGO_BOT%"=="0" set "SALIDA=1"
goto :fin

REM ---------------------------------------------------------------------------
REM  Ejecuta un cuaderno sin abrirlo. El cuaderno original NO se toca: la copia
REM  ejecutada, con todas sus salidas, queda en Registros como comprobante.
:cuaderno
echo.
echo --- %~2: %~1 ---
set "EJECUTADO=Registros\%SELLO%_%~n1.ipynb"
REM --allow-errors: aunque una celda falle, el cuaderno ejecutado SE GUARDA. Sin esto no
REM queda ninguna evidencia de que paso. Despues se revisa si alguna celda dejo error.
"%PY_DATOS%" -m nbconvert --to notebook --execute "%~1" --allow-errors --output-dir "Registros" --output "%SELLO%_%~n1.ipynb" --ExecutePreprocessor.timeout=%SEGUNDOS_POR_CELDA% --ExecutePreprocessor.kernel_name=python3
if errorlevel 1 (
    echo    FALLO: no se pudo ni ejecutar %~1
    echo %~1: FALLO ^(no se pudo ejecutar^) >> "%RESUMEN%"
    set "CODIGO_DATOS=3"
    goto :eof
)

"%PY_DATOS%" -c "import json,sys;c=json.load(open(sys.argv[1],encoding='utf-8'))['cells'];e=[i for i,x in enumerate(c,1) if any(o.get('output_type')=='error' for o in x.get('outputs',[]))];print('   celdas con error:',e) if e else None;sys.exit(1 if e else 0)" "%EJECUTADO%"
if errorlevel 1 (
    echo    FALLO: %~1   ^(abre %EJECUTADO% para ver el detalle^)
    echo %~1: FALLO >> "%RESUMEN%"
    set "CODIGO_DATOS=3"
) else (
    echo    OK: %~1
    echo %~1: OK >> "%RESUMEN%"
)
goto :eof

REM ---------------------------------------------------------------------------
:fin
if defined ESPERAR (
    echo.
    echo ------------------------------------------------------------
    pause
)
exit /b %SALIDA%
