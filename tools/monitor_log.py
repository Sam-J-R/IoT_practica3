import sys
import serial

puerto = sys.argv[1]
baudrate = 115200  # Ajustar según platformio.ini

with serial.Serial(puerto, baudrate, timeout=1) as ser:
    try:
        while True:
            linea = ser.readline().decode("utf-8", errors="replace").strip()
            if linea:
                print(linea)
    except KeyboardInterrupt:
        print("\nMonitor cerrado.")