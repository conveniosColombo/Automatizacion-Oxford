"""Page Objects de Q10 (v3).

Hecho con el relevamiento de los 71 informes del menu Informes. Lo que hay que saber:

  - Los informes son enlaces 'a.reportes' con 'data-href="/Reporte/<Area>/<Nombre>"'. Al hacer clic
    el formulario se inyecta por AJAX EN LA MISMA URL (tarda hasta ~3 s): se espera #formReportes
    o #form0, nunca un tiempo fijo. En el Config se puede escribir el nombre, "Nombre (Seccion)"
    cuando se repite, o la direccion del informe (ListadoCursos), que es lo mas estable.
  - Segun como entregan el resultado hay cuatro familias:
      A  visor PDF en una ventana (#master-modal > iframe#report). Se exporta con la lista
         'select#exportSelect' (PDF, XLSX, XLS, DOC, HTML, CSV, Imagen) y se cierra con #close.
      B  tarea en segundo plano (#programar-reporte-btn): "Generando reporte" -> "El reporte se ha
         generado exitosamente" + "Abrir reporte" + "Volver a generar".
      C  descarga directa del Excel (#generar-reporte-btn en form0 / rutas /Reportes/Excel/).
      D  resultado pintado en la pantalla (/ReportePantalla/): no genera archivo.
    exportar() vigila A, B y C al mismo tiempo porque varios informes no dicen cual usan.
  - Los filtros no son solo listas: hay listas simples y multiples, radios, interruptores, grupos
    de casillas, rangos de fechas (con presets) y autocompletados de personas.
"""
import re
import time

from playwright.sync_api import expect

from core import modo
from core.pagina import Pagina


class LoginQ10(Pagina):
    """Ingreso: usuario -> Siguiente -> contrasena -> Ingresar -> ventana "Seleccione el rol"."""
    USUARIO = "#form-username"
    CLAVE = "#form-password"
    BOTON = "#btn-submit-login"          # dice "Siguiente" y despues "Ingresar"
    CAPTCHA = "#login-form-captcha"      # verificacion de Cloudflare: la resuelve una persona
    MENSAJES = "#login-form-messages"    # errores como clave incorrecta
    ROLES = "#roles a.list-group-item"   # opciones de la ventana de rol

    def iniciar_sesion(self, link, usuario, clave, rol):
        self.page.goto(link)
        self.page.locator(self.USUARIO).fill(usuario)
        self.page.locator(self.BOTON).click()

        # El campo de la contrasena ya existe pero oculto: esperar a que se muestre
        campo_clave = self.page.locator(self.CLAVE)
        expect(campo_clave).to_be_visible(timeout=15_000)
        campo_clave.fill(clave)
        self._esperar_captcha()
        self.page.locator(self.BOTON).click()

        self._elegir_rol(rol)
        return BarraQ10(self.page)

    def _esperar_captcha(self):
        """Q10 a veces pide verificacion de Cloudflare, que solo puede resolver una persona."""
        if not self.page.locator(self.CAPTCHA).is_visible():
            return
        if modo.AUTOMATICO:
            # Corriendo solo no hay quien la resuelva: se corta aqui con un mensaje claro
            raise ValueError("Q10 pidio verificacion de seguridad (captcha) y el bot corre solo. "
                             "Este informe hay que bajarlo a mano esta vez.")
        input("  Q10 pide verificacion de seguridad: resuelvela en el navegador y presiona Enter aqui...")

    def _elegir_rol(self, rol):
        opciones = self.page.locator(self.ROLES)
        opcion = opciones.filter(has_text=self.texto_exacto(rol))
        try:
            expect(opcion).to_be_visible(timeout=30_000)
        except AssertionError:
            if "/user/login" not in self.page.url.lower():
                return  # la cuenta tiene un solo rol y entro directo
            if opciones.count():
                raise ValueError(f"No existe el rol '{rol}'. Opciones: {opciones.all_inner_texts()}")
            mensaje = self.page.locator(self.MENSAJES).inner_text().strip()
            raise ValueError("No pude iniciar sesion en Q10" + (f": {mensaje}" if mensaje else ""))
        print(f"  Rol: {rol}")
        opcion.click()
        self.page.wait_for_url(lambda url: "/user/login" not in url.lower(), timeout=60_000)
        self.page.wait_for_load_state()


class BarraQ10(Pagina):
    """Barra superior azul (Institucional, Academico, Tesoreria, Informes)."""
    # Se usa el enlace y no la URL: tras el login Q10 cambia de servidor (site2 -> site3)
    INFORMES = "nav.q10navbar a[href='/Informes']"

    def ir_a_informes(self):
        """Vuelve al menu de informes.

        Ojo: el formulario de un informe se inyecta dentro de /Informes, asi que estar en esa
        direccion no significa ver el menu. Si el clic no lo trae de vuelta, se entra directo.
        """
        try:
            self.page.locator(self.INFORMES).click(timeout=8_000)
            self.page.wait_for_url(re.compile(r"/Informes", re.I))
            self.page.wait_for_load_state()
        except Exception as error:
            # El visor de un informe puede estar tapando la barra azul
            print(f"  No pude usar el boton Informes de la barra ({type(error).__name__})")
        informes = PaginaInformes(self.page)
        if not informes.esperar_lista(segundos=10):
            destino = re.sub(r"(https?://[^/]+).*", r"\1/Informes", self.page.url)
            print(f"  El menu no volvio con el clic; entro directo a {destino}")
            self.page.goto(destino)
            self.page.wait_for_load_state()
            informes.esperar_lista()
        return informes


