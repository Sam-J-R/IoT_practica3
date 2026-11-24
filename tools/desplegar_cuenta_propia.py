#!/usr/bin/env python3
"""Monta el sistema completo del tendedero en una cuenta propia de AWS y de Alexa.

Pensado para probar todo antes de pasarlo al equipo, sin tocar la cuenta
compartida. Crea, en este orden:

  1. Pila "tendedero-base" (aws/cloudformation/tendedero-base.yaml): tablas de
     vinculaciones y dispositivos, política de AWS IoT, Thing y la Lambda de la
     skill de Alexa con su rol.
  2. Certificado del dispositivo (clave privada solo en esta PC), unido al Thing
     y a la política.
  3. Registro del Thing en tendedero_dispositivos con un código de vinculación.
  4. Pila "tendedero-p4" (tools/desplegar_p4.py): histórico, Lambdas de
     almacenamiento, lógica y supervisor, reglas de IoT, EventBridge y presupuesto.
  5. Skill de Alexa (ASK CLI): manifiesto con el ARN de la Lambda, modelo es-MX
     y pruebas habilitadas en la consola de desarrollo.
  6. firmware/include/secrets.h con el endpoint, el Thing y el certificado nuevos.
     Conserva el WiFi y la CA del secrets.h actual y lo respalda en
     secrets.h.equipo.bak.

Sin --desplegar ni --eliminar no llama a AWS ni a Alexa: solo muestra el plan.
Volver a ejecutarlo es seguro: lo ya creado se reutiliza (ver estado.json).

Requisitos, una sola vez y por la persona dueña de las cuentas:
  aws configure        (claves de un usuario IAM de SU cuenta, región us-east-2)
  npm install -g ask-cli && ask configure   (cuenta de desarrollador de Amazon)

  python tools/desplegar_cuenta_propia.py                       # plan
  python tools/desplegar_cuenta_propia.py --desplegar --correo yo@ejemplo.com
  python tools/desplegar_cuenta_propia.py --desplegar --sin-alexa
  python tools/desplegar_cuenta_propia.py --eliminar            # borra todo lo creado
"""
import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))

PLANTILLA_BASE = RAIZ / "aws" / "cloudformation" / "tendedero-base.yaml"
MODELO_ALEXA = RAIZ / "alexa" / "interaction-model-es-MX.json"
SECRETS = RAIZ / "firmware" / "include" / "secrets.h"
RESPALDO_SECRETS = SECRETS.with_name("secrets.h.equipo.bak")
CARPETA = RAIZ / "resultados_p4" / "cuenta_propia"
ESTADO = CARPETA / "estado.json"
PILA_BASE = "tendedero-base"
URL_CA = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"


class Error(RuntimeError):
    pass


def _ruta(ruta):
    """Ruta relativa al proyecto para los mensajes (absoluta si está fuera)."""
    try:
        return ruta.relative_to(RAIZ)
    except ValueError:
        return ruta


