#pragma once

#include <Arduino.h>
#include <Preferences.h>
#include "config.h"

// Condicion fisica en la que el usuario pide medir el sensor.
enum class Condicion : uint8_t { Ninguna, Seco, Mojado };
// Fabrica: nunca se calibro a pedido. Los demas describen el ultimo pedido:
// Rechazada = referencias demasiado cercanas; Caducada = llego tarde.
enum class ResultadoCalibracion : uint8_t { Fabrica, Aplicada, Rechazada, Caducada };

// Lo que se publica en reported: umbrales vigentes y ultimo pedido atendido.
// "revision" cambia cada vez que hay algo nuevo que reportar.
struct EstadoCalibracion {
  int umbralSeco = 0;
  int umbralAgua = 0;
  Condicion condicion = Condicion::Ninguna;
  uint64_t id = 0;
  ResultadoCalibracion resultado = ResultadoCalibracion::Fabrica;
  uint32_t revision = 0;
};

// Guarda las referencias (lectura en seco y lectura con agua) en la memoria
// no volatil del ESP32 y calcula los umbrales. Asi no hay que recompilar ni
// cargar el programa cuando cambian las condiciones ambientales.
class CalibracionSensor {
public:
  // Carga lo guardado; si no hay nada, usa las referencias de fabrica.
  // Las referencias de fabrica fijan el sentido del sensor: si la lectura
  // sube o baja al mojarse. Ninguna calibracion puede invertirlo.
  void iniciar(int secoFabrica, int aguaFabrica) {
    sube_ = aguaFabrica >= secoFabrica;
    memoria_.begin("calibracion", false);
    seco_ = memoria_.getInt("seco", secoFabrica);
    agua_ = memoria_.getInt("agua", aguaFabrica);
    if (!referenciasValidas(seco_, agua_) && referenciasValidas(secoFabrica, aguaFabrica)) {
      // Referencias guardadas incoherentes (p. ej. invertidas por una version
      // anterior del firmware): se vuelve a las de fabrica.
      seco_ = secoFabrica;
      agua_ = aguaFabrica;
      memoria_.putInt("seco", seco_);
      memoria_.putInt("agua", agua_);
    }
    id_ = memoria_.getULong64("id", 0);
    condicion_ = static_cast<Condicion>(memoria_.getUChar("condicion", 0));
    resultado_ = static_cast<ResultadoCalibracion>(memoria_.getUChar("resultado", 0));
  }

  bool valida() const { return referenciasValidas(seco_, agua_); }

  // Un pedido ya atendido no se repite: el id sobrevive a los reinicios.
  bool yaAtendido(uint64_t id) const { return id == id_; }

  // Umbral = seco + porcentaje del recorrido hacia agua. Funciona tambien
  // con sensores cuya lectura baja al mojarse (recorrido negativo).
  int umbralSeco() const { return seco_ + (agua_ - seco_) * PORCENTAJE_UMBRAL_SECO / 100; }
  int umbralAgua() const { return seco_ + (agua_ - seco_) * PORCENTAJE_UMBRAL_AGUA / 100; }

  // Reemplaza solo la referencia pedida y conserva la otra. Si las dos
  // quedan demasiado cerca o en el sentido contrario al de fabrica (por
  // ejemplo, "seco" medido con el sensor mojado), se rechaza y siguen los
  // valores anteriores.
  bool aplicar(Condicion condicion, uint64_t id, int lectura) {
    const int seco = condicion == Condicion::Seco ? lectura : seco_;
    const int agua = condicion == Condicion::Mojado ? lectura : agua_;
    const bool aceptada = condicion != Condicion::Ninguna && referenciasValidas(seco, agua);
    if (aceptada) {
      seco_ = seco;
      agua_ = agua;
      memoria_.putInt("seco", seco_);
      memoria_.putInt("agua", agua_);
    }
    registrar(condicion, id,
              aceptada ? ResultadoCalibracion::Aplicada : ResultadoCalibracion::Rechazada);
    return aceptada;
  }

  // Marca como atendido un pedido que llego demasiado tarde, sin medir.
  void caducar(Condicion condicion, uint64_t id) {
    registrar(condicion, id, ResultadoCalibracion::Caducada);
  }

  EstadoCalibracion estado() const {
    EstadoCalibracion e;
    e.umbralSeco = umbralSeco();
    e.umbralAgua = umbralAgua();
    e.condicion = condicion_;
    e.id = id_;
    e.resultado = resultado_;
    e.revision = revision_;
    return e;
  }

private:
  void registrar(Condicion condicion, uint64_t id, ResultadoCalibracion resultado) {
    id_ = id;
    condicion_ = condicion;
    resultado_ = resultado;
    memoria_.putULong64("id", id_);
    memoria_.putUChar("condicion", static_cast<uint8_t>(condicion_));
    memoria_.putUChar("resultado", static_cast<uint8_t>(resultado_));
    ++revision_;
  }

  bool referenciasValidas(int seco, int agua) const {
    const int recorrido = sube_ ? agua - seco : seco - agua;
    return seco >= 0 && seco <= 4095 && agua >= 0 && agua <= 4095 &&
           recorrido >= SEPARACION_MINIMA_REFERENCIAS;
  }

  Preferences memoria_;
  bool sube_ = true;  // true: la lectura sube al mojarse (sensor MH en GPIO34).
  int seco_ = -1;
  int agua_ = -1;
  uint64_t id_ = 0;
  Condicion condicion_ = Condicion::Ninguna;
  ResultadoCalibracion resultado_ = ResultadoCalibracion::Fabrica;
  uint32_t revision_ = 1;
};
