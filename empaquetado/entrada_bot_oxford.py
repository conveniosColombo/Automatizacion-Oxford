"""Punto de entrada de 'Bot Oxford.exe': ejecuta automatizar_oxford.main() sin interfaz.

La pantalla de Oxford lo lanza con la salida redirigida (stdin vacio), asi que el input() final
de 'Presiona Enter...' falla con EOFError: es lo esperado y se ignora.
"""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Empaquetado: Playwright buscaria los navegadores dentro del .exe; se usan los del equipo
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"))

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "bots" / "oxford"))

for flujo in (sys.stdout, sys.stderr):
    if hasattr(flujo, "reconfigure"):
        flujo.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)   # UTF-8 y en tiempo real

import automatizar_oxford  # noqa: E402

try:
    automatizar_oxford.main()
except (EOFError, RuntimeError):
    pass
except Exception as error:                                       # noqa: BLE001
    print(f"FALLO: {automatizar_oxford.resumen(error)}")
sys.exit(0)
