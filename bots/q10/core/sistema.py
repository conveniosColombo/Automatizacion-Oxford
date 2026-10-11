"""Clase base de los sistemas de informacion (Oxford, Q10...)."""
from abc import ABC, abstractmethod

from playwright.sync_api import Page

from core import archivos


class Sistema(ABC):
    """Cada sistema hereda de aqui y define NOMBRE, leer_config() y ejecutar().

    Al crearlo lee su hoja y su fila de 'Accesos' en la planilla, asi los errores de
    configuracion salen antes de abrir cualquier pagina.
    """
    NOMBRE = ""  # igual que el nombre de su hoja en la planilla

    def __init__(self, page: Page):
        self.page = page
        self.config = self.leer_config(archivos.planilla().leer_hoja(self.NOMBRE))
        self.credenciales = archivos.Credenciales.de_sistema(self.NOMBRE)

    @abstractmethod
    def leer_config(self, datos: dict):
        """Convierte el diccionario de la hoja en el objeto de configuracion del sistema (y lo valida)."""

    @abstractmethod
    def ejecutar(self):
        """Todos los pasos en orden: iniciar sesion, navegar, filtrar y descargar."""

    def guardar(self, descarga, prefijo):
        return archivos.guardar_descarga(descarga, self.NOMBRE, prefijo)
