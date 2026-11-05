@echo off
chcp 65001 > nul
title Servidor A5 Tecnologia - Esteira & Rotas (Porta 5000)

:: Garante que o script rode sempre na pasta raiz do projeto (mesmo chamado pelo Inicializar do Windows)
cd /d "%~dp0"

:: Garante que o Git esteja no PATH mesmo se o Windows iniciou antes de carregar variaveis de usuario
set "PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files\Git\bin;C:\Program Files (x86)\Git\cmd;%LOCALAPPDATA%\Programs\Git\cmd"

echo ====================================================================
echo   SERVIDOR A5 TECNOLOGIA - ESTEIRA DE PRODUCAO E ROTAS EXTERNAS
echo ====================================================================
echo.
echo Iniciando o painel Administrativo no navegador em 3 segundos...
start "" cmd /c "timeout /t 3 /nobreak > nul && start http://localhost:5000/admin"

:loop
echo [%date% %time%] Iniciando servidor Python (app.py)...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" app.py
) else (
    python app.py
)

echo.
echo [AVISO] O servidor foi encerrado. Reiniciando automaticamente em 5 segundos...
echo Pressione CTRL+C se desejar fechar definitivamente.
timeout /t 5
goto loop
