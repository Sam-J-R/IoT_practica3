#include <Arduino.h>

#include "ServoTendedero.h"

#if __has_include("calibracion_local.h")
#include "calibracion_local.h"
#else
#include "calibracion.example.h"
#endif

namespace {
ServoTendedero servo(SERVO_EXPUESTO_US, SERVO_RESGUARDADO_US, SERVO_FRECUENCIA_HZ,
                    SERVO_ASENTAMIENTO_MS);
bool listo = false;
Posicion anterior = Posicion::Desconocida;

bool parametrosValidos() {
  return SERVO_FRECUENCIA_HZ > 0 && SERVO_ASENTAMIENTO_MS > 0 &&
         SERVO_EXPUESTO_US > 0 && SERVO_RESGUARDADO_US > 0 &&
         SERVO_EXPUESTO_US != SERVO_RESGUARDADO_US &&
         static_cast<uint64_t>(SERVO_EXPUESTO_US) * SERVO_FRECUENCIA_HZ < 1000000 &&
         static_cast<uint64_t>(SERVO_RESGUARDADO_US) * SERVO_FRECUENCIA_HZ < 1000000;
}
}

void setup() {
  Serial.begin(115200);
  Serial.println("[P3] Prueba local del servo, sin WiFi ni AWS");
  if (!parametrosValidos()) {
    Serial.println("[SERVO] Deshabilitado: configurar y verificar calibracion_local.h");
    return;
  }
  listo = servo.iniciar();
  if (!listo) {
    Serial.println("[SERVO] Error al configurar PWM");
    return;
  }
  Serial.println("[SERVO] Listo. Enviar E para expuesto o R para resguardado.");
  Serial.println("[SERVO] Usar fuente externa regulada, GND comun y comenzar sin carga.");
}

void loop() {
  if (!listo) {
    delay(100);
    return;
  }

  const unsigned long ahora = millis();
  while (Serial.available() > 0) {
    const char orden = static_cast<char>(Serial.read());
    if (orden == 'E' || orden == 'e') {
      servo.solicitar(Posicion::Expuesto, ahora);
      Serial.println("[SERVO] Solicitado expuesto");
    } else if (orden == 'R' || orden == 'r') {
      servo.solicitar(Posicion::Resguardado, ahora);
      Serial.println("[SERVO] Solicitado resguardado");
    }
  }

  const Posicion estimada = servo.estimada(ahora);
  if (estimada != anterior) {
    anterior = estimada;
    if (estimada != Posicion::Desconocida) {
      Serial.printf("[SERVO] Asentamiento estimado completado ms=%lu\n", ahora);
    }
  }
  delay(10);
}
