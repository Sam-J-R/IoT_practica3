# Informe técnico — Práctica 3 IoT AWS + Alexa

> **Actualización de Alexa e integración: 9/11/2026.** Se documentan configuración y operaciones del simulador mediante 17 capturas. El equipo confirmó integración con ESP32, sensor, servo, Shadows y DynamoDB, además de recuperación de una orden tras reconectar el dispositivo. Las observaciones funcionales se distinguen de los resultados numéricos de requisitos no funcionales. Véase [ALEXA.md](ALEXA.md).

## 1. Caso de uso y requerimientos

Sistema distribuido que detecta de forma binaria la presencia de agua o lluvia mediante un sensor resistivo MH y permite al usuario ordenar por voz abrir/cerrar una cubierta móvil protectora de un tendedero. No se intenta medir cantidad, volumen ni porcentaje de agua: `sensor_raw` conserva la lectura ADC para calibración y diagnóstico, mientras que Alexa consulta exclusivamente `agua_detectada`. El ESP32 publica el sensor, y Alexa consulta/controla a través de Lambda y AWS IoT Core Device Shadow. No se implementa cierre automático local porque la práctica pide comandos por voz.

### RF

Trazabilidad RF1–RF9 con `docs/PRUEBAS.md` y `referencias/Práctica_3.md`.

### RNF

Declarar explícitamente objetivos, unidad, método y resultados medidos. No copiar las referencias del docente como resultados reales.

## 2. Análisis y diseño

