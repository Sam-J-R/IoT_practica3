# Matriz de pruebas y evidencias — sin resultados inventados

Estado actualizado el 8/11/2026. **«Parcial»** significa que hay una prueba física aislada, una prueba de nube o una simulación, no que el requisito esté aprobado de extremo a extremo.

## Funcionales

| ID | Escenario | Evidencia exigible | Estado |
|---|---|---|---|
| RF1 | Leer sensor analógico en entorno seco/con estímulo controlado | Serie + referencia de ensayo | Parcial: lectura seca `raw=0` y prueba ADC `raw=4095` documentadas; falta caracterizar sensor frente al estímulo |
| RF2 | Sensor y actuador en `reported` periódico | Captura Shadow y tiempos | Pendiente |
| RF3 | Lambda modifica desired → delta → servo → reported | Traza AWS + observación en la demo | Parcial: Lambda escribió `desired` real y el Thing de prueba simuló `reported`; falta ESP32 y servo en la cadena |
| RF4 | Alexa consulta presencia de agua | Simulador voz/texto + Shadow | Parcial: Lambda leyó `reported.agua_detectada`; no se adjuntó evidencia de este intent desde el simulador Alexa |
| RF5 | Alexa ordena abrir/cerrar | Simulador + servo | Parcial: Lambda escribió `desired.cubierta`; no se adjuntó evidencia del intent Alexa ni del movimiento físico |
| RF6 | Alexa consulta estado cubierta | Simulador + reported | Parcial: la Skill real consultó por texto `reported.cubierta` del Thing simulado; falta la cadena física |
| RF7 | Vinculación persiste entre sesiones | DynamoDB y dos sesiones | Parcial: la vinculación desde el simulador se persistió; no se documentaron dos sesiones Alexa reales |
| RF8 | Sin vinculación: guía; con vinculación: resolve por userId | Logs y respuestas | Parcial: el `userId` real del simulador se resolvió mediante DynamoDB; falta demostrar el conjunto completo de sesiones |
| RF9 | Thing inexistente, cambiar y desvincular | Casos positivos/negativos | Parcial: Thing inexistente rechazado y operaciones de vinculación ejercitadas directamente; falta evidencia desde Alexa |

## No funcionales

| RNF | Objetivo de trabajo | Método | Resultado |
|---|---|---|---|
| Estabilidad | 15 min sin reset/bloqueo (referencia docente ≥10 min) | Monitor serie + captura continua | No medido |
| Exactitud | Definir error adecuado a variable física/categórica y referencia verificable | 20 observaciones de referencia; reportar fallos | No medido |
| Respuesta | Intentar ≤3 s de voz a actuador físico | 10 órdenes; cronómetro, timestamps y tabla de mediciones | No medido |
| Frecuencia | Evento + respaldo cada 5 s (propuesta) | Timestamps Shadow/MQTT | No medido |
| Reconexión | Wi-Fi/MQTT automático, desired pendiente aplicado | Desconectar, ordenar offline, reconectar | Wi-Fi local probado; MQTT y recuperación `desired` no medidos |

## Pruebas locales de código (no sustituyen AWS real)

Comando desde la raíz del repositorio: `py -m unittest discover -s tests -v` en Windows, o `python -m unittest discover -s tests -v` en Linux.

- **12/12 satisfactorias** en la revisión del 7/11/2026 de la versión limpia, con el SDK incluido y clientes de AWS simulados (la versión original tenía 11/11).
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
- Estas pruebas directas no sustituyen el conjunto completo del simulador ni el ESP32 real.

## Pruebas desde la Skill Alexa (8/11/2026)

