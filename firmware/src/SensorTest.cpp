#include <Arduino.h>
#include "SensorAgua.h"

namespace {
SensorAgua sensor;
unsigned long ultimaLectura = 0;
}
//PRUEBA DE LAS LECTURAS DEL SENSOR
void setup() {
  Serial.begin(115200);
  sensor.iniciar();
  Serial.println("[P3] Prueba del sensor: GPIO34, lectura ADC, sin servo ni AWS");
}

void loop() {
  const unsigned long ahora = millis();
  if (ahora - ultimaLectura >= INTERVALO_SENSOR_MS) {//cada 500ms
    ultimaLectura = ahora;
    Serial.printf("[SENSOR] ms=%lu raw=%d\n", ahora, sensor.leerRaw());
  }
  delay(5);
}
