# Dashboard (Punto 4)

Dashboard interactivo del Observatorio de Contratación Pública. Responde las tres preguntas del enunciado: dónde se concentra el gasto, quiénes son los principales actores y cómo varía la contratación en el tiempo.

**Estado:** T4.1 (tablas de consumo), T4.2 (tecnología), T4.3 (filtros y tarjetas), T4.4 (visualización temporal), T4.5 (rankings) y T4.6 (geografía y concentración) cerradas el 16-nov-2026. Falta T4.7: pruebas finales y capturas comentadas.

## Geografía y concentración (T4.6)

Responde dónde se concentra el dinero, con los filtros de la barra lateral:

- **Valor adjudicado por departamento**: barras horizontales ordenadas de mayor a menor, con el valor en billones de pesos y, al pasar el cursor, la participación y los contratos. Los contratos cuya entidad no informa departamento forman la categoría **«Sin departamento»**, con otro color: no se ocultan. Una línea bajo el gráfico comprueba que la suma de los departamentos mostrados es igual al valor y a los contratos filtrados de las tarjetas. No hay mapa: haría falta un archivo con los límites departamentales, y las barras responden la misma pregunta sin una descarga más.
- **Concentración en las entidades**: cuántas entidades reúnen el 50 % y el 80 % del valor, cuánto suman las 10 primeras, y la curva del valor acumulado con las entidades ordenadas de mayor a menor valor (eje horizontal logarítmico, porque unas pocas entidades pesan casi todo). Se cuentan las entidades con al menos un contrato en lo filtrado, y la comparación con el umbral usa pesos enteros, sin redondeos. Si el valor filtrado es cero no hay concentración que medir y la app lo dice; con menos de tres entidades no se dibuja la curva.

El departamento es el de la entidad que contrata en cada contrato. La lógica está en `consultas.py` (`valor_por_departamento` y `concentracion_entidades`).

### Verificación contra Spark

Para las mismas siete combinaciones de filtros de T4.5 (ver la tabla de T4.5):

1. `docker exec spark python /home/jovyan/work/scripts/consultas_spark_geografia.py` calcula **directamente sobre gold** el valor y los contratos por departamento y la concentración (el acumulado con una función de ventana de Spark) y guarda `verificacion/geografia_spark.json`.
2. `.venv\Scripts\python scripts\comprobar_geografia.py` compara esa referencia con las funciones del dashboard y con lo que dibuja la app real: los datos de las barras (departamentos y categoría aparte), las tarjetas del 50 % y del 80 %, la curva y la línea de la suma.

Resultado del 16-nov-2026: las siete combinaciones coinciden, con pesos, contratos y número de entidades exactos. Se comprobó que el comprobador falla si se altera un peso, el número de entidades del 50 % o se quita la categoría «Sin departamento» de la referencia. (La primera versión de la referencia guardaba los resultados por departamento en la misma clave que los filtros del caso, y la comprobación resultaba circular; lo detectó esa prueba y se separaron en `departamentos` y `por_departamento`.)

Cifras sin filtros para el informe (pesos sin atípicos):

| Dónde | Cifra |
|---|---|
| Bogotá | 53,6 % del valor y 28,3 % de los contratos (150.188) |
| Los tres primeros departamentos | Bogotá, Antioquia (11,0 %) y Valle del Cauca (4,3 %) suman el 68,8 % del valor |
| Departamentos para llegar al 80 % | 8 de 34 |
| Sin departamento | 18.874 contratos (3,6 %) y 1,0 % del valor |
| Entidades que reúnen la mitad del valor | 30 de 4.050 (0,7 %) |
| Entidades que reúnen el 80 % y el 90 % | 150 (3,7 %) y 324 (8,0 %) |
| Las 10 primeras entidades | 31,2 % del valor |

