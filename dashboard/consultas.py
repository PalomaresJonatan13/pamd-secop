"""Consultas del dashboard sobre las tablas de consumo (T4.3, T4.5 y T4.6).

Las usan `app.py` y `scripts/comprobar_rankings.py`, que compara estos resultados con consultas de Spark sobre gold.
Son funciones de pandas puras: no leen archivos ni dependen de Streamlit.
"""
import numpy as np
import pandas as pd

MEDIDAS_RANKING = ["contratos", "contratos_atipicos", "valor_total"]


def etiquetas_entidades(entidades: pd.DataFrame) -> dict:
    """Texto que el dashboard muestra y usa en la dirección para cada entidad: 'NOMBRE (NIT)'. Una clave por id_entidad.

    `entidades` es la tabla entidades.parquet (id_entidad, nombre_entidad). El NIT va sin el prefijo 'NIT:'.
    """
    return {i: f"{nombre} ({i.removeprefix('NIT:')})" for i, nombre in zip(entidades["id_entidad"], entidades["nombre_entidad"])}


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


def valor_por_departamento(df: pd.DataFrame) -> pd.DataFrame:
    """Contratos, atípicos y valor (sin atípicos) por departamento, de mayor a menor valor.

    Los contratos sin departamento forman la categoría 'SIN DEPARTAMENTO': no se ocultan, y la suma de las filas es igual
    al total de df.
    """
    por_depto = df.groupby("departamento")[MEDIDAS_RANKING].sum().reset_index()
    return por_depto.sort_values(["valor_total", "departamento"], ascending=[False, True]).reset_index(drop=True)


def concentracion_entidades(df: pd.DataFrame, participaciones=(50, 80)) -> dict:
    """Cuántas entidades reúnen cada porcentaje del valor adjudicado (sin atípicos) de df.

    Ordena las entidades de mayor a menor valor y acumula. Para cada porcentaje p devuelve el menor número de entidades
    cuyo valor acumulado llega a p % del total ('para_<p>'). La comparación es con enteros (pesos), sin redondeos.
    Devuelve también el total, el número de entidades con al menos un contrato, el valor de las 10 primeras y la curva
    acumulada (columnas 'entidades' y 'acumulado', en %) para dibujarla. Si el valor total es cero, no hay concentración
    que medir y se devuelve None.
    """
    por_entidad = df.groupby("id_entidad")["valor_total"].sum().sort_values(ascending=False, kind="stable")
    total = int(por_entidad.sum())
    if total == 0:
        return None
    valores = por_entidad.to_numpy(dtype=np.int64)
    acumulado = np.cumsum(valores)
    resultado = {
        "entidades": len(valores),
        "total": total,
        "top10_valor": int(valores[:10].sum()),
        # la entidad k hace falta si, sin ella, el acumulado todavía no llega al umbral
        **{f"para_{p}": int(((acumulado - valores) * 100 < p * total).sum()) for p in participaciones},
        "curva": pd.DataFrame({"entidades": np.arange(1, len(valores) + 1), "acumulado": 100 * acumulado / total}),
    }
    return resultado
