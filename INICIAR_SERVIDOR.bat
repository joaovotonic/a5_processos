@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "A5_TUNNEL_MODE=1"
set "A5_TUNNEL_PUBLIC_HOSTNAME=kanban.a5painel.cloud"
set "A5_SOCKETIO_ASYNC_MODE=gevent"
set "A5_PORT=5000"
set "A5_TUNNEL_HOME=%LOCALAPPDATA%\A5Processos\Cloudflare"
set "A5_TUNNEL_TOKEN_FILE=%A5_TUNNEL_HOME%\producao-token.txt"
set "A5_SECRET_FILE=%A5_TUNNEL_HOME%\session.key"

if /I "%~1"=="--server" goto server
if /I "%~1"=="--tunnel" goto tunnel

if not exist "database\a5_kanban.db" (
    echo ERRO: banco de dados nao encontrado em "%CD%\database\a5_kanban.db".
    echo Nao vou iniciar com um banco vazio.
    pause
    exit /b 2
)

if not exist "%A5_TUNNEL_HOME%" mkdir "%A5_TUNNEL_HOME%"
if errorlevel 1 (
    echo ERRO: nao foi possivel criar a pasta privada de configuracao.
    pause
    exit /b 1
)

:: Localiza o Python
set "A5_PYTHON="
call :find_python
if not defined A5_PYTHON (
    echo ERRO: Python nao encontrado no computador.
    pause
    exit /b 1
)

:: Garante que o arquivo de chave de sessao exista e tenha 64 caracteres hexadecimais validos
"%A5_PYTHON%" -c "import os, re, secrets; p = os.environ['A5_SECRET_FILE']; cur = open(p, 'r', encoding='utf-8').read().strip() if os.path.isfile(p) else ''; print(secrets.token_hex(32), file=open(p, 'w', encoding='utf-8')) if not re.match(r'^[A-Fa-f0-9]{64}$', cur) else None"
if errorlevel 1 (
    echo ERRO: nao foi possivel gerar a chave de sessao.
    pause
    exit /b 1
)
icacls "%A5_SECRET_FILE%" /inheritance:r /grant:r "%USERNAME%:R" >nul 2>nul

set "A5_SECRET_KEY="
set /p A5_SECRET_KEY=<"%A5_SECRET_FILE%"
if not defined A5_SECRET_KEY (
    echo ERRO: a chave de sessao esta vazia ou invalida.
    pause
    exit /b 1
)

if not exist "%A5_TUNNEL_TOKEN_FILE%" (
    echo.
    echo PRIMEIRA CONFIGURACAO DO TUNNEL
    echo No Cloudflare, abra o Tunnel a5-producao e copie somente o valor do token.
    echo Nunca envie esse token por mensagem nem o salve na pasta do projeto.
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $s=Read-Host 'Cole o token do Tunnel (a entrada nao sera exibida)' -AsSecureString; $b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); try { $t=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($b); if ($t -notmatch '^[A-Za-z0-9_+/=-]{100,}$') { throw 'Token vazio ou em formato invalido.' }; [IO.File]::WriteAllText($env:A5_TUNNEL_TOKEN_FILE, $t); icacls $env:A5_TUNNEL_TOKEN_FILE /inheritance:r /grant:r (([Security.Principal.WindowsIdentity]::GetCurrent().Name) + ':R') | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel proteger o arquivo do token.' } } catch { Remove-Item -LiteralPath $env:A5_TUNNEL_TOKEN_FILE -Force -ErrorAction SilentlyContinue; Write-Error $_; exit 1 } finally { if ($b -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) } }"
    if errorlevel 1 (
        echo ERRO: nao foi possivel salvar o token com seguranca.
        pause
        exit /b 1
    )
)

"%A5_PYTHON%" -c "import gevent, geventwebsocket" >nul 2>nul
if errorlevel 1 (
    echo Instalando suporte a WebSocket para o servidor de producao...
    "%A5_PYTHON%" -m pip install "gevent>=24.11.1" "gevent-websocket>=0.10.1"
    if errorlevel 1 (
        echo ERRO: falha ao instalar dependencias. Confira a conexao e tente novamente.
        pause
        exit /b 1
    )
)

set "CLOUDFLARED="
call :find_cloudflared
if not defined CLOUDFLARED (
    where.exe winget >nul 2>nul
    if errorlevel 1 (
        echo ERRO: cloudflared nao encontrado e winget nao esta disponivel.
        echo Instale cloudflared pelo site oficial da Cloudflare e execute este BAT novamente.
        pause
        exit /b 1
    )
    echo Instalando cloudflared da distribuicao oficial...
    winget install --id Cloudflare.cloudflared -e --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo ERRO: nao foi possivel instalar cloudflared.
        pause
        exit /b 1
    )
    call :find_cloudflared
    if not defined CLOUDFLARED (
        echo ERRO: cloudflared instalado, mas nao encontrado. Feche e abra esta sessao do Windows e tente novamente.
        pause
        exit /b 1
    )
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$t=[IO.File]::ReadAllText($env:A5_TUNNEL_TOKEN_FILE).Trim(); if ($t -notmatch '^[A-Za-z0-9_+/=-]{100,}$') { exit 1 }"
if errorlevel 1 (
    echo ERRO: o arquivo de token do Tunnel esta vazio ou invalido.
    pause
    exit /b 1
)

