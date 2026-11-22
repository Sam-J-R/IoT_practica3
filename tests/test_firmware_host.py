"""Compila y ejecuta en la PC las pruebas de la logica del firmware (g++).

No reemplaza la prueba en el ESP32: solo cubre CalibracionSensor.h, SensorAgua.h,
LogicaEdge.h y ConfiguracionOperacion.h, que no dependen del hardware, y
ClienteShadow.cpp con MQTT, cola y cJSON simulados (tests/firmware_host/esp). Se omite si no hay g++ (en Windows: instalar MSYS2
o correrla en GitHub Actions).
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "tests" / "firmware_host"


@unittest.skipUnless(shutil.which("g++"), "g++ no esta instalado")
class FirmwareHostTests(unittest.TestCase):
    def compilar_y_correr(self, nombre, stubs="stubs", fuentes=(), defines=()):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / nombre
            build = subprocess.run(
                ["g++", "-std=gnu++17", "-Wall", "-Wextra", *[f"-D{d}" for d in defines], "-I", str(HOST / stubs),
                 "-I", str(ROOT / "firmware" / "include"), str(HOST / f"{nombre}.cpp"),
                 *[str(ROOT / "firmware" / "src" / f) for f in fuentes], "-o", str(exe)],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, "No compila:\n" + build.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        fallas = [l for l in run.stdout.splitlines() if l.startswith("FALLA")]
        self.assertEqual(fallas, [], "\n" + run.stdout)

    def test_calibracion_e_histeresis(self):
        self.compilar_y_correr("test_calibracion")

    def test_logica_edge_y_modo(self):
        self.compilar_y_correr("test_logica_edge")

    def test_cliente_shadow_real(self):
        """Compila firmware/src/ClienteShadow.cpp con MQTT y cJSON simulados."""
        self.compilar_y_correr("test_cliente_shadow", stubs="esp", fuentes=("ClienteShadow.cpp",))

    def test_cliente_shadow_perfil_de_ensayo(self):
        """El perfil de ensayo agrega ts_dispositivo y luz_simulada; produccion no."""
        self.compilar_y_correr("test_cliente_shadow", stubs="esp", fuentes=("ClienteShadow.cpp",),
                               defines=("MODO_ENSAYO_RNF",))
