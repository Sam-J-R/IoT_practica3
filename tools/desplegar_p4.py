#!/usr/bin/env python3
"""Despliega (o elimina) los recursos de la Práctica 4 con CloudFormation.

Crea la pila "tendedero-p4" desde aws/cloudformation/tendedero-p4.yaml: tabla
tendedero_historico, Lambdas tendedero_almacenamiento / tendedero_logica /
tendedero_supervisor con sus roles, reglas de AWS IoT, programación de
EventBridge y, si se indica --correo, un presupuesto con alerta de gasto.
No modifica nada de la P3.

Necesita la AWS CLI v2 con credenciales (aws configure). Sin --desplegar ni
--eliminar NO llama a AWS: solo muestra lo que haría.

  python tools/desplegar_p4.py                          # plan, sin tocar AWS
  python tools/desplegar_p4.py --desplegar --correo equipo@ejemplo.com
  python tools/desplegar_p4.py --eliminar               # borra la pila (pide confirmación)

Costo: las Lambdas cobran por invocación, la tabla usa 2/2 unidades
aprovisionadas (capa gratuita permanente) y el código se guarda en un bucket de
S3 de unos pocos KB. El presupuesto sin acciones es gratuito.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLA = RAIZ / "aws" / "cloudformation" / "tendedero-p4.yaml"
EMPAQUETADA = RAIZ / "resultados_p4" / "tendedero-p4.packaged.yaml"


class Error(RuntimeError):
    pass


def aws(*args, region, capturar=True, ejecutar=True):
    comando = ["aws", *args, "--region", region]
    print("  $ " + " ".join(comando))
    if not ejecutar:
        return ""
    r = subprocess.run(comando, capture_output=capturar, text=True)
    if r.returncode != 0:
        raise Error((r.stderr or r.stdout or "").strip() or f"falló: {' '.join(comando)}")
    return r.stdout if capturar else ""


def existe(*args, region):
    r = subprocess.run(["aws", *args, "--region", region], capture_output=True, text=True)
    return r.returncode == 0


def comprobar_cli():
    if not shutil.which("aws"):
        raise Error("No se encontró la AWS CLI. Instalen AWS CLI v2 y ejecuten 'aws configure'.")


def desplegar(a):
    ejecutar = a.desplegar
    if ejecutar:
        comprobar_cli()
    print("1. Cuenta y endpoint de AWS IoT")
    cuenta = "ACCOUNT_ID"
    endpoint = "<endpoint>"
    if ejecutar:
        cuenta = json.loads(aws("sts", "get-caller-identity", region=a.region))["Account"]
        endpoint = json.loads(aws("iot", "describe-endpoint", "--endpoint-type", "iot:Data-ATS",
                                  region=a.region))["endpointAddress"]
        print(f"   cuenta {cuenta}, endpoint {endpoint}")
    else:
        aws("sts", "get-caller-identity", region=a.region, ejecutar=False)
        aws("iot", "describe-endpoint", "--endpoint-type", "iot:Data-ATS", region=a.region, ejecutar=False)

    print("2. Revisar que la tabla de histórico no exista fuera de la pila")
    if ejecutar and not existe("cloudformation", "describe-stacks", "--stack-name", a.pila, region=a.region) \
            and existe("dynamodb", "describe-table", "--table-name", "tendedero_historico", region=a.region):
        raise Error("La tabla tendedero_historico ya existe (¿creada a mano?). Bórrenla o cambien "
                    "NombreHistorico con --parametro NombreHistorico=otro_nombre.")

    bucket = a.bucket or f"tendedero-p4-codigo-{cuenta}-{a.region}"
    print(f"3. Bucket para el código de las Lambdas: {bucket}")
    if not ejecutar or not existe("s3api", "head-bucket", "--bucket", bucket, region=a.region):
        aws("s3", "mb", f"s3://{bucket}", region=a.region, ejecutar=ejecutar)

    print("4. Empaquetar el código (lambda/almacenamiento, lambda/logica, lambda/supervisor)")
    EMPAQUETADA.parent.mkdir(parents=True, exist_ok=True)
    aws("cloudformation", "package", "--template-file", str(PLANTILLA), "--s3-bucket", bucket,
        "--output-template-file", str(EMPAQUETADA), region=a.region, ejecutar=ejecutar)

    print("5. Crear o actualizar la pila")
    parametros = [f"IotEndpoint={endpoint}", *a.parametro]
    if a.correo:
        parametros.append(f"CorreoAlertas={a.correo}")
    aws("cloudformation", "deploy", "--template-file", str(EMPAQUETADA), "--stack-name", a.pila,
        "--capabilities", "CAPABILITY_NAMED_IAM", "--no-fail-on-empty-changeset",
        "--parameter-overrides", *parametros, region=a.region, capturar=False, ejecutar=ejecutar)
    if ejecutar:
        print(f"\nListo. Revisen la pila '{a.pila}' en la consola de CloudFormation y luego:\n"
              "  python tools/verificar_aws.py")
    else:
        print("\nPlan solamente: no se llamó a AWS. Agreguen --desplegar para ejecutarlo.")


def eliminar(a):
    comprobar_cli()
    respuesta = input(f"Se borrará la pila '{a.pila}' y la tabla de histórico con sus datos.\n"
                      f"Escriban el nombre de la pila para confirmar: ")
    if respuesta.strip() != a.pila:
        print("Cancelado.")
        return
    aws("cloudformation", "delete-stack", "--stack-name", a.pila, region=a.region)
    aws("cloudformation", "wait", "stack-delete-complete", "--stack-name", a.pila, region=a.region)
    print("Pila eliminada. El bucket de código queda; bórrenlo con 'aws s3 rb s3://<bucket> --force'.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--desplegar", action="store_true", help="crear o actualizar los recursos en AWS")
    modo.add_argument("--eliminar", action="store_true", help="borrar la pila")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--pila", default="tendedero-p4")
    ap.add_argument("--correo", help="correo para el presupuesto con alerta (sin él no se crea)")
    ap.add_argument("--bucket", help="bucket S3 para el código (por defecto uno por cuenta y región)")
    ap.add_argument("--parametro", action="append", default=[],
                    help="parámetro extra de la plantilla, p. ej. FrecuenciaSupervisor='rate(10 minutes)'")
    a = ap.parse_args(argv)
    try:
        eliminar(a) if a.eliminar else desplegar(a)
    except Error as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
