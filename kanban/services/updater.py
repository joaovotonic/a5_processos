"""
Serviço de verificação e aplicação controlada de atualizações via GitHub (joaovotonic/a5_processos).

- Nunca atualiza sozinho: apenas verifica commits novos em `origin/<branch>` com cache.
- Ao ser acionado pelo painel `/admin` (`master` ou `admin_recepcao`):
  1. Cria backup de segurança do SQLite (`perform_daily_backup(force=True)`).
  2. Se `DATA_DIR == BASE_DIR` (Windows/local), protege o banco com `db_guard` (snapshot SHA-256 + restore).
     Se `DATA_DIR != BASE_DIR` (VPS Docker com volume `/data`), o banco nem fica dentro do repo Git!
  3. Atualiza o código para `origin/<branch>` via `git fetch` + `git reset --hard`.
  4. Instala novas dependências se `requirements.txt` mudou.
  5. Agenda reinício limpo do processo para carregar o código novo.
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ..backup import GITHUB_REPO_NAME, GITHUB_USER, _run_git, perform_daily_backup
from ..config import BASE_DIR, DATA_DIR, DB_PATH, UPDATE_BRANCH

logger = logging.getLogger("kanban.updater")

_CHECK_LOCK = threading.Lock()
_APPLY_LOCK = threading.Lock()
_UPDATE_CACHE: Dict[str, Any] = {"ts": 0.0, "data": None}
_CACHE_TTL_SECONDS = 120.0
_APPLYING = False


def _file_sha256(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_git_repo() -> bool:
    return os.path.isdir(os.path.join(BASE_DIR, ".git"))


def _get_head_info() -> Dict[str, str]:
    r_sha = _run_git(["rev-parse", "--short", "HEAD"], timeout=10)
    r_full = _run_git(["rev-parse", "HEAD"], timeout=10)
    r_msg = _run_git(["log", "-1", "--pretty=format:%s"], timeout=10)
    r_date = _run_git(["log", "-1", "--pretty=format:%ci"], timeout=10)
    return {
        "short": (r_sha.stdout or "").strip() if r_sha.returncode == 0 else "",
        "full": (r_full.stdout or "").strip() if r_full.returncode == 0 else "",
        "message": (r_msg.stdout or "").strip() if r_msg.returncode == 0 else "",
        "date": (r_date.stdout or "").strip() if r_date.returncode == 0 else "",
    }


def invalidate_update_cache() -> None:
    with _CHECK_LOCK:
        _UPDATE_CACHE["ts"] = 0.0
        _UPDATE_CACHE["data"] = None


def check_github_updates(force: bool = False) -> Dict[str, Any]:
    """
    Consulta o GitHub (`origin/<UPDATE_BRANCH>`) sem alterar nada localmente.
    Retorna quantidade e lista de commits novos disponíveis.
    """
    branch = os.environ.get("A5_UPDATE_BRANCH", UPDATE_BRANCH).strip() or "main"
    now = time.monotonic()

    with _CHECK_LOCK:
        if (
            not force
            and _UPDATE_CACHE["data"] is not None
            and (now - _UPDATE_CACHE["ts"]) < _CACHE_TTL_SECONDS
        ):
            cached = dict(_UPDATE_CACHE["data"])
            cached["cached"] = True
            return cached

    if not _is_git_repo():
        return {
            "success": False,
            "has_update": False,
            "behind_count": 0,
            "branch": branch,
            "repo": f"{GITHUB_USER}/{GITHUB_REPO_NAME}",
            "commits": [],
            "error": "Repositório Git não encontrado nesta instalação.",
            "checked_at": datetime.now().isoformat(),
        }

    head_info = _get_head_info()
    try:
        fetch_res = _run_git(["fetch", "origin", branch], timeout=25)
        if fetch_res.returncode != 0:
            err_msg = (fetch_res.stderr or fetch_res.stdout or "Falha ao consultar o GitHub.").strip()
            return {
                "success": False,
                "has_update": False,
                "behind_count": 0,
                "branch": branch,
                "repo": f"{GITHUB_USER}/{GITHUB_REPO_NAME}",
                "current_commit": head_info["short"],
                "current_message": head_info["message"],
                "commits": [],
                "error": err_msg[:300],
                "checked_at": datetime.now().isoformat(),
            }

        remote_ref = f"origin/{branch}"
        r_remote = _run_git(["rev-parse", "--short", remote_ref], timeout=10)
        remote_short = (r_remote.stdout or "").strip() if r_remote.returncode == 0 else ""

        r_log = _run_git(
            ["log", f"HEAD..{remote_ref}", "--pretty=format:%h|%s|%an|%ci", "-n", "20"],
            timeout=15,
        )
        commits = []
        if r_log.returncode == 0:
            for line in (r_log.stdout or "").splitlines():
                parts = line.split("|", 3)
                if len(parts) == 4:
                    # Ignora commits puramente de backup automático do banco se o usuário quiser ver código,
                    # mas mantém visível caso haja commits de código; aqui listamos todos e marcamos o tipo.
                    msg = parts[1].strip()
                    commits.append({
                        "hash": parts[0].strip(),
                        "message": msg,
                        "author": parts[2].strip(),
                        "date": parts[3].strip(),
                        "is_backup": msg.lower().startswith("backup nuvem banco de dados"),
                    })

        # Só notifica atualização quando existir pelo menos 1 commit que NÃO seja mero backup do banco
        code_commits = [c for c in commits if not c["is_backup"]]
        behind_count = len(code_commits)

        result = {
            "success": True,
            "has_update": behind_count > 0,
            "behind_count": behind_count,
            "total_remote_commits": len(commits),
            "branch": branch,
            "repo": f"{GITHUB_USER}/{GITHUB_REPO_NAME}",
            "current_commit": head_info["short"],
            "current_message": head_info["message"],
            "remote_commit": remote_short,
            "commits": code_commits[:10],
            "applying": _APPLYING,
            "checked_at": datetime.now().isoformat(),
            "cached": False,
        }

        with _CHECK_LOCK:
            _UPDATE_CACHE["ts"] = time.monotonic()
            _UPDATE_CACHE["data"] = dict(result)
        return result

    except Exception as exc:
        logger.warning("Erro ao verificar atualizações no GitHub: %s", exc)
        return {
            "success": False,
            "has_update": False,
            "behind_count": 0,
            "branch": branch,
            "repo": f"{GITHUB_USER}/{GITHUB_REPO_NAME}",
            "current_commit": head_info["short"],
            "commits": [],
            "error": str(exc)[:300],
            "checked_at": datetime.now().isoformat(),
        }


def _schedule_process_restart(delay_seconds: float = 1.5) -> None:
    """Encerra o processo após enviar a resposta HTTP para o Docker/BAT reiniciar com o código novo."""
    def _restart_worker():
        time.sleep(delay_seconds)
        logger.info("Reiniciando processo após atualização via GitHub...")
        os._exit(0)

    threading.Thread(target=_restart_worker, name="A5UpdateRestart", daemon=True).start()


def apply_github_update(actor: str = "Admin", auto_restart: bool = True) -> Dict[str, Any]:
    """
    Aplica a atualização pendente do GitHub protegendo 100% do banco SQLite.
    """
    global _APPLYING
    branch = os.environ.get("A5_UPDATE_BRANCH", UPDATE_BRANCH).strip() or "main"

    if not _is_git_repo():
        return {"success": False, "error": "Repositório Git não encontrado nesta instalação."}

    if not _APPLY_LOCK.acquire(blocking=False):
        return {"success": False, "error": "Uma atualização já está em andamento. Aguarde concluir."}

    _APPLYING = True
    try:
        # 1. Backup de segurança obrigatório antes de tocar no código
        backup_file = perform_daily_backup(force=True)
        logger.info("Backup pré-atualização gerado por %s: %s", actor, backup_file)

        req_path = os.path.join(BASE_DIR, "requirements.txt")
        req_hash_before = _file_sha256(req_path)

        # 2. Se o banco reside dentro do repositório (Windows/local), cria snapshot SHA-256 fora do repo
        db_inside_repo = False
        try:
            db_inside_repo = os.path.commonpath([os.path.realpath(DB_PATH), os.path.realpath(BASE_DIR)]) == os.path.realpath(BASE_DIR)
        except ValueError:
            db_inside_repo = False

        guard_state_dir = None
        if db_inside_repo and os.path.isfile(DB_PATH):
            from .. import db_guard
            guard_state_dir = Path(tempfile.mkdtemp(prefix="a5_web_update_guard_"))
            db_guard.checkpoint_and_snapshot(Path(DB_PATH), guard_state_dir)

        try:
            # 3. Atualiza o código para origin/<branch>
            fetch_res = _run_git(["fetch", "origin", branch], timeout=45)
            if fetch_res.returncode != 0:
                err_msg = (fetch_res.stderr or fetch_res.stdout or "Falha no git fetch.").strip()
                return {"success": False, "error": f"Falha ao baixar do GitHub: {err_msg[:300]}"}

            reset_res = _run_git(["reset", "--hard", f"origin/{branch}"], timeout=45)
            if reset_res.returncode != 0:
                err_msg = (reset_res.stderr or reset_res.stdout or "Falha no git reset.").strip()
                return {"success": False, "error": f"Falha ao aplicar código novo: {err_msg[:300]}"}

            ep_path = os.path.join(BASE_DIR, "docker-entrypoint.sh")
            if os.path.isfile(ep_path):
                try:
                    os.chmod(ep_path, 0o755)
                except OSError:
                    pass
        finally:
            # 4. Restaura o banco intacto se ele estava dentro do repo
            if guard_state_dir is not None:
                from .. import db_guard
                db_guard.restore_snapshot(Path(DB_PATH), guard_state_dir)
                db_guard.verify_post_init(Path(DB_PATH), guard_state_dir)

        # 5. Instala novas dependências se requirements.txt mudou
        pip_updated = False
        req_hash_after = _file_sha256(req_path)
        if req_hash_after and req_hash_after != req_hash_before:
            pip_res = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-r", req_path],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if pip_res.returncode != 0:
                logger.warning("Aviso ao atualizar pip requirements: %s", (pip_res.stderr or "")[:300])
            else:
                pip_updated = True

        new_head = _get_head_info()
        invalidate_update_cache()

        # Notifica todas as abas autenticadas que o servidor está reiniciando
        try:
            from ..realtime import _emit_safe
            _emit_safe(
                "system_restarting",
                {
                    "actor": actor,
                    "commit": new_head["short"],
                    "message": "Sistema atualizado! Reiniciando servidor...",
                },
                to="staff",
            )
        except Exception:
            pass

        if auto_restart:
            _schedule_process_restart(1.5)

        return {
            "success": True,
            "restarting": bool(auto_restart),
            "commit": new_head["short"],
            "commit_message": new_head["message"],
            "pip_updated": pip_updated,
            "db_protected_outside_repo": not db_inside_repo,
            "message": f"Atualização aplicada ({new_head['short']}). Reiniciando servidor...",
        }
    except Exception as exc:
        logger.error("Erro ao aplicar atualização via GitHub: %s", exc, exc_info=True)
        return {"success": False, "error": f"Erro ao aplicar atualização: {exc}"}
    finally:
        _APPLYING = False
        _APPLY_LOCK.release()
