# Stubs para compilar el firmware en la PC

Reemplazan `Arduino.h` y `Preferences.h` para probar con `g++` la lógica que no
depende del hardware (`CalibracionSensor.h`, `SensorAgua.h`). `__adc` simula la
lectura del ADC y `__nvs` la memoria no volátil, que sobrevive a un "reinicio"
(crear un objeto nuevo) mientras no se llame `__nvs.clear()`.
