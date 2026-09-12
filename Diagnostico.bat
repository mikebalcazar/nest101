@echo off
setlocal enabledelayedexpansion
chcp 437 >nul 2>&1

rem ===========================================================================
rem  Taller 101 - diagnostico de arranque  (v2)
rem
rem  v2 agrega lo que quedo sin explicar en la v1: en DESKTOP-16BJ3EK el motor
rem  arranco bien desde aqui pero la app seguia sin abrir. Las dos diferencias
rem  entre "arrancar a mano" y "arrancar desde la app" son el PUERTO y el PROXY.
rem  Esta version prueba las dos.
rem
rem  No instala nada ni cambia nada. Solo mira y anota.
rem ===========================================================================

set "LOG=%USERPROFILE%\Desktop\diagnostico-taller101.txt"
if not exist "%USERPROFILE%\Desktop" set "LOG=%USERPROFILE%\diagnostico-taller101.txt"

echo Diagnostico Taller 101 v2 > "%LOG%"
echo Fecha: %DATE% %TIME% >> "%LOG%"
echo Equipo: %COMPUTERNAME%   Usuario: %USERNAME% >> "%LOG%"
echo ======================================================== >> "%LOG%"
echo. >> "%LOG%"

echo.
echo   Taller 101 - diagnostico de arranque (v2^)
echo   -----------------------------------------
echo.
echo   Tarda un par de minutos. No cierres la ventana.
echo.

rem ---------------------------------------------------------------- Windows
echo [1] Windows
echo --- WINDOWS --- >> "%LOG%"
ver >> "%LOG%" 2>&1
wmic os get Caption,Version,OSArchitecture /value 2>nul | findstr "=" >> "%LOG%"
echo. >> "%LOG%"

rem ---------------------------------------------------------------- carpeta
echo [2] Buscando la instalacion
echo --- INSTALACION --- >> "%LOG%"
set "APP="
for %%D in (
  "%~dp0."
  "%ProgramFiles%\Taller 101"
  "%ProgramFiles%\Despiezador"
  "%ProgramFiles(x86)%\Taller 101"
  "%ProgramFiles(x86)%\Despiezador"
  "%LOCALAPPDATA%\Programs\taller-101"
  "%LOCALAPPDATA%\Programs\despiezador"
  "%LOCALAPPDATA%\Programs\Taller 101"
  "%LOCALAPPDATA%\Programs\Despiezador"
) do (
  if not defined APP if exist "%%~D\resources\python\python.exe" set "APP=%%~D"
)

if not defined APP (
  echo NO SE ENCONTRO LA INSTALACION >> "%LOG%"
  echo   No encontre la instalacion.
  echo   Copia este archivo DENTRO de la carpeta donde quedo instalado
  echo   el programa (donde esta el .exe^) y vuelve a correrlo.
  echo.
  goto :fin
)

echo Carpeta: %APP% >> "%LOG%"
set "PY=%APP%\resources\python\python.exe"
set "SRV=%APP%\resources\app_py\server.py"
if exist "%PY%" (echo   python.exe SI existe >> "%LOG%") else (echo   python.exe NO existe >> "%LOG%")
if exist "%SRV%" (echo   server.py  SI existe >> "%LOG%") else (echo   server.py  NO existe >> "%LOG%")
if exist "%APP%\resources\app_py\ui\index.html" (echo   ui/index.html SI existe >> "%LOG%") else (echo   ui/index.html NO existe >> "%LOG%")
echo. >> "%LOG%"
echo   Instalacion: %APP%

rem ---------------------------------------------------------------- bytecode
echo [3] Bytecode precompilado
echo --- BYTECODE (arranque lento si falta) --- >> "%LOG%"
set /a NPYC=0
for /f %%N in ('dir /s /b "%APP%\resources\python\Lib\*.pyc" 2^>nul ^| find /c /v ""') do set NPYC=%%N
echo   archivos .pyc en el runtime: %NPYC% >> "%LOG%"
if %NPYC% LSS 100 (
  echo   SIN PRECOMPILAR: Python compila todo en cada arranque >> "%LOG%"
  echo   Sin precompilar (arranque lento^)
) else (
  echo   Precompilado: %NPYC% .pyc
)
echo. >> "%LOG%"

rem ---------------------------------------------------------------- runtime C
echo [4] Runtime de C
echo --- RUNTIME DE C (MSVC) --- >> "%LOG%"
for %%F in (vcruntime140.dll vcruntime140_1.dll) do (
  if exist "%APP%\resources\python\%%F" (echo   %%F en el bundle: SI >> "%LOG%") else (echo   %%F en el bundle: NO >> "%LOG%")
)
for %%F in (vcruntime140.dll vcruntime140_1.dll msvcp140.dll ucrtbase.dll) do (
  if exist "%SystemRoot%\System32\%%F" (echo   %%F en System32: SI >> "%LOG%") else (echo   %%F en System32: NO >> "%LOG%")
)
echo. >> "%LOG%"

