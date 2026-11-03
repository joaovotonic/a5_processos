"""Backup diário automático do banco (cópia .db consistente + dump JSON legível)."""
import json
import os
import sqlite3
import threading
from datetime import datetime

from .config import BACKUP_DIR, MAX_BACKUP_FILES
from .database import connect

_backup_lock = threading.Lock()


def perform_daily_backup(force=False):
    """
    Cria backup diário automático do banco SQLite e um dump em JSON legível.
    Retorna o caminho do arquivo .db gerado, ou None se o backup de hoje já existe.
    """
    with _backup_lock:  # evita dois backups simultâneos quando várias telas atualizam juntas
        today_str = datetime.now().strftime("%Y-%m-%d")

        with connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'last_backup_date'").fetchone()
            last_backup = row["value"] if row else ""

            if not force and last_backup == today_str:
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sqlite_backup_file = os.path.join(BACKUP_DIR, f"a5_kanban_backup_{timestamp}.db")
            json_backup_file = os.path.join(BACKUP_DIR, f"a5_kanban_dump_{timestamp}.json")

            # 1. Cópia segura do SQLite pela API de backup (inclui o que ainda está no arquivo -wal,
            #    o que uma simples cópia do arquivo .db poderia perder)
            target = sqlite3.connect(sqlite_backup_file)
            try:
                conn.backup(target)
            finally:
                target.close()

            # 2. Exportação completa em JSON
            dump = {
                "empresa": "A5 Tecnologia",
                "backup_date": datetime.now().isoformat(),
                "lists": [dict(r) for r in conn.execute("SELECT * FROM lists ORDER BY position").fetchall()],
                "cards": [dict(r) for r in conn.execute("SELECT * FROM cards ORDER BY id").fetchall()],
                "history": [dict(r) for r in conn.execute(
                    "SELECT * FROM card_history ORDER BY id DESC LIMIT 2000").fetchall()],
            }
            with open(json_backup_file, "w", encoding="utf-8") as f:
                json.dump(dump, f, ensure_ascii=False, indent=2)

            conn.execute("UPDATE settings SET value = ? WHERE key = 'last_backup_date'", (today_str,))

        _rotate_backups()
        return sqlite_backup_file


def _rotate_backups():
    """Mantém apenas os últimos 30 backups para não lotar o disco."""
    all_backups = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)],
        key=os.path.getmtime
    )
    while len(all_backups) > MAX_BACKUP_FILES:
        os.remove(all_backups.pop(0))

