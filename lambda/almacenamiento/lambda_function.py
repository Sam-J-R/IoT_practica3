"""Lambda de almacenamiento del tendedero (RF11, RF12).

Disparadores (reglas de AWS IoT, ver aws/reglas/):
- tendedero_lecturas: {"reported": {...}, "thingName": "...", "ts": <ms>}
  -> una lectura (sk = "lectura#<fecha ISO>") con SOLO los datos de los sensores.
     Se guarda una por mensaje publicado: asi se mide la integridad (RNF).
- tendedero_cambios: {"actual": {...}, "anterior": {...}, "thingName": "...", "ts": <ms>}
  -> un evento por cada cambio de posicion, agua, modo, LED o luz ambiente
     (sk = "evento#<fecha ISO>#<cambio>"). La regla entrega todos los documentos
     y esta Lambda compara: asi tambien se guarda el primer cambio de un campo
     que el documento anterior no tenia.

Que se guarda y para que (ver docs/practica4/CONTRATO.md, "Modelo del historico"):
- Lecturas (TTL 30 dias): curva de luz por hora (reporte "mejor momento para
  tender"), deriva del sensor de agua y verificacion de los RNF.
- Eventos (TTL 365 dias): horas expuesta, lluvias, noches y quien movio el
  tendedero. Los de posicion guardan ademas si habia agua y si era de noche,
  para distinguir la proteccion por lluvia (R1) de la de la noche (R5).
- Posicion, modo, origen y LED no se repiten en las lecturas: ya estan en los eventos.

Valida tipos y rangos y descarta el mensaje completo si un campo conocido es
invalido. Agrega thingName, marcas de tiempo (ts_iot de la regla, ts_guardado de
esta Lambda y ts_dispositivo del ESP32 si viene) y ttl.

Permiso necesario: dynamodb:PutItem sobre la tabla de historico. Nada mas.
"""

import logging
import os
import time
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLA = os.environ.get("DDB_HISTORY_TABLE", "tendedero_historico")
DIAS_LECTURAS = int(os.environ.get("TTL_DIAS_LECTURAS", "30"))
DIAS_EVENTOS = int(os.environ.get("TTL_DIAS_EVENTOS", "365"))

POSICIONES = ("expuesto", "resguardado")
MODOS = ("manual", "automatico")
ORIGENES = ("voz", "edge", "nube")
ESTADOS_LED = ("encendido", "apagado")

_tabla = boto3.resource("dynamodb").Table(TABLA)


class MensajeInvalido(ValueError):
    """El mensaje no cumple el contrato del Shadow y no se guarda."""


# ---------------------------------------------------------------- validacion

def _entero(valor, minimo, maximo, campo):
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
        raise MensajeInvalido(f"{campo}={valor!r} fuera de rango {minimo}..{maximo}")
    return valor


def _opcion(valor, opciones, campo):
    if valor not in opciones:
        raise MensajeInvalido(f"{campo}={valor!r} no es uno de {opciones}")
    return valor


def _booleano(valor, campo):
    if not isinstance(valor, bool):
        raise MensajeInvalido(f"{campo}={valor!r} no es booleano")
    return valor


# Campos del reported que se guardan. Los que valen null (sin dato) se omiten.
VALIDADORES = {
    "lectura_adc": lambda v: _entero(v, 0, 4095, "lectura_adc"),
    "agua_detectada": lambda v: _booleano(v, "agua_detectada"),
    "posicion": lambda v: _opcion(v, POSICIONES, "posicion"),
    "modo": lambda v: _opcion(v, MODOS, "modo"),
    "minutos_reexponer": lambda v: _entero(v, 15, 240, "minutos_reexponer"),
    "origen": lambda v: _opcion(v, ORIGENES, "origen"),
    "ts_dispositivo": lambda v: _entero(v, 1, 10**14, "ts_dispositivo"),
    # Luz automatica (LDR + LED).
    "luz_adc": lambda v: _entero(v, 0, 4095, "luz_adc"),
    "oscuro": lambda v: _booleano(v, "oscuro"),
    "led": lambda v: _opcion(v, ESTADOS_LED, "led"),
    "origen_led": lambda v: _opcion(v, ORIGENES, "origen_led"),
    "luz_simulada": lambda v: _booleano(v, "luz_simulada"),
}


