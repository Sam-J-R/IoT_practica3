# Ensayos RNF sin acceso a la cuenta AWS

Complemento de `GUIA_MEDICIONES_RNF.md`. Recursos disponibles: ESP32 montado, certificado del dispositivo, nombre del Thing (`tendedero-inteligente`) y endpoint ATS. No hay acceso a la consola de AWS (cliente MQTT de prueba, CloudWatch, Shadow).

## 1. Restricción que condiciona los ensayos

La política del certificado (`aws/iot-certificate-policy.template.json`) solo permite `iot:Connect` con el clientId `tendedero-inteligente` y solo suscribirse a cinco temas concretos del Shadow. Consecuencias:

- Un monitor en el PC con otro clientId es rechazado. Esto explica que en `rnf-01.csv` y `rnf-04.csv` la fuente `mqtt_estado` solo registre `desconectado`, con reintentos cada vez más espaciados: el monitor del PC nunca llegó a conectarse.
- Un cliente en el PC con el mismo clientId expulsa al ESP32 (AWS admite una sola conexión por clientId). Solo puede usarse mientras el ESP32 está desconectado, que es justamente el caso del ensayo de reconexión.
- Por tanto, la observación de AWS se hace desde el propio dispositivo: el firmware imprime `[SHADOW] reported aceptado` cuando recibe `update/accepted` con su `clientToken`. Esa línea es la confirmación del servicio, no una suposición local.

## 2. Herramientas

| Archivo | Uso |
|---|---|
| `firmware/platformio.ini`, entorno `tendedero_ensayo` | Mismo firmware final con `-DMODO_ENSAYO_RNF`. Añade los comandos serie `abrir`, `cerrar`, `estado` y líneas con marca de tiempo: `[ENSAYO] orden … publicada`, `[SHADOW] delta recibido`, `[SERVO] orden entregada`, `[SHADOW] get … desired=… reported=…`. Sin la bandera, el firmware compila igual que antes. |
| `grabar_rnf.py` | Graba el monitor serie y las marcas en CSV. Si se escribe `abrir`/`cerrar`/`estado`, registra la marca y envía el comando al ESP32. Ya no intenta conectar a AWS. |
| `orden_offline.py` | Deja una orden en `desired` y lee el Shadow con el certificado del dispositivo. Solo con el ESP32 desconectado. Guarda el documento del Shadow en JSON. |
| `analizar_rnf.py` | Igual que antes, con el desglose envío → delta → servo y la confirmación de AWS por serie. |
| `ensayo_rnf.py` | Ejecuta los ensayos de forma automática, calcula el veredicto contra los objetivos declarados y genera informes (sección 7). |

Preparación: `pio run -e tendedero_ensayo -t upload`, cerrar el monitor de PlatformIO (si no, aparece `Acceso denegado` en COM3, como en `rnf-04.csv`) y lanzar `python grabar_rnf.py --puerto COM3 --salida rnf-0X.csv`. Instalar con `pip install pyserial paho-mqtt`.

**Cómo funciona la orden de ensayo.** `abrir`/`cerrar` hace que el ESP32 publique `{"state":{"desired":{"cubierta":"…"}}}` en `shadow/update`, el mismo documento que publica Lambda. AWS calcula el delta y lo devuelve al ESP32, que lo procesa por el mismo código que una orden de Alexa. El recorrido ESP32 → AWS IoT Core → delta → servo es real; lo que no se incluye es Alexa ni Lambda.

## 3. Lo que ya está medido en los registros existentes

Verificado sobre los registros previos a la automatización, conservados en [`resultados/previos/`](../resultados/previos/README.md) (horas de Bolivia, 10/11/2026).

**Frecuencia de reporte (RNF 4), respaldo periódico.** `rnf-01.csv`, 00:20:40–00:39:44: 214 reportes aceptados, 213 intervalos, promedio 5,35 s, máximo 5,54 s, mínimo 5,29 s. `rnf-04.csv`: 30 intervalos, promedio 5,34 s, máximo 5,53 s. El exceso sobre 5 s es coherente con el código: el plazo cuenta desde la aceptación anterior, así que cada intervalo suma el viaje de ida y vuelta ESP32–AWS (≈0,3 s).

**Frecuencia de reporte, por evento.** `rnf-prueba.csv`: el sensor pasa a `agua=1` a las 00:13:00,440 y AWS acepta el reporte a las 00:13:01,273 (0,83 s, intervalo de 3,28 s respecto al anterior); vuelve a `agua=0` a las 00:13:12,939 y se acepta a las 00:13:14,377 (1,44 s). Son dos eventos; conviene ampliar la muestra durante el ensayo del sensor.

