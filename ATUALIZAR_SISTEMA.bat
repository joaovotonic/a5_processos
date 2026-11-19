@echo off
chcp 65001 > nul
setlocal
title Atualizando Sistema A5 Tecnologia
cd /d "%~dp0"

:: Garante que o Git esteja no PATH do Windows
set "PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files\Git\bin;C:\Program Files (x86)\Git\cmd;%LOCALAPPDATA%\Programs\Git\cmd"

where.exe git >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Git nao encontrado no PATH deste computador.
    echo Instale o Git para Windows ou execute via terminal Git Bash.
    pause
    exit /b 1
)

set "A5_PYTHON="
call :find_python
if not defined A5_PYTHON (
    echo [ERRO] Python nao encontrado no computador.
    pause
    exit /b 1
)

set "A5_STATE_HOME=%LOCALAPPDATA%\A5Processos"
set "A5_PRE_UPDATE_DIR=%A5_STATE_HOME%\pre_update_backups"
set "A5_DB_PATH=%CD%\database\a5_kanban.db"

echo ==========================================================
echo       ATUALIZANDO SISTEMA A5 TECNOLOGIA (SOMENTE CODIGO)
echo ==========================================================
echo.
echo Modo seguro ativo: o banco de dados local da oficina
echo (database\a5_kanban.db + WAL) sera 100%% preservado e
echo validado com SHA-256 antes e depois da atualizacao.
echo.

git config user.name "joaovotonic"
git config user.email "joaovotoni1@gmail.com"
git config credential.helper manager

echo [1/4] Encerrando temporariamente o servidor para liberar o banco...
if exist "%~dp0PARAR_SERVIDOR.bat" (
    call "%~dp0PARAR_SERVIDOR.bat" --quiet
) else (
    taskkill /F /FI "WINDOWTITLE eq A5 - Servidor*" /T >nul 2>nul
    taskkill /F /FI "WINDOWTITLE eq A5 Sistema Kanban*" /T >nul 2>nul
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
        if not "%%a"=="0" taskkill /F /PID %%a /T >nul 2>nul
    )
)
ping -n 3 127.0.0.1 >nul

echo [2/4] Consolidando WAL e criando snapshot verificado do banco local...
set "HAS_DB_SNAPSHOT=0"
if exist "%A5_DB_PATH%" (
    set "HAS_DB_SNAPSHOT=1"
    "%A5_PYTHON%" -m kanban.db_guard snapshot --db "%A5_DB_PATH%" --state-dir "%A5_PRE_UPDATE_DIR%" --extra-backup-dir "%CD%\backups"
    if errorlevel 1 (
        echo.
        echo [ABORTADO] Nao foi possivel proteger o banco de dados local com seguranca.
        echo NENHUMA alteracao foi feita no codigo ou no banco.
        echo Feche qualquer programa usando o banco e tente novamente.
        pause
        exit /b 1
    )
)

echo [3/4] Baixando atualizacoes de codigo do GitHub (origin/main)...
git fetch origin main
if errorlevel 1 goto erro_git
git reset --hard origin/main
if errorlevel 1 goto erro_git

if "%HAS_DB_SNAPSHOT%"=="1" (
    "%A5_PYTHON%" -m kanban.db_guard restore --db "%A5_DB_PATH%" --state-dir "%A5_PRE_UPDATE_DIR%"
    if errorlevel 1 (
        echo.
        echo [ERRO CRITICO] Falha ao restaurar o snapshot do banco local.
        echo Uma copia permanente intacta foi salva em:
        echo   %A5_PRE_UPDATE_DIR%
        pause
        exit /b 1
    )
)

echo [4/4] Verificando dependencias, migracoes seguras e integridade do banco...
"%A5_PYTHON%" -m pip install -r requirements.txt --quiet --no-warn-script-location
if errorlevel 1 (
    echo [AVISO] Alguma dependencia pip retornou erro. Verifique sua conexao se houver falha ao iniciar.
)
"%A5_PYTHON%" -c "from kanban.database import init_db; init_db()"
if errorlevel 1 (
    echo [ERRO] Falha ao verificar tabelas do banco de dados.
    pause
    exit /b 1
)

if "%HAS_DB_SNAPSHOT%"=="1" (
    "%A5_PYTHON%" -m kanban.db_guard verify-post-init --db "%A5_DB_PATH%" --state-dir "%A5_PRE_UPDATE_DIR%"
    if errorlevel 1 (
        echo.
        echo [ALERTA] Verifique o aviso acima antes de continuar!
        pause
        exit /b 1
    )
)

echo.
echo ==========================================================
echo   CODIGO ATUALIZADO! BANCO LOCAL 100%% PRESERVADO.
echo ==========================================================
goto iniciar_servidor

:erro_git
if "%HAS_DB_SNAPSHOT%"=="1" (
    "%A5_PYTHON%" -m kanban.db_guard restore --db "%A5_DB_PATH%" --state-dir "%A5_PRE_UPDATE_DIR%" >nul 2>nul
)
echo.
echo [ERRO] Falha ao baixar atualizacoes do GitHub.
echo Seu banco local permanece intacto. Verifique a internet ou credenciais Git.
pause
exit /b 1

:iniciar_servidor
echo.
echo Iniciando o servidor atualizado em segundo plano...
set "A5_TUNNEL_HOME=%A5_STATE_HOME%\Cloudflare"
if exist "%A5_TUNNEL_HOME%\producao-token.txt" (
    if exist "%A5_TUNNEL_HOME%\session.key" (
        if exist "%~dp0INICIAR_SERVIDOR.bat" goto iniciar_tunnel
    )
)

set "A5_LOG_DIR=%A5_STATE_HOME%\logs"
set "A5_SERVER_LOG=%A5_LOG_DIR%\servidor.log"
set "A5_SERVER_PID_FILE=%A5_STATE_HOME%\server.pid"
set "A5_APP_FILE=%CD%\app.py"
set "A5_ROOT=%CD%"
if not exist "%A5_LOG_DIR%" mkdir "%A5_LOG_DIR%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$q=[char]34; $cmd='/c '+$q+$q+$env:A5_PYTHON+$q+' -u '+$q+$env:A5_APP_FILE+$q+' >>'+$q+$env:A5_SERVER_LOG+$q+' 2>&1'+$q; $p=Start-Process -FilePath $env:ComSpec -ArgumentList $cmd -WorkingDirectory $env:A5_ROOT -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText($env:A5_SERVER_PID_FILE, [string]$p.Id)"
echo [OK] Servidor iniciado em segundo plano sem janelas na barra!
echo.
pause
exit /b 0

:iniciar_tunnel
call "%~dp0INICIAR_SERVIDOR.bat"
if errorlevel 1 exit /b 1
echo.
pause
exit /b 0

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
