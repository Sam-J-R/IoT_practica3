#pragma once
#include <cstdint>
#include <cstdlib>
#include <map>
#include <string>
#define INPUT 0
#define ADC_11db 3
#define OUTPUT 3
#define LOW 0
#define HIGH 1
inline int __led = -1;
inline void digitalWrite(int, int v) { __led = v; }
inline int __adc = 0;
inline void pinMode(int,int){} inline void analogReadResolution(int){}
inline void analogSetPinAttenuation(int,int){} inline int analogRead(int){return __adc;}
using std::abs;
