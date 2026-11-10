# Referencia de conexiones del prototipo

Esta referencia sirve para cableado y diagnóstico. El [informe](../docs/INFORME.md) incluye el circuito, su justificación y el alcance de las evidencias; las fotografías o videos no sustituyen mediciones de alimentación.

Fotografías en `referencias/`: ESP32, sensor MH frontal y posterior.

## Sensor MH (3 pines `S + -`)

| Sensor | ESP32 | Razón |
|---|---|---|
| `S` | GPIO34 (`D34`) | ADC1_CH6, entrada analógica compatible con Wi-Fi |
| `+` | `3V3` | Señal limitada a 3,3 V; compatible con modelos equivalentes 3,3–5 V |
| `−` | `GND` | Tierra común |

El sensor mostrado no tiene `DO`/`AO` separados, únicamente `S`, que funciona como salida analógica. No tratarlo como sensor digital con DO. No conectar `+` a 5 V/VIN cuando S va directamente a ADC del ESP32.

## Restricción del prototipo

No se emplean LEDs como actuadores. Los perfiles incluidos permiten probar el sensor y el servo por separado. El sensor **no** debe mover automáticamente la cubierta: los cambios proceden de Alexa mediante el Shadow.

## Servo (unidad identificada en el registro como MG90S)

- Señal PWM: `D26/GPIO26`; los videos de integración muestran movimiento del brazo en banco. Registrar pulsos y fuente usados para reproducirlo.
- Positivo de servo: fuente DC regulada con tensión/corriente indicada por SU modelo, nunca GPIO ni salida 3V3 del ESP32.
- Negativo: GND fuente compartido con ESP32.
- Medir pulsos `SERVO_ABIERTA_US` y `SERVO_CERRADA_US`, frecuencia y asentamiento. Ver el [ensayo de banco](ENSAYO_BANCO.md).
- Verificar fuerza necesaria, tope mecánico, recorrido, corriente de arranque y reinicios ESP32.
- Actuador DC ≤12 V, prohibida carga 220 V AC.

## Seguridad

- Conectar/desconectar cableado con USB desconectado.
- No introducir agua cerca de protoboard/ESP32. Validar con docente método de simulación del sensor.
- No usar resistencias de 220 Ω como alimentación o divisor del servo.
- El sensor resistivo puede corroerse por alimentación continua en húmedo; considerar activación por lectura en el diseño final si el tiempo lo permite y si no rompe estabilidad.

