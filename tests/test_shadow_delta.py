"""Recorre Lambda -> Shadow (delta calculado como AWS) -> regla del firmware.

Detecta el defecto 1 de la revision: repetir la misma condicion de calibracion
genera un delta sin `condicion` y el ESP32 lo descarta.

`pedido_de` replica la regla de `pedidoDe()` en firmware/src/ClienteShadow.cpp.
Si cambian esa funcion, actualicen esta replica; la prueba
`test_replica_coincide_con_firmware` avisa si el firmware deja de exigir `condicion`.
"""

import io
import json
import os
import re
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shadow_sim import ShadowSimulado, calcular_delta  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def pedido_de(estado):
    """Replica de pedidoDe(): exige condicion valida e id numerico >= 1."""
    pedido = estado.get("calibracion_solicitada")
    if not isinstance(pedido, dict):
        return None
    condicion, ident = pedido.get("condicion"), pedido.get("id")
    if condicion not in ("seco", "mojado") or not isinstance(ident, (int, float)) or ident < 1:
        return None
    return condicion, int(ident)


def pedido_incompleto(estado):
    """Replica del valor que devuelve pedidoDe(): id valido pero sin 'condicion'."""
    pedido = estado.get("calibracion_solicitada")
    if not isinstance(pedido, dict):
        return False
    ident = pedido.get("id")
    return "condicion" not in pedido and isinstance(ident, (int, float)) and ident >= 1


def reporte_del_esp32(pedido):
    """Lo que publica el ESP32 al atender un pedido: copia el pedido en reported."""
    return {"state": {"reported": {"calibracion_solicitada": dict(pedido),
                                   "calibracion": {"estado": "rechazada"}}}}


class ShadowDeltaTests(unittest.TestCase):
    def setUp(self):
        self.shadow = ShadowSimulado()
        data = Mock()
        data.update_thing_shadow.side_effect = (
            lambda thingName, payload: self.shadow.update(payload))
        data.get_thing_shadow.side_effect = lambda thingName: {
            "payload": io.BytesIO(json.dumps(self.shadow.documento()).encode())}
        boto3 = types.ModuleType("boto3")
        boto3.client = lambda name, **kw: {"iot": Mock(), "iot-data": data}[name]
        boto3.resource = lambda *a, **kw: Mock()
        botocore = types.ModuleType("botocore")
        exceptions = types.ModuleType("botocore.exceptions")
        exceptions.ClientError = type("ClientError", (Exception,), {})
        modules = {"boto3": boto3, "botocore": botocore, "botocore.exceptions": exceptions}
        env = {"IOT_ENDPOINT": "endpoint.example"}
        with patch.dict(sys.modules, modules), patch.dict(os.environ, env):
            with patch.object(sys, "path", [str(ROOT / "lambda/lambda_deployment_p3.zip"), *sys.path]):
                mod = runpy.run_path(str(ROOT / "lambda/lambda_function.py"))
            self.servicio = mod["ShadowService"]()
        self.ids = iter(range(1_700_000_000_000, 1_800_000_000_000, 1000))

    def pedir(self, condicion):
        with patch("time.time", lambda: next(self.ids) / 1000):
            self.servicio.request_calibration("tendedero-uno", condicion)
        return self.shadow.deltas[-1]["state"]

    def atender(self, delta):
        """Como el firmware: si el delta trae el pedido sin 'condicion', relee el Shadow (GET)."""
        self.gets = getattr(self, "gets", 0)
        pedido = pedido_de(delta)
        if pedido is None and pedido_incompleto(delta):
            self.gets += 1
            pedido = pedido_de(self.shadow.documento()["state"]["desired"])
        if pedido:
            condicion, ident = pedido
            self.shadow.update(reporte_del_esp32({"condicion": condicion, "id": ident}))
        return pedido

    def test_simulador_sigue_el_ejemplo_de_aws(self):
        desired = {"lights": {"color": {"r": 255, "g": 255, "b": 255}}}
        reported = {"lights": {"color": {"r": 255, "g": 0, "b": 255}}}
        self.assertEqual(calcular_delta(desired, reported), {"lights": {"color": {"g": 255}}})

    def test_primera_calibracion_llega(self):
        self.assertIsNotNone(self.atender(self.pedir("seco")))

    def test_seco_y_luego_mojado_llegan(self):
        self.assertIsNotNone(self.atender(self.pedir("seco")))
        self.assertIsNotNone(self.atender(self.pedir("mojado")))

    def test_repetir_la_misma_condicion_llega(self):
        """DEFECTO 1: tras un rechazo, repetir 'seco' debe llegar al ESP32."""
        self.atender(self.pedir("seco"))
        delta = self.pedir("seco")
        self.assertIsNotNone(
            self.atender(delta),
            f"El ESP32 recibiria {json.dumps(delta)} y lo descartaria por no traer 'condicion'")

    def test_primera_calibracion_no_necesita_get(self):
        self.atender(self.pedir("seco"))
        self.atender(self.pedir("mojado"))
        self.assertEqual(self.gets, 0, "solo el pedido incompleto debe provocar un GET")

    def test_repetir_usa_un_solo_get(self):
        self.atender(self.pedir("seco"))
        self.atender(self.pedir("seco"))
        self.assertEqual(self.gets, 1)

    def test_replica_coincide_con_firmware(self):
        fuente = (ROOT / "firmware/src/ClienteShadow.cpp").read_text(encoding="utf-8")
        cuerpo = re.search(r"bool pedidoDe\(.*?\n}\n", fuente, re.S)
        self.assertIsNotNone(cuerpo, "No se encontro bool pedidoDe() en ClienteShadow.cpp")
        self.assertIn('"condicion"', cuerpo.group(0),
                      "pedidoDe() cambio: actualicen la replica pedido_de() de esta prueba")
        self.assertIn("pedidoIncompleto", fuente,
                      "el firmware debe marcar el delta sin 'condicion' y pedir el Shadow completo")
        bloque = re.search(r"if \(evento\.pedidoIncompleto\) \{(.*?)\n      \}", fuente, re.S)
        self.assertTrue(bloque and "pedirShadow()" in bloque.group(1),
                        "con un pedido incompleto el firmware debe llamar a pedirShadow()")
