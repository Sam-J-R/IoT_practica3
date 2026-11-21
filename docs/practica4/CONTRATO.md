# Contrato operativo de integración — práctica 4

Referencia para mantener compatibles el firmware, la Lambda y la Skill. Reemplaza al [contrato de la práctica 3](../CONTRATO.md), que se conserva sin cambios como registro de la primera entrega. El resumen de qué cambió y por qué está en [CAMBIOS.md](CAMBIOS.md).

## Identificación y arquitectura

- Región AWS: `us-east-2` (Ohio) para IoT Core, Lambda y DynamoDB.
- Thing físico: `tendedero-inteligente`. Thing de prueba: `tendedero-prueba2`.
- Convención para Things nuevos: `tendedero-NNN`. El prefijo `tendedero-` es obligatorio.
- Tablas DynamoDB: `tendedero_vinculaciones` y `tendedero_dispositivos`.
- Shadow: clásico (sin nombre).
- El actuador es un brazo que gira el tendedero hasta debajo de un techo fijo. Ya no existe una cubierta que se abre y se cierra.
- Actuadores: el brazo (servo MG90S, principal) y un LED de luz automática. Sensores: agua (MH, GPIO34) y luz (LDR, GPIO35).
- Lógica automática: el ESP32 resguarda la ropa si detecta agua (R1) y enciende el LED si está oscuro (R5), en modo `automatico` y también sin Internet. La Nube vuelve a exponer la ropa (R2), registra alertas (R3) y pasa a `manual` si hay demasiados movimientos (R4). Ver [Lógica de control](#lógica-de-control).

## Documento Shadow

```json
{
  "state": {
    "desired": {
      "posicion": "resguardado",
      "origen": "edge",
      "modo": "automatico",
      "minutos_reexponer": 30,
      "led": "encendido",
      "origen_led": "edge",
      "calibracion_solicitada": { "condicion": "seco", "id": 1731600000000 }
    },
    "reported": {
      "posicion": "resguardado",
      "origen": "edge",
      "agua_detectada": true,
      "lectura_adc": 1830,
      "modo": "automatico",
      "minutos_reexponer": 30,
      "luz_adc": 640,
      "oscuro": true,
      "led": "encendido",
      "origen_led": "edge",
      "ts_dispositivo": 1795110000123,
      "calibracion": { "umbral_seco": 200, "umbral_agua": 600, "estado": "aplicada" },
      "calibracion_solicitada": { "condicion": "seco", "id": 1731600000000 }
    }
  }
}
```

| Atributo | Tipo | Valores | Quién escribe | Uso |
|---|---|---|---|---|
| `desired.posicion` | string | `expuesto`, `resguardado` | Lambda de Alexa, Lambda supervisor (R2) o ESP32 (R1) | Orden de movimiento. Siempre se escribe junto con `desired.origen`. |
| `desired.origen` | string | `voz`, `nube`, `edge` | Quien escribe `desired.posicion` | Quién pidió el movimiento (RF12). |
| `desired.modo` | string | `manual`, `automatico` | Lambda de Alexa o Lambda de lógica (R4) | Modo de operación (RF14). |
| `desired.minutos_reexponer` | entero | 5–240 | Lambda de Alexa | Minutos sin agua antes de que R2 vuelva a exponer. Fuera de rango, el ESP32 lo ignora. |
| `desired.led` | string | `encendido`, `apagado` | Lambda de Alexa o ESP32 (R5) | Orden para el LED. Siempre junto con `desired.origen_led`. |
| `desired.origen_led` | string | `voz`, `nube`, `edge` | Quien escribe `desired.led` | Quién pidió el cambio del LED. |
| `desired.calibracion_solicitada.condicion` | string | `seco`, `mojado` | Lambda | Condición en la que el usuario dice que está el sensor. |
| `desired.calibracion_solicitada.id` | entero | Hora del pedido en milisegundos | Lambda | Distingue cada pedido y permite saber su antigüedad. |
| `reported.posicion` | string | `expuesto`, `resguardado`; ausente si es desconocida | ESP32 | Posición estimada tras el asentamiento del servo. |
| `reported.agua_detectada` | booleano | `true`, `false`; ausente si es desconocido | ESP32 | Respuesta a la consulta de Alexa. |
| `reported.lectura_adc` | entero | 0–4095 | ESP32 | Lectura cruda del sensor. No es un porcentaje de lluvia. |
| `reported.calibracion.umbral_seco` | entero | 0–4095 | ESP32 | Por debajo de este valor, el sensor vuelve a "seco". |
| `reported.calibracion.umbral_agua` | entero | 0–4095 | ESP32 | Desde este valor, el sensor pasa a "agua". |
| `reported.calibracion.estado` | string | `fabrica`, `aplicada`, `rechazada`, `caducada` | ESP32 | Resultado del último pedido de calibración. |
| `reported.calibracion_solicitada` | objeto | Copia del pedido atendido | ESP32 | Confirma qué pedido se atendió y elimina su `delta`. |
| `reported.origen` | string | `voz`, `nube`, `edge` | ESP32 | Quién pidió el último movimiento del brazo. |
| `reported.modo` | string | `manual`, `automatico` | ESP32 | Modo vigente; se guarda en la memoria del ESP32 y sobrevive a reinicios sin Internet. |
| `reported.minutos_reexponer` | entero | 5–240 | ESP32 | Espera vigente para R2. |
| `reported.luz_adc` | entero | 0–4095 | ESP32 | Lectura cruda del LDR. Ausente si no hay LDR. |
| `reported.oscuro` | booleano | `true`, `false`; `null` sin dato | ESP32 | Clasificación del LDR con histéresis (oscuro < 350, claro > 650 en escala 0–1000) y 3 s de confirmación. Ausente si no hay LDR. |
| `reported.led` | string | `encendido`, `apagado` | ESP32 | Estado del LED. Ausente si no hay LED. |
| `reported.origen_led` | string | `voz`, `nube`, `edge` | ESP32 | Quién pidió el último cambio del LED. |
| `reported.luz_simulada` | booleano | `true`; `null` lo borra | ESP32 (perfil de ensayo) | La luz viene de los comandos `ldr_oscuro` / `ldr_claro`, no del LDR. No mezclar con datos reales. |
| `reported.ts_dispositivo` | entero | Epoch en ms (NTP) | ESP32 | Hora del ESP32 en cada reporte, para medir la latencia de almacenamiento. |

Las palabras `state`, `desired`, `reported`, `delta`, `version`, `metadata` y `clientToken` son reservadas de AWS y no se pueden traducir.

### Calibración del sensor

Las **referencias** son las lecturas del sensor en seco y con agua. Se guardan solo en la memoria no volátil del ESP32 y no se publican. Los **umbrales** se calculan a partir de ellas y sí se publican:

- `umbral_seco = referencia_seco + 10 % × (referencia_agua − referencia_seco)`
- `umbral_agua = referencia_seco + 30 % × (referencia_agua − referencia_seco)`

Reglas del ESP32 al recibir un pedido:

1. Si el `id` es el mismo que el último atendido, lo ignora. Ese `id` se guarda en memoria no volátil, así que un reinicio no repite la calibración.
2. Si el pedido tiene más de 2 minutos de antigüedad, no mide y responde `caducada`. Ocurre, por ejemplo, si el equipo estaba apagado cuando se pidió.
3. Promedia 20 lecturas y reemplaza solo la referencia pedida. La otra referencia se conserva.
4. Si las dos referencias quedan a menos de 500 cuentas, responde `rechazada` y mantiene los valores anteriores.
5. En los demás casos responde `aplicada` y usa los umbrales nuevos de inmediato.

Sin calibración previa, el ESP32 usa las referencias de fábrica de `calibracion_local.h` y reporta `estado: fabrica`.

### Frecuencia de reporte

- **Por evento:** un cambio en `agua_detectada`, `posicion`, `origen`, `modo`, `minutos_reexponer`, `oscuro`, `led`, `origen_led` o en la calibración se reporta de inmediato. `lectura_adc` y `luz_adc` solo viajan en esos reportes y en el periódico.
- **Periódico de respaldo:** cada 60 s desde la última aceptación (antes eran 5 s).
- El bloque `calibracion` solo viaja en el primer reporte tras conectar y cuando cambia. El reporte periódico lleva `lectura_adc`, `agua_detectada` y `posicion`.

## Lógica de control

| Regla | Dónde | Condición → acción | Por qué ahí |
|---|---|---|---|
| R1 | Edge (`LogicaEdge::evaluarR1`) | Modo `automatico` y agua detectada → resguardar | Urgente, datos locales, debe funcionar sin Internet. |
| R5 | Edge (`LogicaEdge::evaluarR5`) | Modo `automatico`: oscuro → LED encendido; claro → apagado | Inmediata, datos locales, sin Internet. |
| R2 | Nube (Lambda supervisor, cada 5 min) | Modo `automatico`, resguardado y sin agua durante `minutos_reexponer` → `desired = {posicion: expuesto, origen: nube}` | Necesita el histórico. |
| R3 | Nube (Lambda supervisor) | Sin reporte durante 3 min → alerta en el histórico | El objeto no puede reportar su propia desconexión. |
| R4 | Nube (Lambda de lógica, regla `tendedero_movimientos`) | Más de 6 movimientos en una hora → `desired.modo = manual` | Necesita el histórico de movimientos. |

### Convivencia de la voz con la lógica automática

| Orden de voz | Modo `manual` | Modo `automatico` |
|---|---|---|
| Resguardar | Se cumple | Se cumple |
| Exponer | Se cumple | Se cumple si no hay agua. Con agua, la Lambda responde con una explicación y no escribe; si igual llega, el ESP32 la rechaza y escribe `desired = {posicion: resguardado, origen: edge}` |
| Encender / apagar la luz | Se cumple | Con LDR, la decide el sensor: la Lambda explica y no escribe; el ESP32 también la rechaza. Sin LDR, se cumple |

### Reglas del `delta` que respeta el ESP32

1. **Decisión del Edge:** cuando R1 o R5 actúan, el ESP32 escribe su decisión en `desired` con origen `edge`. Si no, el `desired` anterior generaría un `delta` que la deshace.
2. **Origen omitido:** si `desired.origen` coincide con `reported.origen`, AWS no lo incluye en el `delta`; el ESP32 usa el último origen que reportó. Por eso la Lambda de Alexa no escribe nada si la posición pedida ya es la reportada: un `desired` que solo cambia el origen dejaría un `delta` que nunca se cierra.
3. **Sin conexión:** la decisión del Edge queda pendiente. Al reconectar, el ESP32 descarta el `desired` distinto que trae el GET y publica primero su decisión.

## MQTT Shadow clásico

Sin cambios respecto a la práctica 3. `THING_NAME` es parámetro del firmware.

| Dirección | Tópico |
|---|---|
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/update/delta` |
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/get/accepted` |
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/get/rejected` |
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/update/accepted` |
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/update/rejected` |
| Dispositivo publish | `$aws/things/THING_NAME/shadow/update` |
| Dispositivo publish | `$aws/things/THING_NAME/shadow/get` |

Después de conectar o reconectar, el ESP32 se suscribe, publica `/get`, lee el `desired` vigente, aplica el movimiento pendiente y atiende el pedido de calibración si todavía es válido.

## Vinculación RF7–RF9

El usuario vincula su tendedero con un **código numérico de 6 dígitos** que viene en la etiqueta del producto. Ya no se usa el nombre del Thing ni un mapa de alias en variables de entorno.

Tabla `tendedero_dispositivos` (nueva). Es la ficha de cada producto:

| Campo | Tipo | Uso |
|---|---|---|
| `thingName` | String, clave de partición | Nombre del Thing en IoT Core. |
| `codigoVinculacion` | String, clave del índice `codigoVinculacion-index` | Código de la etiqueta: 6 dígitos, sin empezar en 0, único. |
| `fechaAlta` | String ISO-8601 UTC | Fecha de registro del dispositivo. |

Tabla `tendedero_vinculaciones` (sin cambios):

| Campo | Tipo | Uso |
|---|---|---|
| `userId` | String, clave de partición | `context.System.user.userId` |
| `thingName` | String | Thing validado. |
| `fechaVinculacion` | String ISO-8601 UTC | Auditoría mínima. |

Flujo de la Lambda:

| Momento | Operaciones |
|---|---|
| Vincular o cambiar | Validar formato del código → `Query` al índice por código → `DescribeThing` → `PutItem` en vinculaciones. |
| Cualquier otro intent | `GetItem` en vinculaciones por `userId` → Shadow del Thing. El código no interviene. |
| Desvincular | `DeleteItem` en vinculaciones. |

No se asigna un Thing por defecto a usuarios sin vincular.

## Intents

| Intent | Slot | Comportamiento |
|---|---|---|
| `VincularThingIntent` | `codigo` (`AMAZON.NUMBER`) | Buscar el Thing por código, validar que existe y guardar usuario → Thing. |
| `CambiarThingIntent` | `codigo` (`AMAZON.NUMBER`) | Reemplazar la vinculación existente. |
| `DesvincularThingIntent` | — | Borrar la vinculación. |
| `ConsultarAguaIntent` | — | Responder con `reported.agua_detectada`. |
| `ExponerTendederoIntent` | — | Escribir `desired = {posicion: expuesto, origen: voz}`, salvo en automático con agua (ver convivencia). |
| `ResguardarTendederoIntent` | — | Escribir `desired = {posicion: resguardado, origen: voz}`. |
| `ConsultarPosicionIntent` | — | Leer `reported.posicion` e indicar si hay una orden pendiente. |
| `CalibrarSensorIntent` | `condicion` (`CondicionSensor`: `seco` / `mojado`) | Escribir `desired.calibracion_solicitada`. |
| `ConsultarCalibracionIntent` | — | Informar si el último pedido está pendiente, aplicado, rechazado o caducado. |
| `CambiarModoIntent` | `modo` (`ModoOperacion`: `manual` / `automatico`) | Escribir `desired.modo`. |
| `ConsultarModoIntent` | — | Leer `reported.modo` y `minutos_reexponer`, e indicar si hay un cambio pendiente. |
| `ConfigurarEsperaIntent` | `minutos` (`AMAZON.NUMBER`) | Validar 5–240 y escribir `desired.minutos_reexponer`. |
| `EncenderLuzIntent` / `ApagarLuzIntent` | — | Escribir `desired.led` con `origen_led: voz`, salvo en automático con LDR (ver convivencia). |
| `ConsultarLuzIntent` | — | Leer `reported.oscuro` y `reported.led`. |

## Seguridad y coherencia

- La política IoT usa `${iot:Connection.Thing.ThingName}`: una sola política sirve para todos los tendederos, y cada certificado solo accede al Shadow de su propio Thing.
- El código de la etiqueta no prueba la posesión física del objeto. Quien lo conozca puede vincularlo. Un botón de emparejamiento en el dispositivo queda como mejora futura.
- `userId` identifica una cuenta con la Skill habilitada. Puede cambiar si el usuario deshabilita y vuelve a habilitar la Skill.
- Escribir `desired` no prueba movimiento físico. Alexa dice «He solicitado...» y la posición reportada es una estimación por tiempo.
- Los pulsos del servo no están en el Shadow: dependen del mecanismo, no del ambiente, y un valor incorrecto puede dañar el servo.
