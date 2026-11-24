# Pruebas del ESP32 — 2026-11-24 02:06

Puerto: `COM3` · Pruebas: reconexion · Log: `log.csv`

| Prueba | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| reconexion | modo de la prueba | INFO | guiada: sin credenciales de AWS o sin --thing, la orden se da por Alexa o la consola |
| reconexion | intento 1: aplica la orden pendiente (resguardado) | FALLA | Shadow recuperado en 5.9 s |
| reconexion | intento 1: reconexión <= 30 s | PASA | 5.9 s |
| reconexion | intento 2: aplica la orden pendiente (expuesto) | FALLA | Shadow recuperado en 7.1 s |
| reconexion | intento 2: reconexión <= 30 s | PASA | 7.1 s |
| reconexion | intento 3: aplica la orden pendiente (resguardado) | PASA | Shadow recuperado en 6.5 s |
| reconexion | intento 3: reconexión <= 30 s | PASA | 6.5 s |
| reconexion | nota | INFO | wifi_off desasocia al ESP32; repitan al menos una vez apagando el punto de acceso real |
