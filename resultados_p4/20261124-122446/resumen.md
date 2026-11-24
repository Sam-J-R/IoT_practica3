# Pruebas del ESP32 — 2026-11-24 12:28

Puerto: `COM3` · Pruebas: arranque, r3 · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| arranque | imprime los umbrales vigentes | PASA | seco=142 agua=426 |
| arranque | recupera el Shadow tras conectar | PASA | 9.2 s desde el reinicio |
| arranque | AWS acepta el primer reporte | PASA |  |
| r3 | modo de la prueba | INFO | guiada: sin --thing o sin credenciales de AWS, la alerta se mira en la consola |
| r3 | alerta sin_reporte <= 11 min | PASA | 3.5 min; hora del Enter (aprox.) |
| r3 | al volver la red reporta otra vez | PASA | Shadow recuperado en 12.8 s |
