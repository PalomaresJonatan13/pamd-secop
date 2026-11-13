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
├── scripts/                  utilidades (revisión de la cuarentena sin Spark)
├── data/                     instrucciones para obtener el CSV (los datos no se versionan)
├── dashboard/                Punto 4 del Corte 3
├── report/                   informe técnico
├── presentation/             presentación ejecutiva
└── docs/                     plan de subtareas
```

## Puesta en marcha

Probado el 11 de noviembre de 2026 en Windows con Docker Desktop y PowerShell, partiendo de un clon limpio y de los datos en Drive.

### Requisitos
- **Git** y **Docker Desktop** (abierto, con el motor corriendo). Comprueba con `git --version` y `docker compose version`.
- **Memoria:** unos 8 GB asignados a Docker (la ejecución de referencia usó 7,6 GB). Se cambia en Docker Desktop, Settings → Resources. Spark usa 5 GB de heap (`SPARK_DRIVER_MEMORY` en `src/pamd/spark_session.py`); con el 1 GB por defecto la escritura del Parquet falla por falta de memoria.
  - **Equipos con 8 GB de RAM en total.** Docker Desktop no tiene control de memoria con WSL 2: se fija en `%UserProfile%\.wslconfig` (`[wsl2]`, `memory=5GB`, `swap=4GB`) y se aplica con `wsl --shutdown` y reiniciando Docker Desktop. Con 6 GB Windows se queda sin memoria y el motor de Docker deja de responder. En el `.env` añade `SPARK_DRIVER_MEMORY=2g` y `SPARK_MASTER=local[2,4]`. Así se reconstruyó el bronze completo el 13-nov-2026 (ver *Pendientes conocidos*). Mientras Spark trabaja, cierra las demás aplicaciones y desactiva la suspensión del equipo.
- **Disco:** varias decenas de GB libres. El `.zip` pesa unos 1,7 GB, el CSV descomprimido varios más, y el almacenamiento guarda una copia del CSV y del bronze.
- **Procesador x86-64.** La imagen de Spark no corre en equipos ARM (por ejemplo, Mac con chip Apple).
- **Internet** la primera vez, para descargar las imágenes de Docker y los conectores de Spark.

### Pasos

1. **Clonar:**
   ```
   git clone https://github.com/PalomaresJonatan13/pamd-secop
   cd pamd-secop
   ```
2. **Crear el `.env`** (las claves y el token los inventas tú; no vienen de ningún sitio):
   ```
   copy .env.example .env
   notepad .env
   ```
   Completa `MINIO_ACCESS_KEY` (por ejemplo `admin`), `MINIO_SECRET_KEY` (mínimo 8 caracteres) y `JUPYTER_TOKEN` (cualquier texto largo sin espacios; sirve como contraseña de JupyterLab). Deja `MINIO_ENDPOINT` como está.
3. **Levantar el entorno:**
   ```
   docker compose up -d
   docker compose ps
   docker compose logs minio-init
   ```
   La primera vez descarga las imágenes. `minio` y `spark` deben aparecer en ejecución, y el log de `minio-init` debe decir `Bucket rawdata listo`.
4. **Comprobar el almacenamiento:** abre http://localhost:9002 e inicia sesión con `MINIO_ACCESS_KEY` y `MINIO_SECRET_KEY`. Debe verse el bucket `rawdata`, vacío.
5. **Cargar los datos:** descarga el `.zip` de Drive, descomprímelo en `data\` y ejecuta `docker compose run --rm minio-load`. Pasos detallados en `data/README.md`. Al terminar, `rawdata/secop/` contiene el CSV.
6. **Abrir JupyterLab:** http://localhost:8888/?token=TU_TOKEN (o pega el token cuando lo pida). Entra a `work/notebooks/`.
7. **Construir el bronze:** en el notebook `01`, cambia `RECONSTRUIR_BRONZE = False` por `True` y ejecuta todo (Run → Run All Cells). Lee el CSV **una sola vez** y escribe un Parquet intermedio; de ahí salen el bronze (sin particionar y particionado) y la cuarentena. En el equipo de referencia (8 núcleos, 7,6 GB) el notebook completo tardó unas 2 h 15 min: unos 30 min la escritura del Parquet intermedio (el CSV se lee con `multiLine=True`, que usa un solo núcleo; ver *Notas sobre los datos*) y unos 90 min la medición de consulta sobre el CSV, que repite la lectura completa tres veces (`REPETICIONES_CSV`; con 1 se ahorra más de una hora). Para dejarlo corriendo sin navegador, ver *Ejecutar sin navegador*.
8. **Ejecutar el resto** de los notebooks en orden (el `02` y el `03` tardan unos 3 minutos cada uno). Después de la primera vez, deja `RECONSTRUIR_BRONZE = False`. El `04` sigue la misma idea con `RECONSTRUIR_SILVER` y `RECONSTRUIR_GOLD`: ponlos en `True` la primera vez para escribir silver y gold.

### Accesos
| Qué | Dirección |
|---|---|
| JupyterLab | http://localhost:8888 |
| Consola de almacenamiento | http://localhost:9002 |
| Spark UI (solo mientras corre un trabajo) | http://localhost:4040 |
| API S3 (para Spark) | http://localhost:9000 |

### Ver el avance de una celda larga
Abre el Spark UI (http://localhost:4040). En *Jobs* se ve la fracción de tareas completadas del trabajo en curso; en *Stages*, los datos leídos y escritos. En la consola (puerto 9002) aparecen `bronze/` y `cuarentena/` cuando empieza la escritura. `docker stats` muestra la memoria y la CPU de los contenedores.

### Ejecutar sin navegador
Para una corrida larga (por ejemplo, la reconstrucción del bronze) conviene no depender de la pestaña de JupyterLab: si se cierra, el kernel sigue pero las salidas no se guardan. Con `RECONSTRUIR_BRONZE = True` guardado en el `01` y todos los kernels apagados (Kernel → Shut Down All Kernels):
```
docker exec -d spark sh -c "cd /home/jovyan/work/notebooks && jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --output 01_ejecutado 01_corte1_bronze_y_almacenamiento.ipynb > nbconvert_01.log 2>&1 && jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --output 02_ejecutado 02_corte2_shuffle_y_sesgo.ipynb > nbconvert_02.log 2>&1 && jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 --output 03_ejecutado 03_corte2_pagerank.ipynb > nbconvert_03.log 2>&1"
```
- El comando encadena los tres notebooks con `&&`: se detiene en el primer error. `timeout=-1` quita el límite de 30 s por celda.
- Los resultados quedan en `notebooks/*_ejecutado.ipynb` y los registros en `notebooks/nbconvert_0X.log`; ambos están en `.gitignore`.
- Mientras corre, el avance se ve en el Spark UI. Terminó cuando `docker exec spark ps aux` ya no muestra `jupyter-nbconvert` ni `java`. Si falta algún `*_ejecutado.ipynb`, el motivo está en el registro correspondiente (`docker exec spark tail -n 40 /home/jovyan/work/notebooks/nbconvert_01.log`).
- Para conservar los resultados, copia cada `*_ejecutado.ipynb` sobre el notebook original y deja `RECONSTRUIR_BRONZE = False` en el `01`.
- No abras otra sesión de Spark mientras corre: se repartirían la memoria.
- Si el contenedor se creó con una versión anterior del `docker-compose.yml`, recréalo antes con `docker compose up -d` (se añadió la ruta de PySpark a `PYTHONPATH`, que `docker exec` necesita).

### Uso diario
- Apagar conservando los datos: `docker compose stop`. Volver: `docker compose up -d`.
- **No uses `docker compose down -v`:** borra el volumen con el bronze y hay que reconstruirlo.

### Solución de problemas
| Síntoma | Causa probable y arreglo |
|---|---|
| `pull access denied for minio/mc` o `minio/minio` | MinIO retiró esas imágenes de Docker Hub. Este repositorio ya no las usa (ver *Imagen de almacenamiento*). Si lo ves, tienes un compose antiguo: haz `git pull`. |
| `port is already allocated` | Otro programa o un entorno Docker anterior usa 8888, 9000, 9002 o 4040. Apaga el anterior (`docker ps`, `docker compose down` en su carpeta, sin `-v`). |
| `Define MINIO_ACCESS_KEY en .env` (u otra variable) | Falta el `.env` o tiene campos vacíos. |
| `Falta la variable de entorno MINIO_ACCESS_KEY` en el notebook | El contenedor `spark` arrancó sin el `.env`. Revísalo y ejecuta `docker compose up -d --force-recreate`. |
| `ModuleNotFoundError: pamd` | El repo no está montado. Comprueba con `docker exec spark ls /home/jovyan/work/src`. |
| Error `403` o de acceso a S3 | Las claves del `.env` no coinciden con las del servidor de almacenamiento. Si cambiaste el `.env`, recrea el volumen (borra los datos) o vuelve a las claves anteriores. |
| `minio-load` no encuentra archivos | El CSV no está directamente en `data\` o no termina en `.csv`. |
| El kernel muere o hay error de memoria | Docker tiene poca memoria asignada (ver Requisitos). |
| `OutOfMemoryError: Java heap space` al escribir Parquet | El heap de Spark en modo local es de 1 GB por defecto. `spark_session.py` lo sube a 5 GB, pero solo al iniciar la sesión: reinicia el kernel. Se comprueba en el Spark UI → *Executors*: el driver debe mostrar unos 2,8 GiB de memoria de almacenamiento. |
| `SparkUpgradeException` al escribir fechas (INT96, 1900) | El CSV trae fechas anteriores a 1900. `spark_session.py` ya configura el modo `CORRECTED` de escritura y lectura de Parquet. |
| `TASK_WRITE_FAILED` con `AWSBadRequestException ... IncompleteBody` al escribir Parquet | El almacenamiento, sobrecargado, cortó la copia con la que Spark confirma cada archivo. Es pasajero, pero en modo local Spark no reintenta salvo con `local[N,F]`. `spark_session.py` usa `local[*,4]`; en equipos con poca memoria pon `SPARK_MASTER=local[2,4]` en `.env` y reinicia el kernel. |
| `request returned 500 Internal Server Error for API route` en cualquier comando `docker` | El motor de Docker se colgó por falta de memoria del equipo. Cierra Docker Desktop (si no responde, desde el Administrador de tareas), ejecuta `wsl --shutdown`, baja `memory` en `.wslconfig` y vuelve a abrirlo. Los datos del volumen no se pierden. |
| `No module named 'pyspark'` con `docker exec` | Contenedor creado con un compose antiguo. Ejecuta `docker compose up -d` para recrearlo (los datos no se pierden). |

## Notebooks

Cada notebook empieza con una celda de configuración que importa `pamd.config` (rutas) y `pamd.spark_session.get_spark()` (Spark + MinIO con las credenciales del `.env`).

| Notebook | Corte | Contenido | Estado |
|---|---|---|---|
| `01_corte1_bronze_y_almacenamiento.ipynb` | 1 | Lectura, limpieza y capa bronze en Parquet; comparación de CSV, Parquet y Parquet particionado | Ejecutado el 12-nov-2026 |
| `02_corte2_shuffle_y_sesgo.ipynb` | 2 | `groupByKey` frente a `reduceByKey`, volumen de shuffle y sesgo de datos | Ejecutado el 12-nov-2026 |
| `03_corte2_pagerank.ipynb` | 2 | PageRank entidad → contratista | Ejecutado el 12-nov-2026 |
| `04_corte3_silver_gold.ipynb` | 3 – Punto 1 | Deduplicación, silver, gold y tablas resumen | T1.1 a T1.3 ejecutadas el 13-nov-2026; T1.4 a T1.6 por hacer |
| `05_corte3_streaming_ventanas.ipynb` | 3 – Punto 2 | Micro-lotes, Structured Streaming y ventanas | Por hacer |
| `06_corte3_resiliencia_idempotencia.ipynb` | 3 – Punto 3 | Checkpoint, destino idempotente y pruebas de fallo | Por hacer |

El notebook original (cortes 1 y 2) se dividió en los tres primeros. Los tres se ejecutaron el 12 de noviembre de 2026 sobre el bronze reconstruido, y sus salidas están guardadas. Los notebooks 02 y 03 leen el bronze ya escrito en MinIO, así que el 01 debe ejecutarse antes (con `RECONSTRUIR_BRONZE = True` la primera vez).

## Capas de datos en MinIO

```
s3a://rawdata/
├── secop/                                CSV original
├── staging/secop/con_calidad             todos los registros con sus motivos de rechazo
├── bronze/secop/contratos                Parquet sin particionar
├── bronze/secop/contratos_particionado   Parquet por año y departamento
├── cuarentena/secop                      registros rechazados
├── procesado/                            tablas resumen
├── benchmark_escritura/                  salidas de la prueba de tiempos de escritura
├── silver/secop/contratos                (Corte 3) una fila por proceso + adjudicación
├── silver/secop/descartados              (Corte 3) filas descartadas con su motivo
├── gold/secop/adjudicaciones             (Corte 3) contratos adjudicados, por año de adjudicación
└── gold/secop/excluidos                  (Corte 3) adjudicados que no pasan a gold, con su motivo
```

## Trabajo en equipo

- El plan de subtareas está en `docs/plan_de_subtareas.pdf`. Cada tarea tiene un ID (T0.1, T1.2…); úsalo en los mensajes de commit y en los nombres de rama, por ejemplo `t0.2-credenciales`.
- Trabaja en una rama por tarea y une a `main` con pull request.
- Dos personas no deben editar el mismo notebook a la vez: un `.ipynb` es un JSON y se resuelve mal al unir cambios. La división por notebooks existe para evitarlo.
- No subas `.env`, claves ni datos. Si una clave se sube por error, hay que cambiarla; borrarla del archivo no basta.

## Notas sobre los datos

- **El CSV tiene saltos de línea dentro de campos de texto** (las descripciones de los procesos). Leído con `multiLine=False`, cada salto de línea partía un contrato en varios registros: 3,3 millones de líneas terminaban en cuarentena como `csv_malformado`, entre ellas unas 922.000 cabezas de contratos reales. Con `multiLine=True` se leen 9.099.859 registros y ninguno sale mal formado. Por eso el notebook `01` lee con `multiLine=True`.
- **La poda de columnas del lector CSV está desactivada** en `src/pamd/spark_session.py`. Con la poda activa, un conteo no detecta los registros mal formados en las columnas que no usa, y las cifras de un `count()` difieren de las de la escritura.
- **Los conteos de control se calculan sobre lo escrito** (registros leídos = bronze + cuarentena), no sobre el DataFrame del CSV.
- **Formato colombiano en los enteros.** Muchas columnas numéricas usan el punto como separador de miles (`1.398` = 1.398 proveedores; `1.095` = 1.095 días de duración), y el NIT llega a veces con punto final (`900089839.`) o con dígito de verificación (`814005267-5`). Sin tratarlos, unos 63.000 registros válidos se rechazaban solo por el formato. La limpieza (celda 15 del `01`) quita los puntos únicamente cuando el valor tiene exactamente la forma de miles, para que `5.0` no se convierta en `50`.
- **Resultado de la última reconstrucción (12-nov-2026):** 9.099.859 registros leídos = 9.099.432 en el bronze + 427 en cuarentena, con 0 mal formados. La cuarentena contiene 330 `precio_base` negativos (242 con el mismo valor, `$-10.232.556.498`), 95 códigos PCI con la marca `_DUP` y 2 valores de adjudicación inválidos. `scripts/revisar_cuarentena.py` muestra los valores originales (`docker exec spark python /home/jovyan/work/scripts/revisar_cuarentena.py`).
- **Fechas anteriores a 1900** (errores de captura): el Parquet intermedio las guarda tal cual (modo `CORRECTED`) y el bronze las convierte en nulo.

## Imagen de almacenamiento

MinIO retiró `minio/minio` y `minio/mc` de Docker Hub en septiembre de 2026 (según fuentes de terceros; no hubo aviso oficial). Por eso este repositorio usa:
- **Servidor:** `pgsty/silo` (bifurcación de MinIO con la misma línea de comandos), fijado en `docker-compose.yml`. Se cambia con `MINIO_IMAGE` en `.env`.
- **Cliente:** `amazon/aws-cli`, para crear el bucket y cargar el CSV.

Verificado: el servidor arranca, el bucket se crea, la consola web abre en el puerto 9002, el CSV se carga, Spark lo lee y la escritura completa del bronze, la cuarentena y las tablas de `procesado/` funciona (12-nov-2026). Aún sin confirmar: el uso de checkpoints de streaming (Corte 3).

## Pendientes conocidos

- **T0.4 (cerrada):** el 13-nov-2026 se repitió el flujo desde un clon limpio y un MinIO vacío, siguiendo este README, en un equipo con 8 GB de RAM (Docker con 4,8 GB, `SPARK_DRIVER_MEMORY=2g`, `SPARK_MASTER=local[2,4]`). Resultado: 9.099.859 registros leídos = 9.099.432 en el bronze + 427 en cuarentena, 0 mal formados; el bronze particionado también tiene 9.099.432 filas. Coincide con la ejecución de referencia del 12-nov-2026. No se repitió la medición de tiempos de consulta del `01`.
- **T0.3 (cerrada):** el `02` trabaja sobre 9.099.432 registros, igual que el bronze, y las conclusiones de los notebooks `01`, `02` y `03` se generan con las variables.
- **T0.2:** las credenciales salen de variables de entorno. La búsqueda en el historial con el valor de la clave anterior (`git log -p --all -S"<clave anterior>"`) no devolvió nada. Repítela si se sospecha que se subió una clave; el valor no se escribe aquí.
- **Medición del CSV:** la consulta sobre el CSV dio 888 s con una repetición y 1.806 s de mediana con tres (1.669 a 2.078 s). La limpieza nueva añade trabajo por registro y la máquina pudo tener otra carga; no se investigó. Cítese como medición en un equipo concreto.
- **Escritura particionada:** en la prueba con 10.000 filas, el Parquet particionado tarda unos 15 s frente a 0,6 s del no particionado; probablemente por el costo fijo de crear y confirmar muchos archivos pequeños en el almacenamiento de objetos (no medido).
- **Versiones:** el servidor de almacenamiento está fijado, pero `amazon/aws-cli` no tiene versión fija.
