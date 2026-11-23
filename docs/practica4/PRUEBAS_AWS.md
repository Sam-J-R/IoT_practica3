# Pruebas de AWS paso a paso (encargada de AWS)

Todo se hace desde la **consola de AWS**, región **Ohio `us-east-2`**, sin la CLI. Python solo hace falta en los pasos 6 y 7, para medir y estimar con los archivos descargados; esos scripts no se conectan a AWS.

Los eventos de prueba están en [aws/eventos-prueba/](../../aws/eventos-prueba). Se copian y pegan en la pestaña **Test** de cada Lambda. Las respuestas esperadas de este documento salen de correr esos mismos eventos contra el código del repositorio.

Durante las pruebas se usa el Thing **`tendedero-prueba2`**, que no tiene ESP32. Así no se mueve el tendedero físico y no hace falta Samuel hasta el paso 6.

## 1. Aplicar los cambios

Seguir **«Orden de todo lo pendiente»** al final de [GUIA_AWS.md](GUIA_AWS.md), pasos 1 a 7. El modelo de Alexa (paso 4) lo carga Katherine, y el firmware (paso 9), Samuel. Los dos pueden hacerlo en paralelo.

En el paso 6, además de limpiar los Shadows, cargar en `tendedero-prueba2` el estado simulado de [shadow-prueba2.example.json](../../aws/shadow-prueba2.example.json). Ya tiene los campos de la P4: modo, nivel de luz, LED.

## 2. Verificar la configuración

Revisar cada punto en la consola. Si alguno no se cumple, volver al paso de la guía que lo configura.

| ✓ | Qué revisar | Dónde |
|---|---|---|
| ☐ | `tendedero_vinculaciones` con partition key `userId` y sort key `thingName` | DynamoDB → Tables → la tabla → Overview |
| ☐ | `tendedero_dispositivos` con el índice `codigoVinculacion-index` activo y los dos tendederos | DynamoDB → Tables → la tabla → Indexes / Explore items |
| ☐ | `tendedero_historico` con clave `thingName` + `sk` y TTL activo sobre `ttl` | DynamoDB → Tables → la tabla → Additional settings |
| ☐ | Rol de la Lambda de Alexa: `Query`, `PutItem` y `DeleteItem` en vinculaciones; IoT sobre `thing/tendedero-*` | IAM → Roles → `tendedero-inteligente-lambda-role` |
| ☐ | Rol de lógica con `iot:UpdateThingShadow` (R4 escribe la espera) | IAM → Roles → `tendedero-logica-lambda-role` |
| ☐ | Las cuatro Lambdas con el código nuevo: Alexa, almacenamiento, lógica y supervisor | Lambda → cada función → Code (fecha de *Last modified*) |
| ☐ | Supervisor sin `MINUTOS_SIN_REPORTE`, o con valor `5` | Lambda → `tendedero_supervisor` → Configuration → Environment variables |
| ☐ | Reglas `tendedero_lecturas`, `tendedero_cambios` y `tendedero_movimientos` activas; el SQL de `tendedero_cambios` termina en `WHERE NOT isUndefined(current.state.reported)` | AWS IoT → Message routing → Rules |
| ☐ | Supervisor programado cada 5 minutos | Lambda → `tendedero_supervisor` → Configuration → Triggers (EventBridge `rate(5 minutes)`) |
| ☐ | Shadows sin `cubierta`, `sensor_raw`, `luz_adc` ni `desired.origen_led` | AWS IoT → Things → cada Thing → Device Shadows |
| ☐ | Alerta de facturación creada | Billing and Cost Management → Budgets |

## 3. Lambda de Alexa

**Lambda → `tendedero-inteligente-alexa` → Test.** Para cada archivo `alexa-NN-*.json`, en orden: **Create new event** → nombre igual al archivo → pegar el contenido → **Save** → **Test**.

Todos usan el mismo usuario de prueba (`amzn1.ask.account.PRUEBA-CONSOLA`) y el código `715204` de `tendedero-prueba2`. En el resultado, buscar el texto en `response.outputSpeech.ssml`.

