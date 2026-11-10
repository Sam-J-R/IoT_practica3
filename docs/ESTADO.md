# Estado de la Práctica 3 (actualización de integración: 9 de noviembre de 2026)

Este documento diferencia capturas inspeccionables, ensayos comunicados por el equipo y mediciones. La actualización de Alexa se detalla en [ALEXA.md](ALEXA.md), con [17 capturas](evidencias/alexa/README.md).

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
- CloudWatch no mostró errores en las ejecuciones AWS verificadas. El conjunto AWS publicado registra el trigger restringido al Skill ID; la captura del endpoint y las respuestas del simulador acreditan la conexión de la Skill al backend.
- Skill Custom es-MX configurada con backend propio. Se documentaron apertura, guía sin vínculo, vinculación, persistencia entre conversaciones, rechazo de Thing inexistente, desvinculación, consultas del sensor y cubierta, apertura/cierre y cambio válido de `tendedero-prueba2` a `tendedero-inteligente`.
- El equipo confirmó la integración completa con ESP32, sensor, servo, Shadows y base de datos. También confirmó la aplicación de una orden enviada mientras el ESP32 estaba desconectado, después de volver a conectarlo y sin repetir la solicitud. Es un ensayo de recuperación tras nuevo arranque; las capturas Alexa no se presentan como una grabación del movimiento.
- Las pruebas del simulador se realizaron por texto porque el micrófono no estuvo operativo en el entorno utilizado. Se registra esa modalidad y no se atribuye validación de reconocimiento de voz.

## Alcance de los registros técnicos

1. Se observaron respuestas para ambas clasificaciones del sensor. Los valores numéricos de umbrales y el error de clasificación requieren su propio registro de medición; una consulta satisfactoria no mide exactitud.
2. `calibracion_local.h` y los secretos del dispositivo no se publican; las plantillas permanecen desactivadas por diseño.
3. El ensayo comunicado acredita actuación integrada y recuperación de la posición deseada tras reconectar la alimentación. No se confunde con un ensayo aislado de pérdida de Wi-Fi manteniendo el ESP32 encendido.
4. Las operaciones Alexa se documentan mediante entrada textual. Los registros funcionales no proporcionan por sí solos valores de latencia, estabilidad ni frecuencia efectiva.
5. La [matriz de pruebas](PRUEBAS.md) distingue objetivos de medición, resultados funcionales y observaciones del ensayo sin atribuir valores no medidos.

## Responsabilidades acordadas

- **Samuel:** firmware, sensor, servo, circuito y mediciones físicas.
- **Compañera AWS:** IoT Core, Lambda, DynamoDB, políticas y vinculación.
- **Compañera Alexa:** Skill, intents, slots, frases, simulador y evidencia.

Contrato de integración congelado en [`CONTRATO.md`](CONTRATO.md): región `us-east-2`, Thing físico `tendedero-inteligente`, Thing de prueba `tendedero-prueba2`, tabla `tendedero_vinculaciones` y Shadow clásico. La entrega docente vence el **martes 10/11/2026 a las 17:45, hora Bolivia**.
