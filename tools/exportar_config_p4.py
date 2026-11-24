#!/usr/bin/env python3
# pip install pyyaml
"""Exporta desde la plantilla de CloudFormation las configuraciones que pide la P4 (§6).

La fuente única es aws/cloudformation/tendedero-p4.yaml. Este script escribe:
  aws/tendedero-historico.table.json   definición de la tabla de histórico (create-table)
  aws/reglas/<regla>.json              SQL y acción de cada regla de AWS IoT (create-topic-rule)
  aws/iam/<rol>.json                   política de cada rol de las Lambdas nuevas

Los ARN llevan ACCOUNT_ID en lugar del número de cuenta. Uso:
  python tools/exportar_config_p4.py            # escribe los archivos
  python tools/exportar_config_p4.py --revisar  # solo compara; sale con 1 si difieren
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLA = RAIZ / "aws" / "cloudformation" / "tendedero-p4.yaml"
REGION = "us-east-2"
CUENTA = "ACCOUNT_ID"


class Cargador(yaml.SafeLoader):
    """Entiende las etiquetas cortas de CloudFormation (!Ref, !Sub, !GetAtt...)."""


def _etiqueta(nombre):
    def construir(cargador, nodo):
        if isinstance(nodo, yaml.ScalarNode):
            valor = cargador.construct_scalar(nodo)
            if nombre == "Fn::GetAtt":
                valor = valor.split(".", 1)
        elif isinstance(nodo, yaml.SequenceNode):
            valor = cargador.construct_sequence(nodo, deep=True)
        else:
            valor = cargador.construct_mapping(nodo, deep=True)
        return {nombre: valor}
    return construir


for corta, larga in {"!Ref": "Ref", "!Sub": "Fn::Sub", "!GetAtt": "Fn::GetAtt", "!Not": "Fn::Not",
                     "!Equals": "Fn::Equals", "!If": "Fn::If", "!Join": "Fn::Join"}.items():
    Cargador.add_constructor(corta, _etiqueta(larga))


def cargar_plantilla(ruta=PLANTILLA):
    return yaml.load(ruta.read_text(encoding="utf-8"), Loader=Cargador)


def resolver(valor, plantilla):
    """Reemplaza Ref, Sub y GetAtt por los valores por defecto y marcadores legibles."""
    parametros = {k: v.get("Default", k) for k, v in plantilla.get("Parameters", {}).items()}
    recursos = plantilla["Resources"]

    def nombre_de(logico):
        props = recursos[logico]["Properties"]
        for clave in ("TableName", "FunctionName", "RuleName", "RoleName", "Name"):
            if clave in props:
                return resolver(props[clave], plantilla)
        return logico

    def arn_de(logico):
        tipo, nombre = recursos[logico]["Type"], nombre_de(logico)
        return {"AWS::DynamoDB::Table": f"arn:aws:dynamodb:{REGION}:{CUENTA}:table/{nombre}",
                "AWS::Lambda::Function": f"arn:aws:lambda:{REGION}:{CUENTA}:function:{nombre}",
                "AWS::IoT::TopicRule": f"arn:aws:iot:{REGION}:{CUENTA}:rule/{nombre}",
                "AWS::IAM::Role": f"arn:aws:iam::{CUENTA}:role/{nombre}",
                "AWS::Events::Rule": f"arn:aws:events:{REGION}:{CUENTA}:rule/{nombre}"}[tipo]

    def sustituir(texto):
        def una(m):
            clave = m.group(1)
            if clave == "AWS::Region":
                return REGION
            if clave == "AWS::AccountId":
                return CUENTA
            if clave in parametros:
                return str(parametros[clave])
            return nombre_de(clave)
        return re.sub(r"\$\{([^}]+)\}", una, texto)

    if isinstance(valor, dict) and len(valor) == 1:
        (clave, arg), = valor.items()
        if clave == "Ref":
            seudo = {"AWS::Region": REGION, "AWS::AccountId": CUENTA}
            if arg in seudo:
                return seudo[arg]
            return parametros[arg] if arg in parametros else nombre_de(arg)
        if clave == "Fn::Sub":
            return sustituir(arg)
        if clave == "Fn::GetAtt":
            return arn_de(arg[0])
    if isinstance(valor, dict):
        return {k: resolver(v, plantilla) for k, v in valor.items()}
    if isinstance(valor, list):
        return [resolver(v, plantilla) for v in valor]
    return valor


def exportaciones(plantilla):
    """Devuelve {ruta relativa: contenido JSON} de todo lo exportado."""
    salida = {}
    for logico, recurso in plantilla["Resources"].items():
        tipo, props = recurso["Type"], resolver(recurso.get("Properties", {}), plantilla)
        if tipo == "AWS::DynamoDB::Table":
            salida[f"aws/{props['TableName'].replace('_', '-')}.table.json"] = {
                k: props[k] for k in ("TableName", "AttributeDefinitions", "KeySchema", "BillingMode",
                                      "ProvisionedThroughput", "TimeToLiveSpecification") if k in props}
        elif tipo == "AWS::IoT::TopicRule":
            carga = props["TopicRulePayload"]
            salida[f"aws/reglas/{props['RuleName']}.json"] = {
                "ruleName": props["RuleName"],
                "sql": " ".join(carga["Sql"].split()),
                "awsIotSqlVersion": carga["AwsIotSqlVersion"],
                "ruleDisabled": carga["RuleDisabled"],
                "actions": [{"lambda": {"functionArn": a["Lambda"]["FunctionArn"]}} for a in carga["Actions"]],
            }
        elif tipo == "AWS::IAM::Role":
            for politica in props["Policies"]:
                salida[f"aws/iam/{props['RoleName']}.json"] = politica["PolicyDocument"]
    return salida


def texto(contenido):
    return json.dumps(contenido, ensure_ascii=False, indent=2) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--revisar", action="store_true", help="no escribe; falla si algo difiere")
    a = ap.parse_args(argv)
    distintos = []
    for relativa, contenido in exportaciones(cargar_plantilla()).items():
        ruta = RAIZ / relativa
        actual = ruta.read_text(encoding="utf-8") if ruta.exists() else None
        if actual is not None and json.loads(actual) == contenido:
            continue
        distintos.append(relativa)
        if not a.revisar:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(texto(contenido), encoding="utf-8")
    verbo = "difieren" if a.revisar else "actualizados"
    print(f"{len(distintos)} archivos {verbo}" + "".join(f"\n  {d}" for d in distintos))
    return 1 if a.revisar and distintos else 0


if __name__ == "__main__":
    sys.exit(main())
