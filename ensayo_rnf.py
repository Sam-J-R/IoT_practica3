#!/usr/bin/env python3
# pip install pyserial paho-mqtt
"""Ensayos RNF automatizados del tendedero inteligente.

Requiere el firmware de ensayo:  pio run -e tendedero_ensayo -t upload
Cerrar cualquier otro monitor serie antes de empezar.

Comandos:
  respuesta     RNF 2  órdenes alternadas; envío → delta → servo → reporte aceptado
  estabilidad   RNF 1  15 min con órdenes y consultas; también calcula RNF 4 (frecuencia)
  frecuencia    RNF 4  observación pasiva de reportes (sin órdenes)
  sensor        RNF 3  guiado: el operador coloca seco/agua cuando se le indica
  wifi          RNF 6  corta Wi-Fi en el ESP32, deja la orden en AWS y restablece
  reinicio      RNF 5  mantiene el ESP32 en reset (RTS/EN), deja la orden y lo libera
  todo          respuesta + estabilidad + wifi + reinicio (sensor aparte: necesita operador)

Ejemplo:
  python ensayo_rnf.py --puerto COM3 todo --endpoint XXX-ats.iot.us-east-2.amazonaws.com \\
      --thing tendedero-inteligente --ca AmazonRootCA1.pem --cert cert.pem.crt --key private.pem.key

Cada ensayo deja en ./resultados: el log crudo (formato de analizar_rnf.py), una tabla CSV por
prueba, un informe Markdown con el veredicto calculado y resumen.md con la tabla final.
Los veredictos se calculan con los objetivos declarados en los argumentos; no se ajustan solos.
"""
import argparse
import bisect
import csv
import json
import random
import re
import statistics
import threading
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
RE_GET = r"\[SHADOW\] get v=(\d+) desired=(\S+) reported=(\S+)"
RE_SENSOR = r"\[SENSOR\] ms=(\d+) raw=(-?\d+) agua=(-?\d+)"
RE_ACK = r"\[SHADOW\] reported aceptado"
RE_SERVO = r"\[SERVO\] Posicion estimada"
RE_ARRANQUE = r"\[ENSAYO\] Firmware de ensayo|rst:0x|ESP-ROM:|ets [A-Z][a-z]{2} "


class ErrorEnsayo(Exception):
    pass


