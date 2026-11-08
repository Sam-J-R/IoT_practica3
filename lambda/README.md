# Lambda Alexa — backend provisional (no desplegado)

- Región acordada: `us-east-2`; IoT Core, Lambda y DynamoDB deben permanecer en esa región.
- Requiere `IOT_ENDPOINT` sin `https://` y `DDB_BINDINGS_TABLE=tendedero_vinculaciones`. Lambda proporciona `AWS_REGION` automáticamente.
- Alias acordados: `THING_ALIASES_JSON={"tendedero inteligente":"tendedero-inteligente","prueba dos":"tendedero-prueba2"}`.
- Handler: `lambda_function.lambda_handler`, Python 3.11 o runtime compatible.
- IAM: `iot:DescribeThing` para validar nombre, `iot:GetThingShadow`/`iot:UpdateThingShadow` y `dynamodb:GetItem`/`PutItem`/`DeleteItem` sobre la tabla.
- Añadir el trigger Alexa Skills Kit limitado al Skill ID real de la compañera Alexa.
- Dependencias ASK SDK deben instalarse en la raíz del ZIP de despliegue junto a `lambda_function.py` (o como layer), como en el ejemplo del docente.
- Se incluye `lambda_deployment_p3.zip` generado a partir del paquete del docente con este `lambda_function.py` en la raíz. Si cambia el fuente, se debe reconstruir el ZIP antes de subirlo. Elegir un runtime compatible (la plantilla del docente contiene archivos preparados con Python 3.11).
- `userId` viene de la solicitud Alexa; cada intent de consulta/control lo resuelve en DynamoDB antes de hablar con Shadow. No hay Thing fijo.
- `VincularThingIntent` y `CambiarThingIntent` comparten implementación; el segundo reemplaza vínculo.
- Todavía requiere prueba de integración real con Alexa/AWS, especialmente reconocimiento de alias y comportamientos IAM. No afirmar completado.


## Preparación de la integración

1. **AWS IoT Core → Manage → Things**. Registrar el Thing físico y otro Thing de prueba con el prefijo autorizado por IAM. Provisionar certificado activo para el ESP32 y asociarlo al Thing físico y a la política IoT de la plantilla. Sustituir cuenta, región y nombre en la política. Compartir endpoint ATS, CA, certificado y clave de dispositivo por canal privado.
2. **DynamoDB → Tables → Create table**. Usar la definición `aws/dynamodb-table.template.json` como plantilla revisable. El identificador de usuario es clave de partición de tipo String.
3. **Lambda → Functions → Code**. Preparar el ZIP, handler `lambda_function.lambda_handler`, runtime compatible con el paquete docente y rol de ejecución con logging más la plantilla IAM. En **Configuration → Environment variables**, fijar `IOT_ENDPOINT`, `DDB_BINDINGS_TABLE` y el mapa `THING_ALIASES_JSON`. Limitar el trigger **Alexa Skills Kit** al ID de la Skill.
4. **Alexa Developer Console → Build → Interaction Model → JSON Editor**. Usar el modelo es-MX del repositorio. En **Build → Endpoint** asociar el ARN de Lambda y construir el modelo. En **Test → Development**, verificar primero texto y después voz. Probar cómo aparece el slot realmente, incluidos dígitos y palabras, y mapear variantes observadas al mismo Thing mediante alias explícitos.
5. Registrar evidencia con dos usuarios y dos Things, en sesiones distintas. Probar vínculo, consultas, cambio de Thing válido e inexistente, desvinculación y aislamiento de órdenes. Un Thing simulado sirve para comprobar enrutamiento con AWS. El movimiento y la latencia física requieren el prototipo.

Son pasos para los responsables del equipo cuando se autorice la configuración. El repositorio contiene plantillas; las exportaciones de los recursos reales se adjuntan después de verificarlos. Evitar claves, certificados privados e identificadores completos de usuarios en evidencias.
