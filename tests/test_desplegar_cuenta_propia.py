"""tools/desplegar_cuenta_propia.py y aws/cloudformation/tendedero-base.yaml, sin AWS.

Una consola falsa responde como la AWS CLI y la ASK CLI; se revisa el orden de
los pasos, que se reutilice lo ya creado, la protección contra la cuenta del
equipo y el secrets.h generado.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import desplegar_cuenta_propia as dcp  # noqa: E402

try:
    import yaml  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None

SECRETS_EQUIPO = '''#pragma once
#define WIFI_SSID "MiRed"
#define WIFI_PASSWORD "clave\\"segura"
#define AWS_IOT_ENDPOINT "equipo-ats.iot.us-east-2.amazonaws.com"
#define AWS_IOT_THING_NAME "tendedero-inteligente"

constexpr char AWS_CA_PEM[] = R"EOF(
-----BEGIN CERTIFICATE-----
CAEQUIPO
-----END CERTIFICATE-----
)EOF";
constexpr char AWS_CLIENT_CERT_PEM[] = R"EOF(
-----BEGIN CERTIFICATE-----
VIEJO
-----END CERTIFICATE-----
)EOF";
constexpr char AWS_CLIENT_KEY_PEM[] = R"EOF(
-----BEGIN RSA PRIVATE KEY-----
VIEJA
-----END RSA PRIVATE KEY-----
)EOF";
'''


class ConsolaFalsa(dcp.Consola):
    """Responde como AWS y Alexa; registra cada comando."""

    def __init__(self, region, cuenta_del_equipo=False):
        super().__init__(True, region)
        self.comandos = []
        self.cuenta_del_equipo = cuenta_del_equipo
        self.pila_base = False

    def correr(self, programa, *args, region=True, json_salida=False, permitir_error=False):
        self.comandos.append((programa, *args))
        clave = " ".join(args[:2])
        if clave == "sts get-caller-identity":
            return {"Account": "123456789012"}
        if clave == "cloudformation describe-stacks":
            if not self.pila_base:
                return None
            return {"Stacks": [{"Outputs": [{"OutputKey": "LambdaAlexaArn",
                                             "OutputValue": "arn:aws:lambda:us-east-2:123:function:tendedero_alexa"}]}]}
        if clave == "cloudformation deploy" and "tendedero-base" in args:
            self.pila_base = True
        if clave == "dynamodb describe-table":
            return {"Table": {}} if self.cuenta_del_equipo else None
        if clave == "iot describe-endpoint":
            return {"endpointAddress": "propio-ats.iot.us-east-2.amazonaws.com"}
        if clave == "s3api head-bucket":
            return None
        if clave == "iot create-keys-and-certificate":
            return {"certificateArn": "arn:aws:iot:us-east-2:123:cert/abc", "certificateId": "abc",
                    "certificatePem": "-----BEGIN CERTIFICATE-----\nNUEVO\n-----END CERTIFICATE-----\n",
                    "keyPair": {"PrivateKey": "-----BEGIN RSA PRIVATE KEY-----\nNUEVA\n-----END RSA PRIVATE KEY-----\n"}}
        if clave == "smapi create-skill-for-vendor":
            return {"skillId": "amzn1.ask.skill.prueba"}
        if clave == "smapi get-skill-status":
            return {"manifest": {"lastUpdateRequest": {"status": "SUCCEEDED"}}}
        return {} if json_salida else ""


class DespliegueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.secrets = base / "secrets.h"
        self.secrets.write_text(SECRETS_EQUIPO, encoding="utf-8")
        carpeta = base / "cuenta_propia"
        for nombre, valor in {"CARPETA": carpeta, "ESTADO": carpeta / "estado.json", "SECRETS": self.secrets,
                              "RESPALDO_SECRETS": base / "secrets.h.equipo.bak"}.items():
            self.enterContext(mock.patch.object(dcp, nombre, valor))
        self.p4 = self.enterContext(mock.patch.object(dcp, "desplegar_p4"))

    def tearDown(self):
        self.tmp.cleanup()

    def desplegar(self, consola, *extra):
        a = dcp.argumentos(["--desplegar", "--si", "--thing", "tendedero-samuel", *extra])
        with mock.patch.object(dcp, "Consola", lambda ejecutar, region: consola):
            dcp.desplegar(a)
        return a

    def test_crea_todo_en_orden(self):
        c = ConsolaFalsa("us-east-2")
        self.desplegar(c)
        pasos = [" ".join(x[1:3]) for x in c.comandos]
        orden = ["cloudformation deploy", "iot create-keys-and-certificate", "dynamodb put-item",
                 "smapi create-skill-for-vendor", "smapi set-interaction-model", "smapi set-skill-enablement"]
        indices = [pasos.index(p) for p in orden]
        self.assertEqual(indices, sorted(indices), pasos)
        self.p4.assert_called_once()
        # La base se vuelve a desplegar con el ID de la skill para restringir el permiso.
        despliegues = [x for x in c.comandos if x[1:3] == ("cloudformation", "deploy")]
        self.assertEqual(len(despliegues), 2)
        self.assertNotIn("AlexaSkillId=", " ".join(despliegues[0]))
        self.assertIn("AlexaSkillId=amzn1.ask.skill.prueba", despliegues[1])
        estado = json.loads(dcp.ESTADO.read_text(encoding="utf-8"))
        self.assertEqual(estado["skill_id"], "amzn1.ask.skill.prueba")
        self.assertRegex(estado["codigo"], r"^[1-9]\d{5}$")
        self.assertTrue(Path(estado["clave_privada"]).exists())
        # El manifiesto apunta a la Lambda de la pila base.
        manifiesto = json.loads((dcp.CARPETA / "skill.json").read_text(encoding="utf-8"))
        self.assertIn("tendedero_alexa", manifiesto["manifest"]["apis"]["custom"]["endpoint"]["uri"])

    def test_secrets_nuevo_conserva_wifi_y_ca_y_respalda(self):
        self.desplegar(ConsolaFalsa("us-east-2"))
        nuevo = self.secrets.read_text(encoding="utf-8")
        self.assertIn('#define WIFI_SSID "MiRed"', nuevo)
        self.assertIn('#define WIFI_PASSWORD "clave\\"segura"', nuevo)
        self.assertIn('"propio-ats.iot.us-east-2.amazonaws.com"', nuevo)
        self.assertIn('"tendedero-samuel"', nuevo)
        self.assertIn("CAEQUIPO", nuevo)
        self.assertIn("NUEVO", nuevo)
        self.assertIn("NUEVA", nuevo)
        self.assertNotIn("VIEJO", nuevo)
        self.assertEqual(dcp.RESPALDO_SECRETS.read_text(encoding="utf-8"), SECRETS_EQUIPO)

    def test_segunda_vez_reutiliza_certificado_codigo_y_skill(self):
        self.desplegar(ConsolaFalsa("us-east-2"))
        primero = json.loads(dcp.ESTADO.read_text(encoding="utf-8"))
        c = ConsolaFalsa("us-east-2")
        c.pila_base = True
        self.desplegar(c)
        segundo = json.loads(dcp.ESTADO.read_text(encoding="utf-8"))
        hechos = [" ".join(x[1:3]) for x in c.comandos]
        self.assertNotIn("iot create-keys-and-certificate", hechos)
        self.assertNotIn("smapi create-skill-for-vendor", hechos)
        self.assertIn("smapi update-skill-manifest", hechos)
        self.assertEqual(primero["codigo"], segundo["codigo"])
        # El respaldo sigue siendo el secrets.h del equipo, no el generado.
        self.assertEqual(dcp.RESPALDO_SECRETS.read_text(encoding="utf-8"), SECRETS_EQUIPO)

    def test_se_niega_en_la_cuenta_del_equipo(self):
        with self.assertRaises(dcp.Error) as error:
            self.desplegar(ConsolaFalsa("us-east-2", cuenta_del_equipo=True))
        self.assertIn("cuenta del equipo", str(error.exception))
        self.assertEqual(self.secrets.read_text(encoding="utf-8"), SECRETS_EQUIPO)

    def test_sin_alexa_no_usa_ask(self):
        c = ConsolaFalsa("us-east-2")
        self.desplegar(c, "--sin-alexa")
        self.assertFalse([x for x in c.comandos if x[0] == "ask"])

    def test_plan_no_ejecuta_nada(self):
        with mock.patch.object(dcp.subprocess, "run", side_effect=AssertionError("llamó a AWS")):
            self.assertEqual(dcp.main(["--thing", "tendedero-samuel"]), 0)
        self.assertEqual(self.secrets.read_text(encoding="utf-8"), SECRETS_EQUIPO)

    def test_thing_sin_prefijo_se_rechaza(self):
        with self.assertRaises(SystemExit):
            dcp.argumentos(["--thing", "mi-tendedero"])


@unittest.skipUnless(yaml, "pip install pyyaml")
class PlantillaBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import exportar_config_p4
        cls.plantilla = exportar_config_p4.cargar_plantilla(dcp.PLANTILLA_BASE)
        cls.recursos = cls.plantilla["Resources"]

    def test_zip_de_la_lambda_existe(self):
        codigo = self.recursos["LambdaAlexa"]["Properties"]["Code"]
        self.assertTrue((ROOT / "aws" / "cloudformation" / codigo).resolve().exists())

    def test_permisos_minimos_sin_comodin_total(self):
        for regla in self.recursos["RolAlexa"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]:
            self.assertNotEqual(regla["Resource"], "*", regla["Sid"])

    def test_permiso_de_alexa_se_limita_a_la_skill(self):
        permiso = self.recursos["PermisoAlexa"]["Properties"]
        self.assertEqual(permiso["Principal"], "alexa-appkit.amazon.com")
        self.assertEqual(permiso["EventSourceToken"]["Fn::If"][0], "ConSkill")

    def test_politica_igual_a_la_documentada(self):
        documentada = json.loads((ROOT / "aws" / "iot-certificate-policy.template.json").read_text(encoding="utf-8"))
        acciones = [s["Action"] for s in documentada["Statement"]]
        plantilla = self.recursos["PoliticaDispositivo"]["Properties"]["PolicyDocument"]["Statement"]
        self.assertEqual([s["Action"] for s in plantilla], acciones)
        for doc, cfn in zip(documentada["Statement"], plantilla):
            n = 1 if isinstance(doc["Resource"], str) else len(doc["Resource"])
            m = 1 if not isinstance(cfn["Resource"], list) else len(cfn["Resource"])
            self.assertEqual(n, m, doc["Action"])


if __name__ == "__main__":
    unittest.main()
