#pragma once

constexpr int PIN_AGUA_ANALOGICO = 34;
constexpr int PIN_SERVO_PWM = 26;
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
