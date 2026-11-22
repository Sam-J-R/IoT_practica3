#pragma once

#include <Arduino.h>
#include <mqtt_client.h>
#include "CalibracionSensor.h"
#include "ServoTendedero.h"
#include "TiposTendedero.h"

// Lectura y estado que se publican en cada reporte.
struct Telemetria {
  int lecturaAdc = 0;
  int agua = -1; // -1 = no sabemos; 0 = seco; 1 = se detecta agua.
  Posicion posicion = Posicion::Desconocida;
  Modo modo = Modo::Ninguno;   // Ninguno = no se reporta (perfiles de diagnostico).
  int minutosReexponer = 0;    // 0 = no se reporta.
  Origen origen = Origen::Ninguno; // Quien pidio el ultimo movimiento.
  // Luz automatica (P4). Sin LDR no se reportan luz_adc ni oscuro;
  // sin LED (Desconocida) no se reportan led ni origen_led.
  bool luzInstalada = false;
  bool luzSimulada = false; // Ensayo sin LDR: se marca para no mezclarlo con datos reales.
  int luzAdc = 0;
  int oscuro = -1; // -1 sin dato, 0 claro, 1 oscuro.
  Luz led = Luz::Desconocida;
  Origen origenLed = Origen::Ninguno;
};

// Puente entre ESP32 y AWS IoT Core.
// - Lee ordenes de "desired" (delta/get): posicion del tendedero, modo,
//   minutos_reexponer y pedidos de calibracion del sensor.
// - NO mueve el servo: entrega cada orden al programa principal, que decide
//   con LogicaEdge si la ejecuta (convivencia voz / logica automatica).
// - Publica lecturas, posicion, modo, origen y calibracion en "reported".
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
  // Devuelve true una sola vez por cada orden de posicion recibida.
  // origen = Ninguno si el delta no lo traia (ver LogicaEdge::resolverOrigen).
  bool tomarOrden(Posicion& posicion, Origen& origen);
  // Devuelve true una sola vez por cada cambio de modo o de minutos recibido.
  // modo = Ninguno o minutos = 0 cuando el mensaje no traia ese campo.
  bool tomarConfiguracion(Modo& modo, int& minutos);
  // El ESP32 decidio por su cuenta (R1 o rechazo de una orden): escribe
  // desired.posicion con origen "edge" para que el Shadow no genere un delta
  // que deshaga la decision. Sin conexion queda pendiente y se publica al
  // sincronizar, antes de aplicar el desired antiguo que traiga el GET.
  void publicarDecisionEdge(Posicion posicion);
  // Igual que tomarOrden, para desired.led / desired.origen_led.
  bool tomarOrdenLuz(Luz& luz, Origen& origen);
  // Igual que publicarDecisionEdge, para el LED (apagado automatico por tiempo).
  void publicarDecisionLuz(Luz luz);
  // La calibracion solo viaja al conectar y cuando cambia su revision.
  void reportar(unsigned long ahora, const Telemetria& telemetria,
                const EstadoCalibracion& calibracion);
  // Reporta solo ADC, sin borrar ni confirmar la posicion del tendedero.
  void reportarSensor(unsigned long ahora, int lecturaAdc);
#ifdef MODO_ENSAYO_RNF
  // Publica desired.posicion con el mismo formato que usa Lambda (origen voz).
  bool solicitarDesired(Posicion destino);
  // Publica desired.modo con el mismo formato que usa Lambda.
  bool solicitarModo(Modo modo);
  // Publica desired.led con el mismo formato que usara Lambda (origen_led voz).
  bool solicitarLed(Luz luz);
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
    Modo modo = Modo::Ninguno;
    int minutos = 0;
    Origen origen = Origen::Ninguno;
    Luz led = Luz::Desconocida;
    Origen origenLed = Origen::Ninguno;
    // El delta trajo calibracion_solicitada sin "condicion": AWS omite los
    // campos anidados que no cambiaron (p. ej. al repetir "seco"). Hay que
    // leer el desired completo con GET.
    bool pedidoIncompleto = false;
  };

  static void recibir(void* contexto, esp_event_base_t, int32_t id, void* datos);
  void decodificar(const esp_mqtt_event_t& mensaje);
  void encolar(const Evento& evento);
  void procesar(const Evento& evento, unsigned long ahora, ServoTendedero* servo);
  void suscribir();
  void pedirShadow();
  void aplicar(const Evento& evento, unsigned long ahora, ServoTendedero* servo);
  bool enviarDecisionEdge();

  esp_mqtt_client_handle_t cliente_ = nullptr;
  QueueHandle_t cola_ = nullptr;
  String get_, getAceptado_, getRechazado_;
  String update_, delta_, updateAceptado_, updateRechazado_;
  bool conectado_ = false;
  bool sincronizado_ = false;
  Evento deltaPendiente_{Tipo::Delta};
  uint32_t version_ = 0;
  // Un GET con version menor a esta no trae el pedido incompleto: se ignora.
  uint32_t versionMinimaGet_ = 0;
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
  Modo modoEnviado_ = Modo::Ninguno;
  Modo modoAceptado_ = Modo::Ninguno;
  int minutosEnviados_ = 0;
  int minutosAceptados_ = 0;
  Origen origenEnviado_ = Origen::Ninguno;
  Origen origenAceptado_ = Origen::Ninguno;
  int oscuroEnviado_ = -1;
  int oscuroAceptado_ = -1;
  Luz ledEnviado_ = Luz::Desconocida;
  Luz ledAceptado_ = Luz::Desconocida;
  Origen origenLedEnviado_ = Origen::Ninguno;
  Origen origenLedAceptado_ = Origen::Ninguno;
  // Revision 0 = AWS todavia no acepto ninguna calibracion en esta conexion.
  uint32_t calibracionEnviada_ = 0;
  uint32_t calibracionAceptada_ = 0;
  bool primerReporte_ = true;
  // Pedido de calibracion recibido y aun no entregado al programa principal.
  bool hayPedido_ = false;
  Condicion condicionPedida_ = Condicion::Ninguna;
  uint64_t idPedido_ = 0;
  // Orden de posicion y configuracion aun no entregadas al programa principal.
  bool hayOrden_ = false;
  Posicion posicionPedida_ = Posicion::Desconocida;
  Origen origenPedido_ = Origen::Ninguno;
  bool hayConfiguracion_ = false;
  Modo modoPedido_ = Modo::Ninguno;
  int minutosPedidos_ = 0;
  // Decision del Edge todavia no escrita en desired (p. ej. sin conexion).
  Posicion decisionEdge_ = Posicion::Desconocida;
  bool hayOrdenLuz_ = false;
  Luz luzPedida_ = Luz::Desconocida;
  Origen origenLuzPedido_ = Origen::Ninguno;
  Luz decisionLuz_ = Luz::Desconocida;
};
