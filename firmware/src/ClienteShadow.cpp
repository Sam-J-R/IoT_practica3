#include "ClienteShadow.h"

#include <cJSON.h>
#include <esp_system.h>
#include <memory>
#include <sys/time.h>
#include <time.h>

namespace {
constexpr unsigned long REINTENTO_MS = 5000;

// Compara el nombre exacto del topico recibido, no solo un fragmento.
bool temaIgual(const esp_mqtt_event_t& mensaje, const String& tema) {
  return mensaje.topic_len == static_cast<int>(tema.length()) &&
         memcmp(mensaje.topic, tema.c_str(), tema.length()) == 0;
}

const char* nombre(Condicion c) {
  return c == Condicion::Seco ? "seco" : (c == Condicion::Mojado ? "mojado" : "ninguna");
}

const char* nombre(ResultadoCalibracion r) {
  if (r == ResultadoCalibracion::Aplicada) return "aplicada";
  if (r == ResultadoCalibracion::Rechazada) return "rechazada";
  return r == ResultadoCalibracion::Caducada ? "caducada" : "fabrica";
}

const char* nombre(Posicion p) {
  if (p == Posicion::Expuesto) return "expuesto";
  return p == Posicion::Resguardado ? "resguardado" : "desconocida";
}

const char* nombre(Luz l) {
  return l == Luz::Encendida ? "encendido" : (l == Luz::Apagada ? "apagado" : "desconocido");
}

const char* nombre(Modo m) {
  return m == Modo::Manual ? "manual" : (m == Modo::Automatico ? "automatico" : "ninguno");
}

const char* nombre(Origen o) {
  if (o == Origen::Voz) return "voz";
  if (o == Origen::Edge) return "edge";
  return o == Origen::Nube ? "nube" : "ninguno";
}

#ifdef MODO_ENSAYO_RNF

const char* posicionTexto(const cJSON* estado, const char* seccion) {
  const char* texto = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(
      cJSON_GetObjectItemCaseSensitive(estado, seccion), "posicion"));
  return texto ? texto : "null";
}
#endif

Posicion posicionDe(const cJSON* estado) {
  const char* texto = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(estado, "posicion"));
  if (texto && strcmp(texto, "expuesto") == 0) return Posicion::Expuesto;
  if (texto && strcmp(texto, "resguardado") == 0) return Posicion::Resguardado;
  return Posicion::Desconocida;
}

// Modo, minutos y origen ausentes o con valores fuera del contrato se tratan
// como "no vino": el ESP32 conserva lo que tenia.
Modo modoDe(const cJSON* estado) {
  const char* texto = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(estado, "modo"));
  if (texto && strcmp(texto, "manual") == 0) return Modo::Manual;
  if (texto && strcmp(texto, "automatico") == 0) return Modo::Automatico;
  return Modo::Ninguno;
}

int minutosDe(const cJSON* estado) {
  const cJSON* numero = cJSON_GetObjectItemCaseSensitive(estado, "minutos_reexponer");
  if (!cJSON_IsNumber(numero)) return 0;
  const double valor = numero->valuedouble;
  return valor >= 1 && valor <= 100000 ? static_cast<int>(valor) : 0;
}

Luz ledDe(const cJSON* estado) {
  const char* texto = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(estado, "led"));
  if (texto && strcmp(texto, "encendido") == 0) return Luz::Encendida;
  if (texto && strcmp(texto, "apagado") == 0) return Luz::Apagada;
  return Luz::Desconocida;
}

Origen origenDe(const cJSON* estado) {
  const char* texto = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(estado, "origen"));
  if (texto && strcmp(texto, "voz") == 0) return Origen::Voz;
  if (texto && strcmp(texto, "nube") == 0) return Origen::Nube;
  if (texto && strcmp(texto, "edge") == 0) return Origen::Edge;
  return Origen::Ninguno;
}

