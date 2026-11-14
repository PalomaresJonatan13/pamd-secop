"""Dibuja el diagrama de linaje de datos (docs/linaje_datos.svg).

Uso, desde la raíz del repositorio:

    python scripts/dibujar_linaje.py

Si cambia una ruta o una cifra, se edita aquí y se vuelve a ejecutar. Para el PNG de la presentación:

    rsvg-convert -w 3224 docs/linaje_datos.svg -o docs/linaje_datos.png
"""
from pathlib import Path

from xml.sax.saxutils import escape as e

W, H = 1612, 640
SANS = "DejaVu Sans, Segoe UI, Arial, sans-serif"
MONO = "DejaVu Sans Mono, Consolas, Menlo, monospace"
BW = 196
X = [24 + 228 * i for i in range(7)]
ESTILO = {
    "c1": ("#E8F0FB", "#3B6FB6", "#2A5290"),
    "c2": ("#E4F4EC", "#2E8B6A", "#1F6B4F"),
    "c3": ("#EFE8FB", "#7A4FB5", "#5A3590"),
    "pend": ("#F3F3F3", "#8A8A8A", "#5F5F5F"),
}
out = []
def add(s): out.append(s)

def box(x, y, h, tipo, badge, titulo, ruta=None, l3=None, l4=None, dashed=False):
    fill, stroke, dark = ESTILO[tipo]
    d = ' stroke-dasharray="7 5"' if dashed else ""
    add(f'<rect x="{x}" y="{y}" width="{BW}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"{d}/>')
    add(f'<text x="{x+12}" y="{y+19}" font-family="{SANS}" font-size="10" font-weight="700" letter-spacing="0.8" fill="{dark}">{e(badge)}</text>')
    add(f'<text x="{x+12}" y="{y+40}" font-family="{SANS}" font-size="15" font-weight="700" fill="#1B1B1B">{e(titulo)}</text>')
    yy = y + 60
    if ruta:
        add(f'<text x="{x+12}" y="{yy}" font-family="{MONO}" font-size="10" fill="{dark}">{e(ruta)}</text>'); yy += 19
    if l3:
        add(f'<text x="{x+12}" y="{yy}" font-family="{SANS}" font-size="11.5" font-weight="600" fill="#1B1B1B">{e(l3)}</text>'); yy += 17
    if l4:
        add(f'<text x="{x+12}" y="{yy}" font-family="{SANS}" font-size="11" fill="#444">{e(l4)}</text>')

