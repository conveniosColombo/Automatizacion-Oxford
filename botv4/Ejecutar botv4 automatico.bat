@echo off
REM Corre el bot sin preguntar nada, segun "Config Bot.txt".
REM Es el que se pone en el Programador de tareas: no abre menus y no espera Enter.
REM Codigos de salida:  0 = todo bien   1 = algun sistema fallo   2 = problema de configuracion
cd /d "%~dp0"
"..\.venv\Scripts\python.exe" bot.py --auto %*
exit /b %ERRORLEVEL%
