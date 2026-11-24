# Pruebas del ESP32 — 2026-11-21 14:51

Puerto: `COM3` · Pruebas: arranque, ordenes, persistencia, frecuencia · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| arranque | imprime los umbrales vigentes | PASA | seco=200 agua=600 |
| arranque | recupera el Shadow tras conectar | PASA | 6.4 s desde el reinicio |
| arranque | AWS acepta el primer reporte | PASA |  |
| ordenes | orden -> servo en posición <= 6000 ms | PASA | n=10 media=1640 ms max=2495 ms |
| ordenes | orden -> delta recibido | INFO | n=10 media=652 ms max=1517 ms |
| ordenes | orden -> reporte aceptado | INFO | n=10 media=1913 ms max=2822 ms |
| ordenes | ciclos completos | PASA | 10 de 10 |
| persistencia | conserva los umbrales tras reiniciar | PASA | antes=('200', '600') después=('200', '600') |
| persistencia | no repite una calibración ya atendida | PASA |  |
| frecuencia | intervalo máximo <= 65 s | FALLA | n=4 media=64.1 s max=134.5 s |
| frecuencia | sin reportes rechazados | PASA | 0 rechazados |
