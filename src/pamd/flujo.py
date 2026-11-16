"""Simulación del flujo continuo del Corte 3 (Punto 2): micro-lotes a partir de gold y su entrega a la carpeta de entrada.

La usan el notebook 05 (T2.2 a T2.6) y el 06 (T3.1 a T3.4), para que los dos simulen exactamente el mismo flujo.
Los parámetros (número de lotes, semilla, tardíos, tolerancia) se fijan en el notebook 05 (T2.1).
"""
from pyspark.sql import functions as F

from pamd.calidad import marcar_atipicos, unificar_nit_entidad

# Columnas que viajan en cada micro-lote: la clave de T1.1, el tiempo del evento, la dimensión de región y las medidas
COLUMNAS_FLUJO = [
    "id_del_proceso",
    "id_adjudicacion",
    "fecha_adjudicacion",
    "departamento_entidad",
    "valor_total_adjudicacion",
    "es_atipico",
    "es_valor_cero",
]


def base_del_flujo(gold, silver):
    """Gold con las marcas de calidad (misma regla que las tablas de T1.4), reducido a las columnas del flujo."""
    return marcar_atipicos(unificar_nit_entidad(gold), silver).select(*COLUMNAS_FLUJO)


def plan_de_lotes(base, num_lotes, tardios):
    """Reparte los meses en lotes regulares y decide qué mes alimenta cada lote tardío y cuándo llega.

    Los meses se recorren en orden y se asignan a un lote según los contratos acumulados, así que cada lote
    tiene meses completos y un número parecido de contratos. Devuelve el orden de llegada de los archivos:
    una lista de diccionarios con archivo, tipo, lote de origen, meses y, para los tardíos, el mes retenido.
    """
    meses = (
        base.groupBy(F.date_format("fecha_adjudicacion", "yyyy-MM").alias("anio_mes"))
        .count().orderBy("anio_mes").collect()
    )
    total = sum(r["count"] for r in meses)
    meses_por_lote, acumulado = {}, 0
    for r in meses:
        lote = min(num_lotes, acumulado * num_lotes // total + 1)
        meses_por_lote.setdefault(lote, []).append(r["anio_mes"])
        acumulado += r["count"]
    assert sorted(meses_por_lote) == list(range(1, num_lotes + 1)), "Algún lote regular quedó sin meses"

    orden = []
    for lote in range(1, num_lotes + 1):
        orden.append({"tipo": "regular", "lote_origen": lote, "meses": meses_por_lote[lote], "mes_retenido": None})
        for tipo, t in tardios.items():
            if t["llega_tras_lote"] == lote:
                mes = meses_por_lote[t["lote_origen"]][t["mes_en_lote"]]
                orden.append({"tipo": tipo, "lote_origen": t["lote_origen"], "meses": [mes], "mes_retenido": mes})
    for posicion, entrada in enumerate(orden, 1):
        entrada["archivo"] = f"lote_{posicion:02d}_{entrada['tipo']}"
    return orden


def asignar_lotes(base, orden, semilla, porcentaje_tardio):
    """Añade a cada contrato la columna 'archivo' con el lote en el que llega.

    Los tardíos se eligen con un hash de id_adjudicacion y la semilla, no con rand(): el resultado no depende de cómo
    Spark reparta los datos, así que la misma semilla da siempre los mismos lotes.
    """
    spark = base.sparkSession
    regular = [(m, e["archivo"]) for e in orden if e["tipo"] == "regular" for m in e["meses"]]
    mapa = spark.createDataFrame(regular, "anio_mes string, archivo_regular string")
    elegido = F.pmod(F.xxhash64("id_adjudicacion", F.lit(semilla)), F.lit(100)) < porcentaje_tardio
    archivo = F.col("archivo_regular")
    for e in reversed([e for e in orden if e["tipo"] != "regular"]):
        archivo = F.when((F.col("anio_mes") == e["mes_retenido"]) & elegido, F.lit(e["archivo"])).otherwise(archivo)
    return (
        base.withColumn("anio_mes", F.date_format("fecha_adjudicacion", "yyyy-MM"))
        .join(F.broadcast(mapa), "anio_mes")
        .withColumn("archivo", archivo)
        .drop("anio_mes", "archivo_regular")
    )


def huella_por_lote(df):
    """Filas y huella (suma de xxhash64 de cada fila) por archivo; dos ejecuciones dan los mismos lotes si coinciden."""
    columnas = [c for c in df.columns if c != "archivo"]
    return {
        r["archivo"]: (r["filas"], r["huella"])
        for r in df.groupBy("archivo").agg(
            F.count("*").alias("filas"),
            F.sum(F.xxhash64(*columnas).cast("decimal(38,0)")).alias("huella"),
        ).collect()
    }


def _fs(spark, ruta):
    jvm = spark._jvm
    camino = jvm.org.apache.hadoop.fs.Path(ruta)
    return camino.getFileSystem(spark._jsc.hadoopConfiguration()), camino


def entregar_lote(spark, origen, destino, archivo):
    """Copia el único Parquet del lote preparado a la carpeta de entrada del flujo, como <archivo>.parquet.

    En MinIO (S3) un objeto aparece completo o no aparece, así que el flujo nunca ve un archivo a medio copiar.
    """
    jvm = spark._jvm
    fs, _ = _fs(spark, origen)
    partes = fs.globStatus(jvm.org.apache.hadoop.fs.Path(f"{origen}/archivo={archivo}/part-*.parquet"))
    if partes is None or len(partes) != 1:
        raise RuntimeError(f"El lote {archivo} debe tener exactamente un archivo Parquet en {origen}")
    destino_archivo = jvm.org.apache.hadoop.fs.Path(f"{destino}/{archivo}.parquet")
    jvm.org.apache.hadoop.fs.FileUtil.copy(fs, partes[0].getPath(), fs, destino_archivo, False, spark._jsc.hadoopConfiguration())


def vaciar(spark, *rutas):
    """Borra por completo las carpetas indicadas (entrada, checkpoint, tardíos) para empezar una simulación limpia."""
    for ruta in rutas:
        fs, camino = _fs(spark, ruta)
        if fs.exists(camino):
            fs.delete(camino, True)


def crear_carpeta(spark, ruta):
    fs, camino = _fs(spark, ruta)
    fs.mkdirs(camino)


def existe(spark, ruta):
    fs, camino = _fs(spark, ruta)
    return bool(fs.exists(camino))


# --- Lectura y ventanas (T2.3 a T2.5) ---

# Esquema explícito de los micro-lotes: el flujo no lo infiere de los archivos que van llegando
ESQUEMA_FLUJO = (
    "id_del_proceso STRING, id_adjudicacion STRING, fecha_adjudicacion DATE, departamento_entidad STRING, "
    "valor_total_adjudicacion DECIMAL(20,2), es_atipico BOOLEAN, es_valor_cero BOOLEAN"
)


def leer_flujo(spark, entrada):
    """Flujo sobre la carpeta de entrada: un archivo (un lote) por disparo."""
    return spark.readStream.schema(ESQUEMA_FLUJO).option("maxFilesPerTrigger", 1).parquet(entrada)


def con_mes_y_departamento(df, sin_departamento):
    """Claves de la ventana: inicio del mes de adjudicación (marca de tiempo) y departamento de la entidad.

    Se usa igual en el flujo y en el cálculo por lotes de T2.6, para que las dos versiones agrupen exactamente igual.
    Los contratos sin departamento van a la misma categoría que en las tablas de T1.4.
    """
    departamento = F.trim("departamento_entidad")
    return (
        df.withColumn("mes", F.date_trunc("month", F.col("fecha_adjudicacion").cast("timestamp")))
        .withColumn("departamento", F.when(departamento != "", departamento).otherwise(F.lit(sin_departamento)))
    )


def medidas():
    """Las medidas de las tablas resumen de T1.4: los atípicos se cuentan y se suman aparte del valor normal."""
    normal = ~F.col("es_atipico")
    return [
        F.count("*").alias("contratos"),
        F.sum(F.when(~normal, 1).otherwise(0)).alias("contratos_atipicos"),
        F.sum(F.col("es_valor_cero").cast("int")).alias("contratos_valor_cero"),
        F.sum(F.when(normal, F.col("valor_total_adjudicacion")).otherwise(0)).alias("valor_total"),
        F.sum(F.when(~normal, F.col("valor_total_adjudicacion")).otherwise(0)).alias("valor_atipicos"),
    ]


CLAVES_VENTANA = ["mes", "departamento"]


def ventanas_mensuales(flujo, tolerancia, sin_departamento):
    """Agregación por mes calendario y departamento, con marca de agua sobre el inicio del mes."""
    return (
        con_mes_y_departamento(flujo, sin_departamento)
        .withWatermark("mes", tolerancia)
        .groupBy(*CLAVES_VENTANA)
        .agg(*medidas())
    )


def agregar_por_lotes(df, sin_departamento):
    """La misma agregación que el flujo, como consulta normal (sin marca de agua)."""
    return con_mes_y_departamento(df, sin_departamento).groupBy(*CLAVES_VENTANA).agg(*medidas())


class TablaEnMemoria:
    """Destino de T2: guarda en el driver la última versión de cada ventana.

    En modo update cada micro-lote trae solo las ventanas que cambiaron, con su valor acumulado; guardar() reemplaza
    esas ventanas y deja las demás como estaban. El destino idempotente en MinIO (T3.2) sustituye esta clase.
    """

    def __init__(self):
        self.filas = {}
        self.esquema = None
        self.lotes = []

    def guardar(self, df, batch_id):
        if self.esquema is None:
            self.esquema = df.schema
        cambiadas = df.collect()
        for fila in cambiadas:
            self.filas[tuple(fila[c] for c in CLAVES_VENTANA)] = fila
        self.lotes.append((batch_id, len(cambiadas)))

    def copia(self):
        return dict(self.filas)

    def como_dataframe(self, spark):
        return spark.createDataFrame(list(self.filas.values()), self.esquema)


def registrar_tardios(spark, entrada, archivo, marca_de_agua, destino, sin_departamento):
    """Guarda aparte las filas de un lote que Spark descartó por llegar después de la marca de agua.

    Son las filas cuyo mes empieza antes de la marca de agua con la que se procesó el lote. Se escriben en
    <destino>/archivo=<lote> sobrescribiendo, así que registrar dos veces el mismo lote no las duplica.
    """
    filas = (
        con_mes_y_departamento(spark.read.schema(ESQUEMA_FLUJO).parquet(f"{entrada}/{archivo}.parquet"), sin_departamento)
        .filter(F.col("mes") < F.to_timestamp(F.lit(marca_de_agua)))
        .drop("mes", "departamento")
    )
    n = filas.count()
    if n:
        filas.write.mode("overwrite").parquet(f"{destino}/archivo={archivo}")
    return n


def archivos_por_disparo(spark, checkpoint):
    """Qué archivo leyó cada disparo, según lo que Spark guarda en el checkpoint.

    sources/0 numera los archivos en el orden en que la fuente los encontró (logOffset) y offsets/<disparo> guarda
    hasta qué logOffset llegó cada disparo. Un disparo sin datos repite el logOffset del anterior.
    """
    fuente = (
        spark.read.text(f"{checkpoint}/sources/0")
        .filter(F.col("value").startswith("{"))
        .select(
            F.get_json_object("value", "$.path").alias("ruta"),
            F.get_json_object("value", "$.batchId").cast("long").alias("log_offset"),
        )
        .distinct()
    )
    offsets = (
        spark.read.text(f"{checkpoint}/offsets")
        .filter(F.col("value").contains("logOffset"))
        .select(
            F.regexp_extract(F.input_file_name(), r"/(\d+)$", 1).cast("long").alias("disparo"),
            F.get_json_object("value", "$.logOffset").cast("long").alias("log_offset"),
        )
    )
    return {
        r["disparo"]: r["ruta"].rsplit("/", 1)[-1].replace(".parquet", "")
        for r in offsets.join(fuente, "log_offset").collect()
    }
