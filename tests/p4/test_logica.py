"""Regla R4: mas de 6 movimientos en una hora -> modo manual (solo via desired)."""

import time
import unittest
from datetime import datetime, timedelta, timezone

from tests.p4.fake_aws import ROOT, FakeAws

RUTA = ROOT / "lambda" / "logica" / "lambda_function.py"
TABLA = "tendedero_historico"
LIMITE = 6


def evento_posicion(minutos_atras, posicion):
    t = datetime.now(timezone.utc) - timedelta(minutes=minutos_atras)
    return {"thingName": "tendedero-uno", "sk": "evento#" + t.isoformat(), "tipo": "evento",
            "cambio": "posicion", "posicion": posicion, "origen": "edge"}


@unittest.skipUnless(RUTA.exists(), f"todavia no existe {RUTA.relative_to(ROOT)}")
class LogicaR4Tests(unittest.TestCase):
    def setUp(self):
        self.aws = FakeAws()
        self.handler = self.aws.cargar(
            RUTA, {"DDB_HISTORY_TABLE": TABLA, "LIMITE_MOVIMIENTOS_HORA": str(LIMITE)})["lambda_handler"]
        self.tabla = self.aws.table(TABLA)
        self.evento = {"actual": {"posicion": "expuesto", "modo": "automatico"},
                       "anterior": {"posicion": "resguardado", "modo": "automatico"},
                       "thingName": "tendedero-uno", "ts": int(time.time() * 1000)}

    def test_pasa_a_manual_al_superar_el_limite(self):
        self.tabla.query_items = [evento_posicion(m, "expuesto") for m in range(LIMITE + 1)]
        self.handler(self.evento, None)
        self.assertTrue(self.aws.shadow_updates, "debio escribir el Shadow")
        thing, doc = self.aws.shadow_updates[-1]
        self.assertEqual(thing, "tendedero-uno")
        self.assertEqual(doc["state"]["desired"].get("modo"), "manual")
        self.assertNotIn("reported", doc["state"], "la Nube nunca escribe reported")
        alertas = [i for i in self.tabla.items if i["sk"].startswith("alerta#")]
        self.assertEqual(len(alertas), 1, "debe registrar una alerta")

    def test_no_actua_dentro_del_limite(self):
        self.tabla.query_items = [evento_posicion(m * 5, "expuesto") for m in range(LIMITE)]
        self.handler(self.evento, None)
        self.assertEqual(self.aws.shadow_updates, [])

    def test_no_actua_en_manual(self):
        self.tabla.query_items = [evento_posicion(m, "expuesto") for m in range(LIMITE + 3)]
        self.evento["actual"]["modo"] = "manual"
        self.handler(self.evento, None)
        self.assertEqual(self.aws.shadow_updates, [])
