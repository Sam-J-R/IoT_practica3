"""Reglas programadas: R3 (sin reporte) y R2 (volver a exponer)."""

import unittest
from datetime import datetime, timedelta, timezone

from tests.p4.fake_aws import ROOT, FakeAws

RUTA = ROOT / "lambda" / "supervisor" / "lambda_function.py"
HIST = "tendedero_historico"
DISP = "tendedero_dispositivos"


def hace(minutos):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutos)).isoformat()


@unittest.skipUnless(RUTA.exists(), f"todavia no existe {RUTA.relative_to(ROOT)}")
class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.aws = FakeAws()
        self.handler = self.aws.cargar(
            RUTA, {"DDB_HISTORY_TABLE": HIST, "DDB_DEVICES_TABLE": DISP})["lambda_handler"]
        self.hist = self.aws.table(HIST)
        self.aws.table(DISP).scan_items = [{"thingName": "tendedero-uno", "codigoVinculacion": "111111"}]

    def shadow(self, **reported):
        base = {"modo": "automatico", "posicion": "expuesto", "agua_detectada": False,
                "minutos_reexponer": 30, "origen": "voz"}
        base.update(reported)
        self.aws.shadows["tendedero-uno"] = {"desired": {}, "reported": base}

    def test_r3_alerta_si_no_reporta_en_3_min(self):
        self.shadow()
        self.hist.query_items = [{"thingName": "tendedero-uno", "sk": "lectura#" + hace(10), "tipo": "lectura"}]
        self.handler({}, None)
        alertas = [i for i in self.hist.items if i["sk"].startswith("alerta#")]
        self.assertEqual(len(alertas), 1, "debe registrar la alerta sin_reporte")

    def test_r3_sin_alerta_si_reporta(self):
        self.shadow()
        self.hist.query_items = [{"thingName": "tendedero-uno", "sk": "lectura#" + hace(1), "tipo": "lectura"}]
        self.handler({}, None)
        self.assertEqual([i for i in self.hist.items if i["sk"].startswith("alerta#")], [])

    def test_r2_reexpone_tras_la_espera(self):
        self.shadow(posicion="resguardado", origen="edge", agua_detectada=False)
        self.hist.query_items = [
            {"thingName": "tendedero-uno", "sk": "lectura#" + hace(1), "tipo": "lectura"},
            {"thingName": "tendedero-uno", "sk": "evento#" + hace(45), "tipo": "evento",
             "cambio": "agua", "agua_detectada": False},
        ]
        self.handler({}, None)
        deseados = [d["state"]["desired"] for _, d in self.aws.shadow_updates]
        self.assertIn({"posicion": "expuesto", "origen": "nube"},
                      [{k: v for k, v in d.items() if k in ("posicion", "origen")} for d in deseados])

    def test_r2_no_reexpone_si_lo_resguardo_el_usuario(self):
        self.shadow(posicion="resguardado", origen="voz", agua_detectada=False)
        self.hist.query_items = [
            {"thingName": "tendedero-uno", "sk": "lectura#" + hace(1), "tipo": "lectura"},
            {"thingName": "tendedero-uno", "sk": "evento#" + hace(45), "tipo": "evento",
             "cambio": "agua", "agua_detectada": False},
        ]
        self.handler({}, None)
        self.assertFalse([d for _, d in self.aws.shadow_updates
                          if d["state"]["desired"].get("posicion") == "expuesto"])

    def test_r2_no_actua_en_manual_ni_con_agua(self):
        for reported in ({"modo": "manual"}, {"agua_detectada": True}):
            self.aws.shadow_updates.clear()
            self.shadow(posicion="resguardado", origen="edge", **reported)
            self.handler({}, None)
            self.assertFalse([d for _, d in self.aws.shadow_updates
                              if d["state"]["desired"].get("posicion") == "expuesto"], reported)
