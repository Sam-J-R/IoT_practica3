# Guía AWS — IoT Core, Device Shadow, DynamoDB y Lambda

Esta es la guía operativa de la responsable AWS. Los nombres siguientes forman parte del contrato del equipo y deben escribirse exactamente igual.

| Recurso | Valor definitivo |
|---|---|
| Región | `us-east-2` (Ohio) |
| Thing físico | `tendedero-inteligente` |
| Thing de prueba | `tendedero-prueba2` |
| Shadow | Clásico, sin nombre |
| Tabla DynamoDB | `tendedero_vinculaciones` |
| Clave de partición | `userId` (String) |
| Función Lambda sugerida | `tendedero-inteligente-alexa` |
| Handler | `lambda_function.lambda_handler` |
| Runtime | Python 3.11 |

Mantener IoT Core, DynamoDB y Lambda en `us-east-2`. No copiar certificados, claves privadas, contraseñas, access keys ni valores completos de `userId` al repositorio.

## 1. Preparación y control de costos

1. Iniciar sesión en AWS y seleccionar **Ohio `us-east-2`** en la esquina superior de la consola.
2. Anotar el ID de cuenta de 12 dígitos. Se usará para sustituir `ACCOUNT_ID` en las dos políticas del repositorio; no es una contraseña, pero puede ocultarse parcialmente en capturas públicas.
3. Configurar una alerta de facturación si la cuenta lo permite.
4. Conservar una carpeta privada fuera del repositorio para los materiales del certificado del ESP32.

## 2. Crear la política IoT del dispositivo

1. Abrir **AWS IoT Core → Security → Policies → Create policy**.
2. Usar un nombre reconocible, por ejemplo `tendedero-inteligente-device-policy`.
3. Copiar `aws/iot-certificate-policy.template.json`.
4. Sustituir todas las apariciones de `ACCOUNT_ID` por el ID real de la cuenta.
5. Confirmar antes de guardar que la región sea `us-east-2` y que todos los recursos nombren `tendedero-inteligente`.

La política permite conectar con client ID `tendedero-inteligente`, publicar `get/update` y recibir `delta`, `accepted` y `rejected` del Shadow clásico. No usar un comodín global `*` si la plantilla funciona.

## 3. Crear el Thing físico y su certificado

1. Abrir **AWS IoT Core → Manage → All devices → Things → Create things**.
2. Crear un solo Thing llamado exactamente `tendedero-inteligente`.
3. Generar automáticamente un certificado nuevo y dejarlo **activo**.
4. Asociar al certificado la política `tendedero-inteligente-device-policy`.
5. Confirmar que el certificado también esté asociado al Thing. Son dos relaciones distintas: certificado→política y certificado→Thing.
6. Antes de abandonar la pantalla de descarga, guardar en la carpeta privada:
   - certificado del dispositivo;
   - clave privada;
   - Amazon Root CA 1;
   - nombre exacto del Thing.
7. No guardar estos archivos dentro del repositorio ni enviarlos a la responsable Alexa. La clave privada solo se entrega a Samuel por un canal privado.

No crear manualmente un estado `desired` para el Thing físico hasta que el servo y su recorrido estén calibrados. El Shadow clásico aparecerá cuando el dispositivo o una prueba autorizada realice la primera actualización.

## 4. Obtener el endpoint de datos ATS

En **AWS IoT Core → Settings**, copiar el endpoint de dispositivo. Debe tener una forma similar a:

```text
xxxxxxxxxxxxxx-ats.iot.us-east-2.amazonaws.com
```

Guardar solo el hostname, sin `https://`, sin `mqtts://` y sin `:8883`. Ese mismo valor se usará como `IOT_ENDPOINT` en Lambda y como `AWS_IOT_ENDPOINT` en el archivo local del ESP32.

## 5. Crear el Thing de prueba

1. Crear otro Thing, sin certificado de dispositivo, llamado `tendedero-prueba2`.
2. Usarlo para demostrar que dos usuarios pueden quedar vinculados a Things diferentes.
3. En su Shadow clásico, cargar un estado reportado simulado cuando se realice la prueba:

```json
{
  "state": {
    "reported": {
      "cubierta": "abierta",
      "agua_detectada": false,
      "sensor_raw": 0
    }
  }
}
```

Este Shadow simulado no demuestra funcionamiento del ESP32; sirve solamente para verificar enrutamiento, consultas y aislamiento multiusuario.

## 6. Crear DynamoDB

1. Abrir **DynamoDB → Tables → Create table** en `us-east-2`.
2. Nombre: `tendedero_vinculaciones`.
3. Partition key: `userId`, tipo **String**.
4. No crear sort key ni índices secundarios.
5. Elegir capacidad bajo demanda, `PAY_PER_REQUEST`.
6. Esperar hasta que el estado de la tabla sea **Active**.

`thingName` y `fechaVinculacion` no se declaran al crear la tabla; Lambda los añade a cada ítem. No escribir manualmente usuarios reales salvo para una prueba controlada.

## 7. Crear el rol de Lambda

