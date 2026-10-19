"""Page Object de 'My Progress' + monitor de red para detectar desincronizacion."""
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page

log = logging.getLogger("oxford.progreso")

PATRON_API = re.compile(r"/api/|/progress|/sync", re.I)
PATRON_PORCENTAJE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")


class MonitorRed:
    """Registra las peticiones de fondo (/api/, /progress, /sync) y separa las 4xx/5xx."""

    def __init__(self, page: Page):
        self.errores = []
        self.llamadas = []
        page.on("response", self._al_responder)

    def _al_responder(self, resp):
        if not PATRON_API.search(resp.url):
            return
        req = resp.request
        registro = {"hora": datetime.now().isoformat(timespec="seconds"), "metodo": req.method,
                    "url": resp.url, "estado": resp.status, "payload": (req.post_data or "")[:500]}
        self.llamadas.append(registro)
        if resp.status >= 400:
            try:
                registro["respuesta"] = resp.text()[:500]
            except Exception:
                registro["respuesta"] = "<no legible>"
            self.errores.append(registro)
            log.error("HTTP %s en %s %s | payload=%s", resp.status, req.method, resp.url, registro["payload"])

    def volcar(self, ruta: Path) -> Path:
        """Guarda el 'reporte de red' (llamadas y errores) como JSON junto a la captura."""
        ruta.write_text(json.dumps({"errores": self.errores, "llamadas": self.llamadas},
                                   indent=2, ensure_ascii=False), encoding="utf-8")
        return ruta


class ProgressPage:
    def __init__(self, page: Page):
        self.page = page

    def abrir(self) -> None:
        patron = re.compile(r"my progress", re.I)
        destino = self.page.get_by_role("link", name=patron).or_(
            self.page.get_by_role("button", name=patron)).or_(self.page.get_by_text(patron)).filter(visible=True)
        destino.first.click()
        self.page.wait_for_load_state("networkidle")

    def leer_porcentaje(self) -> float | None:
        """Primer porcentaje visible en la vista de progreso; None si no hay ninguno."""
        self.abrir()
        texto = self.page.locator("main, body").first.inner_text()
        m = PATRON_PORCENTAJE.search(texto)
        valor = float(m.group(1).replace(",", ".")) if m else None
        log.info("Progreso mostrado en My Progress: %s", valor)
        return valor
