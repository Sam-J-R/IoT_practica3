# Pruebas del ESP32 — 2026-11-23 19:54

Puerto: `COM3` · Pruebas: arranque, ordenes, persistencia, frecuencia · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| arranque | imprime los umbrales vigentes | PASA | seco=234 agua=698 |
| arranque | recupera el Shadow tras conectar | PASA | 37.5 s desde el reinicio |
| arranque | AWS acepta el primer reporte | PASA |  |
| ordenes | resguardar: ciclo completo | FALLA | no llegó: delta |
| ordenes | orden -> servo en posición <= 6000 ms | PASA | n=9 media=1829 ms max=2328 ms |
| ordenes | orden -> delta recibido | INFO | n=9 media=835 ms max=1345 ms |
| ordenes | orden -> reporte aceptado | INFO | n=9 media=2314 ms max=2763 ms |
| ordenes | ciclos completos | FALLA | 9 de 10 |
| persistencia | conserva los umbrales tras reiniciar | PASA | antes=('234', '698') después=('234', '698') |
| persistencia | no repite una calibración ya atendida | PASA |  |
| frecuencia | intervalo máximo <= 65 s (con conexión) | PASA | n=5 media=48.6 s max=60.5 s |
| frecuencia | sin reportes rechazados | PASA | 0 rechazados |
