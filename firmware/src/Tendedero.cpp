#include <Arduino.h>
#include <WiFi.h>
#include <time.h>
#include "ClienteShadow.h"
#include "SensorAgua.h"

// PROGRAMA FINAL DEL ESP32
// 1. Lee el sensor de agua cada 500 ms.
// 2. Se conecta a AWS IoT Core usando MQTT seguro (TLS).
// 3. ClienteShadow recibe ordenes de Alexa por el Device Shadow y mueve el servo.
// 4. Publica el sensor y la posicion ESTIMADA del servo en reported.
// IMPORTANTE: leer agua NO mueve el servo automaticamente.

#if __has_include("calibracion_local.h")
#include "calibracion_local.h"
#else
#include "calibracion.example.h"
#endif

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

namespace {
constexpr unsigned long REINTENTO_RED_MS = 10000; // Reintento de conexion Wi-Fi o MQTT cada 10 s.
constexpr time_t RELOJ_MINIMO = 1704067200; // 2024-01-01 UTC, descarta un reloj sin SNTP.
SensorAgua sensor;
ServoCubierta servo(SERVO_ABIERTA_US, SERVO_CERRADA_US, SERVO_FRECUENCIA_HZ,
                    SERVO_ASENTAMIENTO_MS);
ClienteShadow shadow;
bool integracion = false; // Solo se activa con credenciales y calibracion validas.
bool mqttIniciado = false;
unsigned long ultimaLectura = 0;
unsigned long ultimoIntentoMqtt = 0;
int raw = 0;
int agua = -1; // -1 = no sabemos; 0 = seco; 1 = se detecta agua.
Posicion cubierta = Posicion::Desconocida;

bool calibracionValida() {
  const bool sensorValido =
      UMBRAL_SECO >= 0 && UMBRAL_SECO <= 4095 &&
      UMBRAL_AGUA >= 0 && UMBRAL_AGUA <= 4095 && UMBRAL_SECO != UMBRAL_AGUA;

  const bool servoValido =
      SERVO_FRECUENCIA_HZ > 0 && SERVO_ASENTAMIENTO_MS > 0 &&
      SERVO_ABIERTA_US > 0 && SERVO_CERRADA_US > 0 && SERVO_ABIERTA_US != SERVO_CERRADA_US &&
      static_cast<uint64_t>(SERVO_ABIERTA_US) * SERVO_FRECUENCIA_HZ < 1000000 &&
      static_cast<uint64_t>(SERVO_CERRADA_US) * SERVO_FRECUENCIA_HZ < 1000000;

  return sensorValido && servoValido;
}

bool credencialesConfiguradas() {
  return WIFI_SSID[0] && AWS_IOT_ENDPOINT[0] && AWS_IOT_THING_NAME[0] &&
         AWS_CA_PEM[0] && AWS_CLIENT_CERT_PEM[0] && AWS_CLIENT_KEY_PEM[0];
}

void muestrear(unsigned long ahora) {//lee y procesa si hay agua o no, con histeresis
  raw = sensor.leerRaw();
  ultimaLectura = ahora;
  if (integracion) {
    // Histeresis: un umbral para entrar en "agua" y otro para volver a "seco".
    // Evita que pequenas variaciones en el ADC cambien el estado repetidamente.
    const bool desdeSeco = sensor.detectar(raw, false, UMBRAL_SECO, UMBRAL_AGUA);
    const bool desdeAgua = sensor.detectar(raw, true, UMBRAL_SECO, UMBRAL_AGUA);
    //si dan resultados distintos, la lectura cayo en la zona intermedia de los umbrales. 
    if (agua >= 0 || desdeSeco == desdeAgua) { 
      agua = agua == 1 ? desdeAgua : desdeSeco; //si habia agua entonces verifica el umbral desdeAgua, si estaba seco verifica el umbral desdeSeco
    }
  }
  Serial.printf("[SENSOR] ms=%lu raw=%d agua=%d\n", ahora, raw, agua);
}
}

void setup() {
  Serial.begin(115200);
  sensor.iniciar();
  // Seguridad: sin parametros validos, solo se leen valores ADC.
  // No se intenta AWS ni se da una orden al servo.
  integracion = calibracionValida() && credencialesConfiguradas() && servo.iniciar();
  muestrear(millis());
  if (!integracion) {
    Serial.println("[P3] Solo ADC. Completar calibracion y secretos locales para habilitar TLS y servo");
    return;
  }

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org");
  ultimoIntentoMqtt = millis() - REINTENTO_RED_MS; // fuerza un intento inmediato de MQTT
}

void loop() {
  const unsigned long ahora = millis();

  // Paso 1: actualizar la lectura del sensor.
  if (ahora - ultimaLectura >= INTERVALO_SENSOR_MS) muestrear(ahora);

  // Paso 2: iniciar MQTT una vez haya Wi-Fi y reloj correcto para TLS.
  // ClienteShadow gestiona las reconexiones posteriores.
  if (integracion && !mqttIniciado && WiFi.status() == WL_CONNECTED &&
      time(nullptr) >= RELOJ_MINIMO && ahora - ultimoIntentoMqtt >= REINTENTO_RED_MS) {
    ultimoIntentoMqtt = ahora;
    mqttIniciado = shadow.iniciar(AWS_IOT_ENDPOINT, AWS_IOT_THING_NAME, AWS_CA_PEM,
                                 AWS_CLIENT_CERT_PEM, AWS_CLIENT_KEY_PEM);
  }

  // Paso 3: procesar deltas del Shadow. Aqui puede llegar una orden al servo.
  shadow.atender(ahora, servo);

  // Paso 4: solo despues del tiempo de movimiento se estima la posicion.
  // No hay sensor fisico que confirme si la cubierta se atasco.
  const Posicion estimada = servo.estimada(ahora);
  if (estimada != cubierta) {
    cubierta = estimada;
    if (cubierta != Posicion::Desconocida) {
      Serial.printf("[SERVO] Posicion estimada tras espera ms=%lu\n", ahora);
    }
  }

  // Paso 5: informar a AWS (por cambio o como respaldo periodico).
  shadow.reportar(ahora, raw, agua, cubierta);
  delay(1);// cede CPU a Wi-Fi y MQTT
}

