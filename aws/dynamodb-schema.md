# DynamoDB: vinculaciones Alexa ↔ Thing

Crear tabla `tendedero_vinculaciones`:

- Partition key: `userId` (String).
- Sin sort key para la asociación 1 usuario → 1 Thing.
- Atributos de cada ítem: `thingName` (String), `fechaVinculacion` (String ISO 8601).

Ejemplo **ficticio**:

```json
{
  "userId": "amzn1.ask.account.EJEMPLO",
  "thingName": "tendedero-grupo6",
  "fechaVinculacion": "2026-11-07T12:00:00Z"
}
```

- `GetItem` por cada solicitud; `PutItem` para vincular/cambiar; `DeleteItem` para desvincular.
- Lambda debe validar existencia del Thing en IoT Core (`DescribeThing`) ANTES de `PutItem`.
- No guardar claves privadas de certificados ni credenciales AWS en la tabla.
- La vinculación no es una tabla de historial de eventos. Esta última sería extra, no sustituye el requisito.

