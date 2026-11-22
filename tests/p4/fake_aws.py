"""AWS simulado en memoria para probar las Lambdas de la P4 sin cuenta de AWS.

Cada prueba carga los items de la tabla en `query_items`. `query` aplica de verdad
la condicion de clave (con `boto3.dynamodb.conditions.Key` o con una expresion de
texto simple como "thingName = :t AND begins_with(sk, :p)"), ordena por `sk` y
respeta `ScanIndexForward` y `Limit`. Las pruebas revisan lo escrito con
`put_item` y en el Shadow.
"""

import io
import json
import os
import re
import runpy
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2]


class Cond:
    """Condicion de clave minima, compatible con boto3.dynamodb.conditions.Key."""

    def __init__(self, nombre, op=None, valores=(), partes=None):
        self.nombre, self.op, self.valores, self.partes = nombre, op, valores, partes

    def _c(self, op, *valores):
        return Cond(self.nombre, op, valores)

    def eq(self, v): return self._c("eq", v)
    def lt(self, v): return self._c("lt", v)
    def lte(self, v): return self._c("lte", v)
    def gt(self, v): return self._c("gt", v)
    def gte(self, v): return self._c("gte", v)
    def between(self, a, b): return self._c("between", a, b)
    def begins_with(self, v): return self._c("begins_with", v)

    def __and__(self, otra):
        return Cond(None, "and", partes=(self, otra))

    def cumple(self, item):
        if self.op == "and":
            return all(p.cumple(item) for p in self.partes)
        v = item.get(self.nombre)
        if v is None:
            return False
        a = self.valores[0]
        return {"eq": v == a, "lt": v < a, "lte": v <= a, "gt": v > a, "gte": v >= a,
                "begins_with": str(v).startswith(str(a)),
                "between": self.op == "between" and a <= v <= self.valores[-1]}[self.op]


def _cond_de_texto(expr, valores, nombres):
    """Convierte expresiones simples de KeyConditionExpression en Cond."""
    def nombre(n):
        return nombres.get(n, n)
    conds = []
    trozos = re.split(r"\s+AND\s+", expr.strip(), flags=re.I)
    partes = []
    for t in trozos:  # "sk BETWEEN :a" + ":b" vuelven a unirse
        if partes and re.search(r"BETWEEN\s+:\w+$", partes[-1], re.I):
            partes[-1] += " AND " + t
        else:
            partes.append(t)
    for parte in partes:
        parte = parte.strip()
        m = re.fullmatch(r"begins_with\(\s*([#\w]+)\s*,\s*(:\w+)\s*\)", parte)
        if m:
            conds.append(Cond(nombre(m[1])).begins_with(valores[m[2]])); continue
        m = re.fullmatch(r"([#\w]+)\s+BETWEEN\s+(:\w+)\s+AND\s+(:\w+)", parte, re.I)
        if m:
            conds.append(Cond(nombre(m[1])).between(valores[m[2]], valores[m[3]])); continue
        m = re.fullmatch(r"([#\w]+)\s*(=|<=|>=|<|>)\s*(:\w+)", parte)
        if m:
            op = {"=": "eq", "<": "lt", "<=": "lte", ">": "gt", ">=": "gte"}[m[2]]
            conds.append(getattr(Cond(nombre(m[1])), op)(valores[m[3]])); continue
        raise ValueError(f"FakeTable no entiende la condicion: {parte!r}")
    resultado = conds[0]
    for c in conds[1:]:
        resultado = resultado & c
    return resultado


class FakeTable:
    def __init__(self, name):
        self.name = name
        self.items = []           # lo escrito con put_item
        self.query_items = []     # lo que devolvera query
        self.scan_items = []      # lo que devolvera scan
        self.queries = []

    def put_item(self, Item, **kwargs):
        self.items.append(Item)
        return {}

    def query(self, **kwargs):
        self.queries.append(kwargs)
        cond = kwargs.get("KeyConditionExpression")
        if isinstance(cond, str):
            cond = _cond_de_texto(cond, kwargs.get("ExpressionAttributeValues", {}),
                                  kwargs.get("ExpressionAttributeNames", {}))
        items = [i for i in self.query_items if cond is None or cond.cumple(i)]
        items.sort(key=lambda i: i.get("sk", ""), reverse=kwargs.get("ScanIndexForward") is False)
        if "Limit" in kwargs:
            items = items[: kwargs["Limit"]]
        return {"Items": items, "Count": len(items)}

    def scan(self, **kwargs):
        return {"Items": list(self.scan_items)}

    def get_item(self, Key, **kwargs):
        return {}


class FakeAws:
    def __init__(self):
        self.tables = {}
        self.shadows = {}       # thingName -> {"desired":{}, "reported":{}}
        self.shadow_updates = []
        self.data = Mock()
        self.data.update_thing_shadow.side_effect = self._update
        self.data.get_thing_shadow.side_effect = self._get

    def table(self, name):
        return self.tables.setdefault(name, FakeTable(name))

    def _update(self, thingName, payload):
        doc = json.loads(payload)
        self.shadow_updates.append((thingName, doc))
        estado = self.shadows.setdefault(thingName, {"desired": {}, "reported": {}})
        estado["desired"].update(doc.get("state", {}).get("desired", {}))
        return {"payload": io.BytesIO(json.dumps(doc).encode())}

    def _get(self, thingName):
        estado = self.shadows.get(thingName, {})
        return {"payload": io.BytesIO(json.dumps({"state": estado}).encode())}

    def modules(self):
        boto3 = types.ModuleType("boto3")
        boto3.client = lambda name, **kw: {"iot-data": self.data, "iot": Mock()}[name]
        boto3.resource = lambda *a, **kw: Mock(Table=self.table)
        dynamodb = types.ModuleType("boto3.dynamodb")
        conditions = types.ModuleType("boto3.dynamodb.conditions")
        conditions.Key = Cond
        conditions.Attr = MagicMock(name="Attr")
        boto3.dynamodb = dynamodb
        dynamodb.conditions = conditions
        botocore = types.ModuleType("botocore")
        exceptions = types.ModuleType("botocore.exceptions")
        exceptions.ClientError = type("ClientError", (Exception,), {})
        return {"boto3": boto3, "boto3.dynamodb": dynamodb, "boto3.dynamodb.conditions": conditions,
                "botocore": botocore, "botocore.exceptions": exceptions}

    def cargar(self, ruta, env=None):
        """Carga lambda_function.py con AWS simulado y devuelve sus globales."""
        env = {"IOT_ENDPOINT": "endpoint.example", "AWS_REGION": "us-east-2", **(env or {})}
        with patch.dict(sys.modules, self.modules()), patch.dict(os.environ, env):
            return runpy.run_path(str(ruta))