def flecha(d, dashed=False, color="#444"):
    ds = ' stroke-dasharray="6 5"' if dashed else ""
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"{ds} marker-end="url(#p)"/>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add('<defs><marker id="p" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#444"/></marker></defs>')
add(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')
add(f'<text x="24" y="36" font-family="{SANS}" font-size="22" font-weight="700" fill="#1B1B1B">Linaje de datos del Observatorio de Contratación Pública (SECOP II)</text>')
add(f'<text x="24" y="60" font-family="{SANS}" font-size="13" fill="#555">Cada recuadro con ruta es una carpeta real del bucket rawdata de MinIO (s3a://rawdata/…). Cifras de la ejecución del 14-nov-2026.</text>')

Y0, H0 = 92, 84      # fila de arriba (Corte 2 y flujo en streaming)
YM, HM = 226, 112    # fila principal
YS, HS = 408, 88     # fila de descartes

# fila de arriba
box(X[2], Y0, H0, "c2", "CORTE 2 · REUTILIZADO", "Agregación y sesgo", None, "groupByKey vs reduceByKey", "notebook 02 · lee el bronze")
box(X[3], Y0, H0, "c2", "CORTE 2 · REUTILIZADO", "PageRank", None, "entidad → contratista", "notebook 03 · lee el bronze")
box(X[5], Y0, H0 + 12, "pend", "CORTE 3 · PENDIENTE", "Flujo con ventanas", None, "Puntos 2 y 3", "micro-lotes y checkpoint")

# fila principal
box(X[0], YM, HM, "c1", "CORTE 1", "CSV de SECOP II", "secop/", "descarga del 2-sep-2026", "se lee una sola vez")
box(X[1], YM, HM, "c1", "CORTE 1", "Staging", "staging/secop/con_calidad", "9.099.859 filas leídas", "con los motivos de rechazo")
box(X[2], YM, HM, "c1", "CORTE 1", "Bronze", "bronze/secop/contratos", "9.099.432 filas válidas", "y …/contratos_particionado")
box(X[3], YM, HM, "c3", "CORTE 3", "Silver", "silver/secop/contratos", "8.694.126 filas", "una por proceso + adjudicación")
box(X[4], YM, HM, "c3", "CORTE 3", "Gold", "gold/secop/adjudicaciones", "530.192 contratos", "adjudicados, sin duplicados")
box(X[5], YM, HM, "c3", "CORTE 3", "Tablas resumen", "procesado/adjudicaciones_por_", "entidad 4.050 · mes 136", "contratista 99.606 · depto. 34")
box(X[6], YM, HM, "pend", "CORTE 3 · PENDIENTE", "Dashboard", None, "Punto 4", "lee las tablas, sin Spark")

# fila de descartes
box(X[2], YS, HS, "c1", "CORTE 1", "Cuarentena", "cuarentena/secop", "427 filas rechazadas")
box(X[3], YS, HS, "c3", "CORTE 3", "Silver descartados", "silver/secop/descartados", "405.306 filas, con motivo")
box(X[4], YS, HS, "c3", "CORTE 3", "Gold excluidos", "gold/secop/excluidos", "17.226 filas, con motivo")

ym = YM + HM // 2 - 6
# flechas fila principal
for i in range(6):
    if i == 5:
        flecha(f"M{X[5]+BW},{ym} H{X[6]-3}")
    else:
        flecha(f"M{X[i]+BW},{ym} H{X[i+1]-3}")
# staging -> cuarentena (codo)
cx = X[1] + BW // 2
flecha(f"M{cx},{YM+HM} V{YS+HS//2} H{X[2]-3}")
# silver -> descartados, gold -> excluidos
flecha(f"M{X[3]+BW//2},{YM+HM} V{YS-3}")
flecha(f"M{X[4]+BW//2},{YM+HM} V{YS-3}")
# bronze -> Corte 2
flecha(f"M{X[2]+60},{YM} V{Y0+H0+3}", color="#2E8B6A")
flecha(f"M{X[2]+150},{YM} L{X[3]+40},{Y0+H0+3}", color="#2E8B6A")
# gold -> flujo (pendiente), flujo -> dashboard
flecha(f"M{X[4]+BW//2},{YM} V{Y0+H0//2+6} H{X[5]-3}", dashed=True, color="#8A8A8A")
flecha(f"M{X[5]+BW},{Y0+H0//2+6} H{X[6]+BW//2} V{YM-3}", dashed=True, color="#8A8A8A")

# etiquetas pequeñas sobre flechas
def lbl(x, y, t, color="#555", anchor="start"):
    add(f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="10.5" font-style="italic" fill="{color}" text-anchor="{anchor}">{e(t)}</text>')
lbl(cx + 8, YS + HS//2 - 8, "rechazadas")
lbl(X[2] + 66, YM - 22, "lee", "#1F6B4F")
lbl(X[2] + 166, YM - 26, "lee", "#1F6B4F")
lbl(X[3] + BW//2 + 8, YM + HM + 40, "duplicados", "#5A3590")
lbl(X[4] + BW//2 + 8, YM + HM + 40, "no cumplen reglas", "#5A3590")

# leyenda
ly = 538
add(f'<line x1="24" y1="{ly-24}" x2="{W-24}" y2="{ly-24}" stroke="#DDD"/>')
def sw(x, tipo, texto, dashed=False):
    fill, stroke, _ = ESTILO[tipo]
    d = ' stroke-dasharray="5 4"' if dashed else ""
    add(f'<rect x="{x}" y="{ly}" width="28" height="18" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="2"{d}/>')
    add(f'<text x="{x+38}" y="{ly+14}" font-family="{SANS}" font-size="12.5" fill="#333">{e(texto)}</text>')
sw(24, "c1", "Corte 1: almacenamiento en MinIO y bronze en Parquet")
sw(430, "c2", "Corte 2: técnicas reutilizadas (no escriben tablas)")
sw(800, "c3", "Corte 3: deduplicación, gold y tablas resumen")
sw(1160, "pend", "Pendiente", dashed=True)
add(f'<text x="24" y="{ly+48}" font-family="{SANS}" font-size="12" fill="#555">Gold y las tablas resumen se calculan con las marcas de valores atípicos de src/pamd/calidad.py: los atípicos se marcan y se separan del valor normal, pero ningún contrato se borra.</text>')
add(f'<text x="24" y="{ly+68}" font-family="{SANS}" font-size="12" fill="#555">El PageRank y la comparación groupByKey / reduceByKey del Corte 2 se calcularon sobre el bronze, que conserva los duplicados; las cifras del Corte 3 salen de gold, ya deduplicado.</text>')
add('</svg>')
destino = Path(__file__).resolve().parent.parent / "docs" / "linaje_datos.svg"
destino.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"Escrito {destino}")