1. Abrir **IAM → Roles → Create role**.
2. Tipo de entidad: servicio AWS; caso de uso: **Lambda**.
3. Nombre sugerido: `tendedero-inteligente-lambda-role`.
4. Adjuntar la política administrada `AWSLambdaBasicExecutionRole` para CloudWatch Logs.
5. Crear una política en línea con el contenido de `aws/lambda-iam-policy.template.json`.
6. Sustituir `ACCOUNT_ID` por el ID real y confirmar `us-east-2`.

La política desplegada permite únicamente `DescribeThing`, `GetThingShadow` y `UpdateThingShadow` sobre recursos IoT con `Resource: "*"`, además de `GetItem`, `PutItem` y `DeleteItem` sobre la tabla exacta. Se usó el comodín porque el analizador IAM de la cuenta mostró acceso IoT nulo con ARN restringidos. En producción, el permiso mínimo sustituiría `*` por los ARN exactos de `tendedero-inteligente` y `tendedero-prueba2`.

## 8. Crear y configurar Lambda

1. Abrir **Lambda → Create function → Author from scratch**.
2. Nombre: `tendedero-inteligente-alexa`.
3. Runtime: Python 3.11; arquitectura `x86_64`.
4. Seleccionar el rol existente `tendedero-inteligente-lambda-role`.
5. Subir `lambda/lambda_deployment_p3.zip`.
6. Configurar el handler `lambda_function.lambda_handler`.
7. Usar inicialmente 128 MB y un timeout de 10 segundos.
8. Crear estas variables de entorno:

| Variable | Valor |
|---|---|
| `IOT_ENDPOINT` | Endpoint ATS sin protocolo ni puerto |
| `DDB_BINDINGS_TABLE` | `tendedero_vinculaciones` |
| `THING_ALIASES_JSON` | `{"tendedero inteligente":"tendedero-inteligente","prueba dos":"tendedero-prueba2","prueba 2":"tendedero-prueba2","tendedero prueba dos":"tendedero-prueba2","tendedero prueba 2":"tendedero-prueba2"}` |

No crear manualmente `AWS_REGION`: Lambda la proporciona y debe indicar `us-east-2`.

Revisar CloudWatch Logs después de cada prueba. Un `AccessDeniedException` normalmente indica que el ARN, la región, el nombre del Thing o el nombre de tabla no coincide con la política.

## 9. Verificaciones antes de Alexa

- Los dos Things aparecen en `us-east-2`.
- El certificado del Thing físico está activo y asociado tanto al Thing como a su política.
- La política IoT contiene el ID de cuenta real y no conserva `ACCOUNT_ID`.
- La tabla está activa y vacía o contiene solo datos de prueba identificados.
- El rol de Lambda tiene logging y la política limitada a las operaciones del proyecto; el comodín de recursos IoT está justificado y documentado.
- Lambda puede cargar el handler sin errores de importación.
- Las tres variables de entorno están presentes.
- CloudWatch recibe los logs de la función.

## 10. Entrega a la responsable Alexa

Compartir con la responsable Alexa:

- región Lambda: `us-east-2`;
- ARN de `tendedero-inteligente-alexa`;
- locale: `es-MX`;
- nombre de invocación: `tendedero inteligente`;
- modelo `alexa/interaction-model-es-MX.json`;
- alias hablados: `tendedero inteligente`, `prueba dos`, `prueba 2`, `tendedero prueba dos` y `tendedero prueba 2`;
- lista de intents y frases que deben probarse.

No compartir con ella la clave privada, certificado del ESP32, Wi-Fi ni archivos `secrets.h`.

La responsable Alexa devolvió el **Skill ID** y la responsable AWS agregó a Lambda el trigger **Alexa Skills Kit** con verificación de ese identificador. La Skill usa el ARN de Lambda como endpoint predeterminado; una prueba desde el simulador confirmó la vinculación y la consulta de cubierta sobre `tendedero-prueba2`.

## 11. Evidencias que debe conservar la responsable AWS

Guardar capturas o exportaciones, ocultando datos sensibles, de:

1. Región `us-east-2` y lista de Things.
2. Certificado activo y sus asociaciones, sin mostrar la clave privada.
3. Política IoT final.
4. Endpoint ATS parcialmente oculto si la evidencia será pública.
5. Tabla, clave `userId`, modo `PAY_PER_REQUEST` e ítems creados por Lambda.
6. Rol y política IAM de Lambda.
7. Configuración de Lambda, variables y trigger con Skill ID.
8. Shadow simulado de `tendedero-prueba2`; el Shadow físico corresponde a la integración con el ESP32 y a la demostración.
9. CloudWatch Logs de vincular, consultar, cambiar y desvincular.
10. Prueba de dos usuarios sin cruce de Things.

Registrar los resultados en `docs/PRUEBAS.md` y las configuraciones finales en `docs/INFORME.md`. Cada captura debe tener fecha, escenario y resultado, no solo mostrar que el recurso existe.

La lista detallada, los nombres recomendados y las reglas de redacción están en [`EVIDENCIAS_AWS.md`](EVIDENCIAS_AWS.md).
