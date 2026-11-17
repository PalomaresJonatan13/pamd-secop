"""Comprueba los rankings del dashboard (T4.5) contra los tops que Spark calculó directamente sobre gold.

Requiere dashboard/verificacion/rankings_spark.json (lo escribe scripts/consultas_spark_rankings.py dentro del contenedor)
y el entorno del dashboard (ver dashboard/README.md). Desde la raíz del repositorio:
    .venv\\Scripts\\python scripts\\comprobar_rankings.py

Para cada combinación de filtros comprueba, con comparación exacta de identificador, contratos, atípicos y pesos:
  1. que calcular_ranking() sobre las tablas de consumo da el mismo top 10 que Spark, por valor y por número de contratos,
     para entidades y para contratistas;
  2. que el dashboard real (con la prueba de Streamlit, moviendo los filtros y el orden) muestra esos mismos identificadores
     en el mismo orden;
y que con otro N la tabla muestra los N primeros. Termina con error si algo no coincide.
"""
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DASHBOARD = RAIZ / "dashboard"
sys.path.insert(0, str(DASHBOARD))

from consultas import etiquetas_entidades, aplicar_filtros, calcular_ranking  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

REFERENCIA = json.loads((DASHBOARD / "verificacion" / "rankings_spark.json").read_text(encoding="utf-8"))
serie = pd.read_parquet(DASHBOARD / "data" / "serie_mensual.parquet")
contratistas = pd.read_parquet(DASHBOARD / "data" / "contratistas_mensual.parquet")
RANKINGS = {"entidades": ("id_entidad", serie), "contratistas": ("id_contratista", contratistas)}
ETIQUETA_ORDEN = {"valor_total": "Valor", "contratos": "Contratos"}  # texto de cada opción de «Ordenar por»
N = REFERENCIA["n"]
ETIQUETA = etiquetas_entidades(pd.read_parquet(DASHBOARD / "data" / "entidades.parquet"))  # texto de cada entidad en el dashboard
errores = []


def revisar(condicion: bool, mensaje: str) -> bool:
    if not condicion:
        errores.append(mensaje)
    return condicion


def abrir_dashboard(caso: dict) -> AppTest:
    app = AppTest.from_file(str(DASHBOARD / "app.py"), default_timeout=120).run()
    if caso["departamentos"]:
        app.sidebar.multiselect(key="departamento").set_value(caso["departamentos"]).run()
    if caso["entidades"]:
        app.sidebar.multiselect(key="entidad").set_value([ETIQUETA[i] for i in caso["entidades"]]).run()
    app.sidebar.select_slider(key="meses").set_value((caso["desde"], caso["hasta"])).run()
    return app


def identificadores_mostrados(app: AppTest) -> dict:
    """Columna 'Identificación' de las dos tablas de ranking de la pantalla (entidades primero)."""
    tablas = [d.value for d in app.dataframe if "Identificación" in d.value.columns]
    return {"entidades": list(tablas[0]["Identificación"]), "contratistas": list(tablas[1]["Identificación"])}


filas = []
for caso in REFERENCIA["casos"]:
    resumen = {"combinación": caso["nombre"]}
    filtro = (caso["departamentos"], caso["entidades"], caso["desde"], caso["hasta"])

    # 1) Funciones de consulta frente a Spark (exacto)
    ok_totales = True
    esperado_total = caso["totales"]
    filtrada = aplicar_filtros(serie, *filtro)
    ok_totales &= revisar(int(filtrada["contratos"].sum()) == esperado_total["contratos"], f"{caso['nombre']}: contratos totales")
    ok_totales &= revisar(int(filtrada["valor_total"].sum()) == esperado_total["valor_total"], f"{caso['nombre']}: valor total")
    resumen["totales"] = "igual" if ok_totales else "DIFERENTE"

    iguales = 0
    for nombre, (clave, tabla) in RANKINGS.items():
        datos = aplicar_filtros(tabla, *filtro)
        for orden in ("valor_total", "contratos"):
            esperado = caso["rankings"][f"{nombre}_por_{orden}"]
            calculado = calcular_ranking(datos, clave, orden, N)
            obtenido = [
                {"id": r[clave], "contratos": int(r["contratos"]), "contratos_atipicos": int(r["contratos_atipicos"]), "valor_total": int(r["valor_total"])}
                for _, r in calculado.iterrows()
            ]
            iguales += revisar(obtenido == esperado, f"{caso['nombre']}: top {N} de {nombre} por {orden}")
    resumen["tops (de 4)"] = f"{iguales} iguales"

    # 2) El dashboard real muestra los mismos identificadores, en el mismo orden
    app = abrir_dashboard(caso)
    app.number_input(key="n").set_value(N).run()
    en_pantalla = 0
    for orden in ("valor_total", "contratos"):
        app.radio(key="orden").set_value(ETIQUETA_ORDEN[orden]).run()
        mostrados = identificadores_mostrados(app)
        for nombre in RANKINGS:
            esperado_ids = [f["id"] for f in caso["rankings"][f"{nombre}_por_{orden}"]]
            en_pantalla += revisar(mostrados[nombre] == esperado_ids, f"{caso['nombre']}: pantalla, {nombre} por {orden}")
    resumen["pantalla (de 4)"] = f"{en_pantalla} iguales"
    filas.append(resumen)

# 3) Otro N: la tabla muestra los N primeros (los de Spark son 10; con N=3 son su prefijo; con N=50 salen 50 filas o todas las que haya)
primero = REFERENCIA["casos"][0]
app = abrir_dashboard(primero)
app.number_input(key="n").set_value(3).run()
revisar(identificadores_mostrados(app)["entidades"] == [f["id"] for f in primero["rankings"]["entidades_por_valor_total"][:3]], "N=3 entidades")
app.number_input(key="n").set_value(50).run()
mostrados50 = identificadores_mostrados(app)
revisar(len(mostrados50["entidades"]) == 50 and len(mostrados50["contratistas"]) == 50, "N=50: número de filas")
revisar(mostrados50["entidades"][:N] == [f["id"] for f in primero["rankings"]["entidades_por_valor_total"]], "N=50: los 10 primeros no cambian")

print(pd.DataFrame(filas).to_string(index=False))
print(f"\nReferencia de Spark generada el {REFERENCIA['generado_utc']} UTC sobre gold; top {N}; {len(REFERENCIA['casos'])} combinaciones de filtros.")
if errores:
    print("\nNO COINCIDE:\n  " + "\n  ".join(errores))
    sys.exit(1)
print("Todos los rankings coinciden con Spark (identificador, contratos, atípicos y pesos exactos) y con lo que muestra el dashboard.")
