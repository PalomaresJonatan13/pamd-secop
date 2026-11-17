"""Comprueba las tarjetas y el gráfico mensual del dashboard (T4.3, T4.4 y T4.7) contra las cifras que Spark calculó sobre gold.

Requiere dashboard/verificacion/cifras_spark.json (lo escribe scripts/consultas_spark_cifras.py dentro del contenedor) y el entorno
del dashboard (ver dashboard/README.md). Desde la raíz del repositorio:
    .venv\\Scripts\\python scripts\\comprobar_cifras.py

Para cada combinación de filtros comprueba, con comparación exacta:
  1. que las tablas de consumo, filtradas con aplicar_filtros(), dan los mismos totales que Spark (contratos, atípicos, valor y
     valor de atípicos en pesos, entidades y contratistas distintos);
  2. que las cinco tarjetas del dashboard real (con la prueba de Streamlit, moviendo los filtros) muestran esas cifras;
  3. que cada punto mensual que dibuja el gráfico es igual al mes de Spark (y que los meses sin contratos están en cero).
Termina con error si algo no coincide.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa

RAIZ = Path(__file__).resolve().parent.parent
DASHBOARD = RAIZ / "dashboard"
sys.path.insert(0, str(DASHBOARD))

from consultas import etiquetas_entidades, aplicar_filtros  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

REFERENCIA = json.loads((DASHBOARD / "verificacion" / "cifras_spark.json").read_text(encoding="utf-8"))
serie = pd.read_parquet(DASHBOARD / "data" / "serie_mensual.parquet")
contratistas = pd.read_parquet(DASHBOARD / "data" / "contratistas_mensual.parquet")
ETIQUETA = etiquetas_entidades(pd.read_parquet(DASHBOARD / "data" / "entidades.parquet"))  # texto de cada entidad en el dashboard
errores = []


def revisar(condicion: bool, mensaje: str) -> bool:
    if not condicion:
        errores.append(mensaje)
    return bool(condicion)


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def billones(pesos: int) -> str:
    """Igual que en app.py: billones con una decimal, coma decimal y punto de miles."""
    return f"{pesos / 1e12:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".") + " billones"


def abrir_dashboard(caso: dict) -> AppTest:
    app = AppTest.from_file(str(DASHBOARD / "app.py"), default_timeout=120).run()
    if caso["departamentos"]:
        app.sidebar.multiselect(key="departamento").set_value(caso["departamentos"]).run()
    if caso["entidades"]:
        app.sidebar.multiselect(key="entidad").set_value([ETIQUETA[i] for i in caso["entidades"]]).run()
    app.sidebar.select_slider(key="meses").set_value((caso["desde"], caso["hasta"])).run()
    return app


def puntos_mensuales(app: AppTest):
    """La tabla que dibuja el gráfico mensual (contiene 'valor_billones' y 'contexto'), decodificada de lo que recibe el navegador."""
    for grafico in app.get("vega_lite_chart"):
        for dataset in grafico.proto.datasets:
            tabla = pa.ipc.open_stream(dataset.data.data).read_all().to_pandas()
            if {"valor_billones", "contexto", "anio_mes"} <= set(tabla.columns) and len(tabla) > 0:
                yield tabla


filas = []
for caso in REFERENCIA["casos"]:
    nombre, esperado, mensual = caso["nombre"], caso["totales"], caso["mensual"]
    filtro = (caso["departamentos"], caso["entidades"], caso["desde"], caso["hasta"])

    # 1) Tablas de consumo frente a Spark
    s = aplicar_filtros(serie, *filtro)
    c = aplicar_filtros(contratistas, *filtro)
    obtenido = {
        "contratos": int(s["contratos"].sum()), "contratos_atipicos": int(s["contratos_atipicos"].sum()),
        "valor_total": int(s["valor_total"].sum()), "valor_atipicos": int(s["valor_atipicos"].sum()),
        "entidades": int(s["id_entidad"].nunique()), "contratistas": int(c["id_contratista"].nunique()),
    }
    ok_tablas = revisar(obtenido == esperado, f"{nombre}: totales de las tablas {obtenido} frente a Spark {esperado}")

    # 2) Tarjetas del dashboard
    app = abrir_dashboard(caso)
    tarjetas = {m.label: m.value for m in app.metric}
    pedidas = {
        "Contratos adjudicados": miles(esperado["contratos"]),
        "Valor adjudicado (sin atípicos)": billones(esperado["valor_total"]),
        "Contratos atípicos": miles(esperado["contratos_atipicos"]),
        "Entidades": miles(esperado["entidades"]),
        "Contratistas": miles(esperado["contratistas"]),
    }
    ok_tarjetas = all(revisar(tarjetas.get(k) == v, f"{nombre}: tarjeta «{k}»: {tarjetas.get(k)} frente a {v}") for k, v in pedidas.items())

    # 3) Puntos del gráfico mensual
    dibujado = next(puntos_mensuales(app), None)
    ok_meses = False
    if revisar(dibujado is not None, f"{nombre}: no hay gráfico mensual"):
        dibujado = dibujado.set_index("anio_mes")
        meses_esperados = pd.period_range(caso["desde"], caso["hasta"], freq="M").strftime("%Y-%m")
        ok_meses = revisar(list(dibujado.index) == list(meses_esperados), f"{nombre}: el eje mensual no es completo y ordenado")
        for mes in meses_esperados:
            real = mensual.get(mes, {"contratos": 0, "valor_total": 0})
            if mes in dibujado.index:
                ok_meses &= revisar((int(dibujado.loc[mes, "contratos"]), int(dibujado.loc[mes, "valor_total"])) == (real["contratos"], real["valor_total"]),
                                    f"{nombre}: punto {mes}")
        ok_meses &= revisar(set(mensual) <= set(dibujado.index), f"{nombre}: meses de Spark que no están en el gráfico")

    filas.append({
        "combinación": nombre, "contratos": miles(esperado["contratos"]), "valor (pesos)": miles(esperado["valor_total"]),
        "entidades": miles(esperado["entidades"]), "contratistas": miles(esperado["contratistas"]), "meses": len(dibujado) if dibujado is not None else 0,
        "tablas": "igual" if ok_tablas else "DIFERENTE", "tarjetas": "igual" if ok_tarjetas else "DIFERENTE", "puntos": "igual" if ok_meses else "DIFERENTE",
    })

print(pd.DataFrame(filas).to_string(index=False))
print(f"\nReferencia de Spark generada el {REFERENCIA['generado_utc']} UTC sobre gold; {len(REFERENCIA['casos'])} combinaciones de filtros.")
if errores:
    print("\nNO COINCIDE:\n  " + "\n  ".join(errores))
    sys.exit(1)
print("Tarjetas y puntos mensuales coinciden con Spark (contratos y pesos exactos).")
