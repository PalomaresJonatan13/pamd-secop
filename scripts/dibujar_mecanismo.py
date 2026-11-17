"""Dibuja el diagrama del mecanismo de resiliencia e idempotencia (docs/mecanismo_resiliencia.svg, T3.5).

Uso, desde la raíz del repositorio:

    python scripts/dibujar_mecanismo.py

Si cambia una ruta o una cifra, se edita aquí y se vuelve a ejecutar. Para el PNG de la presentación (con Edge o
Chrome, que ya están instalados en Windows; cualquier conversor de SVG sirve):

    msedge --headless --screenshot=docs/mecanismo_resiliencia.png --window-size=1400,676 --force-device-scale-factor=2 docs/mecanismo_resiliencia.svg
"""
from pathlib import Path

from xml.sax.saxutils import escape as e

W, H = 1400, 676
SANS = "DejaVu Sans, Segoe UI, Arial, sans-serif"
MONO = "DejaVu Sans Mono, Consolas, Menlo, monospace"
ESTILO = {
    "entrada": ("#E8F0FB", "#3B6FB6", "#2A5290"),
    "spark": ("#EFE8FB", "#7A4FB5", "#5A3590"),
    "destino": ("#E4F4EC", "#2E8B6A", "#1F6B4F"),
    "control": ("#FFF3DC", "#C98A1B", "#8A5A00"),
    "nota": ("#F6F6F6", "#9A9A9A", "#444444"),
}
out = []
def add(s): out.append(s)

def texto(x, y, t, size=12, color="#1B1B1B", peso=400, fuente=SANS, anchor="start", extra=""):
    add(f'<text x="{x}" y="{y}" font-family="{fuente}" font-size="{size}" font-weight="{peso}" fill="{color}" text-anchor="{anchor}"{extra}>{e(t)}</text>')

def marco(x, y, w, h, tipo, badge):
    """Recuadro grande con una etiqueta arriba; dentro van las cajas."""
    _, stroke, dark = ESTILO[tipo]
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#FFFFFF" stroke="{stroke}" stroke-width="2"/>')
    texto(x + 14, y + 22, badge, 10.5, dark, 700, extra=' letter-spacing="0.8"')

def caja(x, y, w, h, tipo, titulo, lineas, mono_titulo=False):
    fill, stroke, dark = ESTILO[tipo]
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    texto(x + 12, y + 24, titulo, 12.5 if mono_titulo else 14, dark if mono_titulo else "#1B1B1B", 700, MONO if mono_titulo else SANS)
    for i, l in enumerate(lineas):
        texto(x + 12, y + 45 + 17 * i, l, 11.5, "#333")

