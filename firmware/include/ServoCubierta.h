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
    return ledcSetup(CANAL, hz_, BITS) > 0; // prepara la señal, pero no envia aun
  }

  //ordenar una posicion
  void solicitar(Posicion posicion, unsigned long ahora) {
    // Nunca mover con una orden desconocida ni repetir el mismo destino.
    if (posicion == Posicion::Desconocida || posicion == destino_) {
      return;
    }
    const int pulsoUs = posicion == Posicion::Abierta ? abiertaUs_ : cerradaUs_; // escoge el pulso correspondiente
    const uint32_t duty = (static_cast<uint64_t>(pulsoUs) * hz_ * (1UL << BITS)) / 1000000UL; //convierte la duracion del pulso a un valor de duty cycle para ledcWrite
    if (destino_ == Posicion::Desconocida) { // si es la primera vez que se mueve, conecta el pin al canal
      ledcAttachPin(PIN_SERVO_PWM, CANAL);
    }
    ledcWrite(CANAL, duty); //envia la señal 
    destino_ = posicion;
    inicioMs_ = ahora;
  }
  
  // decidir si se ha alcanzado la posicion ordenada, o si aun esta en movimiento
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
