# Lambda Alexa — backend desplegado y probado en AWS

La función `tendedero-inteligente-alexa` está desplegada en `us-east-2` y fue
verificada mediante eventos directos de Lambda. Las pruebas comprobaron carga
del handler, vinculación persistente, consulta del Shadow, escritura de
`desired.cubierta`, cambio de Thing, rechazo de un Thing inexistente y
desvinculación. CloudWatch no mostró errores en las ejecuciones revisadas.

Esto valida el backend AWS, pero no sustituye la prueba extremo a extremo con
la Skill de Alexa ni la conexión física del ESP32.

- Región acordada: `us-east-2`; IoT Core, Lambda y DynamoDB deben permanecer en esa región.
- Requiere `IOT_ENDPOINT` sin `https://` y `DDB_BINDINGS_TABLE=tendedero_vinculaciones`. Lambda proporciona `AWS_REGION` automáticamente.
- Alias verificados: `THING_ALIASES_JSON={"tendedero inteligente":"tendedero-inteligente","prueba dos":"tendedero-prueba2","prueba 2":"tendedero-prueba2","tendedero prueba dos":"tendedero-prueba2","tendedero prueba 2":"tendedero-prueba2"}`. Las variantes con dígito se añadieron porque Alexa normalizó «dos» como `2` durante la prueba real.
- Handler: `lambda_function.lambda_handler`, Python 3.11 o runtime compatible.
- IAM: `iot:DescribeThing` para validar nombre, `iot:GetThingShadow`/`iot:UpdateThingShadow` y `dynamodb:GetItem`/`PutItem`/`DeleteItem` sobre la tabla.
- Trigger Alexa Skills Kit configurado y restringido al Skill ID real de la compañera Alexa.
- Dependencias ASK SDK deben instalarse en la raíz del ZIP de despliegue junto a `lambda_function.py` (o como layer), como en el ejemplo del docente.
- Se incluye `lambda_deployment_p3.zip` generado a partir del paquete del docente con este `lambda_function.py` en la raíz. Si cambia el fuente, se debe reconstruir el ZIP antes de subirlo. Elegir un runtime compatible (la plantilla del docente contiene archivos preparados con Python 3.11).
- `userId` viene de la solicitud Alexa; cada intent de consulta/control lo resuelve en DynamoDB antes de hablar con Shadow. No hay Thing fijo.
- `VincularThingIntent` y `CambiarThingIntent` comparten implementación; el segundo reemplaza vínculo.
- Permisos IAM y alias fueron probados mediante invocaciones directas en AWS. Todavía falta validar el reconocimiento de voz/texto desde la Skill y la cadena completa hasta el ESP32.


## Configuración realizada y cierre de la integración

1. **Realizado — AWS IoT Core.** Están creados el Thing físico y el Thing de prueba. El certificado activo del Thing físico está asociado al Thing y a su política IoT.
2. **Realizado — DynamoDB.** La tabla `tendedero_vinculaciones` usa `userId` String como clave de partición y Lambda crea `thingName` y `fechaVinculacion` en cada ítem.
3. **Realizado — Lambda.** El ZIP, handler, rol, variables de entorno y pruebas directas están configurados. Cuando se modifique `lambda_function.py`, se debe reconstruir el ZIP y volver a desplegarlo.
4. **Realizado — trigger Alexa.** La responsable Alexa entregó el Skill ID y Lambda tiene un trigger **Alexa Skills Kit** restringido a ese identificador.
5. **Realizado parcialmente — Skill.** La Skill invocó la Lambda desde el simulador, vinculó `prueba dos` después de ampliar los alias y consultó correctamente la cubierta del Shadow simulado. La demostración física y cualquier prueba de voz adicional se documentan por separado.

Las capturas y exportaciones deben ocultar claves, certificados privados e identificadores completos de usuarios. La lista detallada está en `docs/EVIDENCIAS_AWS.md`.
