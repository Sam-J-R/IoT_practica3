# Práctica 3 — Tendedero inteligente con Alexa y AWS IoT Core

**SIS-234 · Grupo 6 · Entrega: martes 10/11/2026, 17:45 (Bolivia)**

Un ESP32 lee un sensor analógico MH y mueve una cubierta con un servomotor. La cubierta se controla **solo desde Alexa**, mediante Lambda y AWS IoT Core Device Shadow; el sensor se consulta por voz. No hay LEDs ni cierre automático local.

> **¿Se lo vas a pasar a una compañera?** Empieza por [`GUIA_PARA_COMPANERA.md`](GUIA_PARA_COMPANERA.md). Explica en palabras sencillas cómo funciona, qué hace cada archivo y qué le falta a cada responsable.

## Estructura mínima

| Carpeta | Contenido |
|---|---|
| `firmware/` | Código ESP32 orientado a objetos y perfiles PlatformIO |
| `lambda/` | Backend Alexa: vinculación por usuario y acceso a Shadow |
| `alexa/` | Modelo de interacción en español |
| `aws/` | Plantillas IoT, DynamoDB e IAM |
| `hardware/` | Conexiones y procedimiento de ensayo seguro |
| `docs/` | Contrato, diagramas, pruebas, informe y registro de cambios |
| `tests/` | Pruebas locales sin servicios AWS reales |
| `referencias/` | Enunciado original y fotografías del hardware |

## Firmware: qué ejecutar

Abre **únicamente la carpeta `firmware/`** en VS Code con PlatformIO. Placa: `esp32doit-devkit-v1`; monitor serie: 115200.

| Perfil | Para qué sirve |
|---|---|
| `sensor_test` | Leer GPIO34 sin Wi-Fi, servo ni AWS |
| `servo_test` | Probar apertura/cierre con comandos `A` y `C` en serie, sin AWS |
| `sensor_shadow_test` | Diagnosticar MQTT TLS y reporte ADC sin mover el servo |
| `tendedero_shadow` | **Programa final**: sensor + servo + Device Shadow |

En PowerShell, desde la raíz del repositorio:

```powershell
pio run -d firmware -e tendedero_shadow
pio run -d firmware -e tendedero_shadow -t upload
pio device monitor -b 115200
```

Para pruebas individuales, sustituye `tendedero_shadow` por el perfil correspondiente.

**Antes de cargar el perfil final:**

1. Conectar MH: `S → GPIO34`, `+ → 3V3`, `− → GND`.
2. Conectar señal del servo a GPIO26 y alimentarlo con una fuente DC regulada adecuada, **nunca desde un GPIO o 3V3**; unir tierras.
3. Copiar `firmware/include/secrets.example.h` a `secrets.h` y configurar Wi-Fi, endpoint, Thing y certificados AWS solo en la computadora local.
4. Copiar `calibracion.example.h` a `calibracion_local.h` e introducir **únicamente** umbrales y pulsos medidos con el hardware.
5. Configurar el Thing y su política IoT siguiendo `docs/GUIA_INTEGRACION.md`. Sin credenciales o calibración válida, el firmware final se mantiene en modo lectura ADC, sin activar el servo/MQTT.

No subir ni compartir `secrets.h`, certificados, claves privadas o compilaciones que puedan contener datos Wi-Fi.

## Integración de equipo

- **Samuel:** hardware, firmware y evidencias físicas.
- **Compañera AWS:** Thing, certificados, políticas, DynamoDB y Lambda.
- **Compañera Alexa:** Skill, frases de ejemplo, pruebas del simulador.

Contrato compartido: [`docs/CONTRATO.md`](docs/CONTRATO.md). No cambiar nombres de atributos del Shadow ni de intents sin coordinación.

## Verificación

```powershell
py -m unittest discover -s tests -v
```

Las pruebas locales utilizan el SDK incluido en `lambda/lambda_deployment_p3.zip` y servicios AWS simulados. **Que pasen no demuestra funcionamiento en AWS o Alexa reales.** El ZIP de Lambda coincide con el código fuente entregado; si se modifica Lambda, debe reconstruirse antes de desplegar.

- Estado verificado y pendientes: [`docs/ESTADO.md`](docs/ESTADO.md).
- Guía operativa de la responsable AWS: [`docs/GUIA_AWS.md`](docs/GUIA_AWS.md).
- Configuración y resultados de Alexa: [`docs/ALEXA.md`](docs/ALEXA.md).
- Capturas de configuración y pruebas de Alexa: [`docs/evidencias/alexa/README.md`](docs/evidencias/alexa/README.md).
- Videos de funcionamiento y recuperación de orden: [`docs/evidencias/integracion/README.md`](docs/evidencias/integracion/README.md).
- Guía de integración y demo: [`docs/GUIA_INTEGRACION.md`](docs/GUIA_INTEGRACION.md).
- Matriz de requisitos y pruebas: [`docs/PRUEBAS.md`](docs/PRUEBAS.md).
- Informe técnico: [`docs/INFORME.md`](docs/INFORME.md).
- Cambios de esta versión: [`docs/CAMBIOS_APLICADOS.md`](docs/CAMBIOS_APLICADOS.md).

El trabajo final requiere AWS/Alexa reales, pruebas medibles, evidencias y commits de cada integrante. El docente recibe el enlace al repositorio accesible en LMS-UCB.
