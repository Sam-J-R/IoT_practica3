#pragma once

#include <cstdint>

// Tipos compartidos por el firmware. No dependen de Arduino para poder
// probar la logica en la PC (tests/firmware_host).

// Expuesto: el brazo deja el tendedero fuera del techo.
// Resguardado: el brazo gira el tendedero hasta debajo del techo.
enum class Posicion : uint8_t { Desconocida, Expuesto, Resguardado };

// Modo de operacion (RF14). En Manual ninguna regla automatica mueve el brazo.
// Ninguno = el mensaje no traia modo (no es un valor valido del Shadow).
enum class Modo : uint8_t { Ninguno, Manual, Automatico };

// Estado del LED de luz automatica. Desconocida = sin LED o sin dato.
enum class Luz : uint8_t { Desconocida, Apagada, Encendida };

// Quien pidio el ultimo cambio de un actuador (RF12).
// Voz = Lambda de Alexa; Edge = regla R1 del ESP32; Nube = Lambdas de logica.
enum class Origen : uint8_t { Ninguno, Voz, Edge, Nube };
