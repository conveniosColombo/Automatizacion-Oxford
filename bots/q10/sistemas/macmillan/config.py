"""Lo que se lee de la hoja 'Macmillan' de la planilla."""
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
    def desde_hoja(cls, datos):
        libros = archivos.separar_lista(datos.get("libros", ""))
        if not libros:
            raise ValueError("Escribe en la tabla 'Libro' de la hoja Macmillan al menos un libro con Usar = Sí")
        return cls(libros=libros,
                   niveles=archivos.separar_lista(datos.get("niveles", "")),
                   recurso=datos.get("recurso") or RECURSO_POR_DEFECTO,
                   clases=archivos.separar_lista(datos.get("clases", "")) or ["Todas"])
