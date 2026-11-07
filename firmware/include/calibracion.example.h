#pragma once

// Copiar a calibracion_local.h cuando haya resultados del montaje real.
// -1 y 0 mantienen deshabilitada la integración. Anotar fuente y evidencia.
constexpr int UMBRAL_SECO = -1;
constexpr int UMBRAL_AGUA = -1;
// Valor seguro medido en microsegundos para cada extremo, con carga real.
constexpr int SERVO_ABIERTA_US = 0;
constexpr int SERVO_CERRADA_US = 0;
constexpr int SERVO_FRECUENCIA_HZ = 0;
constexpr unsigned long SERVO_ASENTAMIENTO_MS = 0;
