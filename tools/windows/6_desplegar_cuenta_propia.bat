@echo off
setlocal EnableDelayedExpansion
call "%~dp0comun.bat"
rem Monta el sistema completo (AWS + Alexa) en la cuenta propia de quien lo ejecuta.
rem Primero muestra el plan sin cambiar nada; despliega solo si se confirma.
set "THING=tendedero-samuel"

where aws >nul 2>nul || (
  echo Falta la AWS CLI v2. Instalenla desde https://aws.amazon.com/cli/ y vuelvan a ejecutar.
  pause & exit /b 1
)
aws sts get-caller-identity >nul 2>nul || (
  echo No hay credenciales de AWS. Ejecuten "aws configure" con las claves de SU cuenta
  echo y region us-east-2, y vuelvan a ejecutar este archivo.
  pause & exit /b 1
)
echo Cuenta de AWS configurada:
aws sts get-caller-identity --query Account --output text

set "SIN_ALEXA="
where ask >nul 2>nul || (
  echo.
  echo No se encontro la ASK CLI: la skill de Alexa no se creara.
  echo Para incluirla: "npm install -g ask-cli" y luego "ask configure".
  set "SIN_ALEXA=--sin-alexa"
)

echo.
echo ===== PLAN (no cambia nada) =====
%PY% tools\desplegar_cuenta_propia.py --thing %THING% %SIN_ALEXA%
echo.
set /p "CORREO=Correo para la alerta de gasto (Enter para omitir): "
choice /c SN /m "Desplegar en la cuenta mostrada arriba"
if errorlevel 2 (echo Cancelado. & pause & exit /b 0)

set "CORREO_ARG="
if not "%CORREO%"=="" set "CORREO_ARG=--correo %CORREO%"
%PY% tools\desplegar_cuenta_propia.py --desplegar --thing %THING% %SIN_ALEXA% %CORREO_ARG%
echo DESPLIEGUE=%ERRORLEVEL% > resultados_p4\paso6_cuenta_propia.log
echo.
echo Listo. Revisen el codigo de vinculacion impreso arriba.
pause
