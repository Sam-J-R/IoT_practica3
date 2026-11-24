# Pruebas de AWS desde la consola

- **Fecha:** 23 de noviembre de 2026, entre las 00:20 y las 01:35 UTC (horas de los logs de CloudWatch).
- **Responsable:** María Lozada (encargada de AWS).
- **Cuenta y región:** cuenta del equipo, `us-east-2`.
- **Procedimiento:** [docs/practica4/PRUEBAS_AWS.md](../docs/practica4/PRUEBAS_AWS.md). **Capturas:** [docs/evidencias/p4/aws/](../docs/evidencias/p4/aws/README.md). Los eventos usados están en [aws/eventos-prueba/](../aws/eventos-prueba).
- **Thing:** `tendedero-prueba2` (sin ESP32), con el Shadow simulado de [aws/shadow-prueba2.example.json](../aws/shadow-prueba2.example.json). Usuario de Alexa de prueba: `amzn1.ask.account.PRUEBA-CONSOLA`.

**Resultado: 25 de 25 pruebas pasan.**

## Lambda de Alexa (`tendedero-inteligente-alexa`, pestaña Test)

| # | Prueba | Evento | Respuesta obtenida | Verificación adicional | Resultado |
|---|---|---|---|---|---|
| 1 | Vincular con código y nombre | `alexa-01-vincular` | «He vinculado tu tendedero terraza. Ahora puedes consultar el agua, moverlo o calibrar el sensor.» | Ítem en `tendedero_vinculaciones` con `thingName = tendedero-prueba2` y `nombre = terraza` | PASA |
| 2 | Listar tendederos | `alexa-02-listar` | «Tienes un tendedero vinculado: terraza.» | — | PASA |
| 3 | Consultar agua | `alexa-03-consultar-agua` | «El sensor no detecta agua.» | — | PASA |
| 4 | Cómo está el tendedero (motivo) | `alexa-04-como-esta` | «Según el último reporte, el tendedero está expuesto y recibiendo luz. Se resguardará solo si llueve o anochece.» | Usa `posicion`, `oscuro` y `modo` | PASA |
| 5 | Cambiar a modo manual | `alexa-05-modo-manual` | «He activado el modo manual. El tendedero solo se moverá con tus órdenes, aunque llueva o anochezca.» | `desired.modo = manual` | PASA |
| 6 | Resguardar | `alexa-06-resguardar` | «He solicitado que el tendedero quede resguardado. Espera la confirmación del dispositivo.» | `desired.posicion = resguardado`, `desired.origen = voz` | PASA |
| 7 | Exponer | `alexa-07-exponer` | «He solicitado que el tendedero quede expuesto. Espera la confirmación del dispositivo.» | `desired.posicion = expuesto` | PASA |
| 8 | Configurar espera | `alexa-08-espera-45` | «Listo. En modo automático, la ropa volverá a exponerse después de 45 minutos sin agua, cuando haya luz.» | `desired.minutos_reexponer = 45` | PASA |
| 9 | Encender la luz | `alexa-09-encender-luz` | «He pedido encender la luz del tendedero. Se apagará sola en 10 minutos.» | `desired.led = encendido`, sin `desired.origen_led` | PASA |
| 10 | Cambiar a modo automático | `alexa-10-modo-automatico` | «He activado el modo automático. El tendedero resguardará la ropa si llueve o anochece, y la volverá a exponer cuando haya luz y no llueva.» | `desired.modo = automatico` | PASA |
| 11 | Consultar modo | `alexa-11-consultar-modo` | «El tendedero está en modo automático. Resguarda la ropa si llueve o anochece, y la vuelve a exponer después de 30 minutos sin agua, cuando hay luz.» | Lee `reported`: sin ESP32, la espera sigue en 30 | PASA |
| 12 | Desvincular | `alexa-12-desvincular` | «He eliminado la vinculación de tu tendedero.» | El ítem ya no está en `tendedero_vinculaciones` | PASA |

## Un usuario con dos tendederos (pestaña Test de la Lambda de Alexa)

Mismo usuario de prueba, entre las pruebas 11 y 12. El segundo tendedero es `tendedero-inteligente`, código `483920`. Ninguna de estas pruebas mueve el tendedero físico.

