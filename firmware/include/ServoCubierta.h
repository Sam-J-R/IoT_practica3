#pragma once

#include <Arduino.h>
#include "config.h"

enum class Posicion { Desconocida, Abierta, Cerrada };

// Controla la cubierta con pulsos PWM. NO mide la posicion real del servo.
class ServoCubierta {
public:
  // Los extremos se configuran en microsegundos (us), NO en grados.
  ServoCubierta(int abiertaUs, int cerradaUs, int hz, unsigned long asentamientoMs)
      : abiertaUs_(abiertaUs), cerradaUs_(cerradaUs), hz_(hz),
        asentamientoMs_(asentamientoMs) {}

  bool iniciar() {
    return ledcSetup(CANAL, hz_, BITS) > 0;
  }

  void solicitar(Posicion posicion, unsigned long ahora) {
    // Nunca mover con una orden desconocida ni repetir el mismo destino.
    if (posicion == Posicion::Desconocida || posicion == destino_) {
      return;
    }
    const int pulsoUs = posicion == Posicion::Abierta ? abiertaUs_ : cerradaUs_;
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
  int abiertaUs_;
  int cerradaUs_;
  int hz_;
  unsigned long asentamientoMs_;
  Posicion destino_ = Posicion::Desconocida;
  unsigned long inicioMs_ = 0;
};
