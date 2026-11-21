// Pruebas de la logica de calibracion e histeresis del firmware, compiladas en la PC.
// Las corre tests/test_firmware_host.py. Cada CHECK imprime "PASA" o "FALLA".
#include <cstdio>
#include "CalibracionSensor.h"
#include "SensorAgua.h"

static int fallas = 0, total = 0;
#define CHECK(c, msg) do { ++total; if (c) std::printf("PASA  %s\n", msg); \
  else { ++fallas; std::printf("FALLA %s\n", msg); } } while (0)

static void fabrica() {
  __nvs.clear();
  CalibracionSensor c; c.iniciar(0, 2000);
  CHECK(c.valida(), "referencias de fabrica 0/2000 son validas");
  CHECK(c.umbralSeco() == 200 && c.umbralAgua() == 600, "umbrales de fabrica 200/600 (CONTRATO.md)");
  CHECK(c.estado().resultado == ResultadoCalibracion::Fabrica, "estado inicial = fabrica");
}

static void plantilla_deshabilita() {
  __nvs.clear();
  CalibracionSensor c; c.iniciar(-1, -1);
  CHECK(!c.valida(), "plantilla -1/-1 deshabilita la integracion");
}

static void calibrar_mojado_y_reiniciar() {
  __nvs.clear();
  CalibracionSensor c; c.iniciar(0, 2000);
  const bool ok = c.aplicar(Condicion::Mojado, 111, 2400);
  CHECK(ok && c.umbralSeco() == 240 && c.umbralAgua() == 720, "calibrar mojado 2400 -> 240/720 y conserva seco");
  CHECK(c.yaAtendido(111), "el id atendido queda registrado");
  CalibracionSensor r; r.iniciar(0, 2000);  // reinicio: lee la NVS
  CHECK(r.umbralAgua() == 720 && r.yaAtendido(111), "tras reiniciar conserva referencias e id");
}

static void rechazo_por_cercania() {
  __nvs.clear();
  CalibracionSensor c; c.iniciar(0, 2000);
  const bool ok = c.aplicar(Condicion::Seco, 5, 1800);
  CHECK(!ok && c.umbralSeco() == 200 && c.estado().resultado == ResultadoCalibracion::Rechazada,
        "seco medido casi mojado (1800 vs 2000) -> rechazada, conserva umbrales");
}

static void caducada() {
  __nvs.clear();
  CalibracionSensor c; c.iniciar(0, 2000);
  c.caducar(Condicion::Seco, 9);
  CHECK(c.estado().resultado == ResultadoCalibracion::Caducada && c.umbralSeco() == 200,
        "caducada no cambia los umbrales");
}

// Defecto 2 de la revision: una calibracion no debe invertir el sentido del sensor.
static void no_invierte_el_sentido() {
  __nvs.clear();
  CalibracionSensor c; c.iniciar(0, 2000);
  const bool ok = c.aplicar(Condicion::Seco, 7, 2600);  // "seco" con el sensor empapado
  CHECK(!ok, "DEFECTO 2: seco medido por encima de la referencia de agua (2600 > 2000) se rechaza");
  SensorAgua s;
  CHECK(!s.detectar(0, false, c.umbralSeco(), c.umbralAgua()),
        "DEFECTO 2: tras esa calibracion, el sensor seco (raw=0) sigue sin detectar agua");
}

// Defecto 2, sensor de lectura descendente: el sentido lo fijan las referencias de fabrica.
static void sentido_descendente() {
  __nvs.clear();
  CalibracionSensor c; c.iniciar(3000, 1000);
  CHECK(c.valida(), "sensor descendente 3000/1000 es valido");
  CHECK(c.aplicar(Condicion::Mojado, 21, 800), "descendente: calibrar mojado 800 se aplica");
  CHECK(!c.aplicar(Condicion::Seco, 22, 300), "descendente: seco medido mojado (300 < 800) se rechaza");
}

// Defecto 2, memoria con referencias ya invertidas por el firmware anterior.
static void nvs_invertida_vuelve_a_fabrica() {
  __nvs.clear();
  { CalibracionSensor c; c.iniciar(0, 2000); }
  __nvs["seco"] = 2600; __nvs["agua"] = 2000;  // lo que dejaba el defecto 2
  CalibracionSensor r; r.iniciar(0, 2000);
  CHECK(r.valida() && r.umbralSeco() == 200 && r.umbralAgua() == 600,
        "DEFECTO 2: referencias invertidas guardadas -> vuelve a las de fabrica al arrancar");
}

static void histeresis() {
  SensorAgua s;
  CHECK(!s.detectar(599, false, 200, 600) && s.detectar(600, false, 200, 600), "pasa a agua desde 600");
  CHECK(s.detectar(201, true, 200, 600) && !s.detectar(200, true, 200, 600), "vuelve a seco solo en <= 200");
  CHECK(!s.detectar(400, false, 200, 600) && s.detectar(400, true, 200, 600), "en la banda conserva el estado");
  CHECK(s.detectar(100, false, 1800, 1400) && !s.detectar(1900, false, 1800, 1400),
        "sensor de lectura descendente (seco alto, agua bajo)");
}

int main() {
  fabrica();
  plantilla_deshabilita();
  calibrar_mojado_y_reiniciar();
  rechazo_por_cercania();
  caducada();
  no_invierte_el_sentido();
  sentido_descendente();
  nvs_invertida_vuelve_a_fabrica();
  histeresis();
  std::printf("\n%d/%d pasan\n", total - fallas, total);
  return fallas ? 1 : 0;
}
