# Pruebas del ESP32 — 2026-11-21 14:54

Puerto: `COM3` · Pruebas: calibracion · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| calibracion | calibrar seco | PASA | aplicada lectura=0 umbrales=200/600 (1.5 s) |
| calibracion | calibrar mojado | PASA | aplicada lectura=2321 umbrales=232/696 (1.5 s) |
| calibracion | calibrar seco | PASA | aplicada lectura=16 umbrales=246/707 (1.0 s) |
| calibracion | repetir la misma condición llega al ESP32 | PASA | lectura=3 umbrales=234/698 (3.1 s) |
