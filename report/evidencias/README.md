# Evidencias para el informe (T2.3 a T3.1)

Capturas de las salidas guardadas en los notebooks `05` y `06`, tal como quedaron en `main` el 15-nov-2026. No hubo que volver a ejecutar nada: si se vuelven a correr los notebooks, las cifras deben ser las mismas.

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

Las evidencias de T0.4 y T1.1 a T1.3 son tablas del `README` y del notebook `04`; las de T2.1 y T2.2, la página de diseño y la lista de lotes del notebook `05`.