**Estabilidad (RNF 1), parcial.** `rnf-01.csv`: 19 min 4 s de serie continua (00:20:40–00:39:44), contador `ms` sin reinicios, sin mensajes de arranque, sin silencios mayores de 5 s, sin `[MQTT] Desconectado`. Termina por un error del puerto en el PC, no del ESP32. No hubo órdenes ni consultas durante ese intervalo, así que no cumple el procedimiento declarado (operar con órdenes y consultas); repetirlo con órdenes (sección 4.1).

**Incidencia de red observada.** `rnf-eventos.csv`, 00:06:00,4: error de transporte MQTT (`errno=119`), reconexión a las 00:06:11,5 y Shadow recuperado a las 00:06:13,3. Es una incidencia espontánea, útil como observación, no un ensayo controlado.

**Componente Lambda.** `docs/evidencias/aws/04-cloudwatch-eventos.csv`: cuatro invocaciones del 7/11/2026. La primera, en frío, duró 4045,84 ms, con 689,80 ms adicionales de inicialización (`Init Duration`); las tres siguientes duraron 457,30, 622,83 y 673,31 ms. Mide solo la ejecución de Lambda; no se suma a otros tiempos para inventar un total.

## 4. Ensayos pendientes

### 4.1 Estabilidad con carga (RNF 1)

Escribir `est_ini`, luego cada minuto aproximadamente alternar `cerrar`, `estado`, `abrir`, `estado` durante 15 minutos (≈15 órdenes y ≈15 consultas), y terminar con `est_fin`. Análisis: `python analizar_rnf.py --csv rnf-01b.csv estabilidad`. Las consultas aquí son lecturas del Shadow desde el dispositivo, no consultas por Alexa; declararlo.

Puede ser la misma sesión que el ensayo 4.2: las marcas `envio`/`final` no interfieren.

### 4.2 Tiempo de respuesta (RNF 2)

Si el simulador de Alexa sigue respondiendo (la skill y Lambda pueden seguir desplegadas aunque no tengan la consola), seguir el procedimiento original: es la modalidad que pide la guía. Si no, usar este:

1. Grabar en video el mecanismo y la terminal de `grabar_rnf.py` en el mismo encuadre.
2. Escribir `cerrar` y, al ver el brazo detenido, escribir `final`. Esperar unos 10 s y repetir con `abrir`. Hacer 10 órdenes.
3. Analizar: `python analizar_rnf.py --csv rnf-02.csv respuesta`.

El análisis da tres medidas por orden: envío → delta recibido (ida y vuelta por AWS IoT Core), envío → posición estimada por el firmware (incluye el asentamiento configurado de 1000 ms) y envío → marca `final` (observación humana, con su incertidumbre de reacción). El video permite corregir la marca `final` fotograma a fotograma.

Modalidad a declarar: «orden publicada en `desired` desde el dispositivo hasta el servo, sin Alexa ni Lambda». No es comparable directamente con «≤3 s de voz a actuador». Si se quiere dar contexto, citar la duración de Lambda de CloudWatch como componente medido aparte.

### 4.3 Clasificación del sensor (RNF 3)

Umbrales del firmware: `UMBRAL_SECO = 200`, `UMBRAL_AGUA = 800`. Lecturas secas ya registradas: máximo 157 en `rnf-01.csv`; en `rnf-prueba.csv` hay lecturas con agua entre 208 y 1325 y lecturas de hasta 526 durante transiciones, por eso el tiempo de estabilización importa.

1. Con Samuel, fijar el método seguro para mojar y secar el sensor lejos del ESP32.
2. Para cada observación, establecer la condición, escribir `seco` o `agua` y no tocar nada durante el tiempo de estabilización (3 s por defecto).
3. Alternar condiciones; 20 observaciones (10 y 10), incluyendo transiciones en ambos sentidos.
4. Analizar: `python analizar_rnf.py --csv rnf-03.csv sensor --estab 3`.

La columna «AWS aceptó» indica cuánto tardó el siguiente `reported aceptado` tras la lectura. Tras un cambio de clasificación es el reporte por evento, que además alimenta el RNF 4.

### 4.4 Reconexión de red (RNF 6)

Requisito: el PC necesita Internet por otra vía (cable, datos del celular) mientras se apaga el punto de acceso `sami` del ESP32.

1. Con `grabar_rnf.py` en marcha y la cubierta abierta, escribir `wifi_off` y apagar el punto de acceso.
2. Esperar a que el serie muestre `[MQTT] Desconectado` (puede tardar por el keepalive). Si no aparece, no importa: al conectar el PC con el mismo clientId, AWS cierra la sesión anterior.
3. En otra terminal: `python orden_offline.py --endpoint … --thing tendedero-inteligente --ca … --cert … --key … --posicion cerrada --csv rnf-05.csv`. El script registra la marca `orden`, publica y guarda el Shadow en JSON con `desired = cerrada`, `reported = abierta` y el delta. Ese JSON sustituye a la captura `rnf-05-orden-pendiente.png`.
4. Encender el punto de acceso y escribir `wifi_on`. Sin repetir la orden, esperar el movimiento y escribir `final`.
5. Escribir `estado`: el serie imprime `desired` y `reported` de AWS; si coinciden, hay convergencia (sustituye a `rnf-05-orden-aplicada.png`).
6. Repetir tres veces invirtiendo la posición. Analizar: `python analizar_rnf.py --csv rnf-05.csv reconexion`.

