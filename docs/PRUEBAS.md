# Matriz de pruebas y evidencias

Actualización RNF: 10/11/2026, ensayos automatizados ([resultados](RESULTADOS_RNF.md)). Actualización Alexa e integración: 9/11/2026. Las capturas de respuestas, los [videos de integración](evidencias/integracion/README.md), las pruebas directas AWS y las mediciones tienen alcances distintos. El [registro Alexa](ALEXA.md) identifica resultados y fuentes.

## Funcionales

| ID | Escenario | Evidencia exigible | Estado |
|---|---|---|---|
| RF1 | Leer sensor analógico en condiciones conocidas | Serie + referencia de ensayo | INT-01 muestra `sensor_raw = 0`/`false` y `2453`/`true`; el error físico se evalúa con referencia independiente. |
| RF2 | Sensor y actuador en `reported` periódico | Shadow y tiempos | INT-01 muestra actualizaciones de sensor y cubierta; frecuencia efectiva medida en RNF4 (abajo). |
| RF3 | desired → delta → servo → reported | Observación del mecanismo y AWS | INT-02 muestra orden pendiente, giro del servo y convergencia final; procedimiento de reinicio confirmado por el equipo. |
| RF4 | Alexa consulta presencia de agua | Respuesta y estado de referencia | Captura 14 e INT-01: respuestas negativa/afirmativa coherentes con estados del Shadow. Entrada textual. |
| RF5 | Alexa solicita abrir/cerrar | Respuesta y observación del servo | Captura 15 e INT-01: solicitudes y actuación del servo en el montaje de banco. |
| RF6 | Alexa consulta cubierta | Respuesta sobre reported | Captura 14 e INT-01: consulta y estado reportado de cubierta. |
| RF7 | Vinculación persiste entre sesiones | Vincular, detener, abrir y consultar | Capturas 10 y 11: vínculo confirmado y conservado entre conversaciones. |
| RF8 | Sin vínculo guía; con vínculo resuelve por userId | Respuestas y DynamoDB | Captura 09 muestra guía; 10 y 11 muestran operaciones con vínculo. AWS documenta resolución por usuario. |
| RF9 | Validar, cambiar y eliminar vínculo | Casos positivos/negativos | Captura 12: inexistente rechazado; 13: eliminación; 16: cambio válido al Thing físico. |

