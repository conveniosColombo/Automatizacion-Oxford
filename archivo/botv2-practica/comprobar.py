"""Comprueba los retos de RETOS.md.

Uso: doble clic en "Comprobar retos.bat".
Con el argumento --solucion revisa la carpeta ..\\botv2 en vez de esta (sirve para ver como se ve todo en verde).
"""
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
PROYECTO = CARPETA.parent
SOLUCION = "--solucion" in sys.argv
CODIGO = PROYECTO / "botv2" if SOLUCION else CARPETA

# Dejar en el camino de importacion solo la carpeta que se va a revisar
sys.path[:] = [p for p in sys.path if Path(p).resolve() != CARPETA]
sys.path.insert(0, str(CODIGO))

HTML_FORMULARIO = """
<form>
 <div class="form-group"><label for="sede">Sede - jornada <span>*</span></label>
  <select id="sede"><option>Seleccione</option><option>B2G - Única</option></select></div>
 <div class="form-group"><label for="curso">Curso *</label><select id="curso"><option>Seleccione</option></select></div>
 <button type="button" id="exp">Exportar reporte</button>
</form>
<script>
 sede.addEventListener('change', () => setTimeout(() => curso.innerHTML +=
   '<option>C1.1-7PM217 SDDE</option><option>C1.2-5PM101 GT</option>', 600));
 exp.onclick = () => { const a = document.createElement('a');
   a.href = URL.createObjectURL(new Blob([curso.value])); a.download = 'Inasistencias.xlsx';
   document.body.appendChild(a); a.click(); };
</script>
"""

RETOS = []


def reto(numero, titulo):
    def decorador(funcion):
        RETOS.append((numero, titulo, funcion))
        return funcion
    return decorador


@contextmanager
def carpeta_con(archivos_txt):
    """Carpeta temporal con esos .txt, usada como CARPETA mientras dure el bloque."""
    from core import archivos
    temporal = Path(tempfile.mkdtemp(prefix="retos_"))
    original = archivos.CARPETA
    archivos.CARPETA = temporal
    try:
        for nombre, contenido in archivos_txt.items():
            (temporal / nombre).write_text(contenido, encoding="utf-8")
        yield temporal
    finally:
        archivos.CARPETA = original
        shutil.rmtree(temporal, ignore_errors=True)


class DescargaFalsa:
    """Imita lo que entrega Playwright al descargar, para probar guardar_descarga sin navegador."""
    suggested_filename = "Reporte_16Sep2026.xlsx"

    def save_as(self, ruta):
        Path(ruta).write_text("contenido", encoding="utf-8")


@contextmanager
def pagina_de_prueba(html):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="msedge")
        page = navegador.new_page()
        page.set_content(html)
        try:
            yield page
        finally:
            navegador.close()


@reto(1, "core/archivos.py: CARPETA y leer_txt")
def reto_1():
    from core import archivos
    assert archivos.CARPETA == PROYECTO, f"CARPETA deberia ser {PROYECTO}, no {archivos.CARPETA}"
    with carpeta_con({"Config Prueba.txt": "# comentario\nNombre : Juan\nEdad:30\nsin dos puntos\n"}):
        datos = archivos.leer_txt("Config Prueba.txt")
        assert datos == {"nombre": "Juan", "edad": "30"}, f"leer_txt devolvio {datos}"
        try:
            archivos.leer_txt("No existe.txt")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("leer_txt deberia lanzar FileNotFoundError si el archivo no existe")


@reto(2, "core/archivos.py: separar_lista y es_plantilla")
def reto_2():
    from core import archivos
    assert archivos.separar_lista("a, b , c") == ["a", "b", "c"]
    assert archivos.separar_lista(" ") == []
    assert archivos.es_plantilla("escribe_aqui_tu_clave")
    assert archivos.es_plantilla("Coloca aquí tu usuario q10")
    assert not archivos.es_plantilla("sebastian.mendez@colombobogota.edu.co")


@reto(3, "core/archivos.py: clase Credenciales")
def reto_3():
    from core.archivos import Credenciales
    completas = "User : ana\nPassword : 123\nLink : https://site2.q10.com/User/Login\n"
    with carpeta_con({"Credenciales Q10.txt": completas}):
        credenciales = Credenciales.de_sistema("Q10")
        assert (credenciales.usuario, credenciales.clave) == ("ana", "123"), "los campos no quedaron bien"
        assert credenciales.link.startswith("https://"), "falta el link"
    plantilla = "User : escribe_aqui_tu_usuario\nPassword : \nLink : https://x\n"
    with carpeta_con({"Credenciales Q10.txt": plantilla}):
        try:
            Credenciales.de_sistema("Q10")
        except ValueError as error:
            assert "user" in str(error) and "password" in str(error), f"el mensaje no dice que falta: {error}"
        else:
            raise AssertionError("con la plantilla sin llenar deberia lanzar ValueError")


