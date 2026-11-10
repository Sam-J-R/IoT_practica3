# Práctica 3 — Tendedero inteligente con Alexa y AWS IoT Core

**SIS-234 · Grupo 6 · Entrega: 10/11/2026, 17:45 (Bolivia)**

Un ESP32 captura un sensor analógico MH y controla un servomotor. La Skill consulta y solicita posiciones a través de Lambda, DynamoDB y el Device Shadow del Thing vinculado. No hay cierre automático local ni LED como actuador.

## Informe y evidencias

El **[informe técnico completo](docs/INFORME.md)** concentra los requerimientos, arquitectura, circuito, clases, secuencias, contrato Shadow, configuraciones, pruebas, resultados y anexos exigidos. Se conservan también los registros específicos de cada área para mantener la trazabilidad de los aportes y sus evidencias.

- [Enunciado de la práctica](referencias/Práctica_3.md).
- [Documentación de configuración y pruebas de Alexa](docs/ALEXA.md).
- [Documentación original de evidencias AWS](docs/EVIDENCIAS_AWS.md).
- [Matriz de pruebas y registro del backend](docs/PRUEBAS.md).
- [Capturas de Alexa](docs/evidencias/alexa/README.md).
- [Paneles AWS y CSV](docs/evidencias/aws/README.md).
- [Videos de integración y recuperación](docs/evidencias/integracion/README.md).

Se demostraron operaciones por texto y actuación de servo de banco. La entrada textual corresponde a la limitación de micrófono del entorno. El informe distingue esa evidencia de una prueba de voz, cubierta bajo carga y mediciones RNF; no se atribuyen resultados no registrados.

## Firmware

Abrir `firmware/` en PlatformIO. Placa `esp32doit-devkit-v1`, serie 115200. Los pines del contrato son GPIO34 para sensor y GPIO26 para PWM.

| Perfil | Uso |
|---|---|
| `sensor_test` | Diagnóstico ADC sin red ni servo. |
| `servo_test` | Diagnóstico del servo por comandos serie `A`/`C`. |
| `sensor_shadow_test` | MQTT TLS y reporte ADC sin mover servo. |
| `tendedero_shadow` | Programa final, perfil predeterminado. |

Antes de la integración, copiar y completar localmente `firmware/include/secrets.example.h` como `secrets.h` y `calibracion.example.h` como `calibracion_local.h`. Los valores de calibración deben provenir del montaje. Sin credenciales y parámetros válidos, el programa final solo lee ADC.

Desde la raíz, con PlatformIO instalado:

```powershell
pio run -d firmware -e tendedero_shadow
pio run -d firmware -e tendedero_shadow -t upload
pio device monitor -d firmware -b 115200
```

Conexiones y procedimiento reproducible: [hardware/CONEXIONES.md](hardware/CONEXIONES.md) y [hardware/ENSAYO_BANCO.md](hardware/ENSAYO_BANCO.md). El servo necesita alimentación DC adecuada y GND común; no se alimenta desde GPIO ni 3V3.

## Backend y Skill

- [Manual de aprovisionamiento AWS](docs/GUIA_AWS.md).
- [Contrato operativo de atributos e intents](docs/CONTRATO.md).
- [Paquete y ejecución Lambda](lambda/README.md).
- [Modelo de interacción Alexa](alexa/README.md).

IoT Core, Lambda y DynamoDB utilizan `us-east-2`. El dispositivo físico es `tendedero-inteligente`; el de prueba es `tendedero-prueba2`. El modelo y las políticas se entregan como JSON sin credenciales en `alexa/` y `aws/`.

## Pruebas locales

Con Python compatible con `unittest.TestCase.enterContext` —por ejemplo Python 3.11— instalado:

```powershell
py -B -m unittest discover -s tests -v
```

Las pruebas utilizan el ASK SDK del ZIP y clientes AWS simulados. El informe conserva el resultado histórico y distingue las comprobaciones realizadas en la revisión actual. El fuente del handler y su copia en `lambda/lambda_deployment_p3.zip` coinciden; cualquier modificación del fuente exige reconstruir el paquete antes de desplegar.

No publicar `secrets.h`, `.env`, certificados, claves privadas, tokens de Skill I/O ni compilaciones con datos Wi-Fi. `.gitignore` no protege un archivo ya versionado o un ZIP construido manualmente.
