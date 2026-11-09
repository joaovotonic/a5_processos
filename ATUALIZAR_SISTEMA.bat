@echo off
chcp 65001 > nul
title Atualizando Sistema A5 Tecnologia
cd /d "%~dp0"

:: Garante que o Git esteja no PATH do Windows
set "PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files\Git\bin;C:\Program Files (x86)\Git\cmd;%LOCALAPPDATA%\Programs\Git\cmd"

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

git config user.name "joaovotonic"
git config user.email "joaovotoni1@gmail.com"
git config credential.helper manager

if "%OPCAO%"=="2" (
    echo.
    echo ==========================================================
    echo [Opcao 2] Atualizando codigo e PRESERVANDO banco local...
    echo ==========================================================
    echo.
    if exist "database\a5_kanban.db" (
        echo [1/3] Protegendo o banco de dados local da oficina...
        copy /Y "database\a5_kanban.db" "database\a5_kanban_local_preserve.bak" >nul
        git checkout -- database/a5_kanban.db backups/ 2>nul
    )

    echo [2/3] Baixando atualizacoes de codigo do GitHub...
    git pull origin main

    if exist "database\a5_kanban_local_preserve.bak" (
        copy /Y "database\a5_kanban_local_preserve.bak" "database\a5_kanban.db" >nul
        del /F /Q "database\a5_kanban_local_preserve.bak" >nul
    )

    echo [3/3] Verificando novas dependencias e tabelas do banco...
    pip install -r requirements.txt --quiet --no-warn-script-location
    python -c "from kanban.database import init_db; init_db()" 2>nul

    echo.
    echo ==========================================================
    echo      CODIGO ATUALIZADO! BANCO LOCAL PRESERVADO.
    echo ==========================================================
) else (
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
    git reset --hard origin/main

    echo [3/3] Verificando novas dependencias e tabelas do banco...
    pip install -r requirements.txt --quiet --no-warn-script-location
    python -c "from kanban.database import init_db; init_db()" 2>nul

    echo.
    echo ==========================================================
    echo   SISTEMA E CARDS ATUALIZADOS COM SUCESSO!
    echo ==========================================================
    echo Todos os cards organizados pelo Joao estao prontos no painel.
    echo (Copia anterior salva em database\a5_kanban_backup_antes_atualizar.bak)
)

echo.
echo Reiniciando o servidor local na porta 5000 para aplicar novas rotas...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>nul
)
start "A5 Sistema Kanban" cmd /k "python app.py"
echo Servidor reiniciado com sucesso!
echo.
pause
