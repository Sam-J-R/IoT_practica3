"""Casos adicionales de las Lambdas de la P4 (complementan las pruebas escritas antes del codigo)."""

import time
import unittest
from datetime import datetime, timedelta, timezone

from tests.p4.fake_aws import ROOT, FakeAws

AHORA_MS = int(time.time() * 1000)


def hace(minutos):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutos)).isoformat()


class AlmacenamientoExtra(unittest.TestCase):
    def setUp(self):
        self.aws = FakeAws()
        self.handler = self.aws.cargar(ROOT / "lambda/almacenamiento/lambda_function.py")["lambda_handler"]
        self.tabla = self.aws.table("tendedero_historico")

    def test_campos_nulos_y_de_configuracion_se_omiten(self):
        self.handler({"reported": {"lectura_adc": 10, "agua_detectada": None, "modo": "manual",
                                   "origen": "voz", "ts_dispositivo": float(AHORA_MS),
                                   "calibracion": {"umbral_seco": 200}},
                      "thingName": "t", "ts": AHORA_MS}, None)
        item = self.tabla.items[0]
        self.assertEqual(item["ts_dispositivo"], AHORA_MS)
        for campo in ("agua_detectada", "modo", "origen", "calibracion"):
            self.assertNotIn(campo, item, "una lectura solo guarda datos de sensores")

    def test_descarta_evento_sin_forma_conocida(self):
        self.assertIn("descartado", self.handler({"thingName": "t", "ts": AHORA_MS}, None))
        self.assertEqual(self.tabla.items, [])

    def test_lectura_sin_telemetria_no_se_guarda(self):
        self.handler({"reported": {"calibracion": {"umbral_seco": 1}}, "thingName": "t", "ts": AHORA_MS}, None)
        self.assertEqual(self.tabla.items, [])

    def test_primer_documento_sin_anterior(self):
        self.handler({"actual": {"posicion": "expuesto", "origen": "voz"}, "thingName": "t", "ts": AHORA_MS}, None)
        self.assertEqual([i["cambio"] for i in self.tabla.items], ["posicion"])


class SupervisorExtra(unittest.TestCase):
    def setUp(self):
        self.aws = FakeAws()
        self.handler = self.aws.cargar(ROOT / "lambda/supervisor/lambda_function.py")["lambda_handler"]
        self.hist = self.aws.table("tendedero_historico")
        self.aws.table("tendedero_dispositivos").scan_items = [{"thingName": "uno"}, {"thingName": "dos"}]

    def test_r3_avisa_una_sola_vez_por_desconexion(self):
        self.hist.query_items = [{"thingName": "uno", "sk": "lectura#" + hace(20)},
                                 {"thingName": "uno", "sk": "alerta#" + hace(10) + "#sin_reporte",
                                  "alerta": "sin_reporte"},
                                 {"thingName": "dos", "sk": "lectura#" + hace(1)}]
        self.aws.shadows["dos"] = {"desired": {}, "reported": {"modo": "manual"}}
        resumen = self.handler({}, None)
        self.assertEqual(self.hist.items, [], "ya habia una alerta posterior a la ultima lectura")
        self.assertEqual(resumen, {"revisados": 2, "sin_reporte": 1, "reexpuestos": 0})

    def test_r2_espera_los_minutos_configurados(self):
        self.aws.shadows["uno"] = {"desired": {}, "reported": {
            "modo": "automatico", "posicion": "resguardado", "origen": "edge",
            "agua_detectada": False, "minutos_reexponer": 60}}
        self.aws.table("tendedero_dispositivos").scan_items = [{"thingName": "uno"}]
        self.hist.query_items = [{"thingName": "uno", "sk": "lectura#" + hace(1)},
                                 {"thingName": "uno", "sk": "evento#" + hace(45) + "#agua",
                                  "cambio": "agua", "agua_detectada": False}]
        self.handler({}, None)
        self.assertEqual(self.aws.shadow_updates, [], "45 min < 60 min configurados")

    def test_un_thing_con_error_no_detiene_a_los_demas(self):
        self.hist.query_items = [{"thingName": "uno", "sk": "lectura#" + hace(1)},
                                 {"thingName": "dos", "sk": "lectura#" + hace(1)}]
        self.aws.shadows["dos"] = {"desired": {}, "reported": {}}
        self.aws.data.get_thing_shadow.side_effect = [RuntimeError("sin shadow"),
                                                      self.aws._get("dos")]
        resumen = self.handler({}, None)
        self.assertEqual(resumen["revisados"], 2)


if __name__ == "__main__":
    unittest.main()
