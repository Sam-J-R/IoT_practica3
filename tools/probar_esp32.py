#!/usr/bin/env python3
# pip install pyserial          (boto3 solo para la prueba "reconexion")
"""Pruebas automatizadas del firmware P4 en el ESP32, por el monitor serie.

Requiere el perfil de ensayo cargado:
    pio run -d firmware -e tendedero_ensayo -t upload
y ningún otro monitor serie abierto.

Pruebas (se eligen por nombre; "todo" corre las que no necesitan operador):
  arranque      Reinicia el ESP32 y espera umbrales, Shadow recuperado y primer reporte.
  ordenes       Alterna resguardar/exponer N veces y mide orden -> delta -> servo -> reporte.
  frecuencia    Observa los reportes periódicos durante --minutos (respaldo de 60 s).
  persistencia  Reinicia y comprueba que los umbrales guardados se conservan.
  calibracion   GUIADA: seco, mojado y repetir seco (reproduce el defecto 1 si sigue).
  sensor        GUIADA: el operador pone el sensor seco/con agua; compara con agua=0/1.
  reconexion    Corta el WiFi, deja una orden en el Shadow y lo restablece. Con
                --thing y credenciales de AWS la orden la deja boto3; sin ellas
                es guiada (la orden se da por Alexa o la consola de AWS IoT).
  edge          GUIADA: regla R1 (agua en automático -> resguardar), rechazo de
                "exponer" con agua y modo manual. Mide agua -> servo (RNF Edge).
  luz           GUIADA: regla R5 con el LDR (tapar -> resguardar la ropa), rechazo
                de exponer de noche y luz para recoger la ropa por voz. Mide
                oscuridad -> servo (con el LDR real incluye 5 min de confirmación).
                Con --ldr-simulado no hace falta el LDR: el script envía
                ldr_oscuro / ldr_claro en lugar de pedir que lo tapen.
  sin_conexion  GUIADA: R1 con el WiFi cortado y, al volver, que el desired viejo
                no exponga la ropa (RNF operación sin conexión).
  led           Enciende la luz para recoger la ropa y espera el apagado automático
                (10 min): mide el tiempo, que el origen sea edge y que el reporte
                llegue al Shadow. Con --thing y credenciales de AWS lee además el
                Shadow. Con frecuencia, --con-led hace lo mismo sin sumar tiempo.
  r3            Corta el WiFi del ESP32 (como desenchufarlo, para la Nube) y espera
                la alerta "sin_reporte" del supervisor (regla R3). Con --thing y
                credenciales de AWS la busca sola en DynamoDB; sin ellas es guiada
                (avisan con Enter cuando la ven en la consola). Al final vuelve el
                WiFi y comprueba que el ESP32 reporta otra vez.
  todo          arranque + ordenes + persistencia + frecuencia.

Cada corrida deja en resultados_p4/<fecha-hora>/:
  log.csv     todas las líneas (fuente, epoch, hora, dato): sirve para
              tools/medir_intervalos.py y tools/medir_almacenamiento.py
  resumen.md  tabla PASA / FALLA con los tiempos medidos

Ejemplos:
  python tools/probar_esp32.py --puerto COM3 todo
  python tools/probar_esp32.py --puerto COM3 todo --minutos 15 --con-led
  python tools/probar_esp32.py --puerto /dev/ttyUSB0 calibracion
  python tools/probar_esp32.py --puerto COM3 edge sin_conexion luz
  python tools/probar_esp32.py --puerto COM3 reconexion --thing tendedero-inteligente
"""
import argparse
import csv
import json
import re
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

RE = {
    "umbrales": r"\[CALIBRACION\] umbral_seco=(\d+) umbral_agua=(\d+)",
    "recuperado": r"\[SHADOW\] Estado inicial recuperado",
    "aceptado": r"\[SHADOW\] reported aceptado",
    "rechazado": r"\[SHADOW\] reported rechazado",
    "orden_pub": r"\[ENSAYO\] orden (exponer|resguardar) publicada",
    "orden_no": r"\[ENSAYO\] orden (exponer|resguardar) NO publicada",
    "delta": r"\[SHADOW\] delta recibido destino=(\S+)",
    "servo": r"\[SERVO\] Posicion estimada",
    "pedido_pub": r"\[ENSAYO\] pedido calibrar_(seco|mojado) publicado",
    "calibrado": r"\[CALIBRACION\] condicion=(seco|mojado) lectura=(\d+) (aplicada|rechazada)"
                 r" umbral_seco=(\d+) umbral_agua=(\d+)",
    "caducado": r"\[CALIBRACION\] pedido caducado",
    "sensor": r"\[SENSOR\] ms=\d+ raw=(-?\d+) agua=(-?\d+)",
    "wifi_cortado": r"\[ENSAYO\] wifi cortado",
    "wifi_ok": r"\[ENSAYO\] wifi conectado",
    "mqtt_off": r"\[MQTT\] Desconectado",
    "solo_adc": r"\[P4\] Solo ADC",
    # Practica 4: modo de operacion y logica del Edge.
    "modo_pub": r"\[ENSAYO\] modo (auto|manual) publicado",
    "modo": r"\[OPERACION\] modo=(manual|automatico)",
    "r1": r"\[EDGE\] R1:",
    "rechazo": r"\[EDGE\] Orden de exponer rechazada",
    "edge_pub": r"\[EDGE\] desired\.posicion=(\S+) origen=edge publicado",
    "servo_destino": r"\[SERVO\] destino=(\S+) origen=(\S+)",
    # LDR (regla R5: de noche resguarda) y luz para recoger la ropa.
    "luz": r"\[LUZ\] ms=\d+ raw=(\d+) nivel=(-?\d+) oscuro=(-?\d+)",
    "r5": r"\[EDGE\] R5:",
    "led": r"\[LED\] estado=(encendido|apagado) origen=(\S+)",
    "led_pub": r"\[ENSAYO\] led (on|off) publicado",
    "ldr_sim": r"\[ENSAYO\] ldr (simulado oscuro|simulado claro|real)",
    "led_auto": r"\[EDGE\] LED encendido \d+ min: se apaga solo",
}


