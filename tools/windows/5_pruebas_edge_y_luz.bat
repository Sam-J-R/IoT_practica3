@echo off
setlocal EnableDelayedExpansion
call "%~dp0comun.bat"
rem Pruebas guiadas de la P4 sin LDR: R1 (agua -> resguardar), operacion sin
rem conexion y luz automatica R5 con el LDR simulado. El script pide mojar y
rem secar el sensor de agua; la luz la cambia solo con ldr_oscuro / ldr_claro.
for /f "delims=" %%p in ('%PY% tools\windows\puerto_esp32.py 2^>nul') do set "PUERTO=%%p"
if "%PUERTO%"=="" set "PUERTO=NINGUNO"
if "%PUERTO%"=="NINGUNO" (
  echo No se encontro un unico ESP32 conectado. Puertos disponibles:
  %PY% -m serial.tools.list_ports -v
  pause
  exit /b 1
)
echo Puerto %PUERTO%. Cierren el monitor serie de VS Code antes de seguir.
echo Tengan a mano un vaso con agua y un pano para mojar y secar el sensor.
pause
%PY% tools\probar_esp32.py --puerto %PUERTO% edge sin_conexion luz --ldr-simulado
echo PROBAR=%ERRORLEVEL% > resultados_p4\paso5_edge_y_luz.log
echo.
echo Listo. El resumen esta en la carpeta mas reciente de resultados_p4.
pause
