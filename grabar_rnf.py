#!/usr/bin/env python3
# pip install pyserial
"""Graba el monitor serie del ESP32 y marcas manuales en un CSV (fuente, epoch, hora, dato).

No se conecta a AWS: la política del certificado solo autoriza el clientId del propio
dispositivo, así que un segundo cliente con otro ID es rechazado, y uno con el mismo ID
desconectaría al ESP32. La confirmación de AWS se toma de la línea serie
"[SHADOW] reported aceptado", que el firmware imprime al recibir update/accepted.

Con el firmware de ensayo (entorno tendedero_ensayo) estas palabras se envían al ESP32:
  abrir | cerrar  -> publica desired.cubierta (se registra la marca 'envio' y 'orden')
  estado          -> pide el Shadow y lo imprime (se registra la marca 'consulta')
Cualquier otra palabra se guarda solo como marca: est_ini, est_fin, final, seco, agua,
wifi_off, wifi_on, power_off, power_on...

Uso:  python grabar_rnf.py --puerto COM3 --salida rnf-02.csv
"""
import argparse
import csv
import threading
import time
from datetime import datetime

import serial

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--puerto", required=True)  # ej. COM3 (cerrar antes el monitor de PlatformIO)
ap.add_argument("--baud", type=int, default=115200)
ap.add_argument("--salida", default="rnf-eventos.csv")
a = ap.parse_args()

COMANDOS = {"abrir": ("envio", "orden"), "cerrar": ("envio", "orden"), "estado": ("consulta",)}

lock = threading.Lock()
f = open(a.salida, "a", newline="", encoding="utf-8")
w = csv.writer(f)


def log(fuente, dato):
    t = time.time()
    with lock:
        w.writerow([fuente, f"{t:.3f}", datetime.fromtimestamp(t).isoformat(timespec="milliseconds"), dato])
        f.flush()
    print(f"[{fuente}] {dato}")


# DTR/RTS en falso: abrir el puerto no reinicia el ESP32.
s = serial.Serial()
s.port, s.baudrate, s.timeout = a.puerto, a.baud, 1
s.dtr = False
s.rts = False
try:
    s.open()
except Exception as e:
    raise SystemExit(f"No se pudo abrir {a.puerto}: {e}. ¿Está abierto otro monitor serie?")
log("serie_estado", f"puerto {a.puerto} abierto")


def hilo_serie():
    try:
        while True:
            linea = s.readline().decode(errors="replace").strip()
            if linea:
                log("serie", linea)
    except Exception as e:
        log("serie_estado", f"ERROR serie: {e}")


threading.Thread(target=hilo_serie, daemon=True).start()

print(__doc__.split("Uso:")[0])
print("Escribe un comando o una marca y Enter. Ctrl+C para salir.")
try:
    while True:
        m = input().strip().lower()
        if not m:
            continue
        if m in COMANDOS:
            # La marca se registra justo antes de escribir en el puerto.
            for marca in COMANDOS[m]:
                log("marca", marca)
            with lock:
                s.write((m + "\n").encode())
        else:
            log("marca", m)
except (KeyboardInterrupt, EOFError):
    pass
finally:
    s.close()
    f.close()
