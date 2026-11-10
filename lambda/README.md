# Backend Lambda — desplegado y probado en AWS

La función `tendedero-inteligente-alexa` está desplegada en `us-east-2`. Las pruebas directas comprobaron carga del handler, vinculación persistente, consultas del Shadow, escritura de `desired.cubierta`, cambio de Thing, rechazo de uno inexistente y desvinculación. CloudWatch conserva las ejecuciones revisadas.

Fuente: [lambda_function.py](lambda_function.py). Dependencias declaradas: [requirements.txt](requirements.txt). Paquete entregado: [lambda_deployment_p3.zip](lambda_deployment_p3.zip).

Las pruebas directas del backend se distinguen de las pruebas de la Skill y del dispositivo físico. La documentación de esas etapas se conserva en [ALEXA.md](../docs/ALEXA.md), el [informe consolidado](../docs/INFORME.md) y los [videos de integración](../docs/evidencias/integracion/README.md). El [manual AWS](../docs/GUIA_AWS.md) y la [documentación original de evidencias AWS](../docs/EVIDENCIAS_AWS.md) mantienen el procedimiento y su respaldo.

## Parámetros de despliegue

- Función: `tendedero-inteligente-alexa`; región `us-east-2` para IoT Core, Lambda y DynamoDB.
- Runtime documentado: Python 3.11, arquitectura `x86_64`.
- Handler: `lambda_function.lambda_handler`.
- `IOT_ENDPOINT`: hostname ATS sin protocolo ni puerto.
- `DDB_BINDINGS_TABLE`: `tendedero_vinculaciones`.
- `AWS_REGION`: proporcionada automáticamente por Lambda.
- Rol con `iot:DescribeThing`, `iot:GetThingShadow`, `iot:UpdateThingShadow` y `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:DeleteItem`, además de logging.
- Trigger Alexa Skills Kit configurado y restringido al Skill ID.

Mapa de alias verificado, incluidas las variantes con dígitos observadas en el slot de Alexa:

```json
{
  "tendedero inteligente": "tendedero-inteligente",
  "prueba dos": "tendedero-prueba2",
  "prueba 2": "tendedero-prueba2",
  "tendedero prueba dos": "tendedero-prueba2",
  "tendedero prueba 2": "tendedero-prueba2"
}
```

## Configuración realizada

1. Things físico y de prueba creados; certificado activo del físico asociado al Thing y a la política IoT.
2. Tabla con `userId` String como clave; Lambda añade `thingName` y `fechaVinculacion` a cada ítem.
3. ZIP, handler, variables y rol configurados y ejercitados mediante eventos directos.
4. Skill ID recibido y trigger restringido a ese identificador.
5. Skill conectada al backend. La vinculación y consulta del Thing simulado verificaron el mapa de alias; las pruebas posteriores del simulador y montaje de banco están documentadas por separado en el informe y las evidencias de integración.

`userId` se obtiene de la solicitud y se resuelve en DynamoDB en cada consulta/control: no hay Thing fijo. `VincularThingIntent` y `CambiarThingIntent` comparten implementación, que valida existencia antes de crear o reemplazar el vínculo.

## Mantener el paquete

El ZIP debe contener el handler y ASK SDK en su raíz, o usar una capa adecuada. El fuente y su copia dentro del ZIP deben coincidir. Si cambia el código, reconstruir y desplegar el paquete; no sustituir solo el fuente del repositorio.

Las versiones de `requirements.txt` no están fijadas. Reconstruir con paquetes diferentes requiere verificar compatibilidad con el runtime y repetir las pruebas. No incluir `.venv`, claves, certificados privados, credenciales ni identificadores completos de usuarios en las evidencias.
