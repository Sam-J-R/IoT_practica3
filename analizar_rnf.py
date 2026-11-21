#!/usr/bin/env python3
"""Analiza rnf-eventos.csv (columnas: fuente, epoch, hora, dato) creado por grabar_rnf.py.

Uso:  python analizar_rnf.py --csv rnf-eventos.csv <comando> [opciones]
Comandos: estabilidad | frecuencia | respuesta | sensor | reconexion
"""
import argparse
import csv
import re
import statistics
from datetime import datetime

INF = float("inf")


# ---------- utilidades ----------
def cargar(ruta):
    ev = []
    with open(ruta, newline="", encoding="utf-8") as f:
        for fila in csv.reader(f):
            if len(fila) < 4:
                continue
            try:
                ev.append((float(fila[1]), fila[0], fila[3]))
            except ValueError:
                pass
    return sorted(ev, key=lambda e: e[0])


def hms(t):
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


def fmt(x):
    return "—" if x is None else f"{x:.2f}"


def marcas(ev, nombre):
    return [t for t, f, d in ev if f == "marca" and d == nombre]


def serie(ev, patron):
    rx = re.compile(patron)
    return [(t, d) for t, f, d in ev if f == "serie" and rx.search(d)]


def siguiente(lista, t, hasta=INF):
    return next((x for x in lista if t < x < hasta), None)


def recorte(ev, ini, fin):
    t0 = (marcas(ev, ini) or [ev[0][0]])[0]
    t1 = (marcas(ev, fin) or [ev[-1][0]])[-1]
    return [e for e in ev if t0 <= e[0] <= t1], t0, t1


def resumen(vals, objetivo=None):
    if not vals:
        return "n=0"
    s = f"n={len(vals)}  promedio={statistics.mean(vals):.2f}  máximo={max(vals):.2f}  mínimo={min(vals):.2f}"
    if objetivo is not None:
        s += f"  superan {objetivo}s: {sum(1 for v in vals if v > objetivo)}"
    return s


# ---------- RNF 1: estabilidad ----------
def estabilidad(ev, args):
    ev, t0, t1 = recorte(ev, args.ini, args.fin)
    ser = [(t, d) for t, f, d in ev if f == "serie"]
    print(f"Inicio {hms(t0)} | Fin {hms(t1)} | Duración {(t1 - t0) / 60:.1f} min")

    rst = [t for t, d in ser if re.search(r"rst:0x|ESP-ROM:", d)]
    ms = [(t, int(m.group(1))) for t, d in ser if (m := re.search(r"ms=(\d+)", d))]
    caidas = [q[0] for p, q in zip(ms, ms[1:]) if q[1] < p[1]]
    huecos = [(p[0], q[0] - p[0]) for p, q in zip(ser, ser[1:]) if q[0] - p[0] > args.hueco]

    print(f"Mensajes de arranque (rst:/ESP-ROM): {len(rst)} {[hms(t) for t in rst]}")
    print(f"Reinicios del contador ms: {len(caidas)} {[hms(t) for t in caidas]}")
    print(f"Huecos de serie > {args.hueco}s (posible bloqueo): {len(huecos)}")
    for t, g in huecos:
        print(f"   {hms(t)}  silencio de {g:.1f}s")
    print(f"Órdenes marcadas: {len(marcas(ev, 'orden'))} | Consultas marcadas: {len(marcas(ev, 'consulta'))}")
    print(f"Órdenes publicadas por el firmware: {len(serie(ev, r'orden (abrir|cerrar) publicada'))} | "
          f"Movimientos completados (estimados): {len(serie(ev, r'Posicion estimada'))}")
    print(f"Silencio final de serie hasta '{args.fin}': {t1 - ser[-1][0]:.1f} s" if ser else "Sin líneas serie")
    n_desc = len(serie(ev, r"MQTT\] Desconectado"))
    n_err = len(serie(ev, r"MQTT\] Error"))
    print(f"[MQTT] Desconectado: {n_desc} | [MQTT] Error: {n_err}")


