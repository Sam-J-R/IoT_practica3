# Resultados de los requisitos no funcionales

Ensayos del 10 de noviembre de 2026, 09:48–11:15, hora de Bolivia. Montaje de banco: ESP32, sensor MH y servomotor, con el Thing `tendedero-inteligente` en AWS IoT Core (`us-east-2`).

Los datos crudos, los informes por ensayo y el registro de sesiones fallidas están en [`resultados/`](../resultados/INDICE.md). El procedimiento está en [ENSAYOS_RNF_SIN_CONSOLA.md](ENSAYOS_RNF_SIN_CONSOLA.md) y la herramienta es [`ensayo_rnf.py`](../ensayo_rnf.py).

## 1. Condiciones comunes

Los ensayos se automatizaron con `ensayo_rnf.py` y el firmware `tendedero_ensayo`. Ese firmware es el programa final más comandos por puerto serie: `abrir`, `cerrar`, `estado`, `wifi_off` y `wifi_on`, además de líneas con marca de tiempo. Las horas proceden del reloj del PC al recibir cada línea serie.

No había acceso a la consola de AWS. La política del certificado solo admite el clientId del propio dispositivo, por lo que la confirmación del servicio se toma de las respuestas `update/accepted` y `get/accepted` que recibe el ESP32. Mientras el ESP32 estaba fuera de línea, el PC leyó el Shadow con el mismo certificado; esos documentos se guardaron como JSON.

Diferencias con el procedimiento de la [guía de mediciones](GUIA_MEDICIONES_RNF.md), que se aplican a todos los resultados:

| Aspecto | Guía | Ensayo realizado |
|---|---|---|
| Origen de las órdenes | Texto en el simulador de Alexa | El ESP32 publica `desired.cubierta` con el mismo documento que usa Lambda; AWS devuelve el delta. No interviene Alexa ni Lambda. |
| Consultas durante la estabilidad | Alexa | Lectura del Shadow desde el propio dispositivo. |
| Posición final | Posición física observada | Fin del asentamiento configurado (1000 ms), estimado por el firmware; no hay sensor de posición. |
| Pérdida de red | Apagar el punto de acceso | El ESP32 se desasocia (`wifi_off`) y el punto de acceso sigue encendido. |
| Reinicio | Desconectar la alimentación | Reset por la línea RTS al pin EN: el chip arranca de cero, pero el servo no pierde alimentación. |

