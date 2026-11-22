"""Lambda programada del tendedero: reglas R3 y R2 (Nube).

Se ejecuta con EventBridge (por defecto cada 5 minutos), sin mensaje del objeto.
Para cada tendedero registrado en la tabla de dispositivos:

R3: si no hay una lectura en los ultimos MINUTOS_SIN_REPORTE (5), registra una alerta
    "sin_reporte" (una sola por desconexion). El objeto no puede avisar de su
    propia desconexion, por eso esta regla va en la Nube.
R2: en modo automatico, si el Edge resguardo la ropa (R1 por lluvia o R5 por
    la noche), lleva al menos minutos_reexponer sin agua desde el ultimo evento
    de agua y hay luz, la vuelve a exponer escribiendo
    desired = {posicion: expuesto, origen: nube}. Asi, la ropa que se guardo de
    noche sale sola a la manana siguiente si no llueve. No toca un resguardo
    pedido por voz. Va en la Nube porque cruza el historico de lluvia con el
    estado actual de la luz.

Permisos: dynamodb:Scan sobre la tabla de dispositivos; dynamodb:Query y
dynamodb:PutItem sobre la de historico; iot:GetThingShadow e
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

HISTORICO = os.environ.get("DDB_HISTORY_TABLE", "tendedero_historico")
DISPOSITIVOS = os.environ.get("DDB_DEVICES_TABLE", "tendedero_dispositivos")
# 5 min = 5 reportes periodicos perdidos. Una caida breve de MQTT (medida: 134 s
# entre reportes, con reconexion en 11 s) no cuenta como desconexion: R1 y R5
# siguen funcionando en el ESP32 y el hueco se recupera solo.
MINUTOS_SIN_REPORTE = int(os.environ.get("MINUTOS_SIN_REPORTE", "5"))
DIAS_ALERTAS = int(os.environ.get("TTL_DIAS_EVENTOS", "365"))
EVENTOS_A_REVISAR = 50

_db = boto3.resource("dynamodb")
_historico = _db.Table(HISTORICO)
_dispositivos = _db.Table(DISPOSITIVOS)
_shadow = boto3.client("iot-data", region_name=os.environ.get("AWS_REGION"),
                       endpoint_url="https://" + os.environ["IOT_ENDPOINT"])


# ---------------------------------------------------------------- lecturas

def fecha_de(sk):
    """'lectura#2026-11-20T10:15:00.123+00:00' -> datetime (None si no se entiende)."""
    try:
        return datetime.fromisoformat(sk.split("#")[1])
    except (IndexError, ValueError):
        return None


def things():
    """Nombres de todos los tendederos registrados (Scan paginado; tabla pequena)."""
    nombres, inicio = [], None
    while True:
        args = {"ProjectionExpression": "thingName"}
        if inicio:
            args["ExclusiveStartKey"] = inicio
        respuesta = _dispositivos.scan(**args)
        nombres += [i["thingName"] for i in respuesta.get("Items", []) if i.get("thingName")]
        inicio = respuesta.get("LastEvaluatedKey")
        if not inicio:
            return nombres


def ultimos(thing, prefijo, limite):
    respuesta = _historico.query(
        KeyConditionExpression=Key("thingName").eq(thing) & Key("sk").begins_with(prefijo),
        ScanIndexForward=False, Limit=limite)
    return respuesta.get("Items", [])


def reported_de(thing):
    respuesta = _shadow.get_thing_shadow(thingName=thing)
    documento = json.loads(respuesta["payload"].read())
    return documento.get("state", {}).get("reported", {})


def guardar_alerta(thing, alerta, ahora, **detalle):
    _historico.put_item(Item={
        "thingName": thing, "sk": f"alerta#{ahora.isoformat(timespec='milliseconds')}#{alerta}",
        "tipo": "alerta", "alerta": alerta, "ttl": int(time.time()) + DIAS_ALERTAS * 86400,
        **detalle})


# ---------------------------------------------------------------- reglas

def revisar_r3(thing, ahora):
    """Devuelve True si el Thing reporto hace poco. Si no, registra la alerta una vez."""
    lectura = ultimos(thing, "lectura#", 1)
    ultima = fecha_de(lectura[0]["sk"]) if lectura else None
    if ultima and ahora - ultima <= timedelta(minutes=MINUTOS_SIN_REPORTE):
        return True
    alerta = ultimos(thing, "alerta#", 1)
    ya_avisado = alerta and alerta[0].get("alerta") == "sin_reporte" and (
        ultima is None or (fecha_de(alerta[0]["sk"]) or ahora) > ultima)
    if not ya_avisado:
        detalle = {"ultima_lectura": ultima.isoformat()} if ultima else {}
        guardar_alerta(thing, "sin_reporte", ahora, **detalle)
        logger.warning("R3: %s sin reportes desde %s", thing, ultima)
    return False


def revisar_r2(thing, reported, ahora):
    """Vuelve a exponer si el Edge resguardo, ya paso la espera sin agua y hay luz."""
    if (reported.get("modo") != "automatico" or reported.get("posicion") != "resguardado"
            or reported.get("origen") != "edge" or reported.get("agua_detectada") is not False):
        return False
    if reported.get("oscuro") is True:
        return False  # De noche no se expone: R5 la volveria a resguardar.
    espera = int(reported.get("minutos_reexponer") or 30)
    eventos_agua = [e for e in ultimos(thing, "evento#", EVENTOS_A_REVISAR) if e.get("cambio") == "agua"]
    if eventos_agua:
        if eventos_agua[0].get("agua_detectada") is not False:
            return False  # El ultimo evento dice que llovia: no se arriesga la ropa.
        seco_desde = fecha_de(eventos_agua[0]["sk"])
        if not seco_desde or ahora - seco_desde < timedelta(minutes=espera):
            return False
    # Sin lluvia en los ultimos eventos (p. ej. una noche seca), la espera ya se cumplio.
    _shadow.update_thing_shadow(thingName=thing, payload=json.dumps(
        {"state": {"desired": {"posicion": "expuesto", "origen": "nube"}}}))
    logger.info("R2: %s vuelve a exponerse tras %d min sin agua", thing, espera)
    return True


def lambda_handler(event, context):
    ahora = datetime.now(timezone.utc)
    resumen = {"revisados": 0, "sin_reporte": 0, "reexpuestos": 0}
    for thing in things():
        resumen["revisados"] += 1
        try:
            if not revisar_r3(thing, ahora):
                resumen["sin_reporte"] += 1
                continue  # Desconectado: no se le dan ordenes.
            if revisar_r2(thing, reported_de(thing), ahora):
                resumen["reexpuestos"] += 1
        except Exception:  # Un Thing con problemas no detiene la revision de los demas.
            logger.exception("Error al revisar %s", thing)
    return resumen
