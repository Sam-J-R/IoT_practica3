# Informe de cambios específicos — versión simplificada

**Fecha:** 7 de noviembre de 2026. **Origen:** copia de `IoT-prueba.rar`, contrastada con `Práctica_3(2).md`. **Alcance:** limpieza, explicaciones de código y mejoras de documentación; no se tocó el archivo original ni se realizaron cambios en AWS, Alexa Developer Console o GitHub.

## Segunda revisión: hacerlo entendible para la compañera

La primera revisión redujo el peso del paquete. **La segunda se centró en que una persona del equipo pueda comprenderlo sin conocer todo el historial de desarrollo.** Se mantuvo el contrato de integración y no se cambió la lógica de control remoto.

| Archivo | Última modificación y para qué sirve |
|---|---|
| `GUIA_PARA_COMPANERA.md` | **Nuevo punto de entrada.** Explica el recorrido voz→Lambda→Shadow→servo, un diccionario de términos, el papel de cada archivo, las tareas de cada compañera y lo que falta verificar. |
| `README.md` | Incluye una referencia visible a la guía de traspaso para que se encuentre al abrir el repositorio. |
| `firmware/src/Tendedero.cpp` | Encabezado con las cuatro responsabilidades del programa, comentarios de los cinco pasos de `loop()`, aclaración del estado de sensor `-1/0/1` y separación de `calibracionValida()` en dos comprobaciones legibles (`sensorValido` y `servoValido`). **No cambia la condición lógica de habilitación.** |
| `firmware/include/SensorAgua.h` | Comentarios que explican qué entrega el ADC y para qué sirven los dos umbrales (histéresis). Sin cambios de lectura ni clasificación. |
| `firmware/include/ServoCubierta.h` | Explica pulsos en microsegundos, movimientos solicitados y por qué `estimada()` no confirma mecánicamente la posición. Sin alterar el PWM. |
| `firmware/include/ClienteShadow.h` | Presenta la responsabilidad de la clase y diferencia eventos MQTT, deltas y reportes aceptados. Sin cambios de interfaz pública. |
| `firmware/src/ClienteShadow.cpp` | Comentarios junto a `get`, `delta`, `clientToken`, cola de eventos, reintentos y `reported` para explicar el mecanismo ya implementado. **No altera los tópicos ni el procesamiento.** |
| `docs/CAMBIOS_APLICADOS.md` | Se añade esta segunda fase para diferenciar las mejoras de comprensión de la limpieza inicial. |

**Decisión técnica:** conservar la gestión de reconexiones, versiones y confirmaciones aunque sea más extensa. Es necesaria para la estabilidad exigida y simplificarla eliminando controles podría romper RF2/RF3. La guía y los comentarios facilitan su lectura sin quitar esas protecciones.

**No se tocaron** `lambda/lambda_function.py`, su ZIP de despliegue, el modelo de Alexa, las políticas AWS, `docs/CONTRATO.md` ni los nombres de atributos. Cada compañera puede continuar sobre los mismos nombres sin adaptar interfaces.

### Verificaciones de esta segunda revisión

- [x] Se ejecutó de nuevo la suite local: **12/12** pruebas satisfactorias.
- [x] Se verificó el código Lambda dentro de su ZIP: coincide byte por byte con `lambda_function.py`. El paquete final incluye la guía y este informe.
- [x] Los cuatro perfiles compilaron correctamente en PlatformIO el 7/11/2026; la compilación no sustituye la carga ni la prueba física.
- [ ] Probar conexión AWS y movimiento por Alexa en el hardware del equipo; no se afirmó como realizado.

---

## Primera revisión: limpieza y simplificación técnica

### Resumen de la decisión

Conservar las clases y el contrato funcional RF1–RF9; retirar pruebas obsoletas y archivos regenerables; mejorar mensajes de errores MQTT sin reescribir el protocolo; actualizar la documentación con las pruebas efectivamente realizadas.

### Registro exacto de archivos

