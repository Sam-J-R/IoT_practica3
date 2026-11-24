// Pruebas de la logica del Edge (R1, R5, convivencia con la voz) y de la
// persistencia del modo. Las corre tests/test_firmware_host.py.
#include <cstdio>
#include "ConfiguracionOperacion.h"
#include "LogicaEdge.h"
#include "LuzLed.h"
#include "SensorLuz.h"

static int fallas = 0, total = 0;
#define CHECK(c, msg) do { ++total; if (c) std::printf("PASA  %s\n", msg); \
  else { ++fallas; std::printf("FALLA %s\n", msg); } } while (0)

static void r1() {
  using L = LogicaEdge;
  CHECK(L::evaluarR1(Modo::Automatico, 1, Posicion::Expuesto) == Posicion::Resguardado,
        "R1: automatico + agua + expuesto -> resguardar");
  CHECK(L::evaluarR1(Modo::Automatico, 1, Posicion::Desconocida) == Posicion::Resguardado,
        "R1: al arrancar con agua (posicion desconocida) -> resguardar");
  CHECK(L::evaluarR1(Modo::Automatico, 1, Posicion::Resguardado) == Posicion::Desconocida,
        "R1: ya resguardado -> no repite la orden");
  CHECK(L::evaluarR1(Modo::Manual, 1, Posicion::Expuesto) == Posicion::Desconocida,
        "R1: en manual no actua");
  CHECK(L::evaluarR1(Modo::Automatico, 0, Posicion::Expuesto) == Posicion::Desconocida,
        "R1: seco -> no actua");
  CHECK(L::evaluarR1(Modo::Automatico, -1, Posicion::Expuesto) == Posicion::Desconocida,
        "R1: sin dato del sensor -> no actua");
}

static void voz_frente_a_automatico() {
  using L = LogicaEdge;
  CHECK(!L::aceptarOrden(Modo::Automatico, 1, 0, Posicion::Expuesto),
        "exponer con agua en automatico se rechaza");
  CHECK(!L::aceptarOrden(Modo::Automatico, 0, 1, Posicion::Expuesto),
        "exponer de noche en automatico se rechaza");
  CHECK(L::aceptarOrden(Modo::Automatico, 1, 1, Posicion::Resguardado), "resguardar se acepta siempre");
  CHECK(L::aceptarOrden(Modo::Manual, 1, 1, Posicion::Expuesto), "en manual la voz manda");
  CHECK(L::aceptarOrden(Modo::Automatico, 0, 0, Posicion::Expuesto), "exponer de dia y sin agua se acepta");
  CHECK(L::aceptarOrden(Modo::Automatico, 0, -1, Posicion::Expuesto), "sin LDR, la noche no bloquea exponer");
  CHECK(L::resolverOrigen(Origen::Nube, Origen::Voz) == Origen::Nube, "origen del delta se respeta");
  CHECK(L::resolverOrigen(Origen::Ninguno, Origen::Nube) == Origen::Nube,
        "delta sin origen = el ultimo reportado");
  CHECK(L::resolverOrigen(Origen::Ninguno, Origen::Ninguno) == Origen::Voz,
        "sin origen previo se asume voz (Lambda de la P3)");
}

static void persistencia() {
  __nvs.clear();
  ConfiguracionOperacion c; c.iniciar();
  CHECK(c.modo() == MODO_INICIAL && c.minutosReexponer() == MINUTOS_REEXPONER_INICIAL,
        "sin nada guardado usa los valores de config.h");
  CHECK(c.aplicarModo(Modo::Manual) && !c.aplicarModo(Modo::Manual), "cambiar modo informa solo si cambia");
  CHECK(!c.aplicarModo(Modo::Ninguno) && c.modo() == Modo::Manual, "Ninguno no cambia el modo");
  CHECK(c.aplicarMinutos(45) && c.minutosReexponer() == 45, "minutos validos se aplican");
  CHECK(!c.aplicarMinutos(300) && !c.aplicarMinutos(0) && !c.aplicarMinutos(10) && c.minutosReexponer() == 45,
        "minutos fuera de 15..240 se ignoran");
  ConfiguracionOperacion r; r.iniciar(); // reinicio: lee la NVS
  CHECK(r.modo() == Modo::Manual && r.minutosReexponer() == 45, "tras reiniciar conserva modo y minutos");
  __nvs["espera"] = 9999;
  ConfiguracionOperacion x; x.iniciar();
  CHECK(x.minutosReexponer() == MINUTOS_REEXPONER_INICIAL, "minutos corruptos en NVS vuelven al inicial");
}

