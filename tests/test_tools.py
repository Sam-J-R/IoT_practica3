"""Pruebas de los scripts de medición con datos sintéticos (sin AWS ni ESP32)."""

import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import estimar_costo  # noqa: E402
import medir_almacenamiento  # noqa: E402
import medir_intervalos  # noqa: E402

T0 = 1795000000.0  # epoch de referencia


def escribir_log(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for fuente, t, dato in filas:
            w.writerow([fuente, f"{t:.3f}", datetime.fromtimestamp(t).isoformat(), dato])


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="milliseconds")


def correr(main, args):
    salida = io.StringIO()
    with redirect_stdout(salida):
        codigo = main(args)
    return codigo, salida.getvalue()


class ToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_integridad_y_latencia(self):
        log = self.dir / "log.csv"
        filas = [("serie_estado", T0, "puerto abierto")]
        filas += [("serie", T0 + 60 * i, "[SHADOW] reported aceptado ms=1") for i in range(1, 101)]
        escribir_log(log, filas)
        items = [{"thingName": {"S": "t"}, "sk": {"S": "lectura#" + iso(T0 + 60 * i)},
                  "ts_iot": {"N": str(int((T0 + 60 * i) * 1000))},
                  "ts_guardado": {"N": str(int((T0 + 60 * i) * 1000) + 300)}}
                 for i in range(1, 100)]  # 99 de 100
        (self.dir / "items.json").write_text(json.dumps({"Items": items}))
        codigo, out = correr(medir_almacenamiento.main,
                             ["--log", str(log), "--items", str(self.dir / "items.json")])
        self.assertIn("Integridad: 99.00 %", out)
        self.assertIn("max=300 ms", out)
        self.assertEqual(codigo, 0, out)

    def test_acepta_el_csv_de_la_consola_de_dynamodb(self):
        log = self.dir / "log.csv"
        escribir_log(log, [("serie", T0 + 60 * i, "[SHADOW] reported aceptado ms=1") for i in range(1, 11)])
        # Formato de "Download results to CSV": una columna por atributo, celdas vacias si falta.
        filas = ['"thingName","sk","ts_iot","ts_guardado","ts_dispositivo","nivel_luz"']
        for i in range(1, 11):
            t = int((T0 + 60 * i) * 1000)
            filas.append(f'"t","lectura#{iso(T0 + 60 * i)}","{t}","{t + 900}","{t - 100}",""')
        (self.dir / "lecturas.csv").write_text("\n".join(filas) + "\n", encoding="utf-8")
        codigo, out = correr(medir_almacenamiento.main,
                             ["--log", str(log), "--items", str(self.dir / "lecturas.csv")])
        self.assertIn("Integridad: 100.00 %", out)
        self.assertIn("ts_guardado - ts_dispositivo", out)
        self.assertIn("max=1000 ms", out)
        self.assertEqual(codigo, 0, out)

    def test_integridad_insuficiente_devuelve_error(self):
        log = self.dir / "log.csv"
        escribir_log(log, [("serie", T0 + i, "[SHADOW] reported aceptado ms=1") for i in range(10)])
        (self.dir / "items.json").write_text(json.dumps({"Items": []}))
        codigo, out = correr(medir_almacenamiento.main,
                             ["--log", str(log), "--items", str(self.dir / "items.json")])
        self.assertIn("NO CUMPLE", out)
        self.assertEqual(codigo, 1)

    def test_intervalos_edge_cuenta_solo_el_primer_agua(self):
        log = self.dir / "log.csv"
        escribir_log(log, [
            ("serie", T0, "[SENSOR] ms=1 raw=0 agua=0"),
            ("serie", T0 + 1.0, "[SENSOR] ms=2 raw=900 agua=1"),
            ("serie", T0 + 1.5, "[SENSOR] ms=3 raw=950 agua=1"),
            ("serie", T0 + 2.2, "[SERVO] Posicion estimada tras espera ms=4"),
            ("serie", T0 + 2.5, "[SENSOR] ms=5 raw=950 agua=1"),
        ])
        codigo, out = correr(medir_intervalos.main,
                             ["--log", str(log), "--preset", "edge", "--objetivo-ms", "2000"])
        self.assertIn("n=1", out)
        self.assertIn("max=1200 ms", out)
        self.assertEqual(codigo, 0)

    def test_intervalos_con_marcas_manuales(self):
        log = self.dir / "log.csv"
        escribir_log(log, [("marca", T0, "envio"), ("marca", T0, "orden"),
                           ("serie", T0 + 1.8, "[SERVO] Posicion estimada tras espera ms=1")])
        codigo, out = correr(medir_intervalos.main, ["--log", str(log), "--preset", "orden"])
        self.assertIn("max=1800 ms", out)

    def test_costo_escala_con_things_e_intervalo(self):
        base = estimar_costo.main.__globals__["estimar"]
        args = estimar_costo.argparse.Namespace(things=1, intervalo_s=60, eventos_dia=0, alexa_dia=0,
                                                alertas_dia=0, supervisor_min=5, reglas=1)
        uno = base(args)
        self.assertAlmostEqual(uno["DynamoDB: escrituras"], 43_200)
        args.intervalo_s = 5
        self.assertAlmostEqual(base(args)["DynamoDB: escrituras"], 518_400)
