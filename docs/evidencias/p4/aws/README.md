# Evidencias de AWS (práctica 4)

Capturas tomadas el 22 de noviembre de 2026 (hora de Bolivia, UTC−4) durante las pruebas de [docs/practica4/PRUEBAS_AWS.md](../../../practica4/PRUEBAS_AWS.md). Los resultados están en [resultados_p4/pruebas-aws-consola.md](../../../../resultados_p4/pruebas-aws-consola.md).

Se revisó que ninguna muestre claves, certificados ni el número de cuenta. En `09-eventbridge.jpg`, el número de cuenta del ARN quedó tapado.

## Configuración

| Captura | Qué muestra |
|---|---|
| [01-tablas.jpg](01-tablas.jpg) | Las tres tablas activas: `tendedero_dispositivos` (`thingName`), `tendedero_historico` (`thingName` + `sk`, aprovisionada) y `tendedero_vinculaciones` (`userId` + `thingName`) |
| [02-vinculaciones-dos-tendederos.jpg](02-vinculaciones-dos-tendederos.jpg) | Un mismo usuario con dos tendederos: `tendedero-inteligente` («patio») y `tendedero-prueba2` («terraza») |
| [03-historico-lecturas.jpg](03-historico-lecturas.jpg) | Lecturas (`lectura#…`) solo con datos de los sensores: `agua_detectada`, `lectura_adc`, `nivel_luz` |
| [04-historico-eventos.jpg](04-historico-eventos.jpg) | Eventos de agua y de posición. El de posición guarda `origen = edge`, `oscuro = false` y la posición `resguardado` |
| [05-historico-alertas.jpg](05-historico-alertas.jpg) | Alertas `sin_reporte` de R3 (`alerta#…`) |
| [06-reglas.jpg](06-reglas.jpg) | Las tres reglas de AWS IoT activas y su tema del Shadow |
| [07-regla-cambios-sql.jpg](07-regla-cambios-sql.jpg) | El SQL de `tendedero_cambios`, sin filtro: la Lambda compara los documentos |
| [08-lambdas.jpg](08-lambdas.jpg) | Las cuatro Lambdas: Alexa, almacenamiento, lógica y supervisor |
| [09-eventbridge.jpg](09-eventbridge.jpg) | El disparador del supervisor: `rate(5 minutes)`, activo |
| [10-roles.jpg](10-roles.jpg) | Un rol de IAM por Lambda (`tendedero-*-lambda-role`) |
| [11-shadow-fisico.jpg](11-shadow-fisico.jpg) | El Shadow de `tendedero-inteligente` con los campos de la P4 (modo, espera, calibración, LED, `oscuro`, origen) |
| [12-cloudwatch-descarte.jpg](12-cloudwatch-descarte.jpg) | CloudWatch de `tendedero_almacenamiento`: `Guardados 2 items` y, en la prueba 4.3, dos `Mensaje descartado` (uno por cada regla) |
| [13-facturacion.jpg](13-facturacion.jpg) | Presupuesto *Zero-Spend* creado |

## Pruebas

| Captura | Prueba (en `resultados_p4/pruebas-aws-consola.md`) |
|---|---|
| [20-test-alexa-vincular.jpg](20-test-alexa-vincular.jpg) | 1. Vincular con código y nombre |
| [21-test-alexa-como-esta.jpg](21-test-alexa-como-esta.jpg) | 4. «Cómo está el tendedero», con el motivo |
| [22-shadow-desired.jpg](22-shadow-desired.jpg) | 5 a 9. `desired` de `tendedero-prueba2` después de las órdenes de voz (sin `origen_led`) |
| [23-vinculaciones-un-tendedero.jpg](23-vinculaciones-un-tendedero.jpg) | 1. El ítem del usuario de prueba antes de desvincular |
| [24-test-almacenamiento-invalido.jpg](24-test-almacenamiento-invalido.jpg) | 15. Descarte de un dato inválido en la pestaña Test |
| [25-historico-lectura-y-eventos.jpg](25-historico-lectura-y-eventos.jpg) | 18 y 19. Lecturas y eventos que dejaron las publicaciones por MQTT, junto con las alertas `sin_reporte` |

Falta una captura del resultado del supervisor (prueba 17). Su respuesta quedó registrada en la tabla de resultados.
