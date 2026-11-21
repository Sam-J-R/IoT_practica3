# Guía AWS — práctica 4

Pasos para actualizar la cuenta de AWS que ya funciona con la práctica 3. La [guía de la práctica 3](../GUIA_AWS.md) se conserva sin cambios y sigue siendo la referencia para crear los recursos desde cero. Todo se hace en **Ohio `us-east-2`**.

| Recurso | Cambio |
|---|---|
| Tabla `tendedero_dispositivos` | **Nueva.** |
| Política IoT del dispositivo | Se reemplaza por una genérica. |
| Rol de la Lambda | Se agrega un permiso. |
| Lambda `tendedero-inteligente-alexa` | ZIP nuevo y cambio de variables de entorno. |
| Shadows de los dos Things | Se borran los atributos antiguos. |
| Tabla `tendedero_vinculaciones` | Sin cambios. |

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

## 4. Agregar el permiso al rol de la Lambda

1. Abrir **IAM → Roles → `tendedero-inteligente-lambda-role`**.
2. Editar la política en línea y reemplazarla por [lambda-iam-policy.template.json](../../aws/lambda-iam-policy.template.json), sustituyendo `ACCOUNT_ID`.

El único cambio es una declaración nueva: `dynamodb:Query` sobre el índice `codigoVinculacion-index` de `tendedero_dispositivos`. La Lambda no necesita más permisos sobre esa tabla, porque solo la lee por código.

El comodín `Resource: "*"` de las tres acciones de IoT se mantiene, por el mismo motivo documentado en la práctica 3. El mínimo para producción sigue siendo `arn:aws:iot:us-east-2:ACCOUNT_ID:thing/tendedero-*`.

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

Los Shadows conservan los atributos de la práctica 3 (`cubierta` y `sensor_raw`). Hay que borrarlos en los dos Things, o seguirán apareciendo en el documento.

1. Abrir **AWS IoT Core → Things → `tendedero-inteligente` → Device Shadows → Classic Shadow → Edit**.
2. Pegar el contenido de [shadow-migracion-practica4.json](../../aws/shadow-migracion-practica4.json) y guardar. Escribir `null` en un atributo lo elimina.
3. Repetir en `tendedero-prueba2`.
4. En `tendedero-prueba2`, que no tiene ESP32, cargar además el estado simulado de [shadow-prueba2.example.json](../../aws/shadow-prueba2.example.json).

El Shadow de `tendedero-inteligente` se completa solo cuando el ESP32 se conecta con el firmware nuevo.

## 7. Verificaciones

- [ ] La tabla `tendedero_dispositivos` y su índice están en **Active**, con dos ítems.
- [ ] La versión activa de la política IoT contiene `${iot:Connection.Thing.ThingName}` y no contiene `ACCOUNT_ID`.
- [ ] El rol de la Lambda tiene la declaración `FindDeviceByBindingCode`.
- [ ] La Lambda tiene `DDB_DEVICES_TABLE` y ya no tiene `THING_ALIASES_JSON`.
- [ ] Los Shadows no muestran `cubierta` ni `sensor_raw`.
- [ ] Con el firmware nuevo cargado, el ESP32 se conecta y su Shadow muestra `posicion`, `agua_detectada`, `lectura_adc` y `calibracion`.
- [ ] Prueba directa en la Lambda (**Test**) o desde el simulador de Alexa: vincular con `715204` responde «He vinculado tu tendedero».

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
