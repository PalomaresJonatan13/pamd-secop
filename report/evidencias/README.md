# Evidencias para el informe (T2.3 a T4.7)

Capturas de las salidas guardadas en los notebooks `05` y `06`, tal como quedaron en `main` el 15-nov-2026. No hubo que volver a ejecutar nada: si se vuelven a correr los notebooks, las cifras deben ser las mismas. Las capturas de T3.2 a T3.4 son de las salidas del notebook `06` ejecutado el 16-nov-2026.

| Archivo | Subtarea | Qué muestra | Celda de origen |
|---|---|---|---|
| `t2.3_avance_por_lote.png` | T2.3 | Registro de progreso por micro-lote: 22 disparos con datos, uno por lote y en orden; filas leídas igual a filas del lote; marca de agua de cada disparo | `05`, `# T2.3 · Registro de progreso por micro-lote` |
| `t2.4_ventanas_anual_y_criterios.png` | T2.4 | Versión anual de las ventanas y criterios: 3.735 ventanas (mes × departamento) que suman los 530.192 contratos de gold | `05`, `# T2.4 · Resultado del flujo por ventana` |
| `t2.5_antes_y_despues_de_los_tardios.png` | T2.5 | Antes y después de cada lote tardío: el de 2023-04 (dentro de la tolerancia) se incorpora y solo cambian 33 ventanas de ese mes; el de 2020-10 (fuera) no cambia ninguna ventana y sus 866 filas quedan en `streaming/tardios/` | `05`, `# T2.5 · Comparación antes y después de cada lote tardío` |
| `t2.6_resumen.png` | T2.6 | 3.735 ventanas comparadas, ninguna con diferencia | `05`, `# T2.6 · Comparación ventana por ventana` |
| `t2.6_comparacion_flujo_vs_lotes.png` | T2.6 | Tabla completa por mes: contratos y valor del flujo frente a la consulta por lotes, con su diferencia (cero en los 136 meses) | `05`, `# T2.6 · Comparación ventana por ventana` |
| `t3.1_contenido_del_checkpoint.png` | T3.1 | Qué guarda el checkpoint tras detener el flujo después del lote 11: carpetas, archivos ya leídos, `offsets` y `commits` del último disparo | `06`, `# T3.1 · Contenido del checkpoint después de la parada` |
| `t3.1_antes_y_despues_del_reinicio.png` | T3.1 | Lotes leídos antes y después del reinicio con el mismo checkpoint: sigue en el disparo 21 con el lote 12 y no relee ninguno | `06`, `# T3.1 · Tras detener y reiniciar...` |
| `t3.1_consulta_cambiada.png` | T3.1 | Una consulta cambiada (agrupada solo por mes) no puede usar el checkpoint: `StateSchemaNotCompatible` | `06`, `# T3.1 · Prueba: la misma fuente agrupada solo por mes` |
| `t3.2_mismo_micro_lote_1_2_y_10_veces.png` | T3.2 | El último micro-lote guardado 1, 2 y 10 veces en el destino idempotente: mismas ventanas, contratos, valor y huella | `06`, `# T3.2 · Repetir el último micro-lote` |
| `t3.2_contraste_con_append.png` | T3.2 | El mismo micro-lote en modo `append` sobre una copia de la tabla: cada repetición añade 103 filas y 20.913 contratos ya contados | `06`, `# T3.2 · Contraste con append` |
| `t3.3_sin_deduplicacion.png` | T3.3 | Sin deduplicación, el último lote depositado con otro nombre cuenta 13.179 contratos dos veces | `06`, `# T3.3 · Contraste: la consulta sin deduplicación` |
| `t3.3_lote_repetido.png` | T3.3 | Con deduplicación, tres lotes ya procesados vuelven a la entrada (mismo nombre, otro nombre con meses abiertos, otro nombre con meses cerrados): filas leídas, motivo del descarte y cifras iguales | `06`, `# T3.3 · Los tres casos` |
| `t3.4_caida_durante_la_escritura.png` | T3.4 | Registro del escenario A: parada tras el lote 8, caída a mitad de la escritura del lote 15 y repetición del mismo micro-lote al reiniciar | `06`, `# T3.4 · Escenario A` |
| `t3.4_tabla_de_escenarios.png` | T3.4 | Tabla de los tres escenarios con conteo, valor y estado frente a la ejecución limpia y al cálculo por lotes (0 ventanas distintas), y contratos por año en cada escenario | `06`, `# T3.4 · Tabla de los tres escenarios` |

Las capturas de T4.7 son del dashboard y se toman con `scripts/capturar_dashboard.py`; sus comentarios al pie (qué muestra y qué permite concluir) están en `t4.7_capturas_comentadas.md`.

| Archivo | Qué muestra | Dirección del dashboard |
|---|---|---|
| `t4.7_cabecera_sin_filtros.png` | Filtros abiertos, cinco tarjetas con los totales de gold y fecha del último lote procesado | `/` |
| `t4.7_modulo_tiempo.png` | Valor y contratos por mes con las franjas de la ley de garantías y el cierre fiscal, y los picos | `/` |
| `t4.7_modulo_rankings.png` | Top 10 de entidades y de contratistas por valor | `/?n=10&orden=valor` |
| `t4.7_modulo_geografia.png` | Valor por departamento, con «Sin departamento» como categoría aparte | `/` |
| `t4.7_modulo_concentracion.png` | Entidades que reúnen el 50 % y el 80 % del valor, y curva acumulada | `/` |
| `t4.7_filtro_antioquia_2020_2023.png` | Todos los módulos con un departamento y un rango de meses | `/?departamento=Antioquia&desde=2020-01&hasta=2023-12` |
| `t4.7_filtro_una_entidad.png` | Todos los módulos con una sola entidad (el SENA, 2019 a 2025) | `/?entidad=NIT:899999034&desde=2019-01&hasta=2025-12` |
| `t4.7_filtro_sin_resultados.png` | Combinación sin contratos: aviso claro en lugar de un error | `/?departamento=SIN%20DEPARTAMENTO&desde=2015-06&hasta=2015-07` |

La explicación del mecanismo (T3.5) está en `docs/resiliencia_idempotencia.md`, con el diagrama `docs/mecanismo_resiliencia.svg` (PNG para la presentación).

Las evidencias de T0.4 y T1.1 a T1.3 son tablas del `README` y del notebook `04`; las de T2.1 y T2.2, la página de diseño y la lista de lotes del notebook `05`.