### 4.5 Recuperación tras reinicio (RNF 5)

Igual que 4.4, pero con `power_off`/`power_on` y desconectando la alimentación. Analizar con `reconexion --off power_off --on power_on`. Al reabrir el puerto el ESP32 arranca de cero; el contador `ms` reiniciado es esperado aquí.

## 5. Limitaciones a declarar

Sin consola AWS no hay capturas del Shadow; la evidencia es el log serie con las respuestas de AWS (`update/accepted`, `get/accepted`) y los JSON de `orden_offline.py`. Las horas provienen del reloj del PC al recibir cada línea serie; la latencia USB es despreciable frente a los tiempos medidos. El servo no tiene realimentación de posición: «posición estimada» es el fin del asentamiento configurado, y la posición física la confirma la marca `final` o el video.

## 6. Integridad de los registros

`completar_15.py` genera líneas de sensor, Shadow y MQTT sintéticas para alargar un registro hasta 15 minutos. Ninguna de sus salidas debe usarse como evidencia. Se revisó `rnf-01.csv`: sus horas están en hora local (el script escribe UTC) y los tiempos tienen la variación propia del dispositivo, por lo que no contiene esa salida. El script se eliminó del repositorio.

## 7. Ejecución automática

`ensayo_rnf.py` controla el ESP32 por el puerto serie y, cuando el dispositivo está fuera de línea, AWS con el certificado. Requiere el entorno `tendedero_ensayo`, que además de `abrir`, `cerrar` y `estado` acepta `wifi_off` y `wifi_on`.

```text
python ensayo_rnf.py --puerto COM3 todo --endpoint ag9...-ats.iot.us-east-2.amazonaws.com \
    --thing tendedero-inteligente --ca "certificados AWS/AmazonRootCA1.pem" \
    --cert "certificados AWS/...-certificate.pem.crt" --key "certificados AWS/...-private.pem.key"
python ensayo_rnf.py --puerto COM3 sensor --referencia "gotas con gotero sobre las pistas; secado con papel"
```

| Ensayo | Automatización | Intervención humana |
|---|---|---|
| `respuesta` (RNF 2) | 10 órdenes alternadas; mide envío → delta → posición estimada → reporte aceptado. | Ninguna. Video opcional para la posición física. |
| `estabilidad` (RNF 1 y 4) | 15 min, orden o consulta cada 30 s; detecta reinicios, silencios y huecos de reporte; calcula la frecuencia periódica y por evento. | Ninguna. |
| `wifi` (RNF 6) | `wifi_off` en el ESP32, el PC deja la orden opuesta en `desired`, `wifi_on`; mide red, MQTT, GET, movimiento y reporte; verifica convergencia. | Ninguna. |
| `reinicio` (RNF 5) | Mantiene el ESP32 en reset con RTS (pin EN), deja la orden y lo libera. Con `--modo manual` pide desconectar y reconectar la alimentación. | Solo en modo manual. |
| `sensor` (RNF 3) | Genera una secuencia aleatoria equilibrada, espera la estabilización, toma la lectura y clasifica VP/VN/FP/FN. | El operador moja o seca el sensor cuando se le indica. |

Objetivos por defecto, modificables por argumento: respuesta ≤ 3 s (`--objetivo`), 15 min (`--minutos`), periódico ≤ 6 s (`--max-intervalo`), recuperación ≤ 30 s (`--max-recuperacion`), sensor ≥ 95 % de aciertos y 0 falsos negativos (`--criterio`, `--max-fn`). Declarar y justificar en el informe los valores usados; el veredicto se calcula con ellos y no se ajusta después de ver los resultados.

Salidas en `resultados/`: `log-<sesión>.csv` (compatible con `analizar_rnf.py`), una tabla CSV y un informe Markdown por ensayo, los JSON del Shadow con la orden pendiente y `resumen.md` con la tabla final de la sección 8 de la guía. Si un ensayo falla o se interrumpe, el log se conserva y el informe dice «No cumple» o el motivo de la interrupción; ese resultado se documenta tal cual y una repetición es un ensayo nuevo.

Diferencias con la guía que deben declararse: las órdenes no pasan por Alexa ni Lambda; el corte de red lo provoca el ESP32 al desasociarse (no un apagado del punto de acceso); el reinicio por RTS no corta la alimentación del servo; la posición es la estimada por el firmware al terminar el asentamiento.