@reto(4, "core/archivos.py: guardar_descarga y nombre_archivo")
def reto_4():
    from core import archivos
    assert archivos.nombre_archivo("C1.1-7PM217 SDDE (B2G)") == "C1.1-7PM217_SDDE_B2G_"
    with carpeta_con({}) as temporal:
        ruta = archivos.guardar_descarga(DescargaFalsa(), "Q10", "Inasistencias C1.1")
        assert ruta.exists(), "el archivo no quedo guardado"
        assert ruta.parent == temporal / "Descargas" / "Q10", f"quedo en {ruta.parent}"
        assert ruta.suffix == ".xlsx", "deberia conservar la extension del archivo descargado"
        assert "Inasistencias_C1.1" in ruta.name, f"el nombre no lleva el prefijo: {ruta.name}"
        assert ruta.name[:4].isdigit(), f"el nombre deberia empezar con la fecha: {ruta.name}"


@reto(5, "core/navegador.py y core/errores.py")
def reto_5():
    from core.errores import resumen
    assert resumen(ValueError("No encontre la clase 'X'")) == "ValueError: No encontre la clase 'X'"
    assert resumen(ValueError()) == "ValueError: ", "un error sin mensaje no debe romper resumen()"
    from core.navegador import abrir_navegador
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        navegador = abrir_navegador(p, visible=False)
        assert navegador.is_connected(), "el navegador no abrio"
        navegador.close()


@reto(6, "core/pagina.py: clase Pagina")
def reto_6():
    from core.pagina import Pagina
    assert Pagina.normalizar("Período *") == Pagina.normalizar("periodo"), "normalizar no quita tildes ni *"
    assert Pagina.normalizar("  Sede -  jornada ") == "sede - jornada"
    patron = Pagina.texto_exacto("Curso 1")
    assert patron.search("  curso 1 "), "texto_exacto deberia ignorar mayusculas y espacios"
    assert not patron.search("Curso 10"), "texto_exacto no deberia coincidir con un texto mas largo"


@reto(7, "core/sistema.py: clase base Sistema")
def reto_7():
    from core.sistema import Sistema
    try:
        Sistema(None)
    except TypeError:
        pass
    else:
        raise AssertionError("Sistema no deberia poder crearse directamente (usa @abstractmethod)")

    class Prueba(Sistema):
        NOMBRE = "Prueba"

        def leer_config(self, datos):
            return datos

        def ejecutar(self):
            return "listo"

    archivos_txt = {"Config Prueba.txt": "Dato : 1\n",
                    "Credenciales Prueba.txt": "User : ana\nPassword : 123\nLink : https://x\n"}
    with carpeta_con(archivos_txt):
        sistema = Prueba(page=None)
        assert sistema.config == {"dato": "1"}, "no guardo la configuracion"
        assert sistema.credenciales.usuario == "ana", "no guardo las credenciales"
        ruta = sistema.guardar(DescargaFalsa(), "prueba")
        assert ruta.parent.name == "Prueba", f"guardar() deberia usar el NOMBRE del sistema: {ruta.parent}"


@reto(8, "sistemas/q10/config.py: ConfigQ10")
def reto_8():
    from sistemas.q10.config import ConfigQ10
    datos = {"rol": "Administrativo", "informes": "Inasistencias por curso, Consolidado de notas",
             "sede - jornada": "B2G - Única", "curso": "Todos", "fecha inicial": ""}
    config = ConfigQ10.desde_txt(datos)
    assert config.informes == ["Inasistencias por curso", "Consolidado de notas"]
    assert config.filtros == [("sede - jornada", ["B2G - Única"]), ("curso", ["Todos"])], \
        f"los filtros quedaron asi: {config.filtros}"
    assert ConfigQ10.desde_txt({"informes": "X"}).rol == "Administrativo", "sin rol deberia quedar Administrativo"
    try:
        ConfigQ10.desde_txt({"informes": "escribe_aqui_los_informes"})
    except ValueError:
        pass
    else:
        raise AssertionError("con la plantilla sin llenar deberia lanzar ValueError")


