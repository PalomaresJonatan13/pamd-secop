"""Rutas de almacenamiento en MinIO (bucket `rawdata`), compartidas por todos los notebooks."""

INPUT_CSV = "s3a://rawdata/secop/"
BRONZE_PARQUET_UNPARTITIONED = "s3a://rawdata/bronze/secop/contratos"
BRONZE_PARQUET = "s3a://rawdata/bronze/secop/contratos_particionado"
QUARANTINE_PARQUET = "s3a://rawdata/cuarentena/secop"

WRITE_MODE = "overwrite"
OUTPUT_PARTITIONS = 36