Para leerlas: Bogotá pesa más que todos los demás departamentos juntos en valor, pero menos de un tercio en número de contratos, así que sus contratos son más grandes. Dentro de cada departamento el gasto también se concentra en pocas entidades (en Antioquia, de 2020 a 2023, dos de 279 entidades reúnen la mitad). Es la concentración del valor entre entidades; no dice nada de la competencia dentro de cada contratación.

## Principales actores (T4.5)

Dos tablas, una bajo la otra: las **N entidades** y los **N contratistas** que más pesan en lo filtrado. N se elige entre 1 y 50 (10 por defecto) y el orden, por valor adjudicado o por número de contratos. Cada fila trae nombre, identificación, contratos, contratos atípicos, valor en millones de pesos y su participación en el total filtrado; bajo cada tabla, lo que suman las N primeras. Los rankings respetan los filtros de la barra lateral: se agrupan `serie_mensual` (entidades) y `contratistas_mensual` (contratistas) después de filtrarlas. La lógica está en `consultas.py`.

Reglas de lectura:
- El valor es `valor_total`, **sin atípicos**; los contratos incluyen los atípicos y por eso hay una columna «Atípicos». Un contratista cuyo contrato más grande es atípico puede aparecer con un valor bajo.
- En empate gana el identificador menor, así el resultado es siempre el mismo.
- Una entidad es un NIT y puede agrupar varias dependencias: el nombre que se muestra es el más frecuente (por eso el NIT 899999034, el SENA, aparece como «SENA REGIONAL VALLE» incluso al filtrar por Antioquia).
- El puntaje de PageRank del Corte 2 (opcional en el plan) no se añadió: no hay una tabla guardada con él y recalcularlo sobre gold daría cifras distintas a las del Corte 2, que se calcularon sobre el bronze.

### Verificación contra Spark

Criterio de T4.5: el top 10 del dashboard debe coincidir con una consulta de Spark sobre gold para al menos tres combinaciones de filtros. Se hicieron siete, con entidades y contratistas, por valor y por número de contratos (28 tops de 10 filas):

| Combinación de filtros | Contratos filtrados |
|---|---|
| Sin filtros | 530.192 |
| Antioquia, 2020 a 2023 | 27.728 |
| Bogotá, 2022 | 16.315 |
| Valle del Cauca y Cundinamarca | 63.245 |
| SIN DEPARTAMENTO | 18.874 |
| Una entidad (SENA), 2019 a 2025 | 29.449 |
| Primeros años, 2015 a 2017 | 20.172 |

1. `docker exec spark python /home/jovyan/work/scripts/consultas_spark_rankings.py` calcula los tops **directamente sobre gold** con las reglas de `src/pamd/calidad.py`, sin usar las tablas de consumo, y guarda `verificacion/rankings_spark.json`.
2. `.venv\Scripts\python scripts\comprobar_rankings.py` compara ese archivo con `calcular_ranking()` (identificador, contratos, atípicos y pesos, exactos) y con lo que muestra el dashboard real, moviendo los filtros y el orden con la prueba de Streamlit. También comprueba N=3 y N=50.

Resultado del 16-nov-2026: las siete combinaciones coinciden en los 28 tops y en las 28 tablas de pantalla, y los totales filtrados son iguales. Se comprobó que el comprobador falla si se altera un número o se cambia el orden de dos filas de la referencia.

Cifras sin filtros para el informe (pesos sin atípicos; cálculo con pandas sobre las tablas de consumo):

| | Primero | Las 10 primeras |
|---|---|---|
| Entidades por valor | INVIAS, 6,3 % del valor | 31,2 % del valor |
| Entidades por contratos | SENA (nombre más frecuente: «SENA REGIONAL VALLE»), 6,2 % de los contratos | 16,9 % de los contratos |
| Contratistas por valor | GECELCA S.A. E.S.P., 1,2 % del valor | 6,6 % del valor |
| Contratistas por contratos | La Previsora S.A. Compañía de Seguros, 0,7 % de los contratos | 2,3 % de los contratos |

