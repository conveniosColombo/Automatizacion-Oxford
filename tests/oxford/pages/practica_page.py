"""Page Object de Wide Angle Online Practice (wideangle.oxfordonlinepractice.com).

Es el sitio al que lleva la version 'Closing soon' desde el Hub. Las actividades viven en un iframe
(`activityframe`) del mismo origen; cada tipo de ejercicio tiene su resolvedor y las respuestas salen
del banco `datos/respuestas_wide_angle_l3.json` (clave 'UU/LL/AA' = ruta de la URL de la actividad).
"""
import json
import logging
import re
from pathlib import Path

from playwright.sync_api import Page, expect

log = logging.getLogger("oxford.practica")

BANCO = Path(__file__).resolve().parents[1] / "datos" / "respuestas_wide_angle_l3.json"
IFRAME = 'iframe[name="activityframe"]'
BASE_LIBRO = "https://wideangle.oxfordonlinepractice.com/app/dashboard/book/74"
PATRON_PUNTAJE = re.compile(r"(\d+|-)\s*/\s*(\d+)\s*Last score")  # toma el 'Last score' aunque haya 'First score'

# Selectores del sitio (basados en las clases del motor de actividades)
BOTON_COMPROBAR = re.compile(r"check answers", re.I)
BOTON_SIGUIENTE = re.compile(r"next activity", re.I)

JS_SELECTS = """(resp) => {
    const fallos = [];
    [...document.querySelectorAll('select')].forEach((s, i) => {
        const caja = s.closest('.bootstrap-select') || s.parentElement;
        const li = [...caja.querySelectorAll('li')].find(l => l.textContent.trim() === resp[i]);
        if (!li) { fallos.push(i + ':' + resp[i]); return; }
        li.querySelector('a').click();
    });
    return fallos;
}"""

JS_CASILLAS = """(textos) => {
    const hechas = [];
    [...document.querySelectorAll('li')].filter(li => li.querySelector('label')).forEach(li => {
        if (textos.includes(li.textContent.trim())) { li.querySelector('label').click(); hechas.push(li.textContent.trim()); }
    });
    return hechas;
}"""

JS_RADIOS = """(args) => {
    const [modo, datos, opciones] = args;
    const radios = [...document.querySelectorAll('input[type=radio]')];
    const clic = r => (r.parentElement.querySelector('label') || r).click();
    if (modo === 'plano') datos.forEach(i => clic(radios[i]));
    else if (modo === 'por_pregunta') datos.forEach((a, q) => clic(radios[q * opciones + a]));
    else if (modo === 'nombre') datos.forEach((v, q) => clic(document.querySelector(`input[name=answer${q + 1}][value=${v}]`)));
    return document.querySelectorAll('input:checked').length;
}"""


def cargar_banco() -> dict:
    banco = json.loads(BANCO.read_text(encoding="utf-8"))
    return {k: v for k, v in banco.items() if not k.startswith("_")}


