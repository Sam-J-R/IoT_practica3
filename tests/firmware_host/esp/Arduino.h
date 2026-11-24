#pragma once
// Arduino/FreeRTOS simulados para compilar ClienteShadow.cpp en la PC.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>
#include <vector>
typedef int esp_err_t;
typedef const char* esp_event_base_t;
#define ESP_OK 0
struct String {
  std::string s;
  String() {}
  String(const char* c) : s(c) {}
  String(const std::string& x) : s(x) {}
  String operator+(const String& o) const { return String(s + o.s); }
  String operator+(const char* o) const { return String(s + o); }
  friend String operator+(const char* a, const String& b) { return String(std::string(a) + b.s); }
  const char* c_str() const { return s.c_str(); }
  unsigned length() const { return s.size(); }
};
struct SerialT {
  std::string log;
  void println(const char* t) { log += t; log += "\n"; }
  template <class... A> void printf(const char* f, A... a) {
    char b[512]; std::snprintf(b, sizeof b, f, a...); log += b;
  }
};
inline SerialT Serial;
// Cola de FreeRTOS: copia bytes como la real.
struct Cola { int tam; std::deque<std::vector<char>> items; };
typedef Cola* QueueHandle_t;
typedef int BaseType_t;
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
inline QueueHandle_t xQueueCreate(int, int tam) { return new Cola{tam, {}}; }
inline BaseType_t xQueueSend(QueueHandle_t q, const void* d, int) {
  const char* p = static_cast<const char*>(d); q->items.emplace_back(p, p + q->tam); return 1;
}
inline BaseType_t xQueueReceive(QueueHandle_t q, void* d, int) {
  if (q->items.empty()) return 0;
  std::memcpy(d, q->items.front().data(), q->tam); q->items.pop_front(); return 1;
}
inline void xQueueReset(QueueHandle_t q) { q->items.clear(); }
inline void vQueueDelete(QueueHandle_t q) { delete q; }
inline uint32_t esp_random() { return 7; }
inline int ledcSetup(int, int, int) { return 1; }
inline void ledcAttachPin(int, int) {}
inline uint32_t __ledc = 0;
inline void ledcWrite(int, uint32_t d) { __ledc = d; }
#define INPUT 0
#define OUTPUT 3
#define LOW 0
#define HIGH 1
#define ADC_11db 3
inline void pinMode(int, int) {}
inline void digitalWrite(int, int) {}
inline void analogReadResolution(int) {}
inline void analogSetPinAttenuation(int, int) {}
inline int analogRead(int) { return 0; }
