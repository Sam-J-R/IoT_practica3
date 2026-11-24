"""Lista de entregables de la P4 (seccion 6 del enunciado). Falla mientras falte algo."""

import json
import shutil
import subprocess
import unittest

from tests.p4.fake_aws import ROOT

INFORME_P4 = ROOT / "docs" / "INFORME_P4.md"
TABLA_HIST = ROOT / "aws" / "tendedero-historico.table.json"
REGLAS = ROOT / "aws" / "reglas"
IAM = ROOT / "aws" / "iam"
MODELO = ROOT / "alexa" / "interaction-model-es-MX.json"
INTENTS_P4 = {"CambiarModoIntent", "ConsultarModoIntent"}


class EntregablesP4(unittest.TestCase):
    def test_informe_p4_existe_con_sus_secciones(self):
        self.assertTrue(INFORME_P4.exists(), f"falta {INFORME_P4.relative_to(ROOT)}")
        texto = INFORME_P4.read_text(encoding="utf-8").casefold()
        for seccion in ("caso de uso", "análisis", "desarrollo", "pruebas", "resultados",
                        "conclusiones", "recomendaciones", "anexos"):
            self.assertIn(seccion, texto, f"el informe no tiene la seccion '{seccion}'")
        self.assertIn("mermaid", texto, "se esperan diagramas (mermaid o imagenes)")

    def test_informe_p3_no_se_modifico(self):
        if not shutil.which("git"):
            self.skipTest("git no disponible")
        r = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "practica3-entrega", "--",
                            "docs/INFORME.md"], capture_output=True)
        if r.returncode > 1:
            self.skipTest("no se encontro la etiqueta practica3-entrega")
        self.assertEqual(r.returncode, 0, "docs/INFORME.md cambio respecto a la entrega de la P3")

    def test_tabla_historico_con_claves_y_ttl(self):
        self.assertTrue(TABLA_HIST.exists(), f"falta {TABLA_HIST.relative_to(ROOT)}")
        t = json.loads(TABLA_HIST.read_text(encoding="utf-8"))
        claves = {k["AttributeName"]: k["KeyType"] for k in t["KeySchema"]}
        self.assertEqual(claves, {"thingName": "HASH", "sk": "RANGE"})
        ttl = t.get("TimeToLiveSpecification", {})
        self.assertTrue(ttl.get("Enabled") and ttl.get("AttributeName") == "ttl",
                        "agregar TimeToLiveSpecification {Enabled: true, AttributeName: ttl}")

    def test_reglas_iot_exportadas(self):
        self.assertTrue(REGLAS.is_dir(), f"falta la carpeta {REGLAS.relative_to(ROOT)}")
        reglas = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in REGLAS.glob("*.json")}
        self.assertGreaterEqual(len(reglas), 2, "se esperan al menos dos reglas (almacenamiento y logica)")
        for nombre, regla in reglas.items():
            sql = regla.get("sql", "")
            self.assertIn("$aws/things/+/shadow/", sql, f"{nombre}: la SQL debe leer los temas del Shadow")
            self.assertIn("topic(3)", sql, f"{nombre}: falta topic(3) AS thingName")
            self.assertTrue(regla.get("actions"), f"{nombre}: sin acciones")
            for accion in regla["actions"]:
                self.assertIn("lambda", accion, f"{nombre}: se espera una accion Lambda")

    def test_politicas_iam_de_lambdas_nuevas(self):
        self.assertTrue(IAM.is_dir(), f"falta la carpeta {IAM.relative_to(ROOT)}")
        politicas = list(IAM.glob("*.json"))
        self.assertGreaterEqual(len(politicas), 3, "una politica por Lambda nueva")
        for p in politicas:
            doc = json.loads(p.read_text(encoding="utf-8"))
            for s in doc["Statement"]:
                acciones = s["Action"] if isinstance(s["Action"], list) else [s["Action"]]
                self.assertNotIn("*", acciones, f"{p.name}: accion '*' no permitida")
                self.assertFalse(any(a.endswith(":*") for a in acciones),
                                 f"{p.name}: acciones con comodin; documentar o restringir")

    def test_skill_con_intents_de_modo(self):
        modelo = json.loads(MODELO.read_text(encoding="utf-8"))
        intents = {i["name"] for i in modelo["interactionModel"]["languageModel"]["intents"]}
        self.assertTrue(INTENTS_P4 <= intents, f"faltan intents: {sorted(INTENTS_P4 - intents)}")

    def test_dependencias_con_version_fija(self):
        lineas = [l.strip() for l in (ROOT / "lambda" / "requirements.txt").read_text().splitlines()
                  if l.strip() and not l.startswith("#")]
        sueltas = [l for l in lineas if "==" not in l]
        self.assertEqual(sueltas, [], "fijar versiones (recomendacion del docente en la P3)")

    def test_scripts_de_ensayo_en_tools(self):
        sueltos = [n for n in ("ensayo_rnf.py", "grabar_rnf.py", "analizar_rnf.py", "orden_offline.py")
                   if (ROOT / n).exists()]
        self.assertEqual(sueltos, [], "mover los scripts de ensayo a tools/ (observacion de la P3)")
