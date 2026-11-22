"""Imprime el puerto COM del ESP32 (chip USB-serie CP210x, CH340, CH9102 o FTDI).

Si hay varios candidatos o ninguno, imprime NINGUNO y la lista en stderr.
"""
import sys

from serial.tools import list_ports

CHIPS = ("cp210", "ch340", "ch910", "ch343", "usb-serial", "silicon labs", "ftdi", "uart")
puertos = list(list_ports.comports())
candidatos = [p.device for p in puertos
              if any(c in f"{p.description} {p.manufacturer or ''}".lower() for c in CHIPS)]
if len(candidatos) == 1:
    print(candidatos[0])
else:
    print("NINGUNO")
    for p in puertos:
        print(f"  {p.device}: {p.description} ({p.manufacturer})", file=sys.stderr)
