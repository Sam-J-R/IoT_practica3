# Pruebas del ESP32 — 2026-11-24 14:34

Puerto: `COM3` · Pruebas: arranque, ordenes, persistencia, frecuencia · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| arranque | imprime los umbrales vigentes | PASA | seco=216 agua=648 |
| arranque | recupera el Shadow tras conectar | PASA | 5.5 s desde el reinicio |
| arranque | AWS acepta el primer reporte | PASA |  |
| ordenes | orden -> servo en posición <= 6000 ms | PASA | n=10 media=1857 ms max=2814 ms |
| ordenes | orden -> delta recibido | INFO | n=10 media=858 ms max=1839 ms |
| ordenes | orden -> reporte aceptado | INFO | n=10 media=2184 ms max=3139 ms |
| ordenes | ciclos completos | PASA | 10 de 10 |
| persistencia | conserva los umbrales tras reiniciar | PASA | antes=('216', '648') después=('216', '648') |
| persistencia | no repite una calibración ya atendida | PASA |  |
| frecuencia | intervalo máximo <= 65 s (con conexión) | PASA | n=15 media=56.6 s max=61.7 s |
| frecuencia | sin reportes rechazados | PASA | 0 rechazados |
