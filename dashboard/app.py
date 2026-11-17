"""Dashboard del Observatorio de Contratación Pública (Corte 3, Punto 4).

Se lanza desde la raíz del repositorio con:  streamlit run dashboard/app.py

Lee las tablas de consumo de dashboard/data/ (notebook 07, T4.1) con pandas; no usa Spark ni MinIO.

T4.3: filtros de departamento, entidad y rango de meses en la barra lateral, y tarjetas con los totales filtrados.
T4.4: gráfico mensual de valor y contratos con los periodos de interés (dashboard/periodos.py) y los picos.
T4.5: rankings de entidades y contratistas (dashboard/consultas.py).
El módulo de T4.6 (geografía) usa `serie` y `contratistas`, ya filtradas, de este archivo.
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from consultas import aplicar_filtros, calcular_ranking
from periodos import TIPOS, contexto_mes, periodos_en

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

# --- Evolución en el tiempo (T4.4) ---
st.subheader("Evolución en el tiempo")
st.caption(
    "Valor y número de contratos adjudicados por mes. Las franjas marcan los periodos de la ley de garantías y los cierres "
    "de vigencia fiscal; los puntos rojos son los meses de mayor valor y de más contratos. Pasa el cursor sobre un punto o una franja para leerla."
)
m1, m2 = st.columns(2)
marcar_ley = m1.checkbox("Marcar la ley de garantías", value=True, key="m_ley")
marcar_fiscal = m2.checkbox("Marcar el cierre de vigencia fiscal", value=True, key="m_fiscal")

# Eje de tiempo completo y ordenado: los meses sin contratos aparecen en cero, no se saltan
meses_rango = pd.period_range(mes_desde, mes_hasta, freq="M").strftime("%Y-%m")
mensual = (
    serie.groupby("anio_mes")[["contratos", "valor_total"]].sum()
    .reindex(meses_rango, fill_value=0).rename_axis("anio_mes").reset_index()
)
mensual["anio_mes"] = mensual["anio_mes"].astype(str)
mensual["mes"] = pd.to_datetime(mensual["anio_mes"] + "-01")
mensual["valor_billones"] = mensual["valor_total"] / 1e12
mensual["contexto"] = mensual["anio_mes"].map(contexto_mes)

N_PICOS = 5
picos_valor = mensual[mensual["valor_total"] > 0].nlargest(N_PICOS, "valor_total")
picos_contratos = mensual[mensual["contratos"] > 0].nlargest(N_PICOS, "contratos")
meses_pico = set(picos_valor["anio_mes"]) | set(picos_contratos["anio_mes"])

bandas = pd.DataFrame(periodos_en(mes_desde, mes_hasta, ley=marcar_ley, fiscal=marcar_fiscal))
dominio_x = [mensual["mes"].iloc[0], mensual["mes"].iloc[-1] + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1)]
n_meses = len(mensual)
eje_x = alt.Axis(format="%Y-%m" if n_meses <= 36 else "%Y", tickCount="month" if n_meses <= 36 else "year", labelOverlap=True)


def grafico_mensual(columna: str, titulo: str, formato: str, con_leyenda: bool) -> alt.Chart:
    """Línea mensual con puntos que se pueden leer, picos en rojo y franjas de periodos detrás."""
    x = alt.X("mes:T", title=None, scale=alt.Scale(domain=dominio_x), axis=eje_x)
    y = alt.Y(f"{columna}:Q", title=titulo, axis=alt.Axis(format=formato))
    tip = [
        alt.Tooltip("anio_mes:N", title="Mes"),
        alt.Tooltip("valor_billones:Q", title="Valor (billones de pesos)", format=",.2f"),
        alt.Tooltip("contratos:Q", title="Contratos", format=",d"),
        alt.Tooltip("contexto:N", title="Periodos"),
    ]
    capas = []
    if not bandas.empty:
        franjas = bandas.assign(fin_exclusivo=pd.to_datetime(bandas["fin"]) + pd.Timedelta(days=1))
        capas.append(
            alt.Chart(franjas).mark_rect(clip=True, opacity=0.3).encode(
                x=alt.X("inicio:T"), x2="fin_exclusivo:T",
                color=alt.Color(
                    "tipo:N", title=None,
                    scale=alt.Scale(domain=TIPOS, range=["#d62728", "#ff9f1c", "#7f8fa6"]),
                    legend=alt.Legend(orient="top", columns=1, labelLimit=500) if con_leyenda else None,
                ),
                tooltip=[alt.Tooltip("nombre:N", title="Periodo"), alt.Tooltip("tipo:N", title="Tipo"),
                         alt.Tooltip("inicio:T", title="Desde", format="%Y-%m-%d"), alt.Tooltip("fin:T", title="Hasta", format="%Y-%m-%d")],
            )
        )
    base = alt.Chart(mensual).encode(x=x, y=y, tooltip=tip)
    capas += [
        base.mark_line(),
        base.mark_point(filled=True, size=22),
        alt.Chart(mensual[mensual["anio_mes"].isin(meses_pico)]).encode(x=x, y=y, tooltip=tip).mark_point(
            filled=True, size=110, color="#ff2d2d", stroke="white", strokeWidth=1),
    ]
    return alt.layer(*capas).properties(height=210)


st.altair_chart(
    alt.vconcat(
        grafico_mensual("valor_billones", "Valor adjudicado (billones de pesos)", ",.1f", True),
        grafico_mensual("contratos", "Contratos adjudicados", ",d", False),
    ).resolve_scale(color="shared"),
    width="stretch",
)

ultima_fecha = pd.Timestamp(gold["ultima_fecha_adjudicacion"])
if ultima_fecha.strftime("%Y-%m") == mes_hasta and ultima_fecha != ultima_fecha + pd.offsets.MonthEnd(0):
    st.caption(
        f"El último mes de los datos ({mes_hasta}) llega solo hasta el {ultima_fecha:%d-%m-%Y}: su caída no es real. "
        f"Los primeros meses ({gold['primer_mes']} y 2016) tienen muy pocos contratos."
    )

# Los puntos deben coincidir con las ventanas del flujo (T2.4), que agregan por mes y departamento: solo comparables sin filtro de entidad
if entidades:
    st.caption("Con un filtro de entidad no hay ventanas del flujo equivalentes (el flujo agrega por mes y departamento).")
else:
    ventanas = aplicar_filtros(tablas["ventanas_flujo"], departamentos, [], mes_desde, mes_hasta)
    del_flujo = ventanas.groupby("anio_mes")[["contratos", "valor_total"]].sum().reindex(meses_rango, fill_value=0)
    coincide_flujo = (
        (del_flujo["contratos"].to_numpy() == mensual["contratos"].to_numpy()).all()
        and (del_flujo["valor_total"].to_numpy() == mensual["valor_total"].to_numpy()).all()
    )
    if coincide_flujo:
        st.caption(
            f"✓ Los {n_meses} puntos mensuales coinciden con las ventanas del flujo (T2.4) para estos filtros."
            if n_meses > 1 else "✓ El punto mensual coincide con la ventana del flujo (T2.4) para estos filtros."
        )
    else:
        st.warning("Los puntos mensuales NO coinciden con las ventanas del flujo (T2.4): vuelve a generar las tablas con el notebook 07.")

st.markdown(f"**Picos detectados:** los {N_PICOS} meses de mayor valor y de más contratos en el periodo filtrado.")
p1, p2 = st.columns(2)
for columna_pantalla, titulo, picos in ((p1, "Mayor valor adjudicado", picos_valor), (p2, "Más contratos adjudicados", picos_contratos)):
    columna_pantalla.markdown(f"*{titulo}*")
    columna_pantalla.dataframe(
        picos.rename(columns={"anio_mes": "Mes", "valor_billones": "Valor (billones)", "contratos": "Contratos", "contexto": "Periodos"})
        [["Mes", "Valor (billones)", "Contratos", "Periodos"]],
        hide_index=True,
        column_config={"Valor (billones)": st.column_config.NumberColumn(format="%.2f")},
    )

# --- Principales actores (T4.5) ---
st.subheader("Principales actores")
st.caption(
    "Las entidades y los contratistas con más valor adjudicado o más contratos, con los filtros aplicados. "
    "El valor no incluye los contratos atípicos; los contratos sí los incluyen (columna «Atípicos»). En empate gana el identificador menor."
)
r1, r2 = st.columns(2)
n_ranking = int(r1.number_input("Cuántos mostrar (N)", min_value=1, max_value=50, value=10, step=1, key="n_ranking"))
orden_ranking = r2.radio("Ordenar por", ["Valor adjudicado", "Número de contratos"], horizontal=True, key="orden_ranking")
columna_orden = "valor_total" if orden_ranking == "Valor adjudicado" else "contratos"
total_orden = valor if columna_orden == "valor_total" else contratos
nombres_contratista = tablas["contratistas"].set_index("id_contratista")["nombre_contratista"]


def porcentaje(parte: float, total: float) -> str:
    return f"{100 * parte / total:.1f}".replace(".", ",") + " %" if total else "–"


def mostrar_ranking(pantalla, titulo: str, df: pd.DataFrame, clave: str, nombres: pd.Series) -> None:
    top = calcular_ranking(df, clave, columna_orden, n_ranking)
    pantalla.markdown(f"**{titulo}**")
    pantalla.dataframe(
        pd.DataFrame({
            "#": range(1, len(top) + 1),
            "Nombre": [nombres.get(i, i) for i in top[clave]],
            "Identificación": top[clave],
            "Contratos": [miles(int(c)) for c in top["contratos"]],
            "Atípicos": [miles(int(a)) for a in top["contratos_atipicos"]],
            "Valor (millones de pesos)": [miles(int(round(v / 1e6))) for v in top["valor_total"]],
            "Participación": [porcentaje(x, total_orden) for x in top[columna_orden]],
        }),
        hide_index=True,
    )
    pantalla.caption(
        f"Los {len(top)} primeros suman el {porcentaje(top[columna_orden].sum(), total_orden)} "
        f"del {'valor adjudicado' if columna_orden == 'valor_total' else 'número de contratos'} filtrado."
    )


# Una tabla bajo la otra y a todo el ancho: en media pantalla las columnas de contratos y valor quedaban fuera de la vista
mostrar_ranking(st, f"Top {n_ranking} entidades", serie, "id_entidad", nombres_entidad)
mostrar_ranking(st, f"Top {n_ranking} contratistas", contratistas, "id_contratista", nombres_contratista)

st.info("El módulo geográfico y de concentración se añade en T4.6 y usará estos mismos filtros.")
