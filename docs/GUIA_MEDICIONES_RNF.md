# Guía para medir los requisitos no funcionales

Práctica 3 — Tendedero inteligente con Alexa y AWS IoT Core.

Guía de ensayo preparada el 9 de noviembre de 2026, hora de Bolivia.

Este documento explica cómo realizar y registrar mediciones. Las tablas vacías son formularios para el ensayo; no representan resultados ni afirman que las pruebas no se hayan realizado. Si ya existen registros válidos, pueden reutilizarse.

## 1. Qué se debe demostrar

Los requisitos no funcionales evalúan qué tan bien funciona el sistema: estabilidad, exactitud del sensor, tiempo de respuesta, frecuencia de reporte y recuperación tras una desconexión.

Para cada requisito se necesita:

1. Un objetivo declarado y justificado.
2. Un procedimiento con inicio y fin definidos.
3. Mediciones y condiciones de ensayo.
4. Evidencias identificables.
5. Una conclusión que compare resultados y objetivo.

Las referencias del enunciado no son resultados obtenidos. Una captura aislada normalmente no demuestra tiempos ni estabilidad.

### Reparto del trabajo

| Responsable | Actividad |
|---|---|
| Kathy — Alexa | Enviar comandos, registrar respuestas y coordinar tiempos. |
| Samuel — dispositivo | Observar sensor, movimiento, alimentación y monitor serie. |
| María — AWS | Observar Shadow, mensajes MQTT y timestamps. |

### Modalidad de interacción

Las pruebas descritas utilizan entrada textual en el simulador de Alexa Developer Console. La responsable reportó que el micrófono no estuvo operativo en su entorno. Registrar esta condición al presentar resultados; una medición desde envío textual no debe llamarse latencia de voz.

## 2. Estabilidad

### Objetivo

Operar durante 15 minutos sin reinicios ni bloqueos. Este es el objetivo propuesto en la documentación del equipo; el enunciado proporciona como referencia al menos 10 minutos.

### Procedimiento

1. Conectar el sistema completo y comprobar que responde.
2. Iniciar un cronómetro y guardar la salida del monitor serie.
3. Durante los 15 minutos, enviar consultas y órdenes de apertura/cierre de manera espaciada.
4. Observar si el ESP32 reinicia, deja de responder o presenta movimientos inesperados.
5. Comprobar que continúan los reportes en AWS.
6. Registrar duración e incidencias al finalizar.

No desconectar intencionalmente el dispositivo durante este ensayo. Las interrupciones se evalúan en el ensayo de reconexión.

### Registro

| Fecha y hora inicial | Hora final | Duración observada | Órdenes | Consultas | Reinicios | Bloqueos | Otras incidencias |
|---|---|---|---:|---:|---:|---:|---|
| | | | | | | | |

Conservar el log serie completo y el registro de inicio/fin. Un video continuo es útil, pero no obligatorio. Los mensajes de arranque y un reinicio del contador `ms` pueden ayudar a identificar reinicios; contrastarlos con el resto del registro.

### Conclusión a completar

> Durante ___ minutos se realizaron ___ operaciones, con ___ reinicios y ___ bloqueos. El objetivo declarado se cumplió/no se cumplió porque ___. Evidencias: ___.

Si hubo un fallo, conservar y describir ese ensayo. Una repetición posterior debe quedar identificada como otro ensayo.

## 3. Tiempo de respuesta

### Objetivo y definición

Declarar el tiempo máximo aceptable. El enunciado proporciona como referencia ≤3 segundos de voz a actuador; en este entorno se medirá una modalidad diferente:

> Tiempo desde el envío del comando textual en el simulador hasta que la cubierta alcanza físicamente la posición solicitada.

Registrar explícitamente esta diferencia al comparar resultados con el enunciado.

### Procedimiento

1. Dejar la cubierta en una posición conocida.
2. Grabar de manera que se vea el envío del comando y el mecanismo.
3. Enviar `cierra la cubierta`.
4. Identificar el instante de envío y el de posición física final.
5. Calcular la diferencia.
6. Repetir alternando apertura y cierre; se proponen 10 órdenes. Esta cantidad es una propuesta de ensayo, no una exigencia literal del docente.

La respuesta «He solicitado…» no marca el fin de la medición. El campo `Duration` de CloudWatch mide la ejecución Lambda, no el recorrido completo hasta el movimiento físico.

### Registro

Usar una misma base temporal para inicio y fin, por ejemplo las marcas de un video.

| Prueba | Orden | Instante de envío (s) | Instante de posición final (s) | Tiempo transcurrido (s) | Incidencia |
|---:|---|---:|---:|---:|---|
| 1 | Cerrar | | | | |
| 2 | Abrir | | | | |
| 3 | Cerrar | | | | |
| 4 | Abrir | | | | |
| 5 | Cerrar | | | | |
| 6 | Abrir | | | | |
| 7 | Cerrar | | | | |
| 8 | Abrir | | | | |
| 9 | Cerrar | | | | |
| 10 | Abrir | | | | |

