# Configuración, implementación y validación de Alexa

Registro del **9 de noviembre de 2026**, hora de Bolivia. Los identificadores AX coinciden con el número de captura y con el [informe técnico](INFORME.md) (§4.4).

## 1. Función de Alexa en el sistema

La Skill proporciona la interfaz de consultas y control del tendedero. La invocación abre la conversación; los intents identifican la operación; el slot contiene el identificador del objeto. Lambda valida y resuelve ese identificador, conserva la asociación en DynamoDB y utiliza el Device Shadow del Thing vinculado.

```mermaid
flowchart LR
    U[Usuario en simulador] --> A[Skill es-MX]
    A --> L[Lambda]
    L <--> D[(DynamoDB: usuario y Thing)]
    L <--> S[(Device Shadow)]
    S <--> E[ESP32: sensor y servo]
```

Abrir «tendedero inteligente» no mueve la cubierta ni cambia el vínculo. «Abre la cubierta» es un intent de control separado. No se implementa cierre automático local por presencia de agua; la actuación se solicita desde Alexa a través del Shadow.

## 2. Configuración utilizada

| Elemento | Valor |
|---|---|
| Nombre de la Skill | Tendedero inteligente |
| Modelo de interacción | Custom |
| Idioma | Spanish (MX), `es-MX` |
| Nombre de invocación | `tendedero inteligente` |
| Alojamiento | Backend propio: Provision your own backend resources |
| Endpoint | AWS Lambda ARN de `tendedero-inteligente-alexa` |
| Región del backend | `us-east-2` |
| Etapa de pruebas | Development |
| Inspección de solicitudes y respuestas | Skill I/O |
| Tabla de vínculos | `tendedero_vinculaciones` |
| Thing de prueba | `tendedero-prueba2` |
| Thing físico | `tendedero-inteligente` |
| Shadow | Clásico, sin nombre |

Se utilizó el [modelo JSON incluido en el repositorio](../alexa/interaction-model-es-MX.json), con sus siete intents funcionales. Las capturas de consola también muestran intents integrados. El editor Code de Alexa-hosted no se utiliza: el código Python del backend está en [lambda_function.py](../lambda/lambda_function.py) y se despliega en AWS Lambda.

La configuración se respalda con las [figuras 01 a 07](evidencias/alexa/README.md). La conexión de la Skill al backend se comprobó mediante respuestas reales del simulador. La documentación AWS registra el trigger Alexa Skills Kit restringido al Skill ID.

## 3. Intents, slots y operación del backend

| Intent | Slot | Frase utilizada | Efecto |
|---|---|---|---|
| `VincularThingIntent` | `thing_name`: `AMAZON.SearchQuery` | vincula mi objeto con prueba dos | Validar Thing y persistir usuario → Thing. |
| `CambiarThingIntent` | `thing_name`: `AMAZON.SearchQuery` | cambia mi objeto a tendedero inteligente | Validar el nuevo Thing y reemplazar la asociación. |
| `DesvincularThingIntent` | No requerido por el handler | desvincula mi objeto | Borrar la asociación en DynamoDB. |
| `ConsultarAguaIntent` | — | hay agua en el sensor | Leer `reported.agua_detectada` del Thing vinculado. |
| `AbrirCubiertaIntent` | — | abre la cubierta | Escribir `desired.cubierta = abierta`. |
| `CerrarCubiertaIntent` | — | cierra la cubierta | Escribir `desired.cubierta = cerrada`. |
| `ConsultarCubiertaIntent` | — | cómo está la cubierta | Informar el último `reported.cubierta` y distinguir una orden diferente en `desired`. |

La apertura de la Skill genera `LaunchRequest` y devuelve un saludo. Los intents integrados de ayuda, detener, cancelar y fallback ofrecen orientación, cierre de conversación y respuesta a frases no comprendidas. El cierre de conversación no elimina el vínculo.

## 4. Vinculación y normalización de alias

El slot captura el identificador expresado por el usuario. Durante las primeras pruebas se observó que «prueba dos» llegaba como `prueba 2`. El intent era correcto, pero la variante no coincidía con el alias inicialmente configurado. Se coordinó el siguiente mapa en `THING_ALIASES_JSON`:

```json
{
  "tendedero inteligente": "tendedero-inteligente",
  "prueba dos": "tendedero-prueba2",
  "prueba 2": "tendedero-prueba2",
  "tendedero prueba dos": "tendedero-prueba2",
  "tendedero prueba 2": "tendedero-prueba2"
}
```

