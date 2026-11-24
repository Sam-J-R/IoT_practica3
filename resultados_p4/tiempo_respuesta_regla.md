| Métrica | Resultado | Observaciones |
| :--- | :--- | :--- |
| **Tiempo de respuesta de una regla de la Nube que mueva el actuador (R2)** | **Medido: ~51 s (0,85 min)** de respuesta neta tras cumplirse el tiempo de espera configurado (`minutos_reexponer = 15`), completando el ciclo total en **15 min 51 s** desde `agua = 0` hasta el accionamiento del servo (`origen = nube`). | **Media.** Cumple satisfactoriamente con el umbral de diseño ($\le 5\text{ min}$ del supervisor en la Nube). Evidencia verificada mediante los registros del monitor serie del ESP32 y la sincronización del Device Shadow en AWS IoT. |

### Detalle de la corrida de prueba (Regla R2)

* **Condiciones iniciales:** Modo automático (`modo = automatico`), ambiente iluminado (`oscuro = 0`), brazo expuesto (`posicion = expuesto`) y tiempo de espera ajustado al mínimo operativo (`minutos_reexponer = 15`).
* **Resguardo local previo (R1):** Al detectar agua (`agua = 1`), el Edge resguardó el brazo localmente (`destino = resguardado`, `origen = edge`).
* **Retardo de seguridad:** Transcurrieron los **15 min** configurados con el sensor seco (`agua = 0`) y condiciones diurnas (`oscuro = 0`).
* **Respuesta de la Nube (R2):** Una vez cumplido el tiempo de espera, la regla R2 evaluó el estado en la Nube, actualizó `desired.posicion = "expuesto"` (`origen = nube`) en el Device Shadow y el ESP32 accionó el servo y confirmó el estado en `reported` en **~51 s**.