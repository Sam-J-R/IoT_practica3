#!/usr/bin/env python3
# pip install paho-mqtt
"""Deja una orden pendiente en el Device Shadow y/o lee el Shadow, usando el certificado del dispositivo.

SOLO para el ensayo de reconexión, MIENTRAS EL ESP32 ESTÁ DESCONECTADO (Wi-Fi apagado o sin
alimentación). La política del certificado solo permite conectar con clientId = nombre del Thing;
si el ESP32 está en línea, AWS lo desconecta al entrar este cliente con el mismo ID.
El PC debe tener Internet por otra vía (no por el punto de acceso que se apaga).

Ejemplos:
  python orden_offline.py --endpoint XXX-ats.iot.us-east-2.amazonaws.com --thing tendedero-inteligente \
      --ca AmazonRootCA1.pem --cert cert.pem.crt --key private.pem.key --posicion cerrada --csv rnf-05.csv
  (sin --posicion solo lee el Shadow)
"""
import argparse
import csv
import json
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--endpoint", required=True)
ap.add_argument("--thing", required=True)
ap.add_argument("--ca", required=True)
ap.add_argument("--cert", required=True)
ap.add_argument("--key", required=True)
ap.add_argument("--posicion", choices=["abierta", "cerrada"])
ap.add_argument("--csv", help="CSV de grabar_rnf.py donde añadir la marca 'orden'")
ap.add_argument("--si", action="store_true", help="no preguntar si el ESP32 está desconectado")
a = ap.parse_args()

if not a.si:
    r = input("¿El ESP32 está DESCONECTADO de la red ahora mismo? (s/n): ").strip().lower()
    if r != "s":
        raise SystemExit("Cancelado: con el ESP32 en línea ambos clientes se expulsarían mutuamente.")

base = f"$aws/things/{a.thing}/shadow"
temas = [base + t for t in ("/update/accepted", "/update/rejected", "/get/accepted", "/get/rejected")]
conectado, suscrito, upd, get = (threading.Event() for _ in range(4))
res = {}


def marca(dato):
    t = time.time()
    if a.csv:
        with open(a.csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["marca", f"{t:.3f}", datetime.fromtimestamp(t).isoformat(timespec="milliseconds"), dato])
    return t


def on_connect(c, u, flags, rc, props=None):
    print(f"MQTT conectado rc={rc}")
    if not rc.is_failure:
        conectado.set()
        c.subscribe([(t, 1) for t in temas])


def on_subscribe(c, u, mid, rcs, props=None):
    fallos = [r for r in rcs if r.is_failure]
    if fallos:
        print("Suscripción rechazada:", fallos)
    suscrito.set()


def on_message(c, u, m):
    doc = json.loads(m.payload or b"{}")
    if m.topic.startswith(base + "/update/"):
        res["update"] = (m.topic, doc)
        upd.set()
    elif m.topic.startswith(base + "/get/"):
        res["get"] = (m.topic, doc)
        get.set()


cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=a.thing)
cli.tls_set(ca_certs=a.ca, certfile=a.cert, keyfile=a.key)
cli.on_connect, cli.on_subscribe, cli.on_message = on_connect, on_subscribe, on_message
cli.connect(a.endpoint, 8883, 30)
cli.loop_start()
if not (conectado.wait(15) and suscrito.wait(10)):
    cli.loop_stop()
    raise SystemExit("No se pudo conectar/suscribir. Revisa endpoint, certificados e Internet del PC.")

if a.posicion:
    t = marca("orden")
    cli.publish(base + "/update", json.dumps({"state": {"desired": {"cubierta": a.posicion}}}), qos=1)
    print(f"{datetime.fromtimestamp(t):%H:%M:%S.%f} orden publicada: desired.cubierta={a.posicion}")
    if upd.wait(10):
        print("Respuesta:", res["update"][0].rsplit("/", 1)[-1])
    else:
        print("Sin respuesta de update en 10 s")

cli.publish(base + "/get", "", qos=1)
if get.wait(10):
    tema, doc = res["get"]
    st = doc.get("state", {})
    print("\nShadow (", tema.rsplit("/", 1)[-1], ") versión", doc.get("version"))
    print("  desired.cubierta :", st.get("desired", {}).get("cubierta"))
    print("  reported.cubierta:", st.get("reported", {}).get("cubierta"))
    print("  delta            :", st.get("delta"))
    nombre = f"shadow-{datetime.now():%Y%m%d-%H%M%S}.json"
    with open(nombre, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("Documento guardado en", nombre)
else:
    print("Sin respuesta de get en 10 s")

cli.disconnect()
cli.loop_stop()
