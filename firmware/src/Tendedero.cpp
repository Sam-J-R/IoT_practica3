#include <Arduino.h>
#include <WiFi.h>
#include <time.h>
#include "CalibracionSensor.h"
#include "ClienteShadow.h"
#include "ConfiguracionOperacion.h"
#include "LogicaEdge.h"
#include "LuzLed.h"
#include "SensorAgua.h"
#include "SensorLuz.h"

// PROGRAMA FINAL DEL ESP32 (Practica 4)
// 1. Lee el sensor de agua cada 500 ms.
// 2. Regla R1 (Edge): en modo automatico, si detecta agua, resguarda la ropa.
//    Funciona aunque no haya Wi-Fi ni AWS.
// 3. Se conecta a AWS IoT Core usando MQTT seguro (TLS).
// 4. ClienteShadow recibe del Device Shadow: posicion (voz o nube), modo,
//    minutos_reexponer, luz y pedidos de calibracion. Antes de mover el brazo,
//    LogicaEdge decide si la orden se acepta (en automatico, exponer se rechaza
//    con agua o de noche).
// 5. Regla R5 (Edge): en modo automatico, al anochecer (LDR oscuro sostenido)
//    resguarda la ropa. Tambien sin red.
// 6. El LED es la luz para recoger la ropa: lo enciende la voz y se apaga solo
//    tras LED_APAGADO_AUTOMATICO_MS.
// 7. Publica sensores, posicion ESTIMADA, LED, modo, origen y umbrales en reported.

#if __has_include("calibracion_local.h")
#include "calibracion_local.h"
#else
#include "calibracion.example.h"
#endif

#if __has_include("luz_local.h")
#include "luz_local.h"
#else
#include "luz.example.h"
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
CalibracionSensor calibracion;
ServoTendedero servo(SERVO_EXPUESTO_US, SERVO_RESGUARDADO_US, SERVO_FRECUENCIA_HZ,
                     SERVO_ASENTAMIENTO_MS);
ClienteShadow shadow;
ConfiguracionOperacion operacion;
Origen origen = Origen::Ninguno; // Quien pidio el ultimo movimiento del brazo.
SensorLuz ldr(REFERENCIA_LUZ_CLARO, REFERENCIA_LUZ_OSCURO);
LuzLed led;
Origen origenLed = Origen::Ninguno; // Quien pidio el ultimo cambio del LED.
unsigned long ledEncendidoDesde = 0; // Para apagarlo solo pasado el tiempo maximo.
int luzRaw = 0;
int oscuro = -1; // -1 = sin LDR o sin dato; 0 = claro; 1 = oscuro.
// Solo en el perfil de ensayo: LDR simulado por comandos (ldr_oscuro,
// ldr_claro, ldr_real) para probar R5 sin el LDR conectado.
// -1 = usar el LDR real; 0 = claro; 1 = oscuro.
int luzSimulada = -1;
bool integracion = false; // Solo se activa con credenciales y calibracion validas.
bool mqttIniciado = false;
unsigned long ultimaLectura = 0;
unsigned long ultimoIntentoMqtt = 0;
int raw = 0;
int agua = -1; // -1 = no sabemos; 0 = seco; 1 = se detecta agua.
Posicion posicion = Posicion::Desconocida;

bool servoValido() {
  return SERVO_FRECUENCIA_HZ > 0 && SERVO_ASENTAMIENTO_MS > 0 &&
         SERVO_EXPUESTO_US > 0 && SERVO_RESGUARDADO_US > 0 &&
         SERVO_EXPUESTO_US != SERVO_RESGUARDADO_US &&
         static_cast<uint64_t>(SERVO_EXPUESTO_US) * SERVO_FRECUENCIA_HZ < 1000000 &&
         static_cast<uint64_t>(SERVO_RESGUARDADO_US) * SERVO_FRECUENCIA_HZ < 1000000;
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
    // Los umbrales salen de la calibracion guardada, no de constantes compiladas.
    const int umbralSeco = calibracion.umbralSeco();
    const int umbralAgua = calibracion.umbralAgua();
    const bool desdeSeco = sensor.detectar(raw, false, umbralSeco, umbralAgua);
    const bool desdeAgua = sensor.detectar(raw, true, umbralSeco, umbralAgua);
    if (agua >= 0 || desdeSeco == desdeAgua) {
      agua = agua == 1 ? desdeAgua : desdeSeco;
    }
  }
  Serial.printf("[SENSOR] ms=%lu raw=%d agua=%d\n", ahora, raw, agua);
  if (luzSimulada >= 0) {
    // Sin histeresis ni confirmacion: el cambio es inmediato.
    luzRaw = 0;
    oscuro = luzSimulada;
    Serial.printf("[LUZ] ms=%lu raw=0 nivel=%d oscuro=%d simulado\n", ahora,
                  oscuro ? 0 : 1000, oscuro);
  } else if (ldr.instalado()) {
    luzRaw = ldr.leerRaw();
    oscuro = ldr.actualizar(luzRaw, ahora);
    Serial.printf("[LUZ] ms=%lu raw=%d nivel=%ld oscuro=%d\n", ahora, luzRaw, ldr.nivel(luzRaw),
                  oscuro);
  }
}

