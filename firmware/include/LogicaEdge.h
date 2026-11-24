#pragma once

#include "TiposTendedero.h"

// Logica de control que corre en el ESP32 (Edge). Es una clase sin hardware:
// recibe el estado y devuelve la decision, asi se prueba en la PC.
//
// R1 (Edge): en modo automatico, si el sensor detecta agua y el brazo no esta
// resguardado, resguardar. Va en el Edge porque es urgente, solo depende del
// sensor local y debe seguir funcionando sin Internet.
//
// R5 (Edge): en modo automatico, si el LDR indica que es de noche y el brazo no
// esta resguardado, resguardar. De noche la humedad (sereno, rocio) vuelve a
// mojar la ropa. Va en el Edge por la misma razon que R1. La Nube (R2) vuelve a
// exponer la ropa cuando hay luz y no llueve.
//
// Convivencia con la voz: en automatico, una orden de exponer se rechaza si hay
// agua o es de noche (el ESP32 vuelve a escribir desired = resguardado), porque
// R1 o R5 la deshacerian. Resguardar se acepta siempre. En manual se acepta
// cualquier orden. El LED no tiene regla automatica: solo lo controla la voz.
class LogicaEdge {
public:
  // agua: -1 = sin dato, 0 = seco, 1 = agua. destino: ultima posicion ordenada al servo.
  // Devuelve Resguardado si R1 debe actuar; Desconocida si no hay nada que hacer.
  static Posicion evaluarR1(Modo modo, int agua, Posicion destino) {
    return resguardarSi(modo, agua == 1, destino);
  }

  // oscuro: -1 = sin LDR o sin dato, 0 = de dia, 1 = de noche.
  static Posicion evaluarR5(Modo modo, int oscuro, Posicion destino) {
    return resguardarSi(modo, oscuro == 1, destino);
  }

  // true si una orden llegada por el Shadow (voz o nube) puede ejecutarse.
  static bool aceptarOrden(Modo modo, int agua, int oscuro, Posicion pedida) {
    return !(modo == Modo::Automatico && pedida == Posicion::Expuesto && (agua == 1 || oscuro == 1));
  }

  // Un delta no trae "origen" cuando desired.origen es igual a reported.origen
  // (AWS omite lo que no cambio). En ese caso el origen es el ultimo reportado.
  static Origen resolverOrigen(Origen recibido, Origen ultimoReportado) {
    if (recibido != Origen::Ninguno) return recibido;
    return ultimoReportado != Origen::Ninguno ? ultimoReportado : Origen::Voz;
  }

private:
  static Posicion resguardarSi(Modo modo, bool condicion, Posicion destino) {
    if (modo == Modo::Automatico && condicion && destino != Posicion::Resguardado) {
      return Posicion::Resguardado;
    }
    return Posicion::Desconocida;
  }
};