Los objetivos son los del [informe técnico §1.3](INFORME.md#13-requerimientos-no-funcionales-medibles), declarados el 9/11. El límite de 30 s para la recuperación se fijó en la guía de ensayos antes de ejecutarlos. Ningún objetivo se modificó después de ver los resultados.

## 2. Tabla final

| Requisito | Objetivo declarado | Resultado medido | ¿Cumple? | Evidencia y limitaciones |
|---|---|---|---|---|
| RNF1 Estabilidad | 15 min continuos, 0 reinicios, 0 bloqueos | 15,0 min; 15/15 órdenes y 14/14 consultas completadas; 0 reinicios, 0 silencios serie > 5 s, 0 desconexiones MQTT; máximo 6,97 s sin reporte aceptado | **Cumple** | [rnf-01](../resultados/rnf-01-estabilidad-20261110-094834.md). Las consultas fueron desde el dispositivo, no por Alexa. |
| RNF2 Clasificación del sensor | ≤ 5 % de errores en ≥ 20 observaciones independientes, repartidas entre seco y agua. El ensayo exigió además 0 falsos negativos | 20 observaciones (10 secas, 10 con agua): 20 aciertos, 0 FP, 0 FN. ADC seco 0; con agua 1745–2221; umbrales 200/800 | **Cumple** | [rnf-03](../resultados/rnf-03-sensor-20261110-104652.md). Referencia: toalla mojada en contacto (agua) y secado con su parte seca (seco), rehaciendo la condición en cada observación. Los umbrales son estimados, sin lote de calibración registrado. Solo se validaron condiciones extremas (ver §3.4). |
| RNF3 Tiempo de respuesta | ≤ 3 s hasta la posición final | 10/10 órdenes. Envío → delta: promedio 1,19 s, máximo 1,42 s. Envío → posición estimada: promedio 2,19 s, máximo 2,42 s. Envío → reporte aceptado: máximo 2,86 s | **Cumple en la modalidad ensayada** | [rnf-02](../resultados/rnf-02-respuesta-20261110-094834.md). No incluye Alexa ni Lambda, así que no es la latencia de voz ni de texto del enunciado. Lambda, medida aparte el 7/11 (§5.2 del informe): 457–673 ms en caliente y 4045,84 ms en la primera invocación. |
| RNF4 Frecuencia de reporte | Periódico ≤ 6 s en red estable; por evento ≤ 1 s sin reporte pendiente | Pasivo: 54 intervalos, promedio 5,39 s, máximo 5,74 s. Por evento: 14 de 15 cambios en ≤ 1 s, promedio 0,56 s, máximo 1,033 s. Con carga: máximo periódico 6,97 s | **Periódico: cumple.** **Por evento: no cumple** (1 de 15, por 0,033 s) | [rnf-04 pasivo](../resultados/rnf-04-frecuencia-20261110-111031.md) y [rnf-04 con carga](../resultados/rnf-04-frecuencia-20261110-094834.md). Ver §3.2. |
| RNF5 Recuperación tras reinicio | Aplicar el `desired` vigente sin repetir la orden; convergencia en ≤ 30 s | 3/3 repeticiones con orden pendiente verificada, sin repetirla y con convergencia. MQTT en 4,36–6,79 s; reporte aceptado a los 8,19 s de promedio, máximo 9,67 s | **Cumple** | [rnf-05](../resultados/rnf-05-reinicio-20261110-103933.md) y JSON `rnf-05-repN-pendiente-20261110-103933.json`. Reset por EN. Hay incidencias en intentos anteriores (§3.3). |
| RNF5 Reconexión de red | Ídem, con el equipo encendido | 3/3 repeticiones correctas. MQTT en 3,15–5,02 s; reporte aceptado a los 6,57 s de promedio, máximo 7,69 s | **Cumple** | [rnf-06](../resultados/rnf-06-reconexion-wifi-20261110-101936.md) y JSON `rnf-06-repN-pendiente-20261110-101936.json`. La desasociación la provoca el ESP32. |

Los tiempos de recuperación se cuentan desde la liberación del reset o desde `wifi_on` hasta el `reported aceptado` posterior al movimiento.

## 3. Discusión

### 3.1 Tiempo de respuesta

Alrededor de 1 s del tiempo total es el asentamiento configurado del servo. El trayecto por la nube, desde la publicación hasta la recepción del delta, promedia 1,19 s. Para estimar el tiempo con Alexa habría que añadir el procesamiento de la Skill y de Lambda, que no se midió junto con el resto. Con Lambda en caliente es plausible seguir por debajo de 3 s. En la primera invocación tras inactividad, Lambda duró por sí sola 4,05 s, por lo que esa orden probablemente superaría el objetivo. Esto es una estimación, no una medición del recorrido completo.

### 3.2 Frecuencia de reporte

En reposo, el respaldo periódico se mantuvo entre 5,28 y 5,74 s. El exceso sobre 5 s es de diseño: el plazo cuenta desde la aceptación anterior e incluye el viaje de ida y vuelta a AWS.

Durante la estabilidad, 10 de 158 intervalos superaron 6 s (6,15–6,97 s). Los 10 siguen a una consulta `estado`, un comando de ensayo que hace que el ESP32 pida el documento completo del Shadow. En operación real las consultas de Alexa las resuelve Lambda sin pasar por el ESP32, por lo que no se espera este efecto en uso normal. Esa sesión tampoco cumplía la condición de la guía de mantener sensor y cubierta constantes, y por eso se repitió de forma pasiva. Ambos ensayos se informan.

El reporte por evento promedió 0,56 s, pero un evento tardó 1,033 s sin reporte pendiente, por encima del objetivo de 1 s. La diferencia está dentro de la variación del viaje a AWS, aunque el objetivo declarado no se cumple estrictamente. Las alternativas son mantener el objetivo e informarlo así, o justificar en el informe un objetivo distinto para próximos ensayos; este resultado no cambia.

### 3.3 Incidencias

| Hora | Incidencia | Tratamiento |
|---|---|---|
| 10:05 y 10:13 | El ensayo Wi-Fi se interrumpió: el firmware cargado no tenía el comando `wifi_off` (`comando desconocido`). | Se cargó el firmware actualizado; el ensayo de las 10:19 se completó. No es un fallo del sistema ensayado. |
| 10:24 | Reinicio, repetición 2: el ESP32 arrancó y midió el sensor, pero no conectó a MQTT en 270 s. | Causa no registrada por el firmware de ese momento; causa probable en la fila siguiente. |
| 10:29 | Disco del PC lleno: el log se cortó y el ensayo quedó inválido. | Se liberó espacio; el script ahora se detiene si queda menos de 200 MB. |
| 10:36–10:38 | El ESP32 informó `sin wifi estado=1` (no encuentra la red configurada) durante 2 min. | Ensayo interrumpido. A las 10:39 la red volvió y el reinicio cumplió 3/3. |

La recuperación depende de que el punto de acceso esté disponible. Si la red desaparece varios minutos, como ocurrió entre 10:24 y 10:38, la orden queda pendiente en el Shadow hasta que vuelva.

### 3.4 Clasificación del sensor

Las 20 observaciones son independientes: el sensor se secó y se volvió a mojar en cada una. La separación fue amplia: seco siempre ADC 0, con agua entre 1745 y 2221, frente a umbrales de 200 y 800. Esa misma amplitud limita el alcance: la toalla mojada representa agua abundante, y el ensayo no evalúa gotas aisladas ni humedad leve, que caerían entre los umbrales. Los umbrales son estimaciones del equipo, sin un lote de calibración registrado. El resultado acredita que el sistema distingue seco de mojado con claridad, no un desempeño ante lluvia ligera.

### 3.5 Alcance

Los resultados corresponden a un montaje de banco, con una red Wi-Fi y en un único día. No acreditan funcionamiento bajo carga de una cubierta real, reconocimiento de voz ni consultas por Alexa durante los ensayos. La posición de la cubierta es la estimada por el firmware; los videos INT-01 e INT-02 muestran el giro físico del brazo en sesiones anteriores.

## 4. Información aportada después de los ensayos

Nada. Los datos del ensayo del sensor que aportó el equipo después del ensayo (método de referencia, independencia y origen de los umbrales) están incorporados aquí, en [rnf-03](../resultados/rnf-03-sensor-20261110-104652.md) y en el informe técnico, identificados como información posterior.
