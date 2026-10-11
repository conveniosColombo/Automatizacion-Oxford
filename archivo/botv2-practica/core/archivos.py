"""Carpeta de trabajo, lectura de los .txt (Config y Credenciales) y guardado de descargas y capturas.

Retos 1 a 4 resueltos y comentados. El siguiente archivo es core/navegador.py (reto 5).
"""
import re                                  # expresiones regulares: buscar y reemplazar en textos
import sys                                 # informacion del programa que esta corriendo
from dataclasses import dataclass          # clases que solo guardan datos, sin escribir tanto
from datetime import datetime              # la fecha y hora de ahora, para el nombre de los archivos
from pathlib import Path                   # rutas de archivos y carpetas

# =============================================================================================
# RETO 1 - Donde esta todo
# =============================================================================================

# ¿El programa esta corriendo como .exe? PyInstaller le agrega a sys el atributo "frozen".
# getattr(objeto, "nombre", False) lo pide con cuidado: si no existe, devuelve False en vez de fallar.
ES_EXE = getattr(sys, "frozen", False)

# CARPETA: donde estan los .txt y donde se guardan las descargas y las capturas.
#   - Como .exe: la carpeta del ejecutable (sys.executable es la ruta del .exe).
#   - En desarrollo: la carpeta del proyecto, dos niveles arriba de este archivo:
#       parents[0] = core   parents[1] = botv2-practica   parents[2] = Automatizacion Oxford
# La forma "A if condicion else B" elige entre dos valores en una sola linea.
CARPETA = Path(sys.executable).resolve().parent if ES_EXE else Path(__file__).resolve().parents[2]


def leer_txt(nombre):
    """Lee un .txt con lineas 'Clave : valor' y devuelve un diccionario.

    Ejemplo: "Rol : Administrativo" -> {"rol": "Administrativo"}
    """
    # Las rutas se unen con "/", aunque en Windows se vean con "\"
    ruta = CARPETA / nombre

    # Mejor avisar con un mensaje claro que dejar que reviente al abrirlo
    if not ruta.exists():
        raise FileNotFoundError(f"No encontre '{nombre}' en {CARPETA}")

    datos = {}

    # read_text lee todo el archivo como un texto; splitlines lo parte en una lista de lineas.
    # utf-8-sig: si el Bloc de notas guardo con la marca invisible (BOM), la quita sola.
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():

        # Sirven solo las lineas que tienen ":" y que no son comentarios.
        # strip() quita los espacios de los extremos, por si el "#" viene corrido.
        if ":" in linea and not linea.strip().startswith("#"):

            # El 1 es el maximo de cortes: parte solo en el PRIMER ":".
            # Sin ese 1, un valor como "https://site2.q10.com" se partiria de mas.
            clave, valor = linea.split(":", 1)

            # La clave en minuscula y sin espacios, para buscarla siempre igual (datos["rol"]).
            datos[clave.strip().lower()] = valor.strip()

    return datos


# =============================================================================================
# RETO 2 - Dos ayudas para trabajar los textos del .txt
# =============================================================================================

# Comienzo de los textos de ejemplo de las plantillas sin llenar.
# Va aqui arriba, y no adentro de la funcion, para poder agregar otro sin buscar en el codigo.
PLANTILLAS = ("escribe_aqui", "coloca aqu")


def es_plantilla(valor):
    """¿El texto sigue siendo el de la plantilla, sin llenar?"""
    # lower() para que de igual como lo escriban; startswith acepta una tupla de opciones.
    return valor.lower().startswith(PLANTILLAS)


def separar_lista(valor):
    """'a, b , c' -> ['a', 'b', 'c']. Sirve para las clases, los informes y los valores de un filtro."""
    # Se lee: "por cada pedazo v que salga de partir el texto por comas, guarda v sin espacios,
    # pero solo si al quitarle los espacios queda algo" (asi se descartan los vacios).
    return [v.strip() for v in valor.split(",") if v.strip()]


