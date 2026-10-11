# Bot de descargas v2 (POO + Page Object)

Hace lo mismo que el bot v1 (`..\bot.py`), pero organizado en clases para que sea más fácil de mantener.
Mientras se prueba, usa los mismos `Config`, `Credenciales`, `Descargas` y `Capturas` de la carpeta del proyecto.

## Estructura

```
botv2\
├── bot.py                 Clase Bot: menú, escoger sistemas y ejecutarlos
├── core\                  Piezas comunes
│   ├── archivos.py        Carpeta de trabajo, leer .txt, Credenciales, guardar descargas y capturas
│   ├── navegador.py       Abrir Edge (o Chrome)
│   ├── errores.py         Formato de los mensajes FALLO
│   ├── pagina.py          Clase base Pagina (Page Object)
│   └── sistema.py         Clase base Sistema
└── sistemas\
    ├── __init__.py        Registro de sistemas (SISTEMAS)
    ├── oxford\
    │   ├── config.py      QUÉ pide "Config Oxford.txt"      (ConfigOxford)
    │   ├── paginas.py     DÓNDE hacer clic, una clase por pantalla
    │   └── sistema.py     EN QUÉ ORDEN se hacen los pasos    (Oxford)
    └── q10\
        ├── config.py      (ConfigQ10)
        ├── paginas.py     LoginQ10, BarraQ10, PaginaInformes, FormularioInforme
        └── sistema.py     (Q10)
```

## Dónde tocar según el cambio

| Cambio | Archivo |
|---|---|
| Q10 u Oxford cambió un botón o un campo | `sistemas\<sistema>\paginas.py`, en la clase de esa pantalla (constantes en MAYÚSCULAS) |
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

- Doble clic en `Ejecutar botv2.bat` (usa el `.venv` del proyecto).
- `.exe`: `..\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name "Bot Descargas v2" bot.py`
  desde esta carpeta.