// Hora actual en milisegundos (epoch, reloj NTP). 0 si el reloj no esta listo.
double epochMs() {
  struct timeval ahora;
  gettimeofday(&ahora, nullptr);
  if (ahora.tv_sec < 1704067200) return 0; // 2024-01-01: sin SNTP todavia.
  return static_cast<double>(ahora.tv_sec) * 1000.0 + ahora.tv_usec / 1000;
}

// Lee calibracion_solicitada {condicion, id}. Si falta o esta incompleta,
// deja condicion = Ninguna e id = 0 (no hay pedido). Devuelve true si hay un
// id valido pero falta "condicion": en un delta significa que la condicion no
// cambio respecto de reported y AWS la omitio; el llamador debe pedir un GET.
bool pedidoDe(const cJSON* estado, Condicion& condicion, uint64_t& id) {
  const cJSON* pedido = cJSON_GetObjectItemCaseSensitive(estado, "calibracion_solicitada");
  const char* texto = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(pedido, "condicion"));
  const cJSON* numero = cJSON_GetObjectItemCaseSensitive(pedido, "id");
  condicion = Condicion::Ninguna;
  id = 0;
  const bool idValido = cJSON_IsNumber(numero) && numero->valuedouble >= 1;
  if (!texto) return idValido;
  if (!idValido) return false;
  if (strcmp(texto, "seco") == 0) condicion = Condicion::Seco;
  if (strcmp(texto, "mojado") == 0) condicion = Condicion::Mojado;
  if (condicion != Condicion::Ninguna) id = static_cast<uint64_t>(numero->valuedouble);
  return false;
}
}

bool ClienteShadow::iniciar(const char* endpoint, const char* thing, const char* ca,
                           const char* certificado, const char* clave) {
  // AWS usa topicos reservados que empiezan con $aws/things/NOMBRE/shadow.
  // "get" pide el estado actual; "delta" indica una orden pendiente.
  const String base = String("$aws/things/") + thing + "/shadow";
  get_ = base + "/get";
  getAceptado_ = get_ + "/accepted";
  getRechazado_ = get_ + "/rejected";
  update_ = base + "/update";
  delta_ = update_ + "/delta";
  updateAceptado_ = update_ + "/accepted";
  updateRechazado_ = update_ + "/rejected";
  cola_ = xQueueCreate(24, sizeof(Evento));
  if (!cola_) return false;

  const String uri = String("mqtts://") + endpoint + ":8883";
  esp_mqtt_client_config_t config{};
  config.uri = uri.c_str();
  config.client_id = thing;
  config.cert_pem = ca;
  config.client_cert_pem = certificado;
  config.client_key_pem = clave;
  config.buffer_size = 16384;
  config.out_buffer_size = 1024;
  config.reconnect_timeout_ms = REINTENTO_MS;
  sesion_ = esp_random();
  cliente_ = esp_mqtt_client_init(&config);
  if (cliente_ &&
      esp_mqtt_client_register_event(cliente_, MQTT_EVENT_ANY, recibir, this) == ESP_OK &&
      esp_mqtt_client_start(cliente_) == ESP_OK) {
    return true;
  }

  if (cliente_) esp_mqtt_client_destroy(cliente_);
  cliente_ = nullptr;
  vQueueDelete(cola_);
  cola_ = nullptr;
  return false;
}

void ClienteShadow::recibir(void* contexto, esp_event_base_t, int32_t id, void* datos) {
  // El callback MQTT puede ejecutarse fuera del loop principal.
  // Solo encola avisos: el servo se maneja luego desde atender().
  auto& shadow = *static_cast<ClienteShadow*>(contexto);
  if (id == MQTT_EVENT_CONNECTED) shadow.encolar({Tipo::Conectado});
  if (id == MQTT_EVENT_DISCONNECTED) shadow.encolar({Tipo::Desconectado});
  if (id == MQTT_EVENT_DATA) shadow.decodificar(*static_cast<esp_mqtt_event_t*>(datos));
  if (id == MQTT_EVENT_ERROR) Serial.println("[MQTT] Error de conexion o transporte");
}

