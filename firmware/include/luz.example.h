#pragma once

// Copiar a luz_local.h con las lecturas medidas del LDR en el montaje real
// (ver hardware/CONEXIONES_P4.md). Con -1 la luz automatica queda deshabilitada
// y el firmware funciona igual que sin LDR.

// Lectura ADC (0..4095) del LDR con buena luz (de dia o habitacion iluminada)
// y con el LDR tapado o de noche. El sentido (si sube o baja con la luz)
// depende del cableado; el firmware lo deduce de estos dos valores.
constexpr int REFERENCIA_LUZ_CLARO = -1;
constexpr int REFERENCIA_LUZ_OSCURO = -1;

// true cuando el LED (con su resistencia de 220 ohm) esta conectado a GPIO27.
// Sin LDR el LED sigue funcionando por voz.
constexpr bool LED_INSTALADO = false;
