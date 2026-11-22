# Pruebas del ESP32 en Windows

Doble clic en orden. Cada uno deja su salida en `resultados_p4\`.

1. `1_preparar_y_compilar.bat`: instala pyserial, pytest y boto3, corre las pruebas sin hardware y compila los 5 perfiles.
2. `2_cargar_ensayo_y_probar.bat`: carga `tendedero_ensayo` y corre `probar_esp32.py todo` (10 min, sin tocar nada).
3. `3_calibracion_guiada.bat`: necesita a una persona para secar y mojar el sensor.
4. `4_reconexion.bat`: necesita `aws configure` en esta PC.

Al terminar, volver al firmware final:
`%USERPROFILE%\.platformio\penv\Scripts\platformio.exe run -d firmware -e tendedero_shadow -t upload`