const char* nombreOrigen(Origen quien) {
  return quien == Origen::Edge ? "edge" : (quien == Origen::Nube ? "nube" : "voz");
}

// Cambia el LED y registra quien lo pidio. Devuelve true si cambio.
bool cambiarLed(Luz luz, Origen quien, unsigned long ahora) {
  if (!LED_INSTALADO || !led.aplicar(luz)) return false;
  origenLed = quien;
  if (luz == Luz::Encendida) ledEncendidoDesde = ahora;
  Serial.printf("[LED] estado=%s origen=%s ms=%lu\n",
                luz == Luz::Encendida ? "encendido" : "apagado", nombreOrigen(quien), ahora);
  return true;
}

// Orden de voz para el LED (luz para recoger la ropa). Se cumple siempre.
void atenderOrdenLuz(Luz pedida, Origen quien, unsigned long ahora) {
  if (!LED_INSTALADO) return;
  cambiarLed(pedida, quien, ahora);
}

// Apagado automatico del LED. Escribe desired.led = apagado para que el Shadow
// no devuelva la orden de encender.
void apagarLedPorTiempo(unsigned long ahora) {
  if (!LED_INSTALADO || led.estado() != Luz::Encendida ||
      ahora - ledEncendidoDesde < LED_APAGADO_AUTOMATICO_MS) {
    return;
  }
  Serial.printf("[EDGE] LED encendido %lu min: se apaga solo ms=%lu\n",
                LED_APAGADO_AUTOMATICO_MS / 60000, ahora);
  cambiarLed(Luz::Apagada, Origen::Edge, ahora);
  shadow.publicarDecisionLuz(Luz::Apagada);
}

// Mueve el brazo y registra quien lo pidio. Devuelve true si hubo movimiento.
bool mover(Posicion destino, Origen quien, unsigned long ahora) {
  if (destino == Posicion::Desconocida || destino == servo.destino()) return false;
  servo.solicitar(destino, ahora);
  origen = quien;
  Serial.printf("[SERVO] destino=%s origen=%s ms=%lu\n",
                destino == Posicion::Expuesto ? "expuesto" : "resguardado",
                nombreOrigen(quien), ahora);
  return true;
}

// Mueve el brazo por una regla del Edge y escribe desired para que el Shadow
// no devuelva la orden anterior.
void resguardarPorRegla(Posicion decision, const char* regla, const char* motivo, unsigned long ahora) {
  if (decision == Posicion::Desconocida) return;
  Serial.printf("[EDGE] %s: %s en modo automatico, resguardando ms=%lu\n", regla, motivo, ahora);
  mover(decision, Origen::Edge, ahora);
  shadow.publicarDecisionEdge(decision);
}

// Reglas R1 (lluvia) y R5 (noche). Se evaluan tras cada lectura y no dependen de la red.
void aplicarReglasEdge(unsigned long ahora) {
  resguardarPorRegla(LogicaEdge::evaluarR1(operacion.modo(), agua, servo.destino()),
                     "R1", "agua detectada", ahora);
  resguardarPorRegla(LogicaEdge::evaluarR5(operacion.modo(), oscuro, servo.destino()),
                     "R5", "es de noche", ahora);
}

// Orden llegada por el Shadow (Alexa o Lambdas de la Nube).
void atenderOrden(Posicion pedida, Origen quien, unsigned long ahora) {
  quien = LogicaEdge::resolverOrigen(quien, origen);
  if (!LogicaEdge::aceptarOrden(operacion.modo(), agua, oscuro, pedida)) {
    // Prioridad de las reglas automaticas: la ropa no sale con lluvia ni de noche.
    Serial.printf("[EDGE] Orden de exponer rechazada: %s y el modo es automatico ms=%lu\n",
                  agua == 1 ? "hay agua" : "es de noche", ahora);
    mover(Posicion::Resguardado, Origen::Edge, ahora);
    shadow.publicarDecisionEdge(Posicion::Resguardado);
    return;
  }
  mover(pedida, quien, ahora);
}

