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
        # Tabla de dispositivos: codigo de la etiqueta -> Thing.
        self.devices = {
            "111111": ["tendedero-uno"],
            "222222": ["tendedero-dos"],
            "333333": ["tendedero-borrado"],  # Fila huerfana: el Thing ya no existe.
            "444444": ["tendedero-uno", "tendedero-dos"],  # Error de alta: duplicado.
        }
        self.shadows = {
            "tendedero-uno": {"reported": {"agua_detectada": True, "posicion": "expuesto"}},
            "tendedero-dos": {"reported": {"agua_detectada": False, "posicion": "resguardado"}},
        }
        self.bindings_table = Mock()
        self.bindings_table.get_item.side_effect = self.read_binding
        self.bindings_table.put_item.side_effect = lambda Item: self.bindings.update({Item["userId"]: Item})
        self.bindings_table.delete_item.side_effect = lambda Key: self.bindings.pop(Key["userId"], None)
        self.devices_table = Mock()
        self.devices_table.query.side_effect = self.query_device
        tables = {
            "tendedero_vinculaciones": self.bindings_table,
            "tendedero_dispositivos": self.devices_table,
        }
        self.iot = Mock()
        self.iot.describe_thing.side_effect = self.describe
        self.data = Mock()
        self.data.get_thing_shadow.side_effect = self.read_shadow
        self.data.update_thing_shadow.side_effect = self.update_shadow

        boto3 = types.ModuleType("boto3")
        botocore = types.ModuleType("botocore")
        exceptions = types.ModuleType("botocore.exceptions")
        boto3.client = lambda name, **kwargs: {"iot": self.iot, "iot-data": self.data}[name]
        boto3.resource = lambda *args, **kwargs: Mock(Table=lambda name: tables[name])
        exceptions.ClientError = ClientError

        modules = {"boto3": boto3, "botocore": botocore, "botocore.exceptions": exceptions}
        # Sin mapa de alias: ningun nombre de Thing llega por variables de entorno.
        env = {"IOT_ENDPOINT": "endpoint.example"}
        with patch.dict(sys.modules, modules), patch.dict(os.environ, env):
            with patch.object(sys, "path", [str(ROOT / "lambda/lambda_deployment_p3.zip"), *sys.path]):
                self.handler = runpy.run_path(str(ROOT / "lambda/lambda_function.py"))["lambda_handler"]
        self.enterContext(patch.dict(os.environ, env))

    def read_binding(self, Key, ConsistentRead):
        self.assertTrue(ConsistentRead)
        item = self.bindings.get(Key["userId"])
        return {"Item": item} if item else {}

    def query_device(self, IndexName, KeyConditionExpression, ExpressionAttributeValues):
        self.assertEqual(IndexName, "codigoVinculacion-index")
        self.assertEqual(KeyConditionExpression, "codigoVinculacion = :codigo")
        things = self.devices.get(ExpressionAttributeValues[":codigo"], [])
        return {"Items": [{"thingName": thing} for thing in things]}

    def describe(self, thingName):
        if thingName not in self.shadows:
            raise ClientError("ResourceNotFoundException")

    def read_shadow(self, thingName):
        payload = json.dumps({"state": self.shadows[thingName]}).encode()
        return {"payload": io.BytesIO(payload)}

    def update_shadow(self, thingName, payload):
        for section, values in json.loads(payload)["state"].items():
            self.shadows[thingName].setdefault(section, {}).update(values)

    def ask(self, user, intent, **slots):
        event = {
            "version": "1.0",
            "session": {"new": True, "sessionId": "prueba", "user": {"userId": "ignorar"}},
            "context": {"System": {"user": {"userId": user}}},
            "request": {
                "type": "IntentRequest",
                "requestId": "prueba",
                "locale": "es-MX",
                "timestamp": "2026-11-14T12:00:00Z",
                "intent": {
                    "name": intent,
                    "confirmationStatus": "NONE",
                    "slots": {name: {"name": name, "value": value} for name, value in slots.items()},
                },
            },
        }
        return self.handler(event, None)["response"]["outputSpeech"]["ssml"]

    def test_dynamic_binding_and_shadow_routing(self):
        self.assertIn("No tienes un tendedero vinculado", self.ask("A", "ConsultarAguaIntent"))
        self.data.get_thing_shadow.assert_not_called()
        self.assertIn("He vinculado", self.ask("A", "VincularThingIntent", codigo="111111"))
        self.ask("B", "VincularThingIntent", codigo="222222")
        self.assertEqual(self.bindings["A"]["thingName"], "tendedero-uno")
        self.assertEqual(self.bindings["B"]["thingName"], "tendedero-dos")
        self.assertIn("detecta agua", self.ask("A", "ConsultarAguaIntent"))
        self.assertIn("no detecta agua", self.ask("B", "ConsultarAguaIntent"))
        self.assertIn("He solicitado", self.ask("A", "ResguardarTendederoIntent"))
        self.assertEqual(self.shadows["tendedero-uno"]["desired"]["posicion"], "resguardado")
        self.assertNotIn("desired", self.shadows["tendedero-dos"])
        self.assertIn("orden pendiente", self.ask("A", "ConsultarPosicionIntent"))

        self.assertIn("No encontré", self.ask("A", "CambiarThingIntent", codigo="999999"))
        self.assertEqual(self.bindings["A"]["thingName"], "tendedero-uno")
        self.ask("A", "CambiarThingIntent", codigo="222222")
        self.assertIn("resguardado", self.ask("A", "ConsultarPosicionIntent"))
        self.ask("A", "ExponerTendederoIntent")
        self.assertEqual(self.shadows["tendedero-dos"]["desired"]["posicion"], "expuesto")

        self.ask("A", "DesvincularThingIntent")
        self.assertNotIn("A", self.bindings)
        self.assertIn("No tienes un tendedero vinculado", self.ask("A", "ResguardarTendederoIntent"))
        self.assertIn("resguardado", self.ask("B", "ConsultarPosicionIntent"))

    def test_binding_code_is_validated_before_writing(self):
        # Codigo mal formado: no se consulta ninguna tabla.
        for codigo in ("12345", "1234567", "012345", "?"):
            self.assertIn("seis dígitos", self.ask("A", "VincularThingIntent", codigo=codigo))
        self.assertIn("seis dígitos", self.ask("A", "VincularThingIntent"))
        self.devices_table.query.assert_not_called()
        # Fila que apunta a un Thing eliminado de IoT Core.
        self.assertIn("ya no está registrado", self.ask("A", "VincularThingIntent", codigo="333333"))
        # Dos dispositivos con el mismo codigo: error, no se elige uno al azar.
        self.assertIn("No pude completar", self.ask("A", "VincularThingIntent", codigo="444444"))
        self.assertNotIn("A", self.bindings)
        # Alexa puede entregar el numero con separadores.
        self.assertIn("He vinculado", self.ask("A", "VincularThingIntent", codigo="111 111"))

    def test_uncalibrated_sensor_has_no_water_classification(self):
        self.ask("A", "VincularThingIntent", codigo="111111")
        self.shadows["tendedero-uno"]["reported"]["agua_detectada"] = None
        self.assertIn("no hay una clasificación", self.ask("A", "ConsultarAguaIntent"))

    def test_calibration_request_and_result(self):
        self.assertIn("No tienes un tendedero vinculado", self.ask("A", "CalibrarSensorIntent", condicion="seco"))
        self.ask("A", "VincularThingIntent", codigo="111111")
        shadow = self.shadows["tendedero-uno"]
        self.assertIn("todavía no ha reportado", self.ask("A", "ConsultarCalibracionIntent"))
        shadow["reported"]["calibracion"] = {"umbral_seco": 200, "umbral_agua": 600, "estado": "fabrica"}
        self.assertIn("de fábrica", self.ask("A", "ConsultarCalibracionIntent"))

        self.assertIn("en qué condición", self.ask("A", "CalibrarSensorIntent"))
        self.assertIn("en qué condición", self.ask("A", "CalibrarSensorIntent", condicion="tibio"))
        self.assertNotIn("desired", shadow)

        self.assertIn("calibra el sensor mojado", self.ask("A", "CalibrarSensorIntent", condicion="seco"))
        primero = shadow["desired"]["calibracion_solicitada"]
        self.assertEqual(primero["condicion"], "seco")
        self.assertIsInstance(primero["id"], int)
        self.assertIn("pendiente", self.ask("A", "ConsultarCalibracionIntent"))

        # El ESP32 confirma repitiendo el pedido en reported.
        shadow["reported"]["calibracion_solicitada"] = dict(primero)
        shadow["reported"]["calibracion"]["estado"] = "aplicada"
        self.assertIn("seco, se aplicó", self.ask("A", "ConsultarCalibracionIntent"))

        # Un sinonimo se normaliza; el pedido nuevo vuelve a quedar pendiente.
        with patch("time.time", return_value=primero["id"] / 1000 + 5):
            self.ask("A", "CalibrarSensorIntent", condicion="Con  Agua")
        segundo = shadow["desired"]["calibracion_solicitada"]
        self.assertEqual(segundo["condicion"], "mojado")
        self.assertGreater(segundo["id"], primero["id"])
        self.assertIn("pendiente", self.ask("A", "ConsultarCalibracionIntent"))
        shadow["reported"]["calibracion_solicitada"] = dict(segundo)
        shadow["reported"]["calibracion"]["estado"] = "rechazada"
        self.assertIn("rechazada", self.ask("A", "ConsultarCalibracionIntent"))
        shadow["reported"]["calibracion"]["estado"] = "caducada"
        self.assertIn("llegó tarde", self.ask("A", "ConsultarCalibracionIntent"))
        # La posicion del tendedero no se toca al calibrar.
        self.assertNotIn("posicion", shadow["desired"])


if __name__ == "__main__":
    unittest.main()
