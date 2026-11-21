# Herramientas de prueba y medición (P4)

Ninguna guarda claves en archivos. Las que usan AWS toman las credenciales de
`aws configure`; las de Alexa, de `ask configure`. Los informes quedan en
`resultados_p4/`.

## Pruebas del sistema real

| Script | Qué prueba | Necesita | ¿Cambia algo? |
|---|---|---|---|
| `probar_esp32.py` | Firmware en el ESP32 por el monitor serie: arranque, órdenes, frecuencia, persistencia, calibración (guiada), sensor (guiada), reconexión | `pyserial`, perfil `tendedero_ensayo` cargado | Mueve el servo; `calibracion` cambia los umbrales; `reconexion` escribe `desired` (boto3) |
| `verificar_aws.py` | Configuración de AWS (§7 de `docs/practica4/GUIA_AWS.md`): tablas, índice, códigos, política IoT, certificado, rol, Lambda y ZIP desplegado, Shadows | `boto3` | Solo lee. Con `--e2e N` mueve el tendedero físico |
| `probar_lambda.py` | Lambda desplegada con los eventos de `casos_alexa.json` y un usuario de prueba | `boto3` | Escribe `desired` del Thing de prueba; al final desvincula y limpia |
| `probar_alexa.py` | Skill completa en el simulador (`ask dialog --replay`) o lista para la prueba manual (`--manual`) | ASK CLI v2 | Desvincula al usuario de la consola al final |
| `casos_alexa.json` | Frases, eventos y respuestas esperadas que usan los dos anteriores | — | — |

## Mediciones (RNF)

| Script | Qué mide | Necesita |
|---|---|---|
| `medir_almacenamiento.py` | Integridad (% de reportes guardados) y latencia de almacenamiento | `log.csv` de `probar_esp32.py` + ítems de DynamoDB (exportados o con `boto3`) |
| `medir_intervalos.py` | Tiempo entre dos líneas del log (respuesta del Edge, reconexión, etc.) | `log.csv` de `probar_esp32.py` |
| `estimar_costo.py` | Consumo mensual frente a la capa gratuita | Solo parámetros |

`probar_esp32.py` escribe el log con el mismo formato que `grabar_rnf.py`
(fuente, epoch, hora, dato), así que los scripts de medición sirven con ambos.

## Pruebas de estas herramientas

Todas tienen pruebas sin hardware ni cuenta de AWS, que corren con el resto:

```bash
python -m pytest tests -v
```

- `tests/test_probar_esp32.py`: ESP32 simulado que reproduce el defecto 1.
- `tests/test_herramientas_nube.py`: `probar_lambda` contra la Lambda real del
  repositorio con AWS simulado, `probar_alexa` y `verificar_aws` con clientes falsos.
