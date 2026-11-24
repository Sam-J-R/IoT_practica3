"""Coherencia de la plantilla de CloudFormation, las exportaciones de §6 y el despliegue.

No llama a AWS: lee aws/cloudformation/tendedero-p4.yaml y revisa referencias,
permisos y que aws/reglas, aws/iam y la tabla exportada esten al dia.
"""

import contextlib
import io
import sys
import unittest

from tests.p4.fake_aws import ROOT

try:
    import yaml  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None

sys.path.insert(0, str(ROOT / "tools"))


@unittest.skipUnless(yaml, "pip install pyyaml")
class PlantillaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import exportar_config_p4
        cls.exp = exportar_config_p4
        cls.plantilla = exportar_config_p4.cargar_plantilla()
        cls.recursos = cls.plantilla["Resources"]

    def de_tipo(self, tipo):
        return {k: r for k, r in self.recursos.items() if r["Type"] == tipo}

    def test_exportaciones_al_dia(self):
        for relativa, contenido in self.exp.exportaciones(self.plantilla).items():
            ruta = ROOT / relativa
            self.assertTrue(ruta.exists(), f"falta {relativa}: python tools/exportar_config_p4.py")
            import json
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8")), contenido,
                             f"{relativa} desactualizado: python tools/exportar_config_p4.py")

    def test_codigo_de_cada_lambda_existe(self):
        for nombre, recurso in self.de_tipo("AWS::Lambda::Function").items():
            carpeta = (ROOT / "aws" / "cloudformation" / recurso["Properties"]["Code"]).resolve()
            self.assertTrue((carpeta / "lambda_function.py").exists(), f"{nombre}: falta {carpeta}")
            self.assertEqual(recurso["Properties"]["Handler"], "lambda_function.lambda_handler")

    def test_cada_regla_puede_invocar_solo_su_lambda(self):
        permisos = self.de_tipo("AWS::Lambda::Permission")
        for nombre, regla in self.de_tipo("AWS::IoT::TopicRule").items():
            destino = regla["Properties"]["TopicRulePayload"]["Actions"][0]["Lambda"]["FunctionArn"]["Fn::GetAtt"][0]
            propios = [p["Properties"] for p in permisos.values()
                       if p["Properties"].get("SourceArn") == {"Fn::GetAtt": [nombre, "Arn"]}]
            self.assertEqual(len(propios), 1, f"{nombre}: se espera un permiso con SourceArn propio")
            self.assertEqual(propios[0]["FunctionName"], {"Ref": destino})
            self.assertEqual(propios[0]["Principal"], "iot.amazonaws.com")

    def test_supervisor_programado(self):
        (regla,) = self.de_tipo("AWS::Events::Rule").values()
        destino = regla["Properties"]["Targets"][0]["Arn"]["Fn::GetAtt"][0]
        self.assertEqual(destino, "LambdaSupervisor")
        self.assertIn("events.amazonaws.com",
                      [p["Properties"]["Principal"] for p in self.de_tipo("AWS::Lambda::Permission").values()])

    def test_minimo_privilegio(self):
        """Ninguna accion con comodin; solo almacenamiento puede escribir sin tocar el Shadow."""
        acciones_por_rol = {}
        for nombre, rol in self.de_tipo("AWS::IAM::Role").items():
            acciones = set()
            for politica in rol["Properties"]["Policies"]:
                for s in politica["PolicyDocument"]["Statement"]:
                    lista = s["Action"] if isinstance(s["Action"], list) else [s["Action"]]
                    self.assertFalse([a for a in lista if a == "*" or a.endswith(":*")], nombre)
                    self.assertNotEqual(s["Resource"], "*", f"{nombre}/{s.get('Sid')}: recurso '*'")
                    acciones |= set(lista)
            acciones_por_rol[nombre] = acciones
        self.assertFalse({a for a in acciones_por_rol["RolAlmacenamiento"] if a.startswith("iot:")})
        self.assertNotIn("iot:GetThingShadow", acciones_por_rol["RolLogica"])

    def test_tabla_con_ttl_y_capa_gratuita(self):
        props = self.recursos["TablaHistorico"]["Properties"]
        self.assertEqual(props["TimeToLiveSpecification"], {"AttributeName": "ttl", "Enabled": True})
        if props.get("BillingMode") == "PROVISIONED":
            t = props["ProvisionedThroughput"]
            self.assertLessEqual(t["ReadCapacityUnits"] + t["WriteCapacityUnits"], 50)

    def test_presupuesto_opcional(self):
        self.assertEqual(self.recursos["Presupuesto"].get("Condition"), "ConPresupuesto")


class DesplegarTests(unittest.TestCase):
    def test_sin_bandera_solo_muestra_el_plan(self):
        import desplegar_p4
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), unittest.mock.patch("subprocess.run") as run:
            codigo = desplegar_p4.main(["--correo", "x@ejemplo.com"])
        self.assertEqual(codigo, 0)
        run.assert_not_called()
        texto = salida.getvalue()
        self.assertIn("cloudformation package", texto)
        self.assertIn("CAPABILITY_NAMED_IAM", texto)
        self.assertIn("CorreoAlertas=x@ejemplo.com", texto)
        self.assertIn("no se llamó a AWS", texto)


import unittest.mock  # noqa: E402  (usado arriba con patch)

if __name__ == "__main__":
    unittest.main()
