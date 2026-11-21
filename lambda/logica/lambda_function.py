"""Lambda de logica de negocio del tendedero: regla R4 (Nube).

R4: si el brazo se movio mas de LIMITE_MOVIMIENTOS_HORA veces en la ultima hora
estando en modo automatico, pasar a modo manual y registrar una alerta. Protege
el servo cuando la lluvia es intermitente y R1 lo mueve una y otra vez.

Disparador: regla de AWS IoT tendedero_movimientos (cambios de posicion en modo
automatico, desde $aws/things/+/shadow/update/documents):
    {"actual": {...}, "anterior": {...}, "thingName": "...", "ts": <ms>}

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

_tabla = boto3.resource("dynamodb").Table(TABLA)
_shadow = boto3.client("iot-data", region_name=os.environ.get("AWS_REGION"),
                       endpoint_url="https://" + os.environ["IOT_ENDPOINT"])


def movimientos_ultima_hora(thing, ahora):
    """Eventos de posicion guardados por la Lambda de almacenamiento en la ultima hora."""
    desde = (ahora - timedelta(hours=1)).isoformat(timespec="milliseconds")
    # "evento$" es la primera clave posterior a todas las "evento#...": "$" sigue a "#".
    respuesta = _tabla.query(
        KeyConditionExpression=Key("thingName").eq(thing)
        & Key("sk").between(f"evento#{desde}", "evento$"))
    return [i for i in respuesta.get("Items", []) if i.get("cambio") == "posicion"]


def pasar_a_manual(thing, movimientos, ahora):
    _shadow.update_thing_shadow(
        thingName=thing, payload=json.dumps({"state": {"desired": {"modo": "manual"}}}))
    _tabla.put_item(Item={
        "thingName": thing,
        "sk": f"alerta#{ahora.isoformat(timespec='milliseconds')}#exceso_movimientos",
        "tipo": "alerta", "alerta": "exceso_movimientos", "movimientos": movimientos,
        "limite": LIMITE, "ttl": int(time.time()) + DIAS_ALERTAS * 86400})


def lambda_handler(event, context):
    thing = event.get("thingName")
    actual = event.get("actual") or {}
    if not thing or actual.get("modo") != "automatico":
        return {"accion": "ninguna", "motivo": "sin thing o no esta en automatico"}

    ahora = datetime.now(timezone.utc)
    cantidad = len(movimientos_ultima_hora(thing, ahora))
    if cantidad <= LIMITE:
        return {"accion": "ninguna", "movimientos": cantidad}

    pasar_a_manual(thing, cantidad, ahora)
    logger.warning("R4: %s se movio %d veces en una hora; pasa a manual", thing, cantidad)
    return {"accion": "modo_manual", "movimientos": cantidad}