class Fallo(Exception):
    pass


class Monitor:
    """Lee el puerto en segundo plano, guarda cada línea en el CSV y permite esperar patrones."""

    def __init__(self, puerto, log_path, eco=True):
        self.puerto, self.eco = puerto, eco
        self.lineas = []  # (epoch, texto)
        self.cv = threading.Condition()
        self.f = open(log_path, "a", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        self.activo = True
        self.hilo = threading.Thread(target=self._leer, daemon=True)
        self.hilo.start()
        self.registrar("serie_estado", "puerto abierto")

    def registrar(self, fuente, dato, t=None):
        t = time.time() if t is None else t
        self.w.writerow([fuente, f"{t:.3f}", datetime.fromtimestamp(t).isoformat(timespec="milliseconds"), dato])
        self.f.flush()
        return t

    def marca(self, texto):
        return self.registrar("marca", texto)

    def _leer(self):
        resto = b""
        while self.activo:
            try:
                bloque = self.puerto.read(256)
            except Exception as exc:  # puerto desconectado
                self.registrar("serie_estado", f"error de lectura: {exc}")
                break
            if not bloque:
                continue
            resto += bloque
            *completas, resto = resto.split(b"\n")
            for cruda in completas:
                texto = cruda.decode("utf-8", "replace").strip()
                if not texto:
                    continue
                t = self.registrar("serie", texto)
                if self.eco and not texto.startswith("[SENSOR]"):
                    print(f"  {datetime.fromtimestamp(t):%H:%M:%S.%f}"[:-3] + f"  {texto}")
                with self.cv:
                    self.lineas.append((t, texto))
                    self.cv.notify_all()

    def enviar(self, comando):
        t = self.marca(f"envio {comando}")
        self.puerto.write((comando + "\n").encode())
        self.puerto.flush()
        return t

    def esperar(self, clave, desde, timeout, grupo=None):
        """Primera línea que cumple RE[clave] con epoch >= desde. Devuelve (epoch, match) o None."""
        patron = re.compile(RE[clave])
        limite = time.time() + timeout
        with self.cv:
            while True:
                for t, texto in self.lineas:
                    if t >= desde:
                        m = patron.search(texto)
                        if m and (grupo is None or m.group(1) == grupo):
                            return t, m
                restante = limite - time.time()
                if restante <= 0:
                    return None
                self.cv.wait(min(restante, 0.2))

    def todas(self, clave, desde, hasta=None):
        patron = re.compile(RE[clave])
        with self.cv:
            return [(t, m) for t, texto in self.lineas
                    if t >= desde and (hasta is None or t <= hasta) and (m := patron.search(texto))]

    def reiniciar_esp32(self):
        """Pulso en EN mediante RTS (como hace el monitor de PlatformIO)."""
        t = self.marca("reinicio")
        try:
            self.puerto.dtr = False
            self.puerto.rts = True
            time.sleep(0.15)
            self.puerto.rts = False
        except Exception as exc:
            raise Fallo(f"No se pudo reiniciar por RTS ({exc}). Presionen EN a mano y repitan.")
        return t

    def cerrar(self):
        self.activo = False
        self.hilo.join(timeout=2)
        self.registrar("serie_estado", "puerto cerrado")
        self.f.close()


class Resultados:
    def __init__(self):
        self.filas = []  # (prueba, verificación, resultado, detalle)

    def agregar(self, prueba, verificacion, ok, detalle=""):
        estado = {True: "PASA", False: "FALLA", None: "INFO"}[ok]
        self.filas.append((prueba, verificacion, estado, detalle))
        print(f"[{estado}] {prueba}: {verificacion} {('- ' + detalle) if detalle else ''}")

    def ok(self):
        return all(f[2] != "FALLA" for f in self.filas)

    def markdown(self):
        out = ["| Prueba | Verificación | Resultado | Detalle |", "| --- | --- | --- | --- |"]
        out += [f"| {p} | {v} | {r} | {d} |" for p, v, r, d in self.filas]
        return "\n".join(out)


def ms(a, b):
    return (b - a) * 1000.0


def resumen_ms(valores):
    v = sorted(valores)
    return f"n={len(v)} media={statistics.mean(v):.0f} ms max={v[-1]:.0f} ms"


# ------------------------------------------------------------------ pruebas
def p_arranque(mon, res, a):
    t0 = mon.reiniciar_esp32()
    u = None
    for _ in range(150):  # hasta 15 s: umbrales (modo normal) o "Solo ADC" (sin credenciales)
        u = mon.esperar("umbrales", t0, 0.1)
        if u:
            break
        if mon.esperar("solo_adc", t0, 0):
            raise Fallo("El firmware arrancó en modo 'Solo ADC': faltan secrets.h o calibracion_local.h válidos")
    res.agregar("arranque", "imprime los umbrales vigentes", bool(u),
                f"seco={u[1].group(1)} agua={u[1].group(2)}" if u else "sin línea [CALIBRACION] umbral_seco=")
    r = mon.esperar("recuperado", t0, a.timeout_conexion)
    res.agregar("arranque", "recupera el Shadow tras conectar", bool(r),
                f"{ms(t0, r[0]) / 1000:.1f} s desde el reinicio" if r else f"no llegó en {a.timeout_conexion} s")
    if r:
        ack = mon.esperar("aceptado", r[0], 15)
        res.agregar("arranque", "AWS acepta el primer reporte", bool(ack),
                    "" if ack else "sin '[SHADOW] reported aceptado' (¿política IoT o atributos?)")
    return u


def p_ordenes(mon, res, a):
    tiempos = {"delta": [], "servo": [], "reporte": []}
    destinos = ["resguardar", "exponer"] * ((a.ordenes + 1) // 2)
    for comando in destinos[:a.ordenes]:
        destino = "resguardado" if comando == "resguardar" else "expuesto"
        t0 = mon.enviar(comando)
        pub = mon.esperar("orden_pub", t0, 3, grupo=comando)
        if not pub:
            res.agregar("ordenes", f"{comando}: publicada", False, "el firmware no tiene MQTT activo")
            continue
        d = mon.esperar("delta", t0, a.timeout_orden, grupo=destino)
        s = mon.esperar("servo", d[0], 5) if d else None
        r = mon.esperar("aceptado", s[0], 10) if s else None
        if d and s and r:
            tiempos["delta"].append(ms(t0, d[0]))
            tiempos["servo"].append(ms(t0, s[0]))
            tiempos["reporte"].append(ms(t0, r[0]))
        else:
            falta = "delta" if not d else ("servo" if not s else "reporte aceptado")
            res.agregar("ordenes", f"{comando}: ciclo completo", False, f"no llegó: {falta}")
        time.sleep(a.pausa)
    if tiempos["reporte"]:
        cumple = max(tiempos["servo"]) <= a.objetivo_orden_ms
        res.agregar("ordenes", f"orden -> servo en posición <= {a.objetivo_orden_ms:.0f} ms", cumple,
                    resumen_ms(tiempos["servo"]))
        res.agregar("ordenes", "orden -> delta recibido", None, resumen_ms(tiempos["delta"]))
        res.agregar("ordenes", "orden -> reporte aceptado", None, resumen_ms(tiempos["reporte"]))
        res.agregar("ordenes", "ciclos completos", len(tiempos["reporte"]) == a.ordenes,
                    f"{len(tiempos['reporte'])} de {a.ordenes}")


def p_frecuencia(mon, res, a, cliente_shadow=None):
    t0 = mon.marca("frecuencia inicio")
    t_led = None
    if a.con_led:
        try:
            t_led = _led(mon, "led_on")
        except Fallo as exc:
            res.agregar("led", "enciende la luz al inicio de la frecuencia", False, str(exc))
    print(f"Observando reportes durante {a.minutos} min (no muevan el sensor)...")
    time.sleep(a.minutos * 60)
    if t_led is not None:
        _evaluar_led_automatico(mon, res, a, t_led, cliente_shadow)
    acks = [t for t, _ in mon.todas("aceptado", t0)]
    caidas = [t for t, _ in mon.todas("mqtt_off", t0)]
    # Un intervalo que contiene una caida de MQTT no mide la frecuencia de reporte:
    # mide la reconexion (otro RNF). Se informa aparte.
    normales, con_caida = [], []
    for x, b in zip(acks, acks[1:]):
        (con_caida if any(x < c < b for c in caidas) else normales).append(b - x)
    if len(normales) < 2:
        res.agregar("frecuencia", "reportes periódicos", False, f"solo {len(acks)} reportes aceptados")
        return
    maximo = max(normales)
    res.agregar("frecuencia", f"intervalo máximo <= {a.objetivo_intervalo_s:.0f} s (con conexión)",
                maximo <= a.objetivo_intervalo_s,
                f"n={len(normales)} media={statistics.mean(normales):.1f} s max={maximo:.1f} s")
    if con_caida:
        res.agregar("frecuencia", "huecos por caída de MQTT", None,
                    f"{len(con_caida)} caída(s), hueco máximo {max(con_caida):.1f} s; R3 alerta desde 300 s")
    rechazos = mon.todas("rechazado", t0)
    res.agregar("frecuencia", "sin reportes rechazados", not rechazos, f"{len(rechazos)} rechazados")


def p_persistencia(mon, res, a):
    t_antes = time.time() - 3600
    previos = mon.todas("umbrales", t_antes) + mon.todas("calibrado", t_antes)
    t0 = mon.reiniciar_esp32()
    u = mon.esperar("umbrales", t0, 15)
    if not u:
        res.agregar("persistencia", "umbrales tras reinicio", False, "sin línea de umbrales")
        return
    actual = (u[1].group(1), u[1].group(2))
    if previos:
        _, m = previos[-1]
        esperado = (m.group(1), m.group(2)) if m.re.pattern == RE["umbrales"] else (m.group(4), m.group(5))
        res.agregar("persistencia", "conserva los umbrales tras reiniciar", actual == esperado,
                    f"antes={esperado} después={actual}")
    else:
        res.agregar("persistencia", "umbrales tras reinicio", None, f"{actual} (sin valor previo para comparar)")
    rec = mon.esperar("recuperado", t0, a.timeout_conexion)
    repetido = mon.todas("calibrado", t0)
    res.agregar("persistencia", "no repite una calibración ya atendida", not repetido,
                f"{len(repetido)} calibraciones tras el reinicio" if repetido else "")
    if not rec:
        res.agregar("persistencia", "reconecta tras reiniciar", False, f"no llegó en {a.timeout_conexion} s")


def _calibrar(mon, condicion, timeout):
    t0 = mon.enviar(f"calibrar_{condicion}")
    if not mon.esperar("pedido_pub", t0, 3, grupo=condicion):
        return t0, "no publicado", None, None
    c = mon.esperar("calibrado", t0, timeout, grupo=condicion)
    if c:
        return t0, c[1].group(3), c[1], c[0]
    if mon.esperar("caducado", t0, 0.1):
        return t0, "caducada", None, None
    return t0, "sin respuesta", None, None


def p_calibracion(mon, res, a, preguntar=input):
    pasos = [("seco", "Dejen el sensor SECO y presionen Enter"),
             ("mojado", "MOJEN la superficie del sensor y presionen Enter"),
             ("seco", "SEQUEN el sensor y presionen Enter"),
             ("seco", "Sin tocar nada, presionen Enter: se repite 'seco' (prueba del defecto 1)")]
    for i, (condicion, aviso) in enumerate(pasos, 1):
        preguntar(f"\n[{i}/{len(pasos)}] {aviso}... ")
        t0, resultado, m, t1 = _calibrar(mon, condicion, a.timeout_calibracion)
        detalle = (f"lectura={m.group(2)} umbrales={m.group(4)}/{m.group(5)} "
                   f"({ms(t0, t1) / 1000:.1f} s)" if m else "")
        if i == 4:
            res.agregar("calibracion", "repetir la misma condición llega al ESP32",
                        resultado in ("aplicada", "rechazada"),
                        detalle if m else f"{resultado}: DEFECTO 1 reproducido (delta sin 'condicion')")
        else:
            res.agregar("calibracion", f"calibrar {condicion}", resultado == "aplicada", resultado + " " + detalle)
        if m:
            seco, agua = int(m.group(4)), int(m.group(5))
            if agua < seco:
                res.agregar("calibracion", "conserva el sentido del sensor (agua sube la lectura)", False,
                            f"umbral_agua={agua} < umbral_seco={seco}: DEFECTO 2, el sensor quedó invertido")
        time.sleep(min(a.pausa, 1.0))


def p_sensor(mon, res, a, preguntar=input):
    aciertos, total = 0, 0
    for i in range(a.observaciones):
        esperado = i % 2  # alterna seco / agua
        preguntar(f"\n[{i + 1}/{a.observaciones}] Pongan el sensor {'CON AGUA' if esperado else 'SECO'}, "
                  f"esperen 3 s y presionen Enter... ")
        t0 = time.time()
        lec = mon.esperar("sensor", t0, 3)
        if not lec:
            res.agregar("sensor", f"observación {i + 1}", False, "sin lectura")
            continue
        raw, agua = int(lec[1].group(1)), int(lec[1].group(2))
        mon.marca(f"observacion {i + 1} esperado={esperado} raw={raw} agua={agua}")
        total += 1
        aciertos += agua == esperado
    if total:
        error = 100.0 * (total - aciertos) / total
        res.agregar("sensor", f"error de clasificación <= {a.objetivo_error_sensor:.0f} %",
                    error <= a.objetivo_error_sensor, f"{aciertos}/{total} correctas ({error:.1f} % error)")


def _cliente_aws(a):
    """Cliente iot-data de boto3, o None si no hay boto3 o credenciales de AWS."""
    try:
        import boto3  # solo esta prueba usa AWS
        sesion = boto3.Session(region_name=a.region)
        if sesion.get_credentials() is None:
            return None
        return sesion.client("iot-data")
    except Exception:  # boto3 ausente o configuración inválida
        return None


def p_reconexion(mon, res, a, cliente_shadow=None, preguntar=input):
    """Orden pendiente mientras el ESP32 está sin red; al volver debe aplicarla.

    Con credenciales de AWS (aws configure) y --thing, la orden la deja boto3.
    Sin ellas, la prueba pasa a ser guiada: la orden se da por Alexa o desde la
    consola de AWS IoT (Device Shadow) mientras el WiFi del ESP32 está cortado.
    """
    if cliente_shadow is None and a.thing:
        cliente_shadow = _cliente_aws(a)
    manual = cliente_shadow is None
    if manual:
        res.agregar("reconexion", "modo de la prueba", None,
                    "guiada: sin credenciales de AWS o sin --thing, la orden se da por Alexa o la consola")
    for intento in range(a.repeticiones):
        destino = "resguardado" if intento % 2 == 0 else "expuesto"
        # Dejar el brazo en la posición contraria para que la orden pendiente lo mueva.
        previa = "exponer" if destino == "resguardado" else "resguardar"
        t0 = mon.enviar(previa)
        mon.esperar("servo", t0, a.timeout_orden)
        time.sleep(a.pausa)

        t0 = mon.enviar("wifi_off")
        if not mon.esperar("wifi_cortado", t0, 5):
            res.agregar("reconexion", "corta el WiFi", False, "el firmware no respondió a wifi_off")
            return
        time.sleep(a.espera_corte)
        if manual:
            frase = "resguarda el tendedero" if destino == "resguardado" else "expón el tendedero"
            preguntar(f"\n[intento {intento + 1}] El ESP32 está SIN red. Díganle a Alexa «{frase}» "
                      f"(o en la consola de AWS IoT, Device Shadow: desired.posicion = \"{destino}\"). "
                      f"Cuando Alexa confirme, presionen Enter... ")
        else:
            try:
                cliente_shadow.update_thing_shadow(
                    thingName=a.thing,
                    payload=json.dumps({"state": {"desired": {"posicion": destino}}}).encode())
            except Exception as exc:  # credenciales vencidas, Thing inexistente, sin red...
                raise Fallo(f"AWS rechazó la orden ({type(exc).__name__}: {exc}). Revisen 'aws configure' "
                            "y --thing, o ejecuten la prueba sin --thing para hacerla guiada")
        mon.marca(f"orden pendiente {destino}")
        time.sleep(a.segundos_sin_red)
        t1 = mon.enviar("wifi_on")
        r = mon.esperar("recuperado", t1, a.timeout_conexion)
        s = mon.esperar("servo", r[0], 5) if r else None
        ok = bool(r and s)
        res.agregar("reconexion", f"intento {intento + 1}: aplica la orden pendiente ({destino})", ok,
                    f"Shadow recuperado en {ms(t1, r[0]) / 1000:.1f} s" if r else "no reconectó")
        if r:
            res.agregar("reconexion", f"intento {intento + 1}: reconexión <= {a.objetivo_reconexion_s:.0f} s",
                        ms(t1, r[0]) / 1000 <= a.objetivo_reconexion_s, f"{ms(t1, r[0]) / 1000:.1f} s")
        time.sleep(a.pausa)
    res.agregar("reconexion", "nota", None,
                "wifi_off desasocia al ESP32; repitan al menos una vez apagando el punto de acceso real")


def _modo(mon, modo, timeout=8.0):
    """Publica desired.modo. Devuelve la línea [OPERACION] o None si ya estaba en ese modo."""
    t0 = mon.enviar(modo)
    if not mon.esperar("modo_pub", t0, 3, grupo=modo):
        raise Fallo("el firmware no tiene MQTT activo (¿perfil tendedero_ensayo y WiFi?)")
    return mon.esperar("modo", t0, timeout, grupo="automatico" if modo == "auto" else "manual")


def _esperar_agua(mon, desde, timeout):
    """Primera lectura con agua=1 desde 'desde'. Devuelve su epoch o None."""
    limite = time.time() + timeout
    while time.time() < limite:
        for t, m in mon.todas("sensor", desde):
            if m.group(2) == "1":
                return t
        time.sleep(0.1)
    return None


def _preparar_expuesto(mon, res, prueba, a):
    _modo(mon, "auto")
    t0 = mon.enviar("exponer")
    if not mon.esperar("orden_pub", t0, 3, grupo="exponer"):
        raise Fallo("el firmware no tiene MQTT activo")
    # Si ya estaba expuesto no hay movimiento: basta con que no lo rechace.
    rechazo = mon.esperar("rechazo", t0, 3)
    res.agregar(prueba, "automático + sensor seco: exponer se acepta", not rechazo,
                "rechazada: el sensor no está seco (agua=1)" if rechazo else "")
    time.sleep(1.5)


def p_edge(mon, res, a, preguntar=input):
    preguntar("\n[1/4] Dejen el sensor SECO y presionen Enter... ")
    _preparar_expuesto(mon, res, "edge", a)

    preguntar("\n[2/4] MOJEN el sensor y presionen Enter enseguida... ")
    desde = time.time() - 1
    t_agua = _esperar_agua(mon, desde, 15)
    if not t_agua:
        raise Fallo("el sensor no llegó a agua=1 en 15 s (¿calibración?)")
    r1 = mon.esperar("r1", t_agua - 0.5, 5)
    s = mon.esperar("servo", r1[0], 5) if r1 else None
    pub = mon.esperar("edge_pub", r1[0], 10) if r1 else None
    res.agregar("edge", "R1: con agua en automático resguarda", bool(r1 and s),
                f"agua -> R1 {ms(t_agua, r1[0]):.0f} ms" if r1 else "sin línea [EDGE] R1")
    if s:
        res.agregar("edge", f"agua detectada -> servo resguardado <= {a.objetivo_edge_ms:.0f} ms",
                    ms(t_agua, s[0]) <= a.objetivo_edge_ms, f"{ms(t_agua, s[0]):.0f} ms")
    res.agregar("edge", "R1 escribe desired.posicion con origen edge", bool(pub),
                "" if pub else "sin '[EDGE] desired.posicion=... publicado'")

    t0 = mon.enviar("exponer")
    rechazo = mon.esperar("rechazo", t0, a.timeout_orden)
    time.sleep(2)
    salio = [m for _, m in mon.todas("servo_destino", t0) if m.group(1) == "expuesto"]
    res.agregar("edge", "con agua en automático, 'exponer' por voz se rechaza", bool(rechazo) and not salio,
                "el brazo se expuso" if salio else ("" if rechazo else "sin línea de rechazo"))

    preguntar("\n[3/4] Mantengan el sensor MOJADO y presionen Enter (se pasa a manual)... ")
    m = _modo(mon, "manual")
    res.agregar("edge", "el modo cambia a manual por el Shadow", bool(m), "" if m else "sin '[OPERACION] modo=manual'")
    t0 = mon.enviar("exponer")
    s = mon.esperar("servo_destino", t0, a.timeout_orden, grupo="expuesto")
    res.agregar("edge", "en manual, 'exponer' se cumple aunque haya agua", bool(s),
                f"origen={s[1].group(2)}" if s else "el brazo no se movió")
    time.sleep(1.5)
    mon.enviar("resguardar")
    time.sleep(1.5)

    preguntar("\n[4/4] SEQUEN el sensor y presionen Enter (se vuelve a automático)... ")
    _modo(mon, "auto")


def p_sin_conexion(mon, res, a, preguntar=input):
    preguntar("\n[1/3] Dejen el sensor SECO y presionen Enter... ")
    _preparar_expuesto(mon, res, "sin_conexion", a)
    t0 = mon.enviar("wifi_off")
    if not mon.esperar("wifi_cortado", t0, 3):
        raise Fallo("el firmware no aceptó wifi_off")
    mon.esperar("mqtt_off", t0, 10)

    preguntar("\n[2/3] MOJEN el sensor y presionen Enter (sigue sin WiFi)... ")
    t_agua = _esperar_agua(mon, time.time() - 1, 15)
    r1 = mon.esperar("r1", t_agua - 0.5, 5) if t_agua else None
    s = mon.esperar("servo", r1[0], 5) if r1 else None
    res.agregar("sin_conexion", "R1 resguarda sin conexión", bool(r1 and s),
                f"agua -> servo {ms(t_agua, s[0]):.0f} ms" if s else "no actuó sin red")
    pub = mon.esperar("edge_pub", t0, 1)
    res.agregar("sin_conexion", "sin conexión no intenta publicar", not pub, "")

    preguntar("\n[3/3] Mantengan el sensor MOJADO y presionen Enter (vuelve el WiFi)... ")
    t1 = mon.enviar("wifi_on")
    rec = mon.esperar("recuperado", t1, a.timeout_conexion)
    pub = mon.esperar("edge_pub", rec[0] - 0.5, 10) if rec else None
    time.sleep(3)
    salio = [m for _, m in mon.todas("servo_destino", t1) if m.group(1) == "expuesto"]
    res.agregar("sin_conexion", "al reconectar escribe la decisión pendiente en desired", bool(pub),
                f"{ms(t1, pub[0]) / 1000:.1f} s tras wifi_on" if pub else "sin '[EDGE] desired... publicado'")
    res.agregar("sin_conexion", "el desired viejo (expuesto) no saca la ropa", not salio,
                "el brazo se expuso al reconectar" if salio else "")
    preguntar("\nSequen el sensor y presionen Enter para terminar... ")


def _esperar_nivel(mon, desde, timeout, oscuro):
    """Primera lectura del LDR que cruza el umbral (nivel <= 350 u >= 650). Devuelve su epoch."""
    limite = time.time() + timeout
    while time.time() < limite:
        for t, m in mon.todas("luz", desde):
            nivel = int(m.group(2))
            if (oscuro and nivel <= 350) or (not oscuro and nivel >= 650):
                return t
        time.sleep(0.1)
    return None


def _led(mon, orden):
    t0 = mon.enviar(orden)
    if not mon.esperar("led_pub", t0, 3, grupo=orden.split("_")[1]):
        raise Fallo("el firmware no publicó la orden del LED (¿MQTT?)")
    return t0


def _leer_shadow_reported(cliente_shadow, thing):
    doc = json.loads(cliente_shadow.get_thing_shadow(thingName=thing)["payload"].read())
    return doc.get("state", {}).get("reported", {})


def _evaluar_led_automatico(mon, res, a, t_orden, cliente_shadow=None):
    """Tras un led_on: apagado automático a los --led-s, con origen edge y reportado al Shadow."""
    enc = mon.esperar("led", t_orden, a.timeout_orden, grupo="encendido")
    if not enc:
        res.agregar("led", "la luz se enciende", False, "sin '[LED] estado=encendido'")
        return
    restante = enc[0] + a.led_s + 30 - time.time()
    auto = mon.esperar("led_auto", enc[0], max(restante, 0))
    if not auto:
        res.agregar("led", f"se apaga sola a los {a.led_s:.0f} s", False,
                    f"sin '[EDGE] LED encendido ... se apaga solo' en {a.led_s + 30:.0f} s")
        return
    dt = auto[0] - enc[0]
    res.agregar("led", f"se apaga sola a los {a.led_s:.0f} s", a.led_s - 1 <= dt <= a.led_s + 5, f"{dt:.1f} s")
    apagado = mon.esperar("led", auto[0] - 0.5, 3, grupo="apagado")
    origen = apagado[1].group(2) if apagado else None
    res.agregar("led", "el apagado lo hace el Edge", origen == "edge", f"origen={origen}")
    ack = mon.esperar("aceptado", auto[0], 15)
    caidas = mon.todas("mqtt_off", enc[0], auto[0] + 15)
    res.agregar("led", "el apagado llega al Shadow (reported aceptado)", bool(ack),
                f"{ms(auto[0], ack[0]):.0f} ms" if ack else
                ("sin conexión: hubo [MQTT] Desconectado" if caidas else "sin '[SHADOW] reported aceptado'"))
    if ack and a.thing:
        cliente = cliente_shadow or _cliente_aws(a)
        if cliente is None or not hasattr(cliente, "get_thing_shadow"):
            res.agregar("led", "Shadow: led=apagado, origen_led=edge", None,
                        "sin credenciales de AWS: confirmar en la consola")
            return
        try:
            rep = _leer_shadow_reported(cliente, a.thing)
        except Exception as exc:
            res.agregar("led", "Shadow: led=apagado, origen_led=edge", False, f"{type(exc).__name__}: {exc}")
            return
        res.agregar("led", "Shadow: led=apagado, origen_led=edge",
                    rep.get("led") == "apagado" and rep.get("origen_led") == "edge",
                    f"led={rep.get('led')} origen_led={rep.get('origen_led')}")
    elif ack:
        res.agregar("led", "Shadow: led=apagado, origen_led=edge", None,
                    "sin --thing: confirmar en la consola (captura)")


def _alertas_sin_reporte(a, desde_epoch):
    """Alertas sin_reporte del Thing en tendedero_historico desde 'desde_epoch' (None sin AWS)."""
    try:
        import boto3
        from boto3.dynamodb.conditions import Key
        sesion = boto3.Session(region_name=a.region)
        if sesion.get_credentials() is None:
            return None
        tabla = sesion.resource("dynamodb").Table(a.tabla_historico)
        desde = datetime.fromtimestamp(desde_epoch, timezone.utc).isoformat(timespec="milliseconds")
        r = tabla.query(KeyConditionExpression=Key("thingName").eq(a.thing)
                        & Key("sk").between(f"alerta#{desde}", "alerta#~"))
        return [i for i in r.get("Items", []) if i.get("alerta") == "sin_reporte"]
    except ImportError:
        return None


def _restaurar_wifi(mon, res, a):
    """Devuelve la red al ESP32 y comprueba que vuelve a reportar. Corre incluso si la
    espera de la alerta falló: si no, el objeto se queda sin red y hay que reiniciarlo."""
    t1 = mon.enviar("wifi_on")
    r = mon.esperar("recuperado", t1, a.timeout_conexion)
    ack = mon.esperar("aceptado", r[0], 15) if r else None
    res.agregar("r3", "al volver la red reporta otra vez", bool(ack),
                f"Shadow recuperado en {ms(t1, r[0]) / 1000:.1f} s" if r else "no reconectó")


def _esperar_alerta_r3(mon, res, a, t0, preguntar):
    limite = a.minutos_r3 * 60
    t_alerta, detalle = None, ""
    try:
        automatica = bool(a.thing) and _alertas_sin_reporte(a, t0) is not None
    except Exception as exc:  # credenciales vencidas, permisos, red de la PC
        raise Fallo(f"DynamoDB rechazó la consulta ({type(exc).__name__}: {exc})")
    if automatica:
        print(f"ESP32 sin red. Buscando la alerta sin_reporte en DynamoDB (hasta {a.minutos_r3:.0f} min)...")
        while time.time() - t0 < limite:
            time.sleep(a.sondeo_s)
            try:
                alertas = _alertas_sin_reporte(a, t0)
            except Exception as exc:  # credenciales, permisos o red de la PC
                raise Fallo(f"DynamoDB rechazó la consulta ({type(exc).__name__}: {exc})")
            if alertas:
                t_alerta = time.time()
                detalle = alertas[0].get("sk", "")
                break
    else:
        res.agregar("r3", "modo de la prueba", None,
                    "guiada: sin --thing o sin credenciales de AWS, la alerta se mira en la consola")
        # Antes de MINUTOS_SIN_REPORTE la alerta no puede ser de este corte: seria una vieja.
        minimo = a.minutos_sin_reporte * 60
        print(f"\nESP32 sin red desde las {datetime.fromtimestamp(t0):%H:%M:%S}. "
              f"La alerta de ESTE corte no puede existir antes de las "
              f"{datetime.fromtimestamp(t0 + minimo):%H:%M:%S} "
              f"({a.minutos_sin_reporte:.0f} min sin lectura); el supervisor corre cada 5 min, "
              f"asi que suele aparecer entre {a.minutos_sin_reporte:.0f} y {a.minutos_r3:.0f} min.")
        print("Solo cuenta una alerta NUEVA: su 'sk' (alerta#<fecha UTC>#sin_reporte) debe ser "
              f"posterior a {datetime.fromtimestamp(t0, timezone.utc):%Y-%m-%dT%H:%M:%S}Z.")
        while True:
            preguntar("\nCuando vean esa alerta nueva en DynamoDB (o 'R3:' en CloudWatch del "
                      "supervisor), presionen Enter... ")
            t_alerta = time.time()
            if t_alerta - t0 >= minimo:
                break
            faltan = minimo - (t_alerta - t0)
            print(f"  Han pasado {(t_alerta - t0) / 60:.1f} min: muy pronto. Una alerta visible ahora "
                  f"es de una desconexion anterior. Faltan {faltan / 60:.1f} min como minimo.")
        detalle = "hora del Enter (aprox.)"
    if t_alerta:
        minutos = (t_alerta - t0) / 60
        res.agregar("r3", f"alerta sin_reporte <= {a.minutos_r3:.0f} min", minutos <= a.minutos_r3,
                    f"{minutos:.1f} min; {detalle}")
    else:
        res.agregar("r3", f"alerta sin_reporte <= {a.minutos_r3:.0f} min", False,
                    f"no apareció en {a.minutos_r3:.0f} min (¿EventBridge del supervisor habilitado?)")


def p_r3(mon, res, a, preguntar=input):
    t0 = mon.enviar("wifi_off")
    if not mon.esperar("wifi_cortado", t0, 5):
        raise Fallo("el firmware no aceptó wifi_off (¿perfil tendedero_ensayo?)")
    try:
        _esperar_alerta_r3(mon, res, a, t0, preguntar)
    finally:
        _restaurar_wifi(mon, res, a)


def p_led(mon, res, a, cliente_shadow=None):
    t0 = _led(mon, "led_on")
    print(f"Luz encendida: esperando el apagado automático ({a.led_s:.0f} s)...")
    _evaluar_led_automatico(mon, res, a, t0, cliente_shadow)


def p_luz(mon, res, a, preguntar=input):
    """R5 (de noche resguarda), rechazo de exponer de noche y luz para recoger la ropa por voz."""
    def paso(texto, comando):
        # Con --ldr-simulado el script cambia la luz por comando; si no, la persona tapa el LDR.
        if a.ldr_simulado:
            if comando:
                mon.enviar(comando)
            time.sleep(1)
        else:
            preguntar(texto)

    # Con el LDR real, la noche se confirma tras 5 min de oscuridad sostenida (config.h).
    objetivo_ms = a.objetivo_luz_ms or (3000.0 if a.ldr_simulado else 310000.0)
    t0 = time.time()
    if a.ldr_simulado:
        t0 = mon.enviar("ldr_claro")
        if not mon.esperar("ldr_sim", t0, 3):
            raise Fallo("el firmware no acepta ldr_claro (¿perfil tendedero_ensayo actualizado?)")
    if not mon.esperar("luz", t0 - 2, 4):
        raise Fallo("no hay líneas [LUZ]: falta luz_local.h con las referencias del LDR "
                    "(o usen --ldr-simulado)")
    paso("\n[1/4] Dejen el LDR con LUZ y presionen Enter (la ropa se expone)... ", None)
    _modo(mon, "auto")
    t0 = mon.enviar("exponer")
    mon.esperar("servo_destino", t0, a.timeout_orden, grupo="expuesto")

    espera = "unos segundos" if a.ldr_simulado else "5 minutos"
    paso(f"\n[2/4] TAPEN el LDR y presionen Enter. Manténganlo tapado unos {espera}... ", "ldr_oscuro")
    t_osc = _esperar_nivel(mon, time.time() - 1, 10, oscuro=True)
    if not t_osc:
        raise Fallo("el nivel del LDR no bajó de 350 (revisen luz_local.h)")
    r5 = mon.esperar("r5", t_osc - 0.5, objetivo_ms / 1000 + 5)
    servo = mon.esperar("servo_destino", t_osc - 0.5, objetivo_ms / 1000 + 5, grupo="resguardado")
    res.agregar("luz", "R5: de noche en automático resguarda la ropa", bool(r5 and servo),
                "" if servo else "el brazo no se movió")
    if servo:
        res.agregar("luz", "R5: el movimiento lo pidió el Edge", servo[1].group(2) == "edge",
                    f"origen={servo[1].group(2)}")
        res.agregar("luz", f"oscuridad -> resguardo <= {objetivo_ms:.0f} ms",
                    ms(t_osc, servo[0]) <= objetivo_ms, f"{ms(t_osc, servo[0]):.0f} ms")
    pub = mon.esperar("edge_pub", t_osc - 0.5, 8, grupo="resguardado")
    res.agregar("luz", "R5 escribe desired.posicion con origen edge", bool(pub), "")

    t0 = mon.enviar("exponer")
    rechazo = mon.esperar("rechazo", t0, a.timeout_orden)
    time.sleep(1.5)
    expuesto = [m for _, m in mon.todas("servo_destino", t0) if m.group(1) == "expuesto"]
    res.agregar("luz", "de noche en automático, exponer por voz se rechaza", bool(rechazo) and not expuesto,
                "el brazo se expuso" if expuesto else ("" if rechazo else "sin línea de rechazo"))

    paso("\n[3/4] Mantengan el LDR TAPADO y presionen Enter (luz para recoger la ropa)... ", None)
    t0 = _led(mon, "led_on")
    m = mon.esperar("led", t0, a.timeout_orden, grupo="encendido")
    res.agregar("luz", "la voz enciende la luz para recoger la ropa", bool(m),
                f"origen={m[1].group(2)}" if m else "el LED no cambió")
    t0 = _led(mon, "led_off")
    m = mon.esperar("led", t0, a.timeout_orden, grupo="apagado")
    res.agregar("luz", "la voz apaga la luz", bool(m), f"origen={m[1].group(2)}" if m else "el LED no cambió")
    res.agregar("luz", "apagado automático de la luz a los 10 min", True,
                "no se mide aquí: dejar la luz encendida y buscar '[EDGE] LED encendido 10 min'")

    paso("\n[4/4] DESTAPEN el LDR y presionen Enter... ", "ldr_claro")
    _esperar_nivel(mon, time.time() - 1, 10, oscuro=False)
    if a.ldr_simulado:
        mon.enviar("ldr_real")
        res.agregar("luz", "LDR simulado: falta repetir con el LDR real", True,
                    "sin histéresis ni confirmación de 5 min")


PRUEBAS = {"arranque": p_arranque, "ordenes": p_ordenes, "frecuencia": p_frecuencia,
           "persistencia": p_persistencia, "calibracion": p_calibracion, "sensor": p_sensor,
           "reconexion": p_reconexion, "edge": p_edge, "sin_conexion": p_sin_conexion,
           "luz": p_luz, "led": p_led, "r3": p_r3}
GUIADAS = ("calibracion", "sensor", "edge", "sin_conexion", "luz", "r3")
TODO = ["arranque", "ordenes", "persistencia", "frecuencia"]


def argumentos(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pruebas", nargs="+", choices=[*PRUEBAS, "todo"])
    ap.add_argument("--puerto", required=True, help="COM3, /dev/ttyUSB0...")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--salida", default=str(RAIZ / "resultados_p4"))
    ap.add_argument("--sin-eco", action="store_true", help="no mostrar el monitor en pantalla")
    ap.add_argument("--ordenes", type=int, default=10)
    ap.add_argument("--pausa", type=float, default=4.0, help="segundos entre órdenes")
    ap.add_argument("--minutos", type=float, default=5.0, help="ventana de la prueba de frecuencia")
    ap.add_argument("--observaciones", type=int, default=20)
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--segundos-sin-red", type=float, default=20.0)
    ap.add_argument("--espera-corte", type=float, default=3.0, help="segundos tras wifi_off antes de dejar la orden")
    ap.add_argument("--thing")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--timeout-conexion", type=float, default=45.0)
    ap.add_argument("--timeout-orden", type=float, default=10.0)
    ap.add_argument("--timeout-calibracion", type=float, default=15.0)
    # Objetivos declarados (RNF). Cámbienlos si el informe declara otros.
    ap.add_argument("--objetivo-orden-ms", type=float, default=6000.0)
    ap.add_argument("--objetivo-intervalo-s", type=float, default=65.0)
    ap.add_argument("--objetivo-reconexion-s", type=float, default=30.0)
    ap.add_argument("--objetivo-error-sensor", type=float, default=5.0)
    # Muestreo de 500 ms + asentamiento del servo de 1000 ms + margen.
    ap.add_argument("--objetivo-edge-ms", type=float, default=2500.0)
    # Muestreo de 500 ms + confirmación del LDR de 3000 ms + margen.
    ap.add_argument("--objetivo-luz-ms", type=float, default=None,
                    help="máximo de oscuridad -> resguardo (por defecto 310000 con el LDR real, 3000 simulado)")
    ap.add_argument("--con-led", action="store_true",
                    help="frecuencia: enciende la luz al inicio y comprueba su apagado automático")
    # Apagado automático de la luz (LED_APAGADO_AUTOMATICO_MS en config.h).
    ap.add_argument("--led-s", type=float, default=600.0)
    # R3: 5 min sin lectura + el supervisor corre cada 5 min + margen.
    ap.add_argument("--minutos-r3", type=float, default=11.0)
    # MINUTOS_SIN_REPORTE de la Lambda del supervisor: antes la alerta no puede ser de este corte.
    ap.add_argument("--minutos-sin-reporte", type=float, default=5.0)
    ap.add_argument("--sondeo-s", type=float, default=30.0, help="r3: cada cuánto consultar DynamoDB")
    ap.add_argument("--tabla-historico", default="tendedero_historico")
    ap.add_argument("--ldr-simulado", action="store_true",
                    help="prueba 'luz' sin LDR: usa los comandos ldr_oscuro / ldr_claro del firmware")
    return ap.parse_args(argv)


def ejecutar(a, puerto, preguntar=input, cliente_shadow=None):
    carpeta = Path(a.salida) / datetime.now().strftime("%Y%m%d-%H%M%S")
    carpeta.mkdir(parents=True, exist_ok=True)
    mon = Monitor(puerto, carpeta / "log.csv", eco=not a.sin_eco)
    res = Resultados()
    nombres = [n for p in a.pruebas for n in (TODO if p == "todo" else [p])]
    try:
        time.sleep(0.5)
        for nombre in nombres:
            print(f"\n=== {nombre} ===")
            mon.marca(f"prueba {nombre}")
            try:
                if nombre in GUIADAS:
                    PRUEBAS[nombre](mon, res, a, preguntar=preguntar)
                elif nombre == "reconexion":
                    PRUEBAS[nombre](mon, res, a, cliente_shadow=cliente_shadow, preguntar=preguntar)
                elif nombre in ("led", "frecuencia"):
                    PRUEBAS[nombre](mon, res, a, cliente_shadow=cliente_shadow)
                else:
                    PRUEBAS[nombre](mon, res, a)
            except Fallo as exc:
                res.agregar(nombre, "prueba interrumpida", False, str(exc))
                if nombre == "arranque":
                    break
    finally:
        mon.cerrar()
    texto = (f"# Pruebas del ESP32 — {datetime.now():%Y-%m-%d %H:%M}\n\n"
             f"Puerto: `{a.puerto}` · Pruebas: {', '.join(nombres)} · Log: `log.csv`\n\n{res.markdown()}\n")
    (carpeta / "resumen.md").write_text(texto, encoding="utf-8")
    print(f"\nResultados en {carpeta}")
    return res


def main(argv=None):
    a = argumentos(argv)
    try:
        import serial
    except ImportError:
        sys.exit("Falta pyserial: pip install pyserial")
    puerto = serial.Serial(a.puerto, a.baud, timeout=0.1)
    res = ejecutar(a, puerto)
    puerto.close()
    return 0 if res.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