class Consola:
    """Ejecuta (o solo muestra, en modo plan) los comandos de aws y ask."""

    def __init__(self, ejecutar, region):
        self.ejecutar = ejecutar
        self.region = region

    def correr(self, programa, *args, region=True, json_salida=False, permitir_error=False):
        comando = [programa, *args, *(["--region", self.region] if region else [])]
        print("  $ " + " ".join(comando))
        if not self.ejecutar:
            return {} if json_salida else ""
        ruta = shutil.which(programa)
        if not ruta:
            raise Error(f"No se encontró '{programa}'. Revisen los requisitos al inicio de este script.")
        r = subprocess.run([ruta, *comando[1:]], capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if r.returncode != 0:
            if permitir_error:
                return None
            raise Error((r.stderr or r.stdout or "").strip() or f"falló: {' '.join(comando)}")
        if not json_salida:
            return r.stdout
        inicio = r.stdout.find("{")
        return json.loads(r.stdout[inicio:]) if inicio >= 0 else {}

    def aws(self, *args, **kw):
        return self.correr("aws", *args, **kw)

    def ask(self, *args, **kw):
        return self.correr("ask", *args, region=False, **kw)


# ---------------------------------------------------------------- estado

def leer_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {}


def guardar_estado(estado):
    CARPETA.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- secrets.h

def _define(texto, nombre):
    m = re.search(rf'#define\s+{nombre}\s+"((?:[^"\\]|\\.)*)"', texto)
    return m.group(1) if m else ""


def _literal_ca(texto):
    """Literal C++ de AWS_CA_PEM tal como está en el secrets.h actual (o None)."""
    m = re.search(r"AWS_CA_PEM\[\]\s*=\s*(.*?);\s*$", texto, re.S | re.M)
    if m and "BEGIN CERTIFICATE" in m.group(1):
        return m.group(1).strip()
    return None


def _crudo(pem):
    return 'R"PEM(\n' + pem.strip() + '\n)PEM"'


def generar_secrets(actual, endpoint, thing, certificado, clave, ca_pem=None):
    """Contenido del secrets.h nuevo. Conserva WiFi y CA del archivo actual."""
    ssid = _define(actual, "WIFI_SSID")
    password = _define(actual, "WIFI_PASSWORD")
    ca = _literal_ca(actual) or (_crudo(ca_pem) if ca_pem else None)
    if ca is None:
        raise Error("No hay CA en el secrets.h actual ni se pudo descargar AmazonRootCA1.pem")
    return (
        "#pragma once\n\n"
        f"// Generado por tools/desplegar_cuenta_propia.py el {datetime.now():%Y-%m-%d %H:%M}.\n"
        "// Cuenta propia de pruebas. El secrets.h del equipo quedó en secrets.h.equipo.bak.\n"
        "// No subir al repositorio (está en .gitignore).\n"
        f'#define WIFI_SSID "{ssid}"\n'
        f'#define WIFI_PASSWORD "{password}"\n'
        f'#define AWS_IOT_ENDPOINT "{endpoint}"\n'
        f'#define AWS_IOT_THING_NAME "{thing}"\n\n'
        f"constexpr char AWS_CA_PEM[] = {ca};\n"
        f"constexpr char AWS_CLIENT_CERT_PEM[] = {_crudo(certificado)};\n"
        f"constexpr char AWS_CLIENT_KEY_PEM[] = {_crudo(clave)};\n"
    )


def escribir_secrets(estado, endpoint, ejecutar):
    print("6. firmware/include/secrets.h para la cuenta propia")
    print(f"   respaldo del actual en {RESPALDO_SECRETS.name}; se conservan WiFi y CA")
    if not ejecutar:
        return
    actual = SECRETS.read_text(encoding="utf-8") if SECRETS.exists() else ""
    if not _define(actual, "WIFI_SSID"):
        print("   AVISO: el secrets.h actual no tiene WIFI_SSID; complétenlo a mano.")
    if SECRETS.exists() and not RESPALDO_SECRETS.exists():
        shutil.copy2(SECRETS, RESPALDO_SECRETS)
    ca = None
    if not _literal_ca(actual):
        with urllib.request.urlopen(URL_CA, timeout=20) as r:
            ca = r.read().decode("ascii")
    cert = Path(estado["certificado_pem"]).read_text(encoding="ascii")
    clave = Path(estado["clave_privada"]).read_text(encoding="ascii")
    SECRETS.write_text(generar_secrets(actual, endpoint, estado["thing"], cert, clave, ca), encoding="utf-8")
    print("   secrets.h escrito")


# ---------------------------------------------------------------- pasos

def comprobar_cuenta(c, a):
    print("0. Cuenta de AWS")
    if not c.ejecutar:
        c.aws("sts", "get-caller-identity")
        return "ACCOUNT_ID"
    cuenta = c.aws("sts", "get-caller-identity", json_salida=True)["Account"]
    pila = c.aws("cloudformation", "describe-stacks", "--stack-name", PILA_BASE, json_salida=True,
                 permitir_error=True)
    tabla = c.aws("dynamodb", "describe-table", "--table-name", "tendedero_vinculaciones",
                  json_salida=True, permitir_error=True)
    if tabla and not pila:
        raise Error(f"La cuenta {cuenta} ya tiene tendedero_vinculaciones fuera de la pila "
                    f"'{PILA_BASE}'. Parece la cuenta del equipo: este script es para una cuenta propia. "
                    "Revisen 'aws configure'.")
    print(f"   cuenta {cuenta}")
    if not a.si:
        respuesta = input(f"   Se crearán recursos en la cuenta {cuenta}, región {a.region}. "
                          "Escriban los últimos 4 dígitos de la cuenta para seguir: ")
        if respuesta.strip() != cuenta[-4:]:
            raise Error("Cancelado: no coincide la cuenta.")
    return cuenta


def endpoint_iot(c):
    if not c.ejecutar:
        c.aws("iot", "describe-endpoint", "--endpoint-type", "iot:Data-ATS")
        return "<endpoint>"
    return c.aws("iot", "describe-endpoint", "--endpoint-type", "iot:Data-ATS",
                 json_salida=True)["endpointAddress"]


def bucket_codigo(c, cuenta):
    bucket = f"tendedero-p4-codigo-{cuenta}-{c.region}"
    if not c.ejecutar or c.aws("s3api", "head-bucket", "--bucket", bucket, permitir_error=True) is None:
        c.aws("s3", "mb", f"s3://{bucket}")
    return bucket


def desplegar_base(c, bucket, estado, endpoint, skill_id=""):
    print(f"1. Pila {PILA_BASE}: tablas, política, Thing {estado['thing']} y Lambda de Alexa")
    empaquetada = CARPETA / "tendedero-base.packaged.yaml"
    CARPETA.mkdir(parents=True, exist_ok=True)
    c.aws("cloudformation", "package", "--template-file", str(PLANTILLA_BASE), "--s3-bucket", bucket,
          "--output-template-file", str(empaquetada))
    c.aws("cloudformation", "deploy", "--template-file", str(empaquetada), "--stack-name", PILA_BASE,
          "--capabilities", "CAPABILITY_NAMED_IAM", "--no-fail-on-empty-changeset",
          "--parameter-overrides", f"NombreThing={estado['thing']}", f"IotEndpoint={endpoint}",
          *([f"AlexaSkillId={skill_id}"] if skill_id else []))
    if not c.ejecutar:
        return "arn:aws:lambda:...:function:tendedero_alexa"
    salidas = c.aws("cloudformation", "describe-stacks", "--stack-name", PILA_BASE, json_salida=True)
    for salida in salidas["Stacks"][0].get("Outputs", []):
        if salida["OutputKey"] == "LambdaAlexaArn":
            return salida["OutputValue"]
    raise Error("La pila base no devolvió LambdaAlexaArn")


def crear_certificado(c, estado):
    print("2. Certificado del dispositivo")
    if estado.get("certificado_arn") and Path(estado.get("clave_privada", "")).exists():
        print(f"   se reutiliza {estado['certificado_id']}")
        return
    cert_pem = CARPETA / f"{estado['thing']}.pem.crt"
    clave = CARPETA / f"{estado['thing']}.private.pem.key"
    r = c.aws("iot", "create-keys-and-certificate", "--set-as-active", json_salida=True)
    if c.ejecutar:
        CARPETA.mkdir(parents=True, exist_ok=True)
        cert_pem.write_text(r["certificatePem"], encoding="ascii")
        clave.write_text(r["keyPair"]["PrivateKey"], encoding="ascii")
        estado.update(certificado_arn=r["certificateArn"], certificado_id=r["certificateId"],
                      certificado_pem=str(cert_pem), clave_privada=str(clave))
        guardar_estado(estado)
    arn = estado.get("certificado_arn", "<certificateArn>")
    c.aws("iot", "attach-policy", "--policy-name", "tendedero-politica-dispositivo", "--target", arn)
    c.aws("iot", "attach-thing-principal", "--thing-name", estado["thing"], "--principal", arn)


def registrar_dispositivo(c, estado):
    print("3. Registro del Thing en tendedero_dispositivos")
    estado.setdefault("codigo", str(random.randint(100000, 999999)))
    item = {"thingName": {"S": estado["thing"]}, "codigoVinculacion": {"S": estado["codigo"]},
            "fechaAlta": {"S": datetime.now(timezone.utc).isoformat(timespec="seconds")}}
    c.aws("dynamodb", "put-item", "--table-name", "tendedero_dispositivos", "--item", json.dumps(item))
    print(f"   código de vinculación: {estado['codigo']}")


def desplegar_p4(a):
    print("4. Pila tendedero-p4 (tools/desplegar_p4.py)")
    import desplegar_p4
    argumentos = ["--region", a.region]
    if a.desplegar:
        argumentos.append("--desplegar")
    if a.correo:
        argumentos += ["--correo", a.correo]
    if desplegar_p4.main(argumentos) != 0:
        raise Error("falló el despliegue de la pila tendedero-p4")


def manifiesto(lambda_arn):
    return {"manifest": {
        "manifestVersion": "1.0",
        "publishingInformation": {
            "locales": {"es-MX": {
                "name": "Tendedero inteligente",
                "summary": "Protege la ropa tendida de la lluvia.",
                "description": "Consulta el sensor de agua, mueve el tendedero, cambia el modo automático "
                               "y controla la luz.",
                "examplePhrases": ["Alexa, abre tendedero inteligente",
                                   "Alexa, pídele a tendedero inteligente que resguarde la ropa",
                                   "Alexa, pregúntale a tendedero inteligente si hay agua"],
                "keywords": ["tendedero", "ropa", "lluvia"]}},
            "isAvailableWorldwide": False,
            "distributionCountries": ["MX"],
            "testingInstructions": "Proyecto académico de IoT (práctica 4).",
            "category": "ORGANIZERS_AND_ASSISTANTS"},
        "privacyAndCompliance": {
            "allowsPurchases": False, "usesPersonalInfo": False, "isChildDirected": False,
            "isExportCompliant": True, "containsAds": False, "locales": {"es-MX": {}}},
        "apis": {"custom": {"endpoint": {"uri": lambda_arn}}},
    }}


def _esperar_skill(c, skill_id, recurso):
    if not c.ejecutar:
        return
    for _ in range(40):
        estado = c.ask("smapi", "get-skill-status", "--skill-id", skill_id, "--resource", recurso,
                       json_salida=True, permitir_error=True) or {}
        texto = json.dumps(estado)
        if '"SUCCEEDED"' in texto:
            return
        if '"FAILED"' in texto:
            raise Error(f"Alexa rechazó {recurso}: {texto[:500]}")
        time.sleep(3)
    raise Error(f"Alexa no terminó de procesar {recurso}")


def crear_skill(c, estado, lambda_arn):
    print("5. Skill de Alexa (ASK CLI)")
    archivo = CARPETA / "skill.json"
    CARPETA.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(manifiesto(lambda_arn), indent=2, ensure_ascii=False), encoding="utf-8")
    skill_id = estado.get("skill_id")
    ruta_manifiesto = "file:" + archivo.as_posix()
    if skill_id:
        print(f"   se reutiliza {skill_id}")
        c.ask("smapi", "update-skill-manifest", "--skill-id", skill_id, "--stage", "development",
              "--manifest", ruta_manifiesto)
    else:
        r = c.ask("smapi", "create-skill-for-vendor", "--manifest", ruta_manifiesto, json_salida=True)
        skill_id = r.get("skillId", "<skillId>")
        if c.ejecutar and not r.get("skillId"):
            raise Error("ASK CLI no devolvió el ID de la skill. Revisen 'ask configure' y la consola de Alexa.")
        if c.ejecutar:
            estado["skill_id"] = skill_id
            guardar_estado(estado)
    _esperar_skill(c, skill_id, "manifest")
    c.ask("smapi", "set-interaction-model", "--skill-id", skill_id, "--stage", "development",
          "--locale", "es-MX", "--interaction-model", "file:" + MODELO_ALEXA.as_posix())
    _esperar_skill(c, skill_id, "interactionModel")
    c.ask("smapi", "set-skill-enablement", "--skill-id", skill_id, "--stage", "development")
    return skill_id


