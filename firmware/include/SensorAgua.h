#pragma once

#include <Arduino.h>
#include "config.h"

// Lee el sensor analogico MH por GPIO34; no controla ningun actuador.
class SensorAgua {
public:
  void iniciar() {
    pinMode(PIN_AGUA_ANALOGICO, INPUT);
    analogReadResolution(12);
    analogSetPinAttenuation(PIN_AGUA_ANALOGICO, ADC_11db);
  }

  int leerRaw() const {
    // Lectura ADC sin convertir a porcentaje: rango aproximado 0..4095.
    return analogRead(PIN_AGUA_ANALOGICO);
  }

  // "estado" indica si ANTES se detectaba agua. Se conserva ese estado
  // hasta cruzar el umbral contrario (histeresis).
  // Los sensores pueden subir o bajar su lectura cuando se humedecen.
  bool detectar(int raw, bool estado, int umbralSeco, int umbralAgua) const {
    if (umbralAgua < umbralSeco) {
      raw = -raw;
      umbralSeco = -umbralSeco;
      umbralAgua = -umbralAgua;
    }
    return estado ? raw > umbralSeco : raw >= umbralAgua;
  }
};