# ---------- RNF 4: frecuencia de reporte ----------
def frecuencia(ev, args):
    ev, _, _ = recorte(ev, args.ini, args.fin)
    rep = [t for t, _ in serie(ev, r"\[SHADOW\] reported aceptado")]
    iv = [q - p for p, q in zip(rep, rep[1:])]
    print("N   hora      intervalo(s)")
    for i, t in enumerate(rep):
        print(f"{i + 1:<3} {hms(t)}  {'—' if i == 0 else f'{iv[i - 1]:.2f}'}")
    print(resumen(iv))
    cortos = [x for x in iv if x < args.evento]
    print(f"Intervalos < {args.evento}s (posible reporte por evento): {len(cortos)}")
    mq = sum(1 for _, f, d in ev if f == "mqtt" and "update/accepted" in d)
    print(f"update/accepted vistos por MQTT: {mq} (incluye cualquier otra fuente)")


# ---------- RNF 2: tiempo de respuesta ----------
def respuesta(ev, args):
    # Inicio: la marca 'envio' (grabar_rnf.py la escribe justo antes de mandar abrir/cerrar).
    # Firmware de ensayo: delta recibido de AWS, orden entregada al servo y posición estimada.
    envios, finales = marcas(ev, "envio"), marcas(ev, "final")
    publ = [(t, d) for t, d in serie(ev, r"\[ENSAYO\] orden ")]
    delta = [t for t, _ in serie(ev, r"\[SHADOW\] delta recibido")]
    entrega = [t for t, _ in serie(ev, r"\[SERVO\] orden entregada")]
    servo = [t for t, _ in serie(ev, r"\[SERVO\] Posicion estimada")]
    fis, est, dl = [], [], []
    print("Prueba  envío     orden     delta(s)  entregada(s)  servo estim.(s)  final marca(s)")
    for i, te in enumerate(envios):
        lim = envios[i + 1] if i + 1 < len(envios) else INF
        p = next((d for t, d in publ if te < t < lim), "")
        orden = "abrir" if " abrir " in p else ("cerrar" if " cerrar " in p else "?")
        if "NO publicada" in p:
            orden += " (NO publicada)"
        td, tg = siguiente(delta, te, lim), siguiente(entrega, te, lim)
        ts, tf = siguiente(servo, te, lim), siguiente(finales, te, lim)
        r = lambda t: t - te if t else None
        if r(tf) is not None: fis.append(r(tf))
        if r(ts) is not None: est.append(r(ts))
        if r(td) is not None: dl.append(r(td))
        print(f"{i + 1:<7} {hms(te)}  {orden:<9} {fmt(r(td)):>8}  {fmt(r(tg)):>12}  {fmt(r(ts)):>15}  {fmt(r(tf)):>14}")
    print("\nEnvío → delta recibido (nube ida y vuelta):   ", resumen(dl))
    print("Envío → posición estimada por el firmware:    ", resumen(est, args.objetivo))
    print("Envío → marca 'final' (observación humana):   ", resumen(fis, args.objetivo))


# ---------- RNF 3: exactitud del sensor ----------
def sensor(ev, args):
    cond = [(t, d) for t, f, d in ev if f == "marca" and d in ("seco", "agua")]
    lect = [(t, int(m.group(1)), int(m.group(2)))
            for t, d in serie(ev, r"\[SENSOR\]")
            if (m := re.search(r"raw=(-?\d+) agua=(\d)", d))]
    ack = [t for t, _ in serie(ev, r"\[SHADOW\] reported aceptado")]
    tp = tn = fp = fn = sin = 0
    print("N   hora      condición  ADC    agua(serie)  resultado    AWS aceptó tras la lectura (s)")
    for i, (tm, c) in enumerate(cond):
        ini = tm + args.estab
        lim = min(cond[i + 1][0] if i + 1 < len(cond) else INF, ini + 10)
        l = next(((t, raw, ag) for t, raw, ag in lect if ini <= t < lim), None)
        sh = "—"
        esperado = c == "agua"
        if l is None:
            sin += 1
            res, raw, ag = "SIN LECTURA", "—", "—"
        else:
            tl, raw, ag = l
            ta = siguiente(ack, tl)
            sh = fmt(ta - tl) if ta else "—"
            obs = ag == 1
            if esperado and obs:
                tp += 1; res = "VP acierto"
            elif not esperado and not obs:
                tn += 1; res = "VN acierto"
            elif not esperado and obs:
                fp += 1; res = "FP error"
            else:
                fn += 1; res = "FN error"
        print(f"{i + 1:<3} {hms(tm)}  {c:<9}  {str(raw):<5}  {str(ag):<11}  {res:<11} {sh}")
    n = len(cond)
    if n:
        ac, er = tp + tn, fp + fn + sin
        print(f"\nObservaciones={n} VP={tp} VN={tn} FP={fp} FN={fn} sin lectura={sin}")
        print(f"Aciertos {ac / n * 100:.1f}% | Errores {er / n * 100:.1f}%")


