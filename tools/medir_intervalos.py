#!/usr/bin/env python3
"""Mide el tiempo entre dos tipos de línea en un log CSV de grabar_rnf.py.

Empareja cada línea que cumple --inicio con la primera línea posterior que cumple
--fin. Después de un par, ignora más líneas de inicio hasta que pase ese fin; así,
"[SENSOR] ... agua=1" repetido cada 500 ms cuenta solo la primera vez.

Ajustes predefinidos (--preset); revisen que el firmware imprima esas líneas:
  edge        agua detectada -> servo en posición estimada (regla R1)
  reconexion  [MQTT] Desconectado -> [SHADOW] Estado inicial recuperado
  orden       marca 'envio' de grabar_rnf.py -> [SERVO] Posicion estimada

Las marcas manuales de grabar_rnf.py se leen como "marca:<texto>" (p. ej. ^marca:agua).

Ejemplo:
  python tools/medir_intervalos.py --log resultados/log-p4-edge.csv --preset edge --objetivo-ms 2000
"""
import argparse
import csv
import re
import statistics
import sys

PRESETS = {
    "edge": (r"\[SENSOR\].* agua=1", r"\[SERVO\] Posicion estimada"),
    "reconexion": (r"\[MQTT\] Desconectado", r"\[SHADOW\] Estado inicial recuperado"),
    "orden": (r"^marca:envio", r"\[SERVO\] Posicion estimada"),
}


def pares(lineas, inicio, fin):
    """lineas: [(epoch, texto)] -> [(t_inicio, t_fin, texto_inicio)]"""
    out, abierto = [], None
    for t, texto in lineas:
        if abierto is None and inicio.search(texto):
            abierto = (t, texto)
        elif abierto is not None and fin.search(texto):
            out.append((abierto[0], t, abierto[1]))
            abierto = None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True)
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--inicio", help="expresión regular de la línea de inicio")
    ap.add_argument("--fin", help="expresión regular de la línea de fin")
    ap.add_argument("--objetivo-ms", type=float)
    ap.add_argument("--csv", help="guardar cada intervalo en este CSV")
    a = ap.parse_args(argv)
    if a.preset:
        a.inicio, a.fin = a.inicio or PRESETS[a.preset][0], a.fin or PRESETS[a.preset][1]
    if not (a.inicio and a.fin):
        ap.error("indiquen --preset o --inicio y --fin")

    with open(a.log, newline="", encoding="utf-8") as f:
        # Las líneas del ESP32 quedan tal cual; las marcas manuales, como "marca:<texto>".
        lineas = [(float(r[1]), r[3] if r[0] == "serie" else f"{r[0]}:{r[3]}")
                  for r in csv.reader(f) if len(r) >= 4]
    resultado = pares(lineas, re.compile(a.inicio), re.compile(a.fin))
    if not resultado:
        print("No se encontraron pares inicio -> fin.")
        return 1
    ms = [(t1 - t0) * 1000 for t0, t1, _ in resultado]
    for i, ((t0, t1, texto), m) in enumerate(zip(resultado, ms), 1):
        print(f"{i:3d}  {m:8.0f} ms  {texto[:70]}")
    v = sorted(ms)
    p95 = v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]
    print(f"\nn={len(v)} min={v[0]:.0f} media={statistics.mean(v):.0f} p95={p95:.0f} max={v[-1]:.0f} ms")
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["n", "inicio_epoch", "fin_epoch", "ms"])
            w.writerows((i, f"{t0:.3f}", f"{t1:.3f}", f"{m:.0f}")
                        for i, ((t0, t1, _), m) in enumerate(zip(resultado, ms), 1))
    if a.objetivo_ms is not None:
        cumple = v[-1] <= a.objetivo_ms
        print(f"Máximo {v[-1]:.0f} ms (objetivo <= {a.objetivo_ms:.0f} ms) -> {'CUMPLE' if cumple else 'NO CUMPLE'}")
        return 0 if cumple else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
