# Informe técnico — Práctica 3 IoT AWS + Alexa

> **Borrador técnico actualizado 7/11/2026.** El backend AWS está desplegado y probado mediante eventos directos de Lambda. Hay pruebas físicas parciales del sensor, Wi-Fi y servo; la integración con Alexa, el ESP32 y los requisitos no funcionales siguen pendientes de validación integral.

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
- [ServoCubierta](../firmware/include/ServoCubierta.h) genera PWM en D26 solo después de una orden válida, con pulsos, frecuencia y asentamiento del montaje calibrado. Durante un movimiento o antes de la primera orden, la posición local es desconocida. Al cumplirse el asentamiento se reporta una estimación, pendiente de contrastar con video del mecanismo.
- [ClienteShadow](../firmware/src/ClienteShadow.cpp) prepara MQTT en TLS mutuo sobre 8883, después de sincronizar reloj por SNTP. Se suscribe a `delta`, respuestas de `get` y respuestas de `update`. En cada conexión solicita el Shadow clásico y aplica la orden vigente. Usa la versión para descartar deltas antiguos y `clientToken` para correlacionar la aceptación de cada reporte. Registra fallos inmediatos de suscripción/publicación y reintenta recuperación. Publica al cambiar la clasificación o posición y periódicamente. Un campo desconocido se retira con `null`; Alexa responde que aún no hay clasificación o posición disponible. **Esta lógica está implementada, pero aún no se ha demostrado contra AWS real.**
- [Lambda](../lambda/lambda_function.py) usa `context.System.user.userId`, con lectura consistente de la tabla. Valida el Thing con `DescribeThing` antes de escribir o reemplazar una vinculación. Usa `reported` para consultas y escribe `desired.cubierta` para órdenes. El mapa de alias configurado permite vincular nombres hablados de varios Things.
- Las [plantillas de AWS](../aws) limitan el certificado a los tópicos del Thing físico y el rol de Lambda a tres operaciones IoT y tres operaciones sobre la tabla. En la cuenta de la práctica, el analizador IAM mostró acceso IoT nulo al restringir por ARN, por lo que se usó `Resource: "*"` solo para `DescribeThing`, `GetThingShadow` y `UpdateThingShadow`; en producción se usarían los ARN exactos de los dos Things. El [modelo Alexa es-MX](../alexa/interaction-model-es-MX.json) usa `AMAZON.SearchQuery` para captar el alias; documentar las frases reconocidas en la Skill real. Los PEM y datos Wi-Fi van en el archivo local ignorado por Git.
- En `us-east-2` se desplegaron `tendedero-inteligente`, `tendedero-prueba2`, la tabla `tendedero_vinculaciones`, el rol de ejecución y la función `tendedero-inteligente-alexa`. La responsable Alexa recibió el ARN y el modelo; falta agregar el trigger limitado al Skill ID real.

## 4. Pruebas y validaciones

Llenar la matriz `docs/PRUEBAS.md` con capturas, fechas, métricas y errores. Registrar al menos:

- Exactitud: metodología de referencia (consulta pendiente al docente para sensor sin agua).
- Reporte por evento y periódico con timestamps.
- Latencias extremo a extremo Alexa → servo (n≥10 recomendable), no solo Lambda → Shadow.
- 15 minutos de estabilidad objetivo.
- Reconexión Wi-Fi y MQTT, comando deseado pendiente aplicado.
- RF7–RF9 con usuario sin vínculo, Thing inexistente, cambio y borrado de vínculo.

## 5. Resultados

Se documentaron 27 muestras secas `raw=0`, 12 muestras del ADC a `raw=4095` con estímulo de 3V3 limitado por resistencia y reconexión Wi-Fi local. Samuel confirmó el movimiento físico correcto del servo, pero todavía debe anexar parámetros y video. La suite local ejercitó el handler con dos usuarios y AWS simulado. Además, la Lambda desplegada validó un Thing real, persistió la vinculación, leyó `reported`, escribió `desired`, detectó una orden pendiente y rechazó un Thing inexistente; CloudWatch no mostró errores en las ejecuciones revisadas. Los cuatro perfiles del firmware compilaron correctamente, pero aún no se han cargado y validado como sistema integrado. Quedan por probar Alexa, ESP32→AWS, latencia, reconexión MQTT/Shadow y exactitud con referencia autorizada.

## 6. Conclusiones

Las pruebas locales respaldan el funcionamiento de la entrada analógica, la reconexión Wi-Fi aislada y el movimiento básico del servo. Todavía no permiten afirmar que Alexa controla el dispositivo mediante AWS; esta conclusión se completará tras la demostración integrada.

## 7. Recomendaciones

La realimentación de posición permitiría distinguir entre el movimiento estimado y un posible atasco. Evaluar esa extensión con los resultados del montaje.

## 8. Anexos

Diagrama de circuito final, fotografías del prototipo, pruebas y capturas AWS/Alexa, exportaciones de configuraciones, evidencia de commits propios por cada integrante.

