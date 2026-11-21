# Pruebas de la Práctica 4 (escritas antes que el código)

Estas pruebas describen lo que deben hacer las piezas nuevas de la P4. Mientras
una pieza no exista, sus pruebas se **omiten** (aparecen como `skipped`). Cuando
la creen, se ejecutan solas y dicen qué falta.

| Archivo de prueba | Pieza que prueba | Ruta esperada |
|---|---|---|
| `test_almacenamiento.py` | Lambda de almacenamiento (RF11, RF12) | `lambda/almacenamiento/lambda_function.py` |
| `test_logica.py` | Lambda de lógica, regla R4 | `lambda/logica/lambda_function.py` |
| `test_supervisor.py` | Lambda programada, reglas R2 y R3 | `lambda/supervisor/lambda_function.py` |
| `test_entregables.py` | Archivos que pide §6 del enunciado | `docs/`, `aws/`, `alexa/` |

`test_entregables.py` **no** se omite: falla mientras falte un entregable, como
lista de pendientes.

## Contrato que suponen las pruebas

Si el equipo decide otros nombres, cambien las rutas y constantes al inicio de
cada archivo de prueba; no hace falta reescribirlas.

- Cada Lambda expone `lambda_handler(event, context)`.
- La tabla de histórico se lee de la variable `DDB_HISTORY_TABLE`
  (por defecto `tendedero_historico`), con clave `thingName` + `sk`.
- `sk` empieza con `lectura#`, `evento#` o `alerta#`, seguido de la fecha ISO-8601 UTC.
- Cada ítem lleva `tipo` y `ttl` (epoch en segundos, en el futuro).
- Cada lectura guarda `ts_iot` (el `ts` de la regla, en ms) y `ts_guardado` (hora de
  la Lambda, en ms). Si el ESP32 envía `ts_dispositivo` (epoch en ms, por NTP), se
  copia. Con esas marcas `tools/medir_almacenamiento.py` calcula la latencia.
- Evento de la regla `tendedero_lecturas`: `{"reported": {...}, "thingName": "...", "ts": <ms>}`.
- Evento de las reglas `tendedero_cambios` y `tendedero_movimientos`:
  `{"actual": {...}, "anterior": {...}, "thingName": "...", "ts": <ms>}`.
- La lógica actúa solo con `iot-data.update_thing_shadow` sobre `desired`.
