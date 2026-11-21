#pragma once

// Copiar a calibracion_local.h cuando haya resultados del montaje real.
// -1 y 0 mantienen deshabilitada la integración. Anotar fuente y evidencia.

// Referencias de fabrica del sensor: lectura ADC (0..4095) en seco y con agua.
// Solo se usan hasta que el usuario calibre desde Alexa; despues mandan los
// valores guardados en la memoria no volatil del ESP32.
constexpr int REFERENCIA_SECO_FABRICA = -1;
constexpr int REFERENCIA_AGUA_FABRICA = -1;

// Valor seguro medido en microsegundos para cada extremo, con carga real.
// Dependen del mecanismo, no del ambiente: no se modifican desde el Shadow.
constexpr int SERVO_EXPUESTO_US = 0;
constexpr int SERVO_RESGUARDADO_US = 0;
constexpr int SERVO_FRECUENCIA_HZ = 0;
constexpr unsigned long SERVO_ASENTAMIENTO_MS = 0;
