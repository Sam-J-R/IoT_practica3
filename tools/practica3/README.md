# Scripts de ensayo de la práctica 3

Estaban en la raíz del repositorio. Se movieron aquí por la observación de la práctica 3 («mover los scripts de ensayo a `tools/`»).

| Script | Qué hacía |
|---|---|
| `ensayo_rnf.py` | Ensayos RNF automáticos de la P3 (estabilidad, respuesta, sensor, frecuencia, reinicio, reconexión). |
| `orden_offline.py` | Dejaba una orden en `desired.cubierta` con el ESP32 apagado. |
| `analizar_rnf.py` | Analizaba los CSV de `grabar_rnf.py` de la P3. |

**Usan la cubierta de la P3** (`cubierta`, `abrir` / `cerrar`), así que **no funcionan con el firmware de la P4**. Se conservan porque generaron los resultados de `resultados/` y los documentos de la P3, que los citan con su ruta anterior. La entrega de la P3 completa sigue en la etiqueta `practica3-entrega`.

Para la P4 se usan:

| En lugar de… | Usar |
|---|---|
| `ensayo_rnf.py` | `tools/probar_esp32.py` (arranque, órdenes, frecuencia, persistencia, calibración, sensor, reconexión, edge, luz, sin conexión) |
| `orden_offline.py` | `tools/probar_esp32.py reconexion` |
| `analizar_rnf.py` | `tools/medir_intervalos.py` y `tools/medir_almacenamiento.py` |

`grabar_rnf.py` sigue sirviendo para ensayos manuales: está en `tools/` y ya usa los comandos de la P4.
