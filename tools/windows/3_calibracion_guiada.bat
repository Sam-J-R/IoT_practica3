@echo off
call "%~dp0comun.bat"
for /f "delims=" %%p in ('%PY% tools\windows\puerto_esp32.py 2^>nul') do set "PUERTO=%%p"
echo Prueba GUIADA de calibracion en %PUERTO%. Sigan las instrucciones y presionen Enter en cada paso.
%PY% tools\probar_esp32.py --puerto %PUERTO% calibracion
echo.
echo Prueba GUIADA del sensor: 20 observaciones alternando seco y con agua.
%PY% tools\probar_esp32.py --puerto %PUERTO% sensor
pause
