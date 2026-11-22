#!/usr/bin/env python3
# pip install boto3      (credenciales con "aws configure"; nunca en archivos del repo)
"""Verifica la configuración de AWS de la P4 (lista del §7 de docs/practica4/GUIA_AWS.md).

Por defecto SOLO LEE: no cambia nada en la cuenta.

Revisa:
  1. Tabla tendedero_dispositivos activa, índice codigoVinculacion-index, códigos válidos y únicos.
  2. Tabla tendedero_vinculaciones activa, con clave userId + thingName.
  3. Política IoT genérica (${iot:Connection.Thing.ThingName}, sin ACCOUNT_ID).
  4. Certificado del Thing físico asociado al Thing y con la política.
  5. Rol de la Lambda con dynamodb:Query sobre el índice.
  6. Lambda: variables de entorno, endpoint correcto y código igual al ZIP del repositorio.
  7. Shadows sin atributos de la P3 y, en el físico, con los atributos nuevos y un reporte reciente.

Con --e2e además MUEVE el tendedero físico: escribe desired.posicion y mide cuánto tarda
reported.posicion en cambiar (requiere el ESP32 encendido y conectado).

Ejemplo:
  python tools/verificar_aws.py
  python tools/verificar_aws.py --e2e 4
"""
import argparse
import base64
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ZIP = RAIZ / "lambda" / "lambda_deployment_p3.zip"
# Atributos que ya no se usan: los de la P3 y los que se quitaron en la P4
# (luz_adc -> nivel_luz; desired.origen_led). Los borra shadow-migracion-practica4.json.
ATRIBUTOS_P3 = ("cubierta", "sensor_raw", "luz_adc", "origen_led@desired")
ATRIBUTOS_P4 = ("posicion", "agua_detectada", "lectura_adc", "calibracion", "modo", "minutos_reexponer")


