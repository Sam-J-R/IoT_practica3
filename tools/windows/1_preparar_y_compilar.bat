@echo off
setlocal EnableDelayedExpansion
call "%~dp0comun.bat"
set "LOG=resultados_p4\paso1_preparar_y_compilar.log"
echo Preparando y compilando. La salida completa queda en %LOG%
(
  echo === Fecha: %DATE% %TIME%
  echo === Python
  where python
  %PY% --version
  echo === Dependencias
  %PY% -m pip install --disable-pip-version-check -q pyserial pytest boto3
  echo PIP=!ERRORLEVEL!
  echo === g++
  where g++
  echo === Puertos serie
  %PY% -m serial.tools.list_ports -v
  echo === Puerto elegido
  %PY% tools\windows\puerto_esp32.py
  echo === Pruebas sin hardware
  %PY% -m pytest tests -q -p no:warnings -p no:cacheprovider --ignore=tests/p4/test_entregables.py
  echo PYTEST=!ERRORLEVEL!
  echo === Compilacion de los 5 perfiles
  "%PIO%" run -d firmware -e sensor_test -e servo_test -e sensor_shadow_test -e tendedero_shadow -e tendedero_ensayo
  echo PIO=!ERRORLEVEL!
  echo === FIN
) > "%LOG%" 2>&1
type "%LOG%" | findstr /b /c:"===" /c:"PIO=" /c:"PYTEST=" /c:"PIP=" /c:"COM" /c:"NINGUNO" /c:"passed" /c:"failed"
echo.
echo Listo. Pueden cerrar esta ventana.
pause
