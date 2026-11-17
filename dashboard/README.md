# Dashboard (Punto 4)

Dashboard interactivo del Observatorio de Contratación Pública. Responde las tres preguntas del enunciado: dónde se concentra el gasto, quiénes son los principales actores y cómo varía la contratación en el tiempo.

**Estado:** T4.1 (tablas de consumo) y T4.2 (tecnología) cerradas el 16-nov-2026. `app.py` carga las tablas y muestra los totales; los filtros y los módulos se añaden en T4.3 a T4.6.

## Tecnología (T4.2)

**Streamlit**, porque el proyecto ya está en Python, el dashboard cabe en un archivo y se abre con un solo comando. Lee archivos Parquet locales con pandas: no necesita Spark, Java, Docker ni MinIO en marcha.

## Cómo se lanza

Desde la raíz del repositorio, con Python 3.10 o posterior. La primera vez (PowerShell):

```
python -m venv .venv
.venv\Scripts\python -m pip install -r dashboard\requirements.txt
```

Cada vez que se quiera abrir:

```
.venv\Scripts\python -m streamlit run dashboard\app.py
```

Se abre en el navegador en http://localhost:8501. Se detiene con Ctrl+C en la terminal.

Probado el 16-nov-2026 en Windows con Python 3.14, Streamlit 1.67 y pandas 3.1.

## De dónde lee los datos

De `dashboard/data/`, que está versionada en el repositorio (6,7 MB): con clonar basta para abrir el dashboard. Los archivos los genera el notebook `07_corte3_tablas_dashboard.ipynb` a partir de gold, y la misma copia queda en MinIO en `s3a://rawdata/procesado/dashboard/`. Si gold o el flujo cambian, hay que volver a ejecutar el notebook 07 con `RECONSTRUIR_CONSUMO = True`.

## Tablas de consumo (T4.1)

| Archivo | Una fila por | Filas | Tamaño | Para qué |
|---|---|---|---|---|
| `serie_mensual.parquet` | mes × departamento × entidad | 99.789 | 776 KB | Tarjetas de totales, gráfico temporal, ranking de entidades, valor por departamento y concentración |
| `contratistas_mensual.parquet` | mes × departamento × entidad × contratista | 481.397 | 4,1 MB | Ranking de contratistas con los filtros aplicados |
| `entidades.parquet` | entidad | 4.050 | 81 KB | Nombre de cada entidad |
| `contratistas.parquet` | contratista | 99.606 | 1,8 MB | Nombre de cada contratista |
| `ventanas_flujo.parquet` | mes × departamento | 3.735 | 42 KB | Resultado del flujo (T2.4), para comprobar el gráfico temporal |
| `metadatos.json` | – | – | 1 KB | Totales de gold, fecha del último lote procesado por el flujo y filas de cada tabla |

Los rankings y el valor por departamento no se guardan ya agrupados: el dashboard los calcula después de aplicar los filtros, agrupando `serie_mensual` o `contratistas_mensual`.

### Columnas

Claves:

| Columna | Tipo | Significado |
|---|---|---|
| `anio_mes` | texto | Año y mes de adjudicación, `AAAA-MM`. De `2015-06` a `2026-09`. |
| `departamento` | texto | Departamento de la entidad contratante en cada contrato. Los contratos sin departamento van a `SIN DEPARTAMENTO`. |
| `id_entidad` | texto | Identificador de la entidad contratante (misma regla que gold, con los NIT unificados). |
| `id_contratista` | texto | Identificador del contratista (NIT, luego código, luego nombre). |

Medidas (iguales en `serie_mensual`, `contratistas_mensual` y `ventanas_flujo`; todas son enteros de 64 bits):

| Columna | Significado |
|---|---|
| `contratos` | Número de contratos adjudicados, con los atípicos incluidos. |
| `contratos_atipicos` | Contratos marcados como atípicos en T1.5 (valor inconsistente con el precio base o extremo). |
| `contratos_valor_cero` | Contratos con valor 0. |
| `valor_total` | Suma del valor adjudicado **sin** los atípicos, en pesos enteros. |
| `valor_atipicos` | Suma del valor adjudicado de los contratos atípicos, en pesos enteros. |

Descriptivas:

| Columna | Tabla | Significado |
|---|---|---|
| `nombre_entidad` | `entidades` | Nombre más frecuente entre los contratos de la entidad. |
| `departamento_entidad` | `entidades` | Departamento más frecuente de la entidad. Solo descriptivo: los filtros usan `departamento`. |
| `nombre_contratista` | `contratistas` | Nombre más frecuente entre los contratos del contratista. |

### Comprobaciones (notebook 07)

- Cada tabla con medidas suma lo mismo que gold: 530.192 contratos, 432 atípicos, 1.527 con valor cero, 352.909.018.925.397 pesos sin atípicos y 174.714.776.221.732.357 pesos de atípicos.
- `serie_mensual` agrupada por mes y departamento es igual a `ventanas_flujo` en las 3.735 ventanas.
- `contratistas_mensual` agrupada sin el contratista es igual a `serie_mensual`.
- Una fila por clave, sin claves nulas; todas las entidades y contratistas tienen nombre.
- Los cinco archivos se cargan con pandas en menos de 1 s dentro del contenedor y en unos 3 s la primera vez en Windows.

### Qué tener en cuenta al construir los módulos

- **Los atípicos pesan el 99,8 % del valor de gold.** Los gráficos y rankings deben usar `valor_total` (sin atípicos) y mostrar `valor_atipicos` aparte; sumarlos da cifras dominadas por errores de captura.
- **Una entidad puede tener contratos en más de un departamento** (4.220 pares entidad–departamento para 4.050 entidades). El filtro de departamento se aplica a la columna `departamento` de cada fila, no al departamento de la entidad.
- **Fecha del último lote procesado:** `metadatos.json` → `flujo.fecha_ultimo_micro_lote_utc` es la hora en que el flujo del notebook 06 escribió su último micro-lote (T4.7 pide mostrarla).
