// Pruebas de ClienteShadow.cpp (el archivo real del firmware) en la PC, con
// MQTT, cola y cJSON simulados (tests/firmware_host/esp). Las corre
// tests/test_firmware_host.py. Cada CHECK imprime "PASA" o "FALLA".
#include <cstdio>
#include <string>
#include "ClienteShadow.h"

static int fallas = 0, total = 0;
#define CHECK(c, msg) do { ++total; if (c) std::printf("PASA  %s\n", msg); \
  else { ++fallas; std::printf("FALLA %s\n", msg); } } while (0)

static const std::string BASE = "$aws/things/t1/shadow";
static ClienteShadow shadow;
static ServoTendedero servo(1000, 2000, 50, 1000);
static unsigned long reloj = 1000;

static void atender() { reloj += 10; shadow.atender(reloj, servo); }

static bool publicado(const std::string& tema, const std::string& fragmento) {
  for (const auto& p : __publicados) {
    if (p.tema == tema && p.datos.find(fragmento) != std::string::npos) return true;
  }
  return false;
}

static void conectar_y_sincronizar(const std::string& desired, int version) {
  __publicados.clear();
  __evento(MQTT_EVENT_CONNECTED);
  atender();
  __mensaje(BASE + "/get/accepted",
            "{\"version\":" + std::to_string(version) + ",\"state\":{\"desired\":" + desired + "}}");
  atender();
}

static void get_entrega_orden_y_configuracion() {
  shadow.iniciar("e", "t1", "ca", "c", "k");
  conectar_y_sincronizar(
      "{\"posicion\":\"expuesto\",\"origen\":\"voz\",\"modo\":\"manual\",\"minutos_reexponer\":45}", 5);
  Posicion p; Origen o; Modo m; int min = 0;
  CHECK(shadow.tomarOrden(p, o) && p == Posicion::Expuesto && o == Origen::Voz,
        "GET: entrega la orden expuesto con origen voz");
  CHECK(!shadow.tomarOrden(p, o), "la orden se entrega una sola vez");
  CHECK(shadow.tomarConfiguracion(m, min) && m == Modo::Manual && min == 45,
        "GET: entrega modo manual y 45 minutos");
  CHECK(servo.destino() == Posicion::Desconocida, "ClienteShadow ya no mueve el servo por su cuenta");
}

static void delta_sin_origen_y_solo_modo() {
  Posicion p; Origen o; Modo m; int min = 0;
  __mensaje(BASE + "/update/delta", "{\"version\":6,\"state\":{\"posicion\":\"resguardado\"}}");
  atender();
  CHECK(shadow.tomarOrden(p, o) && p == Posicion::Resguardado && o == Origen::Ninguno,
        "delta sin origen: orden con origen Ninguno (lo resuelve LogicaEdge)");
  __mensaje(BASE + "/update/delta", "{\"version\":7,\"state\":{\"modo\":\"automatico\"}}");
  atender();
  CHECK(!shadow.tomarOrden(p, o), "delta solo con modo: no hay orden de posicion");
  CHECK(shadow.tomarConfiguracion(m, min) && m == Modo::Automatico && min == 0,
        "delta solo con modo: modo automatico, minutos sin cambio");
  __mensaje(BASE + "/update/delta", "{\"version\":8,\"state\":{\"modo\":\"turbo\",\"origen\":\"hackeo\"}}");
  atender();
  CHECK(!shadow.tomarConfiguracion(m, min), "modo invalido se ignora");
}

static void decision_edge_conectado() {
  __publicados.clear();
  shadow.publicarDecisionEdge(Posicion::Resguardado);
  CHECK(publicado(BASE + "/update", "\"desired\":{\"posicion\":\"resguardado\",\"origen\":\"edge\"}"),
        "R1 conectado: escribe desired resguardado con origen edge");
}

static void decision_edge_sin_conexion() {
  __evento(MQTT_EVENT_DISCONNECTED);
  atender();
  __publicados.clear();
  shadow.publicarDecisionEdge(Posicion::Resguardado);
  CHECK(!publicado(BASE + "/update", "\"origen\":\"edge\""), "R1 sin conexion: no publica todavia");
  // Al volver, el GET trae el desired viejo (expuesto, pedido por voz).
  conectar_y_sincronizar("{\"posicion\":\"expuesto\",\"origen\":\"voz\"}", 9);
  Posicion p; Origen o;
  CHECK(!shadow.tomarOrden(p, o), "al reconectar, el desired viejo no deshace la decision del Edge");
  CHECK(publicado(BASE + "/update", "\"desired\":{\"posicion\":\"resguardado\",\"origen\":\"edge\"}"),
        "al reconectar, publica la decision pendiente del Edge");
  __publicados.clear();
  __mensaje(BASE + "/update/delta",
            "{\"version\":11,\"state\":{\"posicion\":\"expuesto\",\"origen\":\"nube\"}}");
  atender();
  CHECK(shadow.tomarOrden(p, o) && p == Posicion::Expuesto && o == Origen::Nube,
        "despues de publicarla, una orden nueva de la nube vuelve a pasar");
}

