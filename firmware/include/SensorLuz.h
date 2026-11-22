#pragma once

#include <Arduino.h>
#include "config.h"

// LDR en divisor de tension leido por GPIO35. Clasifica el ambiente en dia
// (claro) o noche (oscuro) con histeresis y confirmacion temporal. La decision
// de resguardar de noche la toma LogicaEdge (regla R5).
class SensorLuz {
public:
  SensorLuz(int referenciaClaro, int referenciaOscuro)
      : claro_(referenciaClaro), oscuro_(referenciaOscuro) {}

  // Sin referencias validas el LDR se considera no instalado.
  bool instalado() const {
    const int diferencia = claro_ > oscuro_ ? claro_ - oscuro_ : oscuro_ - claro_;
    return claro_ >= 0 && claro_ <= 4095 && oscuro_ >= 0 && oscuro_ <= 4095 &&
           diferencia >= SEPARACION_MINIMA_LUZ;
  }

  void iniciar() {
    if (!instalado()) return;
    pinMode(PIN_LDR_ANALOGICO, INPUT);
    analogReadResolution(12);
    analogSetPinAttenuation(PIN_LDR_ANALOGICO, ADC_11db);
  }

  int leerRaw() const { return analogRead(PIN_LDR_ANALOGICO); }

  // Nivel de luz de 0 (como la referencia oscura) a 1000 (como la clara).
  // Puede salir de ese rango si el ambiente es mas extremo que la calibracion.
  long nivel(int raw) const {
    return (static_cast<long>(raw) - oscuro_) * 1000L / (claro_ - oscuro_);
  }

  // Procesa una lectura. Devuelve -1 sin dato, 0 claro, 1 oscuro.
  // La primera lectura decide de inmediato; despues, un cambio debe
  // mantenerse LUZ_CONFIRMACION_MS para aceptarse.
  int actualizar(int raw, unsigned long ahora) {
    if (!instalado()) return estado_;
    const long n = nivel(raw);
    if (estado_ < 0) {
      estado_ = n < 500 ? 1 : 0;
      return estado_;
    }
    int objetivo = estado_;
    if (estado_ == 0 && n <= LUZ_PERMIL_OSCURO) objetivo = 1;
    if (estado_ == 1 && n >= LUZ_PERMIL_CLARO) objetivo = 0;
    if (objetivo == estado_) {
      hayCandidato_ = false;
      return estado_;
    }
    if (!hayCandidato_ || candidato_ != objetivo) {
      hayCandidato_ = true;
      candidato_ = objetivo;
      desde_ = ahora;
    }
    if (ahora - desde_ >= LUZ_CONFIRMACION_MS) {
      estado_ = objetivo;
      hayCandidato_ = false;
    }
    return estado_;
  }

  int estado() const { return estado_; }

private:
  int claro_;
  int oscuro_;
  int estado_ = -1;
  bool hayCandidato_ = false;
  int candidato_ = -1;
  unsigned long desde_ = 0;
};
