#pragma once

#include <Arduino.h>
#include <mqtt_client.h>
#include "CalibracionSensor.h"
#include "ServoTendedero.h"

// Lectura y estado que se publican en cada reporte.
struct Telemetria {
  int lecturaAdc = 0;
  int agua = -1; // -1 = no sabemos; 0 = seco; 1 = se detecta agua.
  Posicion posicion = Posicion::Desconocida;
};

// Puente entre ESP32 y AWS IoT Core.
// - Lee ordenes de "desired" (delta/get): posicion del tendedero y pedidos
//   de calibracion del sensor.
// - Publica lecturas, posicion y calibracion en "reported".
// - Se recupera tras perder MQTT consultando el Shadow de nuevo.
class ClienteShadow {
public:
  // TLS: endpoint, nombre de Thing y certificados locales.
  bool iniciar(const char* endpoint, const char* thing, const char* ca,
               const char* certificado, const char* clave);
  // Procesa mensajes pendientes; llamar desde loop(), nunca desde interrupcion.
  void atender(unsigned long ahora, ServoTendedero& servo);
  // Modo de diagnostico: nunca envia comandos al servo ni calibra.
  void atender(unsigned long ahora, ServoTendedero* servo);
  // Devuelve true una sola vez por cada pedido de calibracion recibido.
  bool tomarPedidoCalibracion(Condicion& condicion, uint64_t& id);
  // La calibracion solo viaja al conectar y cuando cambia su revision.
  void reportar(unsigned long ahora, const Telemetria& telemetria,
                const EstadoCalibracion& calibracion);
  // Reporta solo ADC, sin borrar ni confirmar la posicion del tendedero.
  void reportarSensor(unsigned long ahora, int lecturaAdc);
#ifdef MODO_ENSAYO_RNF
  // Publica desired.posicion con el mismo formato que usa Lambda.
  bool solicitarDesired(Posicion destino);
  // Publica desired.calibracion_solicitada con el mismo formato que Lambda.
  bool solicitarCalibracion(Condicion condicion);
  // Pide el documento completo; la respuesta se imprime en el monitor serie.
  void consultarShadow();
#endif

private:
  // Eventos internos para no mover el servo dentro del callback MQTT.
  enum class Tipo { Conectado, Desconectado, Delta, Get, SinShadow, ErrorGet,
                    ReporteAceptado, ReporteRechazado };
  struct Evento {
    Tipo tipo;
    Posicion posicion = Posicion::Desconocida;
    uint32_t version = 0;
    uint32_t reporte = 0;
    int codigo = 0;
    Condicion condicion = Condicion::Ninguna;
    uint64_t idCalibracion = 0;
  };

  static void recibir(void* contexto, esp_event_base_t, int32_t id, void* datos);
  void decodificar(const esp_mqtt_event_t& mensaje);
  void encolar(const Evento& evento);
  void procesar(const Evento& evento, unsigned long ahora, ServoTendedero* servo);
  void suscribir();
  void pedirShadow();
  void aplicar(const Evento& evento, unsigned long ahora, ServoTendedero* servo);

  esp_mqtt_client_handle_t cliente_ = nullptr;
  QueueHandle_t cola_ = nullptr;
  String get_, getAceptado_, getRechazado_;
  String update_, delta_, updateAceptado_, updateRechazado_;
  bool conectado_ = false;
  bool sincronizado_ = false;
  Evento deltaPendiente_{Tipo::Delta};
  uint32_t version_ = 0;
  uint32_t sesion_ = 0;
  uint32_t secuencia_ = 0;
  // El token "sesion-secuencia" identifica que reporte acepto AWS.
  uint32_t reportePendiente_ = 0;
  unsigned long ultimoGet_ = 0;
  unsigned long ultimoEnvio_ = 0;
  unsigned long ultimoAceptado_ = 0;
  int aguaEnviada_ = -1;
  Posicion posicionEnviada_ = Posicion::Desconocida;
  int aguaAceptada_ = -1;
  Posicion posicionAceptada_ = Posicion::Desconocida;
  // Revision 0 = AWS todavia no acepto ninguna calibracion en esta conexion.
  uint32_t calibracionEnviada_ = 0;
  uint32_t calibracionAceptada_ = 0;
  bool primerReporte_ = true;
  // Pedido de calibracion recibido y aun no entregado al programa principal.
  bool hayPedido_ = false;
  Condicion condicionPedida_ = Condicion::Ninguna;
  uint64_t idPedido_ = 0;
};