void ClienteShadow::encolar(const Evento& evento) {
  if (xQueueSend(cola_, &evento, pdMS_TO_TICKS(100)) != pdTRUE) {
    Serial.println("[MQTT] Cola llena. Se volvera a solicitar el Shadow");
    xQueueReset(cola_);
    // Un nuevo GET vuelve a establecer el estado desde el servidor.
    const Evento recuperar{Tipo::ErrorGet};
    xQueueSend(cola_, &recuperar, 0);
  }
}

void ClienteShadow::decodificar(const esp_mqtt_event_t& mensaje) {
  // Primero averiguamos si llego un delta, una respuesta a GET o un ACK.
  // Un mensaje incompleto se ignora para no interpretar JSON truncado.
  if (!mensaje.topic || mensaje.current_data_offset != 0 ||
      mensaje.data_len != mensaje.total_data_len) {
    return;
  }
  std::unique_ptr<cJSON, decltype(&cJSON_Delete)> doc(
      cJSON_ParseWithLength(mensaje.data, mensaje.data_len), cJSON_Delete);
  if (!doc) return;

  const auto* version = cJSON_GetObjectItemCaseSensitive(doc.get(), "version");
  const auto* estado = cJSON_GetObjectItemCaseSensitive(doc.get(), "state");
  if (temaIgual(mensaje, delta_) || temaIgual(mensaje, getAceptado_)) {
    if (!cJSON_IsNumber(version) || version->valuedouble < 1 ||
        version->valuedouble > UINT32_MAX) return;
    const uint32_t v = static_cast<uint32_t>(version->valuedouble);
#ifdef MODO_ENSAYO_RNF
    if (temaIgual(mensaje, getAceptado_)) {
      Serial.printf("[SHADOW] get v=%lu desired=%s reported=%s\n", static_cast<unsigned long>(v),
                    posicionTexto(estado, "desired"), posicionTexto(estado, "reported"));
    }
#endif
    // El delta trae solo lo que difiere; el GET trae "desired" completo.
    const bool esDelta = temaIgual(mensaje, delta_);
    const cJSON* deseado = esDelta ? estado : cJSON_GetObjectItemCaseSensitive(estado, "desired");
    Evento evento{esDelta ? Tipo::Delta : Tipo::Get, posicionDe(deseado), v};
    evento.pedidoIncompleto = pedidoDe(deseado, evento.condicion, evento.idCalibracion) && esDelta;
    evento.modo = modoDe(deseado);
    evento.minutos = minutosDe(deseado);
    evento.origen = origenDe(deseado);
    evento.led = ledDe(deseado);
    // Solo la voz ordena la luz por el Shadow: no hace falta desired.origen_led.
    evento.origenLed = evento.led != Luz::Desconocida ? Origen::Voz : Origen::Ninguno;
    encolar(evento);
    return;
  }

  const auto* codigo = cJSON_GetObjectItemCaseSensitive(doc.get(), "code");
  if (temaIgual(mensaje, getRechazado_)) {
    const int error = cJSON_IsNumber(codigo) ? codigo->valueint : 0;
    encolar({error == 404 ? Tipo::SinShadow : Tipo::ErrorGet, Posicion::Desconocida, 0, 0, error});
  } else if (temaIgual(mensaje, updateAceptado_) || temaIgual(mensaje, updateRechazado_)) {
    // clientToken permite relacionar la respuesta con nuestro ultimo reporte.
    const char* token = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(doc.get(), "clientToken"));
    unsigned long sesion = 0, reporte = 0;
    if (token && sscanf(token, "%lu-%lu", &sesion, &reporte) == 2 && sesion == sesion_) {
      encolar({temaIgual(mensaje, updateAceptado_) ? Tipo::ReporteAceptado : Tipo::ReporteRechazado,
               Posicion::Desconocida, 0, static_cast<uint32_t>(reporte),
               cJSON_IsNumber(codigo) ? codigo->valueint : 0});
    }
  }
}

