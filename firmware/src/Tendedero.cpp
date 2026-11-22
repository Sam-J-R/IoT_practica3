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
constexpr unsigned long REINTENTO_RED_MS = 10000;
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

void muestrear(unsigned long ahora) {
  raw = sensor.leerRaw();
  ultimaLectura = ahora;
  if (integracion) {
    // Histeresis: un umbral para entrar en "agua" y otro para volver a "seco".
    // Evita que pequenas variaciones en el ADC cambien el estado repetidamente.
    const bool desdeSeco = sensor.detectar(raw, false, UMBRAL_SECO, UMBRAL_AGUA);
    const bool desdeAgua = sensor.detectar(raw, true, UMBRAL_SECO, UMBRAL_AGUA);
    if (agua >= 0 || desdeSeco == desdeAgua) {
      agua = agua == 1 ? desdeAgua : desdeSeco;
    }
  }
  Serial.printf("[SENSOR] ms=%lu raw=%d agua=%d\n", ahora, raw, agua);
}

#ifdef MODO_ENSAYO_RNF
// Comandos de ensayo por monitor serie: abrir | cerrar | estado | wifi_off | wifi_on.
// abrir/cerrar publican desired en el Shadow (como Lambda); la orden vuelve
// como delta desde AWS, de modo que el recorrido por la nube se conserva.
bool wifiCortado = false;   // wifi_off: corte de red con el ESP32 encendido.
bool esperandoWifi = false; // wifi_on: avisar cuando vuelva la asociacion.

void atenderConsola(unsigned long ahora) {
  static String linea;
  if (esperandoWifi && WiFi.status() == WL_CONNECTED) {
    esperandoWifi = false;
    Serial.printf("[ENSAYO] wifi conectado ip=%s ms=%lu\n", WiFi.localIP().toString().c_str(), ahora);
  }
  static bool relojListo = false;
  if (integracion && !relojListo && time(nullptr) >= RELOJ_MINIMO) {
    relojListo = true;
    Serial.printf("[ENSAYO] reloj NTP listo ms=%lu\n", ahora);
  }
  // Diagnostico: si tras el arranque no hay red, recordarlo cada 10 s.
  static unsigned long ultimoAviso = 0;
  if (integracion && !wifiCortado && WiFi.status() != WL_CONNECTED && ahora - ultimoAviso >= 10000) {
    ultimoAviso = ahora;
    Serial.printf("[ENSAYO] sin wifi estado=%d ms=%lu\n", static_cast<int>(WiFi.status()), ahora);
  }
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') continue;
    if (c != '\n') {
      if (linea.length() < 32) linea += c;
      continue;
    }
    linea.trim();
    linea.toLowerCase();
    if (linea == "abrir" || linea == "cerrar") {
      const bool ok = integracion &&
          shadow.solicitarDesired(linea == "abrir" ? Posicion::Abierta : Posicion::Cerrada);
      Serial.printf("[ENSAYO] orden %s %s ms=%lu\n", linea.c_str(),
                    ok ? "publicada" : "NO publicada (sin MQTT)", ahora);
    } else if (linea == "estado") {
      if (integracion) shadow.consultarShadow();
      Serial.printf("[ENSAYO] consulta de Shadow ms=%lu\n", ahora);
    } else if (linea == "wifi_off" && integracion) {
      WiFi.setAutoReconnect(false);
      WiFi.disconnect();
      wifiCortado = true;
      esperandoWifi = false;
      Serial.printf("[ENSAYO] wifi cortado ms=%lu\n", ahora);
    } else if (linea == "wifi_on" && integracion) {
      if (wifiCortado) {
        WiFi.setAutoReconnect(true);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        wifiCortado = false;
        esperandoWifi = true;
      }
      Serial.printf("[ENSAYO] wifi restableciendo ms=%lu\n", ahora);
    } else if (linea.length() > 0) {
      Serial.printf("[ENSAYO] comando desconocido: %s\n", linea.c_str());
    }
    linea = "";
  }
}
#endif
}

void setup() {
  Serial.begin(115200);
  sensor.iniciar();
  // Seguridad: sin parametros validos, solo se leen valores ADC.
  // No se intenta AWS ni se da una orden al servo.
  integracion = calibracionValida() && credencialesConfiguradas() && servo.iniciar();
  muestrear(millis());
#ifdef MODO_ENSAYO_RNF
  Serial.println("[ENSAYO] Firmware de ensayo RNF: comandos abrir | cerrar | estado | wifi_off | wifi_on");
#endif
  if (!integracion) {
    Serial.println("[P3] Solo ADC. Completar calibracion y secretos locales para habilitar TLS y servo");
    return;
  }

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org");
#ifdef MODO_ENSAYO_RNF
  esperandoWifi = true;
#endif
  ultimoIntentoMqtt = millis() - REINTENTO_RED_MS;
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

#ifdef MODO_ENSAYO_RNF
  atenderConsola(ahora);
#endif

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
  delay(1);
}

