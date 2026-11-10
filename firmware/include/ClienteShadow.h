#pragma once

#include <Arduino.h>
#include <mqtt_client.h>
#include "ServoCubierta.h"

// Puente entre ESP32 y AWS IoT Core.
// - Lee ordenes de "desired" (delta/get) y las entrega al servo.
// - Publica lecturas y estados en "reported".
// - Se recupera tras perder MQTT consultando el Shadow de nuevo.
class ClienteShadow {
public:
  // TLS: endpoint, nombre de Thing y certificados locales.
  bool iniciar(const char* endpoint, const char* thing, const char* ca,
               const char* certificado, const char* clave);
  // Procesa mensajes pendientes; llamar desde loop(), nunca desde interrupcion.
  void atender(unsigned long ahora, ServoCubierta& servo);
  // Modo de diagnostico: nunca envia comandos al servo.
  void atender(unsigned long ahora, ServoCubierta* servo);
  void reportar(unsigned long ahora, int raw, int agua, Posicion cubierta);
  // Reporta solo ADC, sin borrar ni confirmar la posicion de la cubierta.
  void reportarSensor(unsigned long ahora, int raw);
#ifdef MODO_ENSAYO_RNF
  // Publica desired.cubierta con el mismo formato que usa Lambda.
  bool solicitarDesired(Posicion destino);
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
  };

  static void recibir(void* contexto, esp_event_base_t, int32_t id, void* datos);
  void decodificar(const esp_mqtt_event_t& mensaje);
  void encolar(const Evento& evento);
  void procesar(const Evento& evento, unsigned long ahora, ServoCubierta* servo);
  void suscribir();
  void pedirShadow();
  void aplicar(const Evento& evento, unsigned long ahora, ServoCubierta* servo);

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
  Posicion cubiertaEnviada_ = Posicion::Desconocida;
  int aguaAceptada_ = -1;
  Posicion cubiertaAceptada_ = Posicion::Desconocida;
  bool primerReporte_ = true;
};
