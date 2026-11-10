# Registros previos a la automatización

Capturas del monitor serie del 10/11/2026, entre las 00:00 y las 00:45 (hora de Bolivia), hechas con `grabar_rnf.py` antes de disponer de `ensayo_rnf.py`. Formato: `fuente, epoch, hora, dato`, analizable con `analizar_rnf.py`.

| Archivo | Contenido | Uso |
|---|---|---|
| `rnf-eventos.csv` | 00:00–00:38. Incluye un error de transporte MQTT espontáneo a las 00:06:00 y la reconexión posterior. | Observación de incidencia, no ensayo controlado. |
| `rnf-prueba.csv` | 00:12–00:16. Dos cambios de clasificación del sensor con su reporte por evento. | Observación preliminar. |
| `rnf-01.csv` | 00:20–00:39. 19 min de serie sin reinicios, sin órdenes ni consultas. | Estabilidad parcial; no sustituye al ensayo con carga. |
| `rnf-04.csv` | 00:39–00:43. 30 intervalos de reporte. | Frecuencia preliminar. |

En estos registros la fuente `mqtt_estado` solo muestra `desconectado`: el monitor del PC usaba otro clientId y la política del certificado lo rechazaba. No hay marcas de inicio ni fin, por lo que no se usan como resultado de ningún RNF; los resultados válidos están en [`../INDICE.md`](../INDICE.md). Su análisis se resume en [ENSAYOS_RNF_SIN_CONSOLA.md §3](../../docs/ENSAYOS_RNF_SIN_CONSOLA.md#3-lo-que-ya-está-medido-en-los-registros-existentes).
