#include <Arduino.h>
#include "SensorAgua.h"

namespace {
SensorAgua sensor;
unsigned long ultimaLectura = 0;
}

void setup() {
  Serial.begin(115200);
  sensor.iniciar();
  // P4: tambien se muestra el LDR (GPIO35) para medir REFERENCIA_LUZ_CLARO y
  // REFERENCIA_LUZ_OSCURO de luz_local.h. Si no esta conectado, la lectura flota.
  pinMode(PIN_LDR_ANALOGICO, INPUT);
  analogSetPinAttenuation(PIN_LDR_ANALOGICO, ADC_11db);
  Serial.println("[P3] Prueba del sensor: GPIO34, lectura ADC, sin servo ni AWS");
  Serial.println("[P4] LDR en GPIO35: anotar raw con luz y con el LDR tapado");
}

void loop() {
  const unsigned long ahora = millis();
  if (ahora - ultimaLectura >= INTERVALO_SENSOR_MS) {
    ultimaLectura = ahora;
    Serial.printf("[SENSOR] ms=%lu raw=%d\n", ahora, sensor.leerRaw());
    Serial.printf("[LDR] ms=%lu raw=%d\n", ahora, analogRead(PIN_LDR_ANALOGICO));
  }
  delay(5);
}
