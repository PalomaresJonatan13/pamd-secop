"""Periodos de interés que el gráfico temporal (T4.4) marca sobre la serie mensual.

Se consultaron el 16-nov-2026. Cada periodo trae el nombre, la fecha de inicio, la de fin (ambas incluidas) y de dónde sale.

1. Restricción a la contratación directa (Ley 996 de 2005, art. 33). "Durante los cuatro (4) meses anteriores a la elección
   presidencial y hasta la realización de la elección en la segunda vuelta, si fuere el caso, queda prohibida la contratación
   directa por parte de todos los entes del Estado", con excepciones (defensa y seguridad, crédito público, urgencia manifiesta...).
   Texto: https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=22029 (transcrito en un concepto del Consejo de
   Estado de 2006) y Circular 0006 de 2025 de la Agencia Nacional de Contratación Pública, que lo aplica como vigente.
   Fechas de las elecciones presidenciales (primera y segunda vuelta):
     - 2018: 27-may y 17-jun. Circular MinRelaciones 0002 de 2018 y MOE. El inicio, 27-ene, es cuatro meses antes.
     - 2022: 29-may y 19-jun (Resolución 4371 de 2021 de la Registraduría). Inicio de la restricción: 29-ene-2022.
     - 2026: 31-may y 21-jun (Resolución 2580 de 2025 de la Registraduría; Resolución 2837 de 2026 del CNE confirma la
       segunda vuelta). Inicio de la restricción: 31-ene-2026 (tabla de la Mesa de Observación Electoral).

2. Restricción a convenios interadministrativos (Ley 996 de 2005, art. 38, parágrafo): gobernadores, alcaldes, secretarios,
   gerentes y directores no pueden celebrar convenios interadministrativos para ejecutar recursos públicos "dentro de los cuatro
   (4) meses anteriores a las elecciones" a cualquier cargo de elección popular (Circular 0006 de 2025). Es una restricción más
   estrecha que la del art. 33, así que se marca con otro color. Va desde cuatro meses antes hasta el día de la elección:
     - Congreso: 11-mar-2018, 13-mar-2022 y 8-mar-2026 (Resolución 2581 de 2025 de la Registraduría). La restricción de 2026
       empezó el 8-nov-2025, como confirma un concepto de Colombia Compra Eficiente de dic-2025.
     - Territoriales (alcaldes y gobernadores): último domingo de octubre (Ley 163 de 1994): 25-oct-2015, 27-oct-2019 y
       29-oct-2023. Las de 2015 y 2019 se derivan de esa regla, no se confirmaron en una resolución.

3. Cierre de vigencia fiscal: el año fiscal va del 1 de enero al 31 de diciembre (Estatuto Orgánico del Presupuesto, Decreto 111
   de 1996, art. 14; no se abrió el texto en esta consulta). Se marca diciembre de cada año.

No se encontró ninguna ley posterior que modifique los artículos 33 y 38, y la Circular 0006 de 2025 los trata como vigentes,
pero no se consultó una fuente oficial de vigencia: conviene confirmarlo antes de citarlo en el informe.
Las elecciones territoriales de 2027 (31-oct-2027) quedan fuera del rango de los datos (hasta 2026-09).
"""
from datetime import date

ART33 = "Contratación directa prohibida (Ley 996 de 2005, art. 33)"
ART38 = "Convenios interadministrativos restringidos (art. 38)"
FISCAL = "Cierre de vigencia fiscal (diciembre)"
TIPOS = [ART33, ART38, FISCAL]

PERIODOS = [
    # nombre, tipo, inicio, fin
    ("Territoriales 2015", ART38, date(2015, 6, 25), date(2015, 10, 25)),
    ("Congreso 2018", ART38, date(2017, 11, 11), date(2018, 3, 11)),
    ("Presidencial 2018", ART33, date(2018, 1, 27), date(2018, 6, 17)),
    ("Territoriales 2019", ART38, date(2019, 6, 27), date(2019, 10, 27)),
    ("Congreso 2022", ART38, date(2021, 11, 13), date(2022, 3, 13)),
    ("Presidencial 2022", ART33, date(2022, 1, 29), date(2022, 6, 19)),
    ("Territoriales 2023", ART38, date(2023, 6, 29), date(2023, 10, 29)),
    ("Congreso 2026", ART38, date(2025, 11, 8), date(2026, 3, 8)),
    ("Presidencial 2026", ART33, date(2026, 1, 31), date(2026, 6, 21)),
]


def periodos_en(primer_mes: str, ultimo_mes: str, ley: bool = True, fiscal: bool = True) -> list[dict]:
    """Periodos que tocan el rango [primer_mes, ultimo_mes] ('AAAA-MM'), listos para el gráfico (fechas como datetime.date)."""
    desde = date(int(primer_mes[:4]), int(primer_mes[5:]), 1)
    hasta_anio, hasta_mes = int(ultimo_mes[:4]), int(ultimo_mes[5:])
    hasta = date(hasta_anio + (hasta_mes == 12), hasta_mes % 12 + 1, 1)  # primer día del mes siguiente (excluido)
    todos = []
    if ley:
        todos += [{"nombre": n, "tipo": t, "inicio": i, "fin": f} for n, t, i, f in PERIODOS]
    if fiscal:
        todos += [
            {"nombre": f"Cierre fiscal {a}", "tipo": FISCAL, "inicio": date(a, 12, 1), "fin": date(a, 12, 31)}
            for a in range(desde.year, hasta.year + 1)
        ]
    return [p for p in todos if p["inicio"] < hasta and p["fin"] >= desde]


def contexto_mes(anio_mes: str) -> str:
    """Texto con los periodos que tocan un mes ('AAAA-MM'); '(parte del mes)' si el periodo no lo cubre completo."""
    a, m = int(anio_mes[:4]), int(anio_mes[5:])
    primer_dia, ultimo_dia = date(a, m, 1), _ultimo_dia(a, m)
    notas = []
    for p in periodos_en(anio_mes, anio_mes):
        completo = p["inicio"] <= primer_dia and p["fin"] >= ultimo_dia
        notas.append(p["nombre"] + ("" if completo else " (parte del mes)"))
    return "; ".join(notas)


def _ultimo_dia(a: int, m: int) -> date:
    siguiente = date(a + (m == 12), m % 12 + 1, 1)
    return date.fromordinal(siguiente.toordinal() - 1)
