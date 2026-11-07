#include <Arduino.h>
#include <WiFi.h>
#include <time.h>

#include "ClienteShadow.h"
#include "SensorAgua.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

namespace {
constexpr unsigned long REINTENTO_INICIO_MQTT_MS = 10000;
constexpr time_t RELOJ_MINIMO = 1704067200;
SensorAgua sensor;
ClienteShadow shadow;
bool configurado = false;
bool clienteIniciado = false;
unsigned long ultimaLectura = 0;
unsigned long ultimoIntentoMqtt = 0;
int raw = 0;

bool credencialesValidas() {
  return WIFI_SSID[0] && AWS_IOT_ENDPOINT[0] && AWS_IOT_THING_NAME[0] &&
         AWS_CA_PEM[0] && AWS_CLIENT_CERT_PEM[0] && AWS_CLIENT_KEY_PEM[0];
}
}

void setup() {
  Serial.begin(115200);
  sensor.iniciar();
  Serial.println("[P3] Prueba MQTT TLS + Shadow del sensor | servo deshabilitado");
  configurado = credencialesValidas();
  if (!configurado) {
    Serial.println("[P3] Faltan credenciales WiFi o AWS en include/secrets.h");
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org");
  ultimoIntentoMqtt = millis() - REINTENTO_INICIO_MQTT_MS;
}

void loop() {
  const unsigned long ahora = millis();
  if (ahora - ultimaLectura >= INTERVALO_SENSOR_MS) {
    ultimaLectura = ahora;
    raw = sensor.leerRaw();
    Serial.printf("[SENSOR] ms=%lu raw=%d\n", ahora, raw);
  }

  if (configurado && !clienteIniciado && WiFi.status() == WL_CONNECTED &&
      time(nullptr) >= RELOJ_MINIMO &&
      ahora - ultimoIntentoMqtt >= REINTENTO_INICIO_MQTT_MS) {
    ultimoIntentoMqtt = ahora;
    clienteIniciado = shadow.iniciar(AWS_IOT_ENDPOINT, AWS_IOT_THING_NAME,
                                    AWS_CA_PEM, AWS_CLIENT_CERT_PEM, AWS_CLIENT_KEY_PEM);
    if (!clienteIniciado) Serial.println("[MQTT] Fallo de inicio; se reintentara");
  }

  // No aplicar ordenes al actuador en esta prueba. Es un perfil separado del final.
  shadow.atender(ahora, static_cast<ServoCubierta*>(nullptr));
  shadow.reportarSensor(ahora, raw);
  delay(10);
}
