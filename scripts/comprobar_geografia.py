"""Comprueba el módulo geográfico y de concentración del dashboard (T4.6) contra las cifras que Spark calculó sobre gold.

Requiere dashboard/verificacion/geografia_spark.json (lo escribe scripts/consultas_spark_geografia.py dentro del contenedor)
y el entorno del dashboard (ver dashboard/README.md). Desde la raíz del repositorio:
    .venv\\Scripts\\python scripts\\comprobar_geografia.py

Para cada combinación de filtros comprueba, con comparación exacta en pesos y contratos:
  1. valor_por_departamento(): mismos departamentos y mismas cifras que Spark; su suma es igual al total filtrado; y si hay
     contratos sin departamento, aparecen como la fila 'SIN DEPARTAMENTO';
  2. concentracion_entidades(): mismo número de entidades, mismo total, mismo valor de las 10 primeras y las mismas entidades
     para el 50 % y el 80 % que la función de ventana de Spark;
  3. el dashboard real (con la prueba de Streamlit, moviendo los filtros): que el gráfico de barras dibuja esos departamentos,
     con 'Sin departamento' como categoría aparte, que las tarjetas muestran esos números y que la curva tiene una fila por entidad.
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

from consultas import etiquetas_entidades, aplicar_filtros, concentracion_entidades, valor_por_departamento  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

REFERENCIA = json.loads((DASHBOARD / "verificacion" / "geografia_spark.json").read_text(encoding="utf-8"))
serie = pd.read_parquet(DASHBOARD / "data" / "serie_mensual.parquet")
SIN_DEPARTAMENTO = "SIN DEPARTAMENTO"
ETIQUETA = etiquetas_entidades(pd.read_parquet(DASHBOARD / "data" / "entidades.parquet"))  # texto de cada entidad en el dashboard
errores = []


def revisar(condicion: bool, mensaje: str) -> bool:
    if not condicion:
        errores.append(mensaje)
    return bool(condicion)


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def abrir_dashboard(caso: dict) -> AppTest:
    app = AppTest.from_file(str(DASHBOARD / "app.py"), default_timeout=120).run()
    if caso["departamentos"]:
        app.sidebar.multiselect(key="departamento").set_value(caso["departamentos"]).run()
    if caso["entidades"]:
        app.sidebar.multiselect(key="entidad").set_value([ETIQUETA[i] for i in caso["entidades"]]).run()
    app.sidebar.select_slider(key="meses").set_value((caso["desde"], caso["hasta"])).run()
    return app


def datos_de_graficos(app: AppTest) -> list:
    """Las tablas (pandas) que dibujan los gráficos de la pantalla, decodificadas de lo que Streamlit envía al navegador."""
    tablas = []
    for grafico in app.get("vega_lite_chart"):
        for dataset in grafico.proto.datasets:
            tablas.append(pa.ipc.open_stream(dataset.data.data).read_all().to_pandas())
    return tablas


filas = []
for caso in REFERENCIA["casos"]:
    nombre = caso["nombre"]
    filtrada = aplicar_filtros(serie, caso["departamentos"], caso["entidades"], caso["desde"], caso["hasta"])
    resumen = {"combinación": nombre}

    # 1) Departamentos
    por_depto = valor_por_departamento(filtrada)
    obtenido = {r["departamento"]: {"contratos": int(r["contratos"]), "contratos_atipicos": int(r["contratos_atipicos"]), "valor_total": int(r["valor_total"])}
                for _, r in por_depto.iterrows()}
    ok_deptos = revisar(obtenido == caso["por_departamento"], f"{nombre}: valor por departamento")
    ok_suma = revisar(sum(d["valor_total"] for d in obtenido.values()) == caso["totales"]["valor_total"]
                      and sum(d["contratos"] for d in obtenido.values()) == caso["totales"]["contratos"], f"{nombre}: la suma por departamento no es el total")
    ok_sin = revisar((SIN_DEPARTAMENTO in obtenido) == (SIN_DEPARTAMENTO in caso["por_departamento"]), f"{nombre}: SIN DEPARTAMENTO")
    resumen["departamentos"] = f"{len(obtenido)}: " + ("iguales" if ok_deptos and ok_suma and ok_sin else "DIFERENTES")

    # 2) Concentración
    conc = concentracion_entidades(filtrada)
    esperado = caso["concentracion"]
    ok_conc = all(revisar(conc[k] == esperado[k], f"{nombre}: concentración, {k}: {conc[k]} frente a {esperado[k]}")
                  for k in ("entidades", "total", "top10_valor", "para_50", "para_80"))
    resumen["50 % / 80 % / top 10"] = f"{conc['para_50']} / {conc['para_80']} / {100 * conc['top10_valor'] / conc['total']:.1f} %" + ("" if ok_conc else " DIFERENTE")

    # 3) Dashboard real
    app = abrir_dashboard(caso)
    tablas = datos_de_graficos(app)
    barras = next((t for t in tablas if "categoria" in t.columns), None)
    curva = next((t for t in tablas if list(t.columns) == ["entidades", "acumulado"]), None)
    en_pantalla = 0
    if revisar(barras is not None, f"{nombre}: no hay gráfico de barras por departamento"):
        dibujado = {r["departamento"]: (int(r["contratos"]), int(r["valor_total"])) for _, r in barras.iterrows()}
        en_pantalla += revisar(dibujado == {d: (v["contratos"], v["valor_total"]) for d, v in caso["por_departamento"].items()}, f"{nombre}: barras dibujadas")
        categorias = dict(zip(barras["departamento"], barras["categoria"]))
        en_pantalla += revisar(all((categorias[d] == "Sin departamento") == (d == SIN_DEPARTAMENTO) for d in categorias), f"{nombre}: categoría aparte")
    tarjetas = {m.label: m.value for m in app.metric}
    en_pantalla += revisar(tarjetas.get("Entidades que reúnen el 50 % del valor") == miles(esperado["para_50"]), f"{nombre}: tarjeta del 50 %")
    en_pantalla += revisar(tarjetas.get("Entidades que reúnen el 80 % del valor") == miles(esperado["para_80"]), f"{nombre}: tarjeta del 80 %")
    if esperado["entidades"] >= 3:
        en_pantalla += revisar(curva is not None and len(curva) == esperado["entidades"], f"{nombre}: curva de {esperado['entidades']} entidades")
    else:
        en_pantalla += revisar(curva is None, f"{nombre}: con pocas entidades no se dibuja la curva")
    en_pantalla += revisar(any(c.value.startswith("✓ La suma de los") for c in app.caption), f"{nombre}: falta la línea de comprobación de la suma")
    resumen["pantalla"] = "igual" if en_pantalla == 6 else f"{en_pantalla} de 6"
    filas.append(resumen)

print(pd.DataFrame(filas).to_string(index=False))
print(f"\nReferencia de Spark generada el {REFERENCIA['generado_utc']} UTC sobre gold; {len(REFERENCIA['casos'])} combinaciones de filtros.")
if errores:
    print("\nNO COINCIDE:\n  " + "\n  ".join(errores))
    sys.exit(1)
print("Valor por departamento y concentración coinciden con Spark (pesos y contratos exactos) y con lo que dibuja el dashboard.")
