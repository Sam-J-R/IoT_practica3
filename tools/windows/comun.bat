@rem Variables comunes. Lo llaman los demas .bat; no se ejecuta solo.
cd /d "%~dp0..\.."
if not exist resultados_p4 mkdir resultados_p4
set "PIO=%USERPROFILE%\.platformio\penv\Scripts\platformio.exe"
set "PATH=C:\msys64\ucrt64\bin;C:\msys64\mingw64\bin;%PATH%"
set "PYTHONUTF8=1"
set "PY=python"
where python >nul 2>nul || set "PY=py -3"
