#!/usr/bin/env python3
# pip install boto3      (y credenciales con "aws configure"; nunca en archivos del repo)
"""Prueba la Lambda de la skill YA DESPLEGADA, sin pasar por Alexa.

Invoca la función con los mismos eventos que enviaría Alexa (casos_alexa.json),
con un usuario de prueba inventado, y verifica cada respuesta. Con --thing
también revisa que el Shadow quede como corresponde (desired.posicion, etc.).

Qué prueba: Lambda + permisos IAM + DynamoDB (vinculaciones y dispositivos) +
Shadow, en la nube real. Qué NO prueba: el reconocimiento de voz ni el diálogo
de confirmación del código (eso lo hace tools/probar_alexa.py).

Usa el Thing de prueba (sin ESP32) para no mover el tendedero físico:
  python tools/probar_lambda.py --funcion tendedero-inteligente-alexa \\
      --codigo 715204 --thing tendedero-prueba2

Al final desvincula al usuario de prueba y borra el pedido de calibración que dejó.
Deja un informe en resultados_p4/lambda-<fecha-hora>.md.
"""
import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CASOS = Path(__file__).with_name("casos_alexa.json")


def cargar_casos(ruta=CASOS):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))["casos"]


def evento(caso, usuario, codigo):
    req = caso["lambda"]
    base = {"requestId": f"prueba.{uuid.uuid4()}", "locale": "es-MX",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if req.get("tipo") == "LaunchRequest":
        request = {"type": "LaunchRequest", **base}
    else:
        slots = {n: {"name": n, "value": v.replace("{codigo}", codigo), "confirmationStatus": "CONFIRMED"}
                 for n, v in req.get("slots", {}).items()}
        request = {"type": "IntentRequest", "dialogState": "COMPLETED", **base,
                   "intent": {"name": req["intent"], "confirmationStatus": "NONE", "slots": slots}}
    return {"version": "1.0",
            "session": {"new": False, "sessionId": "amzn1.echo-api.session.prueba-automatica",
                        "application": {"applicationId": "amzn1.ask.skill.prueba"},
                        "user": {"userId": usuario}},
            "context": {"System": {"application": {"applicationId": "amzn1.ask.skill.prueba"},
                                   "user": {"userId": usuario}}},
            "request": request}


def texto(respuesta):
    ssml = (respuesta.get("response", {}).get("outputSpeech", {}) or {}).get("ssml", "")
    return re.sub(r"<[^>]+>", "", ssml).strip()


def valor(doc, ruta):
    for parte in ruta.split("."):
        if not isinstance(doc, dict):
            return None
        doc = doc.get(parte)
    return doc


def ejecutar(casos, invocar, leer_shadow=None, codigo="715204", usuario=None, ids=None):
    """invocar(evento) -> dict de respuesta; leer_shadow() -> state del Shadow o None."""
    usuario = usuario or f"amzn1.ask.account.PRUEBA-AUTOMATICA-{uuid.uuid4().hex[:8]}"
    filas = []
    for caso in casos:
        if "lambda" not in caso or (ids and caso["id"] not in ids):
            continue
        try:
            dicho = texto(invocar(evento(caso, usuario, codigo)))
            ok = bool(re.search(caso["espera"], dicho, re.I))
            detalle = dicho
        except Exception as exc:  # error de invocación o de permisos
            ok, detalle = False, f"ERROR: {exc}"
        if ok and caso.get("shadow") and leer_shadow:
            estado = leer_shadow()
            for ruta, esperado in caso["shadow"].items():
                real = valor(estado, ruta)
                if real != esperado:
                    ok, detalle = False, f"{detalle} | Shadow {ruta}={real!r}, se esperaba {esperado!r}"
        filas.append((caso["id"], caso["nombre"], "PASA" if ok else "FALLA", detalle))
        print(f"[{'PASA' if ok else 'FALLA'}] {caso['id']} {caso['nombre']}: {detalle}")
    return usuario, filas


def informe(filas, titulo):
    lineas = [f"# {titulo}", "", "| Caso | Nombre | Resultado | Respuesta |", "| --- | --- | --- | --- |"]
    lineas += [f"| {c} | {n} | {r} | {d.replace('|', '/')} |" for c, n, r, d in filas]
    pasan = sum(r == "PASA" for _, _, r, _ in filas)
    lineas += ["", f"{pasan} de {len(filas)} casos pasan."]
    return "\n".join(lineas) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--funcion", default="tendedero-inteligente-alexa")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--codigo", default="715204", help="código de la etiqueta del Thing de prueba")
    ap.add_argument("--thing", help="Thing de ese código, para verificar el Shadow")
    ap.add_argument("--casos", default=str(CASOS))
    ap.add_argument("--solo", nargs="*", help="ids de casos, p. ej. C06 C09")
    ap.add_argument("--salida", default=str(RAIZ / "resultados_p4"))
    a = ap.parse_args(argv)
    try:
        import boto3
    except ImportError:
        sys.exit("Falta boto3: pip install boto3")
    lam = boto3.client("lambda", region_name=a.region)
    datos = None
    if a.thing:
        ep = boto3.client("iot", region_name=a.region).describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]
        datos = boto3.client("iot-data", region_name=a.region, endpoint_url=f"https://{ep}")

    def invocar(ev):
        r = lam.invoke(FunctionName=a.funcion, Payload=json.dumps(ev).encode())
        cuerpo = json.loads(r["Payload"].read())
        if r.get("FunctionError"):
            raise RuntimeError(cuerpo.get("errorMessage", cuerpo))
        return cuerpo

    def leer_shadow():
        return json.loads(datos.get_thing_shadow(thingName=a.thing)["payload"].read())["state"]

    usuario, filas = ejecutar(cargar_casos(a.casos), invocar, leer_shadow if a.thing else None,
                              a.codigo, ids=a.solo)
    # Limpieza: el usuario de prueba no queda vinculado ni deja calibraciones pendientes.
    invocar(evento({"lambda": {"intent": "DesvincularThingIntent"}}, usuario, a.codigo))
    if datos:
        datos.update_thing_shadow(thingName=a.thing, payload=json.dumps(
            {"state": {"desired": {"calibracion_solicitada": None}}}).encode())
    Path(a.salida).mkdir(parents=True, exist_ok=True)
    ruta = Path(a.salida) / f"lambda-{datetime.now():%Y%m%d-%H%M%S}.md"
    ruta.write_text(informe(filas, f"Lambda {a.funcion} — {datetime.now():%Y-%m-%d %H:%M}"), encoding="utf-8")
    print(f"\nInforme: {ruta}")
    return 0 if all(r == "PASA" for _, _, r, _ in filas) else 1


if __name__ == "__main__":
    sys.exit(main())
