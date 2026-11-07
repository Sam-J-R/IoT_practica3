# Ensayo de banco de Samuel

## 1. Diagnóstico y serie

1. Con el USB desconectado, cablear MH `S → D34/GPIO34`, `+ → 3V3`, `− → GND`. Dejar D26 libre durante la prueba de sensor.
2. Conectar el ESP32 con un cable USB de datos. En VS Code, **Archivo → Abrir carpeta** y elegir `firmware`, donde está `platformio.ini`.
3. En **PlatformIO → Project Tasks → sensor_test**, pulsar **Build → Upload → Monitor**. Esperar `SUCCESS` en los dos primeros pasos. Si el entorno no aparece, abrir la carpeta `firmware` y recargar VS Code.
4. Usar 115200. Si no sale ninguna línea, pulsar **EN** una vez. Para ver el COM en Windows, abrir **Administrador de dispositivos → Puertos (COM y LPT)** y observar qué puerto aparece al conectar el cable. Cerrar Monitor antes de cargar de nuevo. Si la carga se queda en `Connecting...` con el COM correcto, mantener **BOOT** hasta que empiece a escribir y soltarlo entonces.
5. Con el sensor seco, fijo y sin tocar las pistas, guardar **15–20 líneas consecutivas** `[SENSOR] ms=… raw=…`. A 500 ms por muestra, la serie abarca unos 7–10 s. Conservar el log crudo, fecha y hora de Bolivia, montaje, mínimo, máximo y mediana. El perfil del sensor no controla actuadores.

Comandos equivalentes desde la raíz del proyecto:

```powershell
pio run -d firmware -e sensor_test
pio run -d firmware -e sensor_test -t upload
pio device monitor -d firmware -b 115200
```

## 2. Estímulo eléctrico sin agua

- Con USB desconectado, identificar con multímetro en continuidad dos pistas expuestas de redes distintas. Inspeccionar las pistas antes de conectar. Si no puedes identificar ambas redes, aplaza el puente.
- Colocar una resistencia de **100 kΩ** entre esas pistas con contactos secos y firmes. Mantener los tres pines del MH como en el ensayo seco. Evitar puentes directos, contacto con el cabezal y manipulación con alimentación. Los 220 Ω disponibles son para el LED.
- Encender y guardar 15–20 lecturas. Si no hay cambio, documentarlo. Con el USB desconectado, repetir con **47 kΩ** o **10 kΩ** si están disponibles, una por vez. Retirar la resistencia con el USB desconectado y repetir el bloque seco. Conservar valores aunque no haya separación entre las muestras.
- Identificar cada bloque en el registro. Usar la resistencia para comprobar respuesta y repetibilidad eléctrica. Para validar la clasificación de agua, acordar una referencia física segura con el docente y medir casos conocidos. Si se usan umbrales derivados de un estímulo eléctrico en un ensayo de integración, marcarlos como configuración de simulación.

| Condición | Hora local | Resistencia | n | Mín. | Máx. | Mediana | Log |
|---|---|---|---:|---:|---:|---:|---|
| Seco inicial | | — | | | | | |
| Estímulo eléctrico | | | | | | | |
| Seco de retorno | | — | | | | | |

## 3. Servo y parámetros

La etiqueta informada por Samuel es TowerPro MG90S. Samuel confirmó el 7/11 que su unidad se movió correctamente en la prueba local, pero aún falta registrar la tensión, pulsos, tiempos y recorrido del mecanismo en el informe. Antes de repetir, revisar el pinout, la frecuencia PWM y la fuente regulada apropiada para los picos de corriente. [Ficha TowerPro MG90S](https://towerpro.com.tw/product/mg90s-3/).

Ensayar primero sin acoplar la cubierta, con un comprobador de servos compatible y dentro del rango de la unidad. Después acoplar la cubierta sin forzar topes. Medir pulsos de apertura y cierre en µs, frecuencia y tiempo de asentamiento con carga. Registrar tensión y capacidad de fuente, caídas durante el movimiento y compatibilidad de señal. Cortar alimentación si se atasca o zumba sostenidamente. Una vez validado, conectar D26 a la entrada de señal compatible y unir el negativo de la fuente externa con GND del ESP32.

Copiar `firmware/include/calibracion.example.h` como `calibracion_local.h` e introducir solo parámetros obtenidos del ensayo. Conservar las medidas en el informe. La clasificación usa histéresis: `UMBRAL_SECO` marca el regreso al estado seco y `UMBRAL_AGUA` la entrada al estado agua, en el sentido observado de la lectura. Validar ambos en un lote independiente.

## 4. Perfil de integración

1. Copiar `firmware/include/secrets.example.h` como `secrets.h` e introducir localmente SSID, contraseña, endpoint ATS sin protocolo, Thing y PEM de CA, certificado y clave. Usar literales de cadena cruda para PEM multilínea. Git ignora este archivo y el archivo local de calibración.
2. Compilar con `pio run -d firmware -e tendedero_shadow`. Con el montaje y calibración verificados, cargar ese perfil. Si faltan parámetros o certificados, el firmware se queda en modo ADC y D26 permanece sin señal.
3. En AWS IoT Core, abrir **MQTT test client → Subscribe to a topic** y observar los tópicos de Shadow del Thing acordado, en particular `update/delta` y `update/accepted`. En Monitor deben aparecer conexión MQTT, recuperación de Shadow y aceptación de reportes.
4. Para el ensayo offline, partir de una posición conocida. Desconectar Wi-Fi del ESP32, enviar por Alexa una orden a la posición opuesta, verificar que `desired` quedó pendiente y restablecer Wi-Fi. Registrar reconexión, `get`, movimiento físico y aceptación de `reported` sin repetir la orden.