set "A5_SECRET_KEY="
set /p A5_SECRET_KEY=<"%A5_SECRET_FILE%"
if not defined A5_SECRET_KEY (
    echo ERRO: chave de sessao ausente ou vazia em "%A5_SECRET_FILE%".
    pause
    exit /b 1
)

echo.
echo Iniciando o servidor A5 e o Tunnel protegido...
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-NetConnection 127.0.0.1 -Port 5000 -InformationLevel Quiet) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    start "A5 - Servidor" "%ComSpec%" /k ""%~f0" --server"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(45); do { try { $r=Invoke-RestMethod 'http://127.0.0.1:5000/healthz' -TimeoutSec 2; if ($r.service -eq 'a5-kanban' -and $r.status -eq 'ok') { exit 0 } } catch {}; Start-Sleep -Seconds 1 } while ((Get-Date) -lt $deadline); exit 1"
    if errorlevel 1 (
        echo ERRO: o servidor A5 nao ficou pronto; o Tunnel nao sera iniciado.
        echo Confira a janela 'A5 - Servidor'.
        pause
        exit /b 1
    )
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-RestMethod 'http://127.0.0.1:5000/healthz' -TimeoutSec 3; if ($r.service -eq 'a5-kanban' -and $r.status -eq 'ok') { exit 0 } } catch {}; exit 1"
    if errorlevel 1 (
        echo ERRO: a porta 5000 ja esta ocupada por outro servidor.
        echo Feche o servidor antigo, depois execute este BAT novamente.
        pause
        exit /b 1
    )
)

start "A5 - Cloudflare Tunnel" "%ComSpec%" /k ""%~f0" --tunnel"
timeout /t 2 /nobreak >nul
start "" "https://%A5_TUNNEL_PUBLIC_HOSTNAME%/admin"
echo.
echo As janelas do servidor e do Tunnel devem permanecer abertas.
echo Feche cada janela para encerrar o processo correspondente.
exit /b 0

:server
set "A5_RUNTIME_MODE=production"
set "A5_SECRET_KEY="
set /p A5_SECRET_KEY=<"%A5_SECRET_FILE%"
set "A5_PYTHON="
call :find_python
if not defined A5_PYTHON exit /b 1
:server_loop
echo [%date% %time%] Iniciando o servidor A5...
"%A5_PYTHON%" app.py
echo [%date% %time%] O servidor encerrou. Nova tentativa em 5 segundos.
timeout /t 5 /nobreak >nul
goto server_loop

:tunnel
set "A5_RUNTIME_MODE=production"
set "A5_SECRET_KEY="
set /p A5_SECRET_KEY=<"%A5_SECRET_FILE%"
set "CLOUDFLARED="
call :find_cloudflared
if not defined CLOUDFLARED exit /b 1
:tunnel_loop
echo [%date% %time%] Conectando ao Tunnel kanban.a5painel.cloud...
"%CLOUDFLARED%" tunnel run --no-autoupdate --token-file "%A5_TUNNEL_TOKEN_FILE%"
echo [%date% %time%] O Tunnel encerrou. Nova tentativa em 5 segundos.
timeout /t 5 /nobreak >nul
goto tunnel_loop

:find_python
if exist ".venv\Scripts\python.exe" set "A5_PYTHON=%CD%\.venv\Scripts\python.exe"
if not defined A5_PYTHON if exist "venv\Scripts\python.exe" set "A5_PYTHON=%CD%\venv\Scripts\python.exe"
if not defined A5_PYTHON (
    for /f "delims=" %%P in ('where.exe python 2^>nul') do if not defined A5_PYTHON set "A5_PYTHON=%%P"
)
if not defined A5_PYTHON (
    for /f "delims=" %%P in ('where.exe py 2^>nul') do if not defined A5_PYTHON set "A5_PYTHON=%%P"
)
exit /b 0

:find_cloudflared
for /f "delims=" %%P in ('where.exe cloudflared 2^>nul') do if not defined CLOUDFLARED set "CLOUDFLARED=%%P"
if not defined CLOUDFLARED if exist "%ProgramFiles%\cloudflared\cloudflared.exe" set "CLOUDFLARED=%ProgramFiles%\cloudflared\cloudflared.exe"
if not defined CLOUDFLARED if exist "%ProgramFiles(x86)%\cloudflared\cloudflared.exe" set "CLOUDFLARED=%ProgramFiles(x86)%\cloudflared\cloudflared.exe"
if not defined CLOUDFLARED if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe" set "CLOUDFLARED=%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"
exit /b 0