| ID | Prueba | Resultado | Estado |
|---|---|---|---|
| AX-01 | Invocar la Skill mediante el endpoint Lambda con trigger restringido | Alexa alcanzó `tendedero-inteligente-alexa` y recibió respuestas del backend | Aprobada |
| AX-02 | Vincular por texto «prueba dos» | Alexa normalizó inicialmente el slot como `prueba 2`; tras ampliar `THING_ALIASES_JSON`, Lambda resolvió `tendedero-prueba2` y vinculó el usuario | Aprobada |
| AX-03 | Ejecutar `PruebaConsultarCubierta` sobre el usuario vinculado | La ejecución terminó con `Succeeded` y respondió que la cubierta estaba abierta, coherente con `reported.cubierta` | Aprobada |

La prueba AX-02 documenta por qué el mapa final conserva variantes con palabras
y dígitos. Estas pruebas validan Alexa→Lambda→DynamoDB/Shadow, no el movimiento
del ESP32 físico.

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

Las pruebas AWS-BE validan el backend y el enrutamiento por usuario. RF4–RF9
solo se consideran completos cuando los mismos casos se ejecuten desde la Skill
real; RF2, RF3 y RF5 requieren además el ESP32 y el actuador físico.

## Informe Markdown obligatorio

1. Caso de uso y RF/RNF trazables.
2. Arquitectura, circuito, clases ESP32 + Lambda, diagramas de secuencia para vinculación, consulta de sensor y comando.
3. Contrato Shadow y tabla/userId + validaciones, modelo Alexa.
4. Implementación POO y enlaces al código.
5. AWS Thing, certificados/políticas sin secretos, IAM, DynamoDB, Alexa.
6. Pruebas con datos crudos, métricas, errores y discusión.
7. Resultados cuantificables, conclusiones, recomendaciones y anexos.
8. GitHub con archivos, evidencias y commits de las tres cuentas, link LMS.


## Cómo cerrar cada medición

- **RF1**. Aplicar el [ensayo de banco](../hardware/ENSAYO_BANCO.md). Anexar lotes de seco inicial, resistencia conocida y seco de retorno con min/máx/mediana y montaje. Registrar identificación de los electrodos.
- **Exactitud**. La salida final es binaria. Con referencia física autorizada y lote independiente, anotar estado de referencia y observado por muestra, matriz de confusión, falsos positivos/negativos y proporción de errores. Definir el criterio de aceptación con la referencia y el uso real. El ADC crudo y el estímulo eléctrico se conservan como caracterización de banco.
- **Estabilidad**. Cronometrar 15 min continuos desde un sistema integrado y guardar serie con `ms`, Shadow y varias operaciones Alexa. Contar reinicios, bloqueos y pérdida de conexión. Un reinicio de `ms` durante el ensayo se registra como incidencia.
- **Respuesta**. Grabar ≥10 órdenes alternadas con audio y cubierta visible. Medir desde fin de la frase hasta posición mecánica final y registrar también el inicio de movimiento si se distingue. Informar n, mediana, máximo y cantidad que supera la referencia de 3 s. La aceptación de `reported` es una marca de telemetría separada.
- **Frecuencia**. Capturar `update/accepted` en régimen estable y al cambiar la clasificación o posición. Calcular intervalos consecutivos y latencia de evento. Muestreo configurado a 500 ms, intento por evento y respaldo 5 s después de la aceptación previa. En régimen ideal, 5 s entre reportes representan hasta unos 12 intentos periódicos por minuto o 17 280 al día para un dispositivo conectado continuamente, antes de eventos, reintentos y mensajes de respuesta. Registrar volumen observado y contrastarlo con la configuración de cuenta vigente.
- **Reconexión**. Registrar pérdida Wi-Fi/MQTT, orden Alexa en ausencia, `desired` pendiente, vuelta de Wi-Fi, nueva sesión MQTT, `get`, movimiento y convergencia. Medir desde retorno de red hasta movimiento y aceptación, sin repetir la orden. Repetir si se puede aislar solo la pérdida de MQTT.
- **RF4–RF9**. Probar el modelo es-MX por texto y voz, guardar frase reconocida y respuesta. Demostrar dos usuarios en sesiones distintas y dos Things, incluido identificador inexistente, cambio, desvinculación y ruta de comandos aislada. Redactar identificadores completos en capturas.
