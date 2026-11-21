# Cabeceras simuladas del ESP32

Permiten compilar `firmware/src/ClienteShadow.cpp` en la PC con g++ para probar
el manejo del Shadow sin el ESP32 (`test_cliente_shadow.cpp`). No son las
bibliotecas reales: la cola, MQTT y cJSON tienen lo mínimo que usa el firmware.
