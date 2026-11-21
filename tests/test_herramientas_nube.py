"""Pruebas de tools/probar_lambda.py, tools/probar_alexa.py y tools/verificar_aws.py sin AWS.

probar_lambda se ejecuta contra la Lambda REAL del repositorio (lambda_function.py con el
SDK del ZIP) y AWS simulado en memoria, así que los casos de casos_alexa.json quedan
comprobados contra los textos actuales de la skill.
"""

import base64
import hashlib
import io
import json
import os
import runpy
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import probar_alexa  # noqa: E402
import probar_lambda  # noqa: E402
import verificar_aws  # noqa: E402


class ClientError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def cargar_lambda_local(dispositivos, shadows):
    """Devuelve lambda_handler del repositorio con DynamoDB, IoT y Shadow en memoria."""
    vinculos = {}
    vinc = Mock()
    vinc.get_item.side_effect = lambda Key, ConsistentRead: (
        {"Item": vinculos[Key["userId"]]} if Key["userId"] in vinculos else {})
    vinc.put_item.side_effect = lambda Item: vinculos.update({Item["userId"]: Item})
    vinc.delete_item.side_effect = lambda Key: vinculos.pop(Key["userId"], None)
    disp = Mock()
    disp.query.side_effect = lambda **kw: {"Items": [
        {"thingName": t} for c, t in dispositivos.items() if c == kw["ExpressionAttributeValues"][":codigo"]]}
    iot = Mock()

    def describir(thingName):
        if thingName not in shadows:
            raise ClientError("ResourceNotFoundException")
    iot.describe_thing.side_effect = describir
    datos = Mock()
    datos.get_thing_shadow.side_effect = lambda thingName: {
        "payload": io.BytesIO(json.dumps({"state": shadows[thingName]}).encode())}

    def actualizar(thingName, payload):
        for seccion, valores in json.loads(payload)["state"].items():
            destino = shadows[thingName].setdefault(seccion, {})
            for k, v in valores.items():
                if v is None:
                    destino.pop(k, None)
                else:
                    destino[k] = v
    datos.update_thing_shadow.side_effect = actualizar
    boto3 = types.ModuleType("boto3")
    boto3.client = lambda n, **kw: {"iot": iot, "iot-data": datos}[n]
    boto3.resource = lambda *a, **kw: Mock(Table=lambda n: {"tendedero_vinculaciones": vinc,
                                                            "tendedero_dispositivos": disp}[n])
    botocore = types.ModuleType("botocore")
    exc = types.ModuleType("botocore.exceptions")
    exc.ClientError = ClientError
    mods = {"boto3": boto3, "botocore": botocore, "botocore.exceptions": exc}
    # El SDK del ZIP resuelve sus clases al deserializar cada evento: debe quedar en sys.path.
    sdk = str(ROOT / "lambda/lambda_deployment_p3.zip")
    if sdk not in sys.path:
        sys.path.append(sdk)
    # Importar el SDK antes de patch.dict: si se importa dentro, se descarta al salir y
    # el deserializador crea otras clases (isinstance falla y ningún handler responde).
    import ask_sdk_core.utils  # noqa: F401
    import ask_sdk_model  # noqa: F401
    with patch.dict(sys.modules, mods), patch.dict(os.environ, {"IOT_ENDPOINT": "endpoint.example"}):
        handler = runpy.run_path(str(ROOT / "lambda/lambda_function.py"))["lambda_handler"]
    return handler, vinculos


class ProbarLambdaTests(unittest.TestCase):
    def setUp(self):
        self.shadows = {"tendedero-prueba2": {"reported": {
            "posicion": "expuesto", "agua_detectada": False, "lectura_adc": 0,
            "calibracion": {"umbral_seco": 200, "umbral_agua": 600, "estado": "fabrica"}}}}
        self.handler, self.vinculos = cargar_lambda_local({"715204": "tendedero-prueba2"}, self.shadows)

    def test_todos_los_casos_pasan_con_la_lambda_actual(self):
        with patch.dict(os.environ, {"IOT_ENDPOINT": "endpoint.example"}):
            usuario, filas = probar_lambda.ejecutar(
                probar_lambda.cargar_casos(), lambda ev: self.handler(ev, None),
                lambda: self.shadows["tendedero-prueba2"], codigo="715204")
        fallas = [f for f in filas if f[2] != "PASA"]
        self.assertEqual(fallas, [], "\n".join(map(str, fallas)))
        self.assertEqual(len(filas), 27)
        self.assertNotIn(usuario, self.vinculos, "el último caso debe dejar al usuario desvinculado")

    def test_detecta_una_respuesta_distinta(self):
        casos = [{"id": "X", "nombre": "x", "lambda": {"tipo": "LaunchRequest"}, "espera": "otra cosa"}]
        with patch.dict(os.environ, {"IOT_ENDPOINT": "endpoint.example"}):
            _, filas = probar_lambda.ejecutar(casos, lambda ev: self.handler(ev, None))
        self.assertEqual(filas[0][2], "FALLA")

    def test_detecta_un_shadow_incorrecto(self):
        casos = [c for c in probar_lambda.cargar_casos() if c["id"] in ("C06", "C20")]
        with patch.dict(os.environ, {"IOT_ENDPOINT": "endpoint.example"}):
            _, filas = probar_lambda.ejecutar(casos, lambda ev: self.handler(ev, None),
                                              lambda: {"desired": {"modo": "automatico"}})
        self.assertEqual(filas[1][2], "FALLA")
        self.assertIn("desired.modo", filas[1][3])

    def test_error_de_invocacion_es_falla(self):
        def roto(ev):
            raise RuntimeError("AccessDeniedException")
        _, filas = probar_lambda.ejecutar(probar_lambda.cargar_casos()[:1], roto)
        self.assertEqual(filas[0][2], "FALLA")
        self.assertIn("AccessDenied", filas[0][3])