| Evento | Respuesta esperada (inicio) | Qué revisar además |
|---|---|---|
| `alexa-01-vincular` | «He vinculado tu tendedero terraza…» | DynamoDB → `tendedero_vinculaciones`: un ítem con ese `userId`, `thingName = tendedero-prueba2` y `nombre = terraza` |
| `alexa-02-listar` | «Tienes un tendedero vinculado: terraza.» | — |
| `alexa-03-consultar-agua` | «El sensor no detecta agua.» | — |
| `alexa-04-como-esta` | «…el tendedero está expuesto y recibiendo luz. Se resguardará solo si llueve o anochece.» | Es la consulta del motivo: usa `oscuro` y `modo` |
| `alexa-05-modo-manual` | «He activado el modo manual…» | Shadow de `tendedero-prueba2`: `desired.modo = manual` |
| `alexa-06-resguardar` | «He solicitado que el tendedero quede resguardado…» | `desired.posicion = resguardado`, `desired.origen = voz` |
| `alexa-07-exponer` | «He solicitado que el tendedero quede expuesto…» | `desired.posicion = expuesto` |
| `alexa-08-espera-45` | «…después de 45 minutos sin agua, cuando haya luz.» | `desired.minutos_reexponer = 45` |
| `alexa-09-encender-luz` | «He pedido encender la luz… Se apagará sola en 10 minutos.» | `desired.led = encendido` y **sin** `desired.origen_led` |
| `alexa-10-modo-automatico` | «He activado el modo automático…» | `desired.modo = automatico` |
| `alexa-11-consultar-modo` | «…está en modo automático. Resguarda la ropa si llueve o anochece…» | — |
| `alexa-12-desvincular` | «He eliminado la vinculación de tu tendedero.» | El ítem del paso 01 ya no está en `tendedero_vinculaciones` |

### 3.1 Un usuario con dos tendederos

Prueba la clave `userId` + `thingName` y el nombre de cada tendedero. Se hace **entre `alexa-11` y `alexa-12`**, cuando el usuario de prueba ya tiene vinculada la «terraza».

Usa el código `483920` de `tendedero-inteligente`. Si en tu tabla `tendedero_dispositivos` el código es otro, cámbialo en el evento `alexa-13` (aparece dos veces). Ninguno de estos eventos mueve el tendedero físico: solo lo vinculan y leen su Shadow.

| Evento | Respuesta esperada | Qué revisar además |
|---|---|---|
| `alexa-13-vincular-segundo` | «He vinculado tu tendedero patio. Ahora tienes 2 tendederos: patio y terraza…» | `tendedero_vinculaciones`: **dos ítems con el mismo `userId`**, uno `tendedero-prueba2` / `terraza` y otro `tendedero-inteligente` / `patio`. Esta es la captura `02-vinculaciones.png` |
| `alexa-14-agua-sin-nombre` | «¿En cuál tendedero? Tienes patio o terraza.» | En el JSON de la respuesta, `directives` tiene `Dialog.ElicitSlot` con `slotToElicit = nombre`: Alexa pregunta y conserva la orden |
| `alexa-15-agua-del-patio` | «Tendedero patio: El sensor…» | La respuesta empieza con el nombre: con varios tendederos, Alexa confirma sobre cuál actuó |
| `alexa-16-desvincular-patio` | «He desvinculado el tendedero patio. Tu tendedero se llama terraza.» | Queda un solo ítem del usuario, el de la terraza |

Después sigue con `alexa-12-desvincular`. Con un solo tendedero, ya no pregunta cuál.

**Si una respuesta es «No pude completar la solicitud…»:** abrir **Monitor → View CloudWatch logs**, buscar `AccessDeniedException` y revisar el rol (paso 4 de la guía). Si el error es de IoT, ver el procedimiento de respaldo del paso 4.

**Al terminar:** `tendedero-prueba2` no tiene un ESP32 que atienda las órdenes, así que `desired` queda con valores pendientes. Para limpiarlo, en su Device Shadow → **Edit**, pegar y guardar:

