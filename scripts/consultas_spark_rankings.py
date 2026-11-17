"""Tops de referencia para comprobar los rankings del dashboard (T4.5): consultas de Spark directamente sobre gold.

No usa las tablas de consumo de dashboard/data/: parte de gold con las reglas de calidad de `src/pamd/calidad.py` y agrupa por
entidad o contratista para cada combinación de filtros de CASOS. Escribe dashboard/verificacion/rankings_spark.json, que
`scripts/comprobar_rankings.py` compara con lo que muestra el dashboard.

Ejecutar con el entorno levantado (tarda un par de minutos):
    docker exec spark python /home/jovyan/work/scripts/consultas_spark_rankings.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import functions as F

from pamd.calidad import marcar_atipicos, unificar_nit_entidad
from pamd.config import GOLD_PARQUET, SILVER_PARQUET
from pamd.spark_session import get_spark

N = 10
SIN_DEPARTAMENTO = "SIN DEPARTAMENTO"
SALIDA = Path(__file__).resolve().parent.parent / "dashboard" / "verificacion" / "rankings_spark.json"

# Combinaciones de filtros: departamentos (vacío = todos), entidades (vacío = todas), mes desde y mes hasta ('AAAA-MM')
CASOS = [
    {"nombre": "sin filtros", "departamentos": [], "entidades": [], "desde": "2015-06", "hasta": "2026-09"},
    {"nombre": "Antioquia, 2020-2023", "departamentos": ["Antioquia"], "entidades": [], "desde": "2020-01", "hasta": "2023-12"},
    {"nombre": "Bogotá, 2022", "departamentos": ["Distrito Capital de Bogotá"], "entidades": [], "desde": "2022-01", "hasta": "2022-12"},
    {"nombre": "Valle del Cauca y Cundinamarca", "departamentos": ["Valle del Cauca", "Cundinamarca"], "entidades": [], "desde": "2015-06", "hasta": "2026-09"},
    {"nombre": "SIN DEPARTAMENTO", "departamentos": [SIN_DEPARTAMENTO], "entidades": [], "desde": "2015-06", "hasta": "2026-09"},
    {"nombre": "una entidad (SENA), 2019-2025", "departamentos": [], "entidades": ["NIT:899999034"], "desde": "2019-01", "hasta": "2025-12"},
    {"nombre": "primeros años, 2015-2017", "departamentos": [], "entidades": [], "desde": "2015-06", "hasta": "2017-12"},
]
RANKINGS = [("entidades", "id_entidad"), ("contratistas", "id_contratista")]
ORDENES = ["valor_total", "contratos"]


def main():
    spark = get_spark("rankings-referencia")
    spark.sparkContext.setLogLevel("ERROR")
    gold = spark.read.parquet(GOLD_PARQUET)
    silver = spark.read.parquet(SILVER_PARQUET)
    valor = F.col("valor_total_adjudicacion")
    contratos = (
        marcar_atipicos(unificar_nit_entidad(gold), silver)
        .withColumn("departamento", F.when(F.trim("departamento_entidad") != "", F.trim("departamento_entidad")).otherwise(F.lit(SIN_DEPARTAMENTO)))
        .persist(StorageLevel.MEMORY_AND_DISK)
    )
    print(f"Gold con marcas: {contratos.count():,} contratos")

    def filtrar(df, caso):
        condicion = (F.col("anio_mes") >= caso["desde"]) & (F.col("anio_mes") <= caso["hasta"])
        if caso["departamentos"]:
            condicion &= F.col("departamento").isin(caso["departamentos"])
        if caso["entidades"]:
            condicion &= F.col("id_entidad").isin(caso["entidades"])
        return df.filter(condicion)

    def agrupar(df, clave):
        return df.groupBy(clave).agg(
            F.count("*").alias("contratos"),
            F.sum(F.col("es_atipico").cast("long")).alias("contratos_atipicos"),
            F.sum(F.when(~F.col("es_atipico"), valor).otherwise(0)).cast("long").alias("valor_total"),
        )

    resultado = {"generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "n": N, "casos": []}
    for caso in CASOS:
        filtrado = filtrar(contratos, caso)
        totales = filtrado.agg(
            F.count("*").alias("contratos"),
            F.sum(F.when(~F.col("es_atipico"), valor).otherwise(0)).cast("long").alias("valor_total"),
        ).first()
        salida = {**caso, "totales": {"contratos": totales["contratos"], "valor_total": int(totales["valor_total"] or 0)}, "rankings": {}}
        for nombre, clave in RANKINGS:
            agrupado = agrupar(filtrado, clave).persist(StorageLevel.MEMORY_AND_DISK)
            for orden in ORDENES:
                filas = agrupado.orderBy(F.desc(orden), F.asc(clave)).limit(N).collect()
                salida["rankings"][f"{nombre}_por_{orden}"] = [
                    {"id": f[clave], "contratos": int(f["contratos"]), "contratos_atipicos": int(f["contratos_atipicos"]), "valor_total": int(f["valor_total"])}
                    for f in filas
                ]
            agrupado.unpersist()
        resultado["casos"].append(salida)
        print(f"{caso['nombre']}: {totales['contratos']:,} contratos")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("Escrito", SALIDA)


if __name__ == "__main__":
    main()