static void r5() {
  using L = LogicaEdge;
  CHECK(L::evaluarR5(Modo::Automatico, 1, Posicion::Expuesto) == Posicion::Resguardado,
        "R5: de noche en automatico -> resguardar");
  CHECK(L::evaluarR5(Modo::Automatico, 1, Posicion::Resguardado) == Posicion::Desconocida,
        "R5: ya resguardado -> no repite la orden");
  CHECK(L::evaluarR5(Modo::Automatico, 0, Posicion::Expuesto) == Posicion::Desconocida, "R5: de dia no actua");
  CHECK(L::evaluarR5(Modo::Manual, 1, Posicion::Expuesto) == Posicion::Desconocida, "R5: en manual no actua");
  CHECK(L::evaluarR5(Modo::Automatico, -1, Posicion::Expuesto) == Posicion::Desconocida, "R5: sin LDR no actua");
}

static void sensor_luz() {
  SensorLuz sin(-1, -1);
  CHECK(!sin.instalado() && sin.actualizar(100, 0) == -1, "LDR sin referencias: no instalado, sin dato");
  CHECK(sin.nivel(100) == 0, "LDR sin referencias: nivel 0, sin dividir por cero");
  CHECK(!SensorLuz(1000, 1100).instalado(), "referencias demasiado cercanas se rechazan");
  // Divisor que SUBE con la luz: claro 3000, oscuro 500 (nivel 0..1000).
  SensorLuz s(3000, 500);
  CHECK(s.instalado(), "referencias validas: instalado");
  CHECK(s.actualizar(2900, 0) == 0, "primera lectura con luz: claro de inmediato");
  CHECK(s.actualizar(600, 100) == 0, "oscuridad breve: todavia claro (confirmacion)");
  CHECK(s.actualizar(2900, 1500) == 0 && s.actualizar(600, 2000) == 0,
        "una sombra que pasa reinicia la confirmacion");
  CHECK(s.actualizar(600, 2000 + LUZ_CONFIRMACION_MS - 1) == 0, "oscuridad de casi 5 min: todavia de dia");
  CHECK(s.actualizar(600, 2000 + LUZ_CONFIRMACION_MS) == 1, "oscuro sostenido 5 min: noche");
  // Zona de histeresis (nivel 500): se mantiene oscuro.
  const unsigned long t = 2000 + LUZ_CONFIRMACION_MS;
  CHECK(s.actualizar(1750, t + 1000) == 1 && s.actualizar(1750, t + 20000) == 1,
        "nivel intermedio no cambia el estado");
  s.actualizar(2800, t + 30000);
  CHECK(s.actualizar(2800, t + 30000 + LUZ_CONFIRMACION_MS) == 0, "vuelve la luz sostenida: dia");
  // Divisor que BAJA con la luz (LDR del lado de GND invertido): claro 400, oscuro 3500.
  SensorLuz inv(400, 3500);
  CHECK(inv.actualizar(3400, 0) == 1, "sentido inverso: lectura alta = oscuro");
  CHECK(inv.nivel(400) == 1000 && inv.nivel(3500) == 0, "el nivel se normaliza en ambos sentidos");
}

static void led() {
  LuzLed l;
  CHECK(l.estado() == Luz::Desconocida, "LED sin iniciar: estado desconocido");
  l.iniciar();
  CHECK(l.estado() == Luz::Apagada && __led == LOW, "al iniciar el LED queda apagado");
  CHECK(l.aplicar(Luz::Encendida) && __led == HIGH, "encender escribe HIGH");
  CHECK(!l.aplicar(Luz::Encendida), "repetir el mismo estado no cuenta como cambio");
  CHECK(!l.aplicar(Luz::Desconocida) && l.estado() == Luz::Encendida, "Desconocida no cambia el LED");
}

int main() {
  r5();
  sensor_luz();
  led();
  r1();
  voz_frente_a_automatico();
  persistencia();
  std::printf("%d/%d pasan\n", total - fallas, total);
  return fallas ? 1 : 0;
}