Lambda normaliza espacios y mayúsculas, resuelve el alias y valida existencia mediante `DescribeThing` antes de guardar el vínculo. Un identificador inexistente produce rechazo antes de reemplazar el registro.

La tabla guarda `userId`, `thingName` y `fechaVinculacion`. Cada consulta u orden resuelve el Thing mediante el usuario de la solicitud. La lectura consistente de DynamoDB permite recuperar el vínculo después de cerrar y abrir la conversación, sin depender de la memoria de una invocación Lambda.

La prueba de cambio válido muestra primero el vínculo con `tendedero-prueba2` y después la confirmación de `tendedero-inteligente`. De este modo se evidencia que la Skill no está fijada a un único Thing.

## 5. Pruebas funcionales registradas

Modalidad: **entrada textual en el simulador**. En el entorno utilizado, el micrófono no permitió realizar pruebas habladas. Esta es una condición del ensayo, no una operación funcional sin ejecutar; los resultados no se presentan como validación del reconocimiento de voz.

| ID | Escenario | Resultado | Evidencia |
|---|---|---|---|
| AX-08 | Abrir la Skill | Bienvenida y orientación de operaciones. | [08](evidencias/alexa/08-alexa-inicio.png) |
| AX-09 | Consultar sin vínculo después de desvincular | Solicita vincular primero. | [09](evidencias/alexa/09-alexa-sin-vinculo.png) |
| AX-10 | Vincular con prueba dos | Confirma `tendedero-prueba2`. | [10](evidencias/alexa/10-alexa-vinculacion.png) |
| AX-11 | Detener, volver a abrir y consultar | Conserva vínculo y responde sin nueva asociación. | [11](evidencias/alexa/11-alexa-persistencia.png) |
| AX-12 | Solicitar cambio a un Thing inexistente | Rechaza el identificador. | [12](evidencias/alexa/12-alexa-thing-inexistente.png) |
| AX-13 | Desvincular | Confirma eliminación; otra consulta sin vínculo se observa en AX-09. | [13](evidencias/alexa/13-alexa-desvinculacion.png) |
| AX-14 | Consultar clasificación seca y con agua | Respuestas negativa y afirmativa para el sensor. | [14](evidencias/alexa/14-alexa-sensor-seco-y-con-agua.png) |
| AX-14 | Consultar cubierta | Informa cubierta cerrada según el último reporte. | [14](evidencias/alexa/14-alexa-sensor-seco-y-con-agua.png) |
| AX-15 | Solicitar abrir y cerrar | Confirma envío de cada posición solicitada. | [15](evidencias/alexa/15-alexa-abrir-y-cerrar-cubierta.png) |
| AX-16 | Cambiar a un Thing válido | Reemplaza el vínculo de prueba por el Thing físico. | [16](evidencias/alexa/16-alexa-cambio-valido.png) |

Se ejecutaron todos los intents; la tabla lista los que tienen captura. Ayuda y fallback se probaron sin captura.

## 6. Integración con el dispositivo y recuperación de orden

Además de las pruebas iniciales con el Thing de prueba, el ensayo integrado con ESP32, sensor, servo y Shadow cuenta con [dos videos originales](evidencias/integracion/README.md). El equipo confirmó también la revisión de la base de datos. En el [video de funcionamiento](evidencias/integracion/01-funcionamiento-completo.mp4) se observan consultas del sensor, control de apertura/cierre, cambio de orientación del brazo del servo y estados correspondientes en AWS.

Alrededor de 00:09–00:10, el Shadow muestra cubierta cerrada, `sensor_raw = 0` y `agua_detectada = false`. Hacia 00:15–00:16 muestra `sensor_raw = 2453` y `agua_detectada = true`; las consultas del simulador devuelven las respuestas negativa y afirmativa correspondientes.

También se ensayó esta secuencia:

1. Desconectar el cable del ESP32.
2. Enviar desde Alexa una solicitud de apertura o cierre.
3. Conservar la posición solicitada en el Shadow durante la desconexión.
4. Reconectar el ESP32.
5. Observar la aplicación de la orden y la actualización de estado en AWS, sin repetir el comando.

