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
        .config(
            "spark.jars.packages",
            "org.apache.hadoop:hadoop-aws:3.3.4,"
            "com.amazonaws:aws-java-sdk-bundle:1.12.262",
        )
        .getOrCreate()
    )

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
