# Índice de ensayos RNF — 10/11/2026

Registros generados por `ensayo_rnf.py` con el firmware `tendedero_ensayo`, ESP32 en COM3. Horas de Bolivia (UTC−4), tomadas del reloj del PC. La tabla consolidada está en [docs/RESULTADOS_RNF.md](../docs/RESULTADOS_RNF.md); `resumen.md` es la tabla automática y solo guarda el último ensayo de cada requisito.

## Sesiones

| Log | Hora | Ensayo | Resultado | Informe |
|---|---|---|---|---|
| `log-20261110-094834.csv` | 09:48–10:05 | `todo`: respuesta, estabilidad, frecuencia y Wi-Fi | Respuesta y estabilidad completas. Wi-Fi interrumpido: el firmware cargado no tenía `wifi_off`. | [rnf-02](rnf-02-respuesta-20261110-094834.md), [rnf-01](rnf-01-estabilidad-20261110-094834.md), [rnf-04 con carga](rnf-04-frecuencia-20261110-094834.md) |
| `log-20261110-101323.csv` | 10:13 | Wi-Fi | Interrumpido: mismo motivo, firmware sin `wifi_off`. | — |
| `log-20261110-101722.csv`, `log-20261110-101906.csv` | 10:17, 10:19 | — | Vacíos (0 bytes). Ejecuciones que terminaron antes de registrar datos; no se usan. | — |
| `log-20261110-101936.csv` | 10:19–10:21 | Wi-Fi | Completo, 3 repeticiones. | [rnf-06](rnf-06-reconexion-wifi-20261110-101936.md) |
| `log-20261110-102329.csv` | 10:23–10:31 | Reinicio | Interrumpido. Repetición 1 correcta; la 2 no conectó a MQTT en 270 s; disco del PC lleno a las 10:29. | Notas en [rnf-05](rnf-05-reinicio-20261110-103933.md) |
| `log-20261110-103639.csv` | 10:36–10:38 | Reinicio | Interrumpido antes de empezar: el ESP32 no encontraba la red (`sin wifi estado=1`). | Notas en [rnf-05](rnf-05-reinicio-20261110-103933.md) |
| `log-20261110-103933.csv` | 10:39–10:42 | Reinicio | Completo, 3 repeticiones. | [rnf-05](rnf-05-reinicio-20261110-103933.md) |
| `log-20261110-104652.csv` | 10:46–10:52 | Sensor | Completo, 20 observaciones. | [rnf-03](rnf-03-sensor-20261110-104652.md) |
| `log-20261110-111031.csv` | 11:10–11:15 | Frecuencia pasiva | Completo, 5 min. | [rnf-04 pasivo](rnf-04-frecuencia-20261110-111031.md) |

## Archivos por ensayo

Cada ensayo completo tiene un informe `.md` (objetivo, procedimiento, condiciones, mediciones, veredicto y limitaciones) y un `.csv` con la tabla de mediciones. Los `rnf-05-repN-pendiente-*.json` y `rnf-06-repN-pendiente-*.json` son el documento del Shadow leído por el PC durante cada interrupción: muestran `desired` con la orden nueva, `reported` con la posición anterior y el `delta`. Sustituyen a las capturas de la consola AWS, a la que no se tenía acceso. Los JSON con sesión `102329` corresponden al ensayo interrumpido.

Los logs no contienen credenciales: solo líneas del monitor serie, marcas de tiempo y respuestas del Shadow.

## Correspondencia de numeración

Los archivos siguen la numeración de la guía de mediciones; el informe técnico usa otra.

| Archivo | Guía de mediciones | Informe técnico (§1.3) |
|---|---|---|
| `rnf-01-estabilidad` | Estabilidad | RNF1 |
| `rnf-02-respuesta` | Tiempo de respuesta | RNF3 |
| `rnf-03-sensor` | Clasificación del sensor | RNF2 |
| `rnf-04-frecuencia` | Frecuencia de reporte | RNF4 |
| `rnf-05-reinicio` | Recuperación tras reinicio | RNF5 (reinicio) |
| `rnf-06-reconexion-wifi` | Reconexión de red | RNF5 (pérdida de Wi-Fi) |
