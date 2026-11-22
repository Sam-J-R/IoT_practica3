"""Checks that run offline with the standard library; NOT AWS/ESP32 tests."""

import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StaticContract(unittest.TestCase):
    def test_lambda_python_syntax(self):
        source = (ROOT / "lambda" / "lambda_function.py").read_text(encoding="utf-8")
        ast.parse(source)

    def test_intents_exist(self):
        model = json.loads((ROOT / "alexa" / "interaction-model-es-MX.json").read_text(encoding="utf-8"))
        intents = {i["name"] for i in model["interactionModel"]["languageModel"]["intents"]}
        required = {
            "VincularThingIntent", "CambiarThingIntent", "DesvincularThingIntent",
            "ConsultarAguaIntent", "AbrirCubiertaIntent", "CerrarCubiertaIntent", "ConsultarCubiertaIntent"
        }
        self.assertTrue(required <= intents)
        self.assertFalse(any("led" in name.casefold() for name in intents))

    def test_aws_policies_parse(self):
        for name in ("lambda-iam-policy.template.json", "iot-certificate-policy.template.json"):
            data = json.loads((ROOT / "aws" / name).read_text(encoding="utf-8"))
            self.assertEqual(data["Version"], "2012-10-17")

    def test_binding_ops_present(self):
        source = (ROOT / "lambda" / "lambda_function.py").read_text(encoding="utf-8")
        for key in ("describe_thing", "get_item", "put_item", "delete_item", "get_thing_shadow", "update_thing_shadow"):
            self.assertIn(key, source)

    def test_sensor_is_analog(self):
        source = (ROOT / "firmware" / "src" / "SensorTest.cpp").read_text(encoding="utf-8")
        sensor = (ROOT / "firmware" / "include" / "SensorAgua.h").read_text(encoding="utf-8")
        config = (ROOT / "firmware" / "include" / "config.h").read_text(encoding="utf-8")
        self.assertIn("analogRead(PIN_AGUA_ANALOGICO)", sensor)
        self.assertIn('#include "SensorAgua.h"', source)
        self.assertNotIn("PIN_LED", config)

    def test_production_is_default_and_diagnostics_are_isolated(self):
        config = (ROOT / "firmware" / "platformio.ini").read_text(encoding="utf-8")
        self.assertIn("default_envs = tendedero_shadow", config)
        self.assertIn("[env:sensor_test]\nbuild_src_filter = +<SensorTest.cpp>", config)
        self.assertIn("build_src_filter = +<Tendedero.cpp> +<ClienteShadow.cpp>", config)
        source = (ROOT / "firmware" / "src" / "SensorTest.cpp").read_text(encoding="utf-8")
        self.assertIn("sensor.leerRaw()", source)
        self.assertNotIn("ClienteShadow", source)

    def test_shadow_send_and_subscription_failures_are_logged(self):
        shadow = (ROOT / "firmware" / "src" / "ClienteShadow.cpp").read_text(encoding="utf-8")
        self.assertIn("esp_mqtt_client_subscribe(cliente_, tema->c_str(), 1) < 0", shadow)
        self.assertIn("esp_mqtt_client_enqueue(cliente_, update_.c_str(), payload, 0, 0, 0, true) < 0", shadow)
        self.assertIn("suscribir();", shadow)

    def test_servo_diagnostic_guards_calibration(self):
        config = (ROOT / "firmware" / "platformio.ini").read_text(encoding="utf-8")
        source = (ROOT / "firmware" / "src" / "ServoTest.cpp").read_text(encoding="utf-8")
        self.assertIn("[env:servo_test]", config)
        self.assertIn("parametrosValidos()", source)
        self.assertIn("if (!parametrosValidos())", source)
        self.assertIn("servo.solicitar(Posicion::Abierta", source)
        self.assertIn("servo.solicitar(Posicion::Cerrada", source)
        self.assertNotIn("WiFi.begin", source)

    def test_sensor_shadow_diagnostic_never_controls_servo(self):
        config = (ROOT / "firmware" / "platformio.ini").read_text(encoding="utf-8")
        source = (ROOT / "firmware" / "src" / "SensorShadowTest.cpp").read_text(encoding="utf-8")
        shadow = (ROOT / "firmware" / "src" / "ClienteShadow.cpp").read_text(encoding="utf-8")
        self.assertIn("[env:sensor_shadow_test]", config)
        self.assertIn("+<SensorShadowTest.cpp> +<ClienteShadow.cpp>", config)
        self.assertIn("shadow.atender(ahora, static_cast<ServoCubierta*>(nullptr))", source)
        self.assertIn("shadow.reportarSensor(ahora, raw)", source)
        self.assertIn('\\\"sensor_raw\\\":%d', shadow)
        self.assertNotIn("servo.solicitar", source)


if __name__ == "__main__":
    unittest.main()