rem ---------------------------------------------------------------- PROXY
echo [5] Proxy y red local
echo --- PROXY (lo que la app usa y el .bat no) --- >> "%LOG%"
echo [Internet Settings del usuario] >> "%LOG%"
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable 2>nul | findstr ProxyEnable >> "%LOG%"
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer 2>nul | findstr ProxyServer >> "%LOG%"
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride 2>nul | findstr ProxyOverride >> "%LOG%"
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v AutoConfigURL 2>nul | findstr AutoConfigURL >> "%LOG%"
echo [WinHTTP] >> "%LOG%"
netsh winhttp show proxy >> "%LOG%" 2>&1
echo [Variables de entorno] >> "%LOG%"
if defined HTTP_PROXY  echo   HTTP_PROXY=%HTTP_PROXY% >> "%LOG%"
if defined HTTPS_PROXY echo   HTTPS_PROXY=%HTTPS_PROXY% >> "%LOG%"
if defined NO_PROXY    echo   NO_PROXY=%NO_PROXY% >> "%LOG%"
if not defined HTTP_PROXY if not defined HTTPS_PROXY echo   (sin variables de proxy^) >> "%LOG%"
echo. >> "%LOG%"

echo --- RANGOS DE PUERTO RESERVADOS POR WINDOWS --- >> "%LOG%"
echo (si 8760 cae aqui dentro, el servidor no puede usarlo) >> "%LOG%"
netsh int ipv4 show excludedportrange protocol=tcp >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- QUIEN ESTA ESCUCHANDO EN 8760-8765 --- >> "%LOG%"
netstat -ano | findstr ":876" >> "%LOG%" 2>&1
echo. >> "%LOG%"

rem ---------------------------------------------------------------- arranca?
echo [6] Probando el Python incluido
echo --- ARRANQUE DE PYTHON --- >> "%LOG%"
"%PY%" -c "import sys; print('version:', sys.version)" >> "%LOG%" 2>&1
echo codigo de salida: %ERRORLEVEL% >> "%LOG%"
echo. >> "%LOG%"

rem ---------------------------------------------------------------- librerias
echo [7] Probando las librerias
echo --- LIBRERIAS --- >> "%LOG%"
for %%L in (fastapi uvicorn pydantic numpy reportlab ezdxf openpyxl PIL) do (
  "%PY%" -c "import %%L" >nul 2>>"%LOG%"
  if errorlevel 1 (echo   %%L : FALLA >> "%LOG%") else (echo   %%L : ok >> "%LOG%")
)
echo. >> "%LOG%"

rem ---------------------------------------------------------------- servidor
rem  8760 es el puerto que usa la app. 8799 es el de control.
call :probar_puerto 8760
call :probar_puerto 8799

rem ---------------------------------------------------------------- antivirus
echo [9] Antivirus
echo --- ANTIVIRUS --- >> "%LOG%"
powershell -NoProfile -Command "try{Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct | ForEach-Object { $_.displayName }}catch{'no se pudo consultar'}" >> "%LOG%" 2>&1
echo. >> "%LOG%"

rem ---------------------------------------------------------------- registro
echo --- REGISTRO DE ARRANQUE DE LA APP (si existe) --- >> "%LOG%"
for %%R in (
  "%APPDATA%\Taller 101\arranque.log"
  "%APPDATA%\Despiezador\arranque.log"
) do (
  if exist "%%~R" (
    echo [%%~R] >> "%LOG%"
    type "%%~R" >> "%LOG%"
  )
)
echo. >> "%LOG%"

:fin
echo ======================================================== >> "%LOG%"
echo Fin del diagnostico >> "%LOG%"
echo.
echo   Listo. El resultado quedo en:
echo   %LOG%
echo.
echo   Mandame ese archivo.
echo.
start "" notepad "%LOG%"
pause
endlocal
exit /b

rem ===========================================================================
rem  Levanta el servidor en un puerto y mide cuanto tarda en contestar.
rem  Prueba de dos maneras: socket puro (como la app v0.4.3) y HTTP de
rem  PowerShell (como la v1 de este diagnostico).
rem ===========================================================================
:probar_puerto
set "P=%~1"
echo [8] Levantando el servidor en el puerto %P%
echo --- SERVIDOR EN EL PUERTO %P% --- >> "%LOG%"
set "SALIDA=%TEMP%\t101_srv_%P%.txt"
del "%SALIDA%" >nul 2>&1
start "" /b cmd /c ""%PY%" "%SRV%" --port %P% > "%SALIDA%" 2>&1"

set /a INTENTO=0
:esperar_%P%
set /a INTENTO+=1
timeout /t 2 /nobreak >nul

rem  (a) socket puro: sin proxy, sin nombres. Es lo que hace la app 0.4.3.
powershell -NoProfile -Command "try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',%P%);$c.Close();exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 goto vivo_%P%
if %INTENTO% LSS 25 goto esperar_%P%

echo   NO ACEPTO CONEXIONES en ~50 segundos >> "%LOG%"
echo   Puerto %P%: el servidor no acepto conexiones.
goto salida_%P%

:vivo_%P%
set /a SEG=%INTENTO%*2
echo   el socket acepto conexion a los ~%SEG% s >> "%LOG%"
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -Uri 'http://127.0.0.1:%P%/api/salud' -TimeoutSec 5 -UseBasicParsing; Write-Output ('  HTTP ok: ' + $r.Content)}catch{Write-Output ('  HTTP FALLA: ' + $_.Exception.Message)}" >> "%LOG%" 2>&1
echo   Puerto %P%: responde (~%SEG% s^)

:salida_%P%
echo   --- lo que imprimio el servidor en %P% --- >> "%LOG%"
if exist "%SALIDA%" (type "%SALIDA%" >> "%LOG%") else (echo   (sin salida^) >> "%LOG%")
taskkill /f /im python.exe >nul 2>&1
echo. >> "%LOG%"
exit /b
