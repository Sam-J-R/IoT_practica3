# Guía corta de integración y entrega — Práctica 3

**Fecha límite docente:** martes 10 de noviembre de 2026 a las 17:45 (Bolivia). Esta guía usa el contrato de `CONTRATO.md`; coordinar cualquier cambio de atributos con el equipo.

## 1. Samuel: hardware y firmware

1. Confirmar conexiones con el ESP32 **sin alimentación**: MH `S → GPIO34`, `+ → 3V3`, `- → GND`; señal servo `GPIO26`, fuente DC regulada para el servo y **GND común**. No usar LED como actuador.
2. Probar ADC con `pio run -d firmware -e sensor_test -t upload`; monitor serie a 115200. Ya se documentaron 27 lecturas secas `raw=0`; conservar evidencia de cualquier estímulo adicional.
3. Probar servo con `pio run -d firmware -e servo_test -t upload`. En monitor serie enviar `A` (abierta) o `C` (cerrada). Registrar la tensión de fuente, frecuencia, pulsos `SERVO_ABIERTA_US` y `SERVO_CERRADA_US`, tiempo de asentamiento y video sin forzar topes.
4. Medir umbrales `UMBRAL_SECO` y `UMBRAL_AGUA` mediante un método seguro/autorizado. Copiar `calibracion.example.h` a `calibracion_local.h` y escribir valores justificados. La prueba de ADC con resistencia **no equivale** a precisión del detector de agua.
5. Copiar `secrets.example.h` a `secrets.h` y completar Wi-Fi y materiales TLS del Thing que te entregue la compañera AWS. Estos dos archivos locales **no se comparten ni se suben al repositorio**.
6. Una vez exista el Thing real, cargar `tendedero_shadow`. Si aún no hay AWS, `sensor_shadow_test` permite verificar MQTT y reporte ADC **sin mover el servo**. La demo final usa `tendedero_shadow`.

## 2. Compañera AWS: preparar la nube

1. En AWS IoT Core, crear un Thing físico y otro de prueba. Comunicar **por canal privado** a Samuel endpoint Data-ATS, CA, certificado y clave; confirmar el nombre exacto del Thing. Referencia de región acordada: `us-east-1`.
2. Asociar el certificado a una política IoT que permita los tópicos de `CONTRATO.md`. Sustituir `REGION`, `ACCOUNT_ID` y Thing en `aws/iot-certificate-policy.template.json`.
3. Crear en DynamoDB la tabla `tendedero_vinculaciones`: clave de partición `userId` (String); atributos `thingName` y `fechaVinculacion`.
4. Desplegar Lambda con handler `lambda_function.lambda_handler`. Configurar `IOT_ENDPOINT`, `DDB_BINDINGS_TABLE` y alias hablados opcionales `THING_ALIASES_JSON`. Aplicar permisos IAM de IoT Registry/Shadow y DynamoDB de `aws/lambda-iam-policy.template.json`, junto con permisos de CloudWatch Logs. No usar claves de acceso AWS incrustadas.
5. Validar un caso sin vínculo, Thing inexistente, vincular, consultar, cambiar Thing, desvincular y aislamiento entre usuarios. Guardar capturas de DynamoDB, Shadow y CloudWatch sin secretos.

**Atención:** el ZIP de despliegue incluido corresponde exactamente al código Lambda entregado. Si se cambia `lambda_function.py`, **reconstruir el ZIP** con las dependencias antes de desplegarlo.

## 3. Compañera Alexa: Skill

1. En Alexa Developer Console, seleccionar idioma español compatible y usar `alexa/interaction-model-es-MX.json` como base.
2. Configurar el endpoint de la Skill con la Lambda real y autorizar su Skill ID en el trigger AWS.
3. Construir el modelo y comprobar las siete operaciones: vincular, cambiar, desvincular, consultar sensor, abrir, cerrar y consultar cubierta.
4. Ensayar frases **por texto y voz**. Verificar cómo reconoce los alias o códigos hablados del Thing; ajustar `THING_ALIASES_JSON` con la compañera AWS.
5. Capturar frases reconocidas, respuestas y errores. No declarar RF4–RF9 completos basándose solo en las pruebas simuladas.

## 4. Prueba conjunta indispensable

1. **Control:** pedir «cierra la cubierta» y verificar la cadena `Alexa → Lambda → desired.cubierta → delta → movimiento real → reported.cubierta`.
2. **Consulta:** preguntar por el agua y comprobar que la respuesta coincide con `reported.agua_detectada`.
3. **Reconexión:** desconectar Wi-Fi, solicitar desde Alexa la posición opuesta, restaurar Wi-Fi y verificar que el ESP32 obtiene el Shadow y aplica el `desired` pendiente sin repetir el comando.
4. **Dos usuarios:** vincular dos cuentas a dos Things diferentes y verificar que no se cruzan las órdenes.
5. **Métricas:** registrar al menos 10 comandos de voz→servo (referencia ≤3 s), 10–15 minutos de funcionamiento estable, intervalos entre reportes (configuración: respaldo cada 5 s y cambio significativo), error del sensor con referencia válida y reconexión.
6. Actualizar `docs/PRUEBAS.md`, `docs/INFORME.md`, fotos/videos y exportaciones de políticas/Skill. Cada integrante debe hacer sus propios commits.

## 5. Antes de subir a GitHub

- [ ] `python -m unittest discover -s tests -v` sin fallos.
- [ ] Firmware **final** compilado/cargado en PlatformIO y probado físicamente.
- [ ] No incluir `secrets.h`, `calibracion_local.h`, `.pio/`, `.venv/`, certificados ni clave privada.
- [ ] Contrato y nombres de tópicos idénticos en firmware, Lambda y Alexa.
- [ ] Evidencias RF1–RF9 y RNF separadas de pruebas simuladas.
- [ ] Informe Markdown completo, diagramas y configuraciones reales exportadas.
- [ ] Repositorio accesible y enlace enviado por LMS-UCB antes del plazo.
