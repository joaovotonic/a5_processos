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

echo ==========================================================
echo       ATUALIZANDO SISTEMA A5 TECNOLOGIA (PC PRISCILA)
echo ==========================================================
echo.
echo Escolha o tipo de atualizacao desejada:
echo.
echo   [1] Atualizar TUDO (Codigo + Cards e Banco organizados pelo Joao)
echo   [2] Atualizar apenas CODIGO (Manter o banco local deste PC)
echo.
set "OPCAO=1"
set /p "OPCAO=Digite 1 ou 2 e pressione ENTER [Padrao: 1]: "
if defined OPCAO set "OPCAO=%OPCAO: =%"
if not defined OPCAO set "OPCAO=1"

git config user.name "joaovotonic"
git config user.email "joaovotoni1@gmail.com"
git config credential.helper manager

echo.
echo Encerrando temporariamente o servidor na porta 5000 para liberar os arquivos...
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

if "%OPCAO%"=="2" goto opcao2
goto opcao1

:opcao2
echo.
echo ==========================================================
echo [Opcao 2] Atualizando codigo e PRESERVANDO banco local...
echo ==========================================================
echo.
if exist "database\a5_kanban.db" (
    echo [1/3] Protegendo o banco de dados local da oficina...
    copy /Y "database\a5_kanban.db" "database\a5_kanban_local_preserve.bak" >nul
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel copiar database\a5_kanban.db para backup temporario.
        echo Feche qualquer programa usando o banco e tente novamente.
        pause
        exit /b 1
    )
)

echo [2/3] Baixando atualizacoes de codigo do GitHub (origin/main)...
git fetch origin main
if errorlevel 1 goto erro_git_restore_local
git reset --hard origin/main
if errorlevel 1 goto erro_git_restore_local

if exist "database\a5_kanban_local_preserve.bak" (
    copy /Y "database\a5_kanban_local_preserve.bak" "database\a5_kanban.db" >nul
    if not errorlevel 1 del /F /Q "database\a5_kanban_local_preserve.bak" >nul
)

echo [3/3] Verificando novas dependencias e tabelas do banco...
"%A5_PYTHON%" -m pip install -r requirements.txt --quiet --no-warn-script-location
if errorlevel 1 (
    echo [AVISO] Alguma dependencia pip retornou erro. Verifique sua conexao se houver falha ao iniciar.
)
"%A5_PYTHON%" -c "from kanban.database import init_db; init_db()"
if errorlevel 1 (
    echo [ERRO] Falha ao atualizar tabelas do banco de dados.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo      CODIGO ATUALIZADO! BANCO LOCAL PRESERVADO.
echo ==========================================================
goto iniciar_servidor

:erro_git_restore_local
if exist "database\a5_kanban_local_preserve.bak" (
    copy /Y "database\a5_kanban_local_preserve.bak" "database\a5_kanban.db" >nul
    if not errorlevel 1 del /F /Q "database\a5_kanban_local_preserve.bak" >nul
)
echo.
echo [ERRO] Falha ao baixar atualizacoes do GitHub. Verifique a internet ou credenciais Git.
pause
exit /b 1

:opcao1
echo.
echo ==========================================================
echo [Opcao 1] Atualizando TUDO (Codigo + Cards e Banco do Joao)...
echo ==========================================================
echo.
if exist "database\a5_kanban.db" (
    echo [1/3] Criando copia de seguranca do banco atual por garantia...
    copy /Y "database\a5_kanban.db" "database\a5_kanban_backup_antes_atualizar.bak" >nul
)

echo [2/3] Baixando versao completa da nuvem (joaovotonic/a5_processos)...
git fetch origin main
if errorlevel 1 goto erro_git_opcao1
git reset --hard origin/main
if errorlevel 1 goto erro_git_opcao1

echo [3/3] Verificando novas dependencias e tabelas do banco...
"%A5_PYTHON%" -m pip install -r requirements.txt --quiet --no-warn-script-location
if errorlevel 1 (
    echo [AVISO] Alguma dependencia pip retornou erro. Verifique sua conexao se houver falha ao iniciar.
)
"%A5_PYTHON%" -c "from kanban.database import init_db; init_db()"
if errorlevel 1 (
    echo [ERRO] Falha ao atualizar tabelas do banco de dados.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo   SISTEMA E CARDS ATUALIZADOS COM SUCESSO!
echo ==========================================================
echo Todos os cards organizados pelo Joao estao prontos no painel.
echo Copia anterior salva em: database\a5_kanban_backup_antes_atualizar.bak
goto iniciar_servidor

:erro_git_opcao1
echo.
echo [ERRO] Falha ao baixar atualizacoes do GitHub. Verifique a internet ou credenciais Git.
pause
exit /b 1

:iniciar_servidor
echo.
echo Iniciando o servidor atualizado em segundo plano...
set "A5_STATE_HOME=%LOCALAPPDATA%\A5Processos"
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
