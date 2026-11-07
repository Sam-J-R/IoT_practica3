# Estado de la Práctica 3 (7 de noviembre de 2026)

Este documento diferencia pruebas reales, verificaciones de código y tareas todavía pendientes. **No equivale a una demo completa en AWS.**

## Confirmado

- Caso de uso: cubierta de tendedero movida por servo; sensor de agua MH analógico para consulta desde Alexa. Sin LED como actuador ni cierre automático local.
- ESP32 compatible con `esp32doit-devkit-v1`; sensor MH en GPIO34 y señal del servo en GPIO26.
- Diagnósticos anteriores de Samuel: 27 lecturas secas consecutivas `raw=0` a intervalos de 500 ms; prueba del ADC con GPIO34 conectado a 3V3 **mediante resistencia de 220 Ω**, 12 lecturas `raw=4095`; al reinstalar el sensor seco regresó a `raw=0`.
- Sensor + Wi-Fi probado localmente: reconexión Wi-Fi tras apagar y reactivar el punto de acceso; esto **no** prueba reconexión MQTT/Shadow.
- Samuel confirmó en conversación del 7/11 que realizó pruebas físicas del servomotor y que respondió correctamente. Faltan adjuntar registro de pulsos, tensión de alimentación, recorrido y evidencia de su montaje con cubierta.
- Pruebas locales con servicios AWS simulados y comprobaciones estáticas: **12/12 pasaron** en esta versión limpia (11/11 en el original). Los tests de Lambda incluyen vincular dos usuarios a dos Things distintos, cambiar y desvincular.
- Código de firmware MQTT TLS/Shadow preparado. `lambda/lambda_deployment_p3.zip` contiene la misma versión de `lambda_function.py` que el código fuente.

## Aún no demostrado

1. Clasificación del sensor `agua_detectada`: falta umbral calibrado y referencia física/ensayo autorizado. El estímulo eléctrico prueba ADC, no exactitud para agua/lluvia.
2. Valores finales de `calibracion_local.h`: por seguridad no se incluyen datos no verificados ni se adjunta ese archivo local. La plantilla permanece desactivada.
3. Conexión a AWS IoT Core real por TLS; creación de Thing/certificados/política; lectura `get`, recepción `delta`, publicación `reported` y recuperación de `desired` pendiente.
4. Tabla DynamoDB y Lambda desplegadas; Skill Alexa conectada al backend y validada con voz/texto real.
5. RF1–RF9 completos de extremo a extremo; estabilidad ≥10 min, exactitud, latencia objetivo ≤3 s, frecuencia efectiva y reconexión MQTT con Shadow.
6. Fotografías, videos, logs y capturas de AWS/Alexa para el informe; commits por cada integrante y repositorio final accesible.

## Responsabilidades acordadas

- **Samuel:** firmware, sensor, servo, circuito y mediciones físicas.
- **Compañera AWS:** IoT Core, Lambda, DynamoDB, políticas y vinculación.
- **Compañera Alexa:** Skill, intents, slots, frases, simulador y evidencia.

Contrato de integración congelado provisionalmente: [`CONTRATO.md`](CONTRATO.md). La entrega docente vence el **martes 10/11/2026 a las 17:45, hora Bolivia**.
