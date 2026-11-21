#!/usr/bin/env python3
"""RNF de la P4: estimación del consumo mensual frente a la capa gratuita.

Cuenta operaciones, no dólares: los precios cambian por región y por tipo de
cuenta. Los límites por defecto de AWS IoT Core son los de la capa gratuita de 12
meses publicada en https://aws.amazon.com/iot-core/pricing/ (consultada el
19-11-2026). Verifiquen los de Lambda y DynamoDB en sus páginas de precios y en
la consola de Facturación, y pásenlos con los parámetros --libre-*.

Supuestos (ajústenlos si su diseño es distinto):
- Cada reporte del ESP32: 1 mensaje publicado + 1 entregado (update/accepted, al
  que el ESP32 está suscrito) + 1 operación de Shadow.
- Cada reporte activa la regla de lecturas (1 acción) y es evaluado por las reglas
  sobre update/documents. Se cuentan como disparadas, para no subestimar.
- Lambda de almacenamiento: 1 invocación por reporte y 1 por evento.
- DynamoDB: 1 escritura por lectura, por evento y por alerta (ítems de hasta 1 KB).
"""
import argparse

MIN_MES = 60 * 24 * 30


def estimar(a):
    reportes = MIN_MES * 60 / a.intervalo_s + a.eventos_dia * 30   # periódicos + por evento
    eventos = a.eventos_dia * 30
    alexa = a.alexa_dia * 30
    supervisor_runs = MIN_MES / a.supervisor_min
    por_thing = {
        "IoT: mensajes": reportes * 2 + alexa * 1 + eventos,   # + deltas entregados
        "IoT: operaciones de Shadow": reportes + alexa * 2 + supervisor_runs,
        "IoT: reglas disparadas": reportes * a.reglas,
        "IoT: acciones": reportes + eventos * 2,
        "Lambda: invocaciones": reportes + eventos * 2 + alexa,
        "DynamoDB: escrituras": reportes + eventos + a.alertas_dia * 30,
        "DynamoDB: lecturas": supervisor_runs * 2 + eventos + alexa,
    }
    total = {k: v * a.things for k, v in por_thing.items()}
    total["Lambda: invocaciones"] += supervisor_runs  # una sola Lambda programada para todos
    return total


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--things", type=int, default=1)
    ap.add_argument("--intervalo-s", type=float, default=60, help="respaldo periódico del ESP32")
    ap.add_argument("--eventos-dia", type=float, default=20, help="cambios de agua/posición/modo por día")
    ap.add_argument("--alexa-dia", type=float, default=10, help="consultas y comandos de voz por día")
    ap.add_argument("--alertas-dia", type=float, default=1)
    ap.add_argument("--supervisor-min", type=float, default=5)
    ap.add_argument("--reglas", type=int, default=3, help="reglas que escuchan cada reporte")
    ap.add_argument("--libre-mensajes", type=float, default=500_000)
    ap.add_argument("--libre-shadow", type=float, default=225_000)
    ap.add_argument("--libre-reglas", type=float, default=250_000)
    ap.add_argument("--libre-acciones", type=float, default=250_000)
    ap.add_argument("--libre-lambda", type=float, default=None, help="verificar en la página de Lambda")
    ap.add_argument("--libre-ddb-escrituras", type=float, default=None,
                    help="en modo bajo demanda puede no haber capa gratuita de solicitudes: verificar")
    a = ap.parse_args(argv)

    libres = {"IoT: mensajes": a.libre_mensajes, "IoT: operaciones de Shadow": a.libre_shadow,
              "IoT: reglas disparadas": a.libre_reglas, "IoT: acciones": a.libre_acciones,
              "Lambda: invocaciones": a.libre_lambda, "DynamoDB: escrituras": a.libre_ddb_escrituras}
    print(f"{a.things} tendedero(s), respaldo cada {a.intervalo_s:.0f} s, {a.eventos_dia:.0f} eventos/día\n")
    print(f"{'Concepto':30s} {'Por mes':>12s} {'Capa gratuita':>14s} {'Uso':>7s}")
    for k, v in estimar(a).items():
        libre = libres.get(k)
        uso = f"{100 * v / libre:6.1f}%" if libre else "   ver"
        print(f"{k:30s} {v:12,.0f} {(f'{libre:,.0f}' if libre else '—'):>14s} {uso:>7s}")
    return 0


if __name__ == "__main__":
    main()
