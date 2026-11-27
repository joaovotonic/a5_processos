@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "A5_VPS_URL=https://a5painel.cloud"
set "A5_AGENT_HOME=%LOCALAPPDATA%\A5Processos"
set "A5_TOKEN_FILE=%A5_AGENT_HOME%\pdf-ingest-token.txt"

if not exist "%A5_AGENT_HOME%" mkdir "%A5_AGENT_HOME%"

if not exist "%A5_TOKEN_FILE%" (
    echo.
    echo PRIMEIRA CONFIGURACAO DO AGENTE DE PDFs (VPS)
    echo Cole o token A5_PDF_INGEST_TOKEN configurado na VPS:
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=Read-Host 'Token' -AsSecureString; $b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); try { $t=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($b).Trim(); if ($t.Length -lt 16) { throw 'Token invalido.' }; [IO.File]::WriteAllText($env:A5_TOKEN_FILE, $t) } finally { if ($b -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) } }"
    if errorlevel 1 (
        echo ERRO: nao foi possivel salvar o token.
        pause
        exit /b 1
    )
)

set /p A5_PDF_INGEST_TOKEN=<"%A5_TOKEN_FILE%"
set "A5_PY=python"
if exist ".venv\Scripts\python.exe" set "A5_PY=%CD%\.venv\Scripts\python.exe"

:loop
echo [%date% %time%] Iniciando Agente de PDFs A5 para %A5_VPS_URL%
"%A5_PY%" agente_pdfs_recepcao.py
echo [%date% %time%] Agente encerrado. Reiniciando em 5 segundos...
timeout /t 5 /nobreak >nul
goto loop
