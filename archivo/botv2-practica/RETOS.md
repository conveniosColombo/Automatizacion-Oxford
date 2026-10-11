# Retos: construye el bot v2 por tu cuenta

Vas a rehacer el bot v2 paso a paso, en esta carpeta (`botv2-practica`). Cada reto es pequeño y se puede
comprobar solo.

**Cómo trabajar**
1. Lee el reto y crea el archivo que pide, con los nombres exactos que indica (el comprobador los busca así).
2. Doble clic en `Comprobar retos.bat`. Te dice qué pasó y qué falta.
3. Si te atascas, mira el archivo equivalente en la carpeta `..\botv2` (esa es la solución).

**Reglas del juego**
- Los nombres de clases, funciones y parámetros deben ser los que dice cada reto. Lo demás (comentarios,
  orden interno, variables) va como quieras.
- No copies y pegues de una: escribe y prueba. Si algo falla, el mensaje del comprobador te dice qué esperaba.
- Los retos 9, 10, 14 y 15 no se pueden comprobar solos, porque necesitan iniciar sesión de verdad.
  Ahí la prueba es correr el bot y ver que haga lo mismo que la versión que ya funciona.

La estructura final debe quedar así:

```
botv2-practica\
├── bot.py
├── core\
│   ├── __init__.py
│   ├── archivos.py
│   ├── errores.py
│   ├── navegador.py
│   ├── pagina.py
│   └── sistema.py
└── sistemas\
    ├── __init__.py
    ├── q10\      __init__.py · config.py · paginas.py · sistema.py
    └── oxford\   __init__.py · config.py · paginas.py · sistema.py
```

---

## Bloque 1 — Leer los archivos de configuración

### Reto 1: `core\archivos.py`, la carpeta de trabajo y `leer_txt`

Crea `core\__init__.py` (puede tener solo un comentario) y `core\archivos.py` con:

- **`ES_EXE`**: `True` si el programa corre como `.exe`. Pista: `getattr(sys, "frozen", False)`.
- **`CARPETA`**: la carpeta donde están los `.txt`. Si es `.exe`, la carpeta del ejecutable
  (`Path(sys.executable).resolve().parent`). Si no, la carpeta del proyecto, que es la que está dos niveles
  arriba de este archivo. Pista: `Path(__file__).resolve().parents[2]`.
- **`leer_txt(nombre)`**: recibe el nombre de un `.txt` que está en `CARPETA` y devuelve un diccionario.
  - Cada línea con `:` se parte en clave y valor, por el **primer** `:`.
  - Las claves van en minúscula y sin espacios sobrantes; los valores también sin espacios sobrantes.
  - Las líneas que empiezan con `#` se ignoran.
  - Si el archivo no existe, lanza `FileNotFoundError` con un mensaje claro.
  - Lee con `encoding="utf-8-sig"` (así no estorba la marca invisible que a veces pone el Bloc de notas).

### Reto 2: dos ayudas de texto

En `core\archivos.py` agrega:

- **`separar_lista(valor)`**: `"a, b , c"` → `["a", "b", "c"]`. Sin espacios sobrantes y sin vacíos.
- **`es_plantilla(valor)`**: `True` si el texto es de una plantilla sin llenar, o sea si empieza por
  `escribe_aqui` o por `coloca aqu`, sin importar mayúsculas. Pista: `str.startswith` acepta una tupla.

### Reto 3: la clase `Credenciales`

En `core\archivos.py`, una `@dataclass` llamada **`Credenciales`** con tres campos: `usuario`, `clave`, `link`.

Agrega el método de clase **`de_sistema(cls, sistema)`**, que:
- lee `Credenciales <sistema>.txt` con `leer_txt`,
- si falta `user`, `password` o `link`, o si alguno es una plantilla, lanza `ValueError` con un mensaje que
  diga cuáles faltan, por ejemplo: `Completa user, password en 'Credenciales Q10.txt'`,
- si está todo bien, devuelve un `Credenciales`.

Pista: `@classmethod` y `return cls(usuario=..., clave=..., link=...)`.

### Reto 4: guardar lo que se descarga

En `core\archivos.py`:

- **`nombre_archivo(texto)`**: reemplaza por `_` todo lo que no sea letra, número, punto o guion.
  Pista: `re.sub(r"[^\w.-]+", "_", texto)`.
- **`guardar_descarga(descarga, sistema, prefijo)`**: guarda en
  `CARPETA\Descargas\<sistema>\<fecha>_<prefijo><extensión>` y devuelve la ruta.
  - La fecha va como `2026-09-16_0930`. Pista: `f"{datetime.now():%Y-%m-%d_%H%M}"`.
  - La extensión sale de `descarga.suggested_filename`. Pista: `Path(...).suffix`.
  - Crea la carpeta si no existe (`destino.parent.mkdir(parents=True, exist_ok=True)`), porque
    `save_as` **no** la crea.
