"""RF11 y RF12: la Lambda de almacenamiento valida, enriquece y guarda."""

import time
import unittest
from pathlib import Path

from tests.p4.fake_aws import ROOT, FakeAws

RUTA = ROOT / "lambda" / "almacenamiento" / "lambda_function.py"
TABLA = "tendedero_historico"
AHORA_MS = int(time.time() * 1000)


@unittest.skipUnless(RUTA.exists(), f"todavia no existe {RUTA.relative_to(ROOT)}")
class AlmacenamientoTests(unittest.TestCase):
    def setUp(self):
        self.aws = FakeAws()
        self.handler = self.aws.cargar(RUTA, {"DDB_HISTORY_TABLE": TABLA})["lambda_handler"]
        self.tabla = self.aws.table(TABLA)

    def lectura(self, **reported):
        base = {"lectura_adc": 120, "agua_detectada": False, "posicion": "expuesto", "modo": "automatico"}
        base.update(reported)
        return {"reported": base, "thingName": "tendedero-uno", "ts": AHORA_MS}

    def test_guarda_lectura_valida_con_thing_y_fecha(self):
        self.handler(self.lectura(), None)
        self.assertEqual(len(self.tabla.items), 1)
        item = self.tabla.items[0]
        self.assertEqual(item["thingName"], "tendedero-uno")
        self.assertTrue(item["sk"].startswith("lectura#20"), item["sk"])
        self.assertEqual(item["tipo"], "lectura")
        self.assertEqual(int(item["lectura_adc"]), 120)
        self.assertGreater(int(item["ttl"]), time.time(), "ttl debe ser epoch en segundos, en el futuro")

    def test_guarda_las_marcas_para_medir_latencia(self):
        """RNF latencia: ts_iot (hora de la regla) y ts_guardado (hora de la Lambda), en ms."""
        evento = self.lectura(ts_dispositivo=AHORA_MS - 150)
        self.handler(evento, None)
        item = self.tabla.items[0]
        self.assertEqual(int(item["ts_iot"]), AHORA_MS)
        self.assertGreaterEqual(int(item["ts_guardado"]), AHORA_MS - 1000)
        self.assertEqual(int(item["ts_dispositivo"]), AHORA_MS - 150)

    def test_descarta_lecturas_invalidas(self):
        invalidas = [
            self.lectura(lectura_adc=5000),        # fuera de 0..4095
            self.lectura(lectura_adc="alto"),      # tipo incorrecto
            self.lectura(agua_detectada="si"),     # no es booleano
            self.lectura(posicion="abierta"),      # valor de la P3
            {"reported": {"lectura_adc": 10}, "ts": AHORA_MS},  # sin thingName
        ]
        for evento in invalidas:
            self.handler(evento, None)
        self.assertEqual(self.tabla.items, [], "ninguna lectura invalida debe guardarse")

    def test_no_falla_con_reporte_parcial(self):
        """El reporte periodico puede no traer todos los campos (p. ej. sin calibracion)."""
        self.handler({"reported": {"lectura_adc": 50, "agua_detectada": False},
                      "thingName": "tendedero-uno", "ts": AHORA_MS}, None)
        self.assertEqual(len(self.tabla.items), 1)

    def test_evento_de_posicion_con_origen(self):
        self.handler({"actual": {"posicion": "resguardado", "origen": "edge", "agua_detectada": True},
                      "anterior": {"posicion": "expuesto", "origen": "voz", "agua_detectada": True},
                      "thingName": "tendedero-uno", "ts": AHORA_MS}, None)
        eventos = [i for i in self.tabla.items if i["sk"].startswith("evento#")]
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["tipo"], "evento")
        self.assertEqual(eventos[0]["cambio"], "posicion")
        self.assertEqual(eventos[0]["posicion"], "resguardado")
        self.assertEqual(eventos[0]["origen"], "edge")

    def test_evento_de_agua_y_posicion_a_la_vez(self):
        self.handler({"actual": {"posicion": "resguardado", "origen": "edge", "agua_detectada": True},
                      "anterior": {"posicion": "expuesto", "agua_detectada": False},
                      "thingName": "tendedero-uno", "ts": AHORA_MS}, None)
        cambios = sorted(i["cambio"] for i in self.tabla.items if i["sk"].startswith("evento#"))
        self.assertEqual(cambios, ["agua", "posicion"])
        self.assertEqual(len({i["sk"] for i in self.tabla.items}), len(self.tabla.items),
                         "dos eventos del mismo instante no deben compartir sk")

    def test_origen_invalido_no_se_guarda(self):
        self.handler({"actual": {"posicion": "resguardado", "origen": "hackeo"},
                      "anterior": {"posicion": "expuesto"},
                      "thingName": "tendedero-uno", "ts": AHORA_MS}, None)
        self.assertEqual([i for i in self.tabla.items if i.get("origen") == "hackeo"], [])


@unittest.skipUnless(RUTA.exists(), f"todavia no existe {RUTA.relative_to(ROOT)}")
class LuzAutomaticaTests(unittest.TestCase):
    """RF11 y RF12 para el LDR y el LED (regla R5)."""

    def setUp(self):
        self.aws = FakeAws()
        self.handler = self.aws.cargar(RUTA, {"DDB_HISTORY_TABLE": TABLA})["lambda_handler"]
        self.tabla = self.aws.table(TABLA)

    def test_lectura_guarda_luz_y_led(self):
        self.handler({"reported": {"lectura_adc": 10, "luz_adc": 640, "oscuro": True, "led": "encendido",
                                   "origen_led": "edge"},
                      "thingName": "tendedero-uno", "ts": AHORA_MS}, None)
        item = self.tabla.items[0]
        self.assertEqual((int(item["luz_adc"]), item["oscuro"], item["led"]), (640, True, "encendido"))

    def test_descarta_luz_invalida(self):
        for malo in ({"luz_adc": 9000}, {"oscuro": "si"}, {"led": "prendido"}, {"luz_simulada": 1}):
            self.handler({"reported": {"lectura_adc": 10, **malo}, "thingName": "tendedero-uno",
                          "ts": AHORA_MS}, None)
        self.assertEqual(self.tabla.items, [])

    def test_evento_del_led_con_su_origen(self):
        self.handler({"actual": {"led": "encendido", "origen_led": "edge", "oscuro": True, "posicion": "expuesto",
                                 "origen": "voz"},
                      "anterior": {"led": "apagado", "origen_led": "voz", "oscuro": False, "posicion": "expuesto"},
                      "thingName": "tendedero-uno", "ts": AHORA_MS}, None)
        eventos = {i["cambio"]: i for i in self.tabla.items}
        self.assertEqual(sorted(eventos), ["led", "luz"])
        self.assertEqual(eventos["led"]["origen_led"], "edge")
        self.assertNotIn("origen", eventos["led"], "el origen del brazo no se mezcla con el del LED")
        self.assertTrue(eventos["luz"]["oscuro"])

    def test_luz_simulada_queda_marcada(self):
        self.handler({"actual": {"oscuro": True, "luz_simulada": True}, "anterior": {"oscuro": False},
                      "thingName": "tendedero-uno", "ts": AHORA_MS}, None)
        self.assertTrue(self.tabla.items[0]["luz_simulada"])
