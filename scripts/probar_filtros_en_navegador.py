"""Prueba los filtros y controles del dashboard en un navegador de verdad (Microsoft Edge sin ventana).

La prueba de Streamlit (AppTest) simula los controles y no ve lo que muestra el navegador. Por eso no detectó que «Quitar filtros»
recalculaba los datos pero dejaba los filtros anteriores a la vista. Esta prueba abre el dashboard, hace clic y escribe como un
usuario, y lee lo que hay en pantalla (etiquetas de los filtros, posición del rango, tarjetas, títulos) y la dirección.

Desde la raíz del repositorio (con el entorno del dashboard y Edge instalado):
    .venv\\Scripts\\python scripts\\probar_filtros_en_navegador.py
Termina con error si algún caso falla. Solo Windows con Edge.
"""
import asyncio
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from websockets.asyncio.client import connect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capturar_dashboard import EDGE, Edge  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PUERTO_APP, PUERTO_EDGE = 8768, 9334
URL = f"http://localhost:{PUERTO_APP}/"
SERIE = pd.read_parquet(RAIZ / "dashboard" / "data" / "serie_mensual.parquet")
TOTAL = int(SERIE["contratos"].sum())
BOGOTA = "Distrito Capital de Bogotá"
ENTIDAD_BOGOTA = "COLOMBIA COMPRA EFICIENTE (900514813)"  # solo tiene contratos en Bogotá; en la dirección va su texto visible

JS_ESTADO = """
(() => {
  const barra = document.querySelector('[data-testid="stSidebar"]');
  const textos = (raiz, selector) => [...raiz.querySelectorAll(selector)].map(e => e.textContent.trim());
  const selecciones = [...barra.querySelectorAll('[data-testid="stMultiSelect"]')].map(s => [...s.querySelectorAll('[data-tag] span[title]')].map(e => e.getAttribute('title')));
  return {
    departamentos: selecciones[0] || [], entidades: selecciones[1] || [],
    rango: textos(barra, '[data-testid="stSliderThumbValue"], [data-testid="stThumbValue"]'),
    tarjetas: textos(document, '[data-testid="stMetricValue"]'),
    titulos: textos(document, 'p, strong').filter(t => t.startsWith('Top')),
    aviso: textos(document, '[data-testid="stAlert"]').join(' | '),
    error: document.querySelectorAll('[data-testid="stException"]').length,
    orden: [...document.querySelectorAll('[data-testid="stRadio"] label')].filter(l => l.querySelector('input')?.checked).map(l => l.textContent.trim()),
    ocupado: !!document.querySelector('[data-testid="stStatusWidget"]'),
    busqueda: location.search,
  };
})()
"""


class Navegador:
    def __init__(self, cdp: Edge):
        self.cdp = cdp

    async def estado(self):
        return await self.cdp.evaluar(JS_ESTADO)

    async def abrir(self, busqueda: str = ""):
        await self.cdp.llamar("Page.navigate", url=URL + busqueda)
        await self.esperar(lambda e: e["tarjetas"] or e["aviso"], "la página termine de cargar")

    async def esperar(self, condicion, descripcion: str, segundos: int = 60):
        """Espera a que el estado de la pantalla cumpla la condición, y a que Streamlit termine de recalcular."""
        for _ in range(segundos * 4):
            await asyncio.sleep(0.25)
            try:
                estado = await self.estado()
            except Exception:
                continue
            if estado and not estado["ocupado"] and condicion(estado):  # sin estado = la página aún no tiene barra lateral
                await asyncio.sleep(0.5)
                return await self.estado()
        raise AssertionError(f"Se esperaba que {descripcion}, pero la pantalla muestra: {json.dumps(await self.estado(), ensure_ascii=False)}")

    async def clic_boton(self, texto: str):
        await self.cdp.evaluar(f"[...document.querySelectorAll('button')].find(b => b.textContent.trim() === {json.dumps(texto)}).click()")

    async def clic_etiqueta(self, texto: str):
        await self.cdp.evaluar(f"[...document.querySelectorAll('[data-testid=\"stRadio\"] label')].find(l => l.querySelector('input') && l.textContent.trim() === {json.dumps(texto)}).click()")

    async def tecla(self, tecla: str, codigo: int):
        for tipo in ("keyDown", "keyUp"):
            await self.cdp.llamar("Input.dispatchKeyEvent", type=tipo, key=tecla, code=tecla, windowsVirtualKeyCode=codigo)

    async def elegir_en_lista(self, posicion: int, texto: str):
        """Escribe en la lista desplegable de la barra lateral (0 = departamento, 1 = entidad) y elige la primera opción."""
        await self.cdp.evaluar(f"document.querySelectorAll('[data-testid=\"stSidebar\"] [data-testid=\"stMultiSelect\"] input')[{posicion}].focus()")
        await self.cdp.llamar("Input.insertText", text=texto)
        await asyncio.sleep(1)
        await self.tecla("Enter", 13)
        await asyncio.sleep(0.5)
        await self.tecla("Escape", 27)

    async def quitar_etiqueta(self, posicion: int, texto: str):
        """Hace clic en la «x» de una etiqueta ya elegida de la lista `posicion`."""
        await self.cdp.evaluar(
            f"[...document.querySelectorAll('[data-testid=\"stSidebar\"] [data-testid=\"stMultiSelect\"]')][{posicion}]"
            f".querySelector('button[aria-label=' + {json.dumps('"Remove ' + texto + '"')} + ']').click()"
        )

    async def escribir_n(self, valor: int):
        await self.cdp.evaluar("(() => { const c = document.querySelector('[data-testid=\"stNumberInputField\"]'); c.focus(); c.select(); })()")
        await self.cdp.llamar("Input.insertText", text=str(valor))
        await self.tecla("Enter", 13)