void ClienteShadow::suscribir() {
  // Escuchamos ordenes nuevas y respuestas de AWS; reintentamos si falla.
  for (const String* tema : {&delta_, &getAceptado_, &getRechazado_,
                             &updateAceptado_, &updateRechazado_}) {
    if (esp_mqtt_client_subscribe(cliente_, tema->c_str(), 1) < 0) {
      Serial.printf("[MQTT] No se pudo suscribir a %s. Se reintentara.\n", tema->c_str());
    }
  }
}

void ClienteShadow::pedirShadow() {
  if (esp_mqtt_client_enqueue(cliente_, get_.c_str(), "", 0, 0, 0, true) < 0) {
    Serial.println("[SHADOW] No se pudo solicitar el estado. Se reintentara.");
  }
}

void ClienteShadow::aplicar(const Evento& evento, unsigned long ahora, ServoTendedero* servo) {
  // Solo los perfiles con servo real pasan un puntero valido.
  static_cast<void>(ahora); // Solo se usa en los mensajes del perfil de ensayo.
  version_ = evento.version;
#ifdef MODO_ENSAYO_RNF
  if (servo && evento.posicion != Posicion::Desconocida) {
    Serial.printf("[SERVO] orden entregada destino=%s v=%lu ms=%lu\n", nombre(evento.posicion),
                  static_cast<unsigned long>(evento.version), ahora);
  }
#endif
  if (!servo) return;
  // La posicion la ejecuta el programa principal, que aplica la politica
  // voz / logica automatica. Si hay una decision del Edge sin publicar, un
  // desired distinto es anterior a ella (llego con el GET al reconectar).
  Posicion posicion = evento.posicion;
  if (decisionEdge_ != Posicion::Desconocida && posicion != decisionEdge_) {
    posicion = Posicion::Desconocida;
  }
  if (posicion != Posicion::Desconocida) {
    hayOrden_ = true;
    posicionPedida_ = posicion;
    origenPedido_ = evento.origen;
  }
  // Lo mismo para el LED.
  Luz luz = evento.led;
  if (decisionLuz_ != Luz::Desconocida && luz != decisionLuz_) luz = Luz::Desconocida;
  if (luz != Luz::Desconocida) {
    hayOrdenLuz_ = true;
    luzPedida_ = luz;
    origenLuzPedido_ = evento.origenLed;
  }
  if (evento.modo != Modo::Ninguno) {
    hayConfiguracion_ = true;
    modoPedido_ = evento.modo;
  }
  if (evento.minutos != 0) {
    hayConfiguracion_ = true;
    minutosPedidos_ = evento.minutos;
  }
  // La calibracion la ejecuta el programa principal (necesita leer el ADC).
  if (evento.condicion != Condicion::Ninguna && evento.idCalibracion != 0) {
    hayPedido_ = true;
    condicionPedida_ = evento.condicion;
    idPedido_ = evento.idCalibracion;
  }
}

bool ClienteShadow::tomarOrden(Posicion& posicion, Origen& origen) {
  if (!hayOrden_) return false;
  hayOrden_ = false;
  posicion = posicionPedida_;
  origen = origenPedido_;
  return true;
}

bool ClienteShadow::tomarOrdenLuz(Luz& luz, Origen& origen) {
  if (!hayOrdenLuz_) return false;
  hayOrdenLuz_ = false;
  luz = luzPedida_;
  origen = origenLuzPedido_;
  return true;
}

bool ClienteShadow::tomarConfiguracion(Modo& modo, int& minutos) {
  if (!hayConfiguracion_) return false;
  hayConfiguracion_ = false;
  modo = modoPedido_;
  minutos = minutosPedidos_;
  modoPedido_ = Modo::Ninguno;
  minutosPedidos_ = 0;
  return true;
}

void ClienteShadow::publicarDecisionEdge(Posicion posicion) {
  if (posicion == Posicion::Desconocida) return;
  decisionEdge_ = posicion;
  if (conectado_ && sincronizado_) enviarDecisionEdge();
}

void ClienteShadow::publicarDecisionLuz(Luz luz) {
  if (luz == Luz::Desconocida) return;
  decisionLuz_ = luz;
  if (conectado_ && sincronizado_) enviarDecisionEdge();
}

