@echo off
chcp 65001 > nul
title Configurar Inicializacao Automatica - A5 Tecnologia

cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "DESKTOP_DIR=%USERPROFILE%\Desktop"

echo ====================================================================
echo   CONFIGURANDO INICIALIZACAO AUTOMATICA NO WINDOWS (PC PRISCILA)
echo ====================================================================
echo.

:: Cria atalho na pasta Inicializar do Windows (shell:startup)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP_DIR%\Servidor_A5_Tecnologia.lnk'); $s.TargetPath = '%PROJECT_DIR%INICIAR_SERVIDOR.bat'; $s.WorkingDirectory = '%PROJECT_DIR%'; $s.WindowStyle = 7; $s.Description = 'Inicia automaticamente o Servidor A5 Tecnologia ao ligar o PC'; $s.Save()"

:: Cria atalhos na Area de Trabalho para facilitar o uso diario
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP_DIR%\Iniciar Servidor A5.lnk'); $s.TargetPath = '%PROJECT_DIR%INICIAR_SERVIDOR.bat'; $s.WorkingDirectory = '%PROJECT_DIR%'; $s.Description = 'Iniciar Servidor A5 Tecnologia'; $s.Save()"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP_DIR%\Atualizar Sistema A5.lnk'); $s.TargetPath = '%PROJECT_DIR%ATUALIZAR_SISTEMA.bat'; $s.WorkingDirectory = '%PROJECT_DIR%'; $s.Description = 'Baixar atualizacoes do Sistema A5 via Git'; $s.Save()"

echo [OK] Atalho criado na pasta Inicializar do Windows:
echo      %STARTUP_DIR%\Servidor_A5_Tecnologia.lnk
echo.
echo [OK] Atalhos criados na Area de Trabalho:
echo      - Iniciar Servidor A5
echo      - Atualizar Sistema A5
echo.
echo ====================================================================
echo   PRONTO! O servidor vai iniciar quando esta conta entrar no Windows!
echo ====================================================================
echo.
pause