- Diagrama arquitectura: `docs/DIAGRAMAS.md`.
- [Circuito previsto](DIAGRAMAS.md#circuito-previsto). Confirmar la unidad MG90S, nivel de señal, fuente y recorrido con el montaje real.
- [Clases del ESP32 y de Lambda](DIAGRAMAS.md#clases-del-esp32).
- Secuencias mínimas: vinculación, consulta de sensor, comando actuador (ver `docs/DIAGRAMAS.md`).
- Device Shadow: `docs/CONTRATO.md`; documentar atributos, tipos, valores y secciones desired/reported/delta.
- Vinculación: en `us-east-2`, clave `userId`, tabla `tendedero_vinculaciones`, Thing físico `tendedero-inteligente`, Thing de prueba `tendedero-prueba2`, `DescribeThing`, cambiar/eliminar.
- Alexa: `alexa/interaction-model-es-MX.json` y las frases efectivamente probadas.

## 3. Desarrollo e implementación

- [Diagnóstico de sensor](../firmware/src/SensorTest.cpp) y [orquestador Shadow](../firmware/src/Tendedero.cpp) son perfiles separados. [SensorAgua](../firmware/include/SensorAgua.h) muestrea GPIO34 cada 500 ms. La histéresis admite respuesta ascendente o descendente. Las capturas Alexa muestran clasificación seca y con agua; los umbrales locales y el error físico son datos del ensayo del sensor. La muestra cruda se reporta en cuentas ADC.
- [ServoCubierta](../firmware/include/ServoCubierta.h) genera PWM en D26 solo después de una orden válida, con pulsos, frecuencia y asentamiento del montaje calibrado. Durante un movimiento o antes de la primera orden, la posición local es desconocida. Al cumplirse el asentamiento se reporta una estimación; el equipo confirmó movimiento durante el ensayo integrado. No existe realimentación independiente de posición.
- [ClienteShadow](../firmware/src/ClienteShadow.cpp) prepara MQTT en TLS mutuo sobre 8883, después de sincronizar reloj por SNTP. Se suscribe a `delta`, respuestas de `get` y respuestas de `update`. En cada conexión solicita el Shadow clásico y aplica la orden vigente. Usa la versión para descartar deltas antiguos y `clientToken` para correlacionar la aceptación de cada reporte. Registra fallos inmediatos de suscripción/publicación y reintenta recuperación. Publica al cambiar la clasificación o posición y periódicamente. Un campo desconocido se retira con `null`. El equipo confirmó actuación integrada y recuperación de una orden tras reconectar el ESP32, sin repetir la solicitud.
- [Lambda](../lambda/lambda_function.py) usa `context.System.user.userId`, con lectura consistente de la tabla. Valida el Thing con `DescribeThing` antes de escribir o reemplazar una vinculación. Usa `reported` para consultas y escribe `desired.cubierta` para órdenes. El mapa de alias configurado permite vincular nombres hablados de varios Things.
- Las [plantillas de AWS](../aws) limitan el certificado a los tópicos del Thing físico y el rol de Lambda a tres operaciones IoT y tres operaciones sobre la tabla. En la cuenta de la práctica, el analizador IAM mostró acceso IoT nulo al restringir por ARN, por lo que se usó `Resource: "*"` solo para `DescribeThing`, `GetThingShadow` y `UpdateThingShadow`; en producción se usarían los ARN exactos de los dos Things. El [modelo Alexa es-MX](../alexa/interaction-model-es-MX.json) usa `AMAZON.SearchQuery` para captar el alias; documentar las frases reconocidas en la Skill real. Los PEM y datos Wi-Fi van en el archivo local ignorado por Git.
- En `us-east-2` se desplegaron `tendedero-inteligente`, `tendedero-prueba2`, la tabla `tendedero_vinculaciones`, el rol de ejecución y la función `tendedero-inteligente-alexa`. El conjunto AWS publicado documenta el trigger restringido al Skill ID. La captura del endpoint y las respuestas del simulador acreditan la conexión de la Skill.
- [Configuración y validación de Alexa](ALEXA.md): Skill Custom es-MX, backend propio, alias para variantes `dos`/`2` y operaciones de vinculación, persistencia, consulta, control, rechazo de inexistente, cambio válido y eliminación. Las [17 capturas](evidencias/alexa/README.md) se conservan con sus nombres originales. La entrada fue textual porque el micrófono no estuvo operativo en el entorno utilizado.

## 4. Pruebas y validaciones

La matriz [PRUEBAS.md](PRUEBAS.md) y el [registro Alexa](ALEXA.md) distinguen respuestas capturadas, ensayos físicos comunicados y mediciones. Las métricas se registran con los siguientes criterios:

- Exactitud: metodología de referencia (consulta pendiente al docente para sensor sin agua).
- Reporte por evento y periódico con timestamps.
- Latencias extremo a extremo Alexa → servo (n≥10 recomendable), no solo Lambda → Shadow.
- 15 minutos de estabilidad objetivo.
- Reconexión Wi-Fi y MQTT, comando deseado pendiente aplicado.
- RF7–RF9 documentados con capturas de usuario sin vínculo, persistencia, Thing inexistente, cambio válido y borrado de vínculo.

## 5. Resultados

El registro previo incluye 27 muestras secas `raw=0`, 12 muestras del ADC a `raw=4095` con estímulo eléctrico y reconexión Wi-Fi local. La suite simulada ejercitó el handler con dos usuarios. La Lambda desplegada validó Things, persistió vínculos, leyó `reported` y escribió `desired`. El [conjunto AWS ya publicado](https://github.com/Sam-J-R/IoT_practica3/blob/a8a86c3f56a39b063bacd5fe4cc651dabfe73232/docs/EVIDENCIAS_AWS.md) conserva sus paneles, CSV y resultados directos.

La actualización Alexa incorpora respuestas reales del simulador, persistencia entre conversaciones, rechazo de identificador inexistente, eliminación y cambio válido de `tendedero-prueba2` a `tendedero-inteligente`. El equipo confirmó la integración física y la recuperación de una orden tras reconectar el ESP32. Se registra la observación del ensayo sin atribuir a las imágenes del simulador una medición temporal o una fotografía del movimiento. No se inventan valores de latencia, exactitud ni estabilidad.

## 6. Conclusiones

Las pruebas documentadas respaldan la configuración de Alexa y sus operaciones sobre el Thing vinculado, incluida persistencia y cambio de objeto. El ensayo comunicado por el equipo confirma el control del dispositivo mediante AWS y la aplicación de una posición solicitada durante una desconexión, después del nuevo arranque. Se distingue entre solicitud, estado reportado estimado y observación física. La modalidad utilizada fue textual por la limitación de micrófono del entorno.

## 7. Recomendaciones

La realimentación de posición permitiría distinguir entre el movimiento estimado y un posible atasco. Evaluar esa extensión con los resultados del montaje.

## 8. Anexos

Diagrama de circuito final, fotografías del prototipo, pruebas y capturas AWS/Alexa, exportaciones de configuraciones, evidencia de commits propios por cada integrante.