```json
{"state": {"desired": null}}
```

## 4. Reglas y almacenamiento sin el ESP32

Aquí se simula al ESP32 publicando en el Shadow de `tendedero-prueba2`. Así se prueba el recorrido completo: **Shadow → regla → Lambda → DynamoDB**.

**AWS IoT → MQTT test client → Publish to a topic.** Tema:

```
$aws/things/tendedero-prueba2/shadow/update
```

**4.1 Lectura.** Publicar:

```json
{"state": {"reported": {"lectura_adc": 120, "agua_detectada": false, "posicion": "expuesto", "origen": "nube", "modo": "automatico", "nivel_luz": 80, "oscuro": false}}}
```

Esperado, en **DynamoDB → `tendedero_historico` → Explore items**, consultando `thingName = tendedero-prueba2`:

- Un ítem `lectura#<fecha>` con `lectura_adc`, `agua_detectada`, `nivel_luz` y `oscuro`, y **sin** `posicion` ni `modo` (esos van en los eventos).
- Los campos `ts_iot`, `ts_guardado` y `ttl`.

**4.2 Empieza a llover y el ESP32 resguarda la ropa.** Publicar:

```json
{"state": {"reported": {"lectura_adc": 1800, "agua_detectada": true, "posicion": "resguardado", "origen": "edge", "modo": "automatico", "nivel_luz": 60, "oscuro": false}}}
```

Esperado:

- Otra lectura.
- `evento#<fecha>#agua` con `agua_detectada = true`.
- `evento#<fecha>#posicion` con `posicion = resguardado`, `origen = edge`, `agua_detectada = true` y `oscuro = false`. Con esto el reporte de protección cuenta «la protegió de la lluvia».
- En **CloudWatch** de `tendedero_logica`: una ejecución nueva (líneas `START`, `END` y `REPORT`), sin errores. La regla `tendedero_movimientos` se disparó por el cambio de posición en modo automático, pero con un solo movimiento no supera el límite. Lambda no escribe en el log el valor que devuelve, así que `"accion": "ninguna"` no aparece: basta con ver la ejecución.

**Cómo ver los logs:** las reglas de AWS IoT no tienen logs propios. Lo que se mira es la Lambda que invocan, en **CloudWatch → Log groups → `/aws/lambda/<nombre de la función>`** → el *log stream* más reciente. También se llega desde **Lambda → la función → Monitor → View CloudWatch logs**. En `tendedero_almacenamiento`, cada mensaje guardado deja una línea `Guardados N items de tendedero-prueba2`.

**Cuántos ítems deja cada publicación:** siempre **una lectura** (regla `tendedero_lecturas`) y **un evento por cada dato que cambió** (regla `tendedero_cambios`). En 4.1 no cambió nada respecto del Shadow cargado (seguía expuesto, seco y de día), así que solo hay lectura. En 4.2 cambiaron el agua y la posición, así que hay una lectura y dos eventos.

**4.3 Mensaje inválido.** Publicar:

```json
{"state": {"reported": {"lectura_adc": 9999}}}
```

Esperado: **no** aparece una lectura nueva, y en CloudWatch de `tendedero_almacenamiento` aparece `Mensaje descartado: lectura_adc=9999 fuera de rango 0..4095`. Es el «descarte correcto de mensajes inválidos» que pide la rúbrica.

Al terminar, volver a cargar [shadow-prueba2.example.json](../../aws/shadow-prueba2.example.json) en el Shadow de `tendedero-prueba2`.

## 5. Lambdas de la Nube, una por una

En la pestaña **Test** de cada función, con el evento indicado:

| Función | Evento | Respuesta esperada |
|---|---|---|
| `tendedero_almacenamiento` | `almacenamiento-lectura` | `{"guardados": 1}` y una lectura nueva sin `posicion` ni `modo` |
| `tendedero_almacenamiento` | `almacenamiento-cambio-lluvia` | `{"guardados": 2}`: eventos de agua y de posición |
| `tendedero_almacenamiento` | `almacenamiento-invalido` | `{"guardados": 0, "descartado": "lectura_adc=9999 fuera de rango 0..4095"}` |
| `tendedero_logica` | `logica-movimiento` | `{"accion": "ninguna", "movimientos": …}` sin errores de permisos |
| `tendedero_supervisor` | `supervisor` (`{}`) | Un resumen como `{"revisados": 2, "sin_reporte": …, "reexpuestos": …}` |