static void reporte_incluye_modo_y_origen() {
  __publicados.clear();
  Telemetria t;
  t.lecturaAdc = 1500; t.agua = 1; t.posicion = Posicion::Resguardado;
  t.modo = Modo::Automatico; t.minutosReexponer = 30; t.origen = Origen::Edge;
  EstadoCalibracion cal; cal.umbralSeco = 200; cal.umbralAgua = 600; cal.revision = 1;
  reloj += 6000;
  shadow.reportar(reloj, t, cal);
  CHECK(publicado(BASE + "/update", "\"modo\":\"automatico\",\"minutos_reexponer\":30,\"origen\":\"edge\""),
        "reported lleva modo, minutos y origen");
#ifdef MODO_ENSAYO_RNF
  CHECK(publicado(BASE + "/update", "\"ts_dispositivo\":"), "ensayo: reported lleva ts_dispositivo");
#else
  CHECK(!publicado(BASE + "/update", "ts_dispositivo"), "produccion: reported no lleva ts_dispositivo");
#endif
  CHECK(publicado(BASE + "/update", "\"umbral_seco\":200"), "reported sigue llevando la calibracion");
  // AWS acepta el reporte (token sesion-secuencia).
  std::string token;
  for (const auto& p : __publicados) {
    const auto i = p.datos.find("clientToken\":\"");
    if (i != std::string::npos) token = p.datos.substr(i + 14, p.datos.find('"', i + 14) - i - 14);
  }
  __mensaje(BASE + "/update/accepted", "{\"clientToken\":\"" + token + "\"}");
  atender();
  __publicados.clear();
  shadow.reportar(reloj, t, cal);
  CHECK(__publicados.empty(), "sin cambios no se repite el reporte antes de 60 s");
  t.modo = Modo::Manual;
  shadow.reportar(reloj, t, cal);
  CHECK(publicado(BASE + "/update", "\"modo\":\"manual\""), "un cambio de modo se reporta de inmediato");
}

static void luz_automatica() {
  Luz l; Origen o;
  conectar_y_sincronizar("{\"posicion\":\"resguardado\"}", 25);
  Posicion p0; Origen o0;
  shadow.tomarOrden(p0, o0);
  __mensaje(BASE + "/update/delta",
            "{\"version\":30,\"state\":{\"led\":\"encendido\"}}");
  atender();
  CHECK(shadow.tomarOrdenLuz(l, o) && l == Luz::Encendida && o == Origen::Voz,
        "delta led (sin origen_led): entrega orden encendido con origen voz");
  Posicion p; Origen op;
  CHECK(!shadow.tomarOrden(p, op), "un delta solo de led no genera orden de posicion");
  __publicados.clear();
  shadow.publicarDecisionEdge(Posicion::Resguardado);
  shadow.publicarDecisionLuz(Luz::Apagada);
  CHECK(publicado(BASE + "/update", "\"led\":\"apagado\",\"origen_led\":null"),
        "el apagado automatico escribe desired.led y borra el origen_led antiguo");
  // Sin conexion las dos decisiones esperan y salen juntas al reconectar.
  __evento(MQTT_EVENT_DISCONNECTED);
  atender();
  shadow.publicarDecisionEdge(Posicion::Resguardado);
  shadow.publicarDecisionLuz(Luz::Encendida);
  conectar_y_sincronizar("{\"posicion\":\"expuesto\",\"led\":\"apagado\",\"origen_led\":\"voz\"}", 40);
  CHECK(!shadow.tomarOrdenLuz(l, o), "al reconectar, el desired.led viejo no deshace R5");
  CHECK(publicado(BASE + "/update",
                  "{\"posicion\":\"resguardado\",\"origen\":\"edge\",\"led\":\"encendido\",\"origen_led\":null}"),
        "al reconectar publica juntas las decisiones pendientes");
  // Reporte con LDR y LED.
  __publicados.clear();
  Telemetria t;
  t.lecturaAdc = 100; t.agua = 0; t.posicion = Posicion::Resguardado; t.modo = Modo::Automatico;
  t.minutosReexponer = 30; t.origen = Origen::Edge;
  t.luzInstalada = true; t.luzAdc = 640; t.oscuro = 1; t.led = Luz::Encendida; t.origenLed = Origen::Edge;
  EstadoCalibracion cal; cal.umbralSeco = 200; cal.umbralAgua = 600; cal.revision = 2;
  reloj += 70000;
  shadow.reportar(reloj, t, cal);
  CHECK(publicado(BASE + "/update", "\"luz_adc\":640,\"oscuro\":true"), "reported lleva luz_adc y oscuro");
  CHECK(publicado(BASE + "/update", "\"led\":\"encendido\",\"origen_led\":\"edge\""),
        "reported lleva led y origen_led");
#ifdef MODO_ENSAYO_RNF
  CHECK(publicado(BASE + "/update", "\"luz_simulada\":null"), "ensayo: reported lleva luz_simulada");
#else
  CHECK(!publicado(BASE + "/update", "luz_simulada"), "produccion: reported no lleva luz_simulada");
#endif
  __publicados.clear();
  Telemetria sinLuz = t;
  sinLuz.luzInstalada = false; sinLuz.led = Luz::Desconocida; sinLuz.origenLed = Origen::Ninguno;
  reloj += 70000;
  shadow.reportar(reloj, sinLuz, cal);
  CHECK(!publicado(BASE + "/update", "luz_adc") && !publicado(BASE + "/update", "\"led\""),
        "sin LDR ni LED no se reportan sus campos");
}

static void calibracion_incompleta_sigue_pidiendo_get() {
  __publicados.clear();
  __mensaje(BASE + "/update/delta", "{\"version\":20,\"state\":{\"calibracion_solicitada\":{\"id\":3000}}}");
  atender();
  CHECK(publicado(BASE + "/get", ""), "pedido de calibracion sin condicion pide el Shadow (defecto 1)");
}

int main() {
  get_entrega_orden_y_configuracion();
  delta_sin_origen_y_solo_modo();
  decision_edge_conectado();
  decision_edge_sin_conexion();
  reporte_incluye_modo_y_origen();
  calibracion_incompleta_sigue_pidiendo_get();
  luz_automatica();
  std::printf("%d/%d pasan\n", total - fallas, total);
  return fallas ? 1 : 0;
}
