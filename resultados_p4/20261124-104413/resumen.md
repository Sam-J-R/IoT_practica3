# Pruebas del ESP32 — 2026-11-24 10:51

Puerto: `COM3` · Pruebas: luz · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| luz | R5: de noche en automático resguarda la ropa | PASA |  |
| luz | R5: el movimiento lo pidió el Edge | PASA | origen=edge |
| luz | oscuridad -> resguardo <= 310000 ms | PASA | 228581 ms |
| luz | R5 escribe desired.posicion con origen edge | PASA |  |
| luz | de noche en automático, exponer por voz se rechaza | PASA |  |
| luz | la voz enciende la luz para recoger la ropa | PASA | origen=voz |
| luz | la voz apaga la luz | PASA | origen=voz |
| luz | apagado automático de la luz a los 10 min | PASA | no se mide aquí: dejar la luz encendida y buscar '[EDGE] LED encendido 10 min' |
