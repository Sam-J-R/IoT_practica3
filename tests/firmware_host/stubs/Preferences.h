#pragma once
#include <map>
#include <string>
#include <cstdint>
// NVS simulada: persiste entre instancias (simula reinicio).
inline std::map<std::string,uint64_t> __nvs;
class Preferences { public:
 bool begin(const char*,bool){return true;}
 int getInt(const char*k,int d){auto i=__nvs.find(k);return i==__nvs.end()?d:(int)(int64_t)i->second;}
 void putInt(const char*k,int v){__nvs[k]=(uint64_t)(int64_t)v;}
 uint64_t getULong64(const char*k,uint64_t d){auto i=__nvs.find(k);return i==__nvs.end()?d:i->second;}
 void putULong64(const char*k,uint64_t v){__nvs[k]=v;}
 uint8_t getUChar(const char*k,uint8_t d){auto i=__nvs.find(k);return i==__nvs.end()?d:(uint8_t)i->second;}
 void putUChar(const char*k,uint8_t v){__nvs[k]=v;}
};