# Campos de los sensores: lo unico que guarda una lectura.
SENSORES = ("lectura_adc", "agua_detectada", "luz_adc", "oscuro", "luz_simulada", "ts_dispositivo")
# Contexto que se guarda con cada evento de posicion: por que se movio.
CONTEXTO_POSICION = ("agua_detectada", "oscuro")


def validar_reported(reported):
    """Devuelve solo los campos conocidos, validados. Lanza MensajeInvalido."""
    if not isinstance(reported, dict):
        raise MensajeInvalido("reported no es un objeto")
    return {campo: VALIDADORES[campo](valor) for campo, valor in reported.items()
            if campo in VALIDADORES and valor is not None}


def validar_base(evento):
    thing = evento.get("thingName")
    if not isinstance(thing, str) or not thing:
        raise MensajeInvalido("falta thingName")
    ts = _entero(evento.get("ts"), 1, 10**14, "ts")
    return thing, ts


# ---------------------------------------------------------------- items

def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="milliseconds")


def _comunes(thing, ts, tipo, dias):
    ahora = time.time()
    return {"thingName": thing, "tipo": tipo, "ts_iot": ts,
            "ts_guardado": int(ahora * 1000), "ttl": int(ahora) + dias * 86400}


def item_lectura(thing, ts, valores):
    sensores = {campo: valores[campo] for campo in SENSORES if campo in valores}
    return {**_comunes(thing, ts, "lectura", DIAS_LECTURAS), "sk": f"lectura#{iso(ts)}", **sensores}


def items_eventos(thing, ts, actual, anterior):
    """Un evento por cada atributo que cambio entre el documento anterior y el actual."""
    eventos = []
    cambios = (("posicion", "posicion"), ("agua", "agua_detectada"), ("modo", "modo"),
               ("led", "led"), ("luz", "oscuro"))
    for cambio, campo in cambios:
        if campo not in actual or actual.get(campo) == anterior.get(campo):
            continue
        item = {**_comunes(thing, ts, "evento", DIAS_EVENTOS),
                "sk": f"evento#{iso(ts)}#{cambio}", "cambio": cambio, campo: actual[campo]}
        if cambio == "posicion":
            if "origen" in actual:
                item["origen"] = actual["origen"]
            item.update({c: actual[c] for c in CONTEXTO_POSICION if c in actual})
        if cambio == "led" and "origen_led" in actual:
            item["origen_led"] = actual["origen_led"]
        if cambio == "luz" and actual.get("luz_simulada") is True:
            item["luz_simulada"] = True
        if "ts_dispositivo" in actual:
            item["ts_dispositivo"] = actual["ts_dispositivo"]
        eventos.append(item)
    return eventos


def _sin_origen_invalido(reported):
    """Un origen invalido no descarta el evento del actuador: se guarda sin origen."""
    for campo in ("origen", "origen_led"):
        if isinstance(reported, dict) and reported.get(campo) not in (None, *ORIGENES):
            logger.warning("%s invalido descartado: %r", campo, reported.get(campo))
            reported = {k: v for k, v in reported.items() if k != campo}
    return reported


# ---------------------------------------------------------------- handler

def lambda_handler(event, context):
    try:
        thing, ts = validar_base(event)
        if "reported" in event:
            valores = validar_reported(event["reported"])
            if not any(campo in valores for campo in SENSORES):
                return {"guardados": 0, "motivo": "sin datos de sensores"}
            items = [item_lectura(thing, ts, valores)]
        elif "actual" in event:
            actual = validar_reported(_sin_origen_invalido(event["actual"]))
            anterior = validar_reported(_sin_origen_invalido(event.get("anterior") or {}))
            items = items_eventos(thing, ts, actual, anterior)
        else:
            raise MensajeInvalido("el evento no trae reported ni actual")
    except MensajeInvalido as exc:
        logger.warning("Mensaje descartado: %s | evento=%s", exc, event)
        return {"guardados": 0, "descartado": str(exc)}

    for item in items:
        _tabla.put_item(Item=item)
    logger.info("Guardados %d items de %s", len(items), thing)
    return {"guardados": len(items)}