// Atiende un pedido de calibracion llegado por el Shadow. El usuario indico
// la condicion (seco o mojado); aqui se mide el sensor y se guarda la referencia.
void calibrar(Condicion condicion, uint64_t id) {
  if (calibracion.yaAtendido(id)) return; // El mismo pedido no se repite.

  // El id es la hora del pedido en milisegundos. Si llego tarde (por ejemplo,
  // el equipo estaba apagado), no se mide: la condicion pudo haber cambiado.
  const double edadMs = static_cast<double>(time(nullptr)) * 1000.0 - static_cast<double>(id);
  if (edadMs > VIGENCIA_PEDIDO_CALIBRACION_MS) {
    calibracion.caducar(condicion, id);
    Serial.printf("[CALIBRACION] pedido caducado (%.0f s de antiguedad)\n", edadMs / 1000.0);
    return;
  }

  long suma = 0;
  for (int i = 0; i < MUESTRAS_CALIBRACION; ++i) {
    suma += sensor.leerRaw();
    delay(PAUSA_MUESTRA_CALIBRACION_MS);
  }
  const int promedio = static_cast<int>(suma / MUESTRAS_CALIBRACION);
  const bool aplicada = calibracion.aplicar(condicion, id, promedio);
  Serial.printf("[CALIBRACION] condicion=%s lectura=%d %s umbral_seco=%d umbral_agua=%d\n",
                condicion == Condicion::Seco ? "seco" : "mojado", promedio,
                aplicada ? "aplicada" : "rechazada",
                calibracion.umbralSeco(), calibracion.umbralAgua());
  if (aplicada) {
    // Con umbrales nuevos, la clasificacion anterior deja de ser valida.
    agua = -1;
    muestrear(millis());
  }
}

