# Pruebas del ESP32 — 2026-11-24 00:19

Puerto: `COM3` · Pruebas: calibracion · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| calibracion | calibrar seco | PASA | aplicada lectura=0 umbrales=232/696 (2.2 s) |
| calibracion | calibrar mojado | PASA | aplicada lectura=1422 umbrales=142/426 (1.4 s) |
| calibracion | calibrar seco | PASA | aplicada lectura=0 umbrales=142/426 (1.1 s) |
| calibracion | repetir la misma condición llega al ESP32 | PASA | lectura=0 umbrales=142/426 (2.9 s) |