class PracticaPage:
    def __init__(self, page: Page):
        self.page = page
        self.marco = page.frame_locator(IFRAME)

    # ---- entrada ----
    @staticmethod
    def abrir_desde_hub(pagina_hub: Page) -> "PracticaPage":
        """En la ficha del curso del Hub, abre la version 'Closing soon' (se abre en pestana nueva)."""
        enlace = pagina_hub.get_by_role("link", name=re.compile("closing soon", re.I)).first
        enlace.wait_for(state="visible")
        with pagina_hub.context.expect_page():
            enlace.click()
        # La pestana inicial es un intermedio LTI (/dashboard/lti) que redirige o se reemplaza: se espera
        # a la pestana del dashboard ya definitiva (ruta /app/dashboard/... sin 'lti').
        practica = None
        for _ in range(120):
            for candidata in pagina_hub.context.pages:
                if not candidata.is_closed() and re.search(r"oxfordonlinepractice\.com/app/dashboard(?!/lti)", candidata.url):
                    practica = candidata
                    break
            if practica:
                break
            pagina_hub.wait_for_timeout(500)
        assert practica, f"No se abrio el dashboard de practica: {[p.url for p in pagina_hub.context.pages]}"
        practica.wait_for_load_state("domcontentloaded")
        # Banner de cookies del sitio de practica
        try:
            practica.get_by_role("button", name=re.compile("^accept all$", re.I)).click(timeout=8_000)
        except Exception:
            pass
        log.info("Practica abierta: %s", practica.url)
        return PracticaPage(practica)

    def ir_a_actividad(self, clave: str) -> None:
        unidad, leccion, actividad = clave.split("/")
        self.page.goto(f"{BASE_LIBRO}/unit/{unidad}/lesson/{leccion}/activity/{actividad}")
        self.page.wait_for_load_state("domcontentloaded")
        self.marco.locator("body *").first.wait_for(state="attached", timeout=30_000)

    def esperar_actividad(self) -> None:
        """Espera a que el iframe pinte el ejercicio (los juegos de canvas no tienen .mainWrapper)."""
        self.marco.locator(".mainWrapper, canvas").first.wait_for(state="attached", timeout=30_000)
        self.page.wait_for_timeout(500)

    # ---- resultado ----
    def puntaje(self) -> tuple[int | None, int | None]:
        texto = self.page.locator("body").inner_text()
        m = PATRON_PUNTAJE.search(texto)
        if not m:
            return None, None
        return (None if m.group(1) == "-" else int(m.group(1))), int(m.group(2))

    def comprobar(self) -> tuple[int | None, int | None]:
        boton = self.page.get_by_role("button", name=BOTON_COMPROBAR)
        expect(boton).to_be_enabled(timeout=5_000)  # sigue deshabilitado si falta una respuesta
        boton.click()
        self.page.wait_for_timeout(1_000)
        return self.puntaje()

    # ---- resolvedores por tipo ----
    def _marco_js(self):
        return self.page.frame(name="activityframe")

    def _select(self, spec):
        fallos = self._marco_js().evaluate(JS_SELECTS, spec["respuestas"])
        assert not fallos, f"Opciones no encontradas en los desplegables: {fallos}"

    def _checkbox(self, spec):
        hechas = self._marco_js().evaluate(JS_CASILLAS, spec["respuestas"])
        assert len(hechas) == len(spec["respuestas"]), f"Casillas marcadas: {hechas}"

    def _radio(self, spec):
        modo = {"radio_plano": "plano", "radio_por_pregunta": "por_pregunta", "radio_nombre": "nombre"}[spec["tipo"]]
        self._marco_js().evaluate(JS_RADIOS, [modo, spec["respuestas"], spec.get("opciones", 0)])

    def _radio_texto(self, spec):
        for texto in spec["respuestas"]:
            self.marco.locator("label").filter(has_text=re.compile(rf"^\s*{re.escape(texto)}\s*$")).first.click()

    def _opcion_texto(self, spec):
        """Opciones en listas anidadas: cada pregunta es un <li> que contiene su <ul> de opciones."""
        preguntas = self.marco.locator("li:has(> ul)")
        for q, texto in enumerate(spec["respuestas"]):
            opcion = preguntas.nth(q).locator("li").filter(has_text=re.compile(rf"^\s*{re.escape(texto)}\s*$")).first
            opcion.click()

    def _texto(self, spec):
        campos = self.marco.locator("input.inputClass, input[type=text]")
        for i, valor in enumerate(spec["respuestas"]):
            campos.nth(i).click()
            self.page.keyboard.press("Control+A")
            self.page.keyboard.type(valor, delay=8)  # teclear de verdad: 'fill' no habilita 'Check answers'

    def _arrastrar_a(self, origen, destino):
        origen.scroll_into_view_if_needed()
        o, d = origen.bounding_box(), destino.bounding_box()
        raton = self.page.mouse
        raton.move(o["x"] + o["width"] / 2, o["y"] + o["height"] / 2)
        raton.down()
        raton.move(o["x"] + o["width"] / 2 + 6, o["y"] + 6, steps=5)  # jQuery UI exige movimiento gradual
        raton.move(d["x"] + d["width"] / 2, d["y"] + min(d["height"] / 2, 30), steps=15)
        raton.up()
        self.page.wait_for_timeout(300)

    @staticmethod
    def _exacto(texto):
        return re.compile(rf"^\s*{re.escape(texto)}\s*$")

    def _arrastrar(self, spec):
        for i, palabra in enumerate(spec["respuestas"]):
            origen = self.marco.locator(".term").filter(has_text=self._exacto(palabra)).first
            self._arrastrar_a(origen, self.marco.locator(".target-box").nth(i))

    def _bins(self, spec):
        for contenedor, palabras in spec["respuestas"].items():
            for palabra in palabras:
                origen = self.marco.locator(".itemsUl li").filter(has_text=self._exacto(palabra)).first
                self._arrastrar_a(origen, self.marco.locator(".binItemsUl").nth(int(contenedor)))

    def resolver(self, clave: str, spec: dict) -> tuple[int | None, int | None]:
        """Contesta la actividad abierta segun el banco y devuelve (obtenido, total); None si se omite."""
        tipo = spec["tipo"]
        if tipo == "omitir":
            log.info("%s omitida: %s", clave, spec.get("razon", ""))
            return None, None
        despacho = {
            "select": self._select, "checkbox": self._checkbox, "radio_texto": self._radio_texto,
            "opcion_texto": self._opcion_texto, "texto": self._texto, "arrastrar": self._arrastrar,
            "bins": self._bins, "radio_plano": self._radio, "radio_por_pregunta": self._radio,
            "radio_nombre": self._radio,
        }
        despacho[tipo](spec)
        obtenido, total = self.comprobar()
        log.info("%s (%s): %s/%s", clave, tipo, obtenido, total)
        return obtenido, total
