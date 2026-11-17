"""Dashboard del Observatorio de Contratación Pública (Corte 3, Punto 4).

Se lanza desde la raíz del repositorio con:  streamlit run dashboard/app.py

Lee las tablas de consumo de dashboard/data/ (notebook 07, T4.1) con pandas; no usa Spark ni MinIO.

T4.3: filtros de departamento, entidad y rango de meses en la barra lateral, y tarjetas con los totales filtrados.
Los módulos de T4.4 a T4.6 (tiempo, rankings y geografía) usan `serie` y `contratistas`, ya filtradas, de este archivo.
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


def aplicar_filtros(df: pd.DataFrame, departamentos: list, entidades: list, mes_desde: str, mes_hasta: str) -> pd.DataFrame:
    """Filas de df que cumplen los filtros. Una lista vacía significa 'todos'; los meses son 'AAAA-MM' y se comparan como texto."""
    mascara = (df["anio_mes"] >= mes_desde) & (df["anio_mes"] <= mes_hasta)
    if departamentos:
        mascara &= df["departamento"].isin(departamentos)
    if entidades:
        mascara &= df["id_entidad"].isin(entidades)
    return df[mascara]


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
serie_completa = tablas["serie_mensual"]
nombres_entidad = tablas["entidades"].set_index("id_entidad")["nombre_entidad"]
gold, flujo = metadatos["gold"], metadatos["flujo"]

# --- Filtros (barra lateral) ---
meses = sorted(serie_completa["anio_mes"].unique())
departamentos_todos = sorted(serie_completa["departamento"].unique())

with st.sidebar:
    st.header("Filtros")
    departamentos = st.multiselect(
        "Departamento", departamentos_todos, key="f_departamento", placeholder="Todos",
        help="Sin selección se incluyen todos. 'SIN DEPARTAMENTO' agrupa los contratos cuya entidad no lo informa.",
    )

    # Las entidades ofrecidas son las que tienen contratos en los departamentos elegidos; si un cambio de departamento
    # deja fuera una entidad ya elegida, se quita de la selección (Streamlit falla si la selección sale de las opciones).
    en_departamentos = serie_completa if not departamentos else serie_completa[serie_completa["departamento"].isin(departamentos)]
    ids_posibles = en_departamentos["id_entidad"].unique()
    opciones_entidad = sorted(ids_posibles, key=lambda i: (nombres_entidad.get(i, i).casefold(), i))
    if "f_entidad" in st.session_state:
        st.session_state["f_entidad"] = [e for e in st.session_state["f_entidad"] if e in set(opciones_entidad)]
    entidades = st.multiselect(
        f"Entidad ({miles(len(opciones_entidad))} disponibles)", opciones_entidad, key="f_entidad", placeholder="Todas",
        format_func=lambda i: f"{nombres_entidad.get(i, i)} ({i.removeprefix('NIT:')})",
        help="Escribe para buscar por nombre o NIT. Sin selección se incluyen todas.",
    )

    mes_desde, mes_hasta = st.select_slider(
        "Meses de adjudicación", options=meses, value=(meses[0], meses[-1]), key="f_meses",
        help="Rango inclusivo, de 'AAAA-MM' a 'AAAA-MM'.",
    )
    if st.button("Quitar filtros"):
        for clave in ("f_departamento", "f_entidad", "f_meses"):
            st.session_state.pop(clave, None)
        st.rerun()

serie = aplicar_filtros(serie_completa, departamentos, entidades, mes_desde, mes_hasta)
contratistas = aplicar_filtros(tablas["contratistas_mensual"], departamentos, entidades, mes_desde, mes_hasta)

# --- Encabezado y tarjetas ---
st.caption(
    f"Contratos adjudicados de {gold['primer_mes']} a {gold['ultimo_mes']}. "
    f"Último lote procesado por el flujo: {flujo['fecha_ultimo_micro_lote_utc']} UTC. "
    f"Tablas generadas el {metadatos['generado_utc']} UTC."
)

filtros_activos = bool(departamentos or entidades or (mes_desde, mes_hasta) != (meses[0], meses[-1]))
resumen_filtros = [
    f"departamento: {', '.join(departamentos)}" if departamentos else None,
    f"{len(entidades)} entidad(es)" if entidades else None,
    f"meses: {mes_desde} a {mes_hasta}" if (mes_desde, mes_hasta) != (meses[0], meses[-1]) else None,
]
if filtros_activos:
    st.markdown("**Filtros aplicados:** " + " · ".join(f for f in resumen_filtros if f))

if serie.empty:
    st.warning(
        "No hay contratos con esta combinación de filtros. Prueba con otro rango de meses, quita alguna entidad "
        "o usa «Quitar filtros» en la barra lateral."
    )
    st.stop()

contratos = int(serie["contratos"].sum())
valor = int(serie["valor_total"].sum())
atipicos = int(serie["contratos_atipicos"].sum())
valor_atipicos = int(serie["valor_atipicos"].sum())

# Los valores largos ("352,9 billones") se cortaban con cinco tarjetas en una fila: se reparten en dos filas y se achica la letra
st.markdown(
    "<style>[data-testid='stMetricValue'] {font-size: 2rem;} [data-testid='stMetricLabel'] p {white-space: normal;}</style>",
    unsafe_allow_html=True,
)
c1, c2, c3 = st.columns(3)
c4, c5, _ = st.columns(3)
c1.metric("Contratos adjudicados", miles(contratos), help=f"{contratos:,} contratos, con los atípicos incluidos.")
c2.metric(
    "Valor adjudicado (sin atípicos)", billones(valor),
    help=f"{valor:,} pesos. No incluye los contratos atípicos (T1.5), que son errores de captura probables.",
)
c3.metric(
    "Contratos atípicos", miles(atipicos),
    help=f"Su valor, que no entra en la tarjeta anterior, suma {valor_atipicos:,} pesos.",
)
c4.metric("Entidades", miles(serie["id_entidad"].nunique()))
c5.metric("Contratistas", miles(contratistas["id_contratista"].nunique()))

if not filtros_activos:
    coincide = (
        contratos == gold["contratos"] and valor == gold["valor_total"]
        and atipicos == gold["contratos_atipicos"] and valor_atipicos == gold["valor_atipicos"]
    )
    st.caption(
        "Sin filtros, los totales " + ("coinciden con los de gold." if coincide else "NO coinciden con los de gold: vuelve a generar las tablas con el notebook 07.")
    )

st.info("Los módulos de tiempo, rankings y geografía se añaden en T4.4 a T4.6 y usarán estos mismos filtros.")
