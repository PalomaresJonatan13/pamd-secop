"""Dashboard del Observatorio de Contratación Pública (Corte 3, Punto 4).

Se lanza desde la raíz del repositorio con:  streamlit run dashboard/app.py

Lee las tablas de consumo de dashboard/data/ (notebook 07, T4.1) con pandas; no usa Spark ni MinIO.

T4.3: filtros de departamento, entidad y rango de meses en la barra lateral, y tarjetas con los totales filtrados.
T4.4: gráfico mensual de valor y contratos con los periodos de interés (dashboard/periodos.py) y los picos.
T4.5: rankings de entidades y contratistas (dashboard/consultas.py).
T4.6: valor por departamento y concentración del gasto en las entidades.
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from consultas import aplicar_filtros, calcular_ranking, concentracion_entidades, etiquetas_entidades, valor_por_departamento
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

RANGO_COMPLETO = (meses[0], meses[-1])
etiqueta_de = etiquetas_entidades(tablas["entidades"])
id_de = {etiqueta: i for i, etiqueta in etiqueta_de.items()}
assert len(id_de) == len(etiqueta_de), "Dos entidades con la misma etiqueta"
# El texto de cada opción es también su valor en la dirección (?orden=Contratos); con format_func la dirección usaría el texto visible
ORDENES = ["Valor", "Contratos"]


def quitar_filtros():
    """Deja los tres filtros abiertos.

    Corre como callback del botón, antes de que se dibujen los controles, y *asigna* los valores por defecto: así la
    pantalla y la dirección cambian junto con los datos. (Borrar las claves y llamar a st.rerun() recalculaba los datos,
    pero el navegador seguía mostrando los filtros anteriores.)
    """
    st.session_state["departamento"] = []
    st.session_state["entidad"] = []
    st.session_state["meses"] = RANGO_COMPLETO


# Cada filtro está sincronizado con la dirección (bind="query-params"; la clave es el nombre del parámetro), así que la
# dirección siempre refleja lo que se ve y se puede compartir o repetir. Ejemplo:
#   ?departamento=Antioquia&departamento=Boyacá&entidad=INVIAS (800215807)&meses=2020-01&meses=2023-12&n=10&orden=Valor
# Los valores que no existen se ignoran; un valor igual al de por defecto no aparece en la dirección.
with st.sidebar:
    st.header("Filtros")
    departamentos = st.multiselect(
        "Departamento", departamentos_todos, key="departamento", bind="query-params", placeholder="Todos",
        help="Sin selección se incluyen todos. 'SIN DEPARTAMENTO' agrupa los contratos cuya entidad no lo informa.",
    )

    # Las entidades ofrecidas son las que tienen contratos en los departamentos elegidos; si un cambio de departamento
    # deja fuera una entidad ya elegida, se quita de la selección (Streamlit falla si la selección sale de las opciones).
    # Las opciones son el texto visible («NOMBRE (NIT)»), no el NIT: con bind="query-params" la dirección usa el texto de la opción.
    en_departamentos = serie_completa if not departamentos else serie_completa[serie_completa["departamento"].isin(departamentos)]
    opciones_entidad = sorted((etiqueta_de[i] for i in en_departamentos["id_entidad"].unique()), key=lambda e: (e.casefold(), e))
    if "entidad" in st.session_state:
        st.session_state["entidad"] = [e for e in st.session_state["entidad"] if e in set(opciones_entidad)]
    elegidas = st.multiselect(
        f"Entidad ({miles(len(opciones_entidad))} disponibles)", opciones_entidad, key="entidad", bind="query-params", placeholder="Todas",
        help="Escribe para buscar por nombre o NIT. Sin selección se incluyen todas.",
    )
    entidades = [id_de[e] for e in elegidas]

    mes_desde, mes_hasta = st.select_slider(
        "Meses de adjudicación", options=meses, value=RANGO_COMPLETO, key="meses", bind="query-params",
        help="Rango inclusivo, de 'AAAA-MM' a 'AAAA-MM'.",
    )
    st.button("Quitar filtros", on_click=quitar_filtros)

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
            f"✓ Los {n_meses} puntos mensuales coinciden con las ventanas del flujo para estos filtros."
            if n_meses > 1 else "✓ El punto mensual coincide con la ventana del flujo para estos filtros."
        )
    else:
        st.warning("Los puntos mensuales NO coinciden con las ventanas del flujo: vuelve a generar las tablas con el notebook 07.")

st.markdown(f"**Picos detectados:** los {N_PICOS} meses de mayor valor y de más contratos en el periodo filtrado.")
p1, p2 = st.columns(2)
for columna_pantalla, titulo, picos in ((p1, "Mayor valor adjudicado", picos_valor), (p2, "Más contratos adjudicados", picos_contratos)):
    columna_pantalla.markdown(f"*{titulo}*")
    columna_pantalla.dataframe(
        picos.assign(contratos=picos["contratos"].map(lambda c: miles(int(c))))
        .rename(columns={"anio_mes": "Mes", "valor_billones": "Valor (billones)", "contratos": "Contratos", "contexto": "Periodos"})
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
n_ranking = int(r1.number_input("Cuántos mostrar (N)", min_value=1, max_value=50, value=10, step=1, key="n", bind="query-params"))
orden_ranking = r2.radio("Ordenar por", ORDENES, horizontal=True, key="orden", bind="query-params")
columna_orden = "valor_total" if orden_ranking == "Valor" else "contratos"
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
        # anchos fijos: con el automático, la última columna quedaba cortada a la derecha
        column_config={
            "#": st.column_config.TextColumn(width=35),
            "Nombre": st.column_config.TextColumn(width=384),
            "Identificación": st.column_config.TextColumn(width=134),
            "Contratos": st.column_config.TextColumn(width=70),
            "Atípicos": st.column_config.TextColumn(width=65),
            "Valor (millones de pesos)": st.column_config.TextColumn(width=150),
            "Participación": st.column_config.TextColumn(width=95),
        },
    )
    pantalla.caption(
        f"Los {len(top)} primeros suman el {porcentaje(top[columna_orden].sum(), total_orden)} "
        f"del {'valor adjudicado' if columna_orden == 'valor_total' else 'número de contratos'} filtrado."
    )


# Una tabla bajo la otra y a todo el ancho: en media pantalla las columnas de contratos y valor quedaban fuera de la vista
mostrar_ranking(st, f"Top {n_ranking} entidades", serie, "id_entidad", nombres_entidad)
mostrar_ranking(st, f"Top {n_ranking} contratistas", contratistas, "id_contratista", nombres_contratista)

# --- Dónde se concentra el dinero (T4.6) ---
SIN_DEPARTAMENTO = "SIN DEPARTAMENTO"
st.subheader("Dónde se concentra el dinero")

por_departamento = valor_por_departamento(serie)
st.markdown("**Valor adjudicado por departamento**")
st.caption(
    "Departamento de la entidad que contrata. Los contratos cuya entidad no informa departamento forman una categoría aparte "
    "(«Sin departamento»), no se ocultan. El valor no incluye los atípicos."
)
barras = por_departamento.assign(
    valor_billones=por_departamento["valor_total"] / 1e12,
    participacion=100 * por_departamento["valor_total"] / valor,
    categoria=por_departamento["departamento"].map(lambda d: "Sin departamento" if d == SIN_DEPARTAMENTO else "Departamento"),
)
y_depto = alt.Y("departamento:N", sort=list(barras["departamento"]), title=None, axis=alt.Axis(labelLimit=260))
x_valor = alt.X("valor_billones:Q", title="Valor adjudicado (billones de pesos)", axis=alt.Axis(format=",.0f"))
base_barras = alt.Chart(barras).encode(
    y=y_depto, x=x_valor,
    tooltip=[
        alt.Tooltip("departamento:N", title="Departamento"),
        alt.Tooltip("valor_billones:Q", title="Valor (billones de pesos)", format=",.3f"),
        alt.Tooltip("participacion:Q", title="% del valor filtrado", format=".1f"),
        alt.Tooltip("contratos:Q", title="Contratos", format=",d"),
    ],
)
st.altair_chart(
    (
        base_barras.mark_bar().encode(
            color=alt.Color("categoria:N", title=None, scale=alt.Scale(domain=["Departamento", "Sin departamento"], range=["#4c78a8", "#ff9f1c"]),
                            legend=alt.Legend(orient="top"))
        )
        + base_barras.mark_text(align="left", dx=3, fontSize=11, color="#9aa0a6").encode(text=alt.Text("valor_billones:Q", format=",.1f"))
    ).properties(height=alt.Step(24)),  # 24 px por departamento: se ajusta a 1 barra o a 34
    width="stretch",
)

suma_valor, suma_contratos = int(por_departamento["valor_total"].sum()), int(por_departamento["contratos"].sum())
if suma_valor == valor and suma_contratos == contratos:
    st.caption(
        f"✓ La suma de los departamentos mostrados ({len(por_departamento)}: {miles(suma_contratos)} contratos, {billones(suma_valor)}) "
        "es igual a los totales filtrados de las tarjetas."
    )
else:
    st.warning("La suma por departamento NO coincide con los totales filtrados: vuelve a generar las tablas con el notebook 07.")
tres_primeros = por_departamento.head(3)
if len(por_departamento) > 3 and valor:
    st.caption(
        f"{', '.join(tres_primeros['departamento'])} suman el {porcentaje(tres_primeros['valor_total'].sum(), valor)} del valor filtrado."
    )
sin_depto = por_departamento[por_departamento["departamento"] == SIN_DEPARTAMENTO]
if not sin_depto.empty:
    st.caption(
        f"Sin departamento: {miles(int(sin_depto['contratos'].iloc[0]))} contratos y "
        f"{porcentaje(int(sin_depto['valor_total'].iloc[0]), valor)} del valor filtrado."
    )

st.markdown("**Concentración del valor en las entidades**")
concentracion = concentracion_entidades(serie)
if concentracion is None:
    st.info("Con estos filtros el valor adjudicado (sin atípicos) es cero: no hay concentración que medir.")
else:
    n_ent, para_50, para_80 = concentracion["entidades"], concentracion["para_50"], concentracion["para_80"]
    k1, k2, k3 = st.columns(3)
    k1.metric("Entidades que reúnen el 50 % del valor", miles(para_50), delta=f"{porcentaje(para_50, n_ent)} de las {miles(n_ent)} entidades", delta_color="off", delta_arrow="off")
    k2.metric("Entidades que reúnen el 80 % del valor", miles(para_80), delta=f"{porcentaje(para_80, n_ent)} de las {miles(n_ent)} entidades", delta_color="off", delta_arrow="off")
    k3.metric("Las 10 primeras entidades reúnen", porcentaje(concentracion["top10_valor"], concentracion["total"]), delta="del valor filtrado", delta_color="off", delta_arrow="off")
    st.caption(
        f"{miles(para_50)} de {miles(n_ent)} entidades ({porcentaje(para_50, n_ent)}) reúnen la mitad del valor adjudicado en lo filtrado; "
        f"con {miles(para_80)} ({porcentaje(para_80, n_ent)}) se llega al 80 %. Se cuentan las entidades con al menos un contrato."
    )
    if n_ent >= 3:
        curva = concentracion["curva"]
        marcas = pd.DataFrame({"entidades": [para_50, para_80], "acumulado": [curva["acumulado"].iloc[para_50 - 1], curva["acumulado"].iloc[para_80 - 1]],
                               "umbral": ["50 %", "80 %"]})
        x_curva = alt.X("entidades:Q", title="Número de entidades, de mayor a menor valor (escala logarítmica)",
                        scale=alt.Scale(type="log", domain=[1, n_ent], nice=False), axis=alt.Axis(format=",d"))
        y_curva = alt.Y("acumulado:Q", title="% acumulado del valor", scale=alt.Scale(domain=[0, 100]))
        st.altair_chart(
            alt.layer(
                alt.Chart(pd.DataFrame({"y": [50, 80]})).mark_rule(strokeDash=[4, 4], opacity=0.5).encode(y="y:Q"),
                alt.Chart(curva).mark_line().encode(
                    x=x_curva, y=y_curva,
                    tooltip=[alt.Tooltip("entidades:Q", title="Entidades", format=",d"), alt.Tooltip("acumulado:Q", title="% acumulado del valor", format=".1f")],
                ),
                alt.Chart(marcas).mark_point(filled=True, size=90, color="#ff2d2d").encode(
                    x="entidades:Q", y="acumulado:Q",
                    tooltip=[alt.Tooltip("umbral:N", title="Umbral"), alt.Tooltip("entidades:Q", title="Entidades", format=",d"), alt.Tooltip("acumulado:Q", title="% acumulado", format=".1f")],
                ),
            ).properties(height=260),
            width="stretch",
        )
    else:
        st.caption("Con tan pocas entidades la curva no aporta: amplía los filtros para ver la concentración.")
