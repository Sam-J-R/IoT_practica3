# Guía AWS — práctica 4

Pasos para actualizar la cuenta de AWS que ya funciona con la práctica 3. La [guía de la práctica 3](../GUIA_AWS.md) se conserva sin cambios y sigue siendo la referencia para crear los recursos desde cero. Todo se hace en **Ohio `us-east-2`**.

| Recurso | Cambio |
|---|---|
| Tabla `tendedero_dispositivos` | **Nueva.** |
| Política IoT del dispositivo | Se reemplaza por una genérica. |
| Rol de la Lambda | Permisos nuevos sobre DynamoDB e IoT restringido a los Things `tendedero-*`. |
| Lambda `tendedero-inteligente-alexa` | ZIP nuevo y cambio de variables de entorno. |
| Shadows de los dos Things | Se borran los atributos antiguos. |
| Tabla `tendedero_vinculaciones` | **Se recrea** con clave `userId` + `thingName`, para que un usuario tenga varios tendederos (paso 4.1). |
| Lógica de la Nube: tabla `tendedero_historico`, tres Lambdas, tres roles, tres reglas y la programación | **Nueva** (paso 9). |
| Alerta de facturación | **Nueva** (paso 10). |

No copiar certificados, claves privadas, contraseñas ni valores completos de `userId` al repositorio.

## 1. Crear la tabla de dispositivos

1. Abrir **DynamoDB → Tables → Create table**.
2. Nombre: `tendedero_dispositivos`.
3. Partition key: `thingName`, tipo **String**. Sin sort key.
4. En **Table settings**, elegir **Customize settings** y capacidad **On-demand**.
5. En **Secondary indexes → Create global index**:
   - Partition key: `codigoVinculacion`, tipo **String**.
   - Index name: `codigoVinculacion-index`.
   - Attribute projections: **Only keys**.
6. Crear la tabla y esperar a que la tabla y el índice estén en estado **Active**.

La definición equivalente está en [dynamodb-dispositivos.template.json](../../aws/dynamodb-dispositivos.template.json).

## 2. Registrar los dos tendederos

Cada tendedero necesita una fila con su código de vinculación. En **DynamoDB → Explore items → `tendedero_dispositivos` → Create item**, crear estos dos ítems:

| `thingName` (String) | `codigoVinculacion` (String) | `fechaAlta` (String) |
|---|---|---|
| `tendedero-inteligente` | `483920` | fecha de hoy, por ejemplo `2026-11-14T00:00:00Z` |
| `tendedero-prueba2` | `715204` | fecha de hoy |

Reglas del código:

- 6 dígitos, sin empezar en 0.
- Tipo **String** en DynamoDB, no Number. La Lambda lo busca como texto.
- Único: dos tendederos no pueden tener el mismo código. Si se repite, la Lambda rechaza la vinculación.

Los códigos de la tabla son los de ejemplo de [dynamodb-dispositivos.items.example.json](../../aws/dynamodb-dispositivos.items.example.json). Se pueden cambiar por otros; en ese caso, avisar a quien pruebe la Skill.

## 3. Reemplazar la política IoT

1. Abrir **AWS IoT Core → Security → Policies → `tendedero-inteligente-device-policy`**.
2. Elegir **Edit active version**.
3. Pegar el contenido de [iot-certificate-policy.template.json](../../aws/iot-certificate-policy.template.json).
4. Sustituir todas las apariciones de `ACCOUNT_ID` por el ID real de la cuenta.
5. Guardar como versión nueva y marcarla como **activa**.

La política ya no nombra `tendedero-inteligente`. Usa la variable `${iot:Connection.Thing.ThingName}`, que AWS reemplaza por el nombre del Thing al que está asociado el certificado que se conecta. Así una sola política sirve para todos los tendederos.

Esta variable solo funciona si se cumplen dos condiciones, que la práctica 3 ya cumplía:

- El certificado está asociado al Thing (**Things → `tendedero-inteligente` → Certificates**).
- El ESP32 se conecta con un *client ID* igual al nombre del Thing. El firmware ya lo hace.

Si el ESP32 deja de conectarse después de este cambio, volver a activar la versión anterior de la política y revisar esas dos condiciones.

## 4. Actualizar la política del rol de la Lambda

1. Abrir **IAM → Roles → `tendedero-inteligente-lambda-role`**.
2. Editar la política en línea y reemplazarla por [lambda-iam-policy.template.json](../../aws/lambda-iam-policy.template.json), sustituyendo `ACCOUNT_ID`.

