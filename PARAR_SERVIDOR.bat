@echo off
chcp 65001 >nul
setlocal
title Parando Servidor A5 Tecnologia
cd /d "%~dp0"

set "A5_ROOT=%CD%"
set "A5_STATE_HOME=%LOCALAPPDATA%\A5Processos"
set "A5_SERVER_PID_FILE=%A5_STATE_HOME%\server.pid"
set "A5_TUNNEL_PID_FILE=%A5_STATE_HOME%\tunnel.pid"
set "ONLY_SERVER=0"
set "QUIET_MODE=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--server-only" set "ONLY_SERVER=1"
if /I "%~1"=="--quiet" set "QUIET_MODE=1"
shift
goto parse_args

:args_done
if "%QUIET_MODE%"=="0" (
    echo ==========================================================
    echo        ENCERRANDO SERVIDOR A5 TECNOLOGIA
    echo ==========================================================
    echo.
)

:: 1. Encerra loops e processos do Servidor Flask (ocultos ou em janela)
if exist "%A5_SERVER_PID_FILE%" (
    for /f "usebackq delims=" %%P in ("%A5_SERVER_PID_FILE%") do (
        if not "%%P"=="" taskkill /F /PID %%P /T >nul 2>nul
    )
    del /F /Q "%A5_SERVER_PID_FILE%" >nul 2>nul
)

taskkill /F /FI "WINDOWTITLE eq A5 - Servidor*" /T >nul 2>nul
taskkill /F /FI "WINDOWTITLE eq A5 Sistema Kanban*" /T >nul 2>nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and (($_.Name -ieq 'cmd.exe' -and $_.CommandLine -like '*INICIAR_SERVIDOR.bat*--server*') -or (($_.Name -ieq 'python.exe' -or $_.Name -ieq 'pythonw.exe') -and ($_.CommandLine -like ('*' + $env:A5_ROOT + '*app.py*') -or $_.CommandLine -like '*a5_processos*app.py*'))) } | ForEach-Object { & taskkill /F /PID $_.ProcessId /T 2>$null | Out-Null }"

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    if not "%%a"=="0" taskkill /F /PID %%a /T >nul 2>nul
)

if "%ONLY_SERVER%"=="1" goto after_stop

:: 2. Encerra loop e processo do Cloudflare Tunnel
if exist "%A5_TUNNEL_PID_FILE%" (
    for /f "usebackq delims=" %%P in ("%A5_TUNNEL_PID_FILE%") do (
        if not "%%P"=="" taskkill /F /PID %%P /T >nul 2>nul
    )
    del /F /Q "%A5_TUNNEL_PID_FILE%" >nul 2>nul
)

taskkill /F /FI "WINDOWTITLE eq A5 - Cloudflare Tunnel*" /T >nul 2>nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and (($_.Name -ieq 'cmd.exe' -and $_.CommandLine -like '*INICIAR_SERVIDOR.bat*--tunnel*') -or ($_.Name -ieq 'cloudflared.exe' -and $_.CommandLine -like '*tunnel run*')) } | ForEach-Object { & taskkill /F /PID $_.ProcessId /T 2>$null | Out-Null }"

:after_stop
ping -n 2 127.0.0.1 >nul
if "%QUIET_MODE%"=="1" exit /b 0

echo [OK] Servidor A5 encerrado.
if "%ONLY_SERVER%"=="0" echo [OK] Cloudflare Tunnel encerrado.
echo.
pause
exit /b 0