@reto(11, "sistemas/q10/paginas.py: FormularioInforme")
def reto_11():
    from sistemas.q10.paginas import FormularioInforme
    with pagina_de_prueba(HTML_FORMULARIO) as page:
        formulario = FormularioInforme(page)
        assert formulario.campo("Docente") is None, "campo() deberia devolver None si el filtro no existe"
        assert formulario.campo("sede - jornada") is not None, "campo() no encontro 'Sede - jornada'"
        assert formulario.llenar("Docente", "Pepito") is None, "llenar() deberia devolver None si no existe"
        assert formulario.llenar("sede - jornada", "b2g - única") == "B2G - Única", \
            "llenar() deberia devolver el texto exacto de la pagina"
        assert formulario.opciones("curso") == ["C1.1-7PM217 SDDE", "C1.2-5PM101 GT"], \
            "opciones() deberia esperar la cascada y quitar 'Seleccione'"
        try:
            formulario.llenar("curso", "Curso inventado")
        except ValueError as error:
            assert "C1.1-7PM217 SDDE" in str(error), "el error deberia mostrar las opciones disponibles"
        else:
            raise AssertionError("un valor que no existe deberia lanzar ValueError")
        formulario.llenar("curso", "C1.2-5PM101 GT")
        descarga = formulario.exportar()
        assert descarga.suggested_filename.endswith(".xlsx"), "exportar() deberia devolver la descarga"


@reto(12, "sistemas/q10/sistema.py: Q10.llenar_y_exportar")
def reto_12():
    from sistemas.q10.paginas import FormularioInforme
    from sistemas.q10.sistema import Q10
    with carpeta_con({}) as temporal, pagina_de_prueba(HTML_FORMULARIO) as page:
        q10 = object.__new__(Q10)  # sin leer .txt ni iniciar sesion
        q10.page = page
        filtros = [("sede - jornada", ["B2G - Única"]), ("docente", ["Pepito"]), ("curso", ["Todos"])]
        q10.llenar_y_exportar(FormularioInforme(page), "Inasistencias por curso", filtros)
        descargados = sorted(f.name for f in (temporal / "Descargas" / "Q10").glob("*"))
        assert len(descargados) == 2, f"con 'Todos' deberian salir 2 reportes, salieron {len(descargados)}"
        assert any("C1.1-7PM217" in n for n in descargados), f"falta el curso en el nombre: {descargados}"
        assert any("C1.2-5PM101" in n for n in descargados), f"falta el curso en el nombre: {descargados}"


@reto(13, "bot.py: clase Bot (menu y sistemas disponibles)")
def reto_13():
    from bot import Bot
    archivos_txt = {"Config Q10.txt": "Informes : Inasistencias por curso\n",
                    "Config Oxford.txt": "ID : X\n", "Config Inventado.txt": "A : 1\n"}
    with carpeta_con(archivos_txt):
        disponibles = Bot([]).disponibles()
        nombres = sorted(s.NOMBRE for s in disponibles)
        assert nombres == ["Oxford", "Q10"], f"disponibles() devolvio {nombres} (el Config inventado se ignora)"
        assert len(Bot(["Todos"]).elegir(disponibles)) == 2, "'Todos' deberia devolver los dos sistemas"
        elegido = Bot(["Q10"]).elegir(disponibles)
        assert len(elegido) == 1 and elegido[0].NOMBRE == "Q10", "el argumento Q10 deberia devolver solo Q10"
        try:
            Bot(["Nada"]).elegir(disponibles)
        except ValueError:
            pass
        else:
            raise AssertionError("un sistema que no existe deberia lanzar ValueError")


MANUALES = {9: "LoginQ10: se prueba iniciando sesion en Q10 de verdad",
            10: "BarraQ10 y PaginaInformes: se prueban entrando a Informes en Q10",
            14: "Oxford completo: se prueba corriendo el bot con Oxford",
            15: "El .exe: se prueba en una carpeta aparte con credenciales de plantilla"}


def main():
    print(f"\nComprobando: {CODIGO}\n" + "=" * 70)
    automaticos = {numero: (titulo, funcion) for numero, titulo, funcion in RETOS}
    hechos = 0
    for numero in sorted(automaticos | MANUALES):
        if numero in MANUALES:
            print(f"[ manual ] Reto {numero}: {MANUALES[numero]}")
            continue
        titulo, funcion = automaticos[numero]
        try:
            funcion()
        except (ImportError, AttributeError, FileNotFoundError) as error:
            print(f"[  falta ] Reto {numero}: {titulo}\n            -> {type(error).__name__}: {error}")
        except AssertionError as error:
            print(f"[  error ] Reto {numero}: {titulo}\n            -> {error}")
        except Exception as error:  # cualquier otro fallo del codigo
            print(f"[  error ] Reto {numero}: {titulo}\n            -> {type(error).__name__}: {error}")
        else:
            hechos += 1
            print(f"[   OK   ] Reto {numero}: {titulo}")
    print("=" * 70)
    print(f"Retos automaticos superados: {hechos} de {len(automaticos)}")
    if hechos == len(automaticos):
        print("Todos los retos automaticos estan listos. Faltan los manuales (9, 10, 14 y 15).")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"El comprobador fallo: {type(error).__name__}: {error}")
    input("\nPresiona Enter para cerrar...")
