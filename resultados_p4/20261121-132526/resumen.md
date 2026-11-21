# Pruebas del ESP32 — 2026-11-21 13:31

Puerto: `COM3` · Pruebas: arranque, ordenes, persistencia, frecuencia · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| arranque | imprime los umbrales vigentes | PASA | seco=200 agua=600 |
| arranque | recupera el Shadow tras conectar | FALLA | no llegó en 45.0 s |
| ordenes | resguardar: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | exponer: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | resguardar: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | exponer: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | resguardar: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | exponer: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | resguardar: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | exponer: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | resguardar: publicada | FALLA | el firmware no tiene MQTT activo |
| ordenes | exponer: publicada | FALLA | el firmware no tiene MQTT activo |
| persistencia | conserva los umbrales tras reiniciar | PASA | antes=('200', '600') después=('200', '600') |
| persistencia | no repite una calibración ya atendida | PASA |  |
| frecuencia | intervalo máximo <= 65 s | PASA | n=4 media=60.5 s max=60.7 s |
| frecuencia | sin reportes rechazados | PASA | 0 rechazados |
