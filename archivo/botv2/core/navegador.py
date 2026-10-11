"""Navegador del bot: Chrome y, si no esta, Edge (viene con Windows).

Asi el .exe no tiene que traer su propio navegador.
"""


def abrir_navegador(playwright, visible=True):
    for canal in ("chrome", "msedge"):
        try:
            return playwright.chromium.launch(channel=canal, headless=not visible, slow_mo=300)
        except Exception:
            pass
    return playwright.chromium.launch(headless=not visible, slow_mo=300)
