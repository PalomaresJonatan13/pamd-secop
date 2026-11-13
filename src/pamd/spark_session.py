"""Sesión de Spark conectada a MinIO por S3A.

Las credenciales se leen de variables de entorno (ver `.env.example`); no se escriben en el código.
"""

import os

from pyspark.sql import SparkSession

try:  # fuera de Docker, permite leer un archivo .env local
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _variable_requerida(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(
            f"Falta la variable de entorno {nombre}. "
            "Copia .env.example como .env y completa los valores."
        )
    return valor


def get_spark(app_name: str = "PAMD-SECOP") -> SparkSession:
    """Crea (o reutiliza) la sesión de Spark y configura el conector S3A hacia MinIO."""
    endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
    access_key = _variable_requerida("MINIO_ACCESS_KEY")
    secret_key = _variable_requerida("MINIO_SECRET_KEY")

    spark = (
        SparkSession.builder
        .appName(app_name)
        # local[N,F]: N núcleos y hasta F intentos por tarea. En modo local Spark no reintenta una
        # tarea fallida salvo que se indique F; sin reintentos, un error pasajero del almacenamiento
        # (por ejemplo `IncompleteBody` al confirmar archivos en MinIO) aborta toda la escritura.
        # En equipos con poca memoria conviene SPARK_MASTER=local[2,4] en .env.
        .master(os.environ.get("SPARK_MASTER", "local[*,4]"))
        .config(
            "spark.jars.packages",
            "org.apache.hadoop:hadoop-aws:3.3.4,"
            "com.amazonaws:aws-java-sdk-bundle:1.12.262",
        )
        # Sin poda de columnas, el lector CSV revisa todas las columnas de cada registro. Con la
        # poda activa, un conteo no detecta los registros mal formados en las columnas que no usa
        # y da cifras distintas a las de la escritura.
        .config("spark.sql.csv.parser.columnPruning.enabled", "false")
        # En modo local el ejecutor es el propio proceso del driver, y por defecto Spark le da solo
        # 1 GB de heap. Con registros anchos (decenas de columnas, algunas con texto largo) los 8
        # escritores de Parquet en paralelo agotan ese heap (OutOfMemoryError: Java heap space).
        # Solo tiene efecto si esta llamada es la que inicia la JVM (kernel nuevo o proceso nuevo).
        .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "5g"))
        # Grupos de filas de 64 MB (por defecto 128 MB) para reducir la memoria por escritor.
        .config("spark.hadoop.parquet.block.size", str(64 * 1024 * 1024))
        # El Parquet intermedio guarda las fechas tal como vienen del CSV, y algunas son anteriores
        # a 1900 (errores de captura). Spark 3 se niega a escribirlas por la diferencia entre los
        # calendarios juliano y gregoriano (SPARK-31404). CORRECTED las guarda tal cual; es seguro
        # porque Spark también las lee en calendario gregoriano y el bronze las convierte en nulo.
        .config("spark.sql.parquet.int96RebaseModeInWrite", "CORRECTED")
        .config("spark.sql.parquet.datetimeRebaseModeInWrite", "CORRECTED")
        .config("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED")
        .config("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")
        .getOrCreate()
    )
    spark.conf.set("spark.sql.csv.parser.columnPruning.enabled", "false")

    hadoop_conf = spark.sparkContext._jsc.hadoopConfiguration()
    hadoop_conf.set("fs.s3a.endpoint", endpoint)
    hadoop_conf.set("fs.s3a.access.key", access_key)
    hadoop_conf.set("fs.s3a.secret.key", secret_key)
    hadoop_conf.set(
        "fs.s3a.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
    )
    hadoop_conf.set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    hadoop_conf.set("fs.s3a.path.style.access", "true")
    hadoop_conf.set(
        "fs.s3a.connection.ssl.enabled", str(endpoint.startswith("https")).lower()
    )
    return spark
