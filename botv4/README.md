# Bot de descargas v4 — el que corre solo

Misma lógica de la v3 (POO + Page Object, Oxford / Macmillan / Q10). Lo que agrega la v4 es
todo lo necesario para que trabaje **sin una persona delante**, en una máquina virtual.

## Las tres formas de usarlo

| Cómo | Qué hace |
|---|---|
| `Ejecutar botv4.bat` | El menú de siempre: pregunta qué sistema y deja el navegador abierto al final |
| `Ejecutar botv4 automatico.bat` | Lee `Config Bot.txt`, corre esos sistemas y se cierra solo |
| `bot.py Oxford` | Un sistema puntual, con menú desactivado |

## Qué cambia cuando corre solo

| | |
|---|---|
| **Nada pregunta nada** | No hay menú ni "presiona Enter". Si algo necesita una mano (el captcha de Q10), se reporta como falla y sigue con el resto |
| **Un proceso por sistema** | Si Macmillan se cuelga, Oxford no se ve afectado |
| **Tope de tiempo** | `Minutos por sistema` corta el intento; la tarea nunca queda corriendo para siempre |
| **Reintentos** | Las caídas pasajeras de las páginas se reintentan solas |
| **Registro en archivo** | Todo queda en `Registros\<fecha>_<sistema>.log`, con la hora en cada línea. Los de más de 30 días se borran solos |
| **Capturas** | Al terminar cada sistema se guarda una imagen de la pantalla en `Capturas`, que es lo único que se puede mirar después |
| **Código de salida** | `0` todo bien, `1` algún sistema falló, `2` problema de configuración. Es lo que lee el Programador de tareas |

Al final imprime un resumen así:

```
===== RESUMEN =====
  Oxford       OK                  12 archivo(s)     3.4 min
  Macmillan    FALLO                0 archivo(s)     0.6 min   (intentos: 2)
```

## `Config Bot.txt`

Va en la carpeta del proyecto, al lado de los `Config <Sistema>.txt`:

```
Sistemas : Oxford, Macmillan     # en este orden; "Todos" = los que tengan su Config
Sin ventana : No                 # Si = el navegador no se muestra (obligatorio si nadie inicia sesion)
Reintentos : 1                   # 0 a 5
Minutos por sistema : 30         # tope de tiempo por sistema
```

Si el archivo no existe, el bot corre **todos** los sistemas configurados, con ventana visible.

## Montarlo en la máquina virtual

1. **Python 3.13** y, en la carpeta del proyecto, el entorno virtual con Playwright:

   ```
   py -3.13 -m venv .venv
   .venv\Scripts\python.exe -m pip install playwright
   .venv\Scripts\python.exe -m playwright install chromium
   ```

2. **Copiar** la carpeta del proyecto (con `botv4`, los `Config *.txt` y los `Credenciales *.txt`).
   Las credenciales van en texto plano: la VM debe tener el acceso restringido.

3. **Probar a mano una vez**, con ventana, para ver que todo entra bien:

   ```
   botv4\Ejecutar botv4 automatico.bat
   ```

4. **Programar la tarea** (una vez, desde una consola como administrador). Ejemplo: todos los
   días a las 6:00 a.m.

   ```
   schtasks /create /tn "Bot descargas" /tr "\"C:\ruta\al\proyecto\botv4\Ejecutar botv4 automatico.bat\"" /sc daily /st 06:00 /rl highest
   ```

   En las propiedades de la tarea:
   - **"Ejecutar solo cuando el usuario haya iniciado sesión"** → el navegador se ve; es lo más
     parecido a correrlo a mano y lo más estable.
   - **"Ejecutar tanto si el usuario inició sesión como si no"** → no hay escritorio, así que
     hay que poner `Sin ventana : Si` en `Config Bot.txt`.

5. **Revisar** después de la primera corrida automática: `Registros\<fecha>_resumen.log` dice
   cómo le fue a cada sistema, y cada uno tiene su propio `.log` con el detalle.

## Estructura

```
botv4\
├── bot.py                 Menú, modo automático (un proceso por sistema) y códigos de salida
├── core\
│   ├── archivos.py        Carpeta de trabajo, leer .txt, Credenciales, descargas y capturas
│   ├── config_bot.py      QUÉ pide "Config Bot.txt"               (ConfigBot)
│   ├── registro.py        Copia todo lo impreso a Registros\*.log
│   ├── modo.py            AUTOMATICO: si corre solo, nada puede quedarse preguntando
│   ├── navegador.py       Abrir Chrome (o Edge), con o sin ventana
│   ├── errores.py         Formato de los mensajes FALLO
│   ├── pagina.py          Clase base Pagina (Page Object)
│   └── sistema.py         Clase base Sistema
└── sistemas\              oxford\, macmillan\, q10\ — cada uno con config, paginas y sistema
```

## Límites conocidos

- **El captcha de Q10** no se puede resolver solo. Si aparece, ese sistema falla con un mensaje
  claro y esa vez hay que bajarlo a mano. Oxford y Macmillan no lo piden.
- Si un sistema **se pasa del tiempo**, se corta el proceso; puede quedar una ventana de
  navegador abierta en la VM. No afecta a la corrida siguiente, que abre la suya.
- Las descargas van a `Descargas\<Sistema>` dentro de la carpeta del proyecto. Si esa carpeta
  está en OneDrive, conviene que en la VM esté **siempre disponible sin conexión**, para que
  leer y escribir no dependa de la sincronización.
