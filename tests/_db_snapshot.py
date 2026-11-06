"""
Helper para isolar os testes automatizados sem poluir o banco de produção
(`database/a5_kanban.db`) nem os arquivos de backup em nuvem (`backups/a5_kanban_nuvem_latest.*`).
"""
import os
import sqlite3

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(WORKSPACE, "database", "a5_kanban.db")
CLOUD_DB_PATH = os.path.join(WORKSPACE, "backups", "a5_kanban_nuvem_latest.db")
CLOUD_JSON_PATH = os.path.join(WORKSPACE, "backups", "a5_kanban_nuvem_latest.json")


def _checkpoint_and_clean_wal():
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.close()
        except Exception:
            pass
    for suffix in ("-wal", "-shm"):
        p = f"{DB_PATH}{suffix}"
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def take_db_snapshot() -> dict:
    """Captura bytes exatos do banco SQLite e dos arquivos de backup em nuvem."""
    _checkpoint_and_clean_wal()
    snap = {}
    for p in (DB_PATH, CLOUD_DB_PATH, CLOUD_JSON_PATH):
        if os.path.exists(p):
            with open(p, "rb") as f:
                snap[p] = f.read()
    return snap


def restore_db_snapshot(snap: dict):
    """Restaura byte a byte o banco SQLite e os arquivos de backup em nuvem."""
    if not snap:
        return
    _checkpoint_and_clean_wal()
    for p, data in snap.items():
        with open(p, "wb") as f:
            f.write(data)
    _checkpoint_and_clean_wal()

