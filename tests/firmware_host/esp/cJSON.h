#pragma once
// Sustituto minimo de cJSON (objetos, textos, numeros, true/false/null) para pruebas.
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
struct cJSON {
  int tipo = 0; // 0 null, 1 numero, 2 texto, 3 objeto, 4 bool
  double valuedouble = 0; int valueint = 0; std::string texto;
  std::map<std::string, cJSON*> hijos;
  ~cJSON() { for (auto& h : hijos) delete h.second; }
};
namespace cjson_min {
inline void esp(const char*& p) { while (*p == ' ' || *p == '\n' || *p == '\t' || *p == '\r') ++p; }
inline cJSON* valor(const char*& p);
inline std::string cadena(const char*& p) { std::string s; ++p; while (*p && *p != '"') s += *p++; if (*p) ++p; return s; }
inline cJSON* valor(const char*& p) {
  esp(p); auto* n = new cJSON;
  if (*p == '{') { n->tipo = 3; ++p; esp(p);
    while (*p && *p != '}') { esp(p); std::string k = cadena(p); esp(p); ++p; n->hijos[k] = valor(p); esp(p); if (*p == ',') ++p; esp(p); }
    if (*p) ++p;
  } else if (*p == '"') { n->tipo = 2; n->texto = cadena(p); }
  else if (!strncmp(p, "true", 4)) { n->tipo = 4; p += 4; }
  else if (!strncmp(p, "false", 5)) { n->tipo = 4; p += 5; }
  else if (!strncmp(p, "null", 4)) { p += 4; }
  else { char* fin; n->valuedouble = strtod(p, &fin); n->valueint = (int)n->valuedouble; n->tipo = 1; p = fin; }
  return n;
}
}
inline cJSON* cJSON_ParseWithLength(const char* d, size_t n) { std::string s(d, n); const char* p = s.c_str(); return cjson_min::valor(p); }
inline void cJSON_Delete(cJSON* c) { delete c; }
inline cJSON* cJSON_GetObjectItemCaseSensitive(const cJSON* o, const char* k) {
  if (!o || o->tipo != 3) return nullptr;
  auto i = o->hijos.find(k);
  return i == o->hijos.end() ? nullptr : i->second;
}
inline char* cJSON_GetStringValue(const cJSON* c) { return c && c->tipo == 2 ? const_cast<char*>(c->texto.c_str()) : nullptr; }
inline bool cJSON_IsNumber(const cJSON* c) { return c && c->tipo == 1; }
