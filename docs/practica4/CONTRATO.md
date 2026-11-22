# Contrato operativo de integración — práctica 4

Referencia para mantener compatibles el firmware, la Lambda y la Skill. Reemplaza al [contrato de la práctica 3](../CONTRATO.md), que se conserva sin cambios como registro de la primera entrega. El resumen de qué cambió y por qué está en [CAMBIOS.md](CAMBIOS.md).

## Identificación y arquitectura

- Región AWS: `us-east-2` (Ohio) para IoT Core, Lambda y DynamoDB.
- Thing físico: `tendedero-inteligente`. Thing de prueba: `tendedero-prueba2`.
- Convención para Things nuevos: `tendedero-NNN`. El prefijo `tendedero-` es obligatorio.
- Tablas DynamoDB: `tendedero_vinculaciones`, `tendedero_dispositivos` y `tendedero_historico` (ver [Modelo del histórico](#modelo-del-histórico-rf11-rf12-rf15)).
- Shadow: clásico (sin nombre).
- El actuador es un brazo que gira el tendedero hasta debajo de un techo fijo. Ya no existe una cubierta que se abre y se cierra.
- Actuadores: el brazo (servo MG90S, principal) y un LED, la luz para recoger la ropa. Sensores: agua (MH, GPIO34) y luz (LDR, GPIO35), que detecta la noche.
- Lógica automática: el ESP32 resguarda la ropa si detecta agua (R1) o si anochece (R5), en modo `automatico` y también sin Internet. La Nube vuelve a exponer la ropa cuando hay luz y no llueve (R2), registra alertas (R3) y, si hay demasiados movimientos, duplica la espera antes de volver a exponer (R4). Ver [Lógica de control](#lógica-de-control).

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
      "origen_led": "voz",
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
      "origen_led": "voz",
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
| `desired.modo` | string | `manual`, `automatico` | Lambda de Alexa | Modo de operación (RF14). Ninguna regla automática lo cambia. |
| `desired.minutos_reexponer` | entero | 15–240 | Lambda de Alexa o Lambda de lógica (R4) | Minutos sin agua antes de que R2 vuelva a exponer. Fuera de rango, el ESP32 lo ignora. |
| `desired.led` | string | `encendido`, `apagado` | Lambda de Alexa o ESP32 (apagado automático) | Luz para recoger la ropa. Siempre junto con `desired.origen_led`. |
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
| `reported.minutos_reexponer` | entero | 15–240 (inicial 30) | ESP32 | Espera vigente para R2. |
| `reported.luz_adc` | entero | 0–4095 | ESP32 | Lectura cruda del LDR. Ausente si no hay LDR. |
| `reported.oscuro` | booleano | `true`, `false`; `null` sin dato | ESP32 | `true` = es de noche. Clasificación del LDR con histéresis (oscuro < 350, claro > 650 en escala 0–1000) y 5 min de confirmación, para que una nube no cuente como noche. La usan R5, R2 y la respuesta de «¿cómo está el tendedero?». Ausente si no hay LDR. |
| `reported.led` | string | `encendido`, `apagado` | ESP32 | Estado de la luz. Ausente si no hay LED. |
| `reported.origen_led` | string | `voz`, `edge` | ESP32 | `voz` si la encendió o apagó el usuario; `edge` si se apagó sola a los 10 minutos. |
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
| R5 | Edge (`LogicaEdge::evaluarR5`) | Modo `automatico` y de noche (LDR oscuro 5 min) → resguardar | Datos locales y debe funcionar sin Internet, igual que R1. De noche la humedad (sereno, rocío) vuelve a mojar la ropa. |
| R2 | Nube (Lambda supervisor, cada 5 min) | Modo `automatico`, resguardado por el Edge (R1 o R5), sin agua durante `minutos_reexponer` y con luz → `desired = {posicion: expuesto, origen: nube}` | Cruza el histórico de lluvia con la luz actual. Así la ropa guardada de noche sale sola a la mañana si no llueve. Tarda hasta 5 min en actuar. |
| R3 | Nube (Lambda supervisor) | Sin reporte durante 5 min → alerta `sin_reporte` en el histórico (una por desconexión) | El objeto no puede reportar su propia desconexión. 5 min son 5 reportes periódicos perdidos: una caída breve de MQTT no cuenta (ver abajo). Tarda entre 5 y 10 min en detectarla, por el período del supervisor. |
| R4 | Nube (Lambda de lógica, regla `tendedero_movimientos`) | Modo `automatico` y más de 6 movimientos en una hora → `desired.minutos_reexponer` × 2 (tope 240) y alerta `exceso_movimientos` en el histórico. El modo no cambia y R1 sigue activa. | Necesita el histórico de movimientos. |

### Por qué R3 espera 5 minutos

En las pruebas del ESP32 hubo un hueco de 134 s entre dos reportes aceptados. El registro muestra la causa: un envío no terminó a tiempo (`Writing didn't complete in specified timeout`), el cliente MQTT cerró la conexión y se reconectó en 11 s. No fue un error del firmware sino una caída breve de la red, que se recuperó sola. Mientras tanto, R1 y R5 siguieron funcionando en el ESP32.

Con el umbral anterior de 3 minutos, una caída algo más larga habría generado una alerta por un problema que se resuelve solo. Con 5 minutos (5 reportes periódicos perdidos), la alerta marca desconexiones que el usuario sí debería revisar: Wi-Fi caído, equipo apagado o sin corriente. El supervisor corre cada 5 minutos, así que la desconexión se detecta entre 5 y 10 minutos después de la última lectura. Para un tendedero es suficiente, porque las reglas que protegen la ropa no dependen de la Nube.

La prueba de frecuencia (`tools/probar_esp32.py frecuencia`) ahora separa los intervalos que contienen una caída de MQTT. Esos miden la reconexión, que es otro requisito no funcional. Con esa separación, la corrida del 21 de noviembre da un máximo de 60,4 s con conexión (objetivo ≤ 65 s), y el hueco de 134,5 s aparece como caída.

### Por qué R2 va en la Nube

R2 vuelve a exponer la ropa cuando pasó la espera sin agua y hay luz. El ESP32 podría medir el tiempo sin agua por su cuenta, pero R2 va en la Nube por tres razones:

- **Usa el histórico:** cuándo paró la lluvia, aunque el ESP32 se haya reiniciado entretanto.
- **No es urgente:** exponer la ropa unos minutos más tarde no la daña. Lo urgente (resguardar con lluvia o de noche) está en el Edge.
- **Es la regla que conviene cambiar sin reprogramar el objeto:** la espera la ajustan la voz y R4, y la condición de exponer podría sumar datos externos, como el pronóstico del clima, sin tocar el firmware.

### Por qué R4 duplica la espera y no pasa a modo manual

R4 protege el servo cuando la lluvia es intermitente y la espera es corta. En ese caso R2 vuelve a exponer la ropa entre un chubasco y otro, y R1 la resguarda con cada lluvia nueva. Esperar más antes de volver a exponer frena ese vaivén.

- **El modo no cambia.** La primera versión pasaba a modo `manual`, que apagaba también R1: si después alguien exponía la ropa, ninguna regla la protegía de la siguiente lluvia.
- **No agrega estado nuevo.** Usa un parámetro que ya existe, ya está en el Shadow y Alexa ya informa al consultar el modo. El usuario lo puede bajar otra vez por voz («espera treinta minutos para volver a exponer»).
- **Solo actúa al cruzar el límite** (el 7.º movimiento de la hora). Los siguientes movimientos de esa hora no vuelven a duplicar la espera.

Con la espera inicial de 30 minutos, R2 genera como mucho unos 4 movimientos por hora, así que R4 casi nunca actúa. Se activa cuando el usuario configuró una espera corta (el mínimo es 15 minutos) y la lluvia va y viene, que es justamente el caso en que el brazo se mueve de más.

Para contar los movimientos, R4 suma los guardados en la hora anterior al mensaje y el movimiento que trae el mensaje. La misma publicación dispara en paralelo la Lambda de almacenamiento, así que este movimiento puede no estar guardado todavía. Contarlo aparte da el mismo resultado sin importar cuál de las dos termine antes.

### Para qué sirven el LDR y el LED

| Componente | Función | Por qué en este tendedero |
|---|---|---|
| LDR | Detectar la noche (R5) y la luz para volver a exponer (R2). | En una casa, la ropa no se deja afuera de noche: el sereno la vuelve a humedecer. Mide la luz real en lugar de usar la hora, porque la hora de anochecer cambia con la estación y la hora no sabe si el día está muy oscuro. También da el dato de horas de luz para los reportes. |
| LED | Luz para recoger la ropa de noche, encendida por voz. Se apaga sola a los 10 minutos. | De noche la ropa queda resguardada bajo el techo pero sigue colgada; quien sale a recogerla necesita luz. En el prototipo es un LED; en el producto sería una tira LED de 12 V, dentro del límite de baja tensión. |

El LED no tiene regla automática: la luz la decide solo el usuario, así no hay conflicto entre la voz y la lógica automática. El apagado a los 10 minutos lo hace el ESP32 y se registra con origen `edge`.

### Convivencia de la voz con la lógica automática

| Orden de voz | Modo `manual` | Modo `automatico` |
|---|---|---|
| Resguardar | Se cumple | Se cumple |
| Exponer | Se cumple | Se cumple si no hay agua y es de día. Con agua o de noche, la Lambda responde con una explicación y no escribe; si igual llega, el ESP32 la rechaza y escribe `desired = {posicion: resguardado, origen: edge}` |
| Encender / apagar la luz | Se cumple | Se cumple. La luz no tiene regla automática: solo se apaga sola a los 10 minutos. |

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

### Varios tendederos por usuario

Un usuario puede tener más de un tendedero en su casa: uno en el patio y otro en la terraza, por ejemplo. Para que Alexa los distinga, cada vinculación lleva un **nombre** que el usuario elige al vincular. En la práctica 3 la tabla tenía solo `userId` como clave, así que un usuario podía tener un único tendedero.

Tabla `tendedero_vinculaciones` (P4, clave compuesta):

| Campo | Tipo | Uso |
|---|---|---|
| `userId` | String, clave de partición | `context.System.user.userId` |
| `thingName` | String, clave de ordenamiento | Thing validado. Un usuario no puede vincular dos veces el mismo. |
| `nombre` | String | Nombre que dio el usuario («patio», «terraza»). Único entre los tendederos del mismo usuario; la Lambda lo compara sin tildes ni mayúsculas. |
| `fechaVinculacion` | String ISO-8601 UTC | Cuándo se vinculó. Se conserva si el usuario lo renombra. |

Ejemplo ficticio: un usuario con dos tendederos y un segundo usuario de la misma casa.

| `userId` | `thingName` | `nombre` |
|---|---|---|
| `amzn1.ask.account.A` | `tendedero-inteligente` | patio |
| `amzn1.ask.account.A` | `tendedero-prueba2` | terraza |
| `amzn1.ask.account.B` | `tendedero-inteligente` | casa |

Decisiones de diseño:

- **`thingName` como clave de ordenamiento, no `nombre`.** Lo estable es el Thing; el nombre lo puede cambiar el usuario. Así, renombrar es reescribir el mismo ítem y no puede quedar el mismo Thing dos veces con nombres distintos.
- **No hay un tendedero «activo» guardado.** Con varios tendederos, cada orden dice a cuál va; si no lo dice, Alexa pregunta. Se descartó recordar el último elegido: el usuario puede olvidar cuál era y mover el tendedero equivocado, y el aviso llegaría cuando la orden ya está enviada.
- **Un Thing puede estar vinculado a varios usuarios.** En una casa con dos cuentas de Alexa, cada persona vincula el mismo tendedero con su propio nombre.
- **Máximo de 10 tendederos por usuario** (`MAX_TENDEDEROS`). Acota la `Query` de cada solicitud y la lista que Alexa lee al preguntar en cuál actuar.
- **Sin índice por `thingName`.** Ningún flujo actual necesita saber qué usuarios tiene un tendedero. Si más adelante se avisa por voz de una alerta (R3) a los dueños de un Thing, se agrega un índice global `thingName-index`.

Patrones de acceso que satisface:

| Patrón | Operación |
|---|---|
| Tendederos de un usuario (en cada solicitud y en «qué tendederos tengo») | `Query` por `userId`, con lectura consistente |
| Vincular o renombrar un tendedero | `PutItem` (`userId`, `thingName`) |
| Desvincular un tendedero | `DeleteItem` (`userId`, `thingName`) |
| Reportes de un usuario (mockups) | `Query` por `userId` → `thingName` de cada tendedero → `Query` en `tendedero_historico` |

### A qué tendedero va cada orden

1. **Un solo tendedero:** a ese. El usuario no tiene que nombrarlo.
2. **Varios, con nombre en la frase** («resguarda el tendedero **del patio**»): a ese. Si no existe, Alexa dice cuáles tiene el usuario y no escribe nada.
3. **Varios, sin nombre en la frase:** Alexa pregunta «¿En cuál tendedero? Tienes patio o terraza». La Lambda responde con la directiva `Dialog.ElicitSlot` sobre el slot `nombre` y devuelve el mismo intent con sus demás slots, como la condición de una calibración. El usuario contesta («el del patio»), Alexa vuelve a llamar a la Lambda con el nombre completado y la orden original se cumple. Mientras no se sabe cuál, no se lee ni se escribe ningún Shadow.

Con varios tendederos, cada respuesta empieza con el nombre («Tendedero patio: el sensor detecta agua»), para confirmar sobre cuál actuó Alexa.

Al vincular:

- El primer tendedero puede no tener nombre; en ese caso se llama «principal».
- Desde el segundo, el nombre es obligatorio. Alexa lo pide y la Lambda rechaza un nombre repetido.
- Volver a vincular el mismo código con otro nombre lo renombra, sin crear otra fila.

Desvincular sigue la misma regla: con varios tendederos y sin nombre, Alexa pregunta cuál.

Flujo de la Lambda:

| Momento | Operaciones |
|---|---|
| Vincular | Validar formato del código → `Query` al índice por código → `DescribeThing` → `Query` de los tendederos del usuario (nombre repetido, tope) → `PutItem` en vinculaciones. |
| Cualquier otro intent | `Query` por `userId` → tendedero único, nombrado o preguntado → Shadow del Thing. El código no interviene. |
| Desvincular | `Query` por `userId` → `DeleteItem` del tendedero elegido. |

No se asigna un Thing por defecto a usuarios sin vincular.

## Modelo del histórico (RF11, RF12, RF15)

`tendedero_historico` es la tabla de análisis: de ella salen los reportes del usuario. También es la memoria de la lógica en la Nube (R2 lee cuándo paró la lluvia, R3 la última lectura y R4 los movimientos de la última hora).

### Tres tablas, tres responsabilidades

| Tabla | Responde | Cambia |
|---|---|---|
| `tendedero_dispositivos` | Qué tendederos existen y su código. La usan la vinculación y el supervisor (lista de Things que revisan R2 y R3). | Al dar de alta un tendedero |
| `tendedero_vinculaciones` | De quién es cada tendedero y cómo lo llama. | Al vincular o desvincular |
| `tendedero_historico` | Qué le pasó a cada tendedero. | Cada minuto y con cada evento |

### Qué se guarda y para qué

Se parte de las decisiones del usuario, no de la forma de los mensajes:

| Reporte | Pregunta del usuario | Datos que usa |
|---|---|---|
| A. Secado de la semana | ¿Cuántas horas estuvo afuera la ropa y cuánta luz recibió? | Eventos de posición y de luz |
| B. Mejor momento para tender | ¿A qué horas suele llover y cuándo hay más luz? | Eventos de agua y lecturas de `luz_adc` |
| C. Protección | ¿Cuántas veces la protegió de la lluvia y de la noche? ¿Quién movió el tendedero? | Eventos de posición con `origen`, `agua_detectada` y `oscuro` |
| D. Estado del equipo | ¿Estuvo conectado? ¿Cuánto se movió el brazo? | Alertas de R3 y R4, eventos de posición, `lectura_adc` |

Los mockups de los cuatro reportes, con la consulta de cada elemento, están en [MOCKUPS.md](MOCKUPS.md).

Las duraciones (horas afuera, de lluvia, de luz) no se guardan: se calculan restando las fechas de dos eventos seguidos. Los reportes se calculan al abrirlos, consultando el período que muestran.

| Tipo de ítem | `sk` | Campos | TTL | Por qué |
|---|---|---|---|---|
| Lectura | `lectura#<fecha>` | `lectura_adc`, `agua_detectada`, `luz_adc`, `oscuro`, `ts_dispositivo` (y `luz_simulada` en ensayos) | 30 días | Una por mensaje publicado, para medir la integridad del almacenamiento. Sirven para la curva de luz del último mes y la deriva del sensor. Posición, modo, origen y LED no se repiten: están en los eventos. |
| Evento de posición | `evento#<fecha>#posicion` | `posicion`, `origen`, `agua_detectada`, `oscuro` | 365 días | El contexto distingue la protección por lluvia (R1) de la de la noche (R5); `origen` dice quién lo movió. |
| Evento de agua | `evento#<fecha>#agua` | `agua_detectada` | 365 días | Inicio y fin de cada lluvia. |
| Evento de luz | `evento#<fecha>#luz` | `oscuro` | 365 días | Anochecer y amanecer: horas de luz por día. |
| Evento de modo | `evento#<fecha>#modo` | `modo` | 365 días | Cuándo se apagó la protección automática. |
| Evento del LED | `evento#<fecha>#led` | `led`, `origen_led` | 365 días | Lo pide RF12 (cambio de un actuador con su origen). Aporta poco al análisis. |
| Alerta | `alerta#<fecha>#sin_reporte` o `#exceso_movimientos` | Detalle de la alerta | 365 días | Disponibilidad (R3) y espera demasiado corta (R4). |

Todos los ítems llevan `thingName`, `tipo`, `ts_iot` (hora de la regla), `ts_guardado` (hora de la Lambda) y `ttl`.

### Patrones de acceso

| Patrón | Operación |
|---|---|
| Lecturas de un tendedero en un rango de fechas | `Query` `thingName = X AND sk BETWEEN lectura#<desde> AND lectura#<hasta>` |
| Eventos de un tendedero en un rango (todos los tipos) | `Query` `sk BETWEEN evento#<desde> AND evento#<hasta>`; el tipo se filtra por `cambio` |
| Alertas de un tendedero | `Query` `sk BEGINS_WITH alerta#` |
| Reportes de un usuario | `Query` en `tendedero_vinculaciones` por `userId` → una consulta por tendedero |

No hacen falta índices secundarios: todos los reportes son de un tendedero en un rango de fechas. Con 10 a 20 eventos por día, un año son unos 7 000 eventos por tendedero, así que no hace falta un resumen diario precalculado. Queda como mejora si hubiera miles de tendederos. Los reportes para la empresa, que juntan todos los tendederos, necesitarían otro índice o un proceso de agregación, y quedan fuera de esta práctica.

### Reglas que llenan la tabla

- `tendedero_lecturas` (`update/accepted`): cada reporte del ESP32 → una lectura.
- `tendedero_cambios` (`update/documents`): entrega todos los documentos, sin filtro en el SQL, y la Lambda compara el anterior con el actual. Comparar en el SQL perdía el primer valor de un campo que el documento anterior no tenía, por ejemplo después de limpiar el Shadow. Cuesta una invocación más por reporte, dentro de la capa gratuita.

Datos sin conexión: el ESP32 no acumula lecturas mientras está desconectado, así que no se guardan. El hueco queda marcado por la alerta `sin_reporte` de R3.

## Intents

| Intent | Slot | Comportamiento |
|---|---|---|
| `VincularThingIntent` | `codigo` (`AMAZON.NUMBER`), `nombre` (`NombreTendedero`) | Buscar el Thing por código, validar que existe y agregarlo a los tendederos del usuario con ese nombre. Reemplaza también a `CambiarThingIntent` de la práctica 3. |
| `ListarTendederosIntent` | — | Decir los tendederos del usuario. |
| `DesvincularThingIntent` | `nombre` (opcional) | Borrar una vinculación. Con varios tendederos y sin nombre, pregunta cuál. |
| `ConsultarAguaIntent` | `nombre` (opcional) | Responder con `reported.agua_detectada`. |
| `ExponerTendederoIntent` | `nombre` (opcional) | Escribir `desired = {posicion: expuesto, origen: voz}`, salvo en automático con agua (ver convivencia). |
| `ResguardarTendederoIntent` | `nombre` (opcional) | Escribir `desired = {posicion: resguardado, origen: voz}`. |
| `ConsultarPosicionIntent` | `nombre` (opcional) | Decir la posición y **el motivo** (lluvia, noche, orden de voz o modo manual) y cuándo volverá a salir, con `posicion`, `agua_detectada`, `oscuro`, `origen`, `modo` y `minutos_reexponer`. Indica si hay una orden pendiente. |
| `CalibrarSensorIntent` | `condicion` (`CondicionSensor`: `seco` / `mojado`) | Escribir `desired.calibracion_solicitada`. |
| `ConsultarCalibracionIntent` | — | Informar si el último pedido está pendiente, aplicado, rechazado o caducado. |
| `CambiarModoIntent` | `modo` (`ModoOperacion`: `manual` / `automatico`) | Escribir `desired.modo`. |
| `ConsultarModoIntent` | — | Leer `reported.modo` y `minutos_reexponer`, e indicar si hay un cambio pendiente. |
| `ConfigurarEsperaIntent` | `minutos` (`AMAZON.NUMBER`) | Validar 15–240 y escribir `desired.minutos_reexponer`. |
| `EncenderLuzIntent` / `ApagarLuzIntent` | `nombre` (opcional) | Escribir `desired.led` con `origen_led: voz`. Al encender, avisa que se apaga sola a los 10 minutos. |
| `ConsultarLuzIntent` | `nombre` (opcional) | Leer `reported.led`. |

Todos los intents que actúan sobre un tendedero tienen el slot `nombre` (opcional), aunque la tabla no lo repita en cada fila. Así se puede nombrar el tendedero en la frase y la Lambda puede preguntarlo con `Dialog.ElicitSlot`, que solo funciona sobre un slot que el intent tiene en el modelo.

`NombreTendedero` es un tipo propio con valores de ejemplo (patio, terraza, azotea, balcón, jardín, lavandería…). Alexa también acepta nombres fuera de la lista. La Lambda quita «el», «del», «de la» y «tendedero» de lo que llega en el slot.

## Seguridad y coherencia

- La política IoT usa `${iot:Connection.Thing.ThingName}`: una sola política sirve para todos los tendederos, y cada certificado solo accede al Shadow de su propio Thing.
- El código de la etiqueta no prueba la posesión física del objeto. Quien lo conozca puede vincularlo. Un botón de emparejamiento en el dispositivo queda como mejora futura.
- `userId` identifica una cuenta con la Skill habilitada. Puede cambiar si el usuario deshabilita y vuelve a habilitar la Skill.
- La Lambda solo lee y escribe ítems con el `userId` de la solicitud: un usuario no puede ver, elegir ni desvincular los tendederos de otro.
- Escribir `desired` no prueba movimiento físico. Alexa dice «He solicitado...» y la posición reportada es una estimación por tiempo.
- Los pulsos del servo no están en el Shadow: dependen del mecanismo, no del ambiente, y un valor incorrecto puede dañar el servo.
