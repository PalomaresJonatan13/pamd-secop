"""Reglas de calidad sobre gold, compartidas por las tablas resumen (T1.4), el flujo en streaming (Punto 2) y el dashboard.

Gold conserva todos los contratos tal como vienen de SECOP II. Estas funciones no borran filas: unifican identificadores
y añaden marcas. Se aplican siempre en este orden:

    gold_marcado = marcar_atipicos(unificar_nit_entidad(gold), silver)

Las decisiones y sus cifras están en el notebook 04 (T1.5).
"""
from pyspark.sql import functions as F

UMBRAL_RAZON_PRECIO_BASE = 100    # valor adjudicado >= 100 veces el precio base: error de captura (típicamente x1.000)
UMBRAL_EXTREMO = 10**13           # diez billones de pesos: desde ahí la caída natural de la distribución desaparece
UMBRAL_EXTREMO_SIN_BASE = 10**12  # sin precio base utilizable no se puede comparar: se marca desde un billón


def unificar_nit_entidad(gold):
    """Unifica los id_entidad 'NIT:' de 10 dígitos que son otro NIT de 9 dígitos ya existente con el dígito de verificación pegado.

    Solo se unifican los que tienen un id de 9 dígitos existente; los demás ids de 10 dígitos se dejan como están.
    """
    ids9 = (
        gold.select("id_entidad").distinct()
        .filter(F.col("id_entidad").rlike(r"^NIT:\d{9}$"))
        .select(F.col("id_entidad").alias("_id9"))
    )
    return (
        gold.withColumn("_prefijo9", F.when(F.col("id_entidad").rlike(r"^NIT:\d{10}$"), F.substring("id_entidad", 1, 13)))
        .join(F.broadcast(ids9), F.col("_prefijo9") == F.col("_id9"), "left")
        .withColumn("id_entidad", F.coalesce(F.col("_id9"), F.col("id_entidad")))
        .drop("_prefijo9", "_id9")
    )


def marcar_atipicos(gold, silver):
    """Añade precio_base (de silver), razon_valor_precio_base y las marcas es_valor_cero, es_valor_inconsistente,
    es_valor_extremo y es_atipico (= inconsistente o extremo). No cambia el número de filas."""
    # si gold ya trajera alguna de estas columnas (de una versión anterior), se recalculan
    previas = ["precio_base", "razon_valor_precio_base", "es_valor_cero", "es_valor_inconsistente", "es_valor_extremo", "es_atipico"]
    gold = gold.drop(*[c for c in previas if c in gold.columns])
    base = (
        silver.filter(F.coalesce(F.col("adjudicado"), F.lit(False)))
        .select("id_del_proceso", "id_adjudicacion", "precio_base")
    )
    valor = F.col("valor_total_adjudicacion")
    # razón valor / precio base; nula si el precio base es <= 1 (valor de relleno) o el valor es 0
    razon = F.when((F.col("precio_base") > 1) & (valor > 0), valor.cast("double") / F.col("precio_base").cast("double"))
    return (
        gold.join(base, ["id_del_proceso", "id_adjudicacion"], "left")
        .withColumn("razon_valor_precio_base", razon)
        .withColumn("es_valor_cero", valor == 0)
        .withColumn("es_valor_inconsistente",
                    F.coalesce(F.col("razon_valor_precio_base") >= UMBRAL_RAZON_PRECIO_BASE, F.lit(False)))
        .withColumn("es_valor_extremo",
                    (valor > UMBRAL_EXTREMO) | ((valor > UMBRAL_EXTREMO_SIN_BASE) & F.col("razon_valor_precio_base").isNull()))
        .withColumn("es_atipico", F.col("es_valor_inconsistente") | F.col("es_valor_extremo"))
    )