Cambian dos declaraciones:

- **`FindDeviceByBindingCode`** (nueva): `dynamodb:Query` sobre el índice `codigoVinculacion-index` de `tendedero_dispositivos`. La Lambda no necesita más permisos sobre esa tabla, porque solo la lee por código.
- **`PersistUserBindings`**: sobre `tendedero_vinculaciones` pasa de `GetItem`, `PutItem` y `DeleteItem` a `Query`, `PutItem` y `DeleteItem`. `Query` lee todos los tendederos del usuario. `GetItem` se quita porque la Lambda ya no lo usa.

## 4.1 Recrear la tabla de vinculaciones

En DynamoDB, la clave de una tabla no se puede cambiar: hay que borrarla y crearla de nuevo. **Las vinculaciones actuales se pierden** y cada usuario vuelve a vincular su tendedero con el código, esta vez dándole un nombre.

1. Abrir **DynamoDB → Tables → `tendedero_vinculaciones` → Actions → Delete table**. Esperar a que desaparezca.
2. **Create table** con el nombre `tendedero_vinculaciones`:
   - Partition key: `userId` (String).
   - Sort key: `thingName` (String).
   - Capacidad: bajo demanda, igual que [dynamodb-table.template.json](../../aws/dynamodb-table.template.json).
3. Esperar a que quede en **Active**.

Hacerlo justo antes de subir la Lambda nueva (paso 5). La Lambda antigua usa `GetItem` con solo `userId` y falla contra la tabla nueva.

Las tres acciones de IoT (`DescribeThing`, `GetThingShadow` y `UpdateThingShadow`) pasan de `Resource: "*"` a `arn:aws:iot:us-east-2:ACCOUNT_ID:thing/tendedero-*`: la Lambda solo puede leer y escribir los Shadows de los tendederos, que es el mínimo privilegio que pide la rúbrica. El Shadow clásico de un Thing usa el ARN del propio Thing, así que este recurso alcanza.

Si después del cambio aparece `AccessDeniedException` en CloudWatch al consultar o mover el tendedero:

1. Revisar que `ACCOUNT_ID` se haya reemplazado por el número de la cuenta y que la región sea `us-east-2`.
2. Revisar que el nombre del Thing empiece con `tendedero-`.
3. Si aun así falla, volver temporalmente a `"Resource": "*"` (lo que se usó en la práctica 3) y documentarlo en el informe junto con el permiso mínimo para producción.

## 5. Actualizar la Lambda

1. Abrir **Lambda → `tendedero-inteligente-alexa` → Code → Upload from → .zip file**.
2. Subir [lambda_deployment_p3.zip](../../lambda/lambda_deployment_p3.zip). El nombre del archivo no cambió, pero su contenido sí.
3. En **Configuration → Environment variables**:

| Variable | Acción | Valor |
|---|---|---|
| `IOT_ENDPOINT` | Mantener | Endpoint ATS sin protocolo ni puerto. |
| `DDB_BINDINGS_TABLE` | Mantener | `tendedero_vinculaciones` |
| `DDB_DEVICES_TABLE` | **Agregar** | `tendedero_dispositivos` |
| `THING_ALIASES_JSON` | **Eliminar** | Ya no se usa. |

El handler (`lambda_function.lambda_handler`), el runtime y el trigger de Alexa no cambian.

## 6. Limpiar los Shadows

Los Shadows conservan atributos que ya no se usan: los de la práctica 3 (`cubierta` y `sensor_raw`), `desired.origen_led` y los de ensayo (`ts_dispositivo`, `luz_simulada`). Hay que borrarlos en los dos Things, o seguirán apareciendo en el documento. Si después se usa el perfil de ensayo, los de ensayo vuelven a aparecer: es lo esperado.

1. Abrir **AWS IoT Core → Things → `tendedero-inteligente` → Device Shadows → Classic Shadow → Edit**.
2. Pegar el contenido de [shadow-migracion-practica4.json](../../aws/shadow-migracion-practica4.json) y guardar. Escribir `null` en un atributo lo elimina.
3. Repetir en `tendedero-prueba2`.
4. En `tendedero-prueba2`, que no tiene ESP32, cargar además el estado simulado de [shadow-prueba2.example.json](../../aws/shadow-prueba2.example.json).

El Shadow de `tendedero-inteligente` se completa solo cuando el ESP32 se conecta con el firmware nuevo.

## 7. Verificaciones

