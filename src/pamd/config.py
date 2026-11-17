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

# Corte 3, Punto 1: tablas resumen (T1.4). `procesado/` ya guarda tablas del Corte 1 (precio_base_*); no se pisan.
PROCESADO_ENTIDAD_PARQUET = "s3a://rawdata/procesado/adjudicaciones_por_entidad"
PROCESADO_CONTRATISTA_PARQUET = "s3a://rawdata/procesado/adjudicaciones_por_contratista"
PROCESADO_DEPARTAMENTO_PARQUET = "s3a://rawdata/procesado/adjudicaciones_por_departamento"
PROCESADO_MES_PARQUET = "s3a://rawdata/procesado/adjudicaciones_por_mes"

# Corte 3, Punto 2: flujo continuo (notebook 05)
STREAMING_LOTES = "s3a://rawdata/streaming/lotes"                       # micro-lotes preparados (T2.2)
STREAMING_ENTRADA = "s3a://rawdata/streaming/entrada"                   # carpeta que lee el flujo; los lotes llegan aquí uno a uno
STREAMING_TARDIOS = "s3a://rawdata/streaming/tardios"                   # registros que llegaron fuera de la tolerancia (T2.5)
STREAMING_CHECKPOINT = "s3a://rawdata/streaming/checkpoint/ventanas"    # punto de control del flujo (T3.1)
STREAMING_VENTANAS = "s3a://rawdata/streaming/ventanas"                 # destino idempotente: cambios/ por micro-lote y tabla/ por mes (T3.2)
STREAMING_CHECKPOINT_SIN_REPETIDOS = "s3a://rawdata/streaming/checkpoint/ventanas_sin_repetidos"  # consulta con deduplicación (T3.3)

WRITE_MODE = "overwrite"
OUTPUT_PARTITIONS = 36

# Corte 3, Punto 4: tablas de consumo del dashboard (notebook 07, T4.1). Se exportan también a dashboard/data/.
DASHBOARD_SERIE_PARQUET = "s3a://rawdata/procesado/dashboard/serie_mensual"                    # mes x departamento x entidad
DASHBOARD_CONTRATISTAS_MES_PARQUET = "s3a://rawdata/procesado/dashboard/contratistas_mensual"  # mes x departamento x entidad x contratista
DASHBOARD_ENTIDADES_PARQUET = "s3a://rawdata/procesado/dashboard/entidades"                    # nombre de cada entidad
DASHBOARD_CONTRATISTAS_PARQUET = "s3a://rawdata/procesado/dashboard/contratistas"              # nombre de cada contratista
DASHBOARD_VENTANAS_PARQUET = "s3a://rawdata/procesado/dashboard/ventanas_flujo"                # ventanas del flujo (mes x departamento)
