# Pruebas del ESP32 — 2026-11-24 10:03

Puerto: `COM3` · Pruebas: arranque, ordenes · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| arranque | imprime los umbrales vigentes | PASA | seco=142 agua=426 |
| arranque | recupera el Shadow tras conectar | PASA | 7.0 s desde el reinicio |
| arranque | AWS acepta el primer reporte | PASA |  |
| ordenes | resguardar: ciclo completo | FALLA | no llegó: delta |
| ordenes | exponer: ciclo completo | FALLA | no llegó: servo |
| ordenes | resguardar: ciclo completo | FALLA | no llegó: delta |
| ordenes | exponer: ciclo completo | FALLA | no llegó: delta |
| ordenes | resguardar: ciclo completo | FALLA | no llegó: delta |
| ordenes | exponer: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | resguardar: ciclo completo | FALLA | no llegó: delta |
| ordenes | exponer: ciclo completo | FALLA | no llegó: servo |
| ordenes | resguardar: ciclo completo | FALLA | no llegó: delta |
| ordenes | exponer: ciclo completo | FALLA | no llegó: servo |
