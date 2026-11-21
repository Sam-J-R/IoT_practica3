@echo off
call "%~dp0comun.bat"
for /f "delims=" %%p in ('%PY% tools\windows\puerto_esp32.py 2^>nul') do set "PUERTO=%%p"
echo Prueba de reconexion en %PUERTO%.
echo Con credenciales de AWS (aws configure) la orden la deja el script.
echo Sin ellas, el script les pedira dar la orden por Alexa mientras el ESP32 esta sin red.
echo Cierren el monitor serie y tengan el Echo o la app de Alexa a mano.
pause
%PY% tools\probar_esp32.py --puerto %PUERTO% reconexion --thing tendedero-inteligente
pause
