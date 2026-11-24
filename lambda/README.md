# Backend Lambda — práctica 4

Fuente: [lambda_function.py](lambda_function.py). Dependencias declaradas: [requirements.txt](requirements.txt). Paquete para desplegar: [lambda_deployment_p3.zip](lambda_deployment_p3.zip).

El código corresponde a la práctica 4. El contrato está en [docs/practica4/CONTRATO.md](../docs/practica4/CONTRATO.md) y los pasos de despliegue en [docs/practica4/GUIA_AWS.md](../docs/practica4/GUIA_AWS.md). La versión desplegada y probada en la práctica 3 se conserva en la etiqueta de git `practica3-entrega`.

Esta versión se verificó con las pruebas locales de `tests/`, que usan AWS simulado. Todavía no se desplegó ni se probó en la cuenta de AWS.

## Qué hace

- **Vincular y cambiar.** Recibe el código de 6 dígitos de la etiqueta, busca el Thing en `tendedero_dispositivos` por el índice `codigoVinculacion-index`, valida que exista con `DescribeThing` y guarda `userId → thingName` en `tendedero_vinculaciones`.
- **Consultas y órdenes.** Resuelve el Thing por `userId` en cada solicitud y lee o escribe su Shadow: `agua_detectada`, `posicion` (`expuesto` / `resguardado`) y `calibracion_solicitada`.
- **Sin nombres de Things.** No hay Things fijos en el código ni en variables de entorno. La variable `THING_ALIASES_JSON` de la práctica 3 ya no existe.

## Parámetros de despliegue

- Función: `tendedero-inteligente-alexa`; región `us-east-2`.
- Runtime: Python 3.11, arquitectura `x86_64`.
- Handler: `lambda_function.lambda_handler`.
- Variables de entorno:

| Variable | Valor |
|---|---|
| `IOT_ENDPOINT` | Hostname ATS sin protocolo ni puerto. |
| `DDB_BINDINGS_TABLE` | `tendedero_vinculaciones` |
| `DDB_DEVICES_TABLE` | `tendedero_dispositivos` |
| `AWS_REGION` | La proporciona Lambda. |

- Rol: `iot:DescribeThing`, `iot:GetThingShadow`, `iot:UpdateThingShadow`; `dynamodb:Query`, `PutItem` y `DeleteItem` sobre la tabla de vinculaciones; `dynamodb:Query` sobre el índice de la tabla de dispositivos; y logging. Plantilla: [lambda-iam-policy.template.json](../aws/lambda-iam-policy.template.json).
- Trigger Alexa Skills Kit restringido al Skill ID.

## Mantener el paquete

El ZIP contiene el handler y el ASK SDK en su raíz. El fuente y su copia dentro del ZIP deben coincidir: la prueba `test_deployment_zip_matches_source` lo comprueba. Si cambia el código, hay que reemplazar `lambda_function.py` dentro del ZIP y volver a desplegarlo; no basta con cambiar el fuente del repositorio.

Las versiones de `requirements.txt` están fijadas a las que contiene el ZIP (`ask-sdk-core` 1.19.0 y `ask-sdk-model` 1.82.0). `boto3` no se empaqueta porque lo provee el runtime de Lambda. Reconstruir con otras versiones requiere verificar la compatibilidad con el runtime y repetir las pruebas. No incluir `.venv`, claves, certificados privados, credenciales ni identificadores completos de usuarios.
