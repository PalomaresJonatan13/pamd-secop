"""Revisa la cuarentena sin usar Spark (poca memoria; se puede ejecutar mientras corre otro notebook).

Lee solo unas pocas columnas del Parquet de cuarentena en MinIO con pyarrow y muestra, para cada
motivo de rechazo elegido, los valores originales más frecuentes que no pasaron la validación.

Uso (desde la carpeta del repositorio, con el contenedor `spark` en marcha):

    docker exec spark python /home/jovyan/work/scripts/revisar_cuarentena.py
"""

import os
import sys
from urllib.parse import urlparse

try:
    import pyarrow.dataset as ds
    import pyarrow.fs as pafs
except ImportError:
    sys.exit("Falta pyarrow en este entorno. Usa la versión con Spark desde un notebook.")

RUTA = "rawdata/cuarentena/secop"  # bucket/prefijo (equivale a QUARANTINE_PARQUET)

# (motivo de rechazo, columna con el valor original)
REVISIONES = [
    ("proveedores_invitados_invalido", "_raw_proveedores_invitados"),
    ("duracion_invalido", "_raw_duracion"),
    ("nit_entidad_invalido", "_raw_nit_entidad"),
    ("codigo_pci_invalido", "_raw_codigo_pci"),
    ("precio_base_negativo", "_raw_precio_base"),
]
TOP = 15


def sistema_de_archivos():
    endpoint = urlparse(os.environ.get("MINIO_ENDPOINT", "http://minio:9000"))
    return pafs.S3FileSystem(
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        endpoint_override=endpoint.netloc,
        scheme=endpoint.scheme or "http",
        region="us-east-1",
    )


def clasificar(valores):
    """Agrupa los valores originales según su forma, para ver si son recuperables."""
    formas = [
        ("miles con punto (1.398)", r"^\d{1,3}(\.\d{3})+$"),
        ("miles con coma (1,398)", r"^\d{1,3}(,\d{3})+$"),
        ("con dígito de verificación (860.524.654-1)", r"^[\d.]+-\d$"),
        ("decimal de 1 o 2 cifras (5.0, 12,5)", r"^\d+[.,]\d{1,2}$"),
        ("vacío o nulo", r"^(<nulo>)?$"),
    ]
    resultado = valores.copy()
    resultado[:] = "otro (texto u otro formato)"
    asignado = valores.astype(bool) & False
    for nombre, patron in formas:
        coincide = valores.str.match(patron) & ~asignado
        resultado[coincide] = nombre
        asignado = asignado | coincide
    return resultado


def main():
    columnas = ["motivos_rechazo"] + sorted({c for _, c in REVISIONES})
    dataset = ds.dataset(RUTA, filesystem=sistema_de_archivos(), format="parquet")
    existentes = set(dataset.schema.names)
    faltan = [c for c in columnas if c not in existentes]
    if faltan:
        sys.exit(f"La cuarentena no tiene estas columnas: {faltan}")

    df = dataset.to_table(columns=columnas).to_pandas()
    df["motivos"] = df["motivos_rechazo"].apply(list)
    df["n_motivos"] = df["motivos"].apply(len)
    print(f"Filas en cuarentena: {len(df):,}\n")
    print("Cantidad de motivos por fila:")
    print(df["n_motivos"].value_counts().sort_index().to_string(), "\n")

    for motivo, columna in REVISIONES:
        filas = df[df["motivos"].apply(lambda m: motivo in m)]
        solo_este = int((filas["n_motivos"] == 1).sum())
        print("=" * 78)
        print(f"{motivo}: {len(filas):,} filas ({solo_este:,} tienen solo este motivo)")
        valores = filas[columna].fillna("<nulo>").astype(str).str.slice(0, 60)
        print(f"Valores originales distintos: {valores.nunique():,}. Más frecuentes:")
        print(valores.value_counts().head(TOP).to_string())
        print("Forma de los valores (sobre todas las filas de este motivo):")
        print(clasificar(valores).value_counts().to_string(), "\n")


if __name__ == "__main__":
    main()
