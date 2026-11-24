"""Prueba tools/probar_esp32.py contra un ESP32 simulado (sin hardware).

El simulador imprime las mismas líneas que el firmware de ensayo y calcula el
delta del Shadow con shadow_sim, así que la prueba de calibración reproduce el
defecto 1 igual que el ESP32 real: repetir 'seco' no llega.
"""

import json
import queue
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import probar_esp32  # noqa: E402
from shadow_sim import ShadowSimulado  # noqa: E402


def pedido_de(estado):
    p = estado.get("calibracion_solicitada")
    if isinstance(p, dict) and p.get("condicion") in ("seco", "mojado") and p.get("id"):
        return p["condicion"], p["id"]
    return None


class Esp32Simulado:
    """Puerto serie falso: responde a los comandos como el perfil tendedero_ensayo."""

    def __init__(self, invertir_en_seco=None, reporte_s=0.2, relee_shadow=True):
        self.salida = queue.Queue()
        self.shadow = ShadowSimulado()
        self.umbrales = (200, 600)
        self.invertir_en_seco = invertir_en_seco  # lectura "seco" que invierte el sensor
        self.reporte_s = reporte_s
        # True = firmware corregido: si el delta trae el pedido sin 'condicion', pide GET.
        self.relee_shadow = relee_shadow
        self.dtr = self._rts = False
        self.lectura = 0
        # Practica 4: modo, destino del servo y decision del Edge sin publicar.
        # rechaza_voz=False simula un firmware sin la politica voz/automatico.
        self.modo = "automatico"
        self.destino = None
        self.en_linea = True
        self.pendiente = False
        self.rechaza_voz = True
        # Luz automatica: sin LDR por defecto, como el firmware sin luz_local.h.
        self.ldr = False
        self.nivel = 1000
        self.oscuro = -1
        self.cambio_desde = None
        self.led = "apagado"
        self.led_desde = None
        self.led_auto_s = 0.5  # apagado automatico (10 min en el firmware)
        self.confirmacion_s = 0.3
        self.lock = threading.Lock()
        self.vivo = True
        threading.Thread(target=self._latido, daemon=True).start()

    # --- API de pyserial que usa el script
    def read(self, n):
        try:
            return self.salida.get(timeout=0.05)
        except queue.Empty:
            return b""

    def write(self, datos):
        threading.Thread(target=self._comando, args=(datos.decode().strip(),), daemon=True).start()

    def flush(self):
        pass

    @property
    def rts(self):
        return self._rts

    @rts.setter
    def rts(self, valor):
        if self._rts and not valor:  # flanco de liberación de EN = reinicio
            threading.Thread(target=self._arranque, daemon=True).start()
        self._rts = valor

    # --- comportamiento del firmware
    def linea(self, texto):
        self.salida.put((texto + "\n").encode())

    def _arranque(self):
        time.sleep(0.05)
        self.linea("rst:0x1 (POWERON_RESET)")
        self.linea(f"[CALIBRACION] umbral_seco={self.umbrales[0]} umbral_agua={self.umbrales[1]}")
        time.sleep(0.1)
        self.linea("[MQTT] Conectado. Solicitando Shadow")
        self.linea("[SHADOW] Estado inicial recuperado")
        self.linea("[SHADOW] reported aceptado ms=1")

    @property
    def mojado(self):
        return self.lectura >= 600

    def _mover(self, destino, origen):
        if destino == self.destino:
            return False
        self.destino = destino
        self.linea(f"[SERVO] destino={destino} origen={origen} ms=1")
        time.sleep(0.05)
        self.linea("[SERVO] Posicion estimada tras espera ms=1")
        return True

    def _decision_edge(self):
        if self.en_linea:
            self.linea("[EDGE] desired.posicion=resguardado origen=edge publicado")
        else:
            self.pendiente = True

    def _r1(self):
        with self.lock:
            if self.modo == "automatico" and self.mojado and self.destino != "resguardado":
                self.linea("[EDGE] R1: agua detectada en modo automatico, resguardando ms=1")
                self._mover("resguardado", "edge")
                self._decision_edge()

    def _cambiar_led(self, estado, origen):
        if estado == self.led:
            return
        self.led = estado
        self.led_desde = time.time() if estado == "encendido" else None
        self.linea(f"[LED] estado={estado} origen={origen} ms=1")

    def _luz(self):
        if not self.ldr:
            return
        objetivo = self.oscuro
        if self.oscuro < 0:
            self.oscuro = int(self.nivel < 500)
        elif self.oscuro == 0 and self.nivel <= 350:
            objetivo = 1
        elif self.oscuro == 1 and self.nivel >= 650:
            objetivo = 0
        if objetivo != self.oscuro:
            self.cambio_desde = self.cambio_desde or time.time()
            if time.time() - self.cambio_desde >= self.confirmacion_s:
                self.oscuro, self.cambio_desde = objetivo, None
        else:
            self.cambio_desde = None
        self.linea(f"[LUZ] ms=1 raw={self.nivel * 3} nivel={self.nivel} oscuro={self.oscuro}")
        self._r5()

    def _r5(self):
        with self.lock:
            if (self.ldr and self.modo == "automatico" and self.oscuro == 1
                    and self.destino != "resguardado"):
                self.linea("[EDGE] R5: es de noche en modo automatico, resguardando ms=1")
                self._mover("resguardado", "edge")
                self._decision_edge()

    def _latido(self):
        while self.vivo:
            time.sleep(self.reporte_s)
            self.linea(f"[SENSOR] ms=1 raw={self.lectura} agua={int(self.mojado)}")
            self._luz()
            self._r1()
            with self.lock:
                if self.led_desde and time.time() - self.led_desde >= self.led_auto_s:
                    self.linea("[EDGE] LED encendido 10 min: se apaga solo ms=1")
                    self._cambiar_led("apagado", "edge")
            if self.en_linea:
                self.linea("[SHADOW] reported aceptado ms=2")

    def _comando(self, cmd):
        time.sleep(0.02)
        if cmd in ("exponer", "resguardar"):
            destino = "expuesto" if cmd == "exponer" else "resguardado"
            self.linea(f"[ENSAYO] orden {cmd} publicada ms=1")
            time.sleep(0.1)
            self.linea(f"[SHADOW] delta recibido destino={destino} v=3 ms=1")
            time.sleep(0.1)
            with self.lock:
                noche = self.ldr and self.oscuro == 1
                if (self.rechaza_voz and self.modo == "automatico" and (self.mojado or noche)
                        and destino == "expuesto"):
                    motivo = "hay agua" if self.mojado else "es de noche"
                    self.linea(f"[EDGE] Orden de exponer rechazada: {motivo} y el modo es automatico ms=1")
                    self._mover("resguardado", "edge")
                    self._decision_edge()
                else:
                    self._mover(destino, "voz")
            self.linea("[SHADOW] reported aceptado ms=1")
        elif cmd in ("auto", "manual"):
            nuevo = "automatico" if cmd == "auto" else "manual"
            self.linea(f"[ENSAYO] modo {cmd} publicado ms=1")
            time.sleep(0.1)
            if nuevo != self.modo:
                self.modo = nuevo
                self.linea(f"[OPERACION] modo={nuevo} ms=1")
                self._r1()
                self._r5()
        elif cmd in ("ldr_oscuro", "ldr_claro", "ldr_real"):
            self.linea(f"[ENSAYO] ldr {'real' if cmd == 'ldr_real' else 'simulado ' + cmd[4:]} ms=1")
            if cmd != "ldr_real":
                self.ldr = True
                self.nivel = 0 if cmd == "ldr_oscuro" else 1000
                # Como el firmware: R5 actua en la siguiente lectura, no en el comando.
                self.oscuro = int(cmd == "ldr_oscuro")
                self.cambio_desde = None
        elif cmd in ("led_on", "led_off"):
            estado = "encendido" if cmd == "led_on" else "apagado"
            self.linea(f"[ENSAYO] led {cmd[4:]} publicado ms=1")
            time.sleep(0.1)
            with self.lock:
                self._cambiar_led(estado, "voz")  # La luz para recoger la ropa obedece siempre a la voz.
        elif cmd.startswith("calibrar_"):
            condicion = cmd.split("_")[1]
            self.linea(f"[ENSAYO] pedido {cmd} publicado ms=1")
            delta = self.shadow.update({"state": {"desired": {"calibracion_solicitada": {
                "condicion": condicion, "id": int(time.time() * 1000)}}}})
            pedido = pedido_de(delta)
            if not pedido and self.relee_shadow and "calibracion_solicitada" in delta:
                self.linea("[SHADOW] Pedido de calibracion sin condicion en el delta. Solicitando Shadow")
                pedido = pedido_de(self.shadow.documento()["state"]["desired"])
            if not pedido:
                return  # firmware anterior: descarta el delta sin 'condicion'
            if condicion == "seco" and self.invertir_en_seco is not None:
                lectura, seco, agua = self.invertir_en_seco, self.invertir_en_seco + 40, self.invertir_en_seco - 80
            else:
                lectura = 0 if condicion == "seco" else 2400
                seco, agua = (lectura + 200, 600) if condicion == "seco" else (200, 720)
            self.umbrales = (seco, agua)
            self.linea(f"[CALIBRACION] condicion={condicion} lectura={lectura} aplicada "
                       f"umbral_seco={seco} umbral_agua={agua}")
            self.shadow.update({"state": {"reported": {"calibracion_solicitada": {
                "condicion": pedido[0], "id": pedido[1]}}}})
        elif cmd == "wifi_off":
            self.en_linea = False
            self.linea("[ENSAYO] wifi cortado ms=1")
            self.linea("[MQTT] Desconectado")
        elif cmd == "wifi_on":
            time.sleep(0.2)
            self.en_linea = True
            self.linea("[ENSAYO] wifi conectado ip=1.2.3.4 ms=1")
            self.linea("[SHADOW] Estado inicial recuperado")
            if self.pendiente:
                self.pendiente = False
                self.linea("[EDGE] desired.posicion=resguardado origen=edge publicado")
            else:
                self.linea("[SERVO] Posicion estimada tras espera ms=1")


