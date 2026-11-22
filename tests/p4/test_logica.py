"""Regla R4: mas de 6 movimientos en una hora -> duplicar minutos_reexponer (solo via desired)."""

import unittest
from datetime import datetime, timedelta, timezone

from tests.p4.fake_aws import ROOT, FakeAws

RUTA = ROOT / "lambda" / "logica" / "lambda_function.py"
TABLA = "tendedero_historico"
LIMITE = 6
AHORA = datetime(2026, 11, 22, 10, 30, tzinfo=timezone.utc)


def iso(momento):
    return momento.isoformat(timespec="milliseconds")


def evento_posicion(minutos_atras):
    t = AHORA - timedelta(minutes=minutos_atras)
    return {"thingName": "tendedero-uno", "sk": f"evento#{iso(t)}#posicion", "tipo": "evento",
            "cambio": "posicion", "posicion": "expuesto", "origen": "edge"}


@unittest.skipUnless(RUTA.exists(), f"todavia no existe {RUTA.relative_to(ROOT)}")
class LogicaR4Tests(unittest.TestCase):
    def setUp(self):
        self.aws = FakeAws()
        self.handler = self.aws.cargar(
            RUTA, {"DDB_HISTORY_TABLE": TABLA, "LIMITE_MOVIMIENTOS_HORA": str(LIMITE)})["lambda_handler"]
        self.tabla = self.aws.table(TABLA)
        self.evento = {"actual": {"posicion": "resguardado", "modo": "automatico", "minutos_reexponer": 15},
                       "anterior": {"posicion": "expuesto", "modo": "automatico"},
                       "thingName": "tendedero-uno", "ts": int(AHORA.timestamp() * 1000)}

    def previos(self, cantidad, cada=8):
        self.tabla.query_items = [evento_posicion(m * cada + 2) for m in range(cantidad)]

    def deseados(self):
        return [doc["state"]["desired"] for _, doc in self.aws.shadow_updates]

    def test_duplica_la_espera_al_superar_el_limite(self):
        self.previos(LIMITE)  # 6 anteriores + este = 7
        resultado = self.handler(self.evento, None)
        self.assertEqual(resultado, {"accion": "duplicar_espera", "movimientos": 7, "minutos": 30})
        # Solo cambia la espera: el modo sigue en automatico, asi que R1 sigue activa.
        self.assertEqual(self.deseados(), [{"minutos_reexponer": 30}])
        self.assertNotIn("reported", self.aws.shadow_updates[0][1]["state"], "la Nube nunca escribe reported")
        alerta, = self.tabla.items
        self.assertEqual((alerta["alerta"], alerta["minutos_antes"], alerta["minutos_despues"]),
                         ("exceso_movimientos", 15, 30))

    def test_cuenta_este_movimiento_aunque_aun_no_este_guardado(self):
        # La Lambda de almacenamiento corre en paralelo: este 7.o movimiento todavia no esta en la tabla.
        self.previos(LIMITE)
        self.assertEqual(self.handler(self.evento, None)["movimientos"], LIMITE + 1)

    def test_no_cuenta_dos_veces_el_movimiento_ya_guardado(self):
        self.previos(LIMITE - 1)
        self.tabla.query_items.append({**evento_posicion(0), "sk": f"evento#{iso(AHORA)}#posicion"})
        self.assertEqual(self.handler(self.evento, None), {"accion": "ninguna", "movimientos": LIMITE})
        self.assertEqual(self.aws.shadow_updates, [])

    def test_no_vuelve_a_duplicar_en_la_misma_hora(self):
        self.previos(LIMITE + 1, cada=7)  # este seria el 8.o
        self.assertEqual(self.handler(self.evento, None)["accion"], "ninguna")
        self.assertEqual(self.aws.shadow_updates, [])

    def test_respeta_el_tope_de_240(self):
        self.previos(LIMITE)
        self.evento["actual"]["minutos_reexponer"] = 150
        self.assertEqual(self.handler(self.evento, None)["minutos"], 240)
        self.aws.shadow_updates.clear()
        self.evento["actual"]["minutos_reexponer"] = 240
        self.assertEqual(self.handler(self.evento, None)["accion"], "ninguna")
        self.assertEqual(self.aws.shadow_updates, [])

    def test_sin_espera_reportada_parte_de_30(self):
        self.previos(LIMITE)
        del self.evento["actual"]["minutos_reexponer"]
        self.assertEqual(self.deseados() or self.handler(self.evento, None)["minutos"], 60)

    def test_ignora_movimientos_de_hace_mas_de_una_hora(self):
        self.tabla.query_items = [evento_posicion(m) for m in (61, 70, 80, 90, 100, 110, 5)]
        self.assertEqual(self.handler(self.evento, None)["movimientos"], 2)

    def test_no_actua_dentro_del_limite_ni_en_manual(self):
        self.previos(LIMITE - 1)
        self.assertEqual(self.handler(self.evento, None)["accion"], "ninguna")
        self.previos(LIMITE)
        self.evento["actual"]["modo"] = "manual"
        self.assertEqual(self.handler(self.evento, None)["accion"], "ninguna")
        self.assertEqual(self.aws.shadow_updates, [])
