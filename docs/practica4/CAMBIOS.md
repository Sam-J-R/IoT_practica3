# Cambios de la práctica 4

Resumen de lo que cambió respecto a la práctica 3, por qué, y qué tiene que hacer cada integrante para ponerlo en marcha.

La entrega de la práctica 3 queda recuperable en la etiqueta de git `practica3-entrega`. Su documentación (`docs/`, evidencias y resultados) no se modificó. El código y las configuraciones sí se modificaron en su lugar.

## Documentos de esta carpeta

| Documento | Contenido |
|---|---|
| [CONTRATO.md](CONTRATO.md) | Shadow, tablas, intents y reglas de calibración. Es la referencia común. |
| [GUIA_AWS.md](GUIA_AWS.md) | Pasos para actualizar la cuenta de AWS. |
| [ALEXA.md](ALEXA.md) | Pasos para actualizar la Skill y frases de prueba. |

## 1. Qué cambió y por qué

### 1.1 Vinculación por código, sin nombres de Things en la configuración

**Antes.** La Lambda traducía lo que decía el usuario al nombre del Thing con un mapa en la variable de entorno `THING_ALIASES_JSON`. Cada Thing nuevo obligaba a editar la configuración de la Lambda, y Alexa transcribía los nombres de formas distintas («prueba dos», «prueba 2»).

**Ahora.** Cada tendedero tiene un código de 6 dígitos en su etiqueta. El usuario dice ese código, Alexa lo recibe como número (`AMAZON.NUMBER`) y lo confirma, y la Lambda busca el Thing en la tabla nueva `tendedero_dispositivos`. Agregar un tendedero es agregar una fila: la Lambda no se toca.

La política IoT también dejó de nombrar un Thing concreto. Usa `${iot:Connection.Thing.ThingName}` y sirve para todos los tendederos.

El código solo se usa al vincular. En las demás solicitudes, el Thing se sigue resolviendo por `userId` en `tendedero_vinculaciones`, igual que antes.

### 1.2 Calibración del sensor sin recargar el programa

**Antes.** Los umbrales eran constantes de compilación en `calibracion_local.h`. Cambiar de ambiente obligaba a recompilar y cargar el programa.

**Ahora.** El usuario calibra desde Alexa en dos pasos guiados: «calibra el sensor seco» y «calibra el sensor mojado». El ESP32 mide el sensor, guarda la referencia en su memoria no volátil, calcula los umbrales y los publica en `reported.calibracion`. Los valores sobreviven a un reinicio, incluso sin red.

El usuario no dicta números: no tiene forma de saber qué valor poner, y un umbral mal escrito dejaría el sensor sin detectar lluvia. El dispositivo mide su propia realidad y rechaza una calibración incoherente.

### 1.3 Shadow en español

`sensor_raw` pasó a `lectura_adc`. Las palabras reservadas de AWS (`state`, `desired`, `reported`, `clientToken`…) no se pueden traducir.

### 1.4 El tendedero se mueve bajo un techo

**Antes.** Una cubierta se abría y se cerraba sobre el tendedero (`cubierta: abierta / cerrada`).

**Ahora.** El techo es fijo y un brazo gira el tendedero hasta dejarlo debajo (`posicion: expuesto / resguardado`). La maqueta es más simple y el servo mueve menos carga.

### 1.5 Reporte periódico cada 60 s

El respaldo periódico pasó de 5 s a 60 s. Los cambios de agua y de posición se siguen reportando de inmediato. Con 5 s, un dispositivo superaba las 500 000 actualizaciones al mes; con 60 s son unas 43 000.

### 1.6 Varios tendederos por usuario

**Antes.** `tendedero_vinculaciones` tenía solo `userId` como clave: cada usuario podía tener un tendedero, y vincular otro reemplazaba el anterior.

**Ahora.** La clave es `userId` + `thingName` y cada vinculación lleva un `nombre` que elige el usuario («patio», «terraza»).

- **Sin nombre en la frase:** las órdenes van al tendedero activo, que es el último que el usuario vinculó o eligió con «usa el tendedero de la terraza».
- **Con nombre en la frase** («resguarda el tendedero del patio»): la orden va a ese tendedero y el activo no cambia.
- **Con más de un tendedero:** Alexa antepone el nombre a cada respuesta, para que el usuario sepa sobre cuál actuó.