def flecha(d, color="#444", doble=False):
    inicio = ' marker-start="url(#p)"' if doble else ""
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" marker-end="url(#p)"{inicio}/>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add('<defs><marker id="p" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#444"/></marker></defs>')
add(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')
texto(24, 36, "Resiliencia e idempotencia del flujo (Corte 3, Punto 3)", 22, peso=700)
texto(24, 60, "El resultado es el mismo aunque el flujo se detenga, se caiga mientras escribe o reciba dos veces los mismos lotes. Las rutas son carpetas del bucket rawdata de MinIO.", 13, "#555")

# --- Fila de arriba: entrada -> consulta -> destino ---
Y1, H1 = 88, 170
marco(24, Y1, 250, H1, "entrada", "ENTRADA")
caja(38, Y1 + 34, 222, 122, "entrada", "streaming/entrada/", ["un archivo Parquet por lote", "22 lotes, 2 de ellos tardíos", "530.192 contratos de gold"], mono_titulo=True)

marco(334, Y1, 560, H1, "spark", "CONSULTA EN SPARK (STRUCTURED STREAMING)")
caja(348, Y1 + 34, 258, 122, "spark", "1 · Deduplicación", ["clave del contrato (T1.1):", "id_del_proceso + id_adjudicacion", "descarta los contratos ya vistos"])
caja(622, Y1 + 34, 258, 122, "spark", "2 · Ventanas mensuales", ["mes × departamento, modo update", "marca de agua: 75 días", "salen solo las ventanas que cambian"])

marco(954, Y1, 422, H1, "destino", "DESTINO QUE REEMPLAZA · streaming/ventanas/")
caja(968, Y1 + 34, 190, 122, "destino", "cambios/batch_id=N", ["ventanas del micro-lote N", "se sobrescribe la carpeta", "del micro-lote"], mono_titulo=True)
caja(1172, Y1 + 34, 190, 122, "destino", "tabla/anio_mes=…", ["última versión de cada", "ventana; se sobrescribe", "la partición del mes"], mono_titulo=True)

flecha(f"M274,{Y1 + 95} H331")
flecha(f"M606,{Y1 + 95} H619")
flecha(f"M894,{Y1 + 95} H951")
flecha(f"M1158,{Y1 + 95} H1169")

# --- Fila del medio: checkpoint y orden de cada micro-lote ---
Y2, H2 = 306, 136
marco(334, Y2, 560, H2, "control", "CHECKPOINT · streaming/checkpoint/ventanas_sin_repetidos/")
for i, (nombre, l1, l2) in enumerate([
    ("sources", "archivos de la", "entrada ya leídos"),
    ("offsets", "qué se va a leer;", "se anota ANTES"),
    ("state", "claves ya vistas", "y acumulados"),
    ("commits", "lote terminado;", "se anota DESPUÉS"),
]):
    caja(348 + 134 * i, Y2 + 34, 126, 88, "control", nombre, [l1, l2], mono_titulo=True)
flecha(f"M614,{Y1 + H1 + 3} V{Y2 - 3}", doble=True)
texto(624, Y1 + H1 + 30, "lee al arrancar, escribe en cada micro-lote", 10.5, "#555", extra=' font-style="italic"')

marco(954, Y2, 422, H2, "nota", "ORDEN DE CADA MICRO-LOTE")
for i, l in enumerate([
    "1. Anotar en offsets qué archivos va a leer",
    "2. Calcular y guardar en el destino (cambios y tabla)",
    "3. Confirmar en commits",
]):
    texto(968, Y2 + 48 + 20 * i, l, 12.5, "#1B1B1B")
texto(968, Y2 + 116, "Si se cae entre 1 y 3, al reiniciar se repite el micro-lote N.", 12, "#8A5A00", 700)

# --- Fila de abajo: qué protege de cada fallo ---
Y3 = 478
add(f'<line x1="24" y1="{Y3 - 14}" x2="{W - 24}" y2="{Y3 - 14}" stroke="#DDD"/>')
texto(24, Y3 + 12, "Qué protege en cada caso (pruebas del notebook 06)", 15, peso=700)
CASOS = [
    ("control", "Parada y reinicio", ["Checkpoint: sigue en el lote", "siguiente y no relee ninguno."]),
    ("destino", "Caída mientras escribe", ["El micro-lote no queda confirmado,", "Spark lo repite y el destino", "reemplaza: nada se duplica."]),
    ("spark", "El mismo lote otra vez", ["Mismo nombre: no se lee (sources).", "Otro nombre: la deduplicación o la", "marca de agua lo descartan."]),
    ("destino", "El flujo completo otra vez", ["Mismo checkpoint: no lee nada.", "Checkpoint borrado: relee todo y", "el destino reemplaza cada ventana."]),
]
for i, (tipo, titulo, lineas) in enumerate(CASOS):
    caja(24 + 341 * i, Y3 + 28, 329, 104, tipo, titulo, lineas)
texto(24, Y3 + 160, "En los tres escenarios de fallo (T3.4) la tabla final tiene 3.735 ventanas y 529.326 contratos, igual que la ejecución sin interrupciones y que el cálculo por lotes.", 12.5, "#333")
texto(24, Y3 + 180, "Los 866 contratos restantes llegaron fuera de la tolerancia y quedan registrados aparte en streaming/tardios/. Cifras de la ejecución del 16-nov-2026.", 12, "#555")
add('</svg>')

destino = Path(__file__).resolve().parent.parent / "docs" / "mecanismo_resiliencia.svg"
destino.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"Escrito {destino}")