class Verificador:
    def __init__(self, clientes, a):
        self.c, self.a = clientes, a
        self.filas = []

    def anotar(self, grupo, verificacion, ok, detalle=""):
        estado = {True: "PASA", False: "FALLA", None: "INFO"}[ok]
        self.filas.append((grupo, verificacion, estado, detalle))
        print(f"[{estado}] {grupo}: {verificacion} {('- ' + str(detalle)) if detalle else ''}")
        return ok

    def seguro(self, grupo, verificacion, funcion):
        try:
            return funcion()
        except Exception as exc:
            self.anotar(grupo, verificacion, False, f"{type(exc).__name__}: {exc}")
            return None

    # 1 y 2 --------------------------------------------------------------
    def tablas(self):
        ddb = self.c["dynamodb"]
        t = self.seguro("DynamoDB", "describir tendedero_dispositivos",
                        lambda: ddb.describe_table(TableName=self.a.tabla_dispositivos)["Table"])
        if t:
            self.anotar("DynamoDB", "tendedero_dispositivos activa", t["TableStatus"] == "ACTIVE", t["TableStatus"])
            claves = {k["AttributeName"]: k["KeyType"] for k in t["KeySchema"]}
            self.anotar("DynamoDB", "clave de partición thingName", claves == {"thingName": "HASH"}, claves)
            gsi = {g["IndexName"]: g for g in t.get("GlobalSecondaryIndexes", [])}
            g = gsi.get("codigoVinculacion-index")
            self.anotar("DynamoDB", "índice codigoVinculacion-index activo",
                        bool(g) and g.get("IndexStatus") == "ACTIVE", g.get("IndexStatus") if g else "no existe")
            tipos = {d["AttributeName"]: d["AttributeType"] for d in t["AttributeDefinitions"]}
            self.anotar("DynamoDB", "codigoVinculacion es String", tipos.get("codigoVinculacion") == "S",
                        tipos.get("codigoVinculacion"))
            items = self.seguro("DynamoDB", "leer dispositivos",
                                lambda: ddb.scan(TableName=self.a.tabla_dispositivos)["Items"])
            if items is not None:
                codigos = [i.get("codigoVinculacion", {}).get("S", "") for i in items]
                malos = [c for c in codigos if not re.fullmatch(r"[1-9]\d{5}", c)]
                self.anotar("DynamoDB", "dispositivos registrados", len(items) >= 2, f"{len(items)} ítems")
                self.anotar("DynamoDB", "códigos de 6 dígitos sin 0 inicial", not malos, malos or "")
                self.anotar("DynamoDB", "códigos únicos", len(set(codigos)) == len(codigos))
        v = self.seguro("DynamoDB", "describir tendedero_vinculaciones",
                        lambda: ddb.describe_table(TableName=self.a.tabla_vinculaciones)["Table"])
        if v:
            self.anotar("DynamoDB", "tendedero_vinculaciones activa", v["TableStatus"] == "ACTIVE")
            claves = {k["AttributeName"]: k["KeyType"] for k in v["KeySchema"]}
            self.anotar("DynamoDB", "vinculaciones con clave userId + thingName (varios por usuario)",
                        claves == {"userId": "HASH", "thingName": "RANGE"}, claves)

    # 3 y 4 --------------------------------------------------------------
    def politica_iot(self):
        iot = self.c["iot"]
        p = self.seguro("IoT", "leer la política", lambda: iot.get_policy(policyName=self.a.politica_iot))
        if p:
            doc = p["policyDocument"]
            self.anotar("IoT", "política usa ${iot:Connection.Thing.ThingName}",
                        "${iot:Connection.Thing.ThingName}" in doc)
            self.anotar("IoT", "política sin ACCOUNT_ID pendiente", "ACCOUNT_ID" not in doc)
            self.anotar("IoT", "política no nombra un Thing fijo", self.a.thing not in doc)
        certs = self.seguro("IoT", "certificados del Thing físico",
                            lambda: iot.list_thing_principals(thingName=self.a.thing)["principals"])
        if certs is not None:
            self.anotar("IoT", f"{self.a.thing} tiene certificado", len(certs) >= 1, f"{len(certs)} certificados")
            for arn in certs:
                pol = [x["policyName"] for x in iot.list_attached_policies(target=arn)["policies"]]
                self.anotar("IoT", "el certificado tiene la política", self.a.politica_iot in pol, pol)

    # 5 -------------------------------------------------------------------
    def rol_lambda(self, rol):
        iam = self.c["iam"]
        nombres = self.seguro("IAM", "políticas en línea del rol",
                              lambda: iam.list_role_policies(RoleName=rol)["PolicyNames"])
        if nombres is None:
            return
        sentencias = []
        for n in nombres:
            doc = iam.get_role_policy(RoleName=rol, PolicyName=n)["PolicyDocument"]
            if isinstance(doc, str):
                doc = json.loads(doc)
            st = doc.get("Statement", [])
            sentencias += st if isinstance(st, list) else [st]

        def permite(accion, recurso_fin):
            for s in sentencias:
                acciones = s.get("Action", [])
                acciones = [acciones] if isinstance(acciones, str) else acciones
                recursos = s.get("Resource", [])
                recursos = [recursos] if isinstance(recursos, str) else recursos
                if s.get("Effect") == "Allow" and (accion in acciones or "dynamodb:*" in acciones) and \
                        any(r == "*" or r.endswith(recurso_fin) for r in recursos):
                    return True
            return False
        self.anotar("IAM", "Query sobre el índice de dispositivos",
                    permite("dynamodb:Query", "table/tendedero_dispositivos/index/codigoVinculacion-index"))
        self.anotar("IAM", "Query/PutItem/DeleteItem en vinculaciones",
                    all(permite(x, "table/tendedero_vinculaciones")
                        for x in ("dynamodb:Query", "dynamodb:PutItem", "dynamodb:DeleteItem")))

    # 6 -------------------------------------------------------------------
    def funcion(self):
        lam, iot = self.c["lambda"], self.c["iot"]
        cfg = self.seguro("Lambda", "leer la función", lambda: lam.get_function_configuration(FunctionName=self.a.funcion))
        if not cfg:
            return
        env = cfg.get("Environment", {}).get("Variables", {})
        self.anotar("Lambda", "handler lambda_function.lambda_handler", cfg.get("Handler") == "lambda_function.lambda_handler",
                    cfg.get("Handler"))
        self.anotar("Lambda", "tiene DDB_DEVICES_TABLE", env.get("DDB_DEVICES_TABLE") == self.a.tabla_dispositivos,
                    env.get("DDB_DEVICES_TABLE"))
        self.anotar("Lambda", "ya no tiene THING_ALIASES_JSON", "THING_ALIASES_JSON" not in env)
        ep = self.seguro("IoT", "endpoint ATS", lambda: iot.describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"])
        if ep:
            self.anotar("Lambda", "IOT_ENDPOINT es el endpoint ATS de la cuenta", env.get("IOT_ENDPOINT") == ep,
                        env.get("IOT_ENDPOINT"))
        if ZIP.exists():
            local = base64.b64encode(hashlib.sha256(ZIP.read_bytes()).digest()).decode()
            self.anotar("Lambda", "código desplegado = ZIP del repositorio", cfg.get("CodeSha256") == local,
                        "" if cfg.get("CodeSha256") == local else "suban lambda/lambda_deployment_p3.zip otra vez")
        rol = cfg.get("Role", "").split("/")[-1]
        if rol:
            self.rol_lambda(rol)

    # 7 -------------------------------------------------------------------
    def shadow(self, thing):
        datos = self.c["iot-data"]
        doc = self.seguro("Shadow", f"leer {thing}",
                          lambda: json.loads(datos.get_thing_shadow(thingName=thing)["payload"].read()))
        if not doc:
            return None
        rep = doc.get("state", {}).get("reported", {})
        des = doc.get("state", {}).get("desired", {})
        viejos = [x for x in ATRIBUTOS_P3 if ("@desired" in x and x.split("@")[0] in des)
                  or ("@" not in x and (x in rep or x in des))]
        self.anotar("Shadow", f"{thing} sin atributos de la P3", not viejos, viejos or "")
        return doc

    def shadows(self):
        doc = self.shadow(self.a.thing)
        if doc:
            rep = doc.get("state", {}).get("reported", {})
            faltan = [x for x in ATRIBUTOS_P4 if x not in rep]
            self.anotar("Shadow", f"{self.a.thing} reporta los atributos nuevos", not faltan,
                        f"faltan {faltan}" if faltan else "")
            meta = doc.get("metadata", {}).get("reported", {}).get("lectura_adc", {})
            if "timestamp" in meta:
                edad = time.time() - meta["timestamp"]
                self.anotar("Shadow", "último reporte del ESP32 hace menos de 2 min", edad < 120,
                            f"hace {edad:.0f} s")
            cal = rep.get("calibracion", {})
            if cal:
                self.anotar("Shadow", "calibración vigente", None,
                            f"umbral_seco={cal.get('umbral_seco')} umbral_agua={cal.get('umbral_agua')} "
                            f"estado={cal.get('estado')}")
        for t in self.a.things_prueba:
            self.shadow(t)

    def e2e(self, veces, espera_max=20.0):
        datos = self.c["iot-data"]
        tiempos = []
        for i in range(veces):
            destino = "resguardado" if i % 2 == 0 else "expuesto"
            t0 = time.time()
            datos.update_thing_shadow(thingName=self.a.thing, payload=json.dumps(
                {"state": {"desired": {"posicion": destino}}}).encode())
            while time.time() - t0 < espera_max:
                rep = json.loads(datos.get_thing_shadow(thingName=self.a.thing)["payload"].read())
                if rep.get("state", {}).get("reported", {}).get("posicion") == destino:
                    tiempos.append(time.time() - t0)
                    break
                time.sleep(0.25)
            else:
                self.anotar("E2E", f"orden {i + 1} ({destino})", False, f"reported no cambió en {espera_max:.0f} s")
            time.sleep(1)
        if tiempos:
            self.anotar("E2E", f"desired -> reported.posicion (<= {self.a.objetivo_e2e_s:.0f} s)",
                        max(tiempos) <= self.a.objetivo_e2e_s,
                        f"n={len(tiempos)} media={sum(tiempos) / len(tiempos):.2f} s max={max(tiempos):.2f} s "
                        "(incluye el sondeo cada 0,25 s)")

    def informe(self):
        out = [f"# Verificación de AWS — {datetime.now():%Y-%m-%d %H:%M}", "",
               "| Grupo | Verificación | Resultado | Detalle |", "| --- | --- | --- | --- |"]
        out += [f"| {g} | {v} | {r} | {str(d).replace('|', '/')} |" for g, v, r, d in self.filas]
        return "\n".join(out) + "\n"

    def ok(self):
        return all(f[2] != "FALLA" for f in self.filas)


def argumentos(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--thing", default="tendedero-inteligente")
    ap.add_argument("--things-prueba", nargs="*", default=["tendedero-prueba2"])
    ap.add_argument("--funcion", default="tendedero-inteligente-alexa")
    ap.add_argument("--politica-iot", default="tendedero-inteligente-device-policy")
    ap.add_argument("--tabla-dispositivos", default="tendedero_dispositivos")
    ap.add_argument("--tabla-vinculaciones", default="tendedero_vinculaciones")
    ap.add_argument("--e2e", type=int, default=0, metavar="N", help="mueve el tendedero físico N veces")
    ap.add_argument("--objetivo-e2e-s", type=float, default=6.0)
    ap.add_argument("--salida", default=str(RAIZ / "resultados_p4"))
    return ap.parse_args(argv)


def correr(a, clientes):
    v = Verificador(clientes, a)
    v.tablas()
    v.politica_iot()
    v.funcion()
    v.shadows()
    if a.e2e:
        v.e2e(a.e2e)
    Path(a.salida).mkdir(parents=True, exist_ok=True)
    ruta = Path(a.salida) / f"aws-{datetime.now():%Y%m%d-%H%M%S}.md"
    ruta.write_text(v.informe(), encoding="utf-8")
    print(f"\nInforme: {ruta}")
    return v


def main(argv=None):
    a = argumentos(argv)
    try:
        import boto3
    except ImportError:
        sys.exit("Falta boto3: pip install boto3")
    clientes = {n: boto3.client(n, region_name=a.region) for n in ("dynamodb", "iot", "iam", "lambda")}
    endpoint = clientes["iot"].describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]
    clientes["iot-data"] = boto3.client("iot-data", region_name=a.region, endpoint_url=f"https://{endpoint}")
    return 0 if correr(a, clientes).ok() else 1


if __name__ == "__main__":
    sys.exit(main())
