"""Page Objects de Q10: una clase por pantalla, con sus selectores (donde) y sus acciones (que hacer)."""
import re
import time

from playwright.sync_api import expect

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
        if self.page.locator(self.CAPTCHA).is_visible():
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
    # Se usa el enlace y no la URL: tras el login Q10 cambia de servidor (site2 -> site3) y ese numero puede variar
    INFORMES = "nav.q10navbar a[href='/Informes']"

    def ir_a_informes(self):
        self.page.locator(self.INFORMES).click()
        self.page.wait_for_url(re.compile(r"/Informes", re.I))
        self.page.wait_for_load_state()
        return PaginaInformes(self.page)


class PaginaInformes(Pagina):
    """Lista de informes agrupados por seccion (Favoritos, Gestion academica...)."""

    def esta_abierta(self):
        return bool(re.search(r"/Informes/?$", self.page.url, re.I))

    def abrir_informe(self, nombre):
        # El nombre se compara sin importar mayusculas ni tildes: en el Config puede estar escrito
        # "Listado de Cursos" y en Q10 aparecer como "Listado de cursos".
        # Puede repetirse (Favoritos y su seccion), por eso se toma el primero.
        enlace = self.page.get_by_role("link", name=self.texto_exacto(nombre)).first
        if not enlace.count():
            buscado = self.normalizar(nombre)
            titulo = next((t for t in self.page.locator("a:visible").all_inner_texts()
                           if self.normalizar(t) == buscado), None)
            if titulo:
                enlace = self.page.get_by_role("link", name=self.texto_exacto(titulo)).first
        try:
            expect(enlace).to_be_visible(timeout=10_000)
        except AssertionError:
            parecidos = [" ".join(t.split()) for t in self.page.locator("a:visible").all_inner_texts()
                         if self.normalizar(nombre).split()[0] in self.normalizar(t)]
            raise ValueError(f"No encontre el informe '{nombre}'. Revisa Informes en Config Q10.txt."
                             + (f" Parecidos: {parecidos[:5]}" if parecidos else ""))
        print(f"  Clic en el informe: {' '.join(enlace.inner_text().split())}")
        enlace.click()
        self.page.wait_for_load_state()
        self.esperar(2_000)  # dar tiempo a que carguen las listas de filtros
        return FormularioInforme(self.page)


