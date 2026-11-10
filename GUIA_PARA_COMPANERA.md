# Lee esto primero: Práctica 3 — Tendedero inteligente

**Para las compañeras encargadas de AWS y Alexa · Grupo 6 · SIS-234**  
**Entrega del grupo:** martes 10 de noviembre de 2026, 17:45 (hora de Bolivia).

## 1. Qué estamos construyendo

Un **ESP32** lee un sensor de agua y controla un **servo** que abre o cierra la cubierta de un tendedero. El usuario **pregunta por el agua y ordena abrir/cerrar mediante Alexa**. El sensor NO mueve la cubierta automáticamente.

El recorrido del comando es:

1. El usuario dice: «Alexa, abre tendedero inteligente» y luego «cierra la cubierta».
2. **Alexa** reconoce la frase y envía a **Lambda** el intent y el `userId`.
3. **Lambda** busca en **DynamoDB** qué Thing pertenece a ese usuario.
4. Lambda escribe `desired.cubierta = "cerrada"` en el **Device Shadow** del Thing correcto.
5. **AWS IoT Core** entrega un mensaje `delta` al **ESP32**.
6. El ESP32 mueve el **servo** y, tras el tiempo de recorrido calibrado, informa `reported.cubierta = "cerrada"`.

Para consultar agua, el ESP32 envía `reported.agua_detectada` y Lambda lo lee. **No hay conexión directa entre Alexa y el ESP32.**

## 2. Diccionario rápido

| Palabra | Significa en este proyecto |
|---|---|
| **Thing** | Registro en AWS que identifica a un ESP32 concreto |
| **Device Shadow** | Documento JSON en AWS que conserva el estado deseado y reportado del Thing |
| **desired** | Lo que pidió el usuario, por ejemplo abrir la cubierta |
| **delta** | Aviso de AWS: hay una orden nueva que el dispositivo debe aplicar |
| **reported** | Lo último que informó el ESP32; la posición del servo es **estimada**, no medida por un sensor de posición |
| **Lambda** | Código Python que interpreta las órdenes de la Skill y usa AWS |
| **DynamoDB** | Tabla que guarda a qué Thing está vinculada cada cuenta Alexa |
| **MQTT con TLS** | Comunicación de mensajes segura entre ESP32 y AWS IoT Core |

### Contrato que debemos respetar

Ejemplo simplificado del Shadow:

```json
{
  "state": {
    "desired": {"cubierta": "cerrada"},
    "reported": {
      "cubierta": "abierta",
      "agua_detectada": false,
      "sensor_raw": 0
    }
  }
}
```

- `cubierta` solo acepta `"abierta"` o `"cerrada"` cuando es conocida.
- `agua_detectada` es `true` o `false` **solo después de calibrar el sensor**; puede estar ausente si todavía no se conoce.
- `sensor_raw` es una lectura ADC aproximada entre 0 y 4095; **no** es porcentaje de lluvia.
- **No cambiar estos nombres sin acordarlo entre las tres partes.** La especificación completa está en `docs/CONTRATO.md`.

## 3. Qué archivo leer y para qué

| Orden | Archivo | Explicación sencilla |
|---|---|---|
| 1 | `README.md` | Cómo abrir y probar el proyecto |
| 2 | `docs/CONTRATO.md` | Nombres de variables, tópicos e intents que todas debemos usar |
| 3 | `firmware/src/Tendedero.cpp` | El programa principal que organiza sensor, red, servo y reportes |
| 4 | `firmware/include/SensorAgua.h` | Lee el sensor por GPIO34 y decide seco/agua cuando está calibrado |
| 5 | `firmware/include/ServoCubierta.h` | Genera la señal PWM por GPIO26 para mover la cubierta |
| 6 | `firmware/src/ClienteShadow.cpp` | Envía/recibe mensajes de AWS, recupera órdenes pendientes y confirma reportes |
| 7 | `lambda/lambda_function.py` | Vincula usuarios y atiende consultas y órdenes de Alexa |
| 8 | `alexa/interaction-model-es-MX.json` | Define lo que Alexa puede entender |
| 9 | `docs/GUIA_INTEGRACION.md` | Pasos concretos para unir y demostrar todo |
| 10 | `docs/GUIA_AWS.md` | Procedimiento completo de IoT Core, certificados, DynamoDB, IAM, Lambda y entrega a Alexa |

**Si una clase parece complicada:** empieza por `Tendedero.cpp`; los comentarios «Paso 1» a «Paso 5» explican qué hace su `loop()`. `ClienteShadow` contiene más código porque debe recuperar la conexión y no repetir órdenes antiguas.

## 4. Qué tiene que hacer cada una

### Samuel — hardware y ESP32