class PaginaInformes(Pagina):
    """Menu de informes agrupados por seccion (Favoritos, Gestion academica, Comunidad en Excel...)."""
    ENLACES = "a.reportes"
    FORMULARIO = "#formReportes, #form0"
    VOLVER_A_GENERAR = ".reiniciar-tarea, [title='Volver a generar']"
    TEXTO_VOLVER = re.compile(r"volver a generar", re.I)
    # "Estudiantes (Comunidad en Excel)" -> nombre + seccion
    NOMBRE_CON_SECCION = re.compile(r"^(?P<nombre>.+?)\s*\((?P<seccion>[^()]+)\)\s*$")

    def hay_lista(self):
        """Si el menu de informes esta a la vista (y no el formulario de un informe)."""
        enlaces = self.page.locator(self.ENLACES)
        try:
            return enlaces.count() > 0 and enlaces.first.is_visible()
        except Exception:
            return False

    def esperar_lista(self, segundos=20):
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            if self.hay_lista():
                return True
            self.page.wait_for_timeout(500)
        return False

    def esta_abierta(self):
        """No basta la direccion: el formulario de un informe vive dentro de la misma /Informes."""
        return bool(re.search(r"/Informes/?$", self.page.url, re.I)) and self.hay_lista()

    def abrir_informe(self, pedido):
        """Abre el informe. Acepta el nombre, "Nombre (Seccion)" o su direccion (ListadoCursos)."""
        encontrado = self.NOMBRE_CON_SECCION.match(pedido)
        nombre = (encontrado["nombre"] if encontrado else pedido).strip()
        seccion = encontrado["seccion"].strip() if encontrado else None

        enlace = self.enlace_por_direccion(nombre) or self.enlace_por_texto(nombre, seccion)
        ruta = enlace.get_attribute("data-href") or ""
        print(f"  Clic en el informe: {' '.join(enlace.inner_text().split())}"
              + (f" [{seccion}]" if seccion else "") + (f"  ({ruta})" if ruta else ""))
        enlace.click()
        self.esperar_formulario()
        return FormularioInforme(self.page, ruta)

    def enlace_por_direccion(self, nombre):
        """Permite escribir la direccion del informe (ListadoCursos) en vez del nombre visible.

        Es la forma mas estable: no depende del texto ni de en que seccion este.
        """
        if " " in nombre:
            return None
        enlaces = self.page.locator(f'{self.ENLACES}[data-href$="/{nombre.strip("/")}"]')
        # El mismo informe puede estar en Favoritos y en su seccion: se usa el que se vea
        for indice in range(enlaces.count()):
            if enlaces.nth(indice).is_visible():
                return enlaces.nth(indice)
        return None

    def enlace_por_texto(self, nombre, seccion):
        enlaces = self.page.get_by_role("link", name=self.texto_exacto(nombre))
        if not enlaces.count():   # por si el Config lo escribio con otras mayusculas o tildes
            buscado = self.normalizar(nombre)
            titulo = next((t for t in self.page.locator("a:visible").all_inner_texts()
                           if self.normalizar(t) == buscado), None)
            if titulo:
                enlaces = self.page.get_by_role("link", name=self.texto_exacto(titulo))

        total = enlaces.count()
        if not total:
            parecidos = [" ".join(t.split()) for t in self.page.locator("a:visible").all_inner_texts()
                         if self.normalizar(nombre).split()[0] in self.normalizar(t)]
            raise ValueError(f"No encontre el informe '{nombre}'. Revisa Informes en Config Q10.txt."
                             + (f" Parecidos: {parecidos[:5]}" if parecidos else ""))

        indice = 0
        if total > 1:
            secciones = self.secciones_de(enlaces)
            if seccion:
                buscada = self.normalizar(seccion)
                indice = next((i for i, s in enumerate(secciones) if buscada in self.normalizar(s)), None)
                if indice is None:
                    raise ValueError(f"'{nombre}' no esta en la seccion '{seccion}'. "
                                     f"Esta en: {secciones}")
            else:
                print(f"  Aviso: '{nombre}' aparece {total} veces ({secciones}); uso el primero. "
                      f"Para escoger, escribe 'Nombre (Seccion)' en el Config")
        return enlaces.nth(indice)

    def secciones_de(self, enlaces):
        """Titulo de la seccion (Favoritos, Gestion academica...) de cada enlace repetido."""
        return enlaces.evaluate_all("""enlaces => enlaces.map(enlace => {
            let nodo = enlace, titulo = '';
            while (nodo && !titulo) {
                let anterior = nodo.previousElementSibling;
                while (anterior && !titulo) {
                    if (/^H[1-6]$/.test(anterior.tagName)) titulo = anterior.innerText;
                    anterior = anterior.previousElementSibling;
                }
                nodo = nodo.parentElement;
            }
            return titulo.trim();
        })""")

    def boton_volver(self):
        """El "Volver a generar" del resultado anterior (es un enlace, no siempre trae title)."""
        for candidato in (self.page.locator(self.VOLVER_A_GENERAR),
                          self.page.get_by_role("link", name=self.TEXTO_VOLVER),
                          self.page.get_by_role("button", name=self.TEXTO_VOLVER),
                          self.page.get_by_text(self.TEXTO_VOLVER)):
            try:
                if candidato.count() and candidato.first.is_visible():
                    return candidato.first
            except Exception:
                continue
        return None

    def esperar_formulario(self, segundos=30):
        """Espera el formulario, que se inyecta por AJAX en la misma URL (tarda ~3 s).

        A veces el informe no abre en el formulario sino en el resultado de una descarga anterior
        ("El reporte se ha generado exitosamente" + Abrir reporte). Ese reporte es viejo y tiene
        otros filtros, asi que hay que darle a "Volver a generar" para empezar de cero.
        """
        limite = time.monotonic() + segundos
        reinicios = 0
        while time.monotonic() < limite:
            formulario = self.page.locator(self.FORMULARIO).first
            if formulario.count() and formulario.is_visible():
                self.esperar(1_000)   # dar tiempo a que carguen las primeras listas
                return True

            volver = self.boton_volver()
            if reinicios < 2 and volver is not None:
                print("  El informe abrio con un reporte anterior; clic en 'Volver a generar'")
                try:
                    volver.click(timeout=10_000)
                except Exception:
                    volver.dispatch_event("click")
                reinicios += 1
                self.esperar(2_000)
            self.page.wait_for_timeout(500)
        raise ValueError("Di clic en el informe pero no aparecio el formulario de filtros")