bool ClienteShadow::enviarDecisionEdge() {
  // Mismo formato que las Lambdas: desired.posicion + desired.origen y/o
  // desired.led. Ambas decisiones pendientes van juntas. origen_led:null borra
  // el campo que escribian las versiones anteriores, para que no quede un delta.
  char campos[128] = "";
  int usados = 0;
  if (decisionEdge_ != Posicion::Desconocida) {
    usados += snprintf(campos + usados, sizeof(campos) - usados,
                       "\"posicion\":\"%s\",\"origen\":\"edge\"", nombre(decisionEdge_));
  }
  if (decisionLuz_ != Luz::Desconocida && usados < static_cast<int>(sizeof(campos))) {
    snprintf(campos + usados, sizeof(campos) - usados, "%s\"led\":\"%s\",\"origen_led\":null",
             usados ? "," : "", nombre(decisionLuz_));
  }
  if (!campos[0]) return true;
  char payload[176];
  snprintf(payload, sizeof(payload), "{\"state\":{\"desired\":{%s}}}", campos);
  if (esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 1, 0, true) < 0) {
    Serial.println("[EDGE] No se pudo escribir desired. Se reintentara al sincronizar.");
    return false;
  }
  if (decisionEdge_ != Posicion::Desconocida) {
    Serial.printf("[EDGE] desired.posicion=%s origen=edge publicado\n", nombre(decisionEdge_));
  }
  if (decisionLuz_ != Luz::Desconocida) {
    Serial.printf("[EDGE] desired.led=%s publicado\n", nombre(decisionLuz_));
  }
  decisionEdge_ = Posicion::Desconocida;
  decisionLuz_ = Luz::Desconocida;
  return true;
}

bool ClienteShadow::tomarPedidoCalibracion(Condicion& condicion, uint64_t& id) {
  if (!hayPedido_) return false;
  hayPedido_ = false;
  condicion = condicionPedida_;
  id = idPedido_;
  return true;
}

void ClienteShadow::procesar(const Evento& evento, unsigned long ahora, ServoTendedero* servo) {
  switch (evento.tipo) {
    case Tipo::Conectado:
      // Al reconectar hay que leer desired otra vez: pudo cambiar sin Wi-Fi.
      conectado_ = true;
      sincronizado_ = false;
      version_ = 0;
      versionMinimaGet_ = 0;
      deltaPendiente_ = {Tipo::Delta};
      primerReporte_ = true;
      reportePendiente_ = 0;
      calibracionAceptada_ = 0;
      suscribir();
      ultimoGet_ = ahora;
      pedirShadow();
      Serial.println("[MQTT] Conectado. Solicitando Shadow");
      break;
    case Tipo::Desconectado:
      conectado_ = false;
      sincronizado_ = false;
      Serial.println("[MQTT] Desconectado");
      break;
    case Tipo::Delta:
#ifdef MODO_ENSAYO_RNF
      Serial.printf("[SHADOW] delta recibido destino=%s v=%lu ms=%lu\n", nombre(evento.posicion),
                    static_cast<unsigned long>(evento.version), ahora);
#endif
      if (evento.pedidoIncompleto) {
        // Repetir la misma condicion de calibracion genera un delta solo con
        // el id nuevo. Se relee el desired completo; la posicion pendiente, si
        // la hay, tambien llega en ese GET.
        Serial.println("[SHADOW] Pedido de calibracion sin condicion en el delta. Solicitando Shadow");
        sincronizado_ = false;
        deltaPendiente_ = {Tipo::Delta};
        versionMinimaGet_ = evento.version;
        ultimoGet_ = ahora;
        pedirShadow();
        break;
      }
      // Versiones evitan aplicar una orden antigua despues de una nueva.
      if (sincronizado_) {
        if (evento.version > version_) aplicar(evento, ahora, servo);
      } else if (evento.version > deltaPendiente_.version) {
        deltaPendiente_ = evento;
      }
      break;
    case Tipo::Get:
    case Tipo::SinShadow:
      // Un GET pedido antes del pedido incompleto no lo trae: esperar el siguiente.
      if (evento.tipo == Tipo::Get && evento.version < versionMinimaGet_) break;
      if (conectado_ && !sincronizado_) {
        aplicar(deltaPendiente_.version > evento.version ? deltaPendiente_ : evento, ahora, servo);
        sincronizado_ = true;
        Serial.println("[SHADOW] Estado inicial recuperado");
        // Decision tomada sin conexion: se escribe ahora en desired.
        if ((decisionEdge_ != Posicion::Desconocida || decisionLuz_ != Luz::Desconocida) &&
            !enviarDecisionEdge()) {
          sincronizado_ = false; // Reintentar con otro GET.
        }
      }
      break;
    case Tipo::ErrorGet:
      sincronizado_ = false;
      deltaPendiente_ = {Tipo::Delta};
      Serial.printf("[SHADOW] Reintento de get (codigo=%d)\n", evento.codigo);
      break;
    case Tipo::ReporteAceptado:
      // Solo aqui marcamos la telemetria como aceptada por AWS.
      if (reportePendiente_ && evento.reporte == reportePendiente_) {
        aguaAceptada_ = aguaEnviada_;
        posicionAceptada_ = posicionEnviada_;
        modoAceptado_ = modoEnviado_;
        minutosAceptados_ = minutosEnviados_;
        origenAceptado_ = origenEnviado_;
        oscuroAceptado_ = oscuroEnviado_;
        ledAceptado_ = ledEnviado_;
        origenLedAceptado_ = origenLedEnviado_;
        calibracionAceptada_ = calibracionEnviada_;
        ultimoAceptado_ = ahora;
        primerReporte_ = false;
        reportePendiente_ = 0;
        Serial.printf("[SHADOW] reported aceptado ms=%lu\n", ahora);
      }
      break;
    case Tipo::ReporteRechazado:
      if (reportePendiente_ && evento.reporte == reportePendiente_) {
        // Mantener el plazo de reintento para no saturar el servicio.
        Serial.printf("[SHADOW] reported rechazado (codigo=%d)\n", evento.codigo);
      }
      break;
  }
}

