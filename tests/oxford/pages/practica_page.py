"""Page Object de Wide Angle Online Practice (wideangle.oxfordonlinepractice.com).

Es el sitio al que lleva la version 'Closing soon' desde el Hub. Las actividades viven en un iframe
(`activityframe`) del mismo origen; cada tipo de ejercicio tiene su resolvedor y las respuestas salen
del banco `datos/respuestas_wide_angle_l<NIVEL>.json` (clave 'UU/LL/AA' = ruta de la URL de la actividad).

El nivel se elige con la variable de entorno OXFORD_NIVEL (por defecto 3, para no cambiar el
comportamiento historico). Cada nivel tiene su propio 'book id' en la plataforma y su propio banco:
    Level 3 -> book 74 -> respuestas_wide_angle_l3.json
    Level 4 -> book 75 -> respuestas_wide_angle_l4.json
    Level 5 -> book 76 (resuelto por test_wide_angle_auto.py leyendo el XML; sin banco a mano)
"""
import json
import logging
import os
import re
from pathlib import Path

from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PWTimeout

log = logging.getLogger("oxford.practica")

NIVEL = int(os.environ.get("OXFORD_NIVEL", "3"))
BOOKS = {3: 74, 4: 75, 5: 76}  # nivel de Wide Angle -> book id en wideangle.oxfordonlinepractice.com
BOOK_ID = BOOKS.get(NIVEL, 74)
BANCO = Path(__file__).resolve().parents[1] / "datos" / f"respuestas_wide_angle_l{NIVEL}.json"
IFRAME = 'iframe[name="activityframe"]'
BASE_LIBRO = f"https://wideangle.oxfordonlinepractice.com/app/dashboard/book/{BOOK_ID}"
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


class MaterialBloqueado(Exception):
    """El libro del usuario esta sin licencia (candado): hay que activarlo con un codigo."""