| # | Prueba | Evento | Respuesta obtenida | Verificación adicional | Resultado |
|---|---|---|---|---|---|
| 21 | Vincular un segundo tendedero | `alexa-13-vincular-segundo` | «He vinculado tu tendedero patio. Ahora tienes 2 tendederos: patio y terraza. En cada orden di en cuál…» | `tendedero_vinculaciones`: dos ítems con el mismo `userId` («patio» y «terraza»). Captura `02-vinculaciones-dos-tendederos.jpg` | PASA |
| 22 | Orden sin decir en cuál | `alexa-14-agua-sin-nombre` | «¿En cuál tendedero? Tienes patio o terraza.» | La respuesta trae `Dialog.ElicitSlot` sobre el slot `nombre` | PASA |
| 23 | Orden nombrando el tendedero | `alexa-15-agua-del-patio` | «Tendedero patio: El sensor…» | La respuesta empieza con el nombre del tendedero | PASA |
| 24 | Desvincular uno por nombre | `alexa-16-desvincular-patio` | «He desvinculado el tendedero patio. Tu tendedero se llama terraza.» | Queda un solo ítem del usuario | PASA |
| 25 | Desvincular el último | `alexa-12-desvincular` | «He eliminado la vinculación de tu tendedero.» | Con un solo tendedero no pregunta cuál | PASA |

Nota: las pruebas 21 a 25 se agregaron después de la prueba 12 de la tabla anterior. En la ejecución, la prueba 12 se hizo al final, como prueba 25.

## Lambdas de la Nube (pestaña Test)

| # | Prueba | Función y evento | Respuesta obtenida | Resultado |
|---|---|---|---|---|
| 13 | Guardar una lectura | `tendedero_almacenamiento` · `almacenamiento-lectura` | `{"guardados": 1}`. La lectura no incluye `posicion` ni `modo` | PASA |
| 14 | Guardar eventos | `tendedero_almacenamiento` · `almacenamiento-cambio-lluvia` | `{"guardados": 2}`: eventos de agua y de posición | PASA |
| 15 | Descartar un dato inválido | `tendedero_almacenamiento` · `almacenamiento-invalido` | `{"guardados": 0, "descartado": "lectura_adc=9999 fuera de rango 0..4095"}` | PASA |
| 16 | R4 (exceso de movimientos) | `tendedero_logica` · `logica-movimiento` | `{"accion": "ninguna", "movimientos": 3}` | PASA |
| 17 | R2 y R3 (supervisor) | `tendedero_supervisor` · `supervisor` | `{"revisados": 2, "sin_reporte": 1, "reexpuestos": 0}` | PASA |

- **Prueba 16:** R4 cuenta los movimientos de la hora anterior al mensaje, más el del mensaje. Encontró 2 eventos de posición guardados por las pruebas anteriores de esa ventana de tiempo, más este: 3 en total. Como no supera el límite de 6, no actúa. Sin errores de permisos sobre DynamoDB.
- **Prueba 17:** revisó los dos tendederos registrados. `tendedero-prueba2` tenía lecturas recientes de las pruebas MQTT, así que está conectado. `tendedero-inteligente` no tenía al ESP32 conectado, así que R3 lo marcó como `sin_reporte` y registró la alerta en el histórico. R2 no expuso ninguno, porque ninguno cumplía las condiciones (resguardado por el Edge, sin agua y con luz).

## Reglas de AWS IoT de punta a punta (MQTT test client)

Publicando en `$aws/things/tendedero-prueba2/shadow/update`, como lo haría el ESP32:

| # | Prueba | Publicación | Resultado en `tendedero_historico` y CloudWatch | Resultado |
|---|---|---|---|---|
| 18 | Regla `tendedero_lecturas` | 4.1: expuesto, seco, `lectura_adc` 120, `nivel_luz` 80 | 1 lectura (`agua_detectada = false`, 120, 80), sin `posicion` ni `modo`. No hubo eventos: nada cambió respecto del Shadow anterior | PASA |
| 19 | Regla `tendedero_cambios` | 4.2: resguardado por `edge` con lluvia, `lectura_adc` 1800, `nivel_luz` 60 | 1 lectura (`true`, 1800, 60) + evento `agua` + evento `posicion` con `agua_detectada = true`. Dos invocaciones simultáneas de la Lambda (una por regla), visibles en dos log streams a las 01:28:30 UTC. La regla `tendedero_movimientos` también invocó a `tendedero_logica` | PASA |
| 20 | Descarte de un mensaje inválido | 4.3: `lectura_adc` 9999 | No se guardó ninguna lectura. CloudWatch: `Mensaje descartado: lectura_adc=9999 fuera de rango 0..4095` | PASA |

## Observaciones

- Cada publicación genera **siempre una lectura** y **un evento por cada dato que cambió**. Por eso la publicación 4.1 dejó un ítem y la 4.2 dejó tres.
- Las reglas de AWS IoT no tienen logs propios: su ejecución se comprueba en los logs de la Lambda que invocan y en las **Invocations** de la pestaña Monitor.
