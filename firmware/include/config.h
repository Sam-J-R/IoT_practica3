#pragma once

#include "TiposTendedero.h"

constexpr int PIN_AGUA_ANALOGICO = 34;
constexpr int PIN_SERVO_PWM = 26;
// Luz automatica (P4): LDR en divisor de tension y LED con resistencia de 220 ohm.
constexpr int PIN_LDR_ANALOGICO = 35; // ADC1, solo entrada: funciona con Wi-Fi activo.
constexpr int PIN_LED = 27;
constexpr unsigned long INTERVALO_SENSOR_MS = 500;
// Respaldo periodico. Los cambios de agua o posicion se reportan de inmediato.
constexpr unsigned long INTERVALO_REPORTE_MS = 60000;

// Calibracion del sensor a pedido (desired.calibracion_solicitada).
// Los umbrales se ubican a un porcentaje del recorrido entre la referencia
// en seco y la referencia con agua; dos porcentajes distintos dan histeresis.
constexpr int MUESTRAS_CALIBRACION = 20;
constexpr unsigned long PAUSA_MUESTRA_CALIBRACION_MS = 10;
constexpr int PORCENTAJE_UMBRAL_SECO = 10;
constexpr int PORCENTAJE_UMBRAL_AGUA = 30;
// Si seco y agua quedan mas cerca que esto, la calibracion se rechaza.
constexpr int SEPARACION_MINIMA_REFERENCIAS = 500;
// Un pedido mas antiguo que esto no se ejecuta: si el equipo estuvo apagado,
// ya no se sabe si el sensor sigue en la condicion que indico el usuario.
constexpr unsigned long VIGENCIA_PEDIDO_CALIBRACION_MS = 120000;

// Logica automatica (P4). Modo con el que arranca un ESP32 sin nada guardado.
constexpr Modo MODO_INICIAL = Modo::Automatico;
// Espera sin agua antes de que la Nube (regla R2) vuelva a exponer la ropa.
// El ESP32 solo la guarda y la reporta; la decision se toma en la Lambda.
constexpr int MINUTOS_REEXPONER_INICIAL = 30;
constexpr int MINUTOS_REEXPONER_MIN = 15;  // Menos: la ropa sale con la superficie aun mojada.
constexpr int MINUTOS_REEXPONER_MAX = 240;

// Luz automatica (regla R5). La lectura del LDR se lleva a una escala de
// 0 (oscuro) a 1000 (claro) con las referencias de luz_local.h.
// Histeresis: se considera oscuro por debajo de 350 y claro por encima de 650.
constexpr int LUZ_PERMIL_OSCURO = 350;
constexpr int LUZ_PERMIL_CLARO = 650;
// El cambio debe mantenerse 3 s: una sombra que pasa no enciende el LED.
constexpr unsigned long LUZ_CONFIRMACION_MS = 3000;
// Diferencia minima entre las referencias de claro y oscuro para aceptarlas.
constexpr int SEPARACION_MINIMA_LUZ = 200;
