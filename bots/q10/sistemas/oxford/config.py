"""Lo que se lee de la hoja 'Oxford' de la planilla."""
from dataclasses import dataclass

from core import archivos

REQUERIDAS = {"id": "ID de la organización", "clases": "Clase (al menos una con Usar = Sí)",
              "scores": "Scores", "show figures as": "Show figures as",
              "show scores for": "Show scores for"}


@dataclass
class ConfigOxford:
    id_organizacion: str   # columna "ID" de "My Organizations" (distingue mayusculas)
    clases: list[str]
    scores: str            # Progress settings > Scores
    figuras: str           # Progress settings > Show figures as
    puntajes: str          # Progress settings > Show scores for

    @classmethod
    def desde_hoja(cls, datos):
        faltan = [nombre for clave, nombre in REQUERIDAS.items() if not datos.get(clave)]
        if faltan:
            raise ValueError(f"Completa en la hoja Oxford: {', '.join(faltan)}")
        return cls(id_organizacion=datos["id"], clases=archivos.separar_lista(datos["clases"]),
                   scores=datos["scores"], figuras=datos["show figures as"], puntajes=datos["show scores for"])
