#pragma once
#include "Arduino.h"
// Cliente MQTT simulado: guarda lo publicado y deja inyectar mensajes.
typedef struct esp_mqtt_client { int x; }* esp_mqtt_client_handle_t;
struct esp_mqtt_event_t { char* topic; int topic_len; char* data; int data_len; int total_data_len; int current_data_offset; };
struct esp_mqtt_client_config_t { const char* uri; const char* client_id; const char* cert_pem;
  const char* client_cert_pem; const char* client_key_pem; int buffer_size; int out_buffer_size; int reconnect_timeout_ms; };
enum { MQTT_EVENT_ANY = -1, MQTT_EVENT_CONNECTED, MQTT_EVENT_DISCONNECTED, MQTT_EVENT_DATA, MQTT_EVENT_ERROR };
typedef void (*esp_event_handler_t)(void*, esp_event_base_t, int32_t, void*);
struct Publicado { std::string tema, datos; };
inline std::vector<Publicado> __publicados;
inline esp_event_handler_t __handler = nullptr;
inline void* __ctx = nullptr;
inline esp_mqtt_client __cliente;
inline esp_mqtt_client_handle_t esp_mqtt_client_init(const esp_mqtt_client_config_t*) { return &__cliente; }
inline esp_err_t esp_mqtt_client_register_event(esp_mqtt_client_handle_t, int, esp_event_handler_t h, void* c) {
  __handler = h; __ctx = c; return ESP_OK; }
inline esp_err_t esp_mqtt_client_start(esp_mqtt_client_handle_t) { return ESP_OK; }
inline void esp_mqtt_client_destroy(esp_mqtt_client_handle_t) {}
inline int esp_mqtt_client_subscribe(esp_mqtt_client_handle_t, const char*, int) { return 1; }
inline int esp_mqtt_client_enqueue(esp_mqtt_client_handle_t, const char* t, const char* d, int, int, int, bool) {
  __publicados.push_back({t, d}); return 1; }
inline void __evento(int id) { __handler(__ctx, "mqtt", id, nullptr); }
inline void __mensaje(const std::string& tema, const std::string& json) {
  esp_mqtt_event_t e{const_cast<char*>(tema.c_str()), (int)tema.size(), const_cast<char*>(json.c_str()),
                     (int)json.size(), (int)json.size(), 0};
  __handler(__ctx, "mqtt", MQTT_EVENT_DATA, &e);
}