class FormularioInforme(Pagina):
    """Formulario de un informe: sus filtros y el boton que pide el reporte."""
    TITULOS = "label:visible"
    FILA = ("xpath=ancestor::div[contains(@class,'row-filter') or contains(@class,'form-group')"
            " or contains(@class,'row')][1]")
    ERRORES = ".field-validation-error:visible, .has-error label:visible"

    # En orden de preferencia: si un informe trae "Exportar Excel" y "Cargar reporte", se usa el Excel
    BOTONES = ("#generar-excel-btn", "#generar-reporte-btn", "#programar-reporte-btn",
               "[title='Generar reporte']", "[title='Exportar reporte']")
    EXPORTAR = re.compile(r"exportar|generar|cargar", re.I)

    # Panel de resultado (familia B) y visor (familia A)
    VOLVER_A_GENERAR = ".reiniciar-tarea, [title='Volver a generar']"
    TEXTO_VOLVER = re.compile(r"volver a generar", re.I)
    ABRIR_REPORTE = "#abrir-reporte, [title='Abrir reporte']"
    EXITO = re.compile(r"se ha generado exitosamente", re.I)
    SIN_RESULTADOS = re.compile(r"sin resultados|no se encontraron|no hay datos", re.I)
    VISOR = "#master-modal"
    LISTA_DE_FORMATOS = "#exportSelect"      # visor pdf.js de Q10
    PAGINAS_DEL_VISOR = "#numPages"          # dice "de 0" mientras carga
    CERRAR_VISOR = "#close"
    MENU_EXPORTAR = re.compile(r"^\s*exportar\s*$", re.I)
    FORMATOS_DEL_MENU = ["PDF", "XLSX", "XLS", "DOC", "HTML", "CSV", "IMAGEN"]

    # Rango de fechas: se ve DD/MM/YYYY pero se guarda MM/DD/YYYY
    FECHA_INICIO = "input[id$='_InitialDate']"
    FECHA_FIN = "input[id$='_FinalDate']"
    # Solo la clase del calendario: si se buscara algo mas general (.input-group) se confundirian
    # con fechas los campos de texto con adorno, como "Valor inicial de efectivo"
    CALENDARIO = "[class*='daterange']"
    PRESETS = ".daterangepicker:visible .ranges li"
    RANGO = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})\s*(?:-|a|hasta)\s*(\d{1,2}/\d{1,2}/\d{4})")

    AUTOCOMPLETAR = ".selectize-control, input.ui-autocomplete-input"
    SUGERENCIAS = (".selectize-dropdown-content .option:visible, ul.ui-autocomplete:visible li,"
                   " .tt-suggestion:visible")
    INTERRUPTOR = ".bootstrap-switch, .make-switch"
    MARCAR_TODOS = "#todos"
    MARCAR_NINGUNO = "#ninguno"
    SI = re.compile(r"^\s*(si|sí|yes|true|1)\s*$", re.I)

    def __init__(self, page, ruta=""):
        super().__init__(page)
        self.ruta = ruta or ""       # data-href del informe: dice a que familia pertenece

    @property
    def familia(self):
        """A = visor PDF, B = tarea en segundo plano, C = descarga directa, D = solo pantalla."""
        ruta = self.ruta.lower()
        if "/reportepantalla/" in ruta:
            return "D"
        if self.page.locator("#programar-reporte-btn").count():
            return "B"
        if "/reportes/excel/" in ruta or self.page.locator("#form0").count():
            return "C"
        return "A"

    # ------------------------------------------------------------------ filtros ---
    def fila_del_filtro(self, nombre):
        """Fila del filtro cuyo titulo coincide, sin importar mayusculas, tildes ni el '*'.

        Solo mira las etiquetas VISIBLES: los informes con "Filtrar por" esconden los campos de
        los otros modos, y esos no se deben tocar.

        Ojo con los nombres repetidos: en varios informes el "Filtrar por" tiene las opciones
        "Programa" y "Curso", que se llaman igual que los filtros de verdad. Por eso se deja de
        ultimo el texto que solo es la etiqueta de un radio.
        """
        candidatos = []
        for titulo in self.page.locator(self.TITULOS).all():
            try:
                if self.normalizar(titulo.inner_text()) == self.normalizar(nombre):
                    candidatos.append(titulo)
            except Exception:
                continue
        if not candidatos:
            return None

        titulo = next((t for t in candidatos if not self.es_opcion_de_radio(t)), None)
        if titulo is None:
            return None     # ese nombre es solo una opcion de "Filtrar por", no un filtro
        fila = titulo.locator(self.FILA)
        if fila.count():
            return fila.first
        destino = titulo.get_attribute("for")
        if destino and self.page.locator(f"[id='{destino}']").count():
            return self.page.locator(f"[id='{destino}']")
        return None

    def es_opcion_de_radio(self, titulo):
        """True si ese texto es el nombre de una opcion (un radio) y no el nombre de un filtro."""
        destino = titulo.get_attribute("for")
        if not destino:
            return False
        control = self.page.locator(f"[id='{destino}']")
        if not control.count():
            return False
        return (control.first.get_attribute("type") or "").lower() == "radio"

    def esperar_ajax(self, segundos=15):
        """Las listas dependientes se recargan por AJAX: esperar a que la red se calme."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=segundos * 1_000)
        except Exception:
            pass

    def llenar(self, nombre, valor):
        """Pone el valor en el filtro, sea del tipo que sea."""
        fila = self.fila_del_filtro(nombre)
        if fila is None:
            print(f"  Filtro '{nombre}' no existe en este informe (o esta oculto); se salta.")
            return None

        if fila.locator("select").count():
            return self.escoger_de_lista(nombre, fila.locator("select").first, valor)
        if fila.locator(self.FECHA_INICIO).count() or fila.locator(self.CALENDARIO).count():
            return self.poner_fechas(nombre, fila, valor)
        if fila.locator(self.AUTOCOMPLETAR).count():
            return self.autocompletar(nombre, fila, valor)

        casillas = fila.locator("input[type=checkbox]")
        if casillas.count() > 1:
            return self.marcar_casillas(nombre, fila, valor)
        if casillas.count() == 1:
            return self.poner_interruptor(nombre, fila, casillas.first, valor)
        if fila.locator("input[type=radio]").count():
            return self.escoger_radio(nombre, fila, valor)

        texto = fila.locator("input:visible, textarea:visible").first
        if texto.count():
            texto.fill(valor)
            print(f"  {nombre}: {valor}")
            return valor
        print(f"  Filtro '{nombre}': no reconozco el tipo de control; se salta.")
        return None

    def escoger_de_lista(self, nombre, campo, valor):
        """Listas desplegables. En las de seleccion multiple se pueden pedir varias con ';'."""
        multiple = campo.get_attribute("multiple") is not None
        pedidos = [v.strip() for v in str(valor).split(";") if v.strip()] if multiple else [str(valor)]

        etiquetas = []
        for pedido in pedidos:
            # Las listas dependen de la anterior (Sede -> Programa -> Curso): esperar a que cargue
            opcion = campo.locator("option").filter(has_text=self.texto_exacto(pedido)).first
            try:
                expect(opcion).to_be_attached(timeout=15_000)
            except AssertionError:
                opciones = [o.strip() for o in campo.locator("option").all_inner_texts() if o.strip()]
                raise ValueError(f"'{pedido}' no es una opcion de '{nombre}'. Opciones: {opciones[:12]}")
            etiquetas.append(opcion.inner_text().strip())   # texto exacto de Q10

        # force: Q10 tapa el <select> real con un widget (bootstrap-select); el valor igual cambia
        campo.select_option(label=etiquetas if multiple else etiquetas[0], force=True)
        elegido = "; ".join(etiquetas)
        print(f"  {nombre}: {elegido}")
        self.esperar_ajax()                          # la lista siguiente se recarga sola
        return elegido

    def poner_interruptor(self, nombre, fila, casilla, valor):
        """Interruptores Si/No (¿Incluir archivados?, ¿Solo morosos?...).

        La casilla real esta oculta debajo del widget: se hace clic en el widget, que es lo que
        actualiza el campo escondido que Q10 envia.
        """
        quiero = bool(self.SI.match(str(valor).strip()))
        if casilla.is_checked() == quiero:
            print(f"  {nombre}: {valor} (ya estaba asi)")
            return valor

        widget = fila.locator(self.INTERRUPTOR).first
        if widget.count():
            try:
                widget.click(timeout=5_000)
            except Exception:
                pass
        if casilla.is_checked() != quiero:
            try:
                casilla.set_checked(quiero, force=True)
            except Exception:
                casilla.evaluate("(el, quiero) => { el.checked = quiero;"
                                 " el.dispatchEvent(new Event('change', {bubbles: true})); }", quiero)
            self.poner_campo_escondido(casilla, quiero)
        print(f"  {nombre}: {valor}")
        self.esperar_ajax()
        return valor

    def poner_campo_escondido(self, casilla, quiero):
        """Cada interruptor '#algo-switch' tiene un campo escondido '#algo' que es el que se envia."""
        identificador = casilla.get_attribute("id") or ""
        gemelo = identificador.replace("-switch", "")
        if not gemelo or gemelo == identificador:
            return
        escondido = self.page.locator(f"input[type=hidden][id='{gemelo}']")
        if escondido.count():
            escondido.evaluate("(el, valor) => el.value = valor", "true" if quiero else "false")

    def escoger_radio(self, nombre, fila, valor):
        """Opciones tipo radio (Estado: Todos/Activos/Inactivos, Filtrar por: Programa/Curso...)."""
        radios = fila.locator("input[type=radio]")
        textos = []
        for indice in range(radios.count()):
            radio = radios.nth(indice)
            texto = self.texto_de(fila, radio)
            textos.append(texto)
            if self.normalizar(texto) == self.normalizar(valor):
                try:
                    radio.check(force=True)
                except Exception:
                    radio.evaluate("el => { el.checked = true;"
                                   " el.dispatchEvent(new Event('change', {bubbles: true})); }")
                print(f"  {nombre}: {texto}")
                self.esperar(1_000)   # "Filtrar por" muestra y esconde otros filtros
                return texto
        raise ValueError(f"'{valor}' no es una opcion de '{nombre}'. Opciones: {textos}")

    def texto_de(self, fila, control):
        """Texto de la etiqueta de un radio o una casilla (o su valor, si no tiene etiqueta)."""
        identificador = control.get_attribute("id") or ""
        if identificador:
            etiqueta = fila.locator(f"label[for='{identificador}']")
            if etiqueta.count():
                return " ".join(etiqueta.first.inner_text().split())
        return (control.get_attribute("value") or identificador).strip()

    def marcar_casillas(self, nombre, fila, valor):
        """Grupos de casillas (los "Campos" de Comunidad en Excel, que vienen todos marcados).

        Acepta Todos, Ninguno o una lista separada con ';'.
        """
        pedido = str(valor).strip()
        if self.normalizar(pedido) in ("todos", "todas"):
            enlace = self.page.locator(self.MARCAR_TODOS).first
            if enlace.count():
                enlace.click()
                print(f"  {nombre}: Todos")
                return "Todos"
        if self.normalizar(pedido) in ("ninguno", "ninguna"):
            enlace = self.page.locator(self.MARCAR_NINGUNO).first
            if enlace.count():
                enlace.click()
                print(f"  {nombre}: Ninguno")
                return "Ninguno"

        # Lista concreta: se desmarca todo y se marcan solo los pedidos
        deseados = [self.normalizar(c) for c in pedido.split(";") if c.strip()]
        ninguno = self.page.locator(self.MARCAR_NINGUNO).first
        if ninguno.count():
            ninguno.click()
        casillas = fila.locator("input[type=checkbox]")
        marcados, disponibles = [], []
        for indice in range(casillas.count()):
            casilla = casillas.nth(indice)
            texto = self.texto_de(fila, casilla)
            disponibles.append(texto)
            if self.normalizar(texto) in deseados:
                casilla.check(force=True)
                marcados.append(texto)
        if not marcados:
            raise ValueError(f"Ninguno de esos campos existe en '{nombre}'. Hay: {disponibles[:10]}")
        print(f"  {nombre}: {len(marcados)} campo(s) marcados")
        return "; ".join(marcados)

    def poner_fechas(self, nombre, fila, valor):
        """Rango de fechas. Acepta "01/09/2026 - 30/09/2026" o un preset (Hoy, Este mes, Todas...).

        El calendario muestra DD/MM/YYYY pero Q10 guarda MM/DD/YYYY en dos campos escondidos.
        """
        rango = self.RANGO.search(str(valor))
        if rango:
            def a_formato_q10(fecha):
                dia, mes, anio = fecha.split("/")
                return f"{int(mes):02d}/{int(dia):02d}/{anio}"

            for selector, fecha in ((self.FECHA_INICIO, a_formato_q10(rango[1])),
                                    (self.FECHA_FIN, a_formato_q10(rango[2]))):
                campo = fila.locator(selector).first
                if not campo.count():
                    raise ValueError(f"'{nombre}' no guarda el rango como espera el bot")
                campo.evaluate("(el, fecha) => { el.value = fecha;"
                               " el.dispatchEvent(new Event('change', {bubbles: true})); }", fecha)
            print(f"  {nombre}: {rango[1]} a {rango[2]}")
            return f"{rango[1]} a {rango[2]}"
        return self.escoger_preset(nombre, fila, valor)

    def escoger_preset(self, nombre, fila, valor):
        """Presets del calendario: Hoy, Ayer, Ultimos 7 dias, Este mes, Todas..."""
        abridor = fila.locator(f"{self.CALENDARIO}:visible, input:visible, button:visible").first
        if not abridor.count():
            print(f"  Filtro '{nombre}': no pude abrir el calendario; se salta.")
            return None
        abridor.click()
        self.esperar(500)
        presets = self.page.locator(self.PRESETS)
        disponibles = []
        for indice in range(presets.count()):
            opcion = presets.nth(indice)
            texto = " ".join(opcion.inner_text().split())
            disponibles.append(texto)
            if self.normalizar(texto) == self.normalizar(valor):
                opcion.click()
                print(f"  {nombre}: {texto}")
                return texto
        self.page.keyboard.press("Escape")
        raise ValueError(f"'{valor}' no es un rango ni un preset de '{nombre}'. "
                         f"Presets: {disponibles or 'ninguno'}")

    def autocompletar(self, nombre, fila, valor):
        """Campos de persona (docente, asesor, cajero): se escribe y se escoge de la lista."""
        campo = fila.locator(".selectize-input input, input.ui-autocomplete-input, input:visible").first
        campo.click()
        campo.fill("")
        campo.type(str(valor), delay=80)
        sugerencias = self.page.locator(self.SUGERENCIAS)
        try:
            expect(sugerencias.first).to_be_visible(timeout=15_000)
        except AssertionError:
            raise ValueError(f"'{valor}' no dio ninguna sugerencia en '{nombre}'")
        for indice in range(min(sugerencias.count(), 20)):
            opcion = sugerencias.nth(indice)
            texto = " ".join(opcion.inner_text().split())
            if self.normalizar(valor) in self.normalizar(texto):
                opcion.click()
                print(f"  {nombre}: {texto}")
                return texto
        elegido = " ".join(sugerencias.first.inner_text().split())
        sugerencias.first.click()
        print(f"  {nombre}: {elegido} (la primera sugerencia)")
        return elegido

    def existe(self, nombre):
        """Si el informe tiene ese filtro a la vista."""
        return self.fila_del_filtro(nombre) is not None

    def valor_actual(self, nombre):
        """Texto que muestra hoy el filtro. Sirve para saber si ya dice "Todos" sin tocarlo."""
        fila = self.fila_del_filtro(nombre)
        if fila is None:
            return None
        campo = fila.locator("select").first
        if not campo.count():
            return None
        return campo.evaluate(
            "el => el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : ''").strip()

    def opciones(self, nombre):
        """Opciones de una lista (sin "Seleccione"), o None si el filtro no es una lista."""
        fila = self.fila_del_filtro(nombre)
        if fila is None:
            return None
        campo = fila.locator("select").first
        if not campo.count():
            return None
        opciones = campo.locator("option")
        try:
            expect(opciones.nth(1)).to_be_attached(timeout=15_000)
        except AssertionError:
            raise ValueError(f"La lista '{nombre}' no tiene opciones")
        return [o.strip() for o in opciones.all_inner_texts()
                if o.strip() and self.normalizar(o) != "seleccione"]

    # --------------------------------------------------------- pedir el reporte ---
    def boton_generar(self, obligatorio=True):
        """Primer boton VISIBLE para pedir el informe, en orden de preferencia.

        Se busca el visible y no el primero que exista: Q10 deja botones escondidos en el
        formulario y esperar por uno oculto termina en timeout.
        """
        for selector in self.BOTONES:
            candidatos = self.page.locator(selector)
            try:
                for indice in range(min(candidatos.count(), 5)):
                    if candidatos.nth(indice).is_visible():
                        return candidatos.nth(indice)
            except Exception:
                continue
        for candidatos in (self.page.get_by_role("button", name=self.EXPORTAR),
                           self.page.get_by_role("link", name=self.EXPORTAR)):
            try:
                for indice in range(min(candidatos.count(), 5)):
                    if candidatos.nth(indice).is_visible():
                        return candidatos.nth(indice)
            except Exception:
                continue
        if not obligatorio:
            return None
        raise ValueError("No encontre el boton para pedir el informe en esta pantalla")

    def que_lo_tapa(self, elemento):
        """Nombre del elemento que esta encima (si algo tapa al boton y no deja hacer clic)."""
        try:
            return elemento.evaluate("""el => {
                const caja = el.getBoundingClientRect();
                const encima = document.elementFromPoint(caja.left + caja.width / 2,
                                                         caja.top + caja.height / 2);
                if (!encima || encima === el || el.contains(encima)) return '';
                return encima.tagName.toLowerCase() + (encima.id ? '#' + encima.id : '') +
                       (encima.className ? '.' + String(encima.className).trim().split(/\\s+/)[0] : '');
            }""")
        except Exception:
            return ""

    def clic_en_generar(self, boton):
        """Clic en el boton de pedir el informe, contando lo que pase si no se deja."""
        etiqueta = " ".join(boton.inner_text().split()) or "Exportar"
        print(f"  Clic en: {etiqueta}")
        try:
            boton.scroll_into_view_if_needed(timeout=5_000)
        except Exception:
            pass
        # Un boton deshabilitado no recibe clics del raton (ni a la fuerza): se le avisa directo
        if not boton.is_enabled():
            print("  El boton esta bloqueado por el informe anterior; le aviso directamente")
            boton.dispatch_event("click")
            return
        try:
            boton.click(timeout=20_000)
            return
        except Exception as error:
            estorbo = self.que_lo_tapa(boton)
            print(f"  El clic normal no paso ({type(error).__name__}; "
                  f"habilitado={boton.is_enabled()}"
                  + (f", encima esta {estorbo}" if estorbo else "") + ")")
        # Suele ser un panel del informe anterior encima: se intenta a la fuerza y, si no, se
        # avisa al elemento directamente (asi se soluciono el mismo problema en Macmillan)
        try:
            boton.click(force=True, timeout=5_000)
            print("  Clic a la fuerza: hecho")
        except Exception:
            boton.dispatch_event("click")
            print("  Clic enviado directo al boton")

    # ------------------------------------------------------------- el resultado ---
    def marcos(self):
        """Todos los marcos de todas las pestañas: el visor puede abrirse aparte."""
        for pagina in self.page.context.pages:
            try:
                for marco in pagina.frames:
                    yield marco
            except Exception:
                continue

    def visible(self, buscador):
        """True si ese texto o elemento se ve en alguna pestaña (sin reventar si algo falla)."""
        try:
            return buscador.count() > 0 and buscador.first.is_visible()
        except Exception:
            return False

    def boton_volver_a_generar(self):
        for marco in self.marcos():
            for candidato in (marco.locator(self.VOLVER_A_GENERAR),
                              marco.get_by_role("button", name=self.TEXTO_VOLVER),
                              marco.get_by_role("link", name=self.TEXTO_VOLVER),
                              marco.get_by_text(self.TEXTO_VOLVER)):
                if self.visible(candidato):
                    return candidato.first
        return None

    def lista_de_formatos(self):
        """Visor PDF de Q10: la exportacion es una lista 'select#exportSelect' dentro del marco."""
        for marco in self.marcos():
            candidato = marco.locator(self.LISTA_DE_FORMATOS)
            if self.visible(candidato):
                return marco, candidato.first
        return None, None

    def esperar_visor(self, marco, segundos=60):
        """El visor dice "de 0" mientras arma el PDF (tarda 15-20 s): esperar a que tenga paginas."""
        contador = marco.locator(self.PAGINAS_DEL_VISOR)
        if not contador.count():
            return True                      # ese visor no tiene contador de paginas
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            try:
                if re.search(r"[1-9]", contador.inner_text()):
                    return True
            except Exception:
                return True
            marco.page.wait_for_timeout(1_000)
        print("  Aviso: el visor sigue diciendo que no tiene paginas; intento exportar igual")
        return False

    def menu_del_visor(self):
        """Menu "Exportar" del visor (no el boton "Exportar reporte" del formulario)."""
        for marco in self.marcos():
            for candidato in (marco.get_by_role("button", name=self.MENU_EXPORTAR),
                              marco.get_by_role("link", name=self.MENU_EXPORTAR),
                              marco.locator("[title*='Exportar' i], [aria-label*='Exportar' i]"),
                              marco.locator("[class*='export' i]"),
                              marco.get_by_text(self.MENU_EXPORTAR)):
                try:
                    for indice in range(min(candidato.count(), 5)):
                        elemento = candidato.nth(indice)
                        if elemento.is_visible():
                            return marco, elemento
                except Exception:
                    continue
        return None, None

    def opcion_de_formato(self, formato):
        patron = re.compile(rf"^\s*{re.escape(formato)}\s*$", re.I)
        for marco in self.marcos():
            for candidato in (marco.get_by_role("menuitem", name=patron),
                              marco.get_by_role("link", name=patron),
                              marco.get_by_role("button", name=patron),
                              marco.get_by_text(patron)):
                try:
                    for indice in range(min(candidato.count(), 5)):
                        elemento = candidato.nth(indice)
                        if elemento.is_visible():
                            return elemento
                except Exception:
                    continue
        return None

    def exportar_desde_visor(self, formato="XLSX", descargas=()):
        """Saca el archivo del visor: primero la lista de formatos y si no, el menu "Exportar"."""
        marco, lista = self.lista_de_formatos()
        if lista is not None:
            self.esperar_visor(marco)
            print(f"  Visor: escojo {formato} en la lista de exportar")
            try:
                lista.select_option(label=formato, force=True)
            except Exception:
                lista.select_option(value=formato.lower(), force=True)
            espera = time.monotonic() + 30
            while not descargas and time.monotonic() < espera:
                marco.page.wait_for_timeout(500)
            return True
        return self.exportar_desde_menu(formato, descargas)

    def exportar_desde_menu(self, formato="XLSX", descargas=()):
        """Visores viejos: un menu "Exportar" que abre la lista de formatos.

        A veces el menu no se puede leer desde el codigo, asi que hay dos respaldos: recorrerlo
        con el teclado y, si no, hacer clic donde se dibuja la opcion.
        """
        marco, menu = self.menu_del_visor()
        if menu is None:
            return False
        caja = menu.bounding_box()
        pagina = marco.page
        print("  Clic en: Exportar (visor)")
        menu.click()
        self.esperar(2_000)

        opcion = self.opcion_de_formato(formato)
        if opcion is not None:
            print(f"  Clic en: {formato}")
            try:
                opcion.click(timeout=15_000)
            except Exception:
                opcion.dispatch_event("click")
            return True

        posicion = self.FORMATOS_DEL_MENU.index(formato.upper()) + 1
        print(f"  No pude leer el menu; bajo {posicion} veces con el teclado y doy Enter")
        for _ in range(posicion):
            pagina.keyboard.press("ArrowDown")
            pagina.wait_for_timeout(250)
        pagina.keyboard.press("Enter")

        espera = time.monotonic() + 8
        while not descargas and time.monotonic() < espera:
            pagina.wait_for_timeout(500)
        if descargas:
            return True

        if caja:
            alto = 36
            x = caja["x"] + caja["width"] / 2
            y = caja["y"] + caja["height"] + alto * (posicion - 0.5)
            print(f"  Clic por posicion en x={x:.0f} y={y:.0f}")
            pagina.mouse.click(x, y)
        return True

    def cerrar_resultado(self, pestanas_al_inicio):
        """Cierra el visor y las pestañas que abrio el informe, para dejar la pantalla limpia."""
        for marco in self.marcos():
            cerrar = marco.locator(self.CERRAR_VISOR)
            if self.visible(cerrar):
                try:
                    cerrar.first.click(timeout=5_000)
                except Exception:
                    pass
                break
        if self.visible(self.page.locator(self.VISOR)):
            self.page.keyboard.press("Escape")
        for pestana in self.page.context.pages:
            if pestana not in pestanas_al_inicio:
                try:
                    pestana.close()
                except Exception:
                    pass
        try:
            self.page.bring_to_front()
        except Exception:
            pass

    def listo_para_otro_informe(self):
        """El boton de pedir el informe se ve y no esta bloqueado por el informe anterior."""
        boton = self.boton_generar(obligatorio=False)
        try:
            return bool(boton and boton.is_enabled())
        except Exception:
            return False

    def volver_al_formulario(self, espera=15):
        """Deja la pantalla lista para el siguiente valor.

        Q10 muestra "Volver a generar" un momento DESPUES de entregar el archivo, y mientras ese
        panel siga ahi el boton de pedir el informe queda bloqueado. Por eso se espera a que
        aparezca en vez de mirar una sola vez.
        """
        limite = time.monotonic() + espera
        while time.monotonic() < limite:
            volver = self.boton_volver_a_generar()
            if volver:
                print("  Clic en: Volver a generar")
                try:
                    volver.click(timeout=10_000)
                except Exception:
                    volver.dispatch_event("click")
                self.esperar(3_000)
                return True
            if self.listo_para_otro_informe():
                return True          # el formulario quedo servible: no hay nada que limpiar
            self.page.wait_for_timeout(1_000)
        print("  Aviso: el informe anterior no se cerro solo; el siguiente puede tardar mas")
        return False

    def diagnostico(self):
        """Que se ve en cada pestaña mientras se espera el archivo."""
        lineas = []
        for numero, pagina in enumerate(self.page.context.pages, start=1):
            try:
                datos = [f"pestaña {numero}", f"url=...{pagina.url[-40:]}", f"marcos={len(pagina.frames)}"]
                for nombre, selector in (("abrir-reporte", "#abrir-reporte"),
                                         ("reiniciar-tarea", ".reiniciar-tarea"),
                                         ("visor", self.VISOR),
                                         ("lista-formatos", self.LISTA_DE_FORMATOS)):
                    datos.append(f"{nombre}={pagina.locator(selector).count()}")
                texto = " ".join(pagina.locator("body").inner_text().split())[:70]
                datos.append(f"texto='{texto}'")
                lineas.append(" | ".join(datos))
            except Exception as error:
                lineas.append(f"pestaña {numero}: no pude leerla ({type(error).__name__})")
        return "\n      ".join(lineas)

    def exportar(self, espera=240, formato="XLSX"):
        """Pide el informe y devuelve el archivo.

        Se vigilan a la vez las tres formas en que Q10 responde: el visor con su lista de formatos
        (familia A), el panel "Abrir reporte" de las tareas en segundo plano (B) y la descarga
        directa (C). Tambien se detecta "Sin resultados" y los campos requeridos sin llenar.
        """
        if self.familia == "D":
            raise ValueError("Este informe muestra el resultado en la pantalla y no genera archivo")

        boton = self.boton_generar()
        descargas = []
        contexto = self.page.context
        pestanas_al_inicio = list(contexto.pages)

        def guardar_descarga(descarga):
            descargas.append(descarga)

        def escuchar(pagina):
            pagina.on("download", guardar_descarga)

        for pestana in contexto.pages:
            escuchar(pestana)
        contexto.on("page", escuchar)
        try:
            self.clic_en_generar(boton)
            self.esperar(3_000)

            limite = time.monotonic() + espera
            siguiente_aviso = time.monotonic() + 30
            visor_usado = reporte_abierto = False
            while time.monotonic() < limite:
                if descargas:
                    self.cerrar_resultado(pestanas_al_inicio)
                    self.volver_al_formulario()
                    return descargas[0]

                if not visor_usado and self.exportar_desde_visor(formato, descargas):
                    visor_usado = True
                    continue

                # "Abrir reporte" a veces baja el archivo y a veces abre el visor: se da el clic
                # una sola vez y se sigue vigilando, que para eso esta el ciclo
                abrir = self.page.locator(self.ABRIR_REPORTE).first
                if not reporte_abierto and self.visible(abrir):
                    print("  Clic en: Abrir reporte")
                    abrir.click()
                    reporte_abierto = True
                    self.esperar(3_000)
                    continue

                # "Sin resultados" o el panel de volver a empezar sin nada que abrir.
                # Si ya se abrio el reporte, hubo datos: lo que queda es esperar el visor.
                generando = self.visible(self.page.get_by_text(self.EXITO))
                if not reporte_abierto and (self.visible(self.page.get_by_text(self.SIN_RESULTADOS))
                                            or (not generando and self.boton_volver_a_generar())):
                    print("  Q10 respondio 'Sin resultados'")
                    self.volver_al_formulario()
                    raise ValueError("Q10 respondio 'Sin resultados'")

                requeridos = self.page.locator(self.ERRORES).all_inner_texts()
                if requeridos:
                    raise ValueError(f"Q10 pide llenar: "
                                     f"{[r.replace('*', '').strip() for r in requeridos]}")
                if time.monotonic() > siguiente_aviso:
                    print(f"    esperando...\n      {self.diagnostico()}")
                    siguiente_aviso = time.monotonic() + 15
                self.page.wait_for_timeout(1_000)

            raise ValueError(f"Pedi el informe pero en {espera} s no llego ningun archivo. "
                             f"{self.diagnostico()}")
        finally:
            contexto.remove_listener("page", escuchar)
            for pestana in contexto.pages:
                try:
                    pestana.remove_listener("download", guardar_descarga)
                except Exception:
                    pass
