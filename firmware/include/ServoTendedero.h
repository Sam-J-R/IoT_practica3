#pragma once

#include <Arduino.h>
#include "config.h"

// Expuesto: el brazo deja el tendedero fuera del techo.
// Resguardado: el brazo gira el tendedero hasta debajo del techo.
enum class Posicion { Desconocida, Expuesto, Resguardado };

// Mueve el brazo del tendedero con pulsos PWM. NO mide la posicion real del servo.
class ServoTendedero {
public:
  // Los extremos se configuran en microsegundos (us), NO en grados.
  ServoTendedero(int expuestoUs, int resguardadoUs, int hz, unsigned long asentamientoMs)
      : expuestoUs_(expuestoUs), resguardadoUs_(resguardadoUs), hz_(hz),
        asentamientoMs_(asentamientoMs) {}

  bool iniciar() {
    return ledcSetup(CANAL, hz_, BITS) > 0;
  }

  void solicitar(Posicion posicion, unsigned long ahora) {
    // Nunca mover con una orden desconocida ni repetir el mismo destino.
    if (posicion == Posicion::Desconocida || posicion == destino_) {
      return;
    }
    const int pulsoUs = posicion == Posicion::Expuesto ? expuestoUs_ : resguardadoUs_;
    const uint32_t duty = (static_cast<uint64_t>(pulsoUs) * hz_ * (1UL << BITS)) / 1000000UL;
    if (destino_ == Posicion::Desconocida) {
      ledcAttachPin(PIN_SERVO_PWM, CANAL);
    }
    ledcWrite(CANAL, duty);
    destino_ = posicion;
    inicioMs_ = ahora;
  }

  Posicion estimada(unsigned long ahora) const {
    // Se considera alcanzado el destino al pasar el tiempo calibrado.
    // Si el mecanismo esta atascado, este metodo NO puede detectarlo.
    return ahora - inicioMs_ >= asentamientoMs_ ? destino_ : Posicion::Desconocida;
  }

private:
  static constexpr int CANAL = 0;
  static constexpr int BITS = 16;
  int expuestoUs_;
  int resguardadoUs_;
  int hz_;
  unsigned long asentamientoMs_;
  Posicion destino_ = Posicion::Desconocida;
  unsigned long inicioMs_ = 0;
};
