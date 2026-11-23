#!/usr/bin/env python3
"""RNF de la P4: integridad y latencia del almacenamiento en DynamoDB.

Integridad = lecturas guardadas en DynamoDB / reportes que AWS aceptó en la ventana.
Los reportes aceptados se cuentan en el log de grabar_rnf.py (línea
"[SHADOW] reported aceptado"). Las lecturas se leen de DynamoDB o de un JSON exportado.

Latencia = ts_guardado - ts_dispositivo (si el ESP32 lo envía) o - ts_iot (hora en
que la regla recibió el mensaje). El script indica cuál usó.

Ejemplos:
  # 0) Sin CLI: en la consola de DynamoDB, Explore items -> consulta por thingName y
  #    sk que empiece con "lectura#" -> Actions -> Download results to CSV
  python tools/medir_almacenamiento.py --log resultados_p4/<carpeta>/log.csv --items lecturas.csv

  # 1) Exportar los ítems con la CLI de AWS y analizarlos
  aws dynamodb query --table-name tendedero_historico \\
      --key-condition-expression "thingName = :t AND begins_with(sk, :p)" \\
      --expression-attribute-values '{":t":{"S":"tendedero-inteligente"},":p":{"S":"lectura#"}}' \\
      > items.json
  python tools/medir_almacenamiento.py --log resultados/log-p4-integridad.csv --items items.json

  # 2) Consultar DynamoDB directamente (requiere boto3 y aws configure)
  python tools/medir_almacenamiento.py --log log.csv --dynamo --thing tendedero-inteligente
"""
import argparse
import csv
import json
import statistics
import sys
from datetime import datetime, timezone

ACEPTADO = "[SHADOW] reported aceptado"


def leer_log(ruta):
    """Devuelve (epoch, dato) de cada línea del CSV de grabar_rnf.py."""
    with open(ruta, newline="", encoding="utf-8") as f:
        return [(float(fila[1]), fila[3]) for fila in csv.reader(f) if len(fila) >= 4]


def _valor(v):
    """Convierte un atributo en formato DynamoDB JSON ({"N": "1"}) a Python."""
    if not isinstance(v, dict) or len(v) != 1:
        return v
    tipo, dato = next(iter(v.items()))
    return {"S": str, "N": float, "BOOL": bool}.get(tipo, lambda x: x)(dato)


def leer_items_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    items = datos.get("Items", datos) if isinstance(datos, dict) else datos
    return [{k: _valor(v) for k, v in i.items()} for i in items]


def leer_items_csv(ruta):
    """CSV que descarga la consola de DynamoDB (Download results to CSV).

    Cada columna es un atributo. Las celdas vacías (atributo ausente) se omiten;
    los números quedan como texto y se convierten donde se usan.
    """
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        return [{k.strip(): v.strip() for k, v in fila.items() if k and v and v.strip()}
                for fila in csv.DictReader(f)]


def leer_items(ruta):
    return leer_items_csv(ruta) if str(ruta).lower().endswith(".csv") else leer_items_json(ruta)


def leer_items_dynamo(tabla, thing, desde, hasta):
    import boto3  # solo si se usa --dynamo
    from boto3.dynamodb.conditions import Key
    t = boto3.resource("dynamodb").Table(tabla)
    cond = Key("thingName").eq(thing) & Key("sk").between("lectura#" + desde, "lectura#" + hasta)
    items, kwargs = [], {"KeyConditionExpression": cond}
    while True:
        r = t.query(**kwargs)
        items += r["Items"]
        if "LastEvaluatedKey" not in r:
            return items
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="milliseconds")


def epoch_de_sk(sk):
    return datetime.fromisoformat(sk.split("#")[1].replace("Z", "+00:00")).timestamp()


def resumen(valores):
    v = sorted(valores)
    p95 = v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]
    return f"n={len(v)} min={v[0]:.0f} media={statistics.mean(v):.0f} p95={p95:.0f} max={v[-1]:.0f} ms"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True, help="CSV de grabar_rnf.py")
    fuente = ap.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--items", help="ítems de DynamoDB: JSON exportado (query o scan) o CSV de la consola")
    fuente.add_argument("--dynamo", action="store_true", help="consultar DynamoDB con boto3")
    ap.add_argument("--thing", help="thingName (con --dynamo)")
    ap.add_argument("--tabla", default="tendedero_historico")
    ap.add_argument("--desde", help="ISO-8601 UTC; por defecto, la primera línea del log")
    ap.add_argument("--hasta", help="ISO-8601 UTC; por defecto, la última línea del log")
    ap.add_argument("--margen", type=float, default=10.0,
                    help="segundos extra al final de la ventana para lecturas en tránsito")
    ap.add_argument("--objetivo-integridad", type=float, default=99.0)
    ap.add_argument("--objetivo-latencia-ms", type=float, default=5000.0)
    a = ap.parse_args(argv)

    log = leer_log(a.log)
    if not log:
        sys.exit("El log está vacío")
    t0 = datetime.fromisoformat(a.desde).timestamp() if a.desde else log[0][0]
    t1 = datetime.fromisoformat(a.hasta).timestamp() if a.hasta else log[-1][0]
    aceptados = [t for t, dato in log if ACEPTADO in dato and t0 <= t <= t1]

    if a.dynamo:
        if not a.thing:
            sys.exit("--dynamo necesita --thing")
        items = leer_items_dynamo(a.tabla, a.thing, iso(t0), iso(t1 + a.margen))
    else:
        items = leer_items(a.items)
    lecturas = [i for i in items if str(i.get("sk", "")).startswith("lectura#")
                and t0 - 2 <= epoch_de_sk(i["sk"]) <= t1 + a.margen]

    print(f"Ventana: {iso(t0)} -> {iso(t1)} ({(t1 - t0) / 60:.1f} min)")
    print(f"Reportes aceptados por AWS (log): {len(aceptados)}")
    print(f"Lecturas en DynamoDB:             {len(lecturas)}")
    ok = True
    if aceptados:
        integridad = 100.0 * min(len(lecturas), len(aceptados)) / len(aceptados)
        cumple = integridad >= a.objetivo_integridad
        ok &= cumple
        print(f"Integridad: {integridad:.2f} % (objetivo >= {a.objetivo_integridad} %) -> "
              f"{'CUMPLE' if cumple else 'NO CUMPLE'}")
        if len(lecturas) > len(aceptados):
            print("  Aviso: hay más lecturas que reportes aceptados. ¿Ventana o log incompletos?")

    origen = "ts_dispositivo" if any("ts_dispositivo" in i for i in lecturas) else "ts_iot"
    lat = [float(i["ts_guardado"]) - float(i[origen]) for i in lecturas
           if "ts_guardado" in i and origen in i]
    if lat:
        cumple = max(lat) <= a.objetivo_latencia_ms
        ok &= cumple
        print(f"Latencia (ts_guardado - {origen}): {resumen(lat)} "
              f"(objetivo <= {a.objetivo_latencia_ms:.0f} ms) -> {'CUMPLE' if cumple else 'NO CUMPLE'}")
        if origen == "ts_iot":
            print("  Nota: sin ts_dispositivo no se mide el tramo ESP32 -> AWS IoT.")
    else:
        print("Latencia: los ítems no tienen ts_guardado; revisen la Lambda de almacenamiento.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
