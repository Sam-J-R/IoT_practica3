"""Simulador minimo del Device Shadow clasico para pruebas sin AWS.

Calcula el delta como lo documenta AWS: recorre `desired` y, en objetos
anidados, incluye SOLO los campos que difieren de `reported`
(https://docs.aws.amazon.com/iot/latest/developerguide/device-shadow-document.html).
Un valor `null` borra el atributo, igual que en AWS.
"""

import copy
import json


def _merge(base, cambios):
    for clave, valor in cambios.items():
        if valor is None:
            base.pop(clave, None)
        elif isinstance(valor, dict) and isinstance(base.get(clave), dict):
            _merge(base[clave], valor)
        else:
            base[clave] = copy.deepcopy(valor)


def calcular_delta(desired, reported):
    delta = {}
    for clave, valor in desired.items():
        actual = reported.get(clave) if isinstance(reported, dict) else None
        if isinstance(valor, dict) and isinstance(actual, dict):
            sub = calcular_delta(valor, actual)
            if sub:
                delta[clave] = sub
        elif valor != actual:
            delta[clave] = copy.deepcopy(valor)
    return delta


class ShadowSimulado:
    """Guarda desired/reported y registra cada delta que AWS publicaria."""

    def __init__(self):
        self.desired, self.reported = {}, {}
        self.version = 0
        self.deltas = []  # mensajes de $aws/things/<thing>/shadow/update/delta

    def update(self, payload):
        if isinstance(payload, (bytes, str)):
            payload = json.loads(payload)
        estado = payload.get("state", {})
        _merge(self.desired, estado.get("desired") or {})
        _merge(self.reported, estado.get("reported") or {})
        self.version += 1
        delta = calcular_delta(self.desired, self.reported)
        if delta:
            self.deltas.append({"state": delta, "version": self.version})
        return delta

    def documento(self):
        return {"state": {"desired": copy.deepcopy(self.desired),
                          "reported": copy.deepcopy(self.reported)},
                "version": self.version}