resultados = []


def caso(nombre: str, ok: bool, detalle: str = ""):
    resultados.append((nombre, ok, detalle))
    print(f"{'OK     ' if ok else 'FALLA  '}{nombre}" + (f"  ->  {detalle}" if detalle and not ok else ""))


async def probar(nav: Navegador):
    amazonas = int(SERIE.loc[SERIE["departamento"] == "Amazonas", "contratos"].sum())
    miles = lambda n: f"{n:,}".replace(",", ".")

    # 1. Abrir con filtros en la dirección
    await nav.abrir("?departamento=Antioquia&meses=2020-01&meses=2023-12&orden=Contratos&n=5")
    e = await nav.estado()
    caso("1. Los filtros de la dirección se ven en la barra lateral y filtran los datos",
         e["departamentos"] == ["Antioquia"] and e["rango"][:2] == ["2020-01", "2023-12"] and e["tarjetas"][0] == "27.728"
         and e["orden"] == ["Contratos"] and any("Top 5" in t for t in e["titulos"]), json.dumps(e, ensure_ascii=False))

    # 2. Quitar filtros: pantalla, datos y dirección cambian juntos
    await nav.clic_boton("Quitar filtros")
    e = await nav.esperar(lambda e: e["tarjetas"] and e["tarjetas"][0] == miles(TOTAL), "las tarjetas vuelvan al total")
    caso("2. «Quitar filtros» deja los filtros abiertos en la pantalla, no solo en los datos",
         e["departamentos"] == [] and e["entidades"] == [] and e["rango"][:2] == ["2015-06", "2026-09"], json.dumps(e, ensure_ascii=False))
    caso("3. «Quitar filtros» limpia los filtros de la dirección y conserva N y el orden",
         "departamento" not in e["busqueda"] and "meses" not in e["busqueda"] and "orden=Contratos" in e["busqueda"] and "n=5" in e["busqueda"], e["busqueda"])

    # 4. Elegir un departamento con el teclado
    await nav.abrir("")
    await nav.elegir_en_lista(0, "Amazon")
    e = await nav.esperar(lambda e: e["departamentos"] == ["Amazonas"], "se elija Amazonas")
    caso("4. Elegir un departamento filtra los datos y actualiza la dirección",
         e["tarjetas"][0] == miles(amazonas) and "departamento=Amazonas" in e["busqueda"], f"{e['tarjetas'][0]} frente a {miles(amazonas)}; {e['busqueda']}")

    # 5. Recargar la página conserva los filtros (la dirección los guarda)
    await nav.cdp.llamar("Page.reload")
    e = await nav.esperar(lambda e: e["tarjetas"], "la página recargue")
    caso("5. Al recargar la página se conservan los filtros", e["departamentos"] == ["Amazonas"] and e["tarjetas"][0] == miles(amazonas), json.dumps(e, ensure_ascii=False))

    # 6. Quitar filtros desde una combinación elegida con el teclado
    await nav.clic_boton("Quitar filtros")
    e = await nav.esperar(lambda e: e["tarjetas"] and e["tarjetas"][0] == miles(TOTAL), "las tarjetas vuelvan al total")
    caso("6. «Quitar filtros» también funciona con filtros elegidos en la pantalla", e["departamentos"] == [] and e["busqueda"] in ("", "?"), json.dumps(e, ensure_ascii=False))

    # 7. Cambiar de departamento quita las entidades que ya no corresponden
    await nav.abrir(f"?departamento={quote(BOGOTA)}&departamento=Amazonas&entidad={quote(ENTIDAD_BOGOTA)}")
    e = await nav.estado()
    caso("7a. Con dos departamentos y una entidad de Bogotá, la entidad se ve elegida", len(e["departamentos"]) == 2 and len(e["entidades"]) == 1, json.dumps(e, ensure_ascii=False))
    await nav.quitar_etiqueta(0, BOGOTA)
    e = await nav.esperar(lambda e: e["departamentos"] == ["Amazonas"], "se quite Bogotá")
    caso("7b. Al quitar Bogotá, la entidad que solo tiene contratos allí desaparece de la selección y de la dirección",
         e["entidades"] == [] and "entidad=" not in e["busqueda"] and e["tarjetas"][0] == miles(int(SERIE.loc[SERIE["departamento"] == "Amazonas", "contratos"].sum())),
         json.dumps(e, ensure_ascii=False))

    # 8. Orden y número de filas de los rankings
    await nav.abrir("")
    await nav.clic_etiqueta("Contratos")
    e = await nav.esperar(lambda e: e["orden"] == ["Contratos"], "el orden pase a Contratos")
    caso("8a. Cambiar el orden actualiza la dirección", "orden=Contratos" in e["busqueda"], e["busqueda"])
    await nav.clic_etiqueta("Valor")
    e = await nav.esperar(lambda e: e["orden"] == ["Valor"], "el orden vuelva a Valor")
    caso("8b. Volver al orden por defecto lo quita de la dirección", "orden" not in e["busqueda"], e["busqueda"])
    await nav.escribir_n(7)
    e = await nav.esperar(lambda e: any("Top 7" in t for t in e["titulos"]), "los rankings muestren 7")
    caso("8c. Cambiar N actualiza los títulos y la dirección", "n=7" in e["busqueda"], e["busqueda"])

    # 9. Valores inválidos en la dirección se ignoran, sin errores
    await nav.abrir("?departamento=Atlantis&meses=2030-01&n=99&orden=x&entidad=NIT:0")
    e = await nav.estado()
    caso("9. Valores inválidos en la dirección se ignoran y la página abre sin errores ni filtros",
         e["error"] == 0 and e["departamentos"] == [] and e["entidades"] == [] and e["rango"][:2] == ["2015-06", "2026-09"] and e["tarjetas"][0] == miles(TOTAL)
         and any("Top 10" in t for t in e["titulos"]) and e["orden"] == ["Valor"], json.dumps(e, ensure_ascii=False))

    # 10. Combinación sin resultados y salida con «Quitar filtros»
    await nav.abrir(f"?departamento={quote('SIN DEPARTAMENTO')}&meses=2015-06&meses=2015-07")
    e = await nav.estado()
    caso("10a. Una combinación sin contratos muestra un aviso y no un error", "No hay contratos" in e["aviso"] and e["error"] == 0, json.dumps(e, ensure_ascii=False))
    await nav.clic_boton("Quitar filtros")
    e = await nav.esperar(lambda e: e["tarjetas"] and e["tarjetas"][0] == miles(TOTAL), "la página salga del aviso")
    caso("10b. «Quitar filtros» saca de la combinación sin resultados", e["aviso"] == "" and e["departamentos"] == [], json.dumps(e, ensure_ascii=False))


