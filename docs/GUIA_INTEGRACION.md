# Guía corta de integración y entrega — Práctica 3

**Fecha límite docente:** martes 10 de noviembre de 2026 a las 17:45 (Bolivia). Esta guía usa el contrato de `CONTRATO.md`; coordinar cualquier cambio de atributos con el equipo.

## 1. Samuel: hardware y firmware

1. Confirmar conexiones con el ESP32 **sin alimentación**: MH `S → GPIO34`, `+ → 3V3`, `- → GND`; señal servo `GPIO26`, fuente DC regulada para el servo y **GND común**. No usar LED como actuador.
2. Probar ADC con `pio run -d firmware -e sensor_test -t upload`; monitor serie a 115200. Ya se documentaron 27 lecturas secas `raw=0`; conservar evidencia de cualquier estímulo adicional.
3. Probar servo con `pio run -d firmware -e servo_test -t upload`. En monitor serie enviar `A` (abierta) o `C` (cerrada). Registrar la tensión de fuente, frecuencia, pulsos `SERVO_ABIERTA_US` y `SERVO_CERRADA_US`, tiempo de asentamiento, log y fotografía sin forzar topes. El movimiento se verificará en la demostración presencial.
4. Medir umbrales `UMBRAL_SECO` y `UMBRAL_AGUA` mediante un método seguro/autorizado. Copiar `calibracion.example.h` a `calibracion_local.h` y escribir valores justificados. La prueba de ADC con resistencia **no equivale** a precisión del detector de agua.
5. Copiar `secrets.example.h` a `secrets.h` y completar Wi-Fi y materiales TLS del Thing que te entregue la compañera AWS. Estos dos archivos locales **no se comparten ni se suben al repositorio**.
6. Una vez exista el Thing real, cargar `tendedero_shadow`. Si aún no hay AWS, `sensor_shadow_test` permite verificar MQTT y reporte ADC **sin mover el servo**. La demo final usa `tendedero_shadow`.

## 2. Compañera AWS: preparar la nube

Seguir la guía operativa completa [`GUIA_AWS.md`](GUIA_AWS.md). El contrato definitivo usa `us-east-2`, Thing físico `tendedero-inteligente`, Thing de prueba `tendedero-prueba2`, tabla `tendedero_vinculaciones` y Shadow clásico. El ARN ya fue entregado, el Skill ID recibido y el trigger Alexa Skills Kit quedó restringido a ese identificador.

**Atención:** el ZIP de despliegue incluido corresponde exactamente al código Lambda entregado. Si se cambia `lambda_function.py`, **reconstruir el ZIP** con las dependencias antes de desplegarlo.

### Conectar personalmente el ESP32 a AWS

Los tres archivos descargados se usan únicamente en
`firmware/include/secrets.h`, que está ignorado por Git:

- Amazon Root CA 1 → `AWS_CA_PEM`;
- certificado `*-certificate.pem.crt` → `AWS_CLIENT_CERT_PEM`;
- clave `*-private.pem.key` → `AWS_CLIENT_KEY_PEM`.

Completar también el Wi-Fi, el endpoint ATS sin protocolo ni puerto y el nombre
exacto del Thing:

```cpp
#define WIFI_SSID "RED_LOCAL"
#define WIFI_PASSWORD "CLAVE_LOCAL"
#define AWS_IOT_ENDPOINT "xxxxxxxx-ats.iot.us-east-2.amazonaws.com"
#define AWS_IOT_THING_NAME "tendedero-inteligente"

constexpr char AWS_CA_PEM[] = R"PEM(
-----BEGIN CERTIFICATE-----
CONTENIDO_DE_AMAZON_ROOT_CA_1
-----END CERTIFICATE-----
)PEM";

constexpr char AWS_CLIENT_CERT_PEM[] = R"PEM(
-----BEGIN CERTIFICATE-----
CONTENIDO_DEL_CERTIFICADO_DEL_DISPOSITIVO
-----END CERTIFICATE-----
)PEM";

constexpr char AWS_CLIENT_KEY_PEM[] = R"PEM(
-----BEGIN ... PRIVATE KEY-----
CONTENIDO_DE_LA_CLAVE_PRIVADA
-----END ... PRIVATE KEY-----
)PEM";
```

No copiar los marcadores del ejemplo: conservar exactamente las líneas BEGIN,
END y el contenido de cada archivo real. Después:

1. Desconectar MQTT.fx y cualquier otro cliente con Client ID
   `tendedero-inteligente`.
