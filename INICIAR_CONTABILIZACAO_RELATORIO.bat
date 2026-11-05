@echo off
chcp 65001 >nul
title A5 Tecnologia - Iniciar Contabilizacao Oficial do Relatorio
cd /d "%~dp0"

echo ============================================================================
echo     A5 TECNOLOGIA - INICIAR CONTABILIZACAO OFICIAL (RELATORIO SR. JACSON)
echo ============================================================================
echo.
echo  Use este arquivo APOS a Priscila terminar de organizar todas as O.S.
echo  manualmente nas colunas certas do Kanban.
echo.
echo  O que este comando vai fazer:
echo   1. MANTER todos os cartoes exatamente nas colunas onde a Priscila colocou;
echo   2. ZERAR a contagem antiga de Balancas Prontas, Orcamentos e Tempos;
echo   3. INICIAR a contabilizacao oficial do Relatorio do Sr. Jacson e da TV
echo      a partir deste exato momento (comecar a valer de verdade!).
echo.
echo ============================================================================
set /p CONFIRMA="Deseja iniciar a contabilizacao oficial agora? (Digite S e aperte ENTER): "
if /I not "%CONFIRMA%"=="S" (
    echo.
    echo [CANCELADO] Nenhuma alteracao foi feita.
    pause
    exit /b 0
)

echo.
echo [AGUARDE] Sincronizando colunas do Kanban e zerando contadores antigos...
echo.

if exist "venv\Scripts\python.exe" (
    set "PY_CMD=venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

"%PY_CMD%" -c "import urllib.request, json; req = urllib.request.Request('http://127.0.0.1:5000/api/diretoria/reset-metrics', data=b'{\"actor\":\"Priscila (Recepcao)\"}', headers={'Content-Type':'application/json'}, method='POST'); res = json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8')); print('  [OK] Servidor atualizado em tempo real!'); print('  Marco inicial:', res.get('metrics_start_at', '')[:19].replace('T', ' ')); print('  Total de O.S. sincronizadas:', res.get('total_cards_synced'))" 2>nul

if %ERRORLEVEL% NEQ 0 (
    "%PY_CMD%" -c "from kanban.services.diretoria import reset_and_start_official_metrics; res = reset_and_start_official_metrics('Priscila (Recepcao)'); print('  [OK] Banco de dados sincronizado com sucesso!'); print('  Marco inicial:', res.get('metrics_start_at', '')[:19].replace('T', ' ')); print('  Total de O.S. sincronizadas:', res.get('total_cards_synced')); [print(f'   - {k}: {v} O.S.') for k, v in res.get('summary_by_column', {}).items()]"
)

echo.
echo ============================================================================
echo  [SUCESSO] CONTABILIZACAO OFICIAL INICIADA!
echo  A partir de agora, todo orcamento feito e toda balanca finalizada
echo  sera contabilizada certinho no Relatorio do Sr. Jacson e no Placar da TV.
echo ============================================================================
echo.
pause