- Sensor MH: `S → GPIO34`, `+ → 3V3`, `− → GND`.
- Servo: señal en GPIO26, fuente DC regulada adecuada, GND común; **no alimentarlo desde GPIO o 3V3**.
- Ya informó que el servo se movió correctamente en prueba local. Faltan documentar fuente, pulsos, tiempo y recorrido con la cubierta.
- Configurará archivos locales `secrets.h` y `calibracion_local.h`, que **no deben subirse ni enviarse en el ZIP**.
- Probará el ESP32 con AWS real, guardará logs/fotografías de RF1–RF3 y preparará el movimiento físico para la demostración presencial.

### Compañera AWS — IoT Core, Lambda y DynamoDB

1. En `us-east-2`, crear el Thing físico `tendedero-inteligente` y el Thing de prueba `tendedero-prueba2` en **AWS IoT Core**.
2. Crear/asociar certificado y política IoT. Usar `aws/iot-certificate-policy.template.json` como plantilla, reemplazando los identificadores de ejemplo.
3. Compartir **solo por un canal seguro** con Samuel el endpoint Data-ATS, Thing, CA, certificado y clave privada del dispositivo.
4. Crear tabla DynamoDB `tendedero_vinculaciones` con `userId` (String) como clave de partición.
5. Desplegar `lambda/lambda_deployment_p3.zip`, con handler `lambda_function.lambda_handler` y rol IAM apropiado. Configurar `IOT_ENDPOINT` sin protocolo, `DDB_BINDINGS_TABLE=tendedero_vinculaciones` y `THING_ALIASES_JSON={"tendedero inteligente":"tendedero-inteligente","prueba dos":"tendedero-prueba2","prueba 2":"tendedero-prueba2","tendedero prueba dos":"tendedero-prueba2","tendedero prueba 2":"tendedero-prueba2"}`.
6. Probar **dos usuarios y dos Things distintos**, cambio de vínculo, Thing inexistente y desvinculación. El backend **no usa un Thing único para todos**.

### Compañera Alexa — Skill

1. Importar o reproducir `alexa/interaction-model-es-MX.json` en la consola de Alexa, con idioma español compatible.
2. Conectar el endpoint a la Lambda que configuró la compañera AWS.
3. Probar los siete intents: vincular, cambiar, desvincular, consultar agua, abrir, cerrar y consultar cubierta.
4. Ensayar primero **texto** y después **voz**; comprobar cómo reconoce nombres/códigos del Thing y comunicar esos alias a AWS.
5. Guardar capturas de las frases reconocidas y respuestas reales.

## 5. Qué funciona y qué NO debemos afirmar aún

**Confirmado:** lectura ADC seca y prueba eléctrica del GPIO34 documentadas; Wi-Fi local con reconexión; Samuel confirmó movimiento del servo; código Lambda con **12/12 pruebas locales** (incluye validaciones estáticas del proyecto) y AWS simulados.

**Estado actual:** IoT Core, los dos Things, certificado y política del Thing físico, DynamoDB, IAM y Lambda están desplegados. El trigger restringido al Skill ID está configurado y la Skill vinculó el Thing de prueba y consultó su cubierta desde el simulador. La conexión MQTT TLS del ESP32, el ensayo de agua con referencia, `delta`→servo→`reported`, reconexión, latencia y estabilidad corresponden a la integración física.

**Importante:** no hay archivos reales de credenciales ni calibración en este paquete. Si lo abres y compilas sin configurarlos, el programa final solo permite leer ADC y no controla AWS/servo. Es una protección intencional.

## 6. Cómo comprobar el código localmente

Desde la carpeta principal en PowerShell:

```powershell
py -m unittest discover -s tests -v
```

Para compilar el firmware final con PlatformIO:

```powershell
pio run -d firmware -e tendedero_shadow
```

Para probar solo el servo: `pio run -d firmware -e servo_test`; para solo el sensor: `pio run -d firmware -e sensor_test`. Los cuatro perfiles compilaron correctamente el 7/11/2026; todavía deben cargarse y validarse con el hardware real.

## 7. Antes de la entrega

- [ ] RF1–RF9 comprobados de extremo a extremo, no solo con simulaciones.
- [ ] Medidas de estabilidad, exactitud, tiempo de respuesta y reconexión en `docs/PRUEBAS.md`.
- [ ] Informe Markdown y diagramas completos en `docs/INFORME.md` y `docs/DIAGRAMAS.md`.
- [ ] Políticas y modelo de Alexa exportados, **sin claves ni contraseñas**.
- [ ] Commits de las tres cuentas de GitHub y repositorio accesible.
- [ ] Enlace entregado por LMS-UCB antes del martes 10/11 a las 17:45.

**Cualquier duda sobre qué falta realmente:** mirar `docs/ESTADO.md` y `docs/PRUEBAS.md`. **Cualquier duda sobre qué se cambió al simplificar:** mirar `docs/CAMBIOS_APLICADOS.md`.
