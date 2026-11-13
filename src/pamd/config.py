"""Rutas de almacenamiento en MinIO (bucket `rawdata`), compartidas por todos los notebooks."""

INPUT_CSV = "s3a://rawdata/secop/"
STAGING_PARQUET = "s3a://rawdata/staging/secop/con_calidad"
BRONZE_PARQUET_UNPARTITIONED = "s3a://rawdata/bronze/secop/contratos"
BRONZE_PARQUET = "s3a://rawdata/bronze/secop/contratos_particionado"
QUARANTINE_PARQUET = "s3a://rawdata/cuarentena/secop"

# Corte 3, Punto 1 (notebook 04)
SILVER_PARQUET = "s3a://rawdata/silver/secop/contratos"
SILVER_DESCARTADOS_PARQUET = "s3a://rawdata/silver/secop/descartados"
GOLD_PARQUET = "s3a://rawdata/gold/secop/adjudicaciones"
GOLD_EXCLUIDOS_PARQUET = "s3a://rawdata/gold/secop/excluidos"

WRITE_MODE = "overwrite"
OUTPUT_PARTITIONS = 36
