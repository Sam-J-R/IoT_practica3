# Pruebas del ESP32 — 2026-11-24 00:49

Puerto: `COM3` · Pruebas: edge · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| edge | automático + sensor seco: exponer se acepta | PASA |  |
| edge | R1: con agua en automático resguarda | PASA | agua -> R1 1 ms |
| edge | agua detectada -> servo resguardado <= 2500 ms | PASA | 1088 ms |
| edge | R1 escribe desired.posicion con origen edge | PASA |  |
| edge | con agua en automático, 'exponer' por voz se rechaza | PASA |  |
| edge | el modo cambia a manual por el Shadow | PASA |  |
| edge | en manual, 'exponer' se cumple aunque haya agua | PASA | origen=voz |