#ifdef MODO_ENSAYO_RNF
// Comandos de ensayo por monitor serie:
// exponer | resguardar | auto | manual | led_on | led_off | ldr_oscuro |
// ldr_claro | ldr_real | calibrar_seco | calibrar_mojado | estado | wifi_off | wifi_on.
// Las ordenes se publican en desired (como Lambda) y vuelven como delta desde
// AWS, de modo que el recorrido por la nube se conserva.
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
    if (linea == "exponer" || linea == "resguardar") {
      const bool ok = integracion &&
          shadow.solicitarDesired(linea == "exponer" ? Posicion::Expuesto : Posicion::Resguardado);
      Serial.printf("[ENSAYO] orden %s %s ms=%lu\n", linea.c_str(),
                    ok ? "publicada" : "NO publicada (sin MQTT)", ahora);
    } else if (linea == "calibrar_seco" || linea == "calibrar_mojado") {
      const bool ok = integracion &&
          shadow.solicitarCalibracion(linea == "calibrar_seco" ? Condicion::Seco : Condicion::Mojado);
      Serial.printf("[ENSAYO] pedido %s %s ms=%lu\n", linea.c_str(),
                    ok ? "publicado" : "NO publicado (sin MQTT)", ahora);
    } else if (linea == "auto" || linea == "manual") {
      const bool ok = integracion &&
          shadow.solicitarModo(linea == "auto" ? Modo::Automatico : Modo::Manual);
      Serial.printf("[ENSAYO] modo %s %s ms=%lu\n", linea.c_str(),
                    ok ? "publicado" : "NO publicado (sin MQTT)", ahora);
    } else if (linea == "led_on" || linea == "led_off") {
      const bool ok = integracion &&
          shadow.solicitarLed(linea == "led_on" ? Luz::Encendida : Luz::Apagada);
      Serial.printf("[ENSAYO] led %s %s ms=%lu\n", linea == "led_on" ? "on" : "off",
                    ok ? "publicado" : "NO publicado (sin MQTT)", ahora);
    } else if (linea == "ldr_oscuro" || linea == "ldr_claro" || linea == "ldr_real") {
      luzSimulada = linea == "ldr_oscuro" ? 1 : (linea == "ldr_claro" ? 0 : -1);
      if (luzSimulada < 0) oscuro = -1; // El LDR real vuelve a decidir desde cero.
      Serial.printf("[ENSAYO] ldr %s ms=%lu\n",
                    luzSimulada < 0 ? "real" : (luzSimulada ? "simulado oscuro" : "simulado claro"),
                    ahora);
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
  // LDR y LED: opcionales. Sin referencias del LDR o sin LED no se usan.
  ldr.iniciar();
  if (LED_INSTALADO) led.iniciar();
  // Referencias guardadas por una calibracion anterior o, si no hay, de fabrica.
  calibracion.iniciar(REFERENCIA_SECO_FABRICA, REFERENCIA_AGUA_FABRICA);
  // Modo y espera guardados: sin Internet, R1 sigue en el modo que tenia.
  operacion.iniciar();
  // Seguridad: sin parametros validos, solo se leen valores ADC.
  // No se intenta AWS ni se da una orden al servo.
  integracion = calibracion.valida() && servoValido() && credencialesConfiguradas() &&
                servo.iniciar();
  muestrear(millis());
  Serial.printf("[LUZ] ldr=%s led=%s\n", ldr.instalado() ? "instalado" : "no instalado",
                LED_INSTALADO ? "instalado" : "no instalado");
#ifdef MODO_ENSAYO_RNF
  Serial.println("[ENSAYO] Firmware de ensayo RNF: comandos exponer | resguardar | auto | "
                 "manual | led_on | led_off | ldr_oscuro | ldr_claro | ldr_real | "
                 "calibrar_seco | calibrar_mojado | estado | "
                 "wifi_off | wifi_on");
#endif
  if (!integracion) {
    Serial.println("[P4] Solo ADC. Completar calibracion y secretos locales para habilitar TLS y servo");
    return;
  }
  Serial.printf("[CALIBRACION] umbral_seco=%d umbral_agua=%d\n", calibracion.umbralSeco(),
                calibracion.umbralAgua());
  Serial.printf("[OPERACION] modo=%s minutos_reexponer=%d\n",
                operacion.modo() == Modo::Manual ? "manual" : "automatico",
                operacion.minutosReexponer());

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

  // Paso 1: actualizar las lecturas y evaluar R1 y R5 (sin depender de la red).
  if (ahora - ultimaLectura >= INTERVALO_SENSOR_MS) {
    muestrear(ahora);
    if (integracion) aplicarReglasEdge(ahora);
    apagarLedPorTiempo(ahora); // No necesita servo ni AWS.
  }

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

  // Paso 3: procesar deltas del Shadow. Pueden llegar: modo y minutos, una
  // orden de posicion (que pasa por la politica de LogicaEdge) o un pedido de
  // calibracion del sensor. El modo va primero: una orden y un cambio de modo
  // pueden llegar en el mismo delta.
  shadow.atender(ahora, servo);
  Modo modoPedido = Modo::Ninguno;
  int minutosPedidos = 0;
  if (shadow.tomarConfiguracion(modoPedido, minutosPedidos)) {
    if (operacion.aplicarModo(modoPedido)) {
      Serial.printf("[OPERACION] modo=%s ms=%lu\n",
                    operacion.modo() == Modo::Manual ? "manual" : "automatico", ahora);
      aplicarReglasEdge(ahora); // Pasar a automatico con agua o de noche resguarda de inmediato.
    }
    if (operacion.aplicarMinutos(minutosPedidos)) {
      Serial.printf("[OPERACION] minutos_reexponer=%d\n", operacion.minutosReexponer());
    }
  }
  Posicion pedida = Posicion::Desconocida;
  Origen quien = Origen::Ninguno;
  if (shadow.tomarOrden(pedida, quien)) atenderOrden(pedida, quien, ahora);
  Luz luzPedida = Luz::Desconocida;
  Origen quienLuz = Origen::Ninguno;
  if (shadow.tomarOrdenLuz(luzPedida, quienLuz)) atenderOrdenLuz(luzPedida, quienLuz, ahora);
  Condicion condicion = Condicion::Ninguna;
  uint64_t idCalibracion = 0;
  if (shadow.tomarPedidoCalibracion(condicion, idCalibracion)) {
    calibrar(condicion, idCalibracion);
  }

  // Paso 4: solo despues del tiempo de movimiento se estima la posicion.
  // No hay sensor fisico que confirme si el brazo se atasco.
  const Posicion estimada = servo.estimada(ahora);
  if (estimada != posicion) {
    posicion = estimada;
    if (posicion != Posicion::Desconocida) {
      Serial.printf("[SERVO] Posicion estimada tras espera ms=%lu\n", ahora);
    }
  }

  // Paso 5: informar a AWS (por cambio o como respaldo periodico).
  Telemetria telemetria;
  telemetria.lecturaAdc = raw;
  telemetria.agua = agua;
  telemetria.posicion = posicion;
  telemetria.modo = operacion.modo();
  telemetria.minutosReexponer = operacion.minutosReexponer();
  telemetria.origen = origen;
  telemetria.luzInstalada = ldr.instalado() || luzSimulada >= 0;
  telemetria.luzSimulada = luzSimulada >= 0;
  telemetria.luzAdc = luzRaw;
  telemetria.oscuro = oscuro;
  telemetria.led = LED_INSTALADO ? led.estado() : Luz::Desconocida;
  telemetria.origenLed = origenLed;
  shadow.reportar(ahora, telemetria, calibracion.estado());
  delay(1);
}
