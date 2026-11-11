# Observatorio de Contratación Pública – SECOP II

Proyecto integrador de *Procesamiento para el Análisis Masivo de Datos* (Escuela Colombiana de Ingeniería Julio Garavito). Procesa los contratos de SECOP II con Spark y MinIO, y construye un dashboard para ver dónde se concentra el gasto público, quiénes son los mayores contratistas y cómo varía la contratación en el tiempo.

Autores: Gabriel Rodríguez y Jonatan Palomares.

Repositorio: https://github.com/PalomaresJonatan13/pamd-secop

## Estructura

```
.
├── docker-compose.yml        MinIO + JupyterLab con Spark 3.5.1 (servicio `spark`)
├── .env.example              plantilla de variables (copiar como .env)
├── requirements.txt          dependencias para ejecutar sin Docker
├── src/pamd/                 código compartido (rutas y sesión de Spark)
├── notebooks/                notebooks numerados en orden de ejecución
├── data/                     instrucciones para obtener el CSV (los datos no se versionan)
├── dashboard/                Punto 4 del Corte 3
├── report/                   informe técnico
├── presentation/             presentación ejecutiva
└── docs/                     plan de subtareas
```

## Puesta en marcha

Requisitos: Docker con Docker Compose, y unos 8 GB de memoria asignados a Docker (el notebook original se ejecutó con 7,6 GB).

1. Clona el repositorio y entra a la carpeta.
2. Copia `.env.example` como `.env` y completa `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (mínimo 8 caracteres) y `JUPYTER_TOKEN`.
3. Levanta el entorno: `docker compose up -d`. Esto inicia MinIO, crea el bucket `rawdata` y abre JupyterLab (servicio `spark`).
4. Sube el CSV de SECOP II a `rawdata/secop/` (ver `data/README.md`).
5. Abre JupyterLab en http://localhost:8888 con tu token y ejecuta los notebooks en orden.

Otros accesos: consola de MinIO en http://localhost:9002 y Spark UI en http://localhost:4040 mientras corre un trabajo.

## Notebooks

Cada notebook empieza con una celda de configuración que importa `pamd.config` (rutas) y `pamd.spark_session.get_spark()` (Spark + MinIO con las credenciales del `.env`).

| Notebook | Corte | Contenido | Estado |
|---|---|---|---|
| `01_corte1_bronze_y_almacenamiento.ipynb` | 1 | Lectura, limpieza y capa bronze en Parquet; comparación de CSV, Parquet y Parquet particionado | Existente |
| `02_corte2_shuffle_y_sesgo.ipynb` | 2 | `groupByKey` frente a `reduceByKey`, volumen de shuffle y sesgo de datos | Existente |
| `03_corte2_pagerank.ipynb` | 2 | PageRank entidad → contratista | Existente |
| `04_corte3_silver_gold.ipynb` | 3 – Punto 1 | Deduplicación, silver, gold y tablas resumen | Por hacer |
| `05_corte3_streaming_ventanas.ipynb` | 3 – Punto 2 | Micro-lotes, Structured Streaming y ventanas | Por hacer |
| `06_corte3_resiliencia_idempotencia.ipynb` | 3 – Punto 3 | Checkpoint, destino idempotente y pruebas de fallo | Por hacer |

El notebook original (cortes 1 y 2) se dividió en los tres primeros, conservando el código y las salidas. Los notebooks 02 y 03 leen el bronze ya escrito en MinIO, así que el 01 debe ejecutarse antes (con las celdas de escritura activas, ver Pendientes).

## Capas de datos en MinIO

```
s3a://rawdata/
├── secop/                                CSV original
├── bronze/secop/contratos                Parquet sin particionar
├── bronze/secop/contratos_particionado   Parquet por año y departamento
├── cuarentena/secop                      registros rechazados
├── procesado/                            tablas resumen
├── silver/                               (Corte 3) sin duplicados
└── gold/                                 (Corte 3) adjudicaciones
```

## Trabajo en equipo

- El plan de subtareas está en `docs/plan_de_subtareas.pdf`. Cada tarea tiene un ID (T0.1, T1.2…); úsalo en los mensajes de commit y en los nombres de rama, por ejemplo `t0.2-credenciales`.
- Trabaja en una rama por tarea y une a `main` con pull request.
- Dos personas no deben editar el mismo notebook a la vez: un `.ipynb` es un JSON y se resuelve mal al unir cambios. La división por notebooks existe para evitarlo.
- No subas `.env`, claves ni datos. Si una clave se sube por error, hay que cambiarla; borrarla del archivo no basta.

## Pendientes conocidos

- **T0.4:** las celdas que escriben el bronze (notebook 01) siguen comentadas. Falta el parámetro que las activa y probar desde un MinIO vacío.
- **T0.2:** las credenciales salen de variables de entorno. Falta comprobar que el notebook 01 funciona leyendo el `.env`.
- **Versiones:** `minio/minio` y `minio/mc` no tienen versión fija (como en el compose original). Fijarlas a la versión que usa el equipo (`docker exec minio minio --version`). La imagen de Spark es `x86_64-...`, así que no corre en equipos con procesador ARM (por ejemplo, Mac con chip Apple).
- **T0.3:** las cifras escritas a mano en las conclusiones de los notebooks 01 y 02 no coinciden con las salidas de sus celdas.
