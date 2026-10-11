"""Bot de descargas v5: igual que la v3, pero todo se configura en la planilla 'Bot Descargas.xlsx'.

Doble clic: muestra el menu con los sistemas que tienen 'Usar = Si' en la hoja Accesos.
'bot.py Q10' o 'bot.py Todos': ejecuta sin preguntar (sirve para programarlo).
Si la planilla no existe, la crea vacia y explica que llenar.
"""
import subprocess
import sys
from pathlib import Path

ES_EXE = getattr(sys, "frozen", False)
VENV = Path(__file__).resolve().parents[2] / ".venv"  # entorno virtual del proyecto (raiz: bots/q10 -> 2 arriba)

# Con doble clic se abre con el Python global, que no tiene Playwright: relanzar con el del proyecto
if not ES_EXE and (VENV / "Scripts" / "python.exe").exists() and Path(sys.prefix).resolve() != VENV.resolve():
    sys.exit(subprocess.call([str(VENV / "Scripts" / "python.exe"), __file__, *sys.argv[1:]]))

from playwright.sync_api import sync_playwright

from core import archivos, planilla
from core.errores import resumen
from core.navegador import abrir_navegador
from sistemas import SISTEMAS


class Bot:
    """Decide que sistemas correr (por argumento, si hay uno solo, o con el menu) y los ejecuta."""

    def __init__(self, argumentos):
        self.pedido = " ".join(argumentos).strip().lower()

    def disponibles(self):
        """Sistemas programados con 'Usar = Si' en la hoja Accesos."""
        if not archivos.PLANILLA.exists():
            planilla.crear(archivos.PLANILLA)
            print(f"No habia planilla, asi que la cree: {archivos.PLANILLA}\n"
                  "  Abrela, llena tu usuario y contraseña en la hoja 'Accesos', revisa la hoja de\n"
                  "  cada sistema, guarda, cierra el Excel y vuelve a abrir el bot.")
            raise FileNotFoundError(f"Primero llena '{archivos.PLANILLA.name}'")

        encontrados = []
        for clave, datos in archivos.planilla().accesos().items():
            if clave not in SISTEMAS:
                print(f"Aviso: el sistema '{clave}' de la hoja Accesos no esta programado; se ignora.")
            elif datos["usar"]:
                encontrados.append(SISTEMAS[clave])
        if not encontrados:
            raise ValueError(f"En la hoja Accesos de {archivos.PLANILLA.name} ningun sistema tiene "
                             f"Usar = Si. Sistemas programados: "
                             + ", ".join(s.NOMBRE for s in SISTEMAS.values()))
        return encontrados

    def elegir(self, disponibles):
        if self.pedido:
            if self.pedido == "todos":
                return disponibles
            elegidos = [s for s in disponibles if s.NOMBRE.lower() == self.pedido]
            if not elegidos:
                nombres = ", ".join(s.NOMBRE for s in disponibles)
                raise ValueError(f"'{self.pedido}' no tiene Usar = Si en la hoja Accesos. "
                                 f"Disponibles: {nombres}, Todos")
            return elegidos
        if len(disponibles) == 1:
            return disponibles

        print("\nQue sistema quieres ejecutar?")
        for numero, sistema in enumerate(disponibles, start=1):
            print(f"  {numero}. {sistema.NOMBRE}")
        print(f"  {len(disponibles) + 1}. Todos")
        while True:
            # Solo los digitos: descarta marcas invisibles (BOM) si la respuesta viene de otro programa
            respuesta = "".join(c for c in input("Escribe el numero y presiona Enter: ") if c.isdigit())
            if respuesta and 1 <= int(respuesta) <= len(disponibles) + 1:
                numero = int(respuesta)
                return disponibles if numero == len(disponibles) + 1 else [disponibles[numero - 1]]
            print("Opcion no valida.")

    def ejecutar(self, esperar_enter=True):
        elegidos = self.elegir(self.disponibles())

        with sync_playwright() as p:
            navegador = abrir_navegador(p)
            for sistema in elegidos:
                print(f"\n===== {sistema.NOMBRE} =====")
                # Cada sistema en su propia ventana: no comparte cookies ni sesion con los demas
                contexto = navegador.new_context(viewport={"width": 1400, "height": 900})
                page = contexto.new_page()
                page.set_default_timeout(30_000)
                try:
                    sistema(page).ejecutar()
                    print(f"{sistema.NOMBRE}: terminado.")
                except Exception as error:
                    print(f"FALLO en {sistema.NOMBRE}: {resumen(error)}")

                for numero, pestana in enumerate(contexto.pages, start=1):
                    ruta = archivos.captura(pestana, f"resultado_{sistema.NOMBRE}_{numero}.png")
                    print(f"Pestana {numero}: {pestana.url}  -> captura en {ruta.name}")

            if esperar_enter:
                input("\nPresiona Enter para cerrar el navegador...")
            navegador.close()


if __name__ == "__main__":
    try:
        Bot(sys.argv[1:]).ejecutar()
    except Exception as error:
        # Sin esto la consola se cierra sola y no se alcanza a leer el error
        print(f"FALLO: {resumen(error)}")
        input("Presiona Enter para cerrar...")