```text
Tiempo de respuesta = instante final − instante de envío
Promedio = suma de tiempos / número de pruebas
Máximo = mayor tiempo observado
```

Informar también cuántas pruebas superaron el objetivo. Indicar si se incluyó la primera invocación después de inactividad; no descartar resultados lentos sin explicar el criterio.

Si se utiliza cronómetro manual, declarar la incertidumbre por reacción humana. Revisar un video permite identificar los instantes con mayor precisión.

### Resumen

| Objetivo (s) | Número de pruebas | Promedio (s) | Máximo (s) | Pruebas que superan el objetivo | Método de medición |
|---:|---:|---:|---:|---:|---|
| | | | | | |

## 4. Exactitud de la clasificación del sensor

### Qué comparar

La salida final del proyecto es binaria. Comparar una condición física de referencia —seco o presencia de agua— con `agua_detectada`, que puede ser `false` o `true`.

El valor ADC es una lectura cruda; no es porcentaje de lluvia ni una medida directa de volumen de agua.

### Procedimiento

1. Confirmar con el responsable del hardware un método seguro para establecer ambas condiciones, manteniendo líquidos alejados del ESP32 y de la alimentación.
2. Calibrar los umbrales y registrar los valores utilizados.
3. Realizar un lote de validación diferente al usado para calibrar.
4. Anotar condición física, ADC y clasificación reportada para cada observación.
5. Incluir transiciones de seco a agua y de agua a seco, respetando un tiempo de estabilización definido y registrado.
6. Comprobar que cada observación corresponde a una actualización del dispositivo y no a un reporte antiguo conservado en el Shadow.

Se proponen 20 observaciones distribuidas entre ambas condiciones. Repetir veinte veces una consulta sobre el mismo reporte no constituye veinte observaciones físicas independientes.

### Condiciones del ensayo

| Parámetro | Valor utilizado |
|---|---|
| Referencia física y método | |
| `UMBRAL_SECO` | |
| `UMBRAL_AGUA` | |
| Tiempo de estabilización | |
| Distribución de muestras secas/con agua | |
| Criterio de aceptación declarado | |

### Registro por observación

| Observación | Hora | Condición de referencia | ADC | `agua_detectada` | ¿Coincide? | Incidencia |
|---:|---|---|---:|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |

Añadir una fila por cada observación realizada.

| Tipo de resultado | Clasificación |
|---|---|
| Referencia con agua y salida `true` | Acierto: verdadero positivo |
| Referencia seca y salida `false` | Acierto: verdadero negativo |
| Referencia seca y salida `true` | Error: falso positivo |
| Referencia con agua y salida `false` | Error: falso negativo |

```text
Proporción de aciertos (%) = aciertos / observaciones × 100
Proporción de errores (%) = errores / observaciones × 100
```

Una clasificación ausente o desconocida debe registrarse explícitamente, no convertirse automáticamente en seco ni excluirse sin explicación.

El criterio de aceptación debe declararse y justificarse según el uso real. Un falso negativo puede informar al usuario que no hay agua cuando sí existe. Una prueba eléctrica con resistencia caracteriza la respuesta del circuito, pero no demuestra por sí sola exactitud ante agua real.

## 5. Frecuencia de reporte

### Configuración y conceptos

| Concepto | Configuración del código revisado |
|---|---|
| Muestreo del sensor | Cada 500 ms |
| Intento de reporte por evento | Cambio de clasificación de agua o de posición, sujeto a sincronización y reporte pendiente |
| Respaldo periódico | Nominalmente 5 segundos desde la aceptación anterior |

Muestrear cada 500 ms no significa publicar cada 500 ms. El código no genera un reporte inmediato por cada variación de ADC: compara la clasificación y la posición para detectar cambios relevantes.

### Procedimiento periódico

1. Mantener constantes sensor y cubierta.
2. Observar los mensajes `$aws/things/NOMBRE_DEL_THING/shadow/update/accepted` del dispositivo en el cliente MQTT de AWS.
3. Registrar timestamps de unos 10 reportes consecutivos del ESP32. Distinguirlos de actualizaciones de Lambda o manuales; el `clientToken` del firmware ayuda a identificarlos.
4. Calcular diferencias entre mensajes y conservar el registro de origen.

| Reporte | Timestamp observado | Intervalo respecto al anterior (s) | `clientToken` |
|---:|---|---:|---|
| 1 | | — | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |
| 9 | | | |
| 10 | | | |

### Procedimiento por evento

1. Cambiar la condición del sensor y observar cuándo llega el nuevo valor.
2. Enviar una orden de cubierta y observar su reporte final.
3. Registrar los tiempos y las condiciones, incluidos posibles reintentos.

Informar intervalo promedio y máximo. No garantizar exactamente 5,000 segundos: el código cuenta desde la aceptación anterior y existen tiempos de red y procesamiento.

### Justificación y resumen

> Combinamos cambios relevantes con respaldo periódico para actualizar la información sin publicar cada lectura analógica.

Definir y justificar el intervalo máximo aceptable según el caso de uso y contrastarlo con los valores observados. Considerar también el volumen de mensajes y las condiciones de la cuenta AWS; no asumir que todas las operaciones serán gratuitas.