El [video de recuperación](evidencias/integracion/02-recuperacion-orden-reconexion.mp4) muestra hacia 00:08–00:09 `desired.cubierta = abierta`, `reported.cubierta = cerrada` y `delta.cubierta = abierta`. Hacia 00:22–00:24 se observa el giro del brazo del servo y al final se muestran `desired` y `reported` en `abierta`. El procedimiento confirmado por el equipo no repitió la orden.

Este resultado corresponde a recuperación tras desconexión y nuevo arranque. El firmware, al conectar MQTT, solicita el Shadow y aplica la posición deseada vigente. La pérdida de Wi-Fi con el dispositivo encendido se ensayó aparte el 10/11 (RNF5, [resultados](RESULTADOS_RNF.md)): 3/3 recuperaciones, máximo 7,69 s.

Las capturas documentan la interfaz Alexa y los videos incorporan la observación del montaje de banco, el servo y los estados AWS. Se muestra el brazo del servo; no se presenta una prueba de carga de una cubierta instalada. El estado reportado por el firmware sigue siendo una estimación tras asentamiento, no una medición independiente de posición. Las marcas de los videos son referencias de navegación, no mediciones de latencia.

## 7. Relación con los requisitos

| Requisito | Respaldo de esta entrega |
|---|---|
| RF3 | Video INT-02: `desired` diferente de `reported`, movimiento del servo y convergencia final. |
| RF4 | Captura 14 y video INT-01: consultas en español y estados de sensor en AWS, ejecutadas por texto. |
| RF5 | Captura 15 y video INT-01: solicitudes de apertura/cierre y actuación del servo de banco. |
| RF6 | Captura 14 y video INT-01: consulta de cubierta y estados reportados. |
| RF7 | Vinculación y conservación entre conversaciones. |
| RF8 | Guía sin vínculo y consulta posterior con asociación persistida; el backend resuelve por `userId`. |
| RF9 | Rechazo de identificador inexistente, cambio válido y eliminación del vínculo. |

El aislamiento entre usuarios y la persistencia también cuentan con pruebas directas de AWS documentadas por el equipo. Se distinguen de una grabación de dos cuentas operando desde la Skill.

## 8. Reutilización de evidencias AWS

Se referencia el [conjunto AWS existente](https://github.com/Sam-J-R/IoT_practica3/blob/a8a86c3f56a39b063bacd5fe4cc651dabfe73232/docs/EVIDENCIAS_AWS.md), incorporado también en la rama principal, sin copiar sus imágenes a la carpeta de Alexa:

- Things y asociaciones del certificado activo.
- Tabla DynamoDB y vínculos persistidos.
- Lambda, runtime, handler y rol IAM.
- Panel y CSV de CloudWatch.
- Shadow de prueba y respuesta de Lambda.
- Tabla AWS-BE de consultas, comandos, cambio, desvinculación y enrutamiento.

El enlace identifica la revisión concreta utilizada como referencia. Así se conserva trazabilidad aunque la rama local de trabajo parta de una versión anterior.

## 9. Decisiones y límites técnicos

- **Backend propio:** reutiliza la Lambda y los recursos AWS del proyecto; no necesita convertir la Skill a Alexa-hosted.
- **Contrato estable:** se usan los mismos nombres de atributos, intents y Things que el backend.
- **Alias configurables:** admiten variantes textuales sin introducir un Thing único en el código.
- **Persistencia externa:** cerrar conversación no elimina lo guardado en DynamoDB.
- **Separación de solicitud y estado:** «He solicitado…» describe una actualización de `desired`, no una confirmación mecánica.
- **Consulta del último reporte:** una respuesta del sensor no demuestra por sí sola conexión activa ni antigüedad aceptable del dato.
- **Mediciones:** las capturas y videos son evidencia funcional; los valores de latencia, exactitud y estabilidad provienen de los ensayos RNF del 10/11 ([RESULTADOS_RNF.md](RESULTADOS_RNF.md)).

## 10. Evidencias y archivos de configuración

- [Índice de las 17 capturas](evidencias/alexa/README.md).
- [Índice y marcas de tiempo de los dos videos](evidencias/integracion/README.md).
- [Modelo de interacción JSON](../alexa/interaction-model-es-MX.json).
- [Contrato del sistema](CONTRATO.md).
- [Backend Lambda](../lambda/lambda_function.py).
- [Programa del ESP32](../firmware/src/Tendedero.cpp).

Los identificadores del endpoint aparecen parcialmente ocultos en su captura. No se adjuntan eventos completos de Skill I/O, tokens de acceso, secretos Wi-Fi ni materiales privados TLS.