# =============================================================================================
# RETO 3 - Las credenciales de un sistema
# =============================================================================================

# @dataclass escribe por nosotros el __init__ y el modo de mostrarla.
# frozen=True la deja de solo lectura: una vez creada, nadie puede cambiarle la clave por accidente.
@dataclass(frozen=True)
class Credenciales:
    usuario: str
    clave: str
    link: str

    # classmethod: no se usa sobre una credencial ya creada, sino sobre la clase, para fabricar una:
    #     credenciales = Credenciales.de_sistema("Q10")
    # Por eso el primer parametro es cls (la clase) y no self.
    @classmethod
    def de_sistema(cls, sistema):
        """Lee 'Credenciales <sistema>.txt' y avisa si falta algo o si quedo la plantilla sin llenar."""
        nombre = f"Credenciales {sistema}.txt"
        datos = leer_txt(nombre)

        # Un dato falta si no esta, si esta vacio, o si todavia tiene el texto de la plantilla.
        # datos.get(c) devuelve None si la clave no existe, en vez de reventar.
        faltan = [c for c in ("user", "password", "link") if not datos.get(c) or es_plantilla(datos[c])]
        if faltan:
            # join arma "user, password" para que el mensaje diga exactamente que hay que llenar
            raise ValueError(f"Completa {', '.join(faltan)} en '{nombre}'")

        # cls(...) crea la Credenciales. Los nombres del .txt (user, password) se traducen
        # a los del programa (usuario, clave): asi el resto del bot no depende de como se llame el .txt.
        return cls(usuario=datos["user"], clave=datos["password"], link=datos["link"])


# =============================================================================================
# RETO 4 - Guardar lo que se descarga y las capturas de pantalla
# =============================================================================================

def nombre_archivo(texto):
    """Deja el texto listo para ser parte del nombre de un archivo.

    "C1.1-7PM217 SDDE (B2G)" -> "C1.1-7PM217_SDDE_B2G_"
    """
    # re.sub(patron, reemplazo, texto) reemplaza todo lo que coincida con el patron.
    # [^\w.-] significa "cualquier cosa que NO sea letra, numero, guion bajo, punto o guion".
    # El + al final junta los seguidos: "  (" se vuelve un solo "_" y no tres.
    # Windows no acepta caracteres como \ / : * ? " < > | en los nombres de archivo.
    return re.sub(r"[^\w.-]+", "_", texto)


def guardar_descarga(descarga, sistema, prefijo):
    """Guarda el archivo descargado en Descargas/<sistema>/ y devuelve la ruta donde quedo.

    descarga: lo que entrega Playwright cuando la pagina baja un archivo.
    prefijo:  con que nombre queremos reconocerlo (el informe, el curso, la clase...).
    """
    # Del nombre que pone el sistema solo se aprovecha la extension (.xlsx, .csv, .pdf).
    # El resto ya va en el prefijo, y ademas alarga la ruta: Windows no pasa de 260 caracteres.
    extension = Path(descarga.suggested_filename).suffix

    # La fecha va adelante para que los archivos queden ordenados solos: 2026-09-16_0930_...
    destino = (CARPETA / "Descargas" / sistema
               / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre_archivo(prefijo)}{extension}")

    # save_as NO crea la carpeta, asi que toca crearla antes.
    # parents=True crea tambien las de arriba; exist_ok=True evita el error si ya existe.
    destino.parent.mkdir(parents=True, exist_ok=True)

    descarga.save_as(destino)
    return destino


def captura(page, nombre):
    """Guarda una foto de la pagina en la carpeta Capturas y devuelve la ruta.

    Sirve para ver que estaba en pantalla cuando algo fallo.
    """
    ruta = CARPETA / "Capturas" / nombre
    # screenshot espera la ruta como texto, por eso el str(...). Esta si crea la carpeta sola.
    page.screenshot(path=str(ruta))
    return ruta