void ClienteShadow::atender(unsigned long ahora, ServoTendedero& servo) {
  atender(ahora, &servo);
}

void ClienteShadow::atender(unsigned long ahora, ServoTendedero* servo) {
  // Ejecutado en el loop: procesa la cola y, si es necesario, recupera GET.
  if (!cliente_) return;
  Evento evento{Tipo::Desconectado};
  while (xQueueReceive(cola_, &evento, 0) == pdTRUE) {
    procesar(evento, ahora, servo);
  }
  if (conectado_ && !sincronizado_ && ahora - ultimoGet_ >= REINTENTO_MS) {
    ultimoGet_ = ahora;
    suscribir();
    pedirShadow();
  }
}

void ClienteShadow::reportar(unsigned long ahora, const Telemetria& telemetria,
                             const EstadoCalibracion& calibracion) {
  // Publicamos tras cambios relevantes o como respaldo periodico.
  // Si un envio no obtiene aceptacion, se reintenta con espera de 5 s.
  if (!sincronizado_) return;
  if (reportePendiente_ && ahora - ultimoEnvio_ < REINTENTO_MS) return;
  const bool calibracionNueva = calibracion.revision != calibracionAceptada_;
  if (!primerReporte_ && !calibracionNueva && telemetria.agua == aguaAceptada_ &&
      telemetria.posicion == posicionAceptada_ && telemetria.modo == modoAceptado_ &&
      telemetria.minutosReexponer == minutosAceptados_ && telemetria.origen == origenAceptado_ &&
      telemetria.oscuro == oscuroAceptado_ && telemetria.led == ledAceptado_ &&
      telemetria.origenLed == origenLedAceptado_ &&
      ahora - ultimoAceptado_ < INTERVALO_REPORTE_MS) return;

  const char* valorAgua = telemetria.agua < 0 ? "null" : (telemetria.agua ? "true" : "false");
  const char* valorPosicion = "null";
  if (telemetria.posicion == Posicion::Expuesto) valorPosicion = "\"expuesto\"";
  if (telemetria.posicion == Posicion::Resguardado) valorPosicion = "\"resguardado\"";

  // Umbrales vigentes y, si hubo un pedido, su confirmacion. Repetir en
  // reported lo pedido en desired hace desaparecer el delta de ese pedido.
  char bloque[224] = "";
  if (calibracionNueva) {
    const int usados = snprintf(bloque, sizeof(bloque),
                                ",\"calibracion\":{\"umbral_seco\":%d,\"umbral_agua\":%d,"
                                "\"estado\":\"%s\"}",
                                calibracion.umbralSeco, calibracion.umbralAgua,
                                nombre(calibracion.resultado));
    if (calibracion.id != 0 && usados > 0 && usados < static_cast<int>(sizeof(bloque))) {
      snprintf(bloque + usados, sizeof(bloque) - usados,
               ",\"calibracion_solicitada\":{\"condicion\":\"%s\",\"id\":%.0f}",
               nombre(calibracion.condicion), static_cast<double>(calibracion.id));
    }
  }

  // P4: modo, parametros y origen del ultimo movimiento (RF12, RF14). En el
  // perfil de ensayo, ademas, la hora del ESP32 para medir la latencia.
  char operacion[320] = "";
  int usados = 0;
  if (telemetria.modo != Modo::Ninguno) {
    usados += snprintf(operacion + usados, sizeof(operacion) - usados,
                       ",\"modo\":\"%s\",\"minutos_reexponer\":%d",
                       nombre(telemetria.modo), telemetria.minutosReexponer);
  }
  if (telemetria.origen != Origen::Ninguno && usados < static_cast<int>(sizeof(operacion))) {
    usados += snprintf(operacion + usados, sizeof(operacion) - usados, ",\"origen\":\"%s\"",
                       nombre(telemetria.origen));
  }
  // Luz automatica: lectura del LDR, clasificacion, estado del LED y su origen.
  if (telemetria.luzInstalada && usados < static_cast<int>(sizeof(operacion))) {
    usados += snprintf(operacion + usados, sizeof(operacion) - usados,
                       ",\"luz_adc\":%d,\"oscuro\":%s", telemetria.luzAdc,
                       telemetria.oscuro < 0 ? "null" : (telemetria.oscuro ? "true" : "false"));
#ifdef MODO_ENSAYO_RNF
    // Solo en el perfil de ensayo, que es el unico que simula la luz.
    // null borra el atributo del Shadow cuando se vuelve al LDR real.
    if (usados < static_cast<int>(sizeof(operacion))) {
      usados += snprintf(operacion + usados, sizeof(operacion) - usados, ",\"luz_simulada\":%s",
                         telemetria.luzSimulada ? "true" : "null");
    }
#endif
  }
  if (telemetria.led != Luz::Desconocida && usados < static_cast<int>(sizeof(operacion))) {
    usados += snprintf(operacion + usados, sizeof(operacion) - usados, ",\"led\":\"%s\"",
                       nombre(telemetria.led));
  }
  if (telemetria.origenLed != Origen::Ninguno && usados < static_cast<int>(sizeof(operacion))) {
    usados += snprintf(operacion + usados, sizeof(operacion) - usados, ",\"origen_led\":\"%s\"",
                       nombre(telemetria.origenLed));
  }
#ifdef MODO_ENSAYO_RNF
  // Hora del ESP32, solo para medir la latencia de almacenamiento en los ensayos.
  const double ts = epochMs();
  if (ts > 0 && usados < static_cast<int>(sizeof(operacion))) {
    snprintf(operacion + usados, sizeof(operacion) - usados, ",\"ts_dispositivo\":%.0f", ts);
  }
#endif

  const uint32_t reporte = ++secuencia_;
  char payload[800];
  snprintf(payload, sizeof(payload),
           "{\"state\":{\"reported\":{\"lectura_adc\":%d,\"agua_detectada\":%s,"
           "\"posicion\":%s%s%s}},\"clientToken\":\"%lu-%lu\"}",
           telemetria.lecturaAdc, valorAgua, valorPosicion, operacion, bloque,
           static_cast<unsigned long>(sesion_), static_cast<unsigned long>(reporte));
  ultimoEnvio_ = ahora;
  reportePendiente_ = reporte;
  aguaEnviada_ = telemetria.agua;
  posicionEnviada_ = telemetria.posicion;
  modoEnviado_ = telemetria.modo;
  minutosEnviados_ = telemetria.minutosReexponer;
  origenEnviado_ = telemetria.origen;
  oscuroEnviado_ = telemetria.oscuro;
  ledEnviado_ = telemetria.led;
  origenLedEnviado_ = telemetria.origenLed;
  calibracionEnviada_ = calibracionNueva ? calibracion.revision : calibracionAceptada_;
  if (esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 0, 0, true) < 0) {
    Serial.println("[SHADOW] Error al enviar reported. Se reintentara.");
  }
}

