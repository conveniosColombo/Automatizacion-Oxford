"""Clase base de los Page Objects.

Cada pantalla de un sistema es una clase que hereda de Pagina y guarda:
- sus selectores, como constantes en MAYUSCULAS (el "donde": ids, textos, atributos), y
- sus acciones, como metodos (el "que hacer": escribir, dar clic, escoger, descargar).
Si el sistema cambia un boton, solo se toca la clase de esa pantalla.
"""
import re
import unicodedata

from playwright.sync_api import Page

from core import archivos


class Pagina:
    def __init__(self, page: Page):
        self.page = page

    def esperar(self, milisegundos):
        """Pausa fija para pantallas que siguen cargando datos despues de abrir."""
        self.page.wait_for_timeout(milisegundos)

    def captura(self, nombre):
        return archivos.captura(self.page, nombre)

    def clic_y_seguir(self, elemento, espera=5_000):
        """Da clic y devuelve la pagina donde quedo el contenido.

        Algunos enlaces abren una pestaña nueva (target="_blank") y otros no. Se espera un momento
        por la pestaña nueva: si aparece, se sigue en ella; si no, se sigue en la misma.
        """
        try:
            with self.page.context.expect_page(timeout=10_000) as nueva:
                elemento.click()
            pagina = nueva.value
            pagina.bring_to_front()
            print("  (se abrio en una pestaña nueva)")
        except Exception:
            pagina = self.page
        pagina.wait_for_load_state()
        pagina.wait_for_timeout(espera)  # dar tiempo a que cargue el contenido
        return pagina

    @staticmethod
    def texto_exacto(texto):
        """Patron que coincide con el texto completo, sin importar mayusculas ni espacios alrededor."""
        return re.compile(rf"^\s*{re.escape(texto)}\s*$", re.I)

    @staticmethod
    def normalizar(texto):
        """Para comparar nombres sin tildes, mayusculas, signos ni espacios de mas.

        Asi "Período *" == "periodo" y "¿Incluir archivados?" == "Incluir archivados": en el
        Config no hay que copiar los adornos de la pantalla.
        """
        sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
        return " ".join(re.sub(r"[*?:]", "", sin_tildes).lower().split())