- [ ] La tabla `tendedero_dispositivos` y su índice están en **Active**, con dos ítems.
- [ ] La versión activa de la política IoT contiene `${iot:Connection.Thing.ThingName}` y no contiene `ACCOUNT_ID`.
- [ ] El rol de la Lambda tiene la declaración `FindDeviceByBindingCode`, `PersistUserBindings` incluye `Query` y las acciones de IoT apuntan a `thing/tendedero-*`, no a `*`.
- [ ] `tendedero_vinculaciones` tiene partition key `userId` y sort key `thingName`.
- [ ] La Lambda tiene `DDB_DEVICES_TABLE` y ya no tiene `THING_ALIASES_JSON`.
- [ ] Los Shadows no muestran `cubierta` ni `sensor_raw`.
- [ ] Con el firmware nuevo cargado, el ESP32 se conecta y su Shadow muestra `posicion`, `agua_detectada`, `lectura_adc` y `calibracion`.
- [ ] Prueba directa en la Lambda (**Test**) o desde el simulador de Alexa: vincular con `715204` responde «He vinculado tu tendedero…».
- [ ] Con el mismo usuario, vincular también `483920` con otro nombre deja **dos ítems** con el mismo `userId` en `tendedero_vinculaciones`.

Si aparece `AccessDeniedException` en CloudWatch al vincular, revisar el ARN del índice en el rol: debe terminar en `table/tendedero_dispositivos/index/codigoVinculacion-index`.

## 8. Dar de alta un tendedero nuevo

Para esta práctica el alta es manual:

1. Crear el Thing con un nombre `tendedero-NNN`, generar su certificado y asociarle la política existente. La política ya es genérica: no hay que crear otra.
2. Elegir un código de 6 dígitos que no esté en uso y crear su fila en `tendedero_dispositivos`.
3. Cargar en el ESP32 su `secrets.h` con el nombre del Thing y su certificado.

### Recomendación a futuro

Con muchos dispositivos, el alta manual no escala. Hay dos formas de automatizarla:

- **Script de aprovisionamiento.** Un solo comando que genera el código, crea el Thing y el certificado, asocia la política, inserta la fila y entrega el `secrets.h`. La fila nunca queda desincronizada, porque la escribe el mismo proceso que crea el Thing.
- **Fleet Provisioning de AWS IoT.** El ESP32 sale de fábrica con un certificado genérico y se registra solo la primera vez que se conecta. Es la opción para producción masiva.

La tabla `tendedero_dispositivos` también queda preparada para guardar más datos de cada producto (ubicación, modelo, versión de firmware), que servirán para el análisis de datos de la siguiente fase.

## 9. Crear la lógica de la Nube (histórico, Lambdas, reglas y programación)

En la práctica 3 la cuenta solo tenía la Lambda de Alexa. La práctica 4 agrega todo lo que procesa y guarda los datos y ejecuta las reglas en la Nube. Si alguno de estos recursos ya existe en la cuenta, en lugar de crearlo hay que **actualizarlo** con los mismos valores (código, variables, SQL).

