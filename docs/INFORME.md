# Informe técnico — Práctica 3 IoT AWS + Alexa

> **Borrador técnico actualizado 8/11/2026.** El backend AWS está desplegado y probado mediante eventos directos de Lambda. El trigger restringido está configurado y la Skill vinculó y consultó el Thing simulado desde el simulador. Hay pruebas físicas parciales del sensor, Wi-Fi y servo; la integración con el ESP32 y los requisitos no funcionales todavía no tienen validación integral.

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

- [Diagnóstico de sensor](../firmware/src/SensorTest.cpp) y [orquestador Shadow](../firmware/src/Tendedero.cpp) son perfiles separados. [SensorAgua](../firmware/include/SensorAgua.h) muestrea GPIO34 cada 500 ms. La histéresis admite respuesta ascendente o descendente, pero **sus umbrales finales aún no están documentados ni validados físicamente**. La muestra cruda se reporta en cuentas ADC.
- [ServoCubierta](../firmware/include/ServoCubierta.h) genera PWM en D26 solo después de una orden válida, con pulsos, frecuencia y asentamiento del montaje calibrado. Durante un movimiento o antes de la primera orden, la posición local es desconocida. Al cumplirse el asentamiento se reporta una estimación, pendiente de contrastar con el mecanismo durante la demostración presencial.
- [ClienteShadow](../firmware/src/ClienteShadow.cpp) prepara MQTT en TLS mutuo sobre 8883, después de sincronizar reloj por SNTP. Se suscribe a `delta`, respuestas de `get` y respuestas de `update`. En cada conexión solicita el Shadow clásico y aplica la orden vigente. Usa la versión para descartar deltas antiguos y `clientToken` para correlacionar la aceptación de cada reporte. Registra fallos inmediatos de suscripción/publicación y reintenta recuperación. Publica al cambiar la clasificación o posición y periódicamente. Un campo desconocido se retira con `null`; Alexa responde que aún no hay clasificación o posición disponible. **Esta lógica está implementada, pero aún no se ha demostrado contra AWS real.**
- [Lambda](../lambda/lambda_function.py) usa `context.System.user.userId`, con lectura consistente de la tabla. Valida el Thing con `DescribeThing` antes de escribir o reemplazar una vinculación. Usa `reported` para consultas y escribe `desired.cubierta` para órdenes. El mapa de alias incluye `prueba dos`, `prueba 2`, `tendedero prueba dos` y `tendedero prueba 2`, porque durante la prueba Alexa normalizó «dos» como `2`.
- Las [plantillas de AWS](../aws) limitan el certificado a los tópicos del Thing físico y el rol de Lambda a tres operaciones IoT y tres operaciones sobre la tabla. En la cuenta de la práctica, el analizador IAM mostró acceso IoT nulo al restringir por ARN, por lo que se usó `Resource: "*"` solo para `DescribeThing`, `GetThingShadow` y `UpdateThingShadow`; en producción se usarían los ARN exactos de los dos Things. El [modelo Alexa es-MX](../alexa/interaction-model-es-MX.json) usa `AMAZON.SearchQuery` para captar el alias; documentar las frases reconocidas en la Skill real. Los PEM y datos Wi-Fi van en el archivo local ignorado por Git.
- En `us-east-2` se desplegaron `tendedero-inteligente`, `tendedero-prueba2`, la tabla `tendedero_vinculaciones`, el rol de ejecución y la función `tendedero-inteligente-alexa`. El trigger Alexa Skills Kit está limitado al Skill ID real. La Skill usa el ARN como endpoint y la prueba por texto confirmó vinculación y consulta de cubierta sobre `tendedero-prueba2`.

## 4. Pruebas y validaciones

Llenar la matriz `docs/PRUEBAS.md` con capturas, fechas, métricas y errores. Registrar al menos:

- Exactitud: metodología de referencia (consulta pendiente al docente para sensor sin agua).
- Reporte por evento y periódico con timestamps.
- Latencias extremo a extremo Alexa → servo (n≥10 recomendable), no solo Lambda → Shadow.
- 15 minutos de estabilidad objetivo.
- Reconexión Wi-Fi y MQTT, comando deseado pendiente aplicado.
- RF7–RF9 con usuario sin vínculo, Thing inexistente, cambio y borrado de vínculo.

## 5. Resultados

Se documentaron 27 muestras secas `raw=0`, 12 muestras del ADC a `raw=4095` con estímulo de 3V3 limitado por resistencia y reconexión Wi-Fi local. Samuel confirmó el movimiento físico correcto del servo, pero todavía debe anexar parámetros, log y fotografía del montaje; el movimiento se verificará en la demostración. La suite local ejercitó el handler con dos usuarios y AWS simulado. Además, la Lambda desplegada validó un Thing real, persistió la vinculación, leyó `reported`, escribió `desired`, detectó una orden pendiente y rechazó un Thing inexistente; CloudWatch no mostró errores en las ejecuciones revisadas. La Skill real invocó Lambda desde el simulador, vinculó el alias reconocido y consultó la cubierta simulada. Los cuatro perfiles del firmware compilaron correctamente, pero aún no se han cargado y validado como sistema integrado. Quedan por validar la voz si el equipo la presenta, ESP32→AWS, latencia, reconexión MQTT/Shadow y exactitud con referencia autorizada.

### Evidencias AWS consolidadas

![AWS IoT Core: Things y asociaciones del certificado](evidencias/aws/01-iot-core-things-certificado.png)

*Figura AWS-1. Things del proyecto y asociaciones del certificado activo. El ID de cuenta y el identificador del certificado fueron redactados.*

![DynamoDB: tabla y vinculaciones persistidas](evidencias/aws/02-dynamodb-tabla-vinculaciones.png)

*Figura AWS-2. Tabla de vinculaciones e ítems creados por Lambda; los `userId` aparecen truncados.*

![Lambda e IAM](evidencias/aws/03-lambda-iam-configuracion.png)

*Figura AWS-3. Función desplegada, runtime, handler y políticas asociadas al rol.*

![CloudWatch Lambda](evidencias/aws/04-cloudwatch-ejecuciones-lambda.png)

*Figura AWS-4. Eventos de las invocaciones revisadas sin excepciones visibles. Los resultados funcionales se resumen en la tabla AWS-BE de `docs/PRUEBAS.md`.*

![Shadow de prueba y respuesta de Lambda](evidencias/aws/05-backend-shadow-respuesta-lambda.png)

*Figura AWS-5. Shadow clásico simulado de `tendedero-prueba2` y respuesta satisfactoria de `PruebaConsultarCubierta`, coherente con `reported.cubierta = abierta`.*

## 6. Conclusiones

Las pruebas confirman que Alexa invoca Lambda y consulta/controla el Shadow simulado mediante AWS. Todavía no permiten afirmar que Alexa mueve el dispositivo físico; esa conclusión requiere la demostración integrada con el ESP32.

## 7. Recomendaciones

La realimentación de posición permitiría distinguir entre el movimiento estimado y un posible atasco. Evaluar esa extensión con los resultados del montaje.

## 8. Anexos

Diagrama de circuito final, fotografías del prototipo, pruebas y capturas AWS/Alexa, exportaciones de configuraciones, evidencia de commits propios por cada integrante.

