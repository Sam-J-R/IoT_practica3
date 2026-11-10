# Reconexión de red y sincronización

Sesión 20261110-101936 · puerto COM3 · generado por `ensayo_rnf.py` a partir del log `log-20261110-101936.csv`.

## Objetivo declarado

Aplicar la orden pendiente sin repetirla y converger `desired`/`reported` en ≤ 30 s desde `wifi_on`.

## Procedimiento

El ESP32 permanece encendido; `wifi_off` lo desasocia del punto de acceso. Con el dispositivo fuera de línea, el PC publica la posición opuesta en `desired` con el certificado del dispositivo y lee el Shadow. Tras `wifi_on` no se repite la orden. 3 repeticiones, 10 s adicionales fuera de línea.

## Condiciones

| Parámetro | Valor |
|---|---|
| Inicio del cronómetro | `wifi_on` |
| JSON del Shadow durante la interrupción | rnf-06-repN-pendiente-20261110-101936.json |

## Mediciones

| Rep. | Inicial | Orden | desired/reported durante | Red/arranque (s) | MQTT (s) | Shadow (s) | Posición (s) | Aceptado (s) | ¿Repetida? | ¿Converge? |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cerrada | abierta | abierta/cerrada | 0,13 | 3,92 | 4,77 | 5,76 | 6,18 | no | sí |
| 2 | abierta | cerrada | cerrada/abierta | 0,10 | 3,15 | 4,38 | 5,37 | 5,83 | no | sí |
| 3 | cerrada | abierta | abierta/cerrada | 0,11 | 5,02 | 6,25 | 7,24 | 7,69 | no | sí |

## Resumen

| Medida | Valor |
|---|---|
| Repeticiones | 3 |
| Correctas | 3 |
| Recuperación promedio (s) | 6,57 |
| Recuperación máxima (s) | 7,69 |
| Superan el objetivo | 0 |

## Conclusión

**Cumple.** 3/3 repeticiones con orden pendiente verificada, convergencia y sin repetir la orden; recuperación (desde `wifi_on` hasta reporte aceptado): promedio 6,57 s, máximo 7,69 s.

## Limitaciones

La interrupción la provoca el propio ESP32 (desasociación), no un apagado del punto de acceso: el firmware sabe de inmediato que perdió la red. La orden la publica el PC, no Alexa; el documento es el mismo que usa Lambda.

Datos: [rnf-06-reconexion-wifi-20261110-101936.csv](rnf-06-reconexion-wifi-20261110-101936.csv), [log-20261110-101936.csv](log-20261110-101936.csv).