# ---------------------------------------------------------------- monitor serie
class Monitor:
    """Lee el puerto serie en segundo plano, registra todo y permite esperar patrones."""

    def __init__(self, puerto, baud, log_path, eco=True):
        import serial
        self.serial_mod = serial
        self.puerto, self.baud, self.eco = puerto, baud, eco
        self.lineas, self.tiempos = [], []
        self.cv = threading.Condition()
        self.wlock = threading.Lock()
        self.f = open(log_path, "a", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        self.rts = False
        self.error_disco = None
        self.s = None
        self._abrir()
        threading.Thread(target=self._leer, daemon=True).start()

    def _abrir(self):
        s = self.serial_mod.Serial()
        s.port, s.baudrate, s.timeout = self.puerto, self.baud, 0.5
        s.dtr = False      # GPIO0 en alto: nunca entrar en modo descarga
        s.rts = self.rts   # False: abrir el puerto no reinicia el ESP32
        s.open()
        self.s = s
        self.log("serie_estado", f"puerto {self.puerto} abierto")

    def _leer(self):
        while True:
            try:
                data = self.s.readline()
            except Exception as e:  # p. ej. USB desconectado en el ensayo manual
                self.log("serie_estado", f"ERROR serie: {e}")
                try:
                    self.s.close()
                except Exception:
                    pass
                while True:
                    time.sleep(1)
                    try:
                        self._abrir()
                        break
                    except Exception:
                        continue
                continue
            if data:
                linea = data.decode(errors="replace").strip()
                if linea:
                    self.log("serie", linea)

    def log(self, fuente, dato):
        t = time.time()
        with self.cv:
            if not self.error_disco:
                try:
                    self.w.writerow([fuente, f"{t:.3f}", datetime.fromtimestamp(t).isoformat(timespec="milliseconds"), dato])
                    self.f.flush()
                except OSError as e:
                    # Sin poder guardar el log no hay evidencia: el ensayo en curso se invalida.
                    self.error_disco = f"no se pudo escribir el log ({e})"
            self.lineas.append((t, fuente, dato))
            self.tiempos.append(t)
            self.cv.notify_all()
        if self.eco and not (fuente == "serie" and dato.startswith("[SENSOR]")):
            print(f"{datetime.fromtimestamp(t):%H:%M:%S.%f}"[:-3], f"[{fuente}] {dato}")
        return t

    def marca(self, nombre):
        return self.log("marca", nombre)

    def enviar(self, comando, marcas=()):
        """Registra las marcas, escribe el comando y devuelve la hora de la primera marca."""
        tiempos = [self.marca(m) for m in marcas]
        tiempos.append(self.log("comando", comando))
        with self.wlock:
            self.s.write((comando + "\n").encode())
        return tiempos[0]

    def reset(self, mantener):
        """RTS activo = EN en bajo en las placas DevKit con autoreset."""
        self.rts = mantener
        with self.wlock:
            self.s.rts = mantener

    def esperar(self, patron, desde, timeout):
        """Primera línea serie con t >= desde que cumple el patrón -> (t, match) o None."""
        rx = re.compile(patron)
        fin = time.time() + timeout
        with self.cv:
            i = bisect.bisect_left(self.tiempos, desde)
            while True:
                if self.error_disco:
                    raise ErrorEnsayo(self.error_disco + ". Libere espacio y repita el ensayo.")
                while i < len(self.lineas):
                    t, f, d = self.lineas[i]
                    i += 1
                    if f == "serie":
                        m = rx.search(d)
                        if m:
                            return t, m
                resto = fin - time.time()
                if resto <= 0:
                    return None
                self.cv.wait(resto)

    def entre(self, desde, hasta, patron=None, fuente="serie"):
        rx = re.compile(patron) if patron else None
        with self.cv:
            i, j = bisect.bisect_left(self.tiempos, desde), bisect.bisect_right(self.tiempos, hasta)
            out = []
            for t, f, d in self.lineas[i:j]:
                if f != fuente:
                    continue
                m = rx.search(d) if rx else None
                if rx is None or m:
                    out.append((t, d, m))
            return out


# ---------------------------------------------------------------- cliente AWS del PC
class Nube:
    """Conecta con el certificado del dispositivo SOLO mientras el ESP32 está fuera de línea."""

    def __init__(self, a):
        faltan = [n for n in ("endpoint", "thing", "ca", "cert", "key") if not getattr(a, n)]
        if faltan:
            raise ErrorEnsayo("Faltan argumentos para AWS: " + ", ".join("--" + n for n in faltan))
        self.a = a
        self.base = f"$aws/things/{a.thing}/shadow"

    def ordenar(self, posicion, monitor):
        import paho.mqtt.client as mqtt
        ev = {k: threading.Event() for k in ("con", "sub", "upd", "get")}
        res = {}

        def on_connect(c, u, flags, rc, props=None):
            if rc.is_failure:
                res["error"] = f"conexión rechazada rc={rc}"
                ev["con"].set()
                return
            ev["con"].set()
            c.subscribe([(self.base + t, 1) for t in
                         ("/update/accepted", "/update/rejected", "/get/accepted", "/get/rejected")])

        def on_subscribe(c, u, mid, rcs, props=None):
            ev["sub"].set()

        def on_message(c, u, m):
            doc = json.loads(m.payload or b"{}")
            clave = "upd" if "/update/" in m.topic else "get"
            res[clave] = (m.topic.rsplit("/", 1)[-1], doc)
            ev[clave].set()

        cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.a.thing)
        cli.tls_set(ca_certs=self.a.ca, certfile=self.a.cert, keyfile=self.a.key)
        cli.on_connect, cli.on_subscribe, cli.on_message = on_connect, on_subscribe, on_message
        cli.connect(self.a.endpoint, 8883, 30)
        cli.loop_start()
        try:
            if not (ev["con"].wait(20) and "error" not in res and ev["sub"].wait(10)):
                raise ErrorEnsayo("El PC no pudo conectar a AWS IoT: " + res.get("error", "tiempo agotado"))
            t_pub = monitor.marca("orden")
            monitor.log("pc", f"publica desired.cubierta={posicion}")
            cli.publish(self.base + "/update", json.dumps({"state": {"desired": {"cubierta": posicion}}}), qos=1)
            if not ev["upd"].wait(10):
                raise ErrorEnsayo("AWS no respondió al update")
            monitor.log("pc", f"update {res['upd'][0]}")
            cli.publish(self.base + "/get", "", qos=1)
            if not ev["get"].wait(10):
                raise ErrorEnsayo("AWS no respondió al get")
            doc = res["get"][1]
            st = doc.get("state", {})
            monitor.log("pc", "get desired={} reported={}".format(
                st.get("desired", {}).get("cubierta"), st.get("reported", {}).get("cubierta")))
            return {"t": t_pub, "update": res["upd"][0], "doc": doc}
        finally:
            cli.disconnect()
            cli.loop_stop()


# ---------------------------------------------------------------- utilidades de ensayo
def opuesta(p):
    return "cerrada" if p == "abierta" else "abierta"


def comando_de(p):
    return "abrir" if p == "abierta" else "cerrar"


def estado_shadow(mon, timeout=10):
    t = mon.enviar("estado", ("consulta",))
    r = mon.esperar(RE_GET, t, timeout)
    if not r:
        return None
    _, m = r
    return {"t": r[0], "version": int(m.group(1)), "desired": m.group(2), "reported": m.group(3)}


def preparar(mon, timeout=120):
    """Comprueba firmware de ensayo y sincronización; devuelve el estado convergente."""
    print(f"Esperando sincronización con AWS (hasta {timeout} s)...")
    if not mon.esperar(RE_ACK, time.time() - 6, timeout):
        raise ErrorEnsayo("No aparece '[SHADOW] reported aceptado'. ¿Wi-Fi/AWS operativos?")
    st = estado_shadow(mon)
    if not st:
        raise ErrorEnsayo("Sin respuesta a 'estado'. Cargue el entorno tendedero_ensayo.")
    if st["desired"] != st["reported"] and st["desired"] in ("abierta", "cerrada"):
        print("Hay una orden pendiente; esperando a que se aplique...")
        fin = mon.esperar(RE_SERVO, st["t"] - 5, 20)
        if fin:
            mon.esperar(RE_ACK, fin[0], 10)
        st = estado_shadow(mon)
    if not st or st["reported"] not in ("abierta", "cerrada"):
        # Sin posición conocida: fijar una con una orden inicial que no se mide.
        r = orden(mon, "cerrada")
        if r["servo"] is None:
            raise ErrorEnsayo("No se pudo fijar una posición inicial de la cubierta.")
        st = estado_shadow(mon)
    return st


