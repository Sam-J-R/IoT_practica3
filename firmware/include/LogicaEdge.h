#pragma once

#include "TiposTendedero.h"

// Logica de control que corre en el ESP32 (Edge). Es una clase sin hardware:
// recibe el estado y devuelve la decision, asi se prueba en la PC.
//
// R1 (Edge): en modo automatico, si el sensor detecta agua y el brazo no esta
// resguardado, resguardar. Va en el Edge porque es urgente, solo depende del
// sensor local y debe seguir funcionando sin Internet.
//
// R5 (Edge): en modo automatico, el LED se enciende cuando el LDR indica
// oscuridad y se apaga cuando vuelve la luz. Va en el Edge por la misma razon
// que R1: respuesta inmediata con datos locales y sin depender de la red.
//
// Convivencia con la voz: en automatico y con agua detectada, una orden de
// exponer se rechaza (el ESP32 vuelve a escribir desired = resguardado).
// Resguardar se acepta siempre. En manual se acepta cualquier orden.
// Para el LED: en automatico con el LDR funcionando, la luz la decide el
// sensor y la orden de voz se rechaza; en manual, o sin LDR, manda la voz.
class LogicaEdge {
public:
  // agua: -1 = sin dato, 0 = seco, 1 = agua. destino: ultima posicion ordenada al servo.
  // Devuelve Resguardado si R1 debe actuar; Desconocida si no hay nada que hacer.
  static Posicion evaluarR1(Modo modo, int agua, Posicion destino) {
    if (modo == Modo::Automatico && agua == 1 && destino != Posicion::Resguardado) {
      return Posicion::Resguardado;
    }
    return Posicion::Desconocida;
  }

  // oscuro: -1 sin dato (o sin LDR), 0 claro, 1 oscuro. actual: estado del LED.
  // Devuelve el estado que R5 ordena, o Desconocida si no hay nada que hacer.
  static Luz evaluarR5(Modo modo, int oscuro, Luz actual) {
    if (modo != Modo::Automatico || oscuro < 0) return Luz::Desconocida;
    const Luz deseada = oscuro == 1 ? Luz::Encendida : Luz::Apagada;
    return deseada == actual ? Luz::Desconocida : deseada;
  }

  static bool aceptarOrdenLuz(Modo modo, int oscuro) {
    return !(modo == Modo::Automatico && oscuro >= 0);
  }

  // true si una orden llegada por el Shadow (voz o nube) puede ejecutarse.
  static bool aceptarOrden(Modo modo, int agua, Posicion pedida) {
    return !(modo == Modo::Automatico && agua == 1 && pedida == Posicion::Expuesto);
  }

  // Un delta no trae "origen" cuando desired.origen es igual a reported.origen
  // (AWS omite lo que no cambio). En ese caso el origen es el ultimo reportado.
  static Origen resolverOrigen(Origen recibido, Origen ultimoReportado) {
    if (recibido != Origen::Ninguno) return recibido;
    return ultimoReportado != Origen::Ninguno ? ultimoReportado : Origen::Voz;
  }
};
