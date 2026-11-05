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

git config user.name "joaovotonic"
git config user.email "joaovotoni1@gmail.com"
git config credential.helper manager

if exist "database\a5_kanban.db" (
    echo [1/3] Protegendo o banco de dados local da oficina...
    copy /Y "database\a5_kanban.db" "database\a5_kanban_local_preserve.bak" >nul
    git checkout -- database/a5_kanban.db backups/ 2>nul
)

echo [2/3] Baixando atualizacoes do GitHub (joaovotonic/a5_processos)...
git pull origin main

if exist "database\a5_kanban_local_preserve.bak" (
    copy /Y "database\a5_kanban_local_preserve.bak" "database\a5_kanban.db" >nul
    del /F /Q "database\a5_kanban_local_preserve.bak" >nul
)

echo.
echo [3/3] Verificando novas dependencias...
pip install -r requirements.txt --quiet --no-warn-script-location

echo.
echo ==========================================================
echo     SISTEMA ATUALIZADO COM SUCESSO!
echo ==========================================================
echo.
pause