Entre los 99.236 contratistas con valor mayor que cero, el 1 % de mayor valor (992) concentra el 52,6 % del valor adjudicado.

## Visualización temporal (T4.4)

Dos gráficos mensuales con el mismo eje de tiempo: valor adjudicado (billones de pesos, sin atípicos) y número de contratos (con los atípicos incluidos, como en las tarjetas). Responden a los filtros de la barra lateral y muestran todos los meses del rango, también los que no tienen contratos (en cero). Los puntos y las franjas se leen pasando el cursor. Los puntos rojos son los cinco meses de mayor valor y los cinco con más contratos del periodo filtrado, y debajo hay una tabla con ellos y los periodos que los tocan. Dos casillas permiten apagar las franjas de la ley de garantías y las del cierre fiscal.

**Periodos marcados** (`periodos.py` guarda las fechas y las fuentes; consultadas el 16-nov-2026):

| Franja | Periodos | Base |
|---|---|---|
| Contratación directa prohibida a todos los entes del Estado (Ley 996 de 2005, art. 33) | Presidencial 2018: 27-ene a 17-jun · 2022: 29-ene a 19-jun · 2026: 31-ene a 21-jun | Cuatro meses antes de la elección presidencial y hasta la segunda vuelta. Elecciones: 27-may y 17-jun de 2018, 29-may y 19-jun de 2022, 31-may y 21-jun de 2026. |
| Convenios interadministrativos restringidos (art. 38, parágrafo) | Congreso: 11-nov-2017 a 11-mar-2018, 13-nov-2021 a 13-mar-2022, 8-nov-2025 a 8-mar-2026 · Territoriales: 25-jun a 25-oct de 2015, 27-jun a 27-oct de 2019, 29-jun a 29-oct de 2023 | Cuatro meses antes de la elección y hasta ella; alcanza a gobernadores, alcaldes y directivos de entidades territoriales, y solo a esos convenios, por eso va en otro color. |
| Cierre de vigencia fiscal | Diciembre de cada año | El año fiscal va del 1 de enero al 31 de diciembre. |

Lo que se verificó y lo que no:
- Las fechas de las elecciones de 2018, 2022 y 2026 (presidencial y Congreso) están en resoluciones de la Registraduría o en notas que las citan, y las ventanas de 2022 y 2026 coinciden con las que publicaron la Mesa de Observación Electoral y la prensa. Las territoriales de 2015 y 2019 se derivan de la regla del último domingo de octubre (Ley 163 de 1994); no se encontró una resolución que las confirme.
- La regla del art. 33 se tomó del texto transcrito en un concepto del Consejo de Estado y de la Circular 0006 de 2025 de la Agencia Nacional de Contratación Pública, que la aplica como vigente. No se consultó una fuente oficial de vigencia de la ley ni se encontró una modificación posterior: conviene confirmarlo antes de citarlo en el informe.
- La definición del año fiscal (Decreto 111 de 1996, art. 14) no se abrió en esta consulta.
- El art. 33 tiene excepciones (defensa y seguridad, crédito público, urgencia manifiesta, entre otras) y no limita prórrogas ni adiciones de contratos ya firmados.

**Cada punto coincide con las ventanas del flujo (T2.4).** Si no hay filtro de entidad, una línea bajo el gráfico compara los puntos del mes con `ventanas_flujo` (contratos y pesos, exactos) para los mismos departamentos y meses. Se comprobó sin filtros (136 meses), con un departamento, con dos departamentos y un rango de 31 meses, y con un solo mes. Con filtro de entidad no hay ventanas equivalentes, porque el flujo agrega por mes y departamento, y la línea lo dice.

### Picos detectados (sin filtros, 16-nov-2026)

