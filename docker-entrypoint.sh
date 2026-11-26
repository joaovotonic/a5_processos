#!/bin/sh
set -eu

DATA_DIR="${A5_DATA_DIR:-/data}"
mkdir -p \
  "$DATA_DIR/database" \
  "$DATA_DIR/backups" \
  "$DATA_DIR/static/uploads" \
  "$DATA_DIR/entrada_pdfs" \
  "$DATA_DIR/arquivados_pdfs" \
  "$DATA_DIR/entrada_chamados_externos" \
  "$DATA_DIR/arquivados_chamados_externos" \
  "$DATA_DIR/rotas_imagens"

# Na primeira inicialização com volume vazio, semeia o banco a partir da cópia versionada do repositório
if [ ! -f "$DATA_DIR/database/a5_kanban.db" ] && [ -f "/app/database/a5_kanban.db" ]; then
  echo "[a5-esteira] Inicializando $DATA_DIR/database/a5_kanban.db a partir do snapshot do repositório..."
  cp -p /app/database/a5_kanban.db "$DATA_DIR/database/a5_kanban.db"
fi

# Garante catálogo de peças Toledo disponível no volume de dados se existir no repo
if [ ! -f "$DATA_DIR/database/toledo_parts.json" ] && [ -f "/app/kanban/toledo_parts.json" ]; then
  cp -p /app/kanban/toledo_parts.json "$DATA_DIR/database/toledo_parts.json"
fi

# Garante que safe.directory esteja liberado mesmo se /app vier de bind-mount
git config --global --add safe.directory /app 2>/dev/null || true

exec python /app/app.py
