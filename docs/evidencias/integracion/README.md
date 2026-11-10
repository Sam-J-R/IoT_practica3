# Videos de integración y recuperación de orden

Registro documental: **9 de noviembre de 2026**. Los archivos originales se conservan sin recortes, rotaciones ni cambios de contenido.

| ID | Archivo | Duración aproximada | Tamaño | Respaldo principal |
|---|---|---|---|---|
| INT-01 | [01-funcionamiento-completo.mp4](01-funcionamiento-completo.mp4) | 21,70 s | 2 940 705 bytes | Consultas y órdenes en Alexa, posición del servo y valores del sensor en el Shadow. |
| INT-02 | [02-recuperacion-orden-reconexion.mp4](02-recuperacion-orden-reconexion.mp4) | 26,16 s | 3 994 085 bytes | Orden pendiente en `desired`, actuación después de reconectar y convergencia con `reported`. |

Las marcas siguientes son aproximadas y sirven para localizar escenas. No son mediciones de tiempo de respuesta del sistema.

## INT-01 — Funcionamiento integrado

| Momento del video | Contenido visible |
|---|---|
| 00:00 | Shadow con `desired.cubierta = abierta`, `reported.cubierta = abierta`, `sensor_raw = 0` y `agua_detectada = false`. |
| 00:02–00:04 | Solicitud de apertura en el simulador y consulta que informa cubierta abierta. |
| 00:06–00:08 | Servo visible junto al simulador; se observa el cambio de orientación del brazo durante la secuencia de control y una solicitud de cierre. |
| 00:09–00:10 | Shadow con `desired.cubierta = cerrada` y `reported.cubierta = cerrada`; el sensor reporta `0` y `false`. |
| 00:13–00:14 | Consulta del sensor y respuesta «El sensor no detecta agua». |
| 00:15–00:16 | Shadow con `sensor_raw = 2453` y `agua_detectada = true`, conservando cubierta cerrada. |
| 00:19–00:21 | Nueva consulta del sensor y respuesta «El sensor detecta agua». |

**Resultado observado:** las respuestas de Alexa se corresponden con los estados del Shadow mostrados; la secuencia incluye el servo físico y su cambio de posición. La comparación entre `raw = 0`/`false` y `raw = 2453`/`true` acredita dos estados reportados, no una calibración metrológica ni un porcentaje de lluvia.

## INT-02 — Recuperación de una posición deseada

El procedimiento comunicado por el equipo fue desconectar el cable del ESP32, solicitar apertura y volver a conectarlo sin repetir la orden. Se documenta como **recuperación tras desconexión y nuevo arranque**, diferenciada de una pérdida aislada de Wi-Fi con el dispositivo encendido.

| Momento del video | Contenido visible |
|---|---|
| 00:00–00:03 | Montaje de banco: ESP32, sensor y servomotor. |
| 00:05–00:06 | En el simulador se muestra «abre la cubierta» y la confirmación de solicitud de apertura. |
| 00:08–00:09 | Shadow con `desired.cubierta = abierta`, `reported.cubierta = cerrada` y `delta.cubierta = abierta`: hay una posición pendiente. |
| 00:11–00:21 | Vista del montaje durante el retorno a operación; el brazo del servo permanece en su posición inicial durante parte de la espera. |
| 00:22–00:24 | Cambio de orientación del brazo del servo. |
| 00:25–00:26 | Shadow con `desired.cubierta = abierta` y `reported.cubierta = abierta`, sin el delta anterior en la vista mostrada. |

**Resultado observado:** se pasa de una posición deseada diferente de la reportada a la convergencia de ambas, y se observa actuación del servo. La ejecución sin repetir la orden corresponde al procedimiento confirmado por el equipo.

## Alcance y relación con requisitos

- **RF1/RF4:** valores del sensor reportados y consultas coherentes en INT-01.
- **RF2:** se muestran actualizaciones de sensor y actuador; la frecuencia efectiva se determina con timestamps de reportes consecutivos, no con la duración de este video.
- **RF3/RF5/RF6:** solicitudes de apertura/cierre, actuación del servo, consulta y estados reportados en INT-01; orden pendiente y convergencia en INT-02.
- **Recuperación de orden:** INT-02 respalda la parte funcional del ensayo tras reconectar el dispositivo.

Los videos muestran un montaje de banco y el brazo del servomotor; los estados abierta/cerrada son las posiciones lógicas del proyecto. No se atribuye al video una prueba mecánica con carga de una cubierta instalada. El firmware estima la posición después del asentamiento, sin sensor independiente que detecte atasco.

La entrada de los comandos fue textual en el simulador debido a la limitación de micrófono del entorno. El audio que pudiera acompañar las grabaciones no convierte el ensayo en una prueba de reconocimiento de voz.

Estos archivos no contienen una serie de mediciones de latencia, estabilidad o error del sensor. La duración de cada grabación y las marcas de navegación no se presentan como valores de esos RNF.

## Documentos relacionados

- [Configuración y pruebas Alexa](../../ALEXA.md).
- [Matriz de pruebas](../../PRUEBAS.md).
- [Informe técnico](../../INFORME.md).
- [Capturas del simulador](../alexa/README.md).