def desplegar(a):
    c = Consola(a.desplegar, a.region)
    estado = leer_estado()
    estado.setdefault("thing", a.thing)
    estado["region"] = a.region
    cuenta = comprobar_cuenta(c, a)
    endpoint = endpoint_iot(c)
    bucket = bucket_codigo(c, cuenta)
    lambda_arn = desplegar_base(c, bucket, estado, endpoint, estado.get("skill_id", ""))
    crear_certificado(c, estado)
    registrar_dispositivo(c, estado)
    if c.ejecutar:
        estado.update(cuenta=cuenta, endpoint=endpoint, lambda_alexa=lambda_arn)
        guardar_estado(estado)
    desplegar_p4(a)
    if a.sin_alexa:
        print("5. Skill de Alexa: omitida (--sin-alexa)")
    else:
        skill_id = crear_skill(c, estado, lambda_arn)
        # Con el ID, la Lambda solo acepta invocaciones de esta skill.
        print("   permiso de la Lambda restringido a la skill")
        desplegar_base(c, bucket, estado, endpoint, skill_id)
    escribir_secrets(estado, endpoint, c.ejecutar)
    if not c.ejecutar:
        print("\nPlan solamente: no se llamó a AWS ni a Alexa. Agreguen --desplegar para ejecutarlo.")
        return
    print(f"\nListo. Estado en {_ruta(ESTADO)}.\n"
          "Siguientes pasos:\n"
          "  1. Compilar y cargar el firmware (tools/windows/2_cargar_ensayo_y_probar.bat).\n"
          "  2. En la consola de Alexa (Test, Development) o en un Echo de la misma cuenta:\n"
          "     «abre tendedero inteligente» y luego "
          f"«vincula mi tendedero con el código {estado['codigo']}».\n"
          f"  3. python tools/verificar_aws.py --thing {estado['thing']} --funcion tendedero_alexa "
          "--politica-iot tendedero-politica-dispositivo --things-prueba\n"
          f"  4. python tools/probar_lambda.py --funcion tendedero_alexa --codigo {estado['codigo']} "
          f"--thing {estado['thing']}")


