"""Registro de sistemas. Para agregar uno: crear su carpeta (config.py, paginas.py, sistema.py) y sumarlo aqui."""
from .macmillan import Macmillan
from .oxford import Oxford
from .q10 import Q10

SISTEMAS = {sistema.NOMBRE.lower(): sistema for sistema in (Oxford, Q10, Macmillan)}
