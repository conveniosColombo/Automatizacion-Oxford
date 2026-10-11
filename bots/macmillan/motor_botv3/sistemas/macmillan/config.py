"""Lo que se lee de 'Config Macmillan.txt'."""
from dataclasses import dataclass

from core import archivos


RECURSO_POR_DEFECTO = "Macmillan Education Everywhere App"


@dataclass
class ConfigMacmillan:
    libros: list[str]   # nombres tal como aparecen debajo de cada portada en "Mi Estanteria"
    niveles: list[str]  # pestañas dentro del libro (Level 1, Level 2...); "Todos" = todas; vacio = el libro no tiene
    recurso: str        # opcion de la lista del nivel a la que se entra
    clases: list[str]   # clases de Progress; "Todas" = todas las que aparezcan

    @classmethod
    def desde_txt(cls, datos):
        libros = archivos.separar_lista(datos.get("libros", ""))
        if not libros or archivos.es_plantilla(libros[0]):
            raise ValueError("Escribe en 'Libros' de Config Macmillan.txt los libros a descargar, "
                             "separados por coma")
        return cls(libros=libros,
                   niveles=archivos.separar_lista(datos.get("niveles", "")),
                   recurso=datos.get("recurso") or RECURSO_POR_DEFECTO,
                   clases=archivos.separar_lista(datos.get("clases", "")) or ["Todas"])
