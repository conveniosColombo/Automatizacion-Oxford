"""Formato de los mensajes de error que se muestran en la consola."""

# Playwright pone el motivo real del timeout dentro del "Call log", no en la primera linea
CAUSAS = ("element is", "intercepts pointer events", "waiting for element")


def resumen(error):
    """Tipo de error y su primera linea, con el motivo si Playwright lo dejo en el registro.

    Ej. "TimeoutError: Locator.click: Timeout 30000ms exceeded. (element is not enabled)"
    """
    lineas = [linea.strip(" -") for linea in str(error).splitlines() if linea.strip()]
    primera = lineas[0] if lineas else ""
    causa = next((linea for linea in reversed(lineas)
                  if any(linea.startswith(c) or c in linea for c in CAUSAS)), "")
    return f"{type(error).__name__}: {primera}" + (f" ({causa})" if causa else "")
