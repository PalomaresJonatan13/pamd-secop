"""Dashboard del Observatorio de Contratación Pública (Corte 3, Punto 4).

Se lanza desde la raíz del repositorio con:  streamlit run dashboard/app.py

Lee las tablas de consumo de dashboard/data/ (notebook 07, T4.1) con pandas; no usa Spark ni MinIO.
Por ahora solo comprueba la carga y muestra los totales; los filtros y los módulos llegan en T4.3 a T4.6.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATOS = Path(__file__).parent / "data"
TABLAS = ["serie_mensual", "contratistas_mensual", "entidades", "contratistas", "ventanas_flujo"]


@st.cache_data
def cargar_tabla(nombre: str) -> pd.DataFrame:
    """Lee una tabla de consumo; Streamlit la guarda en memoria y no la relee en cada interacción."""
    return pd.read_parquet(DATOS / f"{nombre}.parquet")


@st.cache_data
def cargar_metadatos() -> dict:
    return json.loads((DATOS / "metadatos.json").read_text(encoding="utf-8"))


def miles(n: int) -> str:
    """Entero con punto como separador de miles (formato colombiano)."""
    return f"{n:,}".replace(",", ".")


def billones(pesos: int) -> str:
    """Pesos expresados en billones (10^12), con coma decimal."""
    return f"{pesos / 1e12:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".") + " billones"


st.set_page_config(page_title="Observatorio de Contratación Pública", layout="wide")
st.title("Observatorio de Contratación Pública – SECOP II")

faltan = [f for f in [*(f"{t}.parquet" for t in TABLAS), "metadatos.json"] if not (DATOS / f).exists()]
if faltan:
    st.error(
        "Faltan archivos en dashboard/data/: " + ", ".join(faltan) + ". "
        "Se generan con el notebook 07 (RECONSTRUIR_CONSUMO = True)."
    )
    st.stop()

metadatos = cargar_metadatos()
tablas = {nombre: cargar_tabla(nombre) for nombre in TABLAS}
serie = tablas["serie_mensual"]

gold, flujo = metadatos["gold"], metadatos["flujo"]
st.caption(
    f"Contratos adjudicados de {gold['primer_mes']} a {gold['ultimo_mes']}. "
    f"Último lote procesado por el flujo: {flujo['fecha_ultimo_micro_lote_utc']} UTC. "
    f"Tablas generadas el {metadatos['generado_utc']} UTC."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Contratos adjudicados", miles(int(serie["contratos"].sum())))
c2.metric("Valor adjudicado (sin atípicos)", billones(int(serie["valor_total"].sum())))
c3.metric("Entidades", miles(serie["id_entidad"].nunique()))
c4.metric("Contratistas", miles(len(tablas["contratistas"])))

st.info("Datos cargados. Los filtros y los módulos (tiempo, rankings y geografía) se añaden en T4.3 a T4.6.")

with st.expander("Tablas de consumo cargadas"):
    st.dataframe(
        pd.DataFrame(
            [{"tabla": n, "filas": len(t), "columnas": ", ".join(t.columns)} for n, t in tablas.items()]
        ),
        hide_index=True,
    )
