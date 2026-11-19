"""
Proteção atômica do banco SQLite (incluindo WAL) durante atualizações de código.

Usado pelo ATUALIZAR_SISTEMA.bat para garantir que `git reset --hard origin/main`
NUNCA altere, corrompa ou perca nenhuma transação pendente em `a5_kanban.db-wal`
do banco de produção da oficina.
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

TRACKED_TABLES = (
    "lists",
    "cards",
    "card_history",
    "clients",
    "external_orders",
    "external_routes",
    "pending_entries",
    "settings",
    "users",
)

MAX_PRE_UPDATE_BACKUPS = 25
ACTIVE_SNAPSHOT_NAME = "a5_kanban_preserve_active.db"
MANIFEST_NAME = "a5_kanban_preserve_manifest.json"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    existing = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    counts: Dict[str, int] = {}
    for table in TRACKED_TABLES:
        if table in existing:
            counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return counts


def _check_integrity(conn: sqlite3.Connection, label: str) -> None:
    row = conn.execute("PRAGMA integrity_check;").fetchone()
    status = str(row[0]) if row else "unknown"
    if status.lower() != "ok":
        raise RuntimeError(f"Falha na verificacao de integridade ({label}): {status}")


def _remove_sidecar_files(db_path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(f"{db_path}{suffix}")
        if sidecar.exists():
            sidecar.unlink()


def _rotate_pre_update_backups(backup_dir: Path, max_keep: int = MAX_PRE_UPDATE_BACKUPS) -> None:
    if not backup_dir.is_dir():
        return
    files = sorted(
        backup_dir.glob("a5_kanban_pre_update_*.db"),
        key=lambda p: p.stat().st_mtime,
    )
    while len(files) > max_keep:
        oldest = files.pop(0)
        try:
            oldest.unlink()
        except OSError:
            break


def checkpoint_and_snapshot(
    db_path: Path,
    state_dir: Path,
    extra_backup_dir: Optional[Path] = None,
) -> Dict[str, object]:
    """
    1. Consolida 100% do arquivo WAL no banco principal (`PRAGMA wal_checkpoint(TRUNCATE)`).
    2. Verifica que nenhum outro processo mantém o banco travado (`busy == 0`).
    3. Cria cópia consistente pela API nativa `sqlite3.Connection.backup()`.
    4. Valida integridade, contagens e registra SHA-256 no manifesto.
    """
    db_path = Path(db_path).resolve()
    state_dir = Path(state_dir).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.is_file():
        return {"skipped": True, "reason": "Banco local ainda nao existe."}

    active_snapshot = state_dir / ACTIVE_SNAPSHOT_NAME
    active_tmp = state_dir / f"{ACTIVE_SNAPSHOT_NAME}.tmp"
    manifest_path = state_dir / MANIFEST_NAME

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        ckpt = conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
        if ckpt and int(ckpt[0]) != 0:
            raise RuntimeError(
                "O banco ainda esta em uso por outro processo (WAL busy). "
                "Encerre o servidor antes de atualizar."
            )
        _check_integrity(conn, "banco_origem")
        live_counts = _collect_counts(conn)

        if active_tmp.exists():
            active_tmp.unlink()
        target = sqlite3.connect(str(active_tmp))
        try:
            conn.backup(target)
            target.commit()
        finally:
            target.close()
    finally:
        conn.close()

    os.replace(active_tmp, active_snapshot)

    # Valida integridade e contagens do snapshot gerado
    snap_conn = sqlite3.connect(str(active_snapshot), timeout=30.0)
    try:
        _check_integrity(snap_conn, "snapshot")
        snap_counts = _collect_counts(snap_conn)
    finally:
        snap_conn.close()

    if snap_counts != live_counts:
        raise RuntimeError(
            f"Divergencia de registros entre banco local ({live_counts}) e snapshot ({snap_counts})."
        )

    # Limpa arquivos -wal/-shm vazios apos checkpoint bem-sucedido
    _remove_sidecar_files(db_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    permanent_backup = state_dir / f"a5_kanban_pre_update_{timestamp}.db"
    shutil.copy2(active_snapshot, permanent_backup)
    _rotate_pre_update_backups(state_dir)

    extra_backup_path = ""
    if extra_backup_dir is not None:
        extra_dir = Path(extra_backup_dir).resolve()
        extra_dir.mkdir(parents=True, exist_ok=True)
        extra_copy = extra_dir / f"a5_kanban_pre_update_{timestamp}.db"
        shutil.copy2(active_snapshot, extra_copy)
        extra_backup_path = str(extra_copy)

    sha256 = _sha256_file(active_snapshot)
    manifest = {
        "created_at": datetime.now().isoformat(),
        "db_path": str(db_path),
        "sha256": sha256,
        "size_bytes": active_snapshot.stat().st_size,
        "counts": snap_counts,
        "permanent_backup_path": str(permanent_backup),
        "extra_backup_path": extra_backup_path,
    }
    manifest_tmp = state_dir / f"{MANIFEST_NAME}.tmp"
    manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(manifest_tmp, manifest_path)
    return manifest


def restore_snapshot(db_path: Path, state_dir: Path) -> Dict[str, object]:
    """
    Restaura `database/a5_kanban.db` a partir do snapshot verificado após o `git reset`,
    removendo qualquer `-wal`/`-shm` órfão e validando SHA-256 byte-a-byte.
    """
    db_path = Path(db_path).resolve()
    state_dir = Path(state_dir).resolve()
    active_snapshot = state_dir / ACTIVE_SNAPSHOT_NAME
    manifest_path = state_dir / MANIFEST_NAME

    if not manifest_path.is_file() or not active_snapshot.is_file():
        raise RuntimeError(
            f"Snapshot de preservacao nao encontrado em {state_dir}. "
            "Verifique os backups permanentes a5_kanban_pre_update_*.db."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_sha = manifest["sha256"]
    snap_sha = _sha256_file(active_snapshot)
    if snap_sha != expected_sha:
        raise RuntimeError(
            "Checksum SHA-256 do snapshot corrompido! "
            f"Use o backup permanente em: {manifest.get('permanent_backup_path')}"
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    _remove_sidecar_files(db_path)

    restoring_tmp = Path(f"{db_path}.restoring")
    shutil.copy2(active_snapshot, restoring_tmp)
    os.replace(restoring_tmp, db_path)

    restored_sha = _sha256_file(db_path)
    if restored_sha != expected_sha:
        raise RuntimeError("Falha na verificacao SHA-256 apos restaurar database/a5_kanban.db.")

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        _check_integrity(conn, "banco_restaurado")
        restored_counts = _collect_counts(conn)
    finally:
        conn.close()

    if restored_counts != manifest["counts"]:
        raise RuntimeError(
            f"Divergencia de registros apos restauracao: esperado={manifest['counts']} atual={restored_counts}"
        )

    return {
        "sha256": restored_sha,
        "counts": restored_counts,
        "permanent_backup_path": manifest.get("permanent_backup_path", ""),
    }


def verify_post_init(db_path: Path, state_dir: Path) -> Dict[str, object]:
    """
    Confirma após `init_db()` que o banco permanece íntegro e que nenhuma tabela perdeu registros.
    Remove apenas os arquivos temporários ativos, mantendo os backups com data/hora intactos.
    """
    db_path = Path(db_path).resolve()
    state_dir = Path(state_dir).resolve()
    active_snapshot = state_dir / ACTIVE_SNAPSHOT_NAME
    manifest_path = state_dir / MANIFEST_NAME

    if not manifest_path.is_file():
        return {"skipped": True}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before_counts: Dict[str, int] = manifest.get("counts", {})

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        _check_integrity(conn, "pos_init_db")
        after_counts = _collect_counts(conn)
    finally:
        conn.close()

    shrinkages = {}
    for table, prev_val in before_counts.items():
        cur_val = after_counts.get(table, 0)
        if cur_val < prev_val:
            shrinkages[table] = {"antes": prev_val, "depois": cur_val}

    if shrinkages:
        raise RuntimeError(
            f"ALERTA: reducao inesperada de registros apos init_db(): {shrinkages}. "
            f"Backup intacto disponivel em: {manifest.get('permanent_backup_path')}"
        )

    for tmp_file in (active_snapshot, manifest_path):
        try:
            if tmp_file.exists():
                tmp_file.unlink()
        except OSError:
            pass

    return {
        "counts": after_counts,
        "permanent_backup_path": manifest.get("permanent_backup_path", ""),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Guarda de protecao do banco SQLite A5.")
    parser.add_argument("action", choices=("snapshot", "restore", "verify-post-init"))
    parser.add_argument("--db", required=True, help="Caminho do database/a5_kanban.db")
    parser.add_argument("--state-dir", required=True, help="Pasta segura fora do Git para snapshot")
    parser.add_argument("--extra-backup-dir", default="", help="Pasta opcional de copia adicional")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    state_dir = Path(args.state_dir)
    extra_dir = Path(args.extra_backup_dir) if args.extra_backup_dir else None

    try:
        if args.action == "snapshot":
            info = checkpoint_and_snapshot(db_path, state_dir, extra_backup_dir=extra_dir)
            if info.get("skipped"):
                print(f"[INFO] {info['reason']}")
                return 0
            c = info["counts"]
            print(
                f"[OK] Banco protegido com WAL consolidado "
                f"(SHA-256: {info['sha256'][:12]} | O.S.: {c.get('cards', 0)} | "
                f"Listas: {c.get('lists', 0)} | Externos: {c.get('external_orders', 0)})"
            )
            print(f"[OK] Copia permanente salva em: {info['permanent_backup_path']}")
            return 0

        if args.action == "restore":
            info = restore_snapshot(db_path, state_dir)
            c = info["counts"]
            print(
                f"[OK] Banco local restaurado 100% intacto "
                f"(SHA-256: {info['sha256'][:12]} | O.S.: {c.get('cards', 0)} | "
                f"Listas: {c.get('lists', 0)} | Externos: {c.get('external_orders', 0)})"
            )
            return 0

        if args.action == "verify-post-init":
            info = verify_post_init(db_path, state_dir)
            if info.get("skipped"):
                return 0
            c = info["counts"]
            print(
                f"[OK] Verificacao pos-atualizacao aprovada "
                f"(O.S.: {c.get('cards', 0)} | Listas: {c.get('lists', 0)} | "
                f"Clientes: {c.get('clients', 0)} | Externos: {c.get('external_orders', 0)})"
            )
            return 0
    except Exception as exc:
        print(f"[ERRO DB_GUARD] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