# ---------- RNF 5/6: reconexión ----------
def reconexion(ev, args):
    offs, ons = marcas(ev, args.off), marcas(ev, args.on)
    conn = [t for t, _ in serie(ev, r"\[MQTT\] Conectado")]
    desc = [t for t, _ in serie(ev, r"\[MQTT\] Desconectado")]
    servo = [t for t, _ in serie(ev, r"\[SERVO\] Posicion estimada")]
    rep = [t for t, _ in serie(ev, r"\[SHADOW\] reported aceptado")]
    sync = [t for t, _ in serie(ev, r"\[SHADOW\] Estado inicial recuperado")]
    entrega = [t for t, _ in serie(ev, r"\[SERVO\] orden entregada")]
    ordenes, finales = marcas(ev, "orden"), marcas(ev, "final")
    for i, off in enumerate(offs):
        on = siguiente(ons, off)
        if on is None:
            print(f"Repetición {i + 1}: falta la marca '{args.on}'")
            continue
        t_desc = siguiente(desc, off, on)
        t_mqtt = siguiente(conn, on)
        t_servo = siguiente(servo, on)
        t_rep = siguiente(rep, t_servo) if t_servo else None
        t_fis = siguiente(finales, on)
        fin = t_rep or t_servo or INF
        durante = any(off < o < on for o in ordenes)
        repetida = any(on < o < fin for o in ordenes)
        rel = lambda t: fmt(t - on) if t else "—"
        print(f"\nRepetición {i + 1}  ({hms(off)} → {hms(on)}, interrupción {on - off:.1f}s)")
        print(f"  Orden enviada durante la interrupción: {'sí' if durante else 'NO'}")
        print(f"  Firmware detectó desconexión:  {fmt(t_desc - off) if t_desc else '—'} s tras '{args.off}'")
        print(f"  Recuperación MQTT:             {rel(t_mqtt)} s tras '{args.on}'")
        print(f"  Shadow recuperado (GET):       {rel(siguiente(sync, on))} s")
        print(f"  Orden entregada al servo:      {rel(siguiente(entrega, on))} s")
        print(f"  Movimiento (estimado firmware): {rel(t_servo)} s")
        print(f"  Posición final (marca 'final'): {rel(t_fis)} s")
        print(f"  reported aceptado final:       {rel(t_rep)} s")
        print(f"  ¿Se repitió la orden?          {'SÍ' if repetida else 'no'}")


# ---------- CLI ----------
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", default="rnf-eventos.csv")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("estabilidad")
    s.add_argument("--ini", default="est_ini")
    s.add_argument("--fin", default="est_fin")
    s.add_argument("--hueco", type=float, default=5.0, help="segundos de silencio de serie que cuentan como posible bloqueo")

    s = sub.add_parser("frecuencia")
    s.add_argument("--ini", default="est_ini")
    s.add_argument("--fin", default="est_fin")
    s.add_argument("--evento", type=float, default=4.0, help="intervalos menores a esto = posible reporte por evento")

    s = sub.add_parser("respuesta")
    s.add_argument("--objetivo", type=float, default=3.0)

    s = sub.add_parser("sensor")
    s.add_argument("--estab", type=float, default=3.0, help="segundos de estabilización tras la marca")

    s = sub.add_parser("reconexion")
    s.add_argument("--off", default="wifi_off")
    s.add_argument("--on", default="wifi_on")

    args = p.parse_args()
    ev = cargar(args.csv)
    if not ev:
        raise SystemExit("El CSV está vacío o no tiene el formato esperado.")
    {"estabilidad": estabilidad, "frecuencia": frecuencia, "respuesta": respuesta,
     "sensor": sensor, "reconexion": reconexion}[args.cmd](ev, args)


if __name__ == "__main__":
    main()
