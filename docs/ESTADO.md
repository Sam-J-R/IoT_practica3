# Estado de la Práctica 3 (7 de noviembre de 2026)

Este documento diferencia pruebas reales, verificaciones de código y tareas todavía pendientes. **No equivale a una demo completa en AWS.**

## Confirmado

- Caso de uso: cubierta de tendedero movida por servo; sensor de agua MH analógico para consulta desde Alexa. Sin LED como actuador ni cierre automático local.
- ESP32 compatible con `esp32doit-devkit-v1`; sensor MH en GPIO34 y señal del servo en GPIO26.
- Diagnósticos anteriores de Samuel: 27 lecturas secas consecutivas `raw=0` a intervalos de 500 ms; prueba del ADC con GPIO34 conectado a 3V3 **mediante resistencia de 220 Ω**, 12 lecturas `raw=4095`; al reinstalar el sensor seco regresó a `raw=0`.
- Sensor + Wi-Fi probado localmente: reconexión Wi-Fi tras apagar y reactivar el punto de acceso; esto **no** prueba reconexión MQTT/Shadow.
- Samuel confirmó en conversación del 7/11 que realizó pruebas físicas del servomotor y que respondió correctamente. Faltan adjuntar registro de pulsos, tensión de alimentación, recorrido y evidencia de su montaje con cubierta.
- Pruebas locales con servicios AWS simulados y comprobaciones estáticas: **12/12 pasaron** en esta versión limpia (11/11 en el original). Los tests de Lambda incluyen vincular dos usuarios a dos Things distintos, cambiar y desvincular.
- Los cuatro perfiles PlatformIO (`sensor_test`, `servo_test`, `sensor_shadow_test` y `tendedero_shadow`) compilaron correctamente el 7/11/2026. Esto no demuestra funcionamiento físico ni conexión AWS.
- Código de firmware MQTT TLS/Shadow preparado. `lambda/lambda_deployment_p3.zip` contiene la misma versión de `lambda_function.py` que el código fuente.
- Backend AWS desplegado en `us-east-2`: Things `tendedero-inteligente` y `tendedero-prueba2`, certificado activo del Thing físico, política IoT, endpoint ATS, tabla `tendedero_vinculaciones`, rol IAM y Lambda `tendedero-inteligente-alexa`.
- Pruebas directas desde Lambda satisfactorias: arranque del handler, vinculación persistente, consulta del sensor, escritura de `desired.cubierta`, consulta de cubierta, rechazo de Thing inexistente y desvinculación. El Thing de prueba permitió simular la convergencia `desired`/`reported`.
- CloudWatch no mostró errores en las ejecuciones verificadas; se conservó captura como evidencia. El ARN de Lambda y el modelo fueron entregados a la responsable Alexa; falta recibir el Skill ID y configurar el trigger restringido.

## Aún no demostrado

1. Clasificación del sensor `agua_detectada`: falta umbral calibrado y referencia física/ensayo autorizado. El estímulo eléctrico prueba ADC, no exactitud para agua/lluvia.
2. Valores finales de `calibracion_local.h`: por seguridad no se incluyen datos no verificados ni se adjunta ese archivo local. La plantilla permanece desactivada.
3. Conexión del ESP32 a AWS IoT Core real por TLS; lectura `get`, recepción `delta`, publicación `reported` y recuperación de `desired` pendiente. Los recursos AWS ya existen, pero falta probarlos desde el dispositivo físico.
4. Skill Alexa conectada al backend y validada con voz/texto real. DynamoDB y Lambda ya están desplegadas y probadas mediante eventos directos.
5. RF1–RF9 completos de extremo a extremo; estabilidad ≥10 min, exactitud, latencia objetivo ≤3 s, frecuencia efectiva y reconexión MQTT con Shadow.
6. Fotografías, videos, logs y capturas de AWS/Alexa para el informe; commits por cada integrante y repositorio final accesible.

## Responsabilidades acordadas

- **Samuel:** firmware, sensor, servo, circuito y mediciones físicas.
- **Compañera AWS:** IoT Core, Lambda, DynamoDB, políticas y vinculación.
- **Compañera Alexa:** Skill, intents, slots, frases, simulador y evidencia.

Contrato de integración congelado en [`CONTRATO.md`](CONTRATO.md): región `us-east-2`, Thing físico `tendedero-inteligente`, Thing de prueba `tendedero-prueba2`, tabla `tendedero_vinculaciones` y Shadow clásico. La entrega docente vence el **martes 10/11/2026 a las 17:45, hora Bolivia**.
