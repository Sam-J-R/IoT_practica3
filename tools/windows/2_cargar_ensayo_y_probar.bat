@echo off
setlocal EnableDelayedExpansion
call "%~dp0comun.bat"
for /f "delims=" %%p in ('%PY% tools\windows\puerto_esp32.py 2^>nul') do set "PUERTO=%%p"
if "%PUERTO%"=="" set "PUERTO=NINGUNO"
if "%PUERTO%"=="NINGUNO" (
  echo No se encontro un unico ESP32 conectado. Puertos disponibles:
  %PY% -m serial.tools.list_ports -v
  echo PUERTO=NINGUNO > resultados_p4\paso2_cargar.log
  pause
  exit /b 1
)
set "LOG=resultados_p4\paso2_cargar.log"
echo Cargando el firmware de ensayo en %PUERTO%...
(
  echo PUERTO=%PUERTO%
  "%PIO%" run -d firmware -e tendedero_ensayo -t upload --upload-port %PUERTO%
  echo UPLOAD=!ERRORLEVEL!
) > "%LOG%" 2>&1
findstr /c:"UPLOAD=" "%LOG%"
findstr /c:"UPLOAD=0" "%LOG%" >nul || (echo La carga fallo. Revise %LOG% & pause & exit /b 1)
timeout /t 3 /nobreak >nul
echo.
echo Pruebas automaticas (unos 10 minutos). No toquen el ESP32 ni el sensor.
%PY% tools\probar_esp32.py --puerto %PUERTO% todo
echo PROBAR=%ERRORLEVEL% >> "%LOG%"
echo.
echo Listo. Pueden cerrar esta ventana.
pause