class ProbarAlexaTests(unittest.TestCase):
    def setUp(self):
        self.casos = json.loads((ROOT / "tools/casos_alexa.json").read_text(encoding="utf-8"))["casos"]

    def test_cada_frase_esta_en_el_modelo_o_es_respuesta(self):
        """Las frases del simulador usan muestras del modelo de interacción (o respuestas de diálogo)."""
        modelo = json.loads((ROOT / "alexa/interaction-model-es-MX.json").read_text(encoding="utf-8"))
        lm = modelo["interactionModel"]["languageModel"]
        muestras = [s for i in lm["intents"] for s in i.get("samples", [])]
        invocacion = lm["invocationName"]
        import re
        def cubierta(frase):
            if frase in ("sí", "{codigo}", "ayuda") or frase == f"abre {invocacion}":
                return True
            for m in muestras:
                patron = "^" + re.sub(r"\\\{\w+\\\}", ".+", re.escape(m)) + "$"
                if re.match(patron, frase):
                    return True
            return False
        sin = [f for c in self.casos for f, _ in c.get("alexa", []) if not cubierta(f)]
        self.assertEqual(sin, [], "frases que no coinciden con ninguna muestra del modelo")

    def test_replay_y_comparacion(self):
        lista = probar_alexa.pasos(self.casos, "715204")
        replay = probar_alexa.archivo_replay("amzn1.ask.skill.x", lista)
        self.assertEqual(replay["userInput"][-1], ".quit")
        self.assertIn("715204", replay["userInput"])
        salida = "\n".join(f"User  > {f}\nAlexa > \x1b[32m<speak>{'Bienvenido al tendedero' if i == 0 else 'nada'}</speak>\x1b[0m"
                           for i, (_, _, f, _) in enumerate(lista))
        filas = probar_alexa.comparar(lista, probar_alexa.respuestas_de(salida))
        self.assertEqual(filas[0][3], "PASA")
        self.assertEqual(filas[1][3], "FALLA")

    def test_modo_manual_escribe_la_tabla(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(probar_alexa.main(["--manual", "--salida", tmp]), 0)
            texto = next(Path(tmp).iterdir()).read_text(encoding="utf-8")
        self.assertIn("vincula mi tendedero", texto)
        self.assertIn("| C06 |", texto)


# ---------------------------------------------------------------- verificar_aws
class Pag(dict):
    pass


def clientes_ok(**cambios):
    zip_sha = base64.b64encode(hashlib.sha256((ROOT / "lambda/lambda_deployment_p3.zip").read_bytes()).digest()).decode()
    politica_iot = json.loads((ROOT / "aws/iot-certificate-policy.template.json").read_text()).copy()
    politica_iot = json.dumps(politica_iot).replace("ACCOUNT_ID", "123456789012")
    politica_rol = (ROOT / "aws/lambda-iam-policy.template.json").read_text().replace("ACCOUNT_ID", "123456789012")
    ddb = Mock()
    ddb.describe_table.side_effect = lambda TableName: {"Table": {
        "TableStatus": "ACTIVE", "KeySchema": [{"AttributeName": "thingName" if "disp" in TableName else "userId",
                                                 "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "thingName", "AttributeType": "S"},
                                 {"AttributeName": "codigoVinculacion", "AttributeType": cambios.get("tipo_codigo", "S")}],
        "GlobalSecondaryIndexes": [{"IndexName": "codigoVinculacion-index", "IndexStatus": "ACTIVE"}]}}
    ddb.scan.return_value = {"Items": [{"thingName": {"S": t}, "codigoVinculacion": {"S": c}}
                                       for t, c in cambios.get("dispositivos", [("tendedero-inteligente", "483920"),
                                                                                 ("tendedero-prueba2", "715204")])]}
    iot = Mock()
    iot.get_policy.return_value = {"policyDocument": cambios.get("politica_iot", politica_iot)}
    iot.list_thing_principals.return_value = {"principals": ["arn:cert/1"]}
    iot.list_attached_policies.return_value = {"policies": [{"policyName": "tendedero-inteligente-device-policy"}]}
    iot.describe_endpoint.return_value = {"endpointAddress": "abc-ats.iot.us-east-2.amazonaws.com"}
    iam = Mock()
    iam.list_role_policies.return_value = {"PolicyNames": ["p"]}
    iam.get_role_policy.return_value = {"PolicyDocument": json.loads(cambios.get("politica_rol", politica_rol))}
    lam = Mock()
    lam.get_function_configuration.return_value = {
        "Handler": "lambda_function.lambda_handler", "CodeSha256": cambios.get("sha", zip_sha),
        "Role": "arn:aws:iam::1:role/tendedero-inteligente-lambda-role",
        "Environment": {"Variables": cambios.get("env", {
            "IOT_ENDPOINT": "abc-ats.iot.us-east-2.amazonaws.com", "DDB_BINDINGS_TABLE": "tendedero_vinculaciones",
            "DDB_DEVICES_TABLE": "tendedero_dispositivos"})}}
    reported = cambios.get("reported", {"posicion": "expuesto", "agua_detectada": False, "lectura_adc": 3,
                                        "calibracion": {"umbral_seco": 200, "umbral_agua": 600, "estado": "fabrica"}})
    estado = {"tendedero-inteligente": {"state": {"reported": reported},
                                        "metadata": {"reported": {"lectura_adc": {"timestamp": cambios.get("ts", time.time() - 30)}}}},
              "tendedero-prueba2": {"state": {"reported": {"posicion": "resguardado"}}}}
    datos = Mock()
    datos.get_thing_shadow.side_effect = lambda thingName: {"payload": io.BytesIO(json.dumps(estado[thingName]).encode())}

    def mover(thingName, payload):
        estado[thingName]["state"]["reported"]["posicion"] = json.loads(payload)["state"]["desired"]["posicion"]
    datos.update_thing_shadow.side_effect = mover
    return {"dynamodb": ddb, "iot": iot, "iam": iam, "lambda": lam, "iot-data": datos}


class VerificarAwsTests(unittest.TestCase):
    def correr(self, extra=(), **cambios):
        with tempfile.TemporaryDirectory() as tmp:
            a = verificar_aws.argumentos(["--salida", tmp, *extra])
            v = verificar_aws.correr(a, clientes_ok(**cambios))
            self.assertTrue(any(Path(tmp).iterdir()))
        return v, {(g, x): (r, d) for g, x, r, d in v.filas}

    def test_configuracion_correcta_pasa(self):
        v, _ = self.correr(["--e2e", "2"])
        self.assertTrue(v.ok(), v.informe())

    def test_detecta_errores_tipicos(self):
        _, f = self.correr(env={"IOT_ENDPOINT": "otro", "THING_ALIASES_JSON": "{}"},
                           sha="distinto", tipo_codigo="N",
                           dispositivos=[("a", "012345"), ("b", "483920"), ("c", "483920")],
                           politica_iot='{"Resource": "arn:aws:iot:us-east-2:ACCOUNT_ID:client/tendedero-inteligente"}',
                           reported={"cubierta": "abierta"}, ts=time.time() - 900)
        for clave in [("Lambda", "tiene DDB_DEVICES_TABLE"), ("Lambda", "ya no tiene THING_ALIASES_JSON"),
                      ("Lambda", "IOT_ENDPOINT es el endpoint ATS de la cuenta"),
                      ("Lambda", "código desplegado = ZIP del repositorio"),
                      ("DynamoDB", "codigoVinculacion es String"),
                      ("DynamoDB", "códigos de 6 dígitos sin 0 inicial"), ("DynamoDB", "códigos únicos"),
                      ("IoT", "política usa ${iot:Connection.Thing.ThingName}"),
                      ("IoT", "política sin ACCOUNT_ID pendiente"), ("IoT", "política no nombra un Thing fijo"),
                      ("Shadow", "tendedero-inteligente sin atributos de la P3"),
                      ("Shadow", "tendedero-inteligente reporta los atributos nuevos"),
                      ("Shadow", "último reporte del ESP32 hace menos de 2 min")]:
            self.assertEqual(f[clave][0], "FALLA", clave)

    def test_rol_sin_permiso_de_query(self):
        politica = json.loads((ROOT / "aws/lambda-iam-policy.template.json").read_text())
        politica["Statement"] = [s for s in politica["Statement"] if s.get("Sid") != "FindDeviceByBindingCode"]
        _, f = self.correr(politica_rol=json.dumps(politica))
        self.assertEqual(f[("IAM", "Query sobre el índice de dispositivos")][0], "FALLA")


if __name__ == "__main__":
    unittest.main()