| Recurso | Para qué sirve |
|---|---|
| Tabla `tendedero_historico` | Guarda lecturas, eventos y alertas: es la tabla de análisis de los reportes (ver [CONTRATO.md](CONTRATO.md#modelo-del-histórico-rf11-rf12-rf15)). |
| Lambda `tendedero_almacenamiento` | Valida y guarda en el histórico lo que publica el ESP32 (RF11, RF12). |
| Lambda `tendedero_logica` | R4: si el brazo se mueve demasiado, duplica la espera antes de volver a exponer. |
| Lambda `tendedero_supervisor` | Cada 5 minutos, R2 (volver a exponer) y R3 (detectar que un tendedero dejó de reportar). |
| Reglas `tendedero_lecturas`, `tendedero_cambios`, `tendedero_movimientos` | Llevan cada publicación del Shadow a la Lambda que corresponde. |
| Programación de EventBridge | Ejecuta el supervisor cada 5 minutos. |
| Tres roles de IAM | Cada Lambda con solo los permisos que usa. |

El orden importa: primero la tabla, después los roles, las Lambdas, las reglas y la programación. Cada paso usa lo que se creó en el anterior.

### 9.1 Tabla `tendedero_historico`

1. **DynamoDB → Tables → Create table.**
2. **Table name:** `tendedero_historico`.
3. **Partition key:** `thingName`, tipo **String**.
4. **Sort key:** `sk`, tipo **String**.
5. **Table settings → Customize settings → Read/write capacity settings → Provisioned**, con **Auto scaling apagado** en lectura y escritura, y **2** unidades de lectura y **2** de escritura. Está dentro de la capa gratuita permanente (25 y 25), y un tendedero escribe más o menos una vez por minuto.
6. **Create table** y esperar a que quede en **Active**.
7. Abrir la tabla → **Additional settings → Time to Live (TTL) → Turn on** → atributo **`ttl`** → **Turn on TTL**. DynamoDB borra solo las lecturas de más de 30 días y los eventos y alertas de más de un año.

Las tres Lambdas usan el **mismo endpoint de IoT** que la de Alexa. Copiarlo de **Lambda → `tendedero-inteligente-alexa` → Configuration → Environment variables → `IOT_ENDPOINT`**, o de **AWS IoT → Settings → Device data endpoint**, sin `https://`.

### 9.2 Roles de IAM (uno por Lambda)

Repetir para cada fila:

| Rol | Política (en `aws/iam/`) | Qué permite |
|---|---|---|
| `tendedero-almacenamiento-role` | [tendedero-almacenamiento-role.json](../../aws/iam/tendedero-almacenamiento-role.json) | Solo `PutItem` en el histórico y escribir sus logs |
| `tendedero-logica-role` | [tendedero-logica-role.json](../../aws/iam/tendedero-logica-role.json) | Leer y escribir el histórico y escribir `desired` en el Shadow de los tendederos |
| `tendedero-supervisor-role` | [tendedero-supervisor-role.json](../../aws/iam/tendedero-supervisor-role.json) | Leer la lista de tendederos, leer y escribir el histórico, y leer y escribir el Shadow |

1. **IAM → Roles → Create role.**
2. **Trusted entity type: AWS service. Use case: Lambda** → **Next**.
3. En **Add permissions** no marcar nada → **Next**.
4. **Role name:** el de la tabla → **Create role**.
5. Abrir el rol → **Add permissions → Create inline policy → JSON**.
6. Pegar el contenido del archivo correspondiente y **reemplazar `ACCOUNT_ID`** por el número de la cuenta: 12 dígitos, sin guiones. Si los Things no están en `us-east-2`, cambiar también la región en cada ARN.
7. **Next** → **Policy name:** el mismo nombre del rol → **Create policy**.

Si el resumen de la política muestra «IoT: None» (en los roles de lógica y supervisor), es el mismo aviso del paso 4. Se comprueba con la prueba del paso 9.6 y, si falla, se cambia solo ese recurso a `"*"`.

### 9.3 Lambdas

Para cada fila de esta tabla:

| Función | Código | Rol | Timeout | Variables de entorno |
|---|---|---|---|---|
| `tendedero_almacenamiento` | [lambda/almacenamiento/lambda_function.py](../../lambda/almacenamiento/lambda_function.py) | `tendedero-almacenamiento-role` | 10 s | `DDB_HISTORY_TABLE` = `tendedero_historico` |
| `tendedero_logica` | [lambda/logica/lambda_function.py](../../lambda/logica/lambda_function.py) | `tendedero-logica-role` | 10 s | `DDB_HISTORY_TABLE` = `tendedero_historico`<br>`IOT_ENDPOINT` = el endpoint<br>`LIMITE_MOVIMIENTOS_HORA` = `6` |
| `tendedero_supervisor` | [lambda/supervisor/lambda_function.py](../../lambda/supervisor/lambda_function.py) | `tendedero-supervisor-role` | **30 s** | `DDB_HISTORY_TABLE` = `tendedero_historico`<br>`DDB_DEVICES_TABLE` = `tendedero_dispositivos`<br>`IOT_ENDPOINT` = el endpoint<br>`MINUTOS_SIN_REPORTE` = `5` |

1. **Lambda → Create function → Author from scratch.**
2. **Function name:** el de la tabla, exacto: las reglas y los roles lo usan.
3. **Runtime: Python 3.12.** Architecture: x86_64.
4. **Permissions → Change default execution role → Use an existing role** → el rol de la tabla → **Create function**.
5. **Code:** abrir `lambda_function.py` en el editor, borrar todo, pegar el contenido del archivo del repositorio y elegir **Deploy**. No hace falta subir un ZIP: estas Lambdas solo usan `boto3`, que ya viene incluido.
6. **Configuration → General configuration → Edit:** Memory 128 MB y el **Timeout** de la tabla → **Save**. El valor por defecto (3 s) es poco, sobre todo para el supervisor, que revisa todos los tendederos.
7. **Configuration → Environment variables → Edit:** agregar las variables de la tabla → **Save**.

### 9.4 Reglas de AWS IoT

Para cada fila:

| Regla | Sentencia SQL (copiar de `aws/reglas/`) | Acción: Lambda |
|---|---|---|
| `tendedero_lecturas` | [tendedero_lecturas.json](../../aws/reglas/tendedero_lecturas.json) | `tendedero_almacenamiento` |
| `tendedero_cambios` | [tendedero_cambios.json](../../aws/reglas/tendedero_cambios.json) | `tendedero_almacenamiento` |
| `tendedero_movimientos` | [tendedero_movimientos.json](../../aws/reglas/tendedero_movimientos.json) | `tendedero_logica` |

1. **AWS IoT → Message routing → Rules → Create rule.**
2. **Rule name:** el de la tabla → **Next**.
3. **SQL version: 2016-03-23.** En **SQL statement**, pegar el valor del campo `"sql"` del archivo JSON: solo el texto entre comillas, empezando por `SELECT` → **Next**.
4. **Rule actions → Action 1: Lambda** → elegir la función de la tabla → **Next**.
5. **Create.** La consola agrega sola el permiso para que la regla invoque la Lambda.

Para comprobarlo: **Lambda → la función → Configuration → Triggers** muestra la regla de AWS IoT. `tendedero_almacenamiento` muestra dos: lecturas y cambios.

### 9.5 Programar el supervisor cada 5 minutos

1. **Lambda → `tendedero_supervisor` → Add trigger.**
2. **Source: EventBridge (CloudWatch Events).**
3. **Create a new rule.** Rule name: `tendedero_supervisor_programado`. Rule type: **Schedule expression** → `rate(5 minutes)`.
4. **Add.**

A partir de ahí el supervisor corre solo. En **Monitor → View CloudWatch logs** aparece una ejecución cada 5 minutos.

### 9.6 Verificar

En la pestaña **Test** de cada función, con los eventos de [aws/eventos-prueba/](../../aws/eventos-prueba). El detalle está en el paso 5 de [PRUEBAS_AWS.md](PRUEBAS_AWS.md):

- [ ] `tendedero_almacenamiento` con `almacenamiento-lectura` → `{"guardados": 1}`, y la lectura aparece en **DynamoDB → `tendedero_historico` → Explore items**.
- [ ] `tendedero_logica` con `logica-movimiento` → `{"accion": "ninguna", "movimientos": 1}`.
- [ ] `tendedero_supervisor` con `supervisor` (`{}`) → `{"revisados": 2, …}`.

Si alguna responde con `AccessDeniedException` o `Task timed out`, revisar el rol (9.2) o el timeout (9.3).

## 10. Alerta de facturación

La rúbrica recomienda configurar una alerta de facturación. Se hace una sola vez por cuenta:

1. Abrir **Billing and Cost Management → Budgets → Create budget**.
2. Elegir **Use a template → Zero spend budget**. Avisa por correo apenas haya un cargo, aunque sea de centavos.
3. Escribir el correo del equipo y guardar.
4. Tomar una captura del presupuesto creado para las evidencias.

Con la frecuencia de reporte de 60 s, el consumo estimado queda dentro de la capa gratuita (`python tools/estimar_costo.py`). La alerta avisa si algo se sale de lo previsto, por ejemplo un ESP32 que reporta en bucle.

## Orden de todo lo pendiente

Después de aplicar todo, las pruebas paso a paso están en [PRUEBAS_AWS.md](PRUEBAS_AWS.md).

1. Paso 4: política del rol de la Lambda de Alexa (`Query` sobre vinculaciones e IoT restringido a `tendedero-*`).
2. Paso 4.1: recrear `tendedero_vinculaciones`. **Borra las vinculaciones actuales.**
3. Paso 5: subir el ZIP nuevo de la Lambda de Alexa.
4. [ALEXA.md](ALEXA.md): pegar el modelo nuevo y compilar.
5. Paso 9: crear la tabla `tendedero_historico`, los tres roles, las tres Lambdas (almacenamiento, lógica y supervisor), las tres reglas y la programación del supervisor.
6. Paso 6: limpiar los Shadows con [shadow-migracion-practica4.json](../../aws/shadow-migracion-practica4.json) (borra `cubierta`, `sensor_raw`, `luz_adc`, `desired.origen_led` y los campos de ensayo).
7. Paso 10: alerta de facturación, si la cuenta todavía no la tiene.
8. Volver a vincular los tendederos desde Alexa, con nombre.
9. Fuera de AWS: cargar el firmware nuevo en el ESP32 (R5 de noche, luz con apagado automático y espera mínima de 15 minutos).