`CambiarThingIntent` se reemplaza por `SeleccionarTendederoIntent` y se agrega `ListarTendederosIntent`. El diseño, sus decisiones y los patrones de acceso están en [CONTRATO.md](CONTRATO.md#varios-tendederos-por-usuario).

Cambiar la clave obliga a recrear la tabla. Las vinculaciones de la práctica 3 se pierden y hay que volver a vincular ([GUIA_AWS.md](GUIA_AWS.md), paso 4.1).

## 2. Archivos modificados

| Área | Archivos | Cambio |
|---|---|---|
| Firmware | `include/CalibracionSensor.h` (nuevo) | Referencias en memoria no volátil, cálculo y validación de umbrales. |
| Firmware | `include/ServoTendedero.h` (antes `ServoCubierta.h`) | Posiciones `Expuesto` / `Resguardado`. |
| Firmware | `include/ClienteShadow.h`, `src/ClienteShadow.cpp` | Lee `posicion` y `calibracion_solicitada`; publica `lectura_adc` y `calibracion`. |
| Firmware | `src/Tendedero.cpp` | Ejecuta la calibración y usa los umbrales guardados. |
| Firmware | `include/config.h`, `include/calibracion.example.h` | Intervalo de 60 s, parámetros de calibración y constantes renombradas. |
| Firmware | `src/ServoTest.cpp`, `src/SensorShadowTest.cpp` | Nombres nuevos. `ServoTest` usa `E` y `R`. |
| Lambda | `lambda/lambda_function.py`, `lambda/lambda_deployment_p3.zip` | Vinculación por código, intents nuevos, sin alias. |
| Alexa | `alexa/interaction-model-es-MX.json` | Intents, slot numérico con confirmación y tipo `CondicionSensor`. |
| AWS | `aws/iot-certificate-policy.template.json` | Política genérica. |
| AWS | `aws/lambda-iam-policy.template.json` | Permiso `dynamodb:Query` sobre el índice. |
| AWS | `aws/dynamodb-dispositivos.*.json`, `aws/shadow-*.json` (nuevos) | Tabla nueva, ítems de ejemplo y JSON para migrar los Shadows. |
| Pruebas | `tests/` | 19 pruebas: vinculación por código, calibración y contrato. |
| Varios tendederos | `lambda/lambda_function.py` y el ZIP, `alexa/interaction-model-es-MX.json`, `aws/dynamodb-table.template.json`, `aws/lambda-iam-policy.template.json`, `aws/cloudformation/tendedero-base.yaml`, `tools/verificar_aws.py`, `tools/casos_alexa.json` | Clave `userId` + `thingName`, slot `nombre`, intents para elegir y listar, permisos `Query` y `UpdateItem`. |
| Varios tendederos | `tests/fake_vinculaciones.py` (nuevo), `tests/test_lambda_integration.py`, `tests/test_herramientas_nube.py`, `tests/test_static_contract.py` | Tabla con clave compuesta en memoria; pruebas de varios tendederos, nombres, tope, renombrado y desvinculación. |

## 3. Pasos para cada integrante

El orden importa: primero AWS, después el ESP32 y por último Alexa.

### 3.1 María — AWS

Seguir [GUIA_AWS.md](GUIA_AWS.md) de principio a fin:

1. Crear la tabla `tendedero_dispositivos` con su índice.
2. Registrar los dos tendederos con sus códigos.
3. Reemplazar la política IoT.
4. Actualizar la política del rol de la Lambda y recrear `tendedero_vinculaciones` con la clave `userId` + `thingName`.
5. Subir el ZIP nuevo y cambiar las variables de entorno.
6. Limpiar los Shadows.

### 3.2 Samuel — ESP32

1. Editar el archivo local `firmware/include/calibracion_local.h`. No está en el repositorio, así que el cambio es manual. Los **valores del servo se conservan**; solo cambian los nombres:

   | Antes | Ahora |
   |---|---|
   | `SERVO_ABIERTA_US` | `SERVO_EXPUESTO_US` |
   | `SERVO_CERRADA_US` | `SERVO_RESGUARDADO_US` |
   | `UMBRAL_SECO = 200` | `REFERENCIA_SECO_FABRICA = 0` |
   | `UMBRAL_AGUA = 800` | `REFERENCIA_AGUA_FABRICA = 2000` |

   Las referencias de fábrica son la lectura típica del sensor en seco y con agua. En los ensayos de la práctica 3 fueron 0 y entre 1750 y 2450; con 0 y 2000 los umbrales iniciales quedan en 200 y 600.

2. `secrets.h` no cambia.
3. Compilar y cargar el perfil `tendedero_shadow`:

   ```powershell
   pio run -d firmware -e tendedero_shadow -t upload
   ```

4. Abrir el monitor serie. Al arrancar debe aparecer una línea `[CALIBRACION] umbral_seco=… umbral_agua=…` y, tras conectar, `[SHADOW] reported aceptado`.
5. Cuando el brazo del tendedero esté montado, ajustar los pulsos del servo con el perfil `servo_test` (comandos `E` y `R`).

Para probar sin Alexa, el perfil `tendedero_ensayo` acepta por el monitor serie: `exponer`, `resguardar`, `calibrar_seco`, `calibrar_mojado`, `estado`, `wifi_off` y `wifi_on`.

### 3.3 Katherine — Alexa

Seguir [ALEXA.md](ALEXA.md):

1. Pegar el modelo nuevo en el JSON Editor, guardar y compilar.
2. Probar las frases de la tabla.

## 4. Pendientes

- **Evidencias.** Las capturas, los videos y los ensayos RNF son de la práctica 3 y muestran la cubierta. No se rehicieron.
- **Scripts de ensayo** (`ensayo_rnf.py`, `orden_offline.py`, `grabar_rnf.py`, `analizar_rnf.py`). Siguen usando `cubierta` y los comandos `abrir` / `cerrar`, así que **no funcionan con el firmware nuevo** hasta que se actualicen.
- **Informe.** `docs/INFORME.md` describe la práctica 3.
- **Circuito y fotos.** Los pines no cambiaron, pero el esquema y la foto muestran el montaje anterior.
- **Verificación en hardware.** El firmware compila en todos sus perfiles y las pruebas locales pasan. No se probó todavía en el ESP32 ni en las consolas de AWS y Alexa.

## 5. Recomendaciones a futuro

- **Alta automática de dispositivos.** Un script de aprovisionamiento o Fleet Provisioning, descritos en [GUIA_AWS.md](GUIA_AWS.md) §8.
- **Prueba de posesión.** El código de la etiqueta no demuestra que el usuario tenga el tendedero. Una mejora es un botón en el dispositivo que habilite la vinculación durante unos minutos, como el emparejamiento de un parlante Bluetooth.
- **Historial de datos.** El Shadow solo guarda el estado actual. Para análisis y predicción, una regla de AWS IoT puede copiar cada actualización a una tabla de historial con clave `thingName` y fecha. `lectura_adc` y los resultados de calibración ya quedan disponibles para eso.
- **Datos del producto.** `tendedero_dispositivos` puede crecer con ubicación, modelo y versión de firmware sin rediseño.