class ShadowAws:
    def __init__(self, reported=None):
        self.pedidos = []
        self.reported = reported or {}

    def get_thing_shadow(self, thingName):
        import io
        return {"payload": io.BytesIO(json.dumps({"state": {"reported": self.reported}}).encode())}

    def update_thing_shadow(self, thingName, payload):
        self.pedidos.append((thingName, json.loads(payload)))


class ProbarEsp32Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def correr(self, pruebas, esp=None, preguntar=None, sin_aws=False, **extra):
        args = ["--puerto", "SIM", "--salida", self.tmp.name, "--sin-eco", "--pausa", "0",
                "--ordenes", "4", "--minutos", "0.02", "--timeout-conexion", "3",
                "--timeout-calibracion", "1", "--segundos-sin-red", "0", "--espera-corte", "0", "--repeticiones", "2",
                *[f"--{k.replace('_', '-')}" + ("" if v is True else f"={v}") for k, v in extra.items()], *pruebas]
        a = probar_esp32.argumentos(args)
        esp = esp or Esp32Simulado()
        aws = None if sin_aws else ShadowAws()
        res = probar_esp32.ejecutar(a, esp, preguntar=preguntar or (lambda _: ""), cliente_shadow=aws)
        esp.vivo = False
        filas = {(p, v): (r, d) for p, v, r, d in res.filas}
        carpeta = next(Path(self.tmp.name).iterdir())
        return res, filas, carpeta, aws

    def test_led_se_apaga_solo_y_llega_al_shadow(self):
        res, filas, _, _ = self.correr(["led"], led_s=0.5)
        self.assertTrue(res.ok(), res.markdown())
        self.assertEqual(filas[("led", "el apagado lo hace el Edge")], ("PASA", "origen=edge"))
        self.assertEqual(filas[("led", "Shadow: led=apagado, origen_led=edge")][0], "INFO")

    def test_led_sin_conexion_no_llega_al_shadow(self):
        esp = Esp32Simulado()
        esp.en_linea = False
        res, filas, _, _ = self.correr(["led"], esp=esp, led_s=0.5)
        self.assertEqual(filas[("led", f"se apaga sola a los 0 s")][0], "PASA")
        self.assertEqual(filas[("led", "el apagado llega al Shadow (reported aceptado)")][0], "FALLA")

    def test_led_lee_el_shadow_con_thing(self):
        a = probar_esp32.argumentos(["--puerto", "SIM", "--salida", self.tmp.name, "--sin-eco",
                                     "--led-s", "0.5", "--thing", "t1", "led"])
        esp = Esp32Simulado()
        aws = ShadowAws(reported={"led": "apagado", "origen_led": "edge"})
        res = probar_esp32.ejecutar(a, esp, preguntar=lambda _: "", cliente_shadow=aws)
        esp.vivo = False
        filas = {(p, v): (r, d) for p, v, r, d in res.filas}
        self.assertEqual(filas[("led", "Shadow: led=apagado, origen_led=edge")][0], "PASA")

    def test_r3_guiada_sin_aws(self):
        res, filas, _, _ = self.correr(["r3"], minutos_r3=1, minutos_sin_reporte=0.002)
        self.assertTrue(res.ok(), res.markdown())
        self.assertEqual(filas[("r3", "modo de la prueba")][0], "INFO")
        self.assertEqual(filas[("r3", "al volver la red reporta otra vez")][0], "PASA")

    def test_r3_busca_la_alerta_en_dynamodb(self):
        respuestas = iter([[], [], [{"sk": "alerta#2026-11-24T16:00:00.000+00:00#sin_reporte",
                                    "alerta": "sin_reporte"}]])
        with unittest.mock.patch.object(probar_esp32, "_alertas_sin_reporte",
                                        side_effect=lambda a, t: next(respuestas, [{"sk": "x"}])):
            res, filas, _, _ = self.correr(["r3"], thing="t1", minutos_r3=1, sondeo_s=0.1)
        self.assertTrue(res.ok(), res.markdown())
        self.assertIn("sin_reporte", filas[("r3", "alerta sin_reporte <= 1 min")][1])

    def test_r3_sin_alerta_falla(self):
        with unittest.mock.patch.object(probar_esp32, "_alertas_sin_reporte", return_value=[]):
            res, filas, _, _ = self.correr(["r3"], thing="t1", minutos_r3=0.01, sondeo_s=0.1)
        self.assertEqual(filas[("r3", "alerta sin_reporte <= 0 min")][0], "FALLA")

    def test_r3_guiada_no_acepta_un_enter_prematuro(self):
        pedidos = []

        def preguntar(texto):
            pedidos.append(texto)
            return ""

        res, filas, _, _ = self.correr(["r3"], preguntar=preguntar, minutos_r3=1,
                                       minutos_sin_reporte=0.02)
        self.assertTrue(res.ok(), res.markdown())
        self.assertGreaterEqual(len(pedidos), 2)  # el primer Enter llego antes del minimo

    def test_r3_devuelve_el_wifi_aunque_dynamodb_falle(self):
        with unittest.mock.patch.object(probar_esp32, "_alertas_sin_reporte",
                                        side_effect=RuntimeError("AccessDenied")):
            res, filas, _, esp = self.correr(["r3"], thing="t1", minutos_r3=1)
        self.assertEqual(filas[("r3", "prueba interrumpida")][0], "FALLA")
        self.assertIn("AccessDenied", filas[("r3", "prueba interrumpida")][1])
        # Lo que importa: el ESP32 no se queda sin red.
        self.assertEqual(filas[("r3", "al volver la red reporta otra vez")][0], "PASA")

    def test_frecuencia_con_led(self):
        res, filas, _, _ = self.correr(["frecuencia"], con_led=True, led_s=0.5)
        self.assertTrue(res.ok(), res.markdown())
        self.assertIn(("led", "el apagado lo hace el Edge"), filas)

    def test_todo_pasa_con_un_firmware_correcto(self):
        res, filas, carpeta, _ = self.correr(["todo"])
        self.assertTrue(res.ok(), res.markdown())
        self.assertEqual(filas[("ordenes", "ciclos completos")][0], "PASA")
        self.assertTrue((carpeta / "log.csv").read_text().count("[SERVO] Posicion estimada") >= 4)
        self.assertIn("| arranque |", (carpeta / "resumen.md").read_text())

    def test_calibracion_pasa_con_el_firmware_corregido(self):
        res, filas, _, _ = self.correr(["calibracion"])
        self.assertTrue(res.ok(), res.markdown())
        self.assertEqual(filas[("calibracion", "repetir la misma condición llega al ESP32")][0], "PASA")

    def test_calibracion_reproduce_el_defecto_1(self):
        res, filas, _, _ = self.correr(["calibracion"], esp=Esp32Simulado(relee_shadow=False))
        self.assertEqual(filas[("calibracion", "calibrar seco")][0], "PASA")
        self.assertEqual(filas[("calibracion", "calibrar mojado")][0], "PASA")
        r, detalle = filas[("calibracion", "repetir la misma condición llega al ESP32")]
        self.assertEqual(r, "FALLA")
        self.assertIn("DEFECTO 1", detalle)

    def test_calibracion_detecta_el_sensor_invertido(self):
        res, filas, _, _ = self.correr(["calibracion"], esp=Esp32Simulado(invertir_en_seco=2600))
        r, detalle = filas[("calibracion", "conserva el sentido del sensor (agua sube la lectura)")]
        self.assertEqual(r, "FALLA")
        self.assertIn("DEFECTO 2", detalle)

    def test_reconexion_deja_la_orden_en_el_shadow(self):
        res, filas, _, aws = self.correr(["reconexion"], thing="tendedero-prueba")
        self.assertEqual(len(aws.pedidos), 2)
        self.assertEqual(aws.pedidos[0][1]["state"]["desired"]["posicion"], "resguardado")
        self.assertEqual(filas[("reconexion", "intento 1: aplica la orden pendiente (resguardado)")][0], "PASA")

    @staticmethod
    def operador(esp):
        """Hace lo que piden las pruebas guiadas: mojar o secar el sensor."""
        def preguntar(texto):
            if "MOJEN" in texto:
                esp.lectura = 2400
            elif "SECO" in texto or "SEQUEN" in texto:
                esp.lectura = 0
            time.sleep(0.5)  # el latido imprime la lectura nueva
            return ""
        return preguntar

    def test_edge_pasa_con_el_firmware_p4(self):
        esp = Esp32Simulado(reporte_s=0.1)
        res, filas, _, _ = self.correr(["edge"], esp=esp, preguntar=self.operador(esp), timeout_orden=2)
        self.assertTrue(res.ok(), res.markdown())
        self.assertEqual(filas[("edge", "R1: con agua en automático resguarda")][0], "PASA")
        self.assertEqual(filas[("edge", "en manual, 'exponer' se cumple aunque haya agua")][1], "origen=voz")
        self.assertEqual(esp.modo, "automatico", "la prueba deja el ESP32 en automatico")

    def test_edge_detecta_que_la_voz_saca_la_ropa_con_lluvia(self):
        esp = Esp32Simulado(reporte_s=0.1)
        esp.rechaza_voz = False
        res, filas, _, _ = self.correr(["edge"], esp=esp, preguntar=self.operador(esp), timeout_orden=1)
        self.assertEqual(filas[("edge", "con agua en automático, 'exponer' por voz se rechaza")][0], "FALLA")

    @staticmethod
    def operador_luz(esp):
        def preguntar(texto):
            if "DESTAPEN" in texto:
                esp.nivel = 950
            elif "TAPEN" in texto:
                esp.nivel = 50
            time.sleep(0.3)
            return ""
        return preguntar

    def test_luz_pasa_con_el_firmware_p4(self):
        esp = Esp32Simulado(reporte_s=0.1)
        esp.ldr = True
        res, filas, _, _ = self.correr(["luz"], esp=esp, preguntar=self.operador_luz(esp), timeout_orden=1)
        self.assertTrue(res.ok(), res.markdown())
        self.assertEqual(filas[("luz", "R5: el movimiento lo pidió el Edge")][1], "origen=edge")
        self.assertEqual(filas[("luz", "la voz enciende la luz para recoger la ropa")][1], "origen=voz")
        self.assertEqual((esp.modo, esp.destino, esp.led), ("automatico", "resguardado", "apagado"))

    def test_luz_detecta_que_la_voz_saca_la_ropa_de_noche(self):
        esp = Esp32Simulado(reporte_s=0.1)
        esp.ldr = True
        esp.rechaza_voz = False  # firmware sin la politica voz/noche
        res, filas, _, _ = self.correr(["luz"], esp=esp, preguntar=self.operador_luz(esp), timeout_orden=1)
        self.assertFalse(res.ok())
        self.assertEqual(filas[("luz", "de noche en automático, exponer por voz se rechaza")][0], "FALLA")

    def test_luz_con_ldr_simulado(self):
        esp = Esp32Simulado(reporte_s=0.1)
        preguntas = []
        res, filas, _, _ = self.correr(["luz"], esp=esp, preguntar=preguntas.append, timeout_orden=1,
                                       ldr_simulado=True)
        self.assertTrue(res.ok(), res.markdown())
        self.assertEqual(preguntas, [], "con --ldr-simulado no se pide tapar el LDR")
        self.assertIn(("luz", "LDR simulado: falta repetir con el LDR real"), filas)

    def test_luz_sin_ldr_se_informa(self):
        res, filas, _, _ = self.correr(["luz"], esp=Esp32Simulado(reporte_s=0.1))
        self.assertFalse(res.ok())
        self.assertIn("luz_local.h", filas[("luz", "prueba interrumpida")][1])

    def test_sin_conexion_pasa_con_el_firmware_p4(self):
        esp = Esp32Simulado(reporte_s=0.1)
        res, filas, _, _ = self.correr(["sin_conexion"], esp=esp, preguntar=self.operador(esp))
        self.assertTrue(res.ok(), res.markdown())
        self.assertEqual(filas[("sin_conexion", "al reconectar escribe la decisión pendiente en desired")][0],
                         "PASA")

    def test_reconexion_sin_credenciales_es_guiada(self):
        preguntas = []
        sin_credenciales = unittest.mock.patch.object(probar_esp32, "_cliente_aws", return_value=None)
        with sin_credenciales:
            res, filas, _, _ = self.correr(["reconexion"], sin_aws=True, preguntar=preguntas.append,
                                           thing="tendedero-inteligente")
        self.assertEqual(len(preguntas), 2, "pide la orden por Alexa en cada intento")
        self.assertIn("Alexa", preguntas[0])
        self.assertEqual(filas[("reconexion", "intento 1: aplica la orden pendiente (resguardado)")][0], "PASA")

    def test_firmware_sin_credenciales_se_informa(self):
        esp = Esp32Simulado()
        esp._arranque = lambda: esp.linea("[P4] Solo ADC. Completar calibracion y secretos locales")
        res, filas, _, _ = self.correr(["arranque"], esp=esp)
        self.assertFalse(res.ok())
        self.assertIn("Solo ADC", filas[("arranque", "prueba interrumpida")][1])


if __name__ == "__main__":
    unittest.main()
