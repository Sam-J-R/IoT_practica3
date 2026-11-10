# Backend Lambda

Fuente: [lambda_function.py](lambda_function.py). Dependencias declaradas: [requirements.txt](requirements.txt). Paquete entregado: [lambda_deployment_p3.zip](lambda_deployment_p3.zip).

La configuración, clases, permisos, decisiones y pruebas se explican en [INFORME.md](../docs/INFORME.md). El [manual AWS](../docs/GUIA_AWS.md) conserva el procedimiento de aprovisionamiento.

## Parámetros de despliegue

- Función: `tendedero-inteligente-alexa`, región `us-east-2`.
- Runtime documentado: Python 3.11, arquitectura `x86_64`.
- Handler: `lambda_function.lambda_handler`.
- Variables: `IOT_ENDPOINT` sin protocolo, `DDB_BINDINGS_TABLE` y `THING_ALIASES_JSON`. `AWS_REGION` la proporciona Lambda.
- Rol de ejecución con operaciones IoT/DynamoDB y logging; trigger Alexa Skills Kit restringido al Skill ID.

## Mantener el paquete

El ZIP debe contener el handler y sus dependencias en la raíz o usar una capa adecuada. La revisión verificó igualdad byte por byte entre el fuente y su copia del ZIP. Si cambia el código, reconstruir el paquete antes de desplegar; no sustituir únicamente el fuente del repositorio.

Las versiones de `requirements.txt` no están fijadas. Reconstruir con paquetes diferentes requiere verificar compatibilidad con el runtime y repetir las pruebas. No incluir `.venv`, claves ni credenciales en el ZIP.
