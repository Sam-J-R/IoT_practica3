# Conexiones de la práctica 4: luz automática (LDR + LED)

Amplía [CONEXIONES.md](CONEXIONES.md) (práctica 3), que no cambia: el sensor de agua sigue en GPIO34 y el servo en GPIO26. Se agregan un LDR, que mide la luz ambiente, y un LED de luz automática para el tendedero. El servo sigue siendo el actuador principal; el LED es un actuador adicional, como permite la consigna.

Todo funciona a 3,3 V desde la placa. No hay cargas de más de 5 V.

## LDR en GPIO35

GPIO35 pertenece al ADC1, que funciona con el Wi-Fi activo (el ADC2 no), y es un pin solo de entrada.

**Opción A: LDR suelto (dos patas).** Necesita una resistencia fija para formar un divisor de tensión. Lo ideal es una de 10 kΩ; sirve cualquiera entre 4,7 kΩ y 47 kΩ. La de 220 Ω no sirve: con tan poca resistencia la lectura casi no cambia entre luz y oscuridad.

| Desde | Hasta |
|---|---|
| `3V3` | una pata del LDR |
| otra pata del LDR | `D35` / GPIO35 **y** un extremo de la resistencia de 10 kΩ |
| otro extremo de la resistencia | `GND` |

Con este cableado, más luz da una lectura más alta.

**Opción B: módulo LDR (3 o 4 pines, con potenciómetro).** El módulo ya trae su divisor.

| Pin del módulo | ESP32 |
|---|---|
| `VCC` | `3V3` (no 5 V: la salida no debe superar 3,3 V) |
| `GND` | `GND` |
| `AO` (salida analógica) | `D35` / GPIO35 |
| `DO` (salida digital) | sin conectar |

En muchos módulos la lectura sube con la oscuridad. El firmware deduce el sentido de las dos referencias medidas, así que no hace falta invertir nada.

## LED en GPIO27

| Desde | Hasta |
|---|---|
| `D27` / GPIO27 | resistencia de 220 Ω |
| resistencia de 220 Ω | pata larga del LED (ánodo) |
| pata corta del LED (cátodo, lado plano) | `GND` |

Corriente con un LED rojo, amarillo o verde: (3,3 V − 2,0 V) / 220 Ω ≈ 6 mA, por debajo de los 12 mA recomendados por pin. Un LED blanco o azul (≈ 3 V) queda tenue con 220 Ω; para el prototipo sirve igual.

El LED se enciende y apaga con una salida digital (no PWM), así no comparte temporizador con el servo.

## Medir las referencias del LDR

1. Carguen el perfil `sensor_test` y abran el monitor serie (115200 baudios). Además de `[SENSOR]` aparece `[LDR] ms=... raw=...`.
2. Con el LDR en su lugar definitivo y con buena luz, anoten unas 20 lecturas y saquen el promedio: es `REFERENCIA_LUZ_CLARO`.
3. Tapen el LDR con la mano o cubran el montaje y repitan: es `REFERENCIA_LUZ_OSCURO`.
4. La diferencia debe ser de al menos 200. Si no, revisen la resistencia del divisor (opción A) o el potenciómetro del módulo (opción B).
5. Copien `firmware/include/luz.example.h` a `luz_local.h` (está en `.gitignore`), escriban los dos valores y pongan `LED_INSTALADO = true`.

## Probar sin el LDR (LDR simulado)

Mientras no haya resistencia para el divisor, el LED se puede conectar igual y la luz se simula desde el perfil `tendedero_ensayo`:

1. Conecten solo el LED (GPIO27 → 220 Ω → LED → GND).
2. Creen `luz_local.h` con las referencias en −1 y `LED_INSTALADO = true`.
3. Carguen `tendedero_ensayo`. En el monitor serie: `ldr_oscuro` y `ldr_claro` simulan la luz; `ldr_real` vuelve al LDR.
4. Prueba automática: `python tools/probar_esp32.py --puerto COM3 luz --ldr-simulado`.

El LDR simulado cambia al instante, sin histéresis ni los 3 s de confirmación, y el Shadow marca `luz_simulada: true` para no mezclar esos datos con lecturas reales. La medición del tiempo de respuesta de R5 hay que repetirla con el LDR real.

No conecten el LDR solo con la resistencia de 220 Ω: con un valor tan bajo la lectura casi no cambia entre luz y oscuridad.

## Cómo decide el firmware

- El nivel de luz se lleva a una escala de 0 (como la referencia oscura) a 1000 (como la clara).
- Pasa a **oscuro** por debajo de 350 y vuelve a **claro** por encima de 650. Entre esos valores conserva el estado anterior (histéresis).
- Un cambio debe mantenerse 3 s para aceptarse: una sombra que pasa no enciende el LED.
- **Regla R5 (Edge):** en modo automático, oscuro enciende el LED y claro lo apaga, también sin Internet.
- En modo automático, una orden de voz sobre el LED se rechaza: la luz la decide el LDR. En modo manual, o si no hay LDR, manda la voz.

Sin `luz_local.h`, o con valores −1, el firmware funciona igual que antes: no lee el LDR ni reporta los campos de luz.