def orden(mon, destino, t_delta=10, t_servo=15):
    t0 = mon.enviar(comando_de(destino), ("envio", "orden"))
    r = {"orden": comando_de(destino), "hora": datetime.fromtimestamp(t0).strftime("%H:%M:%S"),
         "delta": None, "entregada": None, "servo": None, "aws": None, "incidencia": ""}
    pub = mon.esperar(r"\[ENSAYO\] orden \w+ (publicada|NO publicada)", t0, 3)
    if not pub or pub[1].group(1) != "publicada":
        r["incidencia"] = "orden no publicada (sin MQTT)"
        return r
    rel = lambda x: round(x[0] - t0, 3) if x else None
    d = mon.esperar(r"\[SHADOW\] delta recibido", t0, t_delta)
    e = mon.esperar(r"\[SERVO\] orden entregada", t0, t_delta)
    s = mon.esperar(RE_SERVO, t0, t_servo)
    a = mon.esperar(RE_ACK, s[0], 10) if s else None
    r.update(delta=rel(d), entregada=rel(e), servo=rel(s), aws=rel(a))
    if not d:
        r["incidencia"] = "sin delta"
    elif not s:
        r["incidencia"] = "sin fin de movimiento"
    elif not a:
        r["incidencia"] = "reporte final no aceptado"
    return r


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0, "promedio": None, "maximo": None, "minimo": None}
    return {"n": len(vals), "promedio": round(statistics.mean(vals), 3),
            "maximo": round(max(vals), 3), "minimo": round(min(vals), 3)}


def f(x, d=2):
    return "—" if x is None else (f"{x:.{d}f}".replace(".", ",") if isinstance(x, float) else str(x))


