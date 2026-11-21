"""Smoke test: SDK del paquete docente + stub AWS. No prueba cuentas reales."""

import runpy
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LambdaSdkImportTests(unittest.TestCase):
    def test_lambda_handler_loads_using_teacher_sdk(self):
        sys.path.insert(0, str(ROOT / "lambda" / "lambda_deployment_p3.zip"))
        boto3 = types.ModuleType("boto3")
        botocore = types.ModuleType("botocore")
        exceptions = types.ModuleType("botocore.exceptions")

        class ClientError(Exception):
            pass

        exceptions.ClientError = ClientError
        boto3.client = lambda *args, **kwargs: None
        boto3.resource = lambda *args, **kwargs: None
        sys.modules["boto3"] = boto3
        sys.modules["botocore"] = botocore
        sys.modules["botocore.exceptions"] = exceptions

        loaded = runpy.run_path(str(ROOT / "lambda" / "lambda_function.py"))
        self.assertTrue(callable(loaded["lambda_handler"]))


if __name__ == "__main__":
    unittest.main()

