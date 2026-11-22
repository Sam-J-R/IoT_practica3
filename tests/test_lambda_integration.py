"""Ejercita el handler real de Alexa con AWS simulado en memoria."""

import io
import json
import os
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class ClientError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class LambdaTests(unittest.TestCase):
    def setUp(self):
        self.bindings = {}
        self.shadows = {
            "tendedero-uno": {"reported": {"agua_detectada": True, "cubierta": "abierta"}},
            "tendedero-dos": {"reported": {"agua_detectada": False, "cubierta": "cerrada"}},
        }
        self.table = Mock()
        self.table.get_item.side_effect = self.read_binding
        self.table.put_item.side_effect = lambda Item: self.bindings.update({Item["userId"]: Item})
        self.table.delete_item.side_effect = lambda Key: self.bindings.pop(Key["userId"], None)
        self.iot = Mock()
        self.iot.describe_thing.side_effect = self.describe
        self.data = Mock()
        self.data.get_thing_shadow.side_effect = self.read_shadow
        self.data.update_thing_shadow.side_effect = self.update_shadow

        boto3 = types.ModuleType("boto3")
        botocore = types.ModuleType("botocore")
        exceptions = types.ModuleType("botocore.exceptions")
        boto3.client = lambda name, **kwargs: {"iot": self.iot, "iot-data": self.data}[name]
        boto3.resource = lambda *args, **kwargs: Mock(Table=lambda name: self.table)
        exceptions.ClientError = ClientError

        modules = {"boto3": boto3, "botocore": botocore, "botocore.exceptions": exceptions}
        env = {
            "IOT_ENDPOINT": "endpoint.example",
            "THING_ALIASES_JSON": json.dumps({
                "grupo uno": "tendedero-uno",
                "grupo dos": "tendedero-dos",
                "grupo 2": "tendedero-dos",
            }),
        }
        with patch.dict(sys.modules, modules), patch.dict(os.environ, env):
            with patch.object(sys, "path", [str(ROOT / "lambda/lambda_deployment_p3.zip"), *sys.path]):
                self.handler = runpy.run_path(str(ROOT / "lambda/lambda_function.py"))["lambda_handler"]
        self.enterContext(patch.dict(os.environ, env))

    def read_binding(self, Key, ConsistentRead):
        self.assertTrue(ConsistentRead)
        item = self.bindings.get(Key["userId"])
        return {"Item": item} if item else {}

    def describe(self, thingName):
        if thingName not in self.shadows:
            raise ClientError("ResourceNotFoundException")

    def read_shadow(self, thingName):
        payload = json.dumps({"state": self.shadows[thingName]}).encode()
        return {"payload": io.BytesIO(payload)}

    def update_shadow(self, thingName, payload):
        self.shadows[thingName].update(json.loads(payload)["state"])

    def ask(self, user, intent, value=None):
        slots = {"thing_name": {"name": "thing_name", "value": value}} if value else {}
        event = {
            "version": "1.0",
            "session": {"new": True, "sessionId": "prueba", "user": {"userId": "ignorar"}},
            "context": {"System": {"user": {"userId": user}}},
            "request": {
                "type": "IntentRequest",
                "requestId": "prueba",
                "locale": "es-MX",
                "timestamp": "2026-11-07T12:00:00Z",
                "intent": {"name": intent, "confirmationStatus": "NONE", "slots": slots},
            },
        }
        return self.handler(event, None)["response"]["outputSpeech"]["ssml"]

    def test_dynamic_binding_and_shadow_routing(self):
        self.assertIn("vinculado", self.ask("A", "ConsultarAguaIntent"))
        self.data.get_thing_shadow.assert_not_called()
        self.ask("A", "VincularThingIntent", "Grupo uno")
        self.ask("B", "VincularThingIntent", "grupo dos")
        self.assertIn("detecta agua", self.ask("A", "ConsultarAguaIntent"))
        self.assertIn("no detecta agua", self.ask("B", "ConsultarAguaIntent"))
        self.assertIn("He solicitado", self.ask("A", "CerrarCubiertaIntent"))
        self.assertEqual(self.shadows["tendedero-uno"]["desired"]["cubierta"], "cerrada")
        self.assertNotIn("desired", self.shadows["tendedero-dos"])
        self.assertIn("orden pendiente", self.ask("A", "ConsultarCubiertaIntent"))

        self.assertIn("objeto registrado", self.ask("A", "CambiarThingIntent", "inexistente"))
        self.assertEqual(self.bindings["A"]["thingName"], "tendedero-uno")
        self.ask("A", "CambiarThingIntent", "grupo 2")
        self.assertIn("cerrada", self.ask("A", "ConsultarCubiertaIntent"))
        self.ask("A", "AbrirCubiertaIntent")
        self.assertEqual(self.shadows["tendedero-dos"]["desired"]["cubierta"], "abierta")

        self.ask("A", "DesvincularThingIntent")
        self.assertNotIn("A", self.bindings)
        self.assertIn("Primero vincula", self.ask("A", "CerrarCubiertaIntent"))
        self.assertIn("cerrada", self.ask("B", "ConsultarCubiertaIntent"))

    def test_uncalibrated_sensor_has_no_water_classification(self):
        self.ask("A", "VincularThingIntent", "grupo uno")
        self.shadows["tendedero-uno"]["reported"]["agua_detectada"] = None
        self.assertIn("no hay una clasificación", self.ask("A", "ConsultarAguaIntent"))


if __name__ == "__main__":
    unittest.main()