void ClienteShadow::reportarSensor(unsigned long ahora, int lecturaAdc) {
  if (!sincronizado_) return;
  if (reportePendiente_ && ahora - ultimoEnvio_ < REINTENTO_MS) return;
  if (!primerReporte_ && ahora - ultimoAceptado_ < INTERVALO_REPORTE_MS) return;

  const uint32_t reporte = ++secuencia_;
  char payload[144];
  snprintf(payload, sizeof(payload),
           "{\"state\":{\"reported\":{\"lectura_adc\":%d}},\"clientToken\":\"%lu-%lu\"}",
           lecturaAdc, static_cast<unsigned long>(sesion_), static_cast<unsigned long>(reporte));
  ultimoEnvio_ = ahora;
  reportePendiente_ = reporte;
  aguaEnviada_ = -1;
  posicionEnviada_ = Posicion::Desconocida;
  calibracionEnviada_ = calibracionAceptada_;
  if (esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 0, 0, true) < 0) {
    Serial.println("[SHADOW] Error al enviar el ADC. Se reintentara.");
  }
}

#ifdef MODO_ENSAYO_RNF
bool ClienteShadow::solicitarDesired(Posicion destino) {
  // Mismo payload que Lambda (sin clientToken): AWS genera el delta y el
  // firmware lo procesa por el camino normal, igual que una orden de Alexa.
  if (!cliente_ || !conectado_ || destino == Posicion::Desconocida) return false;
  char payload[96];
  snprintf(payload, sizeof(payload),
           "{\"state\":{\"desired\":{\"posicion\":\"%s\",\"origen\":\"voz\"}}}",
           nombre(destino));
  return esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 1, 0, true) >= 0;
}

