# Tabla final de RNF

Último ensayo registrado de cada requisito.

| Requisito | Objetivo declarado | Resultado medido | ¿Cumple? | Evidencia |
|---|---|---|---|---|
| Estabilidad | Operar 15 min sin reinicios ni bloqueos, completando todas las órdenes y consultas. | 15.0 min, 15 órdenes (15 completas) y 14 consultas (14 con respuesta); 0 reinicios, 0 bloqueos, 0 desconexiones MQTT. | Cumple | [rnf-01-estabilidad-20261110-094834.md](rnf-01-estabilidad-20261110-094834.md) |
| Tiempo de respuesta orden → actuador | Tiempo desde la publicación de la orden hasta la posición final ≤ 3,00 s en todas las órdenes. | 10/10 órdenes completadas; envío → posición estimada: promedio 2,19 s, máximo 2,42 s; 0 superan 3,00 s. | Cumple | [rnf-02-respuesta-20261110-094834.md](rnf-02-respuesta-20261110-094834.md) |
| Clasificación del sensor de agua | Aciertos ≥ 95 % y como máximo 0 falsos negativos (un falso negativo informa que no hay agua cuando sí la hay). | 20/20 aciertos (100.0 %): VP=10 VN=10 FP=0 FN=0, otras=0. | Cumple | [rnf-03-sensor-20261110-104652.md](rnf-03-sensor-20261110-104652.md) |
| Frecuencia de reporte | Intervalo entre reportes periódicos aceptados ≤ 6,00 s y reporte por evento ante cambios. | Respaldo periódico: 54 intervalos, promedio 5,39 s, máximo 5,74 s. Por evento: 0 cambios, aceptados tras — s en promedio (máx. — s). | Cumple | [rnf-04-frecuencia-20261110-111031.md](rnf-04-frecuencia-20261110-111031.md) |
| Recuperación tras reinicio | Aplicar la orden pendiente sin repetirla y converger `desired`/`reported` en ≤ 30 s desde la liberación del reset. | 3/3 repeticiones con orden pendiente verificada, convergencia y sin repetir la orden; recuperación (desde la liberación del reset hasta reporte aceptado): promedio 8,19 s, máximo 9,67 s. | Cumple | [rnf-05-reinicio-20261110-103933.md](rnf-05-reinicio-20261110-103933.md) |
| Reconexión de red y sincronización | Aplicar la orden pendiente sin repetirla y converger `desired`/`reported` en ≤ 30 s desde `wifi_on`. | 3/3 repeticiones con orden pendiente verificada, convergencia y sin repetir la orden; recuperación (desde `wifi_on` hasta reporte aceptado): promedio 6,57 s, máximo 7,69 s. | Cumple | [rnf-06-reconexion-wifi-20261110-101936.md](rnf-06-reconexion-wifi-20261110-101936.md) |
