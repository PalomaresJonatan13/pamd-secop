"""Simulación del flujo continuo del Corte 3 (Punto 2): micro-lotes a partir de gold y su entrega a la carpeta de entrada.

La usan el notebook 05 (T2.2 a T2.6) y el 06 (T3.1 a T3.4), para que los dos simulen exactamente el mismo flujo.
Los parámetros (número de lotes, semilla, tardíos, tolerancia) se fijan en el notebook 05 (T2.1).
"""
from pyspark.sql import Window, functions as F

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


def entregar_lote(spark, origen, destino, archivo, nombre=None):
    """Copia el único Parquet del lote preparado a la carpeta de entrada del flujo, como <archivo>.parquet.

    En MinIO (S3) un objeto aparece completo o no aparece, así que el flujo nunca ve un archivo a medio copiar.
    Con 'nombre' el archivo se deja con otro nombre (<nombre>.parquet): sirve para volver a depositar un lote
    ya procesado como si fuera un archivo nuevo (T3.3).
    """
    jvm = spark._jvm
    fs, _ = _fs(spark, origen)
    partes = fs.globStatus(jvm.org.apache.hadoop.fs.Path(f"{origen}/archivo={archivo}/part-*.parquet"))
    if partes is None or len(partes) != 1:
        raise RuntimeError(f"El lote {archivo} debe tener exactamente un archivo Parquet en {origen}")
    destino_archivo = jvm.org.apache.hadoop.fs.Path(f"{destino}/{nombre or archivo}.parquet")
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
    esas ventanas y deja las demás como estaban. Vive en la memoria del driver, así que se pierde si el proceso
    se cae; el destino idempotente en MinIO es DestinoVentanas (T3.2).
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


# --- Punto de control y reinicio (T3.1) ---

def lotes_preparados(spark, origen):
    """Nombres de los lotes escritos en T2.2, en orden de llegada (el nombre empieza con la posición)."""
    fs, camino = _fs(spark, origen)
    nombres = [e.getPath().getName() for e in fs.listStatus(camino) if e.isDirectory()]
    return sorted(n.split("=", 1)[1] for n in nombres if n.startswith("archivo="))


def contenido_checkpoint(spark, checkpoint):
    """Archivos del checkpoint (ruta relativa y tamaño), sin los .crc de control."""
    fs, camino = _fs(spark, checkpoint)
    base = fs.makeQualified(camino).toString().rstrip("/") + "/"
    archivos, it = [], fs.listFiles(camino, True)
    while it.hasNext():
        estado = it.next()
        ruta = estado.getPath().toString()
        if not estado.getPath().getName().endswith(".crc"):
            archivos.append((ruta[len(base):] if ruta.startswith(base) else ruta, estado.getLen()))
    return sorted(archivos)


def leer_texto(spark, ruta):
    """Contenido de un archivo pequeño del checkpoint (offsets, commits, metadata)."""
    fs, camino = _fs(spark, ruta)
    entrada = fs.open(camino)
    lector = spark._jvm.java.io.BufferedReader(spark._jvm.java.io.InputStreamReader(entrada, "UTF-8"))
    lineas, linea = [], lector.readLine()
    while linea is not None:
        lineas.append(linea)
        linea = lector.readLine()
    lector.close()
    return lineas


def copiar_carpeta(spark, origen, destino):
    """Copia una carpeta completa (por ejemplo, el checkpoint) para probar cambios sin tocar el original."""
    fs, src = _fs(spark, origen)
    _, dst = _fs(spark, destino)
    spark._jvm.org.apache.hadoop.fs.FileUtil.copy(fs, src, fs, dst, False, spark._jsc.hadoopConfiguration())


# --- Deduplicación dentro del flujo (T3.3) ---

# La clave natural elegida en T1.1: una fila de gold por proceso y adjudicación
CLAVE_CONTRATO = ["id_del_proceso", "id_adjudicacion"]


def ventanas_mensuales_sin_repetidos(flujo, tolerancia, sin_departamento):
    """La agregación de ventanas_mensuales, descartando antes los contratos que ya pasaron por el flujo.

    dropDuplicates guarda en el estado la clave de cada contrato visto y descarta las filas que la repiten, vengan
    en el mismo archivo o en otro. 'mes' entra en la clave para que la marca de agua pueda liberar ese estado: las
    claves de un mes se olvidan cuando el mes queda por debajo de la marca de agua. Un repetido de un mes ya
    olvidado tampoco se cuenta, porque llega por debajo de la marca de agua y se descarta por tardío.

    Es otra consulta para Spark (un operador con estado más), así que necesita su propio checkpoint.
    """
    return (
        con_mes_y_departamento(flujo, sin_departamento)
        .withWatermark("mes", tolerancia)
        .dropDuplicates([*CLAVE_CONTRATO, "mes"])
        .groupBy(*CLAVES_VENTANA)
        .agg(*medidas())
    )


# --- Destino idempotente (T3.2) ---

class DestinoVentanas:
    """Destino de T3.2: la tabla de ventanas en MinIO, escrita de forma que repetir un micro-lote no cambie nada.

    En modo update cada micro-lote trae solo las ventanas que cambiaron, con su valor acumulado. guardar() hace
    dos escrituras, y las dos reemplazan en vez de añadir:

    1. <ruta>/cambios/batch_id=<N>: las ventanas del micro-lote N. La carpeta se sobrescribe entera, así que
       guardar otra vez el micro-lote N deja el mismo contenido.
    2. <ruta>/tabla/anio_mes=<mes>: la tabla que se consulta. Para cada mes tocado por el micro-lote se toma, de
       todos los cambios hasta N, la última versión de cada ventana y se sobrescribe la partición del mes
       (sobrescritura dinámica: los meses que el micro-lote no toca quedan como estaban).

    La tabla se reconstruye siempre a partir de los cambios, nunca a partir de sí misma. Por eso, si el proceso
    se cae a mitad de una escritura, basta con que Spark repita el micro-lote (lo hace solo, porque no quedó
    confirmado en el checkpoint): el paso 1 reescribe la misma carpeta y el paso 2 rehace completos los meses
    afectados, incluidas las ventanas que ese micro-lote no traía.
    """

    def __init__(self, spark, ruta):
        self.spark = spark
        self.cambios = f"{ruta}/cambios"
        self.tabla = f"{ruta}/tabla"
        self.lotes = []

    def guardar(self, df, batch_id):
        df.persist()
        try:
            n = df.count()
            self.lotes.append((batch_id, n))
            if n == 0:
                return  # un disparo sin ventanas cambiadas no escribe nada
            df.coalesce(1).write.mode("overwrite").parquet(f"{self.cambios}/batch_id={batch_id}")

            meses = df.select("mes").distinct()
            ultima_primero = Window.partitionBy(*CLAVES_VENTANA).orderBy(F.col("batch_id").desc())
            (
                self.spark.read.parquet(self.cambios)
                .filter(F.col("batch_id") <= batch_id)
                .join(F.broadcast(meses), "mes", "left_semi")
                .withColumn("_orden", F.row_number().over(ultima_primero))
                .filter("_orden = 1")
                .select(*df.columns, F.date_format("mes", "yyyy-MM").alias("anio_mes"))
                .repartition("anio_mes")  # un archivo por mes
                .write.mode("overwrite").option("partitionOverwriteMode", "dynamic")
                .partitionBy("anio_mes").parquet(self.tabla)
            )
        finally:
            df.unpersist()

    def leer(self):
        """La tabla de ventanas tal como está en MinIO (una fila por mes y departamento)."""
        return self.spark.read.parquet(self.tabla).drop("anio_mes")
