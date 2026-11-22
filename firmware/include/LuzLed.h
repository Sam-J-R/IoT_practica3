#pragma once

#include <Arduino.h>
#include "TiposTendedero.h"
#include "config.h"

// Luz para recoger la ropa en GPIO27 (LED con resistencia de 220 ohm en serie).
// La enciende la voz; el programa principal la apaga sola tras LED_APAGADO_AUTOMATICO_MS.
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