| Archivo | Antes | Cambio realizado |
|---|---|---|
| `firmware/platformio.ini` | `sensor_led_test` era el perfil por defecto; había cinco perfiles | Por defecto `tendedero_shadow`; cuatro perfiles: `sensor_test`, `servo_test`, `sensor_shadow_test`, `tendedero_shadow` |
| `firmware/src/main.cpp` | Prueba temporal ADC + LED GPIO25 | Sustituido por `firmware/src/SensorTest.cpp`, que **solo** lee GPIO34 cada 500 ms |
| `firmware/src/WifiSensorTest.cpp` | Diagnóstico Wi-Fi/ADC separado | No incluido en el paquete simplificado; la reconexión Wi-Fi previa quedó documentada |
| `firmware/include/config.h` | Constante `PIN_LED_PRUEBA = 25` | Eliminada. Se conservan GPIO34 (sensor) y GPIO26 (servo) |
| `.gitignore` | Ignoraba PEM, KEY y secretos locales | Añadidas extensiones de certificados `.crt`, `.cer` y `.der` para reducir riesgo de publicación accidental |
| `firmware/include/ClienteShadow.h` | No declaraba método propio para suscripciones | Se declaró `suscribir()` para reutilizar la lógica de conexión/reintento |
| `firmware/src/ClienteShadow.cpp` | Ignoraba retornos inmediatos de `subscribe` y `enqueue` | Registra fallo de suscripción, solicitudes `get` y publicaciones `reported`; reintenta suscripciones y GET mientras no sincroniza |
| `tests/test_static_contract.py` | Pruebas ligadas a LED y diagnóstico Wi-Fi antiguo | Adaptadas a los perfiles actuales y añadida comprobación de los controles de error MQTT |
| `README.md` | Instrucciones de traspaso con tareas ya superadas | Reescrito como guía corta de estructura, perfiles y ejecución |
| `hardware/CONEXIONES.md` | Incluía LED temporal y servo pendiente | Quitada sección LED; se registra prueba local del servo informada por Samuel |
| `hardware/ENSAYO_BANCO.md` | Indicaba entorno `sensor_led_test` y llegada futura del servo | Actualizado a `sensor_test` y al estado reportado por Samuel |
| `docs/ESTADO.md` | Decía que el servo no había llegado y no existían pruebas físicas | Reescrito con resultados declarados, 12 pruebas locales y pendientes reales |
| `docs/PRUEBAS.md` | Marcaba todas las actividades como pendientes | Distingue evidencia parcial física, simulaciones locales y ausencia de pruebas AWS reales |
| `docs/INFORME.md` | Citaba `main.cpp`/calibración como si estuviese definida | Actualizado a `SensorTest.cpp`; separa resultados físicos de integración no demostrada |
| `docs/GUIA_INTEGRACION.md` | No existía | Nueva guía corta por responsable, instrucciones de integración y checklist de entrega |
| `docs/CAMBIOS_APLICADOS.md` | No existía | Informe de esta intervención |

### Material retirado solo de la copia de entrega

- `firmware/.pio/`: compilaciones antiguas, objetos y cachés.
- `lambda/.venv/`: paquetes y entorno virtual regenerables.
- `firmware/include/secrets.h`: **contenía valores de SSID y contraseña Wi-Fi**; no se incluyen esos valores en el paquete ni se reproducen aquí. La plantilla `secrets.example.h` permanece vacía.
- `docs/PLAN.md`, `docs/GUIA_ENTREGA_SAMUEL.md`, `AGENTS.md` y `CODEX_HANDOFF.md`: documentos de traspaso/planificación con instrucciones redundantes u obsoletas. Las evidencias útiles se integraron en `ESTADO.md` y `PRUEBAS.md`.
- Compilaciones, cachés Python y otros archivos temporales; sin alterar el original.

### Conservado intencionalmente

- `firmware/src/Tendedero.cpp`, `SensorAgua.h`, `ServoCubierta.h`: código principal modular con calibración segura (sin parámetros inventados); en la segunda fase recibieron comentarios y una presentación más clara, sin cambiar su comportamiento previsto.
- `lambda/lambda_function.py`, `alexa/interaction-model-es-MX.json`, `aws/`: **sin cambios**, para respetar el contrato acordado con las compañeras.
- `docs/CONTRATO.md`, `docs/DIAGRAMAS.md`: contrato y diagramas de arquitectura/flujo.
- `lambda/lambda_deployment_p3.zip`: SDK y función coincidentes con el fuente; útil para ejecutar pruebas offline y despliegue cuando se autorice.
- `referencias/Práctica_3.md` y fotos del hardware; todas las plantillas sin secretos.

### Verificación y límites

1. **12/12 pruebas locales satisfactorias** en esta copia (original 11/11). Incluye rutas Lambda multiusuario simuladas y verificaciones estáticas de contratos y perfiles.
2. JSON de Alexa y políticas AWS parseados correctamente por la suite; ZIP de Lambda coincide byte por byte con el fuente incluido.
3. Los cuatro perfiles del firmware ESP32 se compilaron correctamente en PlatformIO el 7/11/2026. Aún requieren carga y validación física en el dispositivo.
4. No hubo acceso a Thing, DynamoDB, Lambda o Skill reales. RF1–RF9 siguen pendientes de demostración extremo a extremo y mediciones RNF.
5. La prueba física del servo se basa en el reporte de Samuel; aún faltan pulsos calibrados, tensión y evidencia integrada.

### Advertencia de seguridad

**`.gitignore` no protege un ZIP/RAR que se construye incluyendo todos los archivos manualmente.** El archivo original contenía `secrets.h` con Wi-Fi configurado y resultados compilados que podrían incorporar esa información. En esta copia no se incluyen. Si el original llegó a un repositorio público o a terceros, cambiar la contraseña Wi-Fi.

### Siguiente paso seguro

Recompilar `tendedero_shadow` en la computadora de Samuel, conectar AWS usando secretos locales, integrar con la Skill real y medir/documentar RF y RNF. No afirmar entrega completa hasta observar la cadena voz→servo y sincronización Shadow.
