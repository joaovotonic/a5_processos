"""Backup diário automático do banco (cópia .db consistente + dump JSON legível + envio para nuvem GitHub)."""
import json
import os
import sqlite3
import subprocess
import threading
from datetime import datetime
from typing import Dict, Any

from .config import BASE_DIR, DB_PATH, BACKUP_DIR, MAX_BACKUP_FILES
from .database import connect

_backup_lock = threading.Lock()

# Configuração oficial da Nuvem GitHub (repositório do João)
GITHUB_USER = "joaovotonic"
GITHUB_EMAIL = "joaovotoni1@gmail.com"
GITHUB_REPO_NAME = "a5_processos"
GITHUB_REPO_URL = "https://github.com/joaovotonic/a5_processos.git"


def _perform_daily_backup_unlocked(force=False):
    today_str = datetime.now().strftime("%Y-%m-%d")

    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'last_backup_date'").fetchone()
        last_backup = row["value"] if row else ""

        if not force and last_backup == today_str:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sqlite_backup_file = os.path.join(BACKUP_DIR, f"a5_kanban_backup_{timestamp}.db")
        json_backup_file = os.path.join(BACKUP_DIR, f"a5_kanban_dump_{timestamp}.json")

        # 1. Cópia segura do SQLite pela API de backup (inclui o que ainda está no arquivo -wal)
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
            "clients": [dict(r) for r in conn.execute("SELECT * FROM clients ORDER BY id").fetchall()],
            "external_orders": [dict(r) for r in conn.execute("SELECT * FROM external_orders ORDER BY id").fetchall()],
            "history": [dict(r) for r in conn.execute(
                "SELECT * FROM card_history ORDER BY id DESC LIMIT 2000").fetchall()],
        }
        with open(json_backup_file, "w", encoding="utf-8") as f:
            json.dump(dump, f, ensure_ascii=False, indent=2)

        conn.execute("""
            INSERT INTO settings (key, value) VALUES ('last_backup_date', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (today_str,))

    _rotate_backups()
    return sqlite_backup_file


def perform_daily_backup(force=False):
    """
    Cria backup diário automático do banco SQLite e um dump em JSON legível.
    Retorna o caminho do arquivo .db gerado, ou None se o backup de hoje já existe.
    """
    with _backup_lock:
        return _perform_daily_backup_unlocked(force=force)


def _rotate_backups():
    """Mantém apenas os últimos 30 backups rotativos para não lotar o disco."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    rotating_files = [
        os.path.join(BACKUP_DIR, f)
        for f in os.listdir(BACKUP_DIR)
        if not f.startswith("a5_kanban_nuvem_latest")
    ]
    all_backups = sorted(rotating_files, key=os.path.getmtime)
    while len(all_backups) > MAX_BACKUP_FILES:
        try:
            os.remove(all_backups.pop(0))
        except Exception:
            break


def _resolve_git_executable() -> str:
    """
    Localiza o executável `git.exe` no Windows mesmo quando o servidor Python
    foi iniciado sem o Git na variável de ambiente PATH (evitando [WinError 2]).
    """
    import glob
    import shutil

    found = shutil.which("git")
    if found and os.path.isfile(found):
        return found

    candidates = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files\Git\mingw64\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\git.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Git\cmd\git.exe"),
    ]
    gh_desktop = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\git.exe"))
    candidates.extend(gh_desktop)

    for path in candidates:
        if path and os.path.isfile(path):
            return path

    return "git"


def _run_git(args, timeout=45):
    """Executa comando git na pasta raiz do projeto garantindo o caminho do git.exe no Windows."""
    git_exe = _resolve_git_executable()
    env = os.environ.copy()
    if os.path.isabs(git_exe):
        git_dir = os.path.dirname(git_exe)
        env["PATH"] = f"{git_dir}{os.pathsep}{env.get('PATH', '')}"

    return subprocess.run(
        [git_exe] + args,
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )


