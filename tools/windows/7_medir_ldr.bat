@echo off
setlocal EnableDelayedExpansion
call "%~dp0comun.bat"
rem Carga sensor_test y muestra el LDR para anotar las referencias de luz_local.h.
for /f "delims=" %%p in ('%PY% tools\windows\puerto_esp32.py 2^>nul') do set "PUERTO=%%p"
if "%PUERTO%"=="" set "PUERTO=NINGUNO"
if "%PUERTO%"=="NINGUNO" (
  echo No se encontro un unico ESP32 conectado. Puertos disponibles:
  %PY% -m serial.tools.list_ports -v
  pause & exit /b 1
)
echo Cargando sensor_test en %PUERTO% (el servo no se mueve, no hay WiFi)...
"%PIO%" run -d firmware -e sensor_test -t upload --upload-port %PUERTO% > resultados_p4\paso7_ldr.log 2>&1
findstr /c:"SUCCESS" resultados_p4\paso7_ldr.log >nul || (echo La carga fallo. Revise resultados_p4\paso7_ldr.log & pause & exit /b 1)
echo.
echo Van a aparecer lineas [SENSOR] (agua, GPIO34) y [LDR] (luz, GPIO35).
echo   1. Con la luz de la habitacion encendida, anoten unos 20 valores de [LDR] raw.
echo   2. Tapen el LDR con la mano y anoten otros 20.
echo   3. Cierren con Ctrl+C y pongan los promedios en firmware\include\luz_local.h
echo      (CLARO = con luz, OSCURO = tapado). Deben diferir al menos 200.
echo.
pause
"%PIO%" device monitor -d firmware -p %PUERTO% -b 115200