class FormularioInforme(Pagina):
    """Formulario de un informe: filtros (Sede, Programa, Periodo, Curso...) y boton Exportar."""
    TITULOS = "label:visible"
    FILA = "xpath=ancestor::div[contains(@class,'form-group')][1]"
    ERRORES = ".has-error label:visible, .field-validation-error:visible"
    # El boton para pedir el informe cambia segun el reporte: "Exportar reporte" en unos y
    # "Cargar reporte" (<button id="generar-reporte-btn" title="Generar reporte">) en otros
    GENERAR = "#generar-reporte-btn, [title='Generar reporte'], [title='Exportar reporte']"
    EXPORTAR = re.compile(r"exportar|generar|cargar", re.I)
    # Cuando el informe sale vacio, Q10 muestra "Sin resultados" con un boton para volver a pedirlo:
    # <button class="btn btn-link q10button pull-right reiniciar-tarea" title="Volver a generar">
    VOLVER_A_GENERAR = ".reiniciar-tarea, [title='Volver a generar']"
    TEXTO_VOLVER = re.compile(r"volver a generar", re.I)
    SIN_RESULTADOS = re.compile(r"sin resultados|no se encontraron resultados", re.I)
    # Cuando el informe si trae datos: <a id="abrir-reporte" title="Abrir reporte" href="/Archivo/Descargar?...">
    ABRIR_REPORTE = "#abrir-reporte, [title='Abrir reporte']"
    # Otros informes (como "Listado de cursos") muestran el reporte en un visor con un menu
    # "Exportar" donde se escoge el formato: PDF, XLSX, XLS, DOC, HTML, CSV, Imagen
    MENU_EXPORTAR = re.compile(r"^\s*exportar\s*$", re.I)

    def campo(self, nombre):
        """Control (select o input) del filtro cuyo titulo coincide con el nombre, o None si no existe."""
        for titulo in self.page.locator(self.TITULOS).all():
            if self.normalizar(titulo.inner_text()) != self.normalizar(nombre):
                continue
            destino = titulo.get_attribute("for")  # <label for="Curso"> apunta al control con id="Curso"
            control = (self.page.locator(f"[id='{destino}']") if destino
                       else titulo.locator(self.FILA).locator("select, input"))  # sin "for": misma fila
            return control.first if control.count() else None
        return None

    def llenar(self, nombre, valor):
        """Escoge o escribe el valor. Devuelve el texto exacto que quedo, o None si el filtro no existe."""
        campo = self.campo(nombre)
        if campo is None:
            print(f"  Filtro '{nombre}' no existe en este informe; se salta.")
            return None

        if campo.evaluate("el => el.tagName") == "SELECT":
            # Las listas dependen de la anterior (Sede -> Programa -> Periodo -> Curso): esperar a que cargue la opcion
            opcion = campo.locator("option").filter(has_text=self.texto_exacto(valor)).first
            try:
                expect(opcion).to_be_attached(timeout=15_000)
            except AssertionError:
                opciones = [o.strip() for o in campo.locator("option").all_inner_texts() if o.strip()]
                raise ValueError(f"'{valor}' no es una opcion de '{nombre}'. Opciones: {opciones}")
            valor = opcion.inner_text().strip()  # texto exacto de Q10 (mayusculas y tildes)
            # force: Q10 puede tapar el <select> real con una lista decorada; el valor igual se cambia
            campo.select_option(label=valor, force=True)
        else:
            campo.fill(valor)
        print(f"  {nombre}: {valor}")
        self.esperar(1_500)  # la siguiente lista se recarga segun esta
        return valor

    def valor_actual(self, nombre):
        """Texto que muestra hoy el filtro. Sirve para saber si ya dice "Todos" sin tocarlo."""
        campo = self.campo(nombre)
        if campo is None:
            return None
        if campo.evaluate("el => el.tagName") != "SELECT":
            return campo.input_value()
        return campo.evaluate(
            "el => el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : ''").strip()

    def opciones(self, nombre):
        """Todas las opciones de una lista (sin "Seleccione"), o None si el filtro no existe. Se usa para "Todos"."""
        campo = self.campo(nombre)
        if campo is None:
            return None
        opciones = campo.locator("option")
        try:
            # La lista se llena segun el filtro anterior: esperar a que haya algo mas que "Seleccione"
            expect(opciones.nth(1)).to_be_attached(timeout=15_000)
        except AssertionError:
            raise ValueError(f"La lista '{nombre}' no tiene opciones")
        return [o.strip() for o in opciones.all_inner_texts() if o.strip() and self.normalizar(o) != "seleccione"]

    def marcos(self):
        """Todos los marcos de todas las pestañas: Q10 abre el visor del reporte en una pestaña nueva."""
        for pagina in self.page.context.pages:
            try:
                for marco in pagina.frames:
                    yield marco
            except Exception:
                continue

    def boton_volver_a_generar(self):
        """Busca el boton "Volver a generar" en cualquier pestaña y dentro de sus marcos (iframes).

        Q10 dibuja ese panel de forma distinta segun el informe, por eso se prueban varias formas:
        por su clase, por el title, por el rol de boton y por el texto.
        """
        for marco in self.marcos():
            for candidato in (marco.locator(self.VOLVER_A_GENERAR),
                              marco.get_by_role("button", name=self.TEXTO_VOLVER),
                              marco.get_by_role("link", name=self.TEXTO_VOLVER),
                              marco.get_by_text(self.TEXTO_VOLVER)):
                try:
                    if candidato.count() and candidato.first.is_visible():
                        return candidato.first
                except Exception:
                    continue
        return None

    def menu_del_visor(self):
        """Menu "Exportar" del visor de reportes (no el boton "Exportar reporte" del formulario)."""
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

    def detalle_exportar(self):
        """Como son los elementos con texto 'Exportar' (para entender por que no se puede hacer clic)."""
        detalles = []
        for marco in self.marcos():
            try:
                candidatos = marco.get_by_text(self.MENU_EXPORTAR)
                for indice in range(min(candidatos.count(), 3)):
                    elemento = candidatos.nth(indice)
                    etiqueta = elemento.evaluate("el => el.tagName + '.' + (el.className || '')")[:40]
                    caja = elemento.bounding_box()
                    detalles.append(f"[{etiqueta} visible={elemento.is_visible()} caja={caja} "
                                    f"marco=...{marco.url[-30:]}]")
            except Exception:
                continue
        return " ".join(detalles) or "(ninguno)"

    def opcion_de_formato(self, formato):
        """Busca la opcion del formato (XLSX, CSV...) en cualquier marco: el menu puede dibujarse aparte."""
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

    # Orden de los formatos en el menu del visor (sirve para moverse con el teclado)
    FORMATOS_DEL_MENU = ["PDF", "XLSX", "XLS", "DOC", "HTML", "CSV", "IMAGEN"]

    def exportar_desde_visor(self, formato="XLSX", descargas=()):
        """Abre el menu "Exportar" del visor y escoge el formato (XLSX por defecto).

        El visor de Q10 no siempre deja leer su menu desde el codigo, asi que si no se encuentra
        la opcion se intenta con el teclado y, como ultimo recurso, con un clic por posicion.
        """
        marco, menu = self.menu_del_visor()
        if menu is None:
            return False
        caja = menu.bounding_box()
        pagina = marco.page
        print("  Clic en: Exportar (visor)")
        menu.click()
        self.esperar(2_000)  # el menu se despliega

        opcion = self.opcion_de_formato(formato)
        if opcion is not None:
            print(f"  Clic en: {formato}")
            try:
                opcion.click(timeout=15_000)
            except Exception:
                opcion.dispatch_event("click")   # si algo lo tapa, se le envia el evento directo
            return True

        # --- Respaldo 1: el menu no se puede leer, se recorre con las flechas del teclado ---
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

        # --- Respaldo 2: clic en la posicion donde se dibuja la opcion, debajo del boton ---
        if caja:
            alto = 36                      # alto aproximado de cada opcion del menu
            x = caja["x"] + caja["width"] / 2
            y = caja["y"] + caja["height"] + alto * (posicion - 0.5)
            print(f"  Clic por posicion en x={x:.0f} y={y:.0f}")
            pagina.mouse.click(x, y)
        return True

    def cerrar_pestanas_nuevas(self, pestanas_al_inicio):
        """Cierra el visor si Q10 lo abrio en una pestaña aparte, para no ir acumulando pestañas."""
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

    def volver_al_formulario(self):
        """Clic en "Volver a generar": regresa al formulario (en blanco) para el siguiente valor."""
        volver = self.boton_volver_a_generar()
        if volver:
            print("  Clic en: Volver a generar")
            volver.click()
            self.esperar(3_000)

    def diagnostico(self):
        """Que se ve en cada pestaña mientras se espera el archivo (para entender por que no llega)."""
        lineas = []
        for numero, pagina in enumerate(self.page.context.pages, start=1):
            try:
                datos = [f"pestaña {numero}", f"url=...{pagina.url[-40:]}", f"marcos={len(pagina.frames)}"]
                for nombre, selector in (("abrir-reporte", "#abrir-reporte"),
                                         ("reiniciar-tarea", ".reiniciar-tarea")):
                    datos.append(f"{nombre}={pagina.locator(selector).count()}")
                exportar = sum(marco.get_by_text(self.MENU_EXPORTAR).count() for marco in pagina.frames)
                datos.append(f"texto'Exportar'={exportar}")
                if exportar:
                    datos.append(f"detalle={self.detalle_exportar()}")
                texto = " ".join(pagina.locator("body").inner_text().split())[:70]
                datos.append(f"texto='{texto}'")
                lineas.append(" | ".join(datos))
            except Exception as error:
                lineas.append(f"pestaña {numero}: no pude leerla ({type(error).__name__})")
        return "\n      ".join(lineas)

    def exportar(self, espera=180, formato="XLSX"):
        """Clic en Exportar y devuelve la descarga.

        Al terminar de generar, Q10 responde de una de dos formas:
          - "El reporte se ha generado exitosamente" con el boton "Abrir reporte", que baja el archivo.
          - "Sin resultados", cuando no hay datos con esos filtros.
        En ambos casos se termina presionando "Volver a generar", que regresa al formulario (en blanco)
        para poder seguir con el siguiente valor del filtro.
        """
        exportar = self.page.locator(self.GENERAR).first
        if not exportar.count():
            exportar = self.page.get_by_role("button", name=self.EXPORTAR).or_(
                self.page.get_by_role("link", name=self.EXPORTAR)).first

        descargas = []
        contexto = self.page.context
        pestanas_al_inicio = list(contexto.pages)

        def guardar_descarga(descarga):
            descargas.append(descarga)

        def escuchar(pagina):
            """El visor puede abrirse en una pestaña nueva: hay que oir sus descargas tambien."""
            pagina.on("download", guardar_descarga)

        for pestana in contexto.pages:
            escuchar(pestana)
        contexto.on("page", escuchar)
        try:
            print(f"  Clic en: {' '.join(exportar.inner_text().split()) or 'Exportar'}")
            exportar.click()
            self.esperar(3_000)  # Q10 empieza a generar el informe

            limite = time.monotonic() + espera
            siguiente_aviso = time.monotonic() + 30
            visor_usado = False
            while time.monotonic() < limite:
                if descargas:
                    self.cerrar_pestanas_nuevas(pestanas_al_inicio)
                    self.volver_al_formulario()
                    return descargas[0]

                if not visor_usado and self.exportar_desde_visor(formato, descargas):
                    visor_usado = True      # el archivo llega por el menu del visor
                    continue

                abrir = self.page.locator(self.ABRIR_REPORTE).first
                if abrir.is_visible():
                    print("  Clic en: Abrir reporte")
                    abrir.click()
                    espera_archivo = time.monotonic() + 120
                    while not descargas and time.monotonic() < espera_archivo:
                        self.page.wait_for_timeout(1_000)
                    if not descargas:
                        raise ValueError("Di clic en 'Abrir reporte' pero no llego el archivo")
                    self.volver_al_formulario()
                    return descargas[0]

                if self.boton_volver_a_generar():
                    print("  Q10 respondio 'Sin resultados'")
                    self.volver_al_formulario()
                    raise ValueError("Q10 respondio 'Sin resultados'")

                requeridos = self.page.locator(self.ERRORES).all_inner_texts()
                if requeridos:
                    raise ValueError(f"Q10 pide llenar: "
                                     f"{[r.replace('*', '').strip() for r in requeridos]}")
                if time.monotonic() > siguiente_aviso:   # para saber que esta viendo el bot
                    print(f"    esperando...\n      {self.diagnostico()}")
                    siguiente_aviso = time.monotonic() + 15
                self.page.wait_for_timeout(1_000)

            raise ValueError(f"Di clic en 'Exportar' pero en {espera} s no llego ningun archivo. "
                             f"{self.diagnostico()}")
        finally:
            contexto.remove_listener("page", escuchar)
            for pestana in contexto.pages:
                try:
                    pestana.remove_listener("download", guardar_descarga)
                except Exception:
                    pass
