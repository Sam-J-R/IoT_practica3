# Evidencias AWS para el informe

Este documento cierra el conjunto de evidencias correspondiente a la
configuración y las pruebas directas realizadas en AWS. Se usan cinco figuras
consolidadas, configuraciones JSON sanitizadas, una tabla de resultados y el
log exportado de CloudWatch. No se requieren más capturas AWS.

## Reglas de seguridad

No incluir en el repositorio:

- clave privada, certificado del dispositivo ni contenido PEM de la CA;
- contraseñas, SSID, access keys o `secrets.h`;
- `userId` completo de Alexa;
- ID completo de cuenta o identificador completo del certificado en capturas
  públicas.

Las capturas originales sin redactar se conservan solo localmente en
`docs/evidencias/aws/originales_privados/`, carpeta ignorada por Git.

## Evidencia AWS final

| Nº | Evidencia | Archivo | Qué demuestra |
|---:|---|---|---|
| 1 | IoT Core y certificado | `docs/evidencias/aws/01-iot-core-things-certificado.png` | Things del proyecto en `us-east-2`, certificado Active y asociaciones con la política y el Thing físico. ID de cuenta y certificado redactados. |
| 2 | DynamoDB | `docs/evidencias/aws/02-dynamodb-tabla-vinculaciones.png` | Tabla Active, clave `userId` String y vinculaciones persistidas por Lambda. Los usuarios aparecen truncados. |
| 3 | Lambda e IAM | `docs/evidencias/aws/03-lambda-iam-configuracion.png` | Función desplegada, variables configuradas, runtime, handler, arquitectura y políticas asociadas al rol. |
| 4 | CloudWatch | `docs/evidencias/aws/04-cloudwatch-ejecuciones-lambda.png` y `04-cloudwatch-eventos.csv` | Invocaciones con eventos `START`, `END` y `REPORT`, sin excepciones visibles en el periodo revisado. |
| 5 | Shadow y respuesta de Lambda | `docs/evidencias/aws/05-backend-shadow-respuesta-lambda.png` | Shadow clásico simulado de `tendedero-prueba2` y ejecución `Succeeded` de `PruebaConsultarCubierta`, con respuesta coherente con `reported.cubierta`. |
| 6 | Resultados del backend | Tabla AWS-BE en `docs/PRUEBAS.md` | Vinculación, consultas, comandos, convergencia, Thing inexistente, aislamiento, cambio y desvinculación. |

## Configuraciones entregadas como JSON

Estas configuraciones sustituyen capturas adicionales de los editores:

- `aws/iot-certificate-policy.template.json`;
- `aws/lambda-iam-policy.template.json`;
- `aws/dynamodb-table.template.json`;
- `alexa/interaction-model-es-MX.json`.

`ACCOUNT_ID` reemplaza el ID real de la cuenta. Las diferencias de mínimo
privilegio y el uso de `Resource: "*"` para las tres acciones IoT de Lambda se
justifican en `docs/GUIA_AWS.md` y `docs/INFORME.md`.

## Alcance cerrado

No se agregarán al conjunto de evidencias AWS capturas del ESP32, estabilidad,
reconexión, movimiento físico o simulador de Alexa. Esas actividades no se
presentan como realizadas por la responsable AWS: pertenecen a la integración
del equipo, a la responsable correspondiente o a la demostración presencial.

No se grabará video. El movimiento del servo se verificará durante la demo. 

## Registro en el informe

Cada figura debe acompañarse por una breve explicación de:

- fecha y recurso observado;
- acción realizada;
- resultado que respalda;
- si se trató de un estado simulado o de una ejecución directa.

Las cinco figuras ya están insertadas en `docs/INFORME.md`. La tabla funcional
detallada se encuentra en `docs/PRUEBAS.md`.
