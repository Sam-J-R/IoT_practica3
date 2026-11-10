# Evidencias AWS

Paneles sanitizados y CSV originales del conjunto de configuración y pruebas directas incorporado en la revisión Git `a8a86c3`, consolidado el 8/11/2026. Se incluyen localmente para que el informe no dependa de archivos en otra rama. No son capturas nuevas ni se atribuyen como ensayos distintos.

| ID | Archivo | Alcance |
|---|---|---|
| AWS-01 | [Things y certificado](01-iot-core-things-certificado.png) | Things, certificado activo y asociaciones con política/Thing. |
| AWS-02 | [DynamoDB](02-dynamodb-tabla-vinculaciones.png) | Tabla activa, clave String y dos vinculaciones con usuarios truncados. |
| AWS-03 | [Lambda e IAM](03-lambda-iam-configuracion.png) | Función, variables, runtime, handler, arquitectura y rol. |
| AWS-04 | [CloudWatch](04-cloudwatch-ejecuciones-lambda.png) y [CSV](04-cloudwatch-eventos.csv) | Fragmento de invocaciones; cuatro valores Duration. No mide movimiento físico. |
| AWS-05 | [Shadow y respuesta Lambda](05-backend-shadow-respuesta-lambda.png) | Shadow simulado de `tendedero-prueba2` y consulta directa satisfactoria. |

Se conserva la [documentación original de evidencias AWS](../../EVIDENCIAS_AWS.md), junto con la [guía AWS](../../GUIA_AWS.md), el [esquema DynamoDB](../../../aws/dynamodb-schema.md) y el [registro de pruebas](../../PRUEBAS.md). Este índice facilita localizar los archivos y no sustituye esos documentos ni reasigna su autoría.

El [informe consolidado](../../INFORME.md) reutiliza estas evidencias. Las cinco imágenes y el CSV mantienen exactamente el contenido de `origin/maria-aws`. No se incluyen materiales privados TLS ni solicitudes completas de Alexa.