async def main_async():
    perfil = tempfile.mkdtemp(prefix="edge_pruebas_")
    edge = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PUERTO_EDGE}", f"--user-data-dir={perfil}", "--remote-allow-origins=*", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                pagina = next(o for o in json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PUERTO_EDGE}/json", timeout=2).read()) if o["type"] == "page")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Edge no respondió")
        cdp = Edge(await connect(pagina["webSocketDebuggerUrl"], max_size=64 * 1024 * 1024))
        await cdp.llamar("Page.enable")
        await cdp.llamar("Emulation.setDeviceMetricsOverride", width=1400, height=1600, deviceScaleFactor=1, mobile=False)
        await probar(Navegador(cdp))
    finally:
        edge.terminate()


def main():
    if EDGE is None:
        sys.exit("No se encontró Microsoft Edge en las rutas habituales.")
    registro = Path(tempfile.mkdtemp(prefix="servidor_pruebas_")) / "servidor.log"
    servidor = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(RAIZ / "dashboard" / "app.py"), "--server.headless", "true", "--server.port", str(PUERTO_APP),
                                 "--browser.gatherUsageStats", "false"], stdout=registro.open("w"), stderr=subprocess.STDOUT, cwd=RAIZ)
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(f"http://localhost:{PUERTO_APP}/_stcore/health", timeout=2).read() == b"ok":
                    break
            except Exception:
                time.sleep(0.5)
        else:
            sys.exit("El dashboard no arrancó")
        try:
            asyncio.run(main_async())
        except AssertionError as error:
            caso("(la prueba se detuvo)", False, str(error))
    finally:
        servidor.terminate()
    lineas = registro.read_text(encoding="utf-8", errors="replace").splitlines()
    # El ruido de asyncio en Windows al cerrar el navegador de golpe (ConnectionResetError) no es del dashboard
    avisos = [l for i, l in enumerate(lineas) if ("Traceback" in l and not any("ConnectionResetError" in x for x in lineas[i:i + 10])) or "Warning" in l or "WARNING" in l]
    caso("11. La consola del servidor no muestra avisos ni errores", not avisos, "; ".join(avisos[:3]))
    fallos = [r for r in resultados if not r[1]]
    print(f"\n{len(resultados) - len(fallos)} de {len(resultados)} comprobaciones correctas.")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