2. Cargar primero `sensor_shadow_test`. Este perfil comprueba Wi-Fi, TLS,
   certificado, política MQTT, `get` y publicación de `sensor_raw` sin activar
   el servo.
3. Abrir el monitor a 115200 y conservar las líneas de conexión, recuperación
   del Shadow y `reported aceptado`. Confirmar en AWS que el Shadow clásico de
   `tendedero-inteligente` contiene `reported.sensor_raw`.
4. Si falla, revisar en este orden: reloj/SNTP, endpoint, Thing/Client ID,
   certificado activo, asociación certificado→Thing, asociación
   certificado→política y permisos exactos de los tópicos.
5. Para cargar `tendedero_shadow`, completar antes
   `calibracion_local.h` con umbrales del sensor y parámetros del servo medidos.
   Sin esos valores el programa se mantiene intencionalmente en modo ADC y no
   activa MQTT ni el servo.
6. Con el perfil final, editar manualmente el Shadow en AWS para establecer
   `desired.cubierta` primero en `cerrada` y luego en `abierta`. Verificar en
   cada caso `delta` → movimiento → `reported.cubierta` igual a `desired`.
7. Probar recuperación: apagar la red del ESP32, escribir la posición opuesta
   en `desired`, restaurar la red y comprobar `get`, movimiento y convergencia
   sin repetir la orden.
8. Mantenerlo al menos 15 minutos y conservar logs con timestamps para la
   demostración del equipo. El conjunto de evidencias de la responsable AWS ya
   está cerrado en [`EVIDENCIAS_AWS.md`](EVIDENCIAS_AWS.md).

La Skill ya invoca Lambda y opera el Shadow simulado. La prueba manual desde el
Shadow demuestra la ruta AWS→ESP32, pero no sustituye la demostración conjunta
Alexa→Lambda→AWS→ESP32 físico.

## 3. Compañera Alexa: Skill

1. En Alexa Developer Console, seleccionar idioma español compatible y usar `alexa/interaction-model-es-MX.json` como base.
2. Configurar el endpoint de la Skill con la Lambda real y autorizar su Skill ID en el trigger AWS.
3. Construir el modelo y comprobar las siete operaciones: vincular, cambiar, desvincular, consultar sensor, abrir, cerrar y consultar cubierta.
4. Ensayar frases **por texto y voz**. En la prueba por texto Alexa normalizó «prueba dos» como `prueba 2`; el mapa definitivo ya incluye ambas variantes y las formas `tendedero prueba dos/2`.
5. Capturar frases reconocidas, respuestas y errores. No declarar RF4–RF9 completos basándose solo en las pruebas simuladas.

## 4. Prueba conjunta indispensable

1. **Control:** pedir «cierra la cubierta» y verificar la cadena `Alexa → Lambda → desired.cubierta → delta → movimiento real → reported.cubierta`.
2. **Consulta:** preguntar por el agua y comprobar que la respuesta coincide con `reported.agua_detectada`.
3. **Reconexión:** desconectar Wi-Fi, solicitar desde Alexa la posición opuesta, restaurar Wi-Fi y verificar que el ESP32 obtiene el Shadow y aplica el `desired` pendiente sin repetir el comando.
4. **Dos usuarios:** vincular dos cuentas a dos Things diferentes y verificar que no se cruzan las órdenes.
5. **Métricas:** registrar al menos 10 comandos de voz→servo (referencia ≤3 s), 10–15 minutos de funcionamiento estable, intervalos entre reportes (configuración: respaldo cada 5 s y cambio significativo), error del sensor con referencia válida y reconexión.
6. Actualizar `docs/PRUEBAS.md`, `docs/INFORME.md`, fotografías, logs y exportaciones de políticas/Skill. Cada integrante debe hacer sus propios commits.

## 5. Antes de subir a GitHub

- [ ] `python -m unittest discover -s tests -v` sin fallos.
- [ ] Firmware **final** compilado/cargado en PlatformIO y probado físicamente.
- [ ] No incluir `secrets.h`, `calibracion_local.h`, `.pio/`, `.venv/`, certificados ni clave privada.
- [ ] Contrato y nombres de tópicos idénticos en firmware, Lambda y Alexa.
- [ ] Evidencias RF1–RF9 y RNF separadas de pruebas simuladas.
- [ ] Informe Markdown completo, diagramas y configuraciones reales exportadas.
- [ ] Repositorio accesible y enlace enviado por LMS-UCB antes del plazo.