| Mayor valor adjudicado | Billones | Más contratos | Contratos |
|---|---|---|---|
| 2025-12 | 15,00 | 2025-12 | 11.437 |
| 2023-12 | 11,66 | 2024-12 | 11.304 |
| 2024-12 | 10,44 | 2025-10 | 10.078 |
| 2022-12 | 9,91 | 2025-11 | 9.750 |
| 2026-07 | 9,04 | 2022-12 | 9.607 |

Qué permite concluir:
- **Diciembre es el pico de cada año.** Cuatro de los cinco meses de mayor valor y dos de los cinco con más contratos son diciembre. En los años completos de 2017 a 2025, diciembre tiene entre 1,25 y 2,06 veces los contratos y entre 1,97 y 5,12 veces el valor del promedio mensual de enero a noviembre. Coincide con el cierre de la vigencia fiscal, aunque estos datos no prueban la causa.
- **No se ve una caída consistente dentro de las ventanas del art. 33.** Promedio mensual de febrero a mayo (meses completos de la ventana) frente a los mismos meses de los años vecinos: 2022, 4.715 contratos frente a 3.190 (2021) y 5.172 (2023); 2026, 6.554 frente a 5.991 (2025); 2018, 2.291 frente a 1.066 (2017) y 2.705 (2019). La tendencia creciente y el pico de diciembre pesan más. La serie cuenta todos los contratos adjudicados, no solo la contratación directa: ver los límites.
- **Octubre y noviembre de 2025 están entre los meses con más contratos**, justo antes de que empezara la restricción del Congreso (8-nov-2025). Es compatible con una aceleración previa, pero los datos no la prueban.
- **Julio de 2026** es el primer mes completo después de que terminó la restricción presidencial y tiene el quinto mayor valor.

Límites de lectura:
- El último mes (2026-09) llega solo hasta el 1 de septiembre: su caída no es real. Los primeros meses (2015-06 y 2016) tienen muy pocos contratos (29 en 2015).
- Las franjas muestran cuándo rige la restricción, no cuánta contratación directa hubo. Para medir el efecto haría falta separar por modalidad de contratación, que las tablas de consumo no traen.
- Las ventanas de los gráficos muestran los números con la convención de la librería (coma de miles y punto decimal), distinta de la de las tarjetas.

## Filtros y tarjetas (T4.3)

La barra lateral tiene tres filtros que se aplican a todo lo que muestre el dashboard:

| Filtro | Cómo funciona |
|---|---|
| Departamento | Selección múltiple; sin selección, todos. `SIN DEPARTAMENTO` es una opción más, no se oculta. |
| Entidad | Selección múltiple con búsqueda por nombre o NIT; sin selección, todas. Solo ofrece las entidades que tienen contratos en los departamentos elegidos, y quita de la selección las que dejan de tenerlos. |
| Meses de adjudicación | Rango inclusivo de `AAAA-MM` a `AAAA-MM` (2015-06 a 2026-09). |

El botón **Quitar filtros** los deja todos abiertos. Las tarjetas muestran contratos adjudicados, valor adjudicado (sin atípicos), contratos atípicos, entidades y contratistas de lo filtrado. Si una combinación no tiene contratos, aparece un aviso y ninguna tarjeta, no un error. Con todos los filtros abiertos, una línea bajo las tarjetas confirma que los totales coinciden con los de gold.

Para los módulos siguientes: `app.py` deja `serie` (de `serie_mensual`) y `contratistas` (de `contratistas_mensual`) ya filtradas con `aplicar_filtros()`; solo hay que agruparlas.

Comprobado el 16-nov-2026 con la prueba de Streamlit y un cálculo independiente sobre `contratistas_mensual` (otra tabla): sin filtros dan los totales de gold (530.192 contratos, 432 atípicos) y cinco combinaciones de departamento, entidad y meses dan las mismas cifras en las tarjetas (por ejemplo, Antioquia: 59.982 contratos, 38,7 billones, 417 entidades y 12.133 contratistas; el año 2024: 74.067 contratos, los mismos que gold).

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
