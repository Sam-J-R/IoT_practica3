# Contrato operativo de integración

Referencia breve para mantener compatibles firmware, Lambda y Skill. La explicación completa, diagramas y resultados se encuentran en [INFORME.md](INFORME.md).

## Identificación y arquitectura

- Región AWS definitiva: `us-east-2` (Ohio). IoT Core, Lambda y DynamoDB deben crearse en esta misma región.
- Thing físico: `tendedero-inteligente`.
- Thing de prueba para demostrar la vinculación multiusuario: `tendedero-prueba2`.
- Tabla DynamoDB: `tendedero_vinculaciones`.
- Shadow: clásico (sin nombre). El ESP32 conoce SU nombre de Thing, la Skill no: Lambda lo resuelve desde DynamoDB para CADA `userId`.
- El actuador **no** depende automáticamente del sensor. El usuario pregunta por el agua y ordena el movimiento por Alexa.

## Documento Shadow

```json
{
  "state": {
    "desired": { "cubierta": "cerrada" },
    "reported": {
      "cubierta": "abierta",
      "agua_detectada": false,
      "sensor_raw": 0
    }
  }
}
```

| Atributo | Tipo | Valores | Quién escribe | Uso |
|---|---|---|---|---|
| `desired.cubierta` | string | `abierta`, `cerrada` | Lambda | Solicitud remota |
| `reported.cubierta` | string | `abierta`, `cerrada` | ESP32 | Posición estimada tras comando |
| `reported.agua_detectada` | bool | `true`, `false` | ESP32 | Consulta Alexa |
| `reported.sensor_raw` | integer | 0..4095 aproximadamente | ESP32 | Evidencia y calibración analógica |

El umbral `agua_detectada` debe definirse a partir de pruebas, no inventarse. El valor analógico es crudo, no porcentaje físico de lluvia.

## MQTT Shadow clásico (THING_NAME es parámetro)

| Dirección | Tópico |
|---|---|
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/update/delta` |
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/get/accepted` |
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/get/rejected` |
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/update/accepted` |
| Dispositivo subscribe | `$aws/things/THING_NAME/shadow/update/rejected` |
| Dispositivo publish reportado | `$aws/things/THING_NAME/shadow/update` |
| Dispositivo publish recuperación | `$aws/things/THING_NAME/shadow/get` |

Después de conectar/reconectar: suscribir, publicar `/get`, leer desired vigente, aplicar movimiento pendiente y reportar cambio. El firmware utiliza mensajes JSON completos, versión y `clientToken`. Reporta por cambio de clasificación/posición y como respaldo nominal 5 s desde la aceptación previa; el informe distingue configuración y frecuencia efectiva.

## Vinculación RF7–RF9

Tabla DynamoDB `tendedero_vinculaciones`:

| Campo | Tipo | Uso |
|---|---|---|
| `userId` | String, partition key | `context.System.user.userId` |
| `thingName` | String | Nombre de AWS Thing validado previamente |
| `fechaVinculacion` | ISO-8601 UTC | Auditoría mínima |

El backend valida `DescribeThing` antes de `PutItem`, busca `GetItem` en cada intent de consulta/control, y permite cambiar (sobrescribir binding) o eliminar (`DeleteItem`). No asignar un Thing por defecto a usuarios sin vincular.

## Intents mínimos

| Intent | Slot | Comportamiento |
|---|---|---|
| `VincularThingIntent` | `thing_name` | Validar existencia y guardar usuario→Thing |
| `CambiarThingIntent` | `thing_name` | Reemplazar vinculación existente |
| `DesvincularThingIntent` | — | Borrar vinculación |
| `ConsultarAguaIntent` | — | Responder con `reported.agua_detectada`; `sensor_raw` queda solo para calibración, evidencia y diagnóstico |
| `AbrirCubiertaIntent` | — | Escribir `desired.cubierta = abierta` |
| `CerrarCubiertaIntent` | — | Escribir `desired.cubierta = cerrada` |
| `ConsultarCubiertaIntent` | — | Leer `reported.cubierta` |

El identificador se resuelve mediante alias configurables sin fijar un único Thing. La variante `prueba 2`, recibida en el slot, y `prueba dos` se asignan a `tendedero-prueba2`. Los ensayos documentados utilizaron texto por la limitación de micrófono del entorno.

## Seguridad y coherencia

- `userId` identifica cuenta con Skill habilitada, no persona biométrica. Puede cambiar al deshabilitar/re-habilitar Skill.
- Lambda debe usar permisos IAM, no access keys. Certificado MQTT en archivo ignorado por Git.
- Reportar `desired` no prueba movimiento físico. Alexa debe decir «He solicitado...» hasta que `reported` coincida; el servo sin realimentación independiente solo permite inferir posición.

