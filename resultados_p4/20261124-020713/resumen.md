# Pruebas del ESP32 — 2026-11-24 02:08

Puerto: `COM3` · Pruebas: sin_conexion · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| sin_conexion | automático + sensor seco: exponer se acepta | PASA |  |
| sin_conexion | R1 resguarda sin conexión | FALLA | no actuó sin red |
| sin_conexion | sin conexión no intenta publicar | PASA |  |
| sin_conexion | al reconectar escribe la decisión pendiente en desired | PASA | 7.6 s tras wifi_on |
| sin_conexion | el desired viejo (expuesto) no saca la ropa | PASA |  |