Las capturas se consultan en el [índice de evidencias Alexa](evidencias/alexa/README.md). La entrada fue textual debido a la limitación de micrófono del entorno; no se presenta como reconocimiento de voz. El [registro AWS existente](https://github.com/Sam-J-R/IoT_practica3/blob/a8a86c3f56a39b063bacd5fe4cc651dabfe73232/docs/PRUEBAS.md) conserva las pruebas directas y el enrutamiento entre Things sin duplicar sus archivos.

## No funcionales

Ensayos automatizados del 10/11/2026 con `ensayo_rnf.py` y el firmware `tendedero_ensayo`. La tabla completa, con condiciones, discusión e incidencias, está en [RESULTADOS_RNF.md](RESULTADOS_RNF.md); los datos crudos están en [`resultados/`](../resultados/INDICE.md). En esos ensayos las órdenes las publica el propio ESP32 en `desired`, sin Alexa ni Lambda; el tiempo de respuesta se midió además de extremo a extremo con órdenes desde la Skill.

| RNF | Objetivo de trabajo | Método | Resultado |
|---|---|---|---|
| Estabilidad | 15 min sin reset/bloqueo (referencia docente ≥10 min) | Log serie continuo; orden o consulta cada 30 s | **Cumple.** 15,0 min, 15/15 órdenes, 14/14 consultas, 0 reinicios, 0 bloqueos. [rnf-01](../resultados/rnf-01-estabilidad-20261110-094834.md) |
| Exactitud | ≤5 % de errores en ≥20 observaciones independientes; 0 falsos negativos | 20 observaciones físicas en orden aleatorio, 3 s de estabilización | **Cumple:** 20/20, 0 FP, 0 FN. Referencia: toalla mojada y secado, rehechos en cada observación. Umbrales 200/800 estimados; solo se validaron condiciones extremas. [rnf-03](../resultados/rnf-03-sensor-20261110-104652.md) |
| Respuesta (con Alexa) | ≤3 s desde la orden en la Skill hasta la posición final | 10 órdenes alternadas desde el simulador, video del servo analizado cuadro a cuadro | **Cumple:** promedio 1,70 s, máximo 1,80 s, 0/10 superan 3 s. La primera orden tras inactividad tardó 6,47 s (Lambda en frío). [Informe](../resultados/respuesta-alexa-20261110-1431.md), [video](../resultados/RNF3.webm) |
| Respuesta (sin Alexa) | ≤3 s hasta posición final | 10 órdenes alternadas, orden MQTT desde el dispositivo | **Cumple en la modalidad ensayada:** promedio 2,19 s, máximo 2,42 s hasta la posición estimada. No incluye Alexa ni Lambda. [rnf-02](../resultados/rnf-02-respuesta-20261110-094834.md) |
| Frecuencia | Periódico ≤6 s; evento ≤1 s sin reporte pendiente | `reported aceptado` del ESP32, en reposo y con carga | **Periódico cumple** (reposo: máximo 5,74 s). **Evento no cumple:** 14/15 en ≤1 s, máximo 1,033 s. Con consultas de ensayo cada 60 s, máximo periódico 6,97 s. [Reposo](../resultados/rnf-04-frecuencia-20261110-111031.md), [con carga](../resultados/rnf-04-frecuencia-20261110-094834.md) |
| Reconexión (reinicio) | Aplicar `desired` sin repetir orden; ≤30 s | Reset por RTS/EN; el PC deja la orden mientras el ESP32 está fuera de línea | **Cumple:** 3/3, máximo 9,67 s. Un intento previo falló porque la red no estaba disponible. [rnf-05](../resultados/rnf-05-reinicio-20261110-103933.md) |
| Reconexión (Wi-Fi) | Ídem, con el equipo encendido | Desasociación `wifi_off`/`wifi_on` | **Cumple:** 3/3, máximo 7,69 s. [rnf-06](../resultados/rnf-06-reconexion-wifi-20261110-101936.md) |

INT-02 se conserva como evidencia cualitativa de recuperación tras reinicio con orden enviada desde Alexa.

## Evidencias audiovisuales de integración

| ID | Archivo | Resultado observado | Referencias aproximadas |
|---|---|---|---|
| INT-01 | [Funcionamiento completo](evidencias/integracion/01-funcionamiento-completo.mp4) | Consultas y control del servo; estados de agua y cubierta en Shadow. | 00:06–00:10: actuación/cierre; 00:13–00:21: consultas y estados del sensor. |
| INT-02 | [Recuperación de orden](evidencias/integracion/02-recuperacion-orden-reconexion.mp4) | `desired = abierta` mientras `reported = cerrada`, giro del servo y convergencia en abierta. | 00:08–00:09: delta; 00:22–00:24: giro; 00:25–00:26: estado final. |

Las marcas localizan escenas y no se registran como latencia del sistema. El [índice audiovisual](evidencias/integracion/README.md) detalla condiciones y alcance; se observa el brazo del servo de banco, sin atribuir prueba de carga de una cubierta instalada.

## Pruebas locales de código (no sustituyen AWS real)

Comando desde la raíz del repositorio: `py -m unittest discover -s tests -v` en Windows, o `python -m unittest discover -s tests -v` en Linux.

- **12/12 satisfactorias** el 7/11/2026 y de nuevo el 10/11/2026 sobre la revisión final, con el SDK incluido y clientes de AWS simulados.
- La prueba dinámica verifica dos usuarios, dos Things, vínculos independientes, órdenes sobre cada Shadow, cambio y desvinculación.
- Una prueba estática comprueba la separación de los perfiles de diagnóstico y el programa final sin LED como actuador.
- Una compilación de firmware o el paso de la suite no sustituyen la carga física ni demuestran tiempos de respuesta o permisos reales.

No introducir agua cerca de la alimentación sin aprobación y metodología segura. Un puente conductor simulado solo comprueba respuesta eléctrica, no exactitud física del sensor.

## Pruebas directas del backend AWS (7/11/2026)

- Recursos desplegados en `us-east-2`: dos Things, Shadow clásico simulado, DynamoDB, IAM y Lambda.
- El evento `LaunchRequest` cargó correctamente el handler y ASK SDK.
- `VincularThingIntent` validó `tendedero-prueba2` y persistió `userId → thingName`.
- `ConsultarAguaIntent` respondió de acuerdo con cambios reales de `reported.agua_detectada`.
- `CerrarCubiertaIntent` escribió `desired.cubierta`; el reporte simulado eliminó el `delta` al converger.
- `ConsultarCubiertaIntent` distinguió estado reportado y orden pendiente.
- Un Thing inexistente fue rechazado sin sustituir la vinculación válida.
- CloudWatch no mostró errores en las ejecuciones revisadas. La captura se conserva como evidencia.
- Estas pruebas directas AWS se complementan con las pruebas Alexa e integración registradas el 9/11 en [ALEXA.md](ALEXA.md).

### Tabla consolidada del backend desplegado

| ID | Prueba realizada | Resultado esperado | Resultado observado | Estado | Evidencia |
|---|---|---|---|---|---|
| AWS-BE-01 | Ejecutar `LaunchRequest` | Cargar ASK SDK y devolver bienvenida | La invocación terminó con `Succeeded` y devolvió la respuesta de bienvenida | Aprobada | Ejecución directa y CloudWatch |
| AWS-BE-02 | Vincular un usuario de prueba con `tendedero-prueba2` | Validar el Thing y persistir `userId → thingName` | `DescribeThing` aceptó el identificador y DynamoDB creó el ítem con fecha | Aprobada | Panel DynamoDB y ejecución directa |
| AWS-BE-03 | Consultar agua con usuario vinculado | Leer `reported.agua_detectada` del Shadow correcto | La respuesta cambió de acuerdo con el booleano simulado del Shadow | Aprobada | Ejecución directa y Shadow de prueba |
| AWS-BE-04 | Solicitar cerrar la cubierta | Escribir `desired.cubierta = cerrada` | El Shadow mostró la orden deseada y Lambda respondió que fue solicitada | Aprobada | Ejecución directa y Shadow de prueba |
| AWS-BE-05 | Consultar cubierta | Informar el último estado reportado y, si corresponde, una orden pendiente | `PruebaConsultarCubierta` terminó con `Succeeded` y respondió que la cubierta estaba abierta, coherente con el Shadow capturado | Aprobada | [`05-backend-shadow-respuesta-lambda.png`](evidencias/aws/05-backend-shadow-respuesta-lambda.png) |
| AWS-BE-06 | Simular que el dispositivo alcanzó la posición | Hacer converger `reported.cubierta` con `desired.cubierta` | Al actualizar `reported`, dejó de existir diferencia pendiente | Aprobada | Shadow de prueba |
| AWS-BE-07 | Intentar vincular un Thing inexistente | Rechazarlo sin reemplazar la vinculación válida | Lambda indicó que no estaba registrado y conservó el vínculo anterior | Aprobada | Ejecución directa |
| AWS-BE-08 | Usar dos usuarios vinculados a Things distintos | Resolver cada solicitud por su propio `userId` | Las consultas se dirigieron al Thing vinculado de cada usuario sin cruce | Aprobada | Dos ítems DynamoDB y ejecuciones directas |
| AWS-BE-09 | Cambiar la vinculación de un usuario | Sobrescribir el `thingName` para la misma clave | DynamoDB conservó un solo vínculo activo para el usuario con el nuevo Thing | Aprobada | Ejecución directa y DynamoDB |
| AWS-BE-10 | Desvincular un usuario | Eliminar el ítem y exigir nueva vinculación | El ítem fue eliminado y las operaciones posteriores solicitaron vincular | Aprobada | Ejecución directa |
| AWS-BE-11 | Revisar invocaciones en CloudWatch | No encontrar excepciones ni `AccessDenied` | Se observaron eventos `START`, `END` y `REPORT` sin errores en el periodo revisado | Aprobada | [`04-cloudwatch-ejecuciones-lambda.png`](evidencias/aws/04-cloudwatch-ejecuciones-lambda.png) y [`04-cloudwatch-eventos.csv`](evidencias/aws/04-cloudwatch-eventos.csv) |

Las pruebas AWS-BE validan el backend y el enrutamiento por usuario. Los mismos
casos se ejecutaron después desde la Skill (capturas AX-08 a AX-16) y con el
ESP32 y el servo (videos INT-01 e INT-02).