| Objetivo máximo (s) | Intervalo promedio (s) | Intervalo máximo (s) | Reporte por evento observado | Evidencia |
|---:|---:|---:|---|---|
| | | | | |

## 6. Reconexión y sincronización

### Dos escenarios diferentes

- Desconectar y reconectar la alimentación prueba recuperación después de un reinicio.
- Interrumpir Wi-Fi manteniendo el ESP32 encendido prueba reconexión de red durante la ejecución.

La responsable confirmó que el equipo ya probó el primer escenario y observó la aplicación de la orden al reconectar. Conservar las condiciones y evidencias de esa ejecución si están disponibles.

### Procedimiento de reconexión de red

1. Mantener el ESP32 encendido y dejar la cubierta abierta.
2. Desactivar temporalmente el punto de acceso Wi-Fi.
3. Enviar `cierra la cubierta` desde Alexa.
4. Comprobar en AWS `desired.cubierta = cerrada` y `reported.cubierta = abierta`.
5. Restablecer Wi-Fi.
6. Sin repetir la orden, observar conexión MQTT, movimiento y actualización de `reported`.

El responsable del hardware debe confirmar que el montaje permanece alimentado durante la interrupción de red. Se puede invertir abierta/cerrada siempre que la orden pida la posición opuesta a la inicial.

### Registro

| Dato | Resultado |
|---|---|
| Fecha y hora | |
| Número de repetición | |
| Tipo de interrupción: alimentación o Wi-Fi | |
| Posición inicial | |
| Orden enviada durante la interrupción | |
| Estado `desired`/`reported` durante la interrupción | |
| Hora de restablecimiento | |
| Hora de recuperación MQTT | |
| Hora de posición física final | |
| Hora de aceptación del reporte final | |
| ¿Se repitió la orden? | |
| ¿Convergieron `desired` y `reported`? | |
| Evidencias | |

Se proponen tres repeticiones para observar reproducibilidad. Si se declara un tiempo máximo de recuperación, definir el punto de inicio, por ejemplo cuando el punto de acceso vuelve a estar disponible, y medir siempre desde ese mismo criterio.

### Explicación del mecanismo

> La orden queda almacenada en `desired` durante la desconexión. Cuando el firmware establece una nueva conexión MQTT, solicita el Shadow, recupera la posición deseada, la aplica y actualiza `reported`.

El Shadow conserva el estado deseado final; no es una cola histórica de todas las órdenes enviadas durante la desconexión.

## 7. Organización de evidencias

Una sesión de estabilidad puede servir también para observar frecuencia de reportes y ejecutar órdenes para medir respuesta. Mantener identificados los instantes y las condiciones de cada medición. La clasificación del sensor y las interrupciones intencionales conviene tratarlas como ensayos separados.

| Contenido | Nombre sugerido |
|---|---|
| Registro de estabilidad | `rnf-01-estabilidad.md` |
| Log serie continuo | `rnf-01-monitor-serie.txt` |
| Tiempos por orden | `rnf-02-tiempos-respuesta.csv` |
| Grabación usada para medir movimiento, si se realiza | `rnf-02-respuesta-fisica.mp4` |
| Observaciones de clasificación del sensor | `rnf-03-validacion-sensor.csv` |
| Timestamps e intervalos de reportes | `rnf-04-frecuencia-reportes.csv` |
| Ensayo de recuperación | `rnf-05-reconexion.md` |
| Shadow durante la desconexión | `rnf-05-orden-pendiente.png` |
| Shadow después de aplicar la orden | `rnf-05-orden-aplicada.png` |

Los nombres son sugerencias. Enlazar las evidencias ya existentes evita duplicarlas. Un video por cada operación no es obligatorio; pueden combinar escenarios en una grabación e indicar las marcas temporales.

No incluir credenciales, claves privadas, tokens de Skill I/O ni identificadores completos de usuarios en archivos públicos.

## 8. Tabla final de conclusiones

| Requisito | Objetivo declarado | Resultado medido | ¿Cumple? | Evidencia y limitaciones |
|---|---|---|---|---|
| Estabilidad | | | | |
| Tiempo de respuesta textual → actuador | | | | |
| Clasificación del sensor | | | | |
| Frecuencia de reporte | | | | |
| Recuperación tras reinicio | | | | |
| Reconexión de red y sincronización | | | | |

Los resultados no tienen que ser perfectos para documentarse correctamente. Las condiciones, mediciones, incidencias y conclusiones deben ser verificables y coherentes con los objetivos declarados. No rellenar valores estimados como si fueran mediciones reales.

## Referencias del proyecto

- [Enunciado de la práctica](../referencias/Práctica_3.md).
- [Matriz de pruebas](PRUEBAS.md).
- [Programa principal del ESP32](../firmware/src/Tendedero.cpp).
- [Cliente Shadow](../firmware/src/ClienteShadow.cpp).
- [Sensor de agua](../firmware/include/SensorAgua.h).
- [Control del servo](../firmware/include/ServoCubierta.h).
- [Configuración de intervalos y pines](../firmware/include/config.h).
