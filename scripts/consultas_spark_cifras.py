"""Cifras de referencia para las tarjetas y el gráfico mensual del dashboard (T4.3, T4.4 y T4.7), calculadas con Spark sobre gold.

No usa las tablas de consumo de dashboard/data/: parte de gold con las reglas de `src/pamd/calidad.py`. Para las mismas combinaciones
de filtros que `consultas_spark_rankings.py` calcula los totales de las tarjetas (contratos, atípicos, valor, entidades y contratistas
distintos) y la serie mensual de contratos y valor. Escribe dashboard/verificacion/cifras_spark.json, que
`scripts/comprobar_cifras.py` compara con el dashboard.

Ejecutar con el entorno levantado (tarda un par de minutos):
    docker exec spark python /home/jovyan/work/scripts/consultas_spark_cifras.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import functions as F

from consultas_spark_rankings import CASOS, SIN_DEPARTAMENTO  # mismas combinaciones de filtros que los rankings
from pamd.calidad import marcar_atipicos, unificar_nit_entidad
from pamd.config import GOLD_PARQUET, SILVER_PARQUET
from pamd.spark_session import get_spark

SALIDA = Path(__file__).resolve().parent.parent / "dashboard" / "verificacion" / "cifras_spark.json"


def main():
    spark = get_spark("cifras-referencia")
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
    valor_atipico = F.sum(F.when(F.col("es_atipico"), valor).otherwise(0)).cast("long")
    resultado = {"generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "casos": []}
    for caso in CASOS:
        filtrado = filtrar(contratos, caso)
        t = filtrado.agg(
            F.count("*").alias("contratos"),
            F.sum(F.col("es_atipico").cast("long")).alias("contratos_atipicos"),
            valor_normal.alias("valor_total"),
            valor_atipico.alias("valor_atipicos"),
            F.countDistinct("id_entidad").alias("entidades"),
            F.countDistinct("id_contratista").alias("contratistas"),
        ).first()
        mensual = (
            filtrado.groupBy("anio_mes").agg(F.count("*").alias("contratos"), valor_normal.alias("valor_total")).collect()
        )
        resultado["casos"].append({
            **caso,
            "totales": {k: int(t[k]) for k in ("contratos", "contratos_atipicos", "valor_total", "valor_atipicos", "entidades", "contratistas")},
            "mensual": {m["anio_mes"]: {"contratos": int(m["contratos"]), "valor_total": int(m["valor_total"])} for m in mensual},
        })
        print(f"{caso['nombre']}: {t['contratos']:,} contratos, {t['entidades']:,} entidades, {t['contratistas']:,} contratistas, {len(mensual)} meses")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("Escrito", SALIDA)


if __name__ == "__main__":
    main()
