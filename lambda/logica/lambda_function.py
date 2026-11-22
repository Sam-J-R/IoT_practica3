"""Lambda de logica de negocio del tendedero: regla R4 (Nube).

R4: si el brazo se movio mas de LIMITE_MOVIMIENTOS_HORA veces en la ultima hora
estando en modo automatico, duplica minutos_reexponer (con tope de 240) y
registra una alerta.

Por que duplicar la espera: con lluvia intermitente y una espera corta, R2
vuelve a exponer la ropa entre un chubasco y otro, y R1 la resguarda con cada
lluvia nueva. Esperar mas antes de volver a exponer frena ese vaiven. El modo
no cambia, asi que R1 sigue protegiendo la ropa. La espera nueva queda en el
Shadow: Alexa la dice al consultar el modo y el usuario la puede cambiar por voz.

Disparador: regla de AWS IoT tendedero_movimientos (cambios de posicion en modo
automatico, desde $aws/things/+/shadow/update/documents):
    {"actual": {...}, "anterior": {...}, "thingName": "...", "ts": <ms>}

La misma publicacion dispara en paralelo la Lambda de almacenamiento, que guarda
este movimiento. Por eso se cuentan los movimientos anteriores a este mensaje y
se suma este: el resultado no depende de cual de las dos termine antes.

Actua sobre el objeto solo a traves de desired (nunca escribe reported).
Permisos: dynamodb:Query y dynamodb:PutItem sobre la tabla de historico,
iot:UpdateThingShadow sobre los Things del tendedero.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLA = os.environ.get("DDB_HISTORY_TABLE", "tendedero_historico")
LIMITE = int(os.environ.get("LIMITE_MOVIMIENTOS_HORA", "6"))
DIAS_ALERTAS = int(os.environ.get("TTL_DIAS_EVENTOS", "365"))
# Mismos valores que config.h del ESP32.
MINUTOS_INICIAL, MINUTOS_MAX = 30, 240
# Dos movimientos del brazo no caben en un segundo (el servo tarda mas en llegar):
# lo guardado en ese margen antes del mensaje es este mismo movimiento.
MARGEN_MISMO_MOVIMIENTO = timedelta(seconds=1)

_tabla = boto3.resource("dynamodb").Table(TABLA)
_shadow = boto3.client("iot-data", region_name=os.environ.get("AWS_REGION"),
                       endpoint_url="https://" + os.environ["IOT_ENDPOINT"])


def iso(momento):
    """Mismo formato de fecha que usa la Lambda de almacenamiento en las claves."""
    return momento.isoformat(timespec="milliseconds")


def movimientos_previos(thing, momento):
    """Eventos de posicion de la hora anterior a este mensaje, sin incluirlo."""
    respuesta = _tabla.query(
        KeyConditionExpression=Key("thingName").eq(thing) & Key("sk").between(
            f"evento#{iso(momento - timedelta(hours=1))}",
            f"evento#{iso(momento - MARGEN_MISMO_MOVIMIENTO)}"))
    return [i for i in respuesta.get("Items", []) if i.get("cambio") == "posicion"]


def duplicar_espera(thing, actual, nueva, movimientos, momento):
    _shadow.update_thing_shadow(
        thingName=thing, payload=json.dumps({"state": {"desired": {"minutos_reexponer": nueva}}}))
    _tabla.put_item(Item={
        "thingName": thing,
        "sk": f"alerta#{iso(momento)}#exceso_movimientos",
        "tipo": "alerta", "alerta": "exceso_movimientos", "movimientos": movimientos,
        "limite": LIMITE, "minutos_antes": actual, "minutos_despues": nueva,
        "ttl": int(time.time()) + DIAS_ALERTAS * 86400})


def lambda_handler(event, context):
    thing = event.get("thingName")
    actual = event.get("actual") or {}
    if not thing or actual.get("modo") != "automatico":
        return {"accion": "ninguna", "motivo": "sin thing o no esta en automatico"}

    ts = event.get("ts")
    momento = (datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if isinstance(ts, (int, float))
               else datetime.now(timezone.utc))
    cantidad = len(movimientos_previos(thing, momento)) + 1  # +1: este movimiento
    # Solo al cruzar el limite: los movimientos siguientes de la misma hora no
    # vuelven a duplicar la espera (30 -> 60, no 30 -> 60 -> 120 -> 240).
    if cantidad != LIMITE + 1:
        return {"accion": "ninguna", "movimientos": cantidad}

    minutos = actual.get("minutos_reexponer")
    minutos = minutos if isinstance(minutos, int) else MINUTOS_INICIAL
    nueva = min(minutos * 2, MINUTOS_MAX)
    if nueva == minutos:
        return {"accion": "ninguna", "motivo": "la espera ya esta en el maximo", "movimientos": cantidad}

    duplicar_espera(thing, minutos, nueva, cantidad, momento)
    logger.warning("R4: %s se movio %d veces en una hora; espera %d -> %d min",
                   thing, cantidad, minutos, nueva)
    return {"accion": "duplicar_espera", "movimientos": cantidad, "minutos": nueva}