# ---------------------------------------------------------------- informes
class Informe:
    def __init__(self, carpeta, sesion, puerto):
        self.carpeta, self.sesion, self.puerto = carpeta, sesion, puerto

    def tabla_csv(self, nombre, filas):
        ruta = self.carpeta / f"{nombre}-{self.sesion}.csv"
        if filas:
            with open(ruta, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
                w.writeheader()
                w.writerows(filas)
        return ruta

    def escribir(self, clave, titulo, objetivo, procedimiento, condiciones, columnas, filas,
                 resumen, cumple, resultado, limitaciones):
        csv_ruta = self.tabla_csv(clave, filas)
        md = [f"# {titulo}", "",
              f"Sesión {self.sesion} · puerto {self.puerto} · generado por `ensayo_rnf.py` a partir del log "
              f"`log-{self.sesion}.csv`.", "",
              "## Objetivo declarado", "", objetivo, "",
              "## Procedimiento", "", procedimiento, "",
              "## Condiciones", "", "| Parámetro | Valor |", "|---|---|"]
        md += [f"| {k} | {v} |" for k, v in condiciones.items()]
        md += ["", "## Mediciones", "", "| " + " | ".join(c for c, _ in columnas) + " |",
               "|" + "|".join("---" for _ in columnas) + "|"]
        md += ["| " + " | ".join(f(fila.get(k)) for _, k in columnas) + " |" for fila in filas]
        md += ["", "## Resumen", "", "| Medida | Valor |", "|---|---|"]
        md += [f"| {k} | {f(v)} |" for k, v in resumen.items()]
        veredicto = {True: "Cumple", False: "No cumple", None: "Incompleto"}[cumple]
        md += ["", "## Conclusión", "", f"**{veredicto}.** {resultado}", "",
               "## Limitaciones", "", limitaciones, "",
               f"Datos: [{csv_ruta.name}]({csv_ruta.name}), [log-{self.sesion}.csv](log-{self.sesion}.csv)."]
        ruta = self.carpeta / f"{clave}-{self.sesion}.md"
        ruta.write_text("\n".join(md) + "\n", encoding="utf-8")
        self._resumen(clave, titulo, objetivo, resultado, veredicto, ruta.name)
        print(f"\n==> {titulo}: {veredicto}. Informe: {ruta}")
        return ruta

    def _resumen(self, clave, titulo, objetivo, resultado, veredicto, archivo):
        ruta_json = self.carpeta / "resumen.json"
        datos = json.loads(ruta_json.read_text(encoding="utf-8")) if ruta_json.exists() else {}
        datos[clave] = {"titulo": titulo, "objetivo": objetivo, "resultado": resultado,
                        "veredicto": veredicto, "archivo": archivo}
        ruta_json.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        md = ["# Tabla final de RNF", "", "Último ensayo registrado de cada requisito.", "",
              "| Requisito | Objetivo declarado | Resultado medido | ¿Cumple? | Evidencia |", "|---|---|---|---|---|"]
        for k in sorted(datos):
            d = datos[k]
            md.append(f"| {d['titulo']} | {d['objetivo']} | {d['resultado']} | {d['veredicto']} | "
                      f"[{d['archivo']}]({d['archivo']}) |")
        (self.carpeta / "resumen.md").write_text("\n".join(md) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- RNF 2
def ensayo_respuesta(mon, inf, a):
    st = preparar(mon)
    destino = opuesta(st["reported"])
    filas = []
    for i in range(a.ordenes):
        print(f"\nOrden {i + 1}/{a.ordenes}: {comando_de(destino)}")
        r = orden(mon, destino)
        r = {"prueba": i + 1, **r}
        filas.append(r)
        destino = opuesta(destino)
        time.sleep(a.espera)
    s_servo, s_delta, s_aws = (stats([r[k] for r in filas]) for k in ("servo", "delta", "aws"))
    fallidas = sum(1 for r in filas if r["servo"] is None)
    superan = sum(1 for r in filas if r["servo"] is not None and r["servo"] > a.objetivo)
    cumple = None if s_servo["n"] == 0 else (fallidas == 0 and superan == 0)
    resultado = (f"{s_servo['n']}/{len(filas)} órdenes completadas; envío → posición estimada: promedio "
                 f"{f(s_servo['promedio'])} s, máximo {f(s_servo['maximo'])} s; {superan} superan {f(float(a.objetivo))} s.")
    inf.escribir(
        "rnf-02-respuesta", "Tiempo de respuesta orden → actuador",
        f"Tiempo desde la publicación de la orden hasta la posición final ≤ {f(float(a.objetivo))} s en todas las órdenes.",
        f"{a.ordenes} órdenes alternadas enviadas por serie con el firmware de ensayo, con {a.espera} s entre órdenes. "
        "El ESP32 publica `desired.cubierta` (mismo documento que Lambda), AWS devuelve el delta y el servo se mueve por el "
        "camino normal. Fin: línea `[SERVO] Posicion estimada`; confirmación: siguiente `reported aceptado`.",
        {"Modalidad": "Orden MQTT desde el dispositivo, sin Alexa ni Lambda",
         "Asentamiento configurado del servo": "incluido en el tiempo medido (ver calibracion_local.h)",
         "Reloj": "PC, al recibir cada línea serie"},
        [("Prueba", "prueba"), ("Orden", "orden"), ("Hora", "hora"), ("Delta (s)", "delta"),
         ("Posición estimada (s)", "servo"), ("Reporte aceptado (s)", "aws"), ("Incidencia", "incidencia")],
        filas,
        {"Órdenes": len(filas), "Fallidas": fallidas,
         "Envío → delta, promedio (s)": s_delta["promedio"], "Envío → delta, máximo (s)": s_delta["maximo"],
         "Envío → posición, promedio (s)": s_servo["promedio"], "Envío → posición, máximo (s)": s_servo["maximo"],
         "Envío → reporte aceptado, máximo (s)": s_aws["maximo"], "Superan el objetivo": superan},
        cumple, resultado,
        "No incluye Alexa ni Lambda, por lo que no es la latencia de voz del enunciado; la duración de Lambda medida en "
        "CloudWatch es un componente aparte. La posición es la estimada por el firmware al terminar el asentamiento; "
        "confirmar con video si se requiere la posición física.")


# ---------------------------------------------------------------- RNF 1 + RNF 4
def analizar_ventana(mon, t0, t1, hueco):
    serie = mon.entre(t0, t1)
    arranques = [t for t, d, _ in serie if re.search(RE_ARRANQUE, d)]
    ms = [(t, int(m.group(1))) for t, d, m in mon.entre(t0, t1, RE_SENSOR)]
    caidas = [q[0] for p, q in zip(ms, ms[1:]) if q[1] < p[1]]
    huecos = [(p[0], round(q[0] - p[0], 2)) for p, q in zip(serie, serie[1:]) if q[0] - p[0] > hueco]
    acks = [t for t, _, _ in mon.entre(t0, t1, RE_ACK)]
    eventos = [t for t, _, _ in mon.entre(t0, t1, RE_SERVO)]
    agua = [(t, m.group(3)) for t, d, m in mon.entre(t0, t1, RE_SENSOR)]
    eventos += [q[0] for p, q in zip(agua, agua[1:]) if q[1] != p[1]]
    # Al empezar a moverse la posición pasa a desconocida y el firmware también reporta ese cambio.
    inicios = [t for t, _, _ in mon.entre(t0, t1, r"\[SERVO\] orden entregada")]
    periodicos, por_evento = [], []
    for p, q in zip(acks, acks[1:]):
        (por_evento if any(p < e <= q for e in eventos + inicios) else periodicos).append(round(q - p, 3))
    lat_evento = [round(next(x for x in acks if x > e) - e, 3) for e in sorted(eventos) if any(x > e for x in acks)]
    return {"arranques": arranques, "caidas_ms": caidas, "huecos": huecos, "acks": acks,
            "periodicos": periodicos, "por_evento": por_evento, "lat_evento": lat_evento,
            "mqtt_desc": len(mon.entre(t0, t1, r"\[MQTT\] Desconectado"))}


def informe_frecuencia(inf, a, v, origen):
    sp, se = stats(v["periodicos"]), stats(v["lat_evento"])
    cumple = None if sp["n"] < 2 else (sp["maximo"] <= a.max_intervalo)
    resultado = (f"Respaldo periódico: {sp['n']} intervalos, promedio {f(sp['promedio'])} s, máximo {f(sp['maximo'])} s. "
                 f"Por evento: {se['n']} cambios, aceptados tras {f(se['promedio'])} s en promedio (máx. {f(se['maximo'])} s).")
    filas = [{"n": i + 1, "intervalo": x, "tipo": "periódico"} for i, x in enumerate(v["periodicos"])]
    filas += [{"n": i + 1, "intervalo": x, "tipo": "cambio → aceptado"} for i, x in enumerate(v["lat_evento"])]
    inf.escribir(
        "rnf-04-frecuencia", "Frecuencia de reporte",
        f"Intervalo entre reportes periódicos aceptados ≤ {f(float(a.max_intervalo))} s y reporte por evento ante cambios.",
        f"Timestamps de `[SHADOW] reported aceptado` (respuesta update/accepted de AWS con el clientToken del firmware) "
        f"durante {origen}. Un intervalo es «por evento» si contiene un fin de movimiento o un cambio de clasificación.",
        {"Muestreo": "500 ms", "Respaldo nominal": "5 s desde la aceptación anterior"},
        [("N", "n"), ("Intervalo (s)", "intervalo"), ("Tipo", "tipo")], filas,
        {"Intervalos periódicos": sp["n"], "Promedio (s)": sp["promedio"], "Máximo (s)": sp["maximo"],
         "Mínimo (s)": sp["minimo"], "Eventos con reporte": se["n"], "Latencia evento máx. (s)": se["maximo"]},
        cumple, resultado,
        "El intervalo supera 5 s por diseño: el plazo cuenta desde la aceptación anterior e incluye el viaje a AWS. "
        "Los reportes de Lambda o manuales no se cuentan porque el firmware solo registra los de su clientToken.")


def ensayo_estabilidad(mon, inf, a, con_ordenes=True):
    st = preparar(mon)
    destino = opuesta(st["reported"])
    t0 = mon.marca("est_ini")
    ordenes, consultas, k = [], [], 0
    duracion = a.minutos * 60
    print(f"Ensayo de {a.minutos} min" + (f", acción cada {a.periodo} s" if con_ordenes else " pasivo"))
    while time.time() - t0 < duracion:
        siguiente = t0 + (k + 1) * a.periodo
        time.sleep(max(0, min(siguiente, t0 + duracion) - time.time()))
        if time.time() - t0 >= duracion or not con_ordenes:
            k += 1
            continue
        if k % 2 == 0:
            r = orden(mon, destino)
            ordenes.append(r)
            destino = opuesta(destino)
        else:
            e = estado_shadow(mon)
            consultas.append(e is not None)
        k += 1
        print(f"  {int(time.time() - t0)} s / {duracion} s")
    t1 = mon.marca("est_fin")
    v = analizar_ventana(mon, t0, t1, a.hueco)
    origen = f"el ensayo de {'estabilidad' if con_ordenes else 'observación pasiva'} ({a.minutos} min)"
    informe_frecuencia(inf, a, v, origen)
    if not con_ordenes:
        return
    ok_ord = sum(1 for r in ordenes if r["servo"] is not None and r["aws"] is not None)
    ok_con = sum(consultas)
    reinicios = len(v["arranques"]) + len(v["caidas_ms"])
    max_ack = max([q - p for p, q in zip(v["acks"], v["acks"][1:])], default=None)
    bloqueos = len(v["huecos"]) + (1 if max_ack is None or max_ack > a.max_sin_reporte else 0)
    dur = (t1 - t0) / 60
    cumple = (dur >= a.minutos - 0.05 and reinicios == 0 and bloqueos == 0
              and ok_ord == len(ordenes) and ok_con == len(consultas))
    filas = [{"tipo": "orden", "n": i + 1, **r} for i, r in enumerate(ordenes)]
    resultado = (f"{dur:.1f} min, {len(ordenes)} órdenes ({ok_ord} completas) y {len(consultas)} consultas ({ok_con} con "
                 f"respuesta); {reinicios} reinicios, {bloqueos} bloqueos, {v['mqtt_desc']} desconexiones MQTT.")
    inf.escribir(
        "rnf-01-estabilidad", "Estabilidad",
        f"Operar {a.minutos} min sin reinicios ni bloqueos, completando todas las órdenes y consultas.",
        f"Desde `est_ini` hasta `est_fin`: cada {a.periodo} s se alterna una orden (abrir/cerrar) y una consulta del Shadow. "
        f"Reinicio = mensaje de arranque o retroceso del contador `ms`. Bloqueo = silencio serie > {a.hueco} s o más de "
        f"{a.max_sin_reporte} s sin reporte aceptado por AWS.",
        {"Inicio": datetime.fromtimestamp(t0).strftime("%Y-%m-%d %H:%M:%S"),
         "Fin": datetime.fromtimestamp(t1).strftime("%H:%M:%S"),
         "Consultas": "lectura del Shadow desde el dispositivo (no Alexa)"},
        [("N", "n"), ("Orden", "orden"), ("Hora", "hora"), ("Posición (s)", "servo"), ("Aceptado (s)", "aws"),
         ("Incidencia", "incidencia")], filas,
        {"Duración (min)": round(dur, 2), "Órdenes": len(ordenes), "Órdenes completas": ok_ord,
         "Consultas": len(consultas), "Consultas con respuesta": ok_con, "Reinicios": reinicios,
         "Silencios serie > umbral": len(v["huecos"]), "Máx. sin reporte aceptado (s)": round(max_ack, 2) if max_ack else None,
         "Desconexiones MQTT": v["mqtt_desc"]},
        cumple, resultado,
        "El ensayo no cubre la interacción por Alexa. Un ESP32 bloqueado con el puerto USB activo se detecta por silencio serie.")


# ---------------------------------------------------------------- RNF 3
def leer_umbrales():
    for nombre in ("calibracion_local.h", "calibracion.example.h"):
        p = RAIZ / "firmware" / "include" / nombre
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace")
            g = lambda n: (re.search(rf"{n}\s*=\s*(-?\d+)", txt) or [None, "?"])[1]
            return {"UMBRAL_SECO": g("UMBRAL_SECO"), "UMBRAL_AGUA": g("UMBRAL_AGUA"), "archivo": nombre}
    return {"UMBRAL_SECO": "?", "UMBRAL_AGUA": "?", "archivo": "no encontrado"}


def ensayo_sensor(mon, inf, a):
    preparar(mon)
    umb = leer_umbrales()
    semilla = a.semilla if a.semilla is not None else int(time.time())
    rnd = random.Random(semilla)
    secuencia = ["seco"] * (a.observaciones // 2) + ["agua"] * (a.observaciones - a.observaciones // 2)
    rnd.shuffle(secuencia)
    print(f"Umbrales {umb}. Secuencia aleatoria (semilla {semilla}). Mantenga líquidos lejos del ESP32.")
    filas = []
    for i, cond in enumerate(secuencia):
        input(f"\nObservación {i + 1}/{len(secuencia)}: deje el sensor {cond.upper()} y pulse Enter...")
        t = mon.marca(cond)
        time.sleep(a.estab)
        l = mon.esperar(RE_SENSOR, t + a.estab, 3)
        fila = {"n": i + 1, "hora": datetime.fromtimestamp(t).strftime("%H:%M:%S"), "condicion": cond,
                "adc": None, "agua_detectada": None, "resultado": "SIN LECTURA", "aceptado": None}
        if l:
            raw, ag = int(l[1].group(2)), int(l[1].group(3))
            ack = mon.esperar(RE_ACK, l[0], 7)
            esperado = cond == "agua"
            obs = {1: True, 0: False}.get(ag)
            res = ("DESCONOCIDA" if obs is None else
                   "VP" if esperado and obs else "VN" if not esperado and not obs else "FP" if obs else "FN")
            fila.update(adc=raw, agua_detectada={True: "true", False: "false", None: "desconocida"}[obs],
                        resultado=res, aceptado=round(ack[0] - l[0], 3) if ack else None)
        filas.append(fila)
        print(f"  ADC={fila['adc']} agua={fila['agua_detectada']} → {fila['resultado']}")
    n = len(filas)
    cuenta = {k: sum(1 for x in filas if x["resultado"] == k) for k in ("VP", "VN", "FP", "FN")}
    aciertos = cuenta["VP"] + cuenta["VN"]
    pct = 100 * aciertos / n if n else 0
    cumple = pct >= a.criterio and cuenta["FN"] <= a.max_fn
    resultado = (f"{aciertos}/{n} aciertos ({pct:.1f} %): VP={cuenta['VP']} VN={cuenta['VN']} FP={cuenta['FP']} "
                 f"FN={cuenta['FN']}, otras={n - sum(cuenta.values())}.")
    inf.escribir(
        "rnf-03-sensor", "Clasificación del sensor de agua",
        f"Aciertos ≥ {a.criterio:g} % y como máximo {a.max_fn} falsos negativos (un falso negativo informa que no hay agua cuando sí la hay).",
        f"{n} observaciones físicas en orden aleatorio ({secuencia.count('seco')} secas, {secuencia.count('agua')} con agua). "
        f"Tras la marca se esperan {a.estab} s y se toma la primera lectura `[SENSOR]` siguiente; se registra cuánto tardó "
        "AWS en aceptar el reporte posterior.",
        {"UMBRAL_SECO": umb["UMBRAL_SECO"], "UMBRAL_AGUA": umb["UMBRAL_AGUA"], "Fuente de umbrales": umb["archivo"],
         "Estabilización (s)": a.estab, "Semilla de la secuencia": semilla,
         "Referencia física": a.referencia or "(describir con --referencia)"},
        [("N", "n"), ("Hora", "hora"), ("Condición", "condicion"), ("ADC", "adc"), ("agua_detectada", "agua_detectada"),
         ("Resultado", "resultado"), ("AWS aceptó (s)", "aceptado")], filas,
        {"Observaciones": n, "Aciertos": aciertos, "Proporción de aciertos (%)": round(pct, 1),
         "Falsos positivos": cuenta["FP"], "Falsos negativos": cuenta["FN"]},
        cumple, resultado,
        "La referencia física la establece el operador. El lote debe ser distinto del usado para calibrar los umbrales.")


# ---------------------------------------------------------------- RNF 5 / RNF 6
def ensayo_recuperacion(mon, inf, a, tipo):
    nube = Nube(a)
    filas = []
    for rep in range(1, a.repeticiones + 1):
        print(f"\n=== Repetición {rep}/{a.repeticiones} ({tipo})")
        st = preparar(mon)
        P, Q = st["reported"], opuesta(st["reported"])
        fila = {"rep": rep, "inicial": P, "orden": Q, "incidencia": ""}
        if tipo == "wifi":
            t_off = mon.enviar("wifi_off", ("wifi_off",))
            if not mon.esperar(r"\[ENSAYO\] wifi cortado", t_off, 5):
                raise ErrorEnsayo("El firmware no confirmó 'wifi cortado'. ¿Es el entorno tendedero_ensayo actualizado?")
            d = mon.esperar(r"\[MQTT\] Desconectado", t_off, 60)
            fila["deteccion"] = round(d[0] - t_off, 2) if d else None
        elif a.modo == "rts":
            t_off = mon.marca("power_off")
            mon.reset(True)
            time.sleep(2)
            if mon.entre(t_off + 1, time.time()):
                mon.reset(False)
                raise ErrorEnsayo("El ESP32 sigue enviando datos con RTS activo: la placa no tiene autoreset por RTS. "
                                  "Use --modo manual.")
            fila["deteccion"] = None
        else:
            input("Desconecte la alimentación del ESP32 y pulse Enter...")
            t_off = mon.marca("power_off")
            fila["deteccion"] = None
        pendiente = nube.ordenar(Q, mon)
        sd = pendiente["doc"].get("state", {})
        fila["desired_durante"] = sd.get("desired", {}).get("cubierta")
        fila["reported_durante"] = sd.get("reported", {}).get("cubierta")
        json_ruta = inf.carpeta / f"rnf-0{5 if tipo == 'reinicio' else 6}-rep{rep}-pendiente-{inf.sesion}.json"
        json_ruta.write_text(json.dumps(pendiente["doc"], ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(a.fuera)
        if tipo == "wifi":
            t_on = mon.enviar("wifi_on", ("wifi_on",))
        elif a.modo == "rts":
            t_on = mon.marca("power_on")
            mon.reset(False)
        else:
            input("Reconecte la alimentación y pulse Enter en el mismo instante...")
            t_on = mon.marca("power_on")
        rel = lambda x: round(x[0] - t_on, 2) if x else None
        if tipo == "wifi":
            fila["red"] = rel(mon.esperar(r"\[ENSAYO\] wifi conectado", t_on, 60))
        else:
            arr = mon.esperar(RE_ARRANQUE, t_on - 1, 20)
            if not arr and a.modo == "rts":
                raise ErrorEnsayo("No se detectó el arranque tras liberar RTS.")
            fila["red"] = rel(arr)
        limite = a.max_recuperacion + 60
        m = mon.esperar(r"\[MQTT\] Conectado", t_on, limite)
        g = mon.esperar(r"\[SHADOW\] Estado inicial recuperado", t_on, 20) if m else None
        e = mon.esperar(r"\[SERVO\] orden entregada", t_on, 20) if g else None
        if not m:
            fila["incidencia"] = f"sin conexión MQTT en {limite:.0f} s"
            red = mon.entre(t_on, time.time(), r"\[ENSAYO\] (wifi conectado|reloj NTP listo|sin wifi)")
            fila["incidencia"] += "; " + (red[-1][1] if red else "sin mensajes de red del firmware")
            print("  ATENCIÓN:", fila["incidencia"])
        s = mon.esperar(RE_SERVO, e[0] if e else t_on, 20) if e else None
        k = mon.esperar(RE_ACK, s[0], 15) if s else None
        fila.update(mqtt=rel(m), shadow=rel(g), servo=rel(s), aceptado=rel(k))
        fin = estado_shadow(mon)
        fila["convergencia"] = bool(fin and fin["desired"] == fin["reported"] == Q)
        fila["repetida"] = "sí" if mon.entre(t_off, time.time(), r"\[ENSAYO\] orden \w+ publicada") else "no"
        fila["pendiente_ok"] = fila["desired_durante"] == Q and fila["reported_durante"] == P
        filas.append(fila)
        time.sleep(3)
    ok = [x for x in filas if x["convergencia"] and x["pendiente_ok"] and x["repetida"] == "no" and x["aceptado"] is not None]
    tiempos = stats([x["aceptado"] for x in filas])
    superan = sum(1 for x in filas if x["aceptado"] is None or x["aceptado"] > a.max_recuperacion)
    cumple = len(ok) == len(filas) and superan == 0
    if tipo == "wifi":
        clave, titulo, inicio = "rnf-06-reconexion-wifi", "Reconexión de red y sincronización", "`wifi_on`"
        proc = ("El ESP32 permanece encendido; `wifi_off` lo desasocia del punto de acceso. Con el dispositivo fuera de línea, "
                "el PC publica la posición opuesta en `desired` con el certificado del dispositivo y lee el Shadow. "
                "Tras `wifi_on` no se repite la orden.")
        lim = ("La interrupción la provoca el propio ESP32 (desasociación), no un apagado del punto de acceso: el firmware "
               "sabe de inmediato que perdió la red. La orden la publica el PC, no Alexa; el documento es el mismo que usa Lambda.")
    else:
        clave, titulo, inicio = "rnf-05-reinicio", "Recuperación tras reinicio", "la liberación del reset" if a.modo == "rts" else "la reconexión de la alimentación"
        proc = ("El ESP32 se mantiene en reset con la línea RTS (pin EN) mientras el PC deja la orden en `desired`; luego se "
                "libera y arranca desde cero." if a.modo == "rts" else
                "Se desconecta la alimentación, el PC deja la orden en `desired` y se reconecta la alimentación.")
        lim = ("Reinicio por EN: el chip arranca desde cero, pero el servo no pierde alimentación." if a.modo == "rts"
               else "Los instantes de corte y reconexión dependen de la pulsación del operador.")
    resultado = (f"{len(ok)}/{len(filas)} repeticiones con orden pendiente verificada, convergencia y sin repetir la orden; "
                 f"recuperación (desde {inicio} hasta reporte aceptado): promedio {f(tiempos['promedio'])} s, máximo {f(tiempos['maximo'])} s.")
    inf.escribir(
        clave, titulo,
        f"Aplicar la orden pendiente sin repetirla y converger `desired`/`reported` en ≤ {a.max_recuperacion} s desde {inicio}.",
        proc + f" {a.repeticiones} repeticiones, {a.fuera} s adicionales fuera de línea.",
        {"Inicio del cronómetro": inicio, "JSON del Shadow durante la interrupción": f"rnf-0{5 if tipo == 'reinicio' else 6}-repN-pendiente-{inf.sesion}.json"},
        [("Rep.", "rep"), ("Inicial", "inicial"), ("Orden", "orden"), ("desired/reported durante", "durante"),
         ("Red/arranque (s)", "red"), ("MQTT (s)", "mqtt"), ("Shadow (s)", "shadow"), ("Posición (s)", "servo"),
         ("Aceptado (s)", "aceptado"), ("¿Repetida?", "repetida"), ("¿Converge?", "conv"), ("Incidencia", "incidencia")],
        [{**x, "durante": f"{x['desired_durante']}/{x['reported_durante']}", "conv": "sí" if x["convergencia"] else "no"} for x in filas],
        {"Repeticiones": len(filas), "Correctas": len(ok), "Recuperación promedio (s)": tiempos["promedio"],
         "Recuperación máxima (s)": tiempos["maximo"], "Superan el objetivo": superan},
        cumple, resultado, lim)


# ---------------------------------------------------------------- CLI
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--puerto", required=True)
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--resultados", default="resultados")
    p.add_argument("--silencioso", action="store_true", help="no mostrar el log en consola")
    sub = p.add_subparsers(dest="cmd", required=True)

    def aws(sp):
        for n in ("endpoint", "thing", "ca", "cert", "key"):
            sp.add_argument("--" + n)

    def rec(sp):
        sp.add_argument("--repeticiones", type=int, default=3)
        sp.add_argument("--fuera", type=float, default=10, help="segundos extra fuera de línea tras dejar la orden")
        sp.add_argument("--max-recuperacion", type=float, default=30)
        sp.add_argument("--modo", choices=["rts", "manual"], default="rts", help="solo reinicio")

    def resp(sp):
        sp.add_argument("--ordenes", type=int, default=10)
        sp.add_argument("--espera", type=float, default=8)
        sp.add_argument("--objetivo", type=float, default=3.0)

    def est(sp):
        sp.add_argument("--minutos", type=float, default=15)
        sp.add_argument("--periodo", type=float, default=30, help="segundos entre acciones (orden/consulta alternas)")
        sp.add_argument("--hueco", type=float, default=5)
        sp.add_argument("--max-sin-reporte", type=float, default=15)
        sp.add_argument("--max-intervalo", type=float, default=6.0, help="objetivo RNF 4 para el respaldo periódico")

    resp(sub.add_parser("respuesta"))
    est(sub.add_parser("estabilidad"))
    fr = sub.add_parser("frecuencia")
    est(fr)
    fr.set_defaults(minutos=2)
    s = sub.add_parser("sensor")
    s.add_argument("--observaciones", type=int, default=20)
    s.add_argument("--estab", type=float, default=3)
    s.add_argument("--criterio", type=float, default=95)
    s.add_argument("--max-fn", type=int, default=0)
    s.add_argument("--semilla", type=int)
    s.add_argument("--referencia", help="descripción del método físico (p. ej. 'gotas con pipeta, secado con papel')")
    for nombre in ("wifi", "reinicio"):
        sp = sub.add_parser(nombre)
        aws(sp)
        rec(sp)
    t = sub.add_parser("todo")
    aws(t)
    rec(t)
    resp(t)
    est(t)
    a = p.parse_args()

    carpeta = Path(a.resultados)
    carpeta.mkdir(parents=True, exist_ok=True)
    import shutil
    libre = shutil.disk_usage(carpeta).free / 2**20
    if libre < 200:
        raise SystemExit(f"Solo quedan {libre:.0f} MB libres en el disco. Libere espacio (≥ 200 MB) antes de ensayar.")
    sesion = datetime.now().strftime("%Y%m%d-%H%M%S")
    mon = Monitor(a.puerto, a.baud, carpeta / f"log-{sesion}.csv", eco=not a.silencioso)
    inf = Informe(carpeta, sesion, a.puerto)
    try:
        if a.cmd in ("respuesta", "todo"):
            ensayo_respuesta(mon, inf, a)
        if a.cmd in ("estabilidad", "todo"):
            ensayo_estabilidad(mon, inf, a)
        if a.cmd == "frecuencia":
            ensayo_estabilidad(mon, inf, a, con_ordenes=False)
        if a.cmd == "sensor":
            ensayo_sensor(mon, inf, a)
        if a.cmd in ("wifi", "todo"):
            ensayo_recuperacion(mon, inf, a, "wifi")
        if a.cmd in ("reinicio", "todo"):
            ensayo_recuperacion(mon, inf, a, "reinicio")
    except ErrorEnsayo as e:
        mon.log("ensayo", f"INTERRUMPIDO: {e}")
        raise SystemExit(f"\nEnsayo interrumpido: {e}\nEl log quedó en {carpeta / f'log-{sesion}.csv'}")
    except KeyboardInterrupt:
        mon.log("ensayo", "INTERRUMPIDO por el operador")
        raise SystemExit("\nInterrumpido por el operador.")
    finally:
        if mon.rts:
            mon.reset(False)
    print(f"\nTabla final: {carpeta / 'resumen.md'}")


if __name__ == "__main__":
    main()
