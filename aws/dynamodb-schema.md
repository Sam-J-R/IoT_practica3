# DynamoDB: vinculaciones Alexa ↔ Thing

Crear tabla `tendedero_vinculaciones` con [dynamodb-table.template.json](dynamodb-table.template.json):

- Región: `us-east-2`.
- Partition key: `userId` (String).
- Sort key: `thingName` (String). Desde la práctica 4, un usuario puede tener varios tendederos. En la práctica 3 no había sort key y cada usuario tenía uno solo.
- Atributos de cada ítem: `nombre` (String, el que dio el usuario), `fechaVinculacion` y `fechaSeleccion` (String ISO 8601).
- El tendedero activo de un usuario es el de `fechaSeleccion` más reciente.
- Modo de capacidad: bajo demanda (`PAY_PER_REQUEST`).

Ejemplo **ficticio**:

```json
{
  "userId": "amzn1.ask.account.EJEMPLO",
  "thingName": "tendedero-inteligente",
  "nombre": "patio",
  "fechaVinculacion": "2026-11-07T12:00:00Z",
  "fechaSeleccion": "2026-11-21T10:05:00Z"
}
```

- `Query` por `userId` en cada solicitud (todos los tendederos del usuario).
- `PutItem` para vincular o renombrar.
- `UpdateItem` de `fechaSeleccion` para elegir el tendedero activo.
- `DeleteItem` (`userId` + `thingName`) para desvincular uno.
- Lambda debe validar existencia del Thing en IoT Core (`DescribeThing`) ANTES de `PutItem`.
- No guardar claves privadas de certificados ni credenciales AWS en la tabla.
- La vinculación no es una tabla de historial de eventos. Esta última sería extra, no sustituye el requisito.
- Diseño y patrones de acceso completos: [docs/practica4/CONTRATO.md](../docs/practica4/CONTRATO.md#varios-tendederos-por-usuario).

## Tabla de dispositivos (práctica 4)

Crear tabla `tendedero_dispositivos` con [dynamodb-dispositivos.template.json](dynamodb-dispositivos.template.json):

- Partition key: `thingName` (String). Sin sort key.
- Índice secundario global `codigoVinculacion-index`, con partition key `codigoVinculacion` (String) y proyección de solo claves.
- Atributos de cada ítem: `codigoVinculacion` (String, 6 dígitos, sin empezar en 0, único) y `fechaAlta` (String ISO 8601).
- Modo de capacidad: bajo demanda (`PAY_PER_REQUEST`).

Ítems de ejemplo: [dynamodb-dispositivos.items.example.json](dynamodb-dispositivos.items.example.json).

- Las filas se crean a mano al dar de alta cada tendedero; la Lambda solo lee esta tabla.
- Lambda hace `Query` al índice por código al vincular o cambiar. En las demás solicitudes no consulta esta tabla.
- El procedimiento completo está en [docs/practica4/GUIA_AWS.md](../docs/practica4/GUIA_AWS.md).