Sobre el supervisor: `tendedero-prueba2` no reporta solo, así que pasados 5 minutos sin lecturas aparece en `sin_reporte` y se crea una alerta `alerta#<fecha>#sin_reporte` en el histórico. Eso es R3 funcionando. La alerta se crea una sola vez por desconexión.

Los eventos de almacenamiento usan una fecha fija de noviembre de 2026, así que esos ítems quedan al principio de la consulta. Se pueden borrar desde Explore items si molestan.

## 6. Integridad y latencia del almacenamiento (con Samuel)

Lo mide la rúbrica: al menos el 99 % de los mensajes guardados, con una latencia de 5 s como máximo.

1. **Samuel**, con el perfil `tendedero_ensayo` cargado, corre unos 15 a 20 minutos sin tocar el sensor:
   ```powershell
   python tools/probar_esp32.py --puerto COM3 frecuencia --minutos 15
   ```
   y te pasa la carpeta que se crea en `resultados_p4/` (con su `log.csv`).
2. **Tú**, en **DynamoDB → `tendedero_historico` → Explore items → Query**:
   - Partition key `thingName` = `tendedero-inteligente`.
   - Sort key **Begins with** `lectura#`.
   - **Run**, después **Actions → Download results to CSV**. Si hay más de una página de resultados, avanzar hasta la última antes de descargar.
3. Guardar el CSV en la misma carpeta de Samuel como `lecturas.csv` y correr:
   ```powershell
   python tools/medir_almacenamiento.py --log resultados_p4/<carpeta>/log.csv --items resultados_p4/<carpeta>/lecturas.csv
   ```
4. Esperado: `Integridad: … % … CUMPLE` y `Latencia (ts_guardado - ts_dispositivo): … CUMPLE`. Si dice `ts_iot` en lugar de `ts_dispositivo`, el ESP32 no tenía el perfil de ensayo cargado.
5. Guardar la salida en `resultados_p4/<carpeta>/almacenamiento.txt`.

## 7. Costo mensual

```powershell
python tools/estimar_costo.py --libre-lambda 1000000
```

Copiar la tabla que muestra a `resultados_p4/costo.md`, junto con el modelo de la cuenta. Para saberlo, ir a **Billing and Cost Management → Free Tier**: o lista límites por servicio (capa gratuita clásica) o muestra un saldo de créditos. El resultado de esta cuenta ya está en [resultados_p4/costo.md](../../resultados_p4/costo.md): plan con créditos y un costo estimado de entre USD 0,21 y 1,37 al mes.

No redirigir la salida con `>` en PowerShell: guarda el archivo en otra codificación y las tildes salen mal.

## 8. Evidencias

Las capturas están en [docs/evidencias/p4/aws/](../evidencias/p4/aws/README.md), numeradas: de la 01 a la 13 son de configuración y de la 20 en adelante, de pruebas. El README de esa carpeta explica qué muestra cada una.

Antes de agregar una captura nueva, revisar que no aparezcan claves, certificados ni el número de cuenta, que suele estar en los ARN y en el menú de arriba a la derecha. Si aparece, taparlo.

## 9. Subir tus resultados

Con tu cuenta de GitHub, para que cuente como tu aporte:

```powershell
git checkout practica4-maria
```
```powershell
git pull origin practica_4
```
```powershell
git add docs/evidencias/p4/aws resultados_p4
```
```powershell
git commit -m "test: pruebas de AWS y evidencias de la P4"
```
```powershell
git push origin practica4-maria
```

Después, en GitHub, crear el PR de `practica4-maria` hacia **`practica_4`**. Revisar que el desplegable **base** diga `practica_4` y no `main`.
