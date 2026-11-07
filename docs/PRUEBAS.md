# Matriz de pruebas y evidencias — sin resultados inventados

Estado actualizado el 7/11/2026. **«Parcial»** significa que hay una prueba física aislada o una prueba local simulada, no que el requisito esté aprobado de extremo a extremo.

## Funcionales

| ID | Escenario | Evidencia exigible | Estado |
|---|---|---|---|
| RF1 | Leer sensor analógico en entorno seco/con estímulo controlado | Serie + referencia de ensayo | Parcial: lectura seca `raw=0` y prueba ADC `raw=4095` documentadas; falta caracterizar sensor frente al estímulo |
| RF2 | Sensor y actuador en `reported` periódico | Captura Shadow y tiempos | Pendiente |
| RF3 | Lambda modifica desired → delta → servo → reported | Traza AWS + video servo | Parcial: servo físico probado por Samuel, falta cadena AWS completa |
| RF4 | Alexa consulta presencia de agua | Simulador voz/texto + Shadow | Pendiente |
| RF5 | Alexa ordena abrir/cerrar | Simulador + servo | Pendiente |
| RF6 | Alexa consulta estado cubierta | Simulador + reported | Pendiente |
| RF7 | Vinculación persiste entre sesiones | DynamoDB y dos sesiones | Pendiente |
| RF8 | Sin vinculación: guía; con vinculación: resolve por userId | Logs y respuestas | Pendiente |
| RF9 | Thing inexistente, cambiar y desvincular | Casos positivos/negativos | Pendiente |

## No funcionales

| RNF | Objetivo de trabajo | Método | Resultado |
|---|---|---|---|
| Estabilidad | 15 min sin reset/bloqueo (referencia docente ≥10 min) | Monitor serie + captura continua | No medido |
| Exactitud | Definir error adecuado a variable física/categórica y referencia verificable | 20 observaciones de referencia; reportar fallos | No medido |
| Respuesta | Intentar ≤3 s de voz a actuador físico | 10 órdenes; video con inicio/fin y cronometraje | No medido |
| Frecuencia | Evento + respaldo cada 5 s (propuesta) | Timestamps Shadow/MQTT | No medido |
| Reconexión | Wi-Fi/MQTT automático, desired pendiente aplicado | Desconectar, ordenar offline, reconectar | Wi-Fi local probado; MQTT y recuperación `desired` no medidos |

## Pruebas locales de código (no sustituyen AWS real)

Comando desde la raíz del repositorio: `py -m unittest discover -s tests -v` en Windows, o `python -m unittest discover -s tests -v` en Linux.

- **12/12 satisfactorias** en la revisión del 7/11/2026 de la versión limpia, con el SDK incluido y clientes de AWS simulados (la versión original tenía 11/11).
- La prueba dinámica verifica dos usuarios, dos Things, vínculos independientes, órdenes sobre cada Shadow, cambio y desvinculación.
- Una prueba estática comprueba la separación de los perfiles de diagnóstico y el programa final sin LED como actuador.
- Una compilación de firmware o el paso de la suite no sustituyen la carga física ni demuestran tiempos de respuesta o permisos reales.

No introducir agua cerca de la alimentación sin aprobación y metodología segura. Un puente conductor simulado solo comprueba respuesta eléctrica, no exactitud física del sensor.

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