bool ClienteShadow::solicitarLed(Luz luz) {
  if (!cliente_ || !conectado_ || luz == Luz::Desconocida) return false;
  char payload[96];
  snprintf(payload, sizeof(payload),
           "{\"state\":{\"desired\":{\"led\":\"%s\"}}}", nombre(luz));
  return esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 1, 0, true) >= 0;
}

bool ClienteShadow::solicitarModo(Modo modo) {
  if (!cliente_ || !conectado_ || modo == Modo::Ninguno) return false;
  char payload[64];
  snprintf(payload, sizeof(payload), "{\"state\":{\"desired\":{\"modo\":\"%s\"}}}",
           nombre(modo));
  return esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 1, 0, true) >= 0;
}

bool ClienteShadow::solicitarCalibracion(Condicion condicion) {
  // Igual que Lambda: el id es la hora actual en milisegundos (reloj NTP).
  if (!cliente_ || !conectado_ || condicion == Condicion::Ninguna) return false;
  char payload[128];
  snprintf(payload, sizeof(payload),
           "{\"state\":{\"desired\":{\"calibracion_solicitada\":"
           "{\"condicion\":\"%s\",\"id\":%.0f}}}}",
           nombre(condicion), static_cast<double>(time(nullptr)) * 1000.0);
  return esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 1, 0, true) >= 0;
}

void ClienteShadow::consultarShadow() {
  if (cliente_ && conectado_) pedirShadow();
}
#endif
