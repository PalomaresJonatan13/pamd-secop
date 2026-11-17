"""Toma las capturas del dashboard para el informe y la presentación (T4.7), con Microsoft Edge sin ventana.

Levanta el dashboard, abre Edge en modo headless, carga cada dirección de CAPTURAS (los filtros van en la dirección, ver app.py),
espera a que los gráficos estén dibujados y guarda una captura PNG de la zona pedida a 1400 px de ancho. Controla el navegador
con su protocolo de depuración usando `websockets`, que ya instala Streamlit: no hay que instalar nada más. Solo Windows con Edge.

Desde la raíz del repositorio (con el entorno del dashboard):
    .venv\\Scripts\\python scripts\\capturar_dashboard.py [carpeta_de_salida]
La carpeta por defecto es report/evidencias. Los comentarios al pie de cada captura están en report/evidencias/t4.7_capturas_comentadas.md.
"""
import asyncio
import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from websockets.asyncio.client import connect

RAIZ = Path(__file__).resolve().parent.parent
PUERTO_APP, PUERTO_EDGE = 8766, 9333
ANCHO, ALTO = 1400, 6500  # alto de sobra: la página cabe entera y no hay que desplazarse
EDGE = next((p for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe") if Path(p).exists()), None)

CABECERA, TIEMPO, ACTORES, GEOGRAFIA, CONCENTRACION, TODO = "cabecera", "tiempo", "actores", "geografia", "concentracion", "todo"

# (archivo, filtros de la dirección, zona, gráficos que deben estar dibujados)
CAPTURAS = [
    ("t4.7_cabecera_sin_filtros.png", [], CABECERA, 1),
    ("t4.7_modulo_tiempo.png", [], TIEMPO, 3),
    ("t4.7_modulo_rankings.png", [], ACTORES, 3),
    ("t4.7_modulo_geografia.png", [], GEOGRAFIA, 3),
    ("t4.7_modulo_concentracion.png", [], CONCENTRACION, 3),
    ("t4.7_filtro_antioquia_2020_2023.png", [("departamento", "Antioquia"), ("desde", "2020-01"), ("hasta", "2023-12")], TODO, 3),
    ("t4.7_filtro_una_entidad.png", [("entidad", "NIT:899999034"), ("desde", "2019-01"), ("hasta", "2025-12")], TODO, 2),  # con una sola entidad la curva de concentración no se dibuja
    ("t4.7_filtro_sin_resultados.png", [("departamento", "SIN DEPARTAMENTO"), ("desde", "2015-06"), ("hasta", "2015-07")], CABECERA, 0),
]


class Edge:
    """Conexión mínima al protocolo de depuración de Edge (CDP) por websocket."""

    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def llamar(self, metodo, **parametros):
        self.n += 1
        await self.ws.send(json.dumps({"id": self.n, "method": metodo, "params": parametros}))
        while True:
            respuesta = json.loads(await self.ws.recv())
            if respuesta.get("id") == self.n:
                if "error" in respuesta:
                    raise RuntimeError(f"{metodo}: {respuesta['error']}")
                return respuesta["result"]

    async def evaluar(self, js):
        resultado = await self.llamar("Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=True)
        return resultado["result"].get("value")


# Posición (en píxeles de la página) de los títulos que delimitan cada zona
JS_POSICIONES = """
(() => {
  const principal = document.querySelector('[data-testid="stMainBlockContainer"]');
  const rect = e => e.getBoundingClientRect();
  const buscar = (selector, texto) => [...document.querySelectorAll(selector)].filter(e => e.textContent.trim().startsWith(texto)).sort((a, b) => a.textContent.length - b.textContent.length)[0];
  const arriba = e => e ? Math.round(rect(e).top + window.scrollY) : null;
  const p = rect(principal);
  const ultimo = rect([...principal.querySelectorAll('[data-testid="stElementContainer"]')].pop());
  return {
    izquierda: Math.round(p.left), ancho: Math.round(p.width), fin: Math.round(ultimo.bottom + window.scrollY),  // fin del último elemento, sin el relleno de la página
    tiempo: arriba(buscar('h3', 'Evolución en el tiempo')), actores: arriba(buscar('h3', 'Principales actores')),
    geografia: arriba(buscar('h3', 'Dónde se concentra el dinero')),
    concentracion: arriba(buscar('p, div', 'Concentración del valor en las entidades')),
  };
})()
"""
JS_LISTO = """
(() => {
  const terminado = document.querySelector('[data-testid="stMetric"], [data-testid="stAlert"]') && !document.querySelector('[data-testid="stStatusWidget"]');
  return terminado ? document.querySelectorAll('.vega-embed canvas, .vega-embed svg.marks, .vega-embed svg').length : -1;
})()
"""


def zona(nombre, pos):
    """(x, y, ancho, alto) de la captura. La cabecera incluye la barra lateral (filtros); los módulos solo el contenido."""
    if nombre == TODO:
        return 0, 0, ANCHO, pos["fin"] + 24
    if nombre == CABECERA:
        return 0, 0, ANCHO, (pos["tiempo"] or pos["fin"]) - 8
    inicio = {TIEMPO: pos["tiempo"], ACTORES: pos["actores"], GEOGRAFIA: pos["geografia"], CONCENTRACION: pos["concentracion"]}[nombre]
    fin = {TIEMPO: pos["actores"], ACTORES: pos["geografia"], GEOGRAFIA: pos["concentracion"], CONCENTRACION: pos["fin"] + 16}[nombre]
    return pos["izquierda"] - 16, inicio - 12, pos["ancho"] + 32, fin - inicio + 8


async def capturar(carpeta: Path):
    app_url = f"http://localhost:{PUERTO_APP}/"
    perfil = tempfile.mkdtemp(prefix="edge_capturas_")
    edge = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PUERTO_EDGE}", f"--user-data-dir={perfil}", "--remote-allow-origins=*",
                             "--hide-scrollbars", "--force-color-profile=srgb", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                objetivos = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PUERTO_EDGE}/json", timeout=2).read())
                pagina = next(o for o in objetivos if o["type"] == "page")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Edge no respondió")
        cdp = Edge(await connect(pagina["webSocketDebuggerUrl"], max_size=128 * 1024 * 1024))
        await cdp.llamar("Page.enable")
        await cdp.llamar("Emulation.setDeviceMetricsOverride", width=ANCHO, height=ALTO, deviceScaleFactor=1, mobile=False)
        await cdp.llamar("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])

        for archivo, filtros, region, graficos in CAPTURAS:
            await cdp.llamar("Page.navigate", url=app_url + ("?" + urlencode(filtros) if filtros else ""))
            for _ in range(180):  # hasta 90 s
                await asyncio.sleep(0.5)
                if await cdp.evaluar(JS_LISTO) >= graficos:
                    break
            else:
                raise RuntimeError(f"{archivo}: la página no terminó de dibujarse")
            await asyncio.sleep(4)  # tablas y etiquetas de los gráficos
            pos = await cdp.evaluar(JS_POSICIONES)
            x, y, ancho, alto = zona(region, pos)
            imagen = await cdp.llamar("Page.captureScreenshot", format="png", clip={"x": max(0, x), "y": max(0, y), "width": ancho, "height": alto, "scale": 1})
            (carpeta / archivo).write_bytes(base64.b64decode(imagen["data"]))
            print(f"{archivo}: {ancho}x{alto}")
    finally:
        edge.terminate()


def main():
    if EDGE is None:
        sys.exit("No se encontró Microsoft Edge en las rutas habituales.")
    carpeta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "report" / "evidencias"
    carpeta.mkdir(parents=True, exist_ok=True)
    servidor = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(RAIZ / "dashboard" / "app.py"), "--server.headless", "true",
                                 "--server.port", str(PUERTO_APP), "--browser.gatherUsageStats", "false"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=RAIZ)
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(f"http://localhost:{PUERTO_APP}/_stcore/health", timeout=2).read() == b"ok":
                    break
            except Exception:
                time.sleep(0.5)
        else:
            sys.exit("El dashboard no arrancó")
        asyncio.run(capturar(carpeta))
    finally:
        servidor.terminate()


if __name__ == "__main__":
    main()
