"""Cifras de referencia para comprobar el módulo geográfico y de concentración del dashboard (T4.6), calculadas con Spark sobre gold.

No usa las tablas de consumo de dashboard/data/: parte de gold con las reglas de `src/pamd/calidad.py`. Para las mismas combinaciones
de filtros que `consultas_spark_rankings.py` calcula el valor por departamento y la concentración del valor en las entidades
(cuántas entidades reúnen el 50 % y el 80 %, y cuánto suman las 10 primeras; el acumulado se hace con una función de ventana).
Escribe dashboard/verificacion/geografia_spark.json, que `scripts/comprobar_geografia.py` compara con el dashboard.

Ejecutar con el entorno levantado (tarda un par de minutos):
    docker exec spark python /home/jovyan/work/scripts/consultas_spark_geografia.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import Window, functions as F

from consultas_spark_rankings import CASOS, SIN_DEPARTAMENTO  # mismas combinaciones de filtros que los rankings
from pamd.calidad import marcar_atipicos, unificar_nit_entidad
from pamd.config import GOLD_PARQUET, SILVER_PARQUET
from pamd.spark_session import get_spark

SALIDA = Path(__file__).resolve().parent.parent / "dashboard" / "verificacion" / "geografia_spark.json"
PARTICIPACIONES = (50, 80)


def main():
    spark = get_spark("geografia-referencia")
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

    valor_normal = F.sum(F.when(~F.col("es_atipico"), valor).otherwise(0)).cast("long")
    resultado = {"generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "casos": []}
    for caso in CASOS:
        filtrado = filtrar(contratos, caso)

        totales = filtrado.agg(F.count("*").alias("contratos"), valor_normal.alias("valor_total")).first()
        por_depto = (
            filtrado.groupBy("departamento")
            .agg(F.count("*").alias("contratos"), F.sum(F.col("es_atipico").cast("long")).alias("contratos_atipicos"), valor_normal.alias("valor_total"))
            .collect()
        )

        # Concentración: entidades de mayor a menor valor, valor acumulado con una ventana y umbral con enteros (pesos)
        por_entidad = filtrado.groupBy("id_entidad").agg(valor_normal.alias("valor_total"))
        orden = Window.orderBy(F.desc("valor_total"), F.asc("id_entidad"))
        acumulado = por_entidad.withColumn("acumulado", F.sum("valor_total").over(orden.rowsBetween(Window.unboundedPreceding, Window.currentRow)))
        acumulado = acumulado.withColumn("antes", F.col("acumulado") - F.col("valor_total")).persist(StorageLevel.MEMORY_AND_DISK)
        total = int(totales["valor_total"])
        concentracion = {
            "entidades": acumulado.count(),
            "total": total,
            "top10_valor": int(acumulado.orderBy(F.desc("valor_total"), F.asc("id_entidad")).limit(10).agg(F.sum("valor_total")).first()[0]),
            # la entidad k hace falta si, sin ella, el acumulado todavía no llega al umbral
            **{f"para_{p}": acumulado.filter(F.col("antes") * 100 < p * total).count() for p in PARTICIPACIONES},
        }
        acumulado.unpersist()

        resultado["casos"].append({
            **caso,
            "totales": {"contratos": int(totales["contratos"]), "valor_total": total},
            "por_departamento": {
                f["departamento"]: {"contratos": int(f["contratos"]), "contratos_atipicos": int(f["contratos_atipicos"]), "valor_total": int(f["valor_total"])}
                for f in por_depto
            },
            "concentracion": concentracion,
        })
        print(f"{caso['nombre']}: {len(por_depto)} departamentos; 50 % = {concentracion['para_50']} de {concentracion['entidades']} entidades")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("Escrito", SALIDA)


if __name__ == "__main__":
    main()
