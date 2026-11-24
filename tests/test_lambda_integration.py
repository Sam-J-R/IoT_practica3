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
sys.path.insert(0, str(ROOT))
from tests.fake_vinculaciones import TablaVinculaciones  # noqa: E402

# El SDK del ZIP resuelve sus clases al deserializar cada evento: se importa una
# vez, fuera de patch.dict, para que las clases no se descarten entre pruebas.
_SDK = str(ROOT / "lambda/lambda_deployment_p3.zip")
if _SDK not in sys.path:
    sys.path.append(_SDK)
import ask_sdk_core.utils  # noqa: E402,F401
import ask_sdk_model  # noqa: E402,F401


class ClientError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class LambdaTests(unittest.TestCase):
    def setUp(self):
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
        self.bindings_table = TablaVinculaciones()
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
            self.module = runpy.run_path(str(ROOT / "lambda/lambda_function.py"))
        self.handler = self.module["lambda_handler"]
        # Reloj que siempre avanza, para fechas de vinculacion distintas y deterministas.
        self.tick = 0

        def ahora():
            self.tick += 1
            return "2026-11-21T10:00:{:02d}.000000+00:00".format(self.tick)
        # run_path devuelve una copia de los globales: se cambia el diccionario real.
        self.module["BindingRepository"].bind.__globals__["_ahora"] = ahora
        self.enterContext(patch.dict(os.environ, env))

    def bound(self, user):
        """thingName -> nombre de los tendederos del usuario."""
        return {t: i["nombre"] for t, i in self.bindings_table.de(user).items()}

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
        return self.ask_full(user, intent, **slots)["outputSpeech"]["ssml"]

    def ask_full(self, user, intent, **slots):
        """Respuesta completa de la skill (texto, directivas y fin de sesion)."""
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
        return self.handler(event, None)["response"]

    def test_dynamic_binding_and_shadow_routing(self):
        self.assertIn("No tienes un tendedero vinculado", self.ask("A", "ConsultarAguaIntent"))
        self.data.get_thing_shadow.assert_not_called()
        # Primer tendedero sin nombre: queda como "principal" y la respuesta no lleva prefijo.
        self.assertIn("He vinculado tu tendedero principal", self.ask("A", "VincularThingIntent", codigo="111111"))
        self.ask("B", "VincularThingIntent", codigo="222222", nombre="patio")
        self.assertEqual(self.bound("A"), {"tendedero-uno": "principal"})
        self.assertEqual(self.bound("B"), {"tendedero-dos": "patio"})
        respuesta = self.ask("A", "ConsultarAguaIntent")
        self.assertIn("detecta agua", respuesta)
        self.assertNotIn("Tendedero principal:", respuesta)
        self.assertIn("no detecta agua", self.ask("B", "ConsultarAguaIntent"))
        self.assertIn("He solicitado", self.ask("A", "ResguardarTendederoIntent"))
        self.assertEqual(self.shadows["tendedero-uno"]["desired"]["posicion"], "resguardado")
        self.assertNotIn("desired", self.shadows["tendedero-dos"])
        self.assertIn("orden pendiente", self.ask("A", "ConsultarPosicionIntent"))

        self.assertIn("No encontré", self.ask("A", "VincularThingIntent", codigo="999999", nombre="terraza"))
        self.assertEqual(self.bound("A"), {"tendedero-uno": "principal"})

        self.ask("A", "DesvincularThingIntent")
        self.assertEqual(self.bound("A"), {})
        self.assertIn("No tienes un tendedero vinculado", self.ask("A", "ResguardarTendederoIntent"))
        # Desvincular a A no toca los tendederos de B.
        self.assertIn("resguardado", self.ask("B", "ConsultarPosicionIntent"))

    def test_un_usuario_con_varios_tendederos(self):
        self.ask("A", "VincularThingIntent", codigo="111111", nombre="patio")
        # Con un solo tendedero no hace falta nombrarlo.
        self.assertIn("detecta agua", self.ask("A", "ConsultarAguaIntent"))
        # Un segundo tendedero necesita nombre para distinguirlo del primero.
        self.assertIn("necesita un nombre", self.ask("A", "VincularThingIntent", codigo="222222"))
        self.assertIn("Ya tienes un tendedero llamado pátio",
                      self.ask("A", "VincularThingIntent", codigo="222222", nombre="Pátio"))
        respuesta = self.ask("A", "VincularThingIntent", codigo="222222", nombre="la Terraza")
        self.assertIn("Ahora tienes 2 tendederos: patio y terraza", respuesta)
        self.assertIn("te preguntaré", respuesta)
        self.assertEqual(self.bound("A"), {"tendedero-uno": "patio", "tendedero-dos": "terraza"})
        self.assertNotIn("fechaSeleccion", self.bindings_table.de("A")["tendedero-dos"])

        # Sin nombre en la frase, Alexa pregunta cual y conserva el intent con sus slots.
        lecturas = self.data.get_thing_shadow.call_count
        respuesta = self.ask_full("A", "CalibrarSensorIntent", condicion="seco")
        self.assertIn("¿En cuál tendedero? Tienes patio o terraza", respuesta["outputSpeech"]["ssml"])
        directiva = respuesta["directives"][0]
        self.assertEqual(directiva["type"], "Dialog.ElicitSlot")
        self.assertEqual(directiva["slotToElicit"], "nombre")
        self.assertEqual(directiva["updatedIntent"]["name"], "CalibrarSensorIntent")
        self.assertEqual(directiva["updatedIntent"]["slots"]["condicion"]["value"], "seco")
        self.assertFalse(respuesta["shouldEndSession"])
        # No se leyo ni escribio ningun Shadow mientras no se sabe cual.
        self.assertEqual(self.data.get_thing_shadow.call_count, lecturas)
        self.data.update_thing_shadow.assert_not_called()
        # Alexa vuelve con la respuesta del usuario en el slot: se cumple la orden original.
        respuesta = self.ask("A", "CalibrarSensorIntent", condicion="seco", nombre="el de la terraza")
        self.assertIn("Tendedero terraza:", respuesta)
        self.assertEqual(self.shadows["tendedero-dos"]["desired"]["calibracion_solicitada"]["condicion"], "seco")
        self.assertNotIn("desired", self.shadows["tendedero-uno"])

        # Nombrar el tendedero en la frase actua sobre ese y la respuesta lo confirma.
        respuesta = self.ask("A", "ResguardarTendederoIntent", nombre="del patio")
        self.assertIn("Tendedero patio:", respuesta)
        self.assertEqual(self.shadows["tendedero-uno"]["desired"]["posicion"], "resguardado")
        self.assertNotIn("posicion", self.shadows["tendedero-dos"]["desired"])
        # Ninguna orden queda dirigida a un tendedero por defecto: siempre se pregunta.
        self.assertEqual(self.ask_full("A", "ConsultarPosicionIntent")["directives"][0]["type"], "Dialog.ElicitSlot")
        self.assertIn("No tienes un tendedero llamado azotea. Tus tendederos son: patio y terraza",
                      self.ask("A", "ExponerTendederoIntent", nombre="azotea"))
        respuesta = self.ask("A", "ListarTendederosIntent")
        self.assertIn("Tienes 2 tendederos: patio y terraza", respuesta)
        self.assertIn("di en cuál", respuesta)

        # Otro usuario puede vincular el mismo tendedero (una casa con dos cuentas).
        self.ask("B", "VincularThingIntent", codigo="111111", nombre="casa")
        self.assertEqual(self.bound("B"), {"tendedero-uno": "casa"})
        self.assertEqual(self.bound("A")["tendedero-uno"], "patio")
        self.assertNotIn("Tendedero casa:", self.ask("B", "ConsultarAguaIntent"))

        # Volver a vincular el mismo codigo renombra y conserva la fecha de vinculacion.
        fecha = self.bindings_table.de("A")["tendedero-dos"]["fechaVinculacion"]
        self.assertIn("Ahora se llama azotea", self.ask("A", "VincularThingIntent", codigo="222222", nombre="azotea"))
        self.assertEqual(self.bindings_table.de("A")["tendedero-dos"]["fechaVinculacion"], fecha)
        self.assertEqual(len(self.bound("A")), 2)

        # Con varios, desvincular sin nombre tambien pregunta cual.
        respuesta = self.ask_full("A", "DesvincularThingIntent")
        self.assertIn("¿Cuál quieres desvincular? Tienes azotea o patio", respuesta["outputSpeech"]["ssml"])
        self.assertEqual(respuesta["directives"][0]["updatedIntent"]["name"], "DesvincularThingIntent")
        self.assertEqual(len(self.bound("A")), 2)
        respuesta = self.ask("A", "DesvincularThingIntent", nombre="azotea")
        self.assertIn("He desvinculado el tendedero azotea. Tu tendedero se llama patio", respuesta)
        self.assertEqual(self.bound("A"), {"tendedero-uno": "patio"})
        # Con uno solo, vuelve a no hacer falta el nombre ni el prefijo.
        respuesta = self.ask("A", "ConsultarAguaIntent")
        self.assertIn("detecta agua", respuesta)
        self.assertNotIn("Tendedero patio:", respuesta)

    def test_tope_de_tendederos_por_usuario(self):
        self.module["BindingRepository"].bind.__globals__["MAX_TENDEDEROS"] = 1
        self.ask("A", "VincularThingIntent", codigo="111111", nombre="patio")
        self.assertIn("que es el máximo", self.ask("A", "VincularThingIntent", codigo="222222", nombre="terraza"))
        self.assertEqual(self.bound("A"), {"tendedero-uno": "patio"})
        # Renombrar el que ya tiene no cuenta como uno nuevo.
        self.assertIn("Ahora se llama terraza", self.ask("A", "VincularThingIntent", codigo="111111", nombre="terraza"))

    def test_nombres_se_comparan_sin_tildes_ni_articulos(self):
        limpiar = self.module["limpiar_nombre"]
        clave = self.module["clave_nombre"]
        self.assertEqual(limpiar("el tendedero del  Patio"), "patio")
        self.assertEqual(limpiar("de la terraza"), "terraza")
        self.assertEqual(limpiar("Balcón"), "balcón")
        self.assertEqual(clave("Balcón"), clave("balcon"))
        nombres = [{"thingName": "t", "nombre": n} for n in ("b", "a", "c")]
        self.assertEqual(self.module["lista_hablada"](nombres), "a, b y c")

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
        self.assertEqual(self.bound("A"), {})
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

    def test_voz_convive_con_la_logica_automatica(self):
        """P4: origen voz, rechazo de exponer con lluvia en automatico y posicion repetida."""
        self.ask("A", "VincularThingIntent", codigo="111111")
        shadow = self.shadows["tendedero-uno"]
        self.ask("A", "ResguardarTendederoIntent")
        self.assertEqual(shadow["desired"], {"posicion": "resguardado", "origen": "voz"})
        # En automatico y con agua, exponer se rechaza sin escribir nada.
        shadow["reported"].update({"posicion": "resguardado", "modo": "automatico", "agua_detectada": True})
        self.assertIn("modo manual", self.ask("A", "ExponerTendederoIntent"))
        self.assertEqual(shadow["desired"]["posicion"], "resguardado")
        # Ya resguardado sin otra orden pendiente: no se escribe un desired que solo cambie el origen.
        escrituras = self.data.update_thing_shadow.call_count
        self.assertIn("ya está resguardado", self.ask("A", "ResguardarTendederoIntent"))
        self.assertEqual(self.data.update_thing_shadow.call_count, escrituras)
        # En manual, la voz manda aunque haya agua.
        shadow["reported"]["modo"] = "manual"
        self.assertIn("He solicitado", self.ask("A", "ExponerTendederoIntent"))
        self.assertEqual(shadow["desired"]["posicion"], "expuesto")

    def test_modo_y_espera_por_voz(self):
        self.ask("A", "VincularThingIntent", codigo="111111")
        shadow = self.shadows["tendedero-uno"]
        self.assertIn("todavía no ha reportado su modo", self.ask("A", "ConsultarModoIntent"))
        self.assertIn("modo automático", self.ask("A", "CambiarModoIntent", modo="automático"))
        self.assertEqual(shadow["desired"]["modo"], "automatico")
        self.assertIn("Qué modo", self.ask("A", "CambiarModoIntent", modo="turbo"))
        self.assertIn("modo manual", self.ask("A", "CambiarModoIntent", modo="Manual"))
        self.assertEqual(shadow["desired"]["modo"], "manual")
        shadow["reported"].update({"modo": "automatico", "minutos_reexponer": 30})
        respuesta = self.ask("A", "ConsultarModoIntent")
        self.assertIn("modo automático", respuesta)
        self.assertIn("30 minutos", respuesta)
        self.assertIn("pendiente a modo manual", respuesta)
        self.assertIn("45 minutos", self.ask("A", "ConfigurarEsperaIntent", minutos="45"))
        self.assertEqual(shadow["desired"]["minutos_reexponer"], 45)
        for fuera in ("2", "10", "300", "?"):
            self.assertIn("entre 15 y 240", self.ask("A", "ConfigurarEsperaIntent", minutos=fuera))
        self.assertEqual(shadow["desired"]["minutos_reexponer"], 45)

    def test_luz_para_recoger_la_ropa(self):
        self.ask("A", "VincularThingIntent", codigo="111111")
        shadow = self.shadows["tendedero-uno"]
        self.assertIn("no tiene la luz", self.ask("A", "EncenderLuzIntent"))
        self.assertIn("no tiene la luz", self.ask("A", "ConsultarLuzIntent"))
        self.assertNotIn("led", shadow.get("desired", {}))
        # La luz obedece a la voz en cualquier modo, de dia o de noche.
        shadow["reported"].update({"led": "apagado", "oscuro": True, "modo": "automatico"})
        self.assertIn("Se apagará sola en 10 minutos", self.ask("A", "EncenderLuzIntent"))
        self.assertEqual(shadow["desired"], {"led": "encendido"})  # sin origen_led: solo la voz ordena la luz
        shadow["reported"]["led"] = "encendido"
        self.assertIn("está encendida", self.ask("A", "ConsultarLuzIntent"))
        # Repetir la orden no escribe un desired que ya esta.
        escrituras = self.data.update_thing_shadow.call_count
        self.assertIn("ya está encendida", self.ask("A", "EncenderLuzIntent"))
        self.assertEqual(self.data.update_thing_shadow.call_count, escrituras)
        shadow["reported"]["modo"] = "manual"
        self.assertIn("apagar la luz", self.ask("A", "ApagarLuzIntent"))
        self.assertEqual(shadow["desired"]["led"], "apagado")

    def test_motivo_de_la_posicion(self):
        self.ask("A", "VincularThingIntent", codigo="111111")
        reported = self.shadows["tendedero-uno"]["reported"]
        casos = [
            ({"posicion": "resguardado", "origen": "edge", "agua_detectada": True, "oscuro": False,
              "modo": "automatico", "minutos_reexponer": 30},
             ["resguardado porque está lloviendo", "cuando pasen 30 minutos sin agua y haya luz"]),
            ({"posicion": "resguardado", "origen": "edge", "agua_detectada": False, "oscuro": True,
              "modo": "automatico"}, ["resguardado porque ya oscureció"]),
            ({"posicion": "resguardado", "origen": "voz", "agua_detectada": False, "oscuro": False,
              "modo": "automatico"}, ["porque se lo pediste", "No volverá a salir solo"]),
            ({"posicion": "resguardado", "origen": "voz", "modo": "manual"},
             ["porque se lo pediste", "modo manual, así que solo saldrá cuando lo pidas"]),
            ({"posicion": "expuesto", "origen": "nube", "agua_detectada": False, "oscuro": False,
              "modo": "automatico"}, ["expuesto y recibiendo luz", "Se resguardará solo si llueve o anochece"]),
            ({"posicion": "expuesto", "origen": "voz", "oscuro": True, "modo": "manual"},
             ["expuesto.", "si llueve o anochece, no se resguardará solo"]),
        ]
        for estado, esperado in casos:
            reported.clear()
            reported.update(estado)
            respuesta = self.ask("A", "ConsultarPosicionIntent")
            for texto in esperado:
                self.assertIn(texto, respuesta, estado)
        reported.clear()
        self.assertIn("todavía no ha reportado su posición", self.ask("A", "ConsultarPosicionIntent"))

    def test_exponer_de_noche_en_automatico_se_rechaza(self):
        self.ask("A", "VincularThingIntent", codigo="111111")
        shadow = self.shadows["tendedero-uno"]
        shadow["reported"] = {"posicion": "resguardado", "modo": "automatico", "agua_detectada": False,
                              "oscuro": True}
        self.assertIn("Ya es de noche", self.ask("A", "ExponerTendederoIntent"))
        self.assertNotIn("desired", shadow)
        # En manual, la voz manda aunque sea de noche.
        shadow["reported"]["modo"] = "manual"
        self.assertIn("He solicitado", self.ask("A", "ExponerTendederoIntent"))
        self.assertEqual(shadow["desired"]["posicion"], "expuesto")

if __name__ == "__main__":
    unittest.main()
