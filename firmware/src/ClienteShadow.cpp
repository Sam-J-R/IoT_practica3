#include "ClienteShadow.h"

#include <cJSON.h>
#include <esp_system.h>
#include <memory>

namespace {
constexpr unsigned long REINTENTO_MS = 5000;

// Compara el nombre exacto del topico recibido, no solo un fragmento.
bool temaIgual(const esp_mqtt_event_t& mensaje, const String& tema) {
  return mensaje.topic_len == static_cast<int>(tema.length()) &&
         memcmp(mensaje.topic, tema.c_str(), tema.length()) == 0;
}

#ifdef MODO_ENSAYO_RNF
const char* nombre(Posicion p) {
  return p == Posicion::Abierta ? "abierta" : (p == Posicion::Cerrada ? "cerrada" : "desconocida");
}

const char* cubiertaDe(const cJSON* estado, const char* seccion) {
  const char* texto = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(
      cJSON_GetObjectItemCaseSensitive(estado, seccion), "cubierta"));
  return texto ? texto : "null";
}
#endif

Posicion posicionDe(const cJSON* estado) {
  const char* texto = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(estado, "cubierta"));
  if (texto && strcmp(texto, "abierta") == 0) return Posicion::Abierta;
  if (texto && strcmp(texto, "cerrada") == 0) return Posicion::Cerrada;
  return Posicion::Desconocida;
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
                    cubiertaDe(estado, "desired"), cubiertaDe(estado, "reported"));
    }
#endif
    if (temaIgual(mensaje, delta_)) {
      encolar({Tipo::Delta, posicionDe(estado), v});
    } else {
      encolar({Tipo::Get, posicionDe(cJSON_GetObjectItemCaseSensitive(estado, "desired")), v});
    }
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

void ClienteShadow::aplicar(const Evento& evento, unsigned long ahora, ServoCubierta* servo) {
  // Solo los perfiles con servo real pasan un puntero valido.
  version_ = evento.version;
#ifdef MODO_ENSAYO_RNF
  if (servo && evento.posicion != Posicion::Desconocida) {
    Serial.printf("[SERVO] orden entregada destino=%s v=%lu ms=%lu\n", nombre(evento.posicion),
                  static_cast<unsigned long>(evento.version), ahora);
  }
#endif
  if (servo) servo->solicitar(evento.posicion, ahora);
}

void ClienteShadow::procesar(const Evento& evento, unsigned long ahora, ServoCubierta* servo) {
  switch (evento.tipo) {
    case Tipo::Conectado:
      // Al reconectar hay que leer desired otra vez: pudo cambiar sin Wi-Fi.
      conectado_ = true;
      sincronizado_ = false;
      version_ = 0;
      deltaPendiente_ = {Tipo::Delta};
      primerReporte_ = true;
      reportePendiente_ = 0;
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
      // Versiones evitan aplicar una orden antigua despues de una nueva.
      if (sincronizado_) {
        if (evento.version > version_) aplicar(evento, ahora, servo);
      } else if (evento.version > deltaPendiente_.version) {
        deltaPendiente_ = evento;
      }
      break;
    case Tipo::Get:
    case Tipo::SinShadow:
      if (conectado_ && !sincronizado_) {
        aplicar(deltaPendiente_.version > evento.version ? deltaPendiente_ : evento, ahora, servo);
        sincronizado_ = true;
        Serial.println("[SHADOW] Estado inicial recuperado");
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
        cubiertaAceptada_ = cubiertaEnviada_;
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

void ClienteShadow::atender(unsigned long ahora, ServoCubierta& servo) {
  atender(ahora, &servo);
}

void ClienteShadow::atender(unsigned long ahora, ServoCubierta* servo) {
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

void ClienteShadow::reportar(unsigned long ahora, int raw, int agua, Posicion cubierta) {
  // Publicamos tras cambios relevantes o cada 5 s como respaldo.
  // Si un envio no obtiene aceptacion, se reintenta con espera de 5 s.
  if (!sincronizado_) return;
  if (reportePendiente_ && ahora - ultimoEnvio_ < REINTENTO_MS) return;
  if (!primerReporte_ && agua == aguaAceptada_ && cubierta == cubiertaAceptada_ &&
      ahora - ultimoAceptado_ < INTERVALO_REPORTE_MS) return;

  const char* valorAgua = agua < 0 ? "null" : (agua ? "true" : "false");
  const char* valorCubierta = "null";
  if (cubierta == Posicion::Abierta) valorCubierta = "\"abierta\"";
  if (cubierta == Posicion::Cerrada) valorCubierta = "\"cerrada\"";

  const uint32_t reporte = ++secuencia_;
  char payload[192];
  snprintf(payload, sizeof(payload),
           "{\"state\":{\"reported\":{\"sensor_raw\":%d,\"agua_detectada\":%s,"
           "\"cubierta\":%s}},\"clientToken\":\"%lu-%lu\"}",
           raw, valorAgua, valorCubierta, static_cast<unsigned long>(sesion_),
           static_cast<unsigned long>(reporte));
  ultimoEnvio_ = ahora;
  reportePendiente_ = reporte;
  aguaEnviada_ = agua;
  cubiertaEnviada_ = cubierta;
  if (esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 0, 0, true) < 0) {
    Serial.println("[SHADOW] Error al enviar reported. Se reintentara.");
  }
}

void ClienteShadow::reportarSensor(unsigned long ahora, int raw) {
  if (!sincronizado_) return;
  if (reportePendiente_ && ahora - ultimoEnvio_ < REINTENTO_MS) return;
  if (!primerReporte_ && ahora - ultimoAceptado_ < INTERVALO_REPORTE_MS) return;

  const uint32_t reporte = ++secuencia_;
  char payload[144];
  snprintf(payload, sizeof(payload),
           "{\"state\":{\"reported\":{\"sensor_raw\":%d}},\"clientToken\":\"%lu-%lu\"}",
           raw, static_cast<unsigned long>(sesion_), static_cast<unsigned long>(reporte));
  ultimoEnvio_ = ahora;
  reportePendiente_ = reporte;
  aguaEnviada_ = -1;
  cubiertaEnviada_ = Posicion::Desconocida;
  if (esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 0, 0, true) < 0) {
    Serial.println("[SHADOW] Error al enviar el ADC. Se reintentara.");
  }
}

#ifdef MODO_ENSAYO_RNF
bool ClienteShadow::solicitarDesired(Posicion destino) {
  // Mismo payload que Lambda (sin clientToken): AWS genera el delta y el
  // firmware lo procesa por el camino normal, igual que una orden de Alexa.
  if (!cliente_ || !conectado_ || destino == Posicion::Desconocida) return false;
  char payload[80];
  snprintf(payload, sizeof(payload), "{\"state\":{\"desired\":{\"cubierta\":\"%s\"}}}",
           nombre(destino));
  return esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 1, 0, true) >= 0;
}

void ClienteShadow::consultarShadow() {
  if (cliente_ && conectado_) pedirShadow();
}
#endif