- **`captura(page, nombre)`**: guarda una foto en `CARPETA\Capturas\<nombre>` y devuelve la ruta.
  Pista: `page.screenshot(path=str(ruta))`.

---

## Bloque 2 — Las bases

### Reto 5: `core\navegador.py` y `core\errores.py`

- **`abrir_navegador(playwright, visible=True)`**: intenta abrir Edge (`channel="msedge"`); si falla,
  Chrome (`channel="chrome"`); si falla, el navegador propio de Playwright. Usa
  `headless=not visible` y `slow_mo=300`.
- **`resumen(error)`** en `errores.py`: devuelve `"TipoDeError: primera línea del mensaje"`.
  Ojo: hay errores sin mensaje, y ahí no debe romperse.

### Reto 6: `core\pagina.py`, la clase base de las pantallas

Clase **`Pagina`** con:
- `__init__(self, page)`: guarda la pestaña en `self.page`.
- `esperar(self, milisegundos)`: pausa. Pista: `self.page.wait_for_timeout(...)`.
- `captura(self, nombre)`: usa la función del reto 4.
- `texto_exacto(texto)` (estático): devuelve un patrón que coincide con el texto **completo**, sin importar
  mayúsculas ni espacios alrededor. Pista: `re.compile(rf"^\s*{re.escape(texto)}\s*$", re.I)`.
- `normalizar(texto)` (estático): deja el texto sin tildes, en minúsculas, sin `*` y sin espacios de más,
  para poder comparar. `"Período *"` y `"periodo"` deben quedar iguales.
  Pista: `unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()`.

### Reto 7: `core\sistema.py`, la clase base de los sistemas

Clase **`Sistema`** que hereda de `ABC`:
- Atributo de clase `NOMBRE = ""`.
- `__init__(self, page)`: guarda `self.page`, lee `Config <NOMBRE>.txt` y se lo pasa a `self.leer_config(...)`
  para guardar el resultado en `self.config`; y guarda `self.credenciales` con `Credenciales.de_sistema(...)`.
- Métodos abstractos `leer_config(self, datos)` y `ejecutar(self)`. Pista: `@abstractmethod`.
- `guardar(self, descarga, prefijo)`: llama a `guardar_descarga` con el `NOMBRE` del sistema.

Debe ser imposible crear un `Sistema` directamente o una subclase a la que le falte un método.

---

## Bloque 3 — Q10

### Reto 8: `sistemas\q10\config.py`

Crea `sistemas\__init__.py`, `sistemas\q10\__init__.py` y `config.py` con la `@dataclass` **`ConfigQ10`**
(campos `rol`, `informes`, `filtros`) y el método de clase **`desde_txt(cls, datos)`** que:
- saca `informes` con `separar_lista`; si está vacío o es plantilla, lanza `ValueError`,
- toma como filtros **todo lo demás** del `.txt` que tenga valor, menos `rol` e `informes`,
  guardándolos como lista de pares: `[("sede - jornada", ["B2G - Única"]), ("curso", ["Todos"])]`,
- si no hay `rol`, usa `"Administrativo"`.

El orden de los filtros debe ser el mismo del archivo (los diccionarios de Python lo conservan).

### Reto 9: `sistemas\q10\paginas.py`, pantalla de login *(comprobación manual)*

Clase **`LoginQ10(Pagina)`** con sus selectores como constantes:
`USUARIO = "#form-username"`, `CLAVE = "#form-password"`, `BOTON = "#btn-submit-login"`,
`CAPTCHA = "#login-form-captcha"`, `MENSAJES = "#login-form-messages"`, `ROLES = "#roles a.list-group-item"`.

Método `iniciar_sesion(self, link, usuario, clave, rol)`: abre el link, escribe el usuario, clic en el botón,
**espera a que se vea** el campo de contraseña (existe oculto desde el principio), la escribe, clic otra vez,
y escoge el rol. Que devuelva la barra de navegación (reto 10).

Si aparece el captcha, el bot **no** lo resuelve: se detiene con `input(...)` para que lo resuelva una persona.

### Reto 10: `paginas.py`, barra y lista de informes *(comprobación manual)*

- **`BarraQ10(Pagina)`** con `INFORMES = "nav.q10navbar a[href='/Informes']"` y el método `ir_a_informes()`,
  que da clic, espera la URL y devuelve una `PaginaInformes`.
- **`PaginaInformes(Pagina)`** con:
  - `esta_abierta()`: `True` si la URL termina en `/Informes`,
  - `abrir_informe(nombre)`: clic en el enlace con ese nombre exacto (usa `get_by_role("link", ...)` y toma
    el primero, porque el informe puede estar repetido en Favoritos). Devuelve un `FormularioInforme`.

### Reto 11: `paginas.py`, el formulario de filtros

Clase **`FormularioInforme(Pagina)`** con cuatro métodos:

