"""Formato de los mensajes de error que se muestran en la consola."""


def resumen(error):
    """Tipo de error y su primera linea, ej. "ValueError: No encontre la clase 'X'"."""
    lineas = str(error).splitlines()
    return f"{type(error).__name__}: {lineas[0] if lineas else ''}"
