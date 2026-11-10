# Evidencias de configuración y pruebas de Alexa

Registro consolidado: **9 de noviembre de 2026**. Interfaz: Alexa Developer Console, simulador en **Development**, idioma **Spanish (MX)**.

Las 17 imágenes se conservan con los nombres originales. Dos capturas corresponden a la lista de intents. Las fechas visibles en la consola pueden corresponder a distintas sesiones de configuración y ensayo.

## Configuración

| Archivo | Contenido observado |
|---|---|
| [01-invocacion.png](01-invocacion.png) | Nombre de invocación `tendedero inteligente` e idioma Spanish (MX). |
| [02-intentsp1.png](02-intentsp1.png) | Primera parte de la lista de intents funcionales. |
| [02-intentsp2.png](02-intentsp2.png) | Segunda parte de la lista, con consulta de cubierta e intents integrados. |
| [03-slot-vincular.png](03-slot-vincular.png) | Frases de vinculación y slot `thing_name` de tipo `AMAZON.SearchQuery`. |
| [04-slot-cambiar.png](04-slot-cambiar.png) | Frases de cambio de Thing y su slot `thing_name`. |
| [05-modelo-construido.png](05-modelo-construido.png) | Notificación `Build Completed` y construcción satisfactoria del modelo. |
| [06-endpoint.png](06-endpoint.png) | Endpoint de tipo AWS Lambda ARN; los campos de identificadores aparecen parcialmente ocultos. |
| [07-json-editor.png](07-json-editor.png) | Modelo en JSON Editor, locale Spanish (MX) y fecha de construcción satisfactoria. |

El archivo de configuración del proyecto está en [interaction-model-es-MX.json](../../../alexa/interaction-model-es-MX.json). La captura del editor complementa ese archivo, no lo sustituye.

## Pruebas funcionales

| Archivo | Operación y resultado observado | Requisito relacionado |
|---|---|---|
| [08-alexa-inicio.png](08-alexa-inicio.png) | «abre tendedero inteligente» devuelve el saludo del backend. | Entrada a la Skill |
| [09-alexa-sin-vinculo.png](09-alexa-sin-vinculo.png) | Después de desvincular, consultar el agua devuelve «No tienes un objeto vinculado. Vincúlalo primero». | RF8 |
| [10-alexa-vinculacion.png](10-alexa-vinculacion.png) | «vincula mi objeto con prueba dos» confirma `tendedero-prueba2`. | RF7 |
| [11-alexa-persistencia.png](11-alexa-persistencia.png) | «para», nueva apertura y consulta del sensor sin volver a vincular. | RF7 |
| [12-alexa-thing-inexistente.png](12-alexa-thing-inexistente.png) | «cambia mi objeto a objeto inexistente nueve» devuelve rechazo del identificador. | RF9, caso negativo |
| [13-alexa-desvinculacion.png](13-alexa-desvinculacion.png) | «desvincula mi objeto» devuelve confirmación de eliminación. | RF9 |
| [14-alexa-sensor-seco-y-con-agua.png](14-alexa-sensor-seco-y-con-agua.png) | Respuestas «El sensor no detecta agua» y «El sensor detecta agua»; también se observa una consulta que informa cubierta cerrada. | RF4 y RF6 |
| [15-alexa-abrir-y-cerrar-cubierta.png](15-alexa-abrir-y-cerrar-cubierta.png) | Solicitudes de apertura y cierre aceptadas con «He solicitado…». | RF5 |
| [16-alexa-cambio-valido.png](16-alexa-cambio-valido.png) | Vinculación inicial con `tendedero-prueba2` y cambio satisfactorio a `tendedero-inteligente`. | RF9, caso positivo |

## Alcance de las evidencias

Las capturas acreditan la configuración y las respuestas observadas en la Skill. Los [dos videos de integración](../integracion/README.md) complementan este conjunto con el montaje de banco, actuación del servo y estados del Shadow. El segundo muestra la posición deseada pendiente y la convergencia posterior; el procedimiento confirmado por el equipo fue reconectar la alimentación sin repetir el comando. La revisión de DynamoDB cuenta con el conjunto AWS existente. Las capturas del simulador por sí solas no son fotografías del mecanismo ni mediciones temporales.

Las pruebas utilizaron entrada textual porque el micrófono no estuvo operativo en el entorno utilizado. No se presentan como pruebas de reconocimiento de voz.

Las evidencias generales de AWS se reutilizan desde el [conjunto ya incorporado en el repositorio](https://github.com/Sam-J-R/IoT_practica3/blob/a8a86c3f56a39b063bacd5fe4cc651dabfe73232/docs/EVIDENCIAS_AWS.md): Things y certificado, DynamoDB, Lambda e IAM, CloudWatch y Shadow de prueba. No se duplican en esta carpeta.

No se incluyen solicitudes completas de Skill I/O, tokens ni claves privadas. Las capturas muestran solo las porciones visibles de los paneles aportados.
