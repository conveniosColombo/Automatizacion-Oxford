"""Lo que se lee de 'Config Oxford.txt'."""
from dataclasses import dataclass

from core import archivos

REQUERIDAS = ("id", "clases", "scores", "show figures as", "show scores for")


@dataclass
class ConfigOxford:
    id_organizacion: str   # columna "ID" de "My Organizations" (distingue mayusculas)
    clases: list[str]
    scores: str            # Progress settings > Scores
    figuras: str           # Progress settings > Show figures as
    puntajes: str          # Progress settings > Show scores for

    @classmethod
    def desde_txt(cls, datos):
        faltan = [c for c in REQUERIDAS if not datos.get(c)]
        if faltan:
            raise ValueError(f"Completa {', '.join(faltan)} en 'Config Oxford.txt'")
        return cls(id_organizacion=datos["id"], clases=archivos.separar_lista(datos["clases"]),
                   scores=datos["scores"], figuras=datos["show figures as"], puntajes=datos["show scores for"])