- **`campo(nombre)`**: devuelve el control (`select` o `input`) del filtro cuyo título coincide con `nombre`,
  o `None` si ese filtro no existe en el informe. Recorre los `label` visibles, compara con `normalizar`,
  y usa el atributo `for` del label para llegar al control.
- **`llenar(nombre, valor)`**: si el filtro no existe, avisa y devuelve `None`. Si es una lista (`SELECT`),
  espera a que la opción exista (las listas se cargan en cascada), la escoge y devuelve el **texto exacto**
  de Q10. Si el valor no está entre las opciones, lanza `ValueError` mostrando las opciones. Si es un
  `input`, escribe el valor.
  Pistas: `campo.evaluate("el => el.tagName")`, `expect(opcion).to_be_attached(timeout=15_000)`,
  `campo.select_option(label=..., force=True)`.
- **`opciones(nombre)`**: lista todas las opciones de esa lista sin contar `"Seleccione"`, o `None` si el
  filtro no existe. Es lo que hace funcionar `Curso : Todos`.
- **`exportar()`**: clic en el botón que diga "Exportar" y devuelve la descarga. Si no llega ninguna descarga,
  revisa si Q10 marcó campos obligatorios y lanza `ValueError` diciendo cuáles.
  Pista: `with self.page.expect_download(timeout=120_000) as info:` y luego `return info.value`.

### Reto 12: `sistemas\q10\sistema.py`

Clase **`Q10(Sistema)`** con `NOMBRE = "Q10"`, `leer_config()` (usa `ConfigQ10`) y:

- **`ejecutar()`**: login → Informes → por cada informe: abrirlo y llamar a `llenar_y_exportar`.
  Si un informe falla, avisa con `FALLO en el informe ...` y sigue con el siguiente.
- **`llenar_y_exportar(self, formulario, informe, filtros, etiquetas=())`**: el reto grande.
  - Si ya no quedan filtros: exporta, guarda con `self.guardar(...)` y el nombre lleva el informe más las
    etiquetas acumuladas.
  - Si el primer filtro dice `Todos`: pide las opciones con `formulario.opciones(...)`.
  - Si el filtro tiene **un** valor: lo llena y sigue con los filtros restantes.
  - Si tiene **varios**: por cada valor lo llena y repite todo lo que sigue, agregando el valor a las
    etiquetas. Si uno falla, avisa y continúa con el siguiente.
  - Pista: la función se llama a sí misma con `filtros[1:]` (recursividad).

### Reto 13: `bot.py`, el menú

Clase **`Bot`** con `__init__(self, argumentos)` y:
- **`disponibles()`**: busca los `Config *.txt` de `CARPETA`, y devuelve las **clases** de los sistemas
  registrados en `sistemas\__init__.py` (diccionario `SISTEMAS`). Si un Config no corresponde a ningún
  sistema, avisa y lo ignora. Si no hay ninguno, lanza `FileNotFoundError`.
- **`elegir(disponibles)`**: si hay argumento (`bot.py Q10` o `bot.py Todos`) lo usa; si hay un solo sistema,
  ese; si no, muestra el menú numerado con la opción "Todos" al final y repite hasta que escriban un número válido.
- **`ejecutar(esperar_enter=True)`**: abre el navegador y, por cada sistema, una ventana nueva
  (`navegador.new_context(...)`), crea el sistema, llama a `ejecutar()`, atrapa los errores para mostrar
  `FALLO en <sistema>: ...` y guarda la captura final.

Agrega también, al inicio del archivo, el relanzamiento con el Python del `.venv` y el `try/except` final
con `input(...)`, para que la consola no se cierre sola.

---

## Bloque 4 — Oxford y el cierre

### Reto 14: Oxford completo *(comprobación manual)*

Repite el patrón en `sistemas\oxford\`: `config.py` (`ConfigOxford` con `id_organizacion`, `clases`,
`scores`, `figuras`, `puntajes`), `paginas.py` (una clase por pantalla: inicio, menú de la cuenta, ventana de
organizaciones, menú lateral, My Organization, clase y progreso) y `sistema.py` (`Oxford(Sistema)`).

Regístralo en `sistemas\__init__.py` junto a Q10.

### Reto 15: el `.exe` *(comprobación manual)*

Genera el ejecutable de tu versión, desde la carpeta `botv2-practica`:

```
..\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name "Bot practica" bot.py
```

Pruébalo en una carpeta aparte con los `Config` y unas credenciales de plantilla: debe mostrar el menú y
avisar que faltan las credenciales.

---

## Retos extra (si quieres ir más allá)

- Que cada sistema escriba un `registro.txt` con la fecha, qué descargó y cuánto tardó.
- Que `Bot` acepte `bot.py Q10 "Inasistencias por curso"` para un solo informe.
- Que los filtros acepten rangos de fechas relativos, por ejemplo `Fecha inicial : hace 30 dias`.
- Un sistema nuevo (el tercero) siguiendo el mismo patrón.
