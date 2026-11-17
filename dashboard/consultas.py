"""Consultas del dashboard sobre las tablas de consumo (T4.3 y T4.5).

Las usan `app.py` y `scripts/comprobar_rankings.py`, que compara estos resultados con consultas de Spark sobre gold.
Son funciones de pandas puras: no leen archivos ni dependen de Streamlit.
"""
import pandas as pd

MEDIDAS_RANKING = ["contratos", "contratos_atipicos", "valor_total"]


def aplicar_filtros(df: pd.DataFrame, departamentos: list, entidades: list, mes_desde: str, mes_hasta: str) -> pd.DataFrame:
    """Filas de df que cumplen los filtros. Una lista vacía significa 'todos'; los meses son 'AAAA-MM' y se comparan como texto."""
    mascara = (df["anio_mes"] >= mes_desde) & (df["anio_mes"] <= mes_hasta)
    if departamentos:
        mascara &= df["departamento"].isin(departamentos)
    if entidades:
        mascara &= df["id_entidad"].isin(entidades)
    return df[mascara]


def calcular_ranking(df: pd.DataFrame, clave: str, orden: str, n: int) -> pd.DataFrame:
    """Las n filas con más `orden` ('valor_total' o 'contratos') al agrupar df por `clave` ('id_entidad' o 'id_contratista').

    Devuelve la clave y las medidas sumadas (contratos, contratos_atipicos, valor_total), de mayor a menor. En empate gana el
    identificador menor, para que el resultado sea siempre el mismo. `valor_total` no incluye los atípicos; `contratos` sí.
    """
    agrupado = df.groupby(clave)[MEDIDAS_RANKING].sum().reset_index()
    return agrupado.sort_values([orden, clave], ascending=[False, True]).head(n).reset_index(drop=True)
