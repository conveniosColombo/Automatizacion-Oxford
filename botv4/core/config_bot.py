"""Lo que se lee de 'Config Bot.txt': como trabaja el bot cuando corre solo.

Si el archivo no existe, se usan los valores de siempre (todos los sistemas, ventana visible).
"""
from dataclasses import dataclass

from core import archivos

NOMBRE = "Config Bot.txt"
SI = ("si", "sí", "s", "yes", "true", "1")


def entero(texto, por_defecto, minimo, maximo):
    """Convierte a numero y lo deja dentro de un rango razonable."""
    try:
        return max(minimo, min(maximo, int(str(texto).strip())))
    except (TypeError, ValueError):
        return por_defecto


@dataclass
class ConfigBot:
    sistemas: list[str]                 # en el orden en que se ejecutan; "Todos" vale
    sin_ventana: bool = False           # True: el navegador no se ve (maquina virtual sin sesion)
    reintentos: int = 1                 # cuantas veces se vuelve a intentar un sistema que fallo
    minutos_por_sistema: int = 30       # tope de tiempo, para que nunca se quede colgado
    existe: bool = False                # si de verdad habia un 'Config Bot.txt'

    @classmethod
    def desde_txt(cls, nombre=NOMBRE):
        ruta = archivos.CARPETA / nombre
        if not ruta.exists():
            return cls(sistemas=["Todos"])
        datos = archivos.leer_txt(nombre)
        sistemas = archivos.separar_lista(datos.get("sistemas", ""))
        return cls(
            sistemas=[s for s in sistemas if not archivos.es_plantilla(s)] or ["Todos"],
            sin_ventana=(datos.get("sin ventana") or "").strip().lower() in SI,
            reintentos=entero(datos.get("reintentos"), 1, minimo=0, maximo=5),
            minutos_por_sistema=entero(datos.get("minutos por sistema"), 30, minimo=1, maximo=600),
            existe=True,
        )

    def resumen(self):
        return (f"sistemas: {', '.join(self.sistemas)} | "
                f"sin ventana: {'si' if self.sin_ventana else 'no'} | "
                f"reintentos: {self.reintentos} | "
                f"tope por sistema: {self.minutos_por_sistema} min")
