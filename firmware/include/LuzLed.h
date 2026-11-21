#pragma once

#include <Arduino.h>
#include "TiposTendedero.h"
#include "config.h"

// LED de luz automatica en GPIO27 (con resistencia de 220 ohm en serie).
// Encendido/apagado digital: no usa PWM, asi no comparte temporizador con el servo.
class LuzLed {
public:
  void iniciar() {
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);
    estado_ = Luz::Apagada;
  }

  // Devuelve true si el estado cambio.
  bool aplicar(Luz luz) {
    if (luz == Luz::Desconocida || luz == estado_) return false;
    digitalWrite(PIN_LED, luz == Luz::Encendida ? HIGH : LOW);
    estado_ = luz;
    return true;
  }

  Luz estado() const { return estado_; }

private:
  Luz estado_ = Luz::Desconocida;
};