def eliminar(a):
    c = Consola(True, a.region)
    estado = leer_estado()
    if not estado:
        raise Error(f"No hay {_ruta(ESTADO)}: nada que eliminar desde este script.")
    cuenta = c.aws("sts", "get-caller-identity", json_salida=True)["Account"]
    if estado.get("cuenta") and estado["cuenta"] != cuenta:
        raise Error(f"Las credenciales son de la cuenta {cuenta}, pero lo creado está en {estado['cuenta']}.")
    respuesta = input(f"Se borrará TODO lo creado en la cuenta {cuenta}: skill, pilas {PILA_BASE} y "
                      "tendedero-p4 (con sus tablas y datos) y el certificado.\n"
                      f"Escriban {PILA_BASE} para confirmar: ")
    if respuesta.strip() != PILA_BASE:
        print("Cancelado.")
        return
    if estado.get("skill_id"):
        c.ask("smapi", "delete-skill", "--skill-id", estado["skill_id"], permitir_error=True)
    for pila in ("tendedero-p4", PILA_BASE):
        c.aws("cloudformation", "delete-stack", "--stack-name", pila)
        c.aws("cloudformation", "wait", "stack-delete-complete", "--stack-name", pila)
    if estado.get("certificado_arn"):
        arn = estado["certificado_arn"]
        c.aws("iot", "detach-policy", "--policy-name", "tendedero-politica-dispositivo", "--target", arn,
              permitir_error=True)
        c.aws("iot", "detach-thing-principal", "--thing-name", estado["thing"], "--principal", arn,
              permitir_error=True)
        c.aws("iot", "update-certificate", "--certificate-id", estado["certificado_id"],
              "--new-status", "INACTIVE")
        c.aws("iot", "delete-certificate", "--certificate-id", estado["certificado_id"])
    ESTADO.rename(ESTADO.with_suffix(".eliminado.json"))
    print("Eliminado. El bucket de código queda; bórrenlo con 'aws s3 rb s3://<bucket> --force'.")
    if RESPALDO_SECRETS.exists():
        print(f"Para volver a la cuenta del equipo: copien {RESPALDO_SECRETS.name} sobre secrets.h.")


def argumentos(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--desplegar", action="store_true", help="crear o actualizar todo")
    modo.add_argument("--eliminar", action="store_true", help="borrar todo lo creado por este script")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--thing", default="tendedero-propio", help="nombre del Thing (prefijo tendedero-)")
    ap.add_argument("--correo", help="correo para la alerta de gasto (recomendado)")
    ap.add_argument("--sin-alexa", action="store_true", help="no crear la skill (sin ASK CLI)")
    ap.add_argument("--si", action="store_true", help="no pedir confirmación de la cuenta")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"tendedero-[a-z0-9-]+", a.thing):
        ap.error("--thing debe empezar con 'tendedero-' y usar minúsculas, dígitos y guiones")
    return a


def main(argv=None):
    a = argumentos(argv)
    try:
        eliminar(a) if a.eliminar else desplegar(a)
    except Error as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
