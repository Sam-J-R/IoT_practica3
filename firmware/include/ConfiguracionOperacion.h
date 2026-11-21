#pragma once

#include <Preferences.h>
#include "TiposTendedero.h"
#include "config.h"

// Modo de operacion y parametros de la logica automatica (RF14).
// Se guardan en la memoria no volatil: si el ESP32 se reinicia sin Internet,
// sigue en el mismo modo y R1 sigue protegiendo la ropa.
class ConfiguracionOperacion {
public:
  void iniciar() {
    memoria_.begin("operacion", false);
    const uint8_t guardado = memoria_.getUChar("modo", static_cast<uint8_t>(MODO_INICIAL));
    modo_ = guardado == static_cast<uint8_t>(Modo::Manual) ? Modo::Manual : Modo::Automatico;
    const int minutos = memoria_.getInt("espera", MINUTOS_REEXPONER_INICIAL);
    minutos_ = minutosValidos(minutos) ? minutos : MINUTOS_REEXPONER_INICIAL;
  }

  Modo modo() const { return modo_; }
  int minutosReexponer() const { return minutos_; }

  // Devuelve true si el modo cambio. Ninguno se ignora (el mensaje no traia modo).
  bool aplicarModo(Modo modo) {
    if (modo == Modo::Ninguno || modo == modo_) return false;
    modo_ = modo;
    memoria_.putUChar("modo", static_cast<uint8_t>(modo_));
    return true;
  }

  // minutos_reexponer lo usa la regla R2 en la Nube; el ESP32 solo lo guarda
  // y lo confirma en reported. 0 = el mensaje no lo traia.
  bool aplicarMinutos(int minutos) {
    if (!minutosValidos(minutos) || minutos == minutos_) return false;
    minutos_ = minutos;
    memoria_.putInt("espera", minutos_);
    return true;
  }

  static bool minutosValidos(int minutos) {
    return minutos >= MINUTOS_REEXPONER_MIN && minutos <= MINUTOS_REEXPONER_MAX;
  }

private:
  Preferences memoria_;
  Modo modo_ = Modo::Automatico;
  int minutos_ = MINUTOS_REEXPONER_INICIAL;
};