class PracticaPage:
    def __init__(self, page: Page):
        self.page = page
        self.marco = page.frame_locator(IFRAME)

    # ---- entrada ----
    @staticmethod
    def hay_candado(pagina_hub: Page) -> bool:
        """True si en la ficha del curso (Course Material) hay un candado: icono/imagen con 'lock' como PALABRA
        en alt, aria-label, title, data-testid, clase o src. 'block', 'clock' o 'unlock' NO cuentan."""
        try:
            return bool(pagina_hub.evaluate(r"""() => {
                const rx = /(^|[^a-z])lock(ed)?([^a-z]|$)/i;
                const texto = e => [e.getAttribute('alt'), e.getAttribute('aria-label'), e.getAttribute('title'),
                    e.getAttribute('data-testid'), e.getAttribute('src'),
                    typeof e.className === 'string' ? e.className : (e.className && e.className.baseVal) || ''
                ].filter(Boolean).join(' ');
                return [...document.querySelectorAll('img, svg, [class], [aria-label], [title], [data-testid]')]
                    .some(e => rx.test(texto(e)));
            }"""))
        except Exception:
            return False

    @staticmethod
    def abrir_desde_hub(pagina_hub: Page) -> "PracticaPage":
        """En la ficha del curso del Hub, abre la version 'Closing soon' (se abre en pestana nueva)."""
        enlace = pagina_hub.get_by_role("link", name=re.compile("closing soon", re.I)).first
        try:
            enlace.wait_for(state="visible", timeout=10_000)
            with pagina_hub.context.expect_page(timeout=15_000):
                enlace.click()
        except PWTimeout:
            # Material con candado (licencia sin activar): no hay enlace que abra la practica, o al
            # pulsarlo el Hub muestra el panel 'Activate code'. Se avisa para pasar al siguiente usuario.
            activar = pagina_hub.get_by_text(re.compile(r"activate code|enter your code", re.I)).first
            if PracticaPage.hay_candado(pagina_hub) or (activar.count() and activar.is_visible()):
                raise MaterialBloqueado("material Wide Angle con candado (pide 'Activate code')") from None
            raise
        # La pestana inicial es un intermedio LTI (/dashboard/lti) que redirige o se reemplaza: se espera
        # a la pestana del dashboard ya definitiva (ruta /app/dashboard/... sin 'lti').
        practica = None
        con_terminos = []                         # paginas ya atendidas: se aceptan UNA sola vez
        for _ in range(300):                      # 300 x 0.2 s = 60 s como maximo; se sale apenas aparece
            for candidata in pagina_hub.context.pages:
                if (not candidata.is_closed() and "oxfordonlinepractice.com/app/termsCondition" in candidata.url
                        and candidata not in con_terminos):
                    con_terminos.append(candidata)
                    PracticaPage._aceptar_terminos(candidata)     # primera vez de la cuenta: pide la edad
                if not candidata.is_closed() and re.search(r"oxfordonlinepractice\.com/app/dashboard(?!/lti)", candidata.url):
                    practica = candidata
                    break
            if practica:
                break
            pagina_hub.wait_for_timeout(200)
        assert practica, f"No se abrio el dashboard de practica: {[p.url for p in pagina_hub.context.pages]}"
        practica.wait_for_load_state("domcontentloaded")
        # Banner de cookies del sitio de practica (si no esta, no se espera: 2 s)
        try:
            practica.get_by_role("button", name=re.compile("^accept all$", re.I)).click(timeout=2_500)
        except Exception:
            pass
        log.info("Practica abierta: %s", practica.url)
        return PracticaPage(practica)

    @staticmethod
    def _aceptar_terminos(pagina: Page) -> None:
        """Pantalla 'Terms and Conditions' (se ve al abrir la practica con una cuenta nueva): elige
        'I am over 16 years of age', marca 'I agree to the Terms and Conditions' y pulsa Continue.

        La casilla de marketing ('tick this box if you do NOT want to receive email...') se deja como esta.
        """
        try:
            opcion = pagina.get_by_role("radio", name=re.compile(r"over\s+16", re.I))
            texto_edad = pagina.get_by_text(re.compile(r"I am\s+over\s+16", re.I))
            # Clic apenas pinta la pantalla (sin esperas fijas): lo primero que aparezca de las dos formas
            opcion.or_(texto_edad).first.wait_for(state="attached", timeout=10_000)
            if opcion.count():
                opcion.first.check(force=True)
            else:
                texto_edad.first.click()
            # La casilla 'I agree...' aparece al elegir la edad. Se marca la CASILLA (la primera; la segunda
            # es la de marketing), no el texto: pulsar el texto abre el documento de terminos.
            # El <input> esta oculto (la casilla que se ve es un cuadro dibujado aparte), por eso se marca
            # con un clic del propio elemento y no con el raton. Se espera a que aparezca tras elegir la edad.
            casilla = pagina.locator("input[type=checkbox]").first
            casilla.wait_for(state="attached", timeout=8_000)
            agree = pagina.get_by_role("button", name=re.compile(r"^\s*agree\s*$", re.I))

            def _aceptar_ventana():
                # Si el sitio abre la ventana con el texto de los terminos, se pulsa 'Agree' sin leerla
                try:
                    agree.first.wait_for(state="visible", timeout=1_500)
                    agree.first.click()
                    pagina.wait_for_timeout(500)
                except PWTimeout:
                    pass

            if not casilla.is_checked():
                casilla.evaluate("e => e.click()")
                _aceptar_ventana()
            if not casilla.is_checked():
                # Respaldo: clic con el raton sobre el cuadro, que queda a la izquierda del texto 'I agree...'
                caja = pagina.get_by_text(re.compile(r"^\s*I agree to the", re.I)).first.bounding_box()
                if caja:
                    for dx in (-19, 13):
                        pagina.mouse.click(caja["x"] + dx, caja["y"] + caja["height"] / 2)
                        _aceptar_ventana()
                        if casilla.is_checked():
                            break
            boton = pagina.get_by_role("button", name=re.compile(r"^\s*continue\s*$", re.I))
            expect(boton).to_be_enabled(timeout=5_000)
            boton.click()
            pagina.wait_for_timeout(1_500)
            log.info("Terms and Conditions: 'I am over 16 years of age' aceptado")
        except Exception as exc:
            log.warning("No pude aceptar Terms and Conditions: %s", str(exc).splitlines()[0])

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
        cuerpo = r"\s+".join(re.escape(t) for t in texto.split()) or re.escape(texto)
        return re.compile(rf"^\s*{cuerpo}\s*$")  # \s+ entre tokens tolera espacios duros (&#160;)

    @staticmethod
    def _subcadena(texto):
        """Subcadena tolerante a espacios duros, para ubicar frases largas al ordenar."""
        return re.compile(r"\s+".join(re.escape(t) for t in texto.split()) or re.escape(texto))

    def _arrastrar(self, spec):
        """El tipo 'arrastrar' abarca dos layouts del motor de actividades:
        - emparejar mitades: fichas .term -> casillas .target-box (0..n)
        - ordenar (sequencing): fichas .itemsUl .item -> ranuras .userItem[data-item-id=1..n]
        """
        if self.marco.locator(".target-box").count():
            for i, palabra in enumerate(spec["respuestas"]):
                origen = self.marco.locator(".term").filter(has_text=self._exacto(palabra)).first
                self._arrastrar_a(origen, self.marco.locator(".target-box").nth(i))
        else:
            for i, palabra in enumerate(spec["respuestas"], start=1):
                origen = self.marco.locator(".itemsUl .item").filter(has_text=self._subcadena(palabra)).first
                self._arrastrar_a(origen, self.marco.locator(f'.userItem[data-item-id="{i}"]'))

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