def get_cloud_backup_status() -> Dict[str, Any]:
    """
    Retorna o status atual do backup em nuvem (GitHub) e se o alerta fixo das 16h40
    (segunda a sexta) deve estar ativo.
    """
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    is_weekday = now.weekday() < 5  # 0=Segunda ... 4=Sexta
    after_1640 = (now.hour > 16) or (now.hour == 16 and now.minute >= 40)

    with connect() as conn:
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE key IN ('cloud_backup_last_date', 'cloud_backup_last_at')"
        ).fetchall()
        s = {r["key"]: r["value"] for r in rows}

    last_date = s.get("cloud_backup_last_date") or ""
    last_at = s.get("cloud_backup_last_at") or ""
    done_today = (last_date == today_str)

    return {
        "github_user": GITHUB_USER,
        "github_email": GITHUB_EMAIL,
        "github_repo": f"{GITHUB_USER}/{GITHUB_REPO_NAME}",
        "github_url": GITHUB_REPO_URL,
        "cloud_backup_last_date": last_date,
        "cloud_backup_last_at": last_at,
        "done_today": done_today,
        "should_alert_now": bool(is_weekday and after_1640 and not done_today),
    }


def upload_database_to_github(dry_run: bool = False) -> Dict[str, Any]:
    """
    Consolida o banco de dados SQLite (`database/a5_kanban.db`), gera a cópia oficial
    de nuvem (`backups/a5_kanban_nuvem_latest.db` e `.json`) e sobe automaticamente
    para o repositório GitHub configurado (`joaovotonic/a5_processos`).
    """
    now_dt = datetime.now()
    today_str = now_dt.strftime("%Y-%m-%d")
    now_iso = now_dt.isoformat()
    human_dt = now_dt.strftime("%d/%m/%Y %H:%M")

    os.makedirs(BACKUP_DIR, exist_ok=True)
    cloud_db_path = os.path.join(BACKUP_DIR, "a5_kanban_nuvem_latest.db")
    cloud_json_path = os.path.join(BACKUP_DIR, "a5_kanban_nuvem_latest.json")

    with _backup_lock:
        # 1. Garante backup local diário e atualiza metadados de nuvem no banco
        _perform_daily_backup_unlocked(force=True)

        with connect() as conn:
            conn.execute("""
                INSERT INTO settings (key, value) VALUES ('cloud_backup_last_date', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (today_str,))
            conn.execute("""
                INSERT INTO settings (key, value) VALUES ('cloud_backup_last_at', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (now_iso,))
            conn.commit()

            # Consolida arquivo WAL diretamente dentro de database/a5_kanban.db
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            except Exception:
                pass

            # Cria cópia binária consistente em backups/a5_kanban_nuvem_latest.db
            if os.path.exists(cloud_db_path):
                try:
                    os.remove(cloud_db_path)
                except Exception:
                    pass
            target = sqlite3.connect(cloud_db_path)
            try:
                conn.backup(target)
            finally:
                target.close()

            # Cria espelho JSON legível em backups/a5_kanban_nuvem_latest.json
            dump = {
                "empresa": "A5 Tecnologia",
                "github_repo": f"{GITHUB_USER}/{GITHUB_REPO_NAME}",
                "backup_date": now_iso,
                "lists": [dict(r) for r in conn.execute("SELECT * FROM lists ORDER BY position").fetchall()],
                "cards": [dict(r) for r in conn.execute("SELECT * FROM cards ORDER BY id").fetchall()],
                "clients": [dict(r) for r in conn.execute("SELECT * FROM clients ORDER BY id").fetchall()],
                "external_orders": [dict(r) for r in conn.execute("SELECT * FROM external_orders ORDER BY id").fetchall()],
                "settings": {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings").fetchall()},
            }
            with open(cloud_json_path, "w", encoding="utf-8") as f:
                json.dump(dump, f, ensure_ascii=False, indent=2)

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "cloud_backup_last_date": today_str,
                "cloud_backup_last_at": now_iso,
                "github_repo": f"{GITHUB_USER}/{GITHUB_REPO_NAME}",
                "message": f"Backup preparado com sucesso para {GITHUB_USER}/{GITHUB_REPO_NAME}!"
            }

        # 2. Configura usuário, e-mail e repositório remoto do GitHub
        try:
            _run_git(["config", "user.name", GITHUB_USER])
            _run_git(["config", "user.email", GITHUB_EMAIL])
            _run_git(["config", "credential.helper", "manager"])

            rem = _run_git(["remote", "get-url", "origin"])
            if rem.returncode != 0:
                _run_git(["remote", "add", "origin", GITHUB_REPO_URL])
            elif GITHUB_REPO_NAME not in (rem.stdout or ""):
                _run_git(["remote", "set-url", "origin", GITHUB_REPO_URL])

            files_to_stage = [
                "database/a5_kanban.db",
                "backups/a5_kanban_nuvem_latest.db",
                "backups/a5_kanban_nuvem_latest.json",
            ]
            _run_git(["add", "-f"] + files_to_stage)

            commit_msg = f"Backup Nuvem Banco de Dados (Oficina A5) - {human_dt}"
            _run_git(["commit", "-m", commit_msg])

            # 3. Envia para o GitHub (branch main)
            push_res = _run_git(["push", "origin", "HEAD:main"], timeout=60)

            if push_res.returncode != 0:
                # Se houver atualizações remotas no GitHub, preserva o banco local da Priscila, sincroniza e envia
                with open(DB_PATH, "rb") as f_db:
                    db_bytes = f_db.read()
                with open(cloud_db_path, "rb") as f_cdb:
                    cdb_bytes = f_cdb.read()
                with open(cloud_json_path, "rb") as f_cjs:
                    cjs_bytes = f_cjs.read()

                _run_git(["fetch", "origin", "main"], timeout=30)
                rb = _run_git(["rebase", "-X", "theirs", "origin/main"], timeout=30)
                if rb.returncode != 0:
                    _run_git(["rebase", "--abort"])
                    _run_git(["reset", "--soft", "origin/main"])

                with open(DB_PATH, "wb") as f_db:
                    f_db.write(db_bytes)
                with open(cloud_db_path, "wb") as f_cdb:
                    f_cdb.write(cdb_bytes)
                with open(cloud_json_path, "wb") as f_cjs:
                    f_cjs.write(cjs_bytes)

                _run_git(["add", "-f"] + files_to_stage)
                _run_git(["commit", "-m", commit_msg])
                push_res = _run_git(["push", "origin", "HEAD:main"], timeout=60)

            if push_res.returncode != 0:
                err_out = (push_res.stderr or push_res.stdout or "Falha ao conectar ao GitHub.").strip()
                # Reverte a data de hoje para manter o aviso fixo visível até que o envio funcione
                with connect() as conn:
                    conn.execute("UPDATE settings SET value = '' WHERE key = 'cloud_backup_last_date'")
                    conn.commit()
                return {
                    "success": False,
                    "error": f"Não foi possível enviar ao GitHub ({GITHUB_USER}/{GITHUB_REPO_NAME}): {err_out}"
                }

            return {
                "success": True,
                "cloud_backup_last_date": today_str,
                "cloud_backup_last_at": now_iso,
                "github_repo": f"{GITHUB_USER}/{GITHUB_REPO_NAME}",
                "message": f"✅ Banco de dados salvo na nuvem GitHub ({GITHUB_USER}/{GITHUB_REPO_NAME}) às {human_dt}!"
            }

        except Exception as exc:
            with connect() as conn:
                conn.execute("UPDATE settings SET value = '' WHERE key = 'cloud_backup_last_date'")
                conn.commit()
            return {
                "success": False,
                "error": f"Erro ao executar backup no GitHub: {exc}"
            }
