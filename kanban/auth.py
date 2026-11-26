"""Autenticação multiperfil (Priscila / Recepção, Sr. Jacson / Diretoria e Master) e guardas de API."""
from collections import defaultdict
from functools import wraps
import os
import threading
import time

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .config import TUNNEL_MODE
from .database import connect

# Rate limit em memória para proteção contra força bruta em login/exclusão
_AUTH_RATE_LOCK = threading.Lock()
_AUTH_FAILURES: dict[str, list[float]] = defaultdict(list)
AUTH_RATE_WINDOW_SECONDS = 300  # 5 minutos
AUTH_RATE_MAX_FAILURES = 10


def get_client_ip() -> str:
    """Resolve IP real do cliente (respeitando proxy reverso/Cloudflare quando ativo)."""
    if TUNNEL_MODE or request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For"):
        cf_ip = (request.headers.get("CF-Connecting-IP") or "").strip()
        if cf_ip:
            return cf_ip
        xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if xff:
            return xff
    return (request.remote_addr or "unknown").strip()


def check_login_rate_limit(scope: str = "login", max_failures: int = AUTH_RATE_MAX_FAILURES, window_seconds: int = AUTH_RATE_WINDOW_SECONDS) -> tuple[bool, int]:
    """Retorna (permitido, retry_after_segundos)."""
    key = f"{scope}:{get_client_ip()}"
    now = time.monotonic()
    cutoff = now - window_seconds
    with _AUTH_RATE_LOCK:
        recent = [ts for ts in _AUTH_FAILURES.get(key, []) if ts > cutoff]
        if recent:
            _AUTH_FAILURES[key] = recent
        else:
            _AUTH_FAILURES.pop(key, None)
        if len(recent) >= max_failures:
            retry_after = max(1, int(window_seconds - (now - recent[0])))
            return False, retry_after
    return True, 0


def record_login_failure(scope: str = "login", window_seconds: int = AUTH_RATE_WINDOW_SECONDS) -> None:
    key = f"{scope}:{get_client_ip()}"
    now = time.monotonic()
    cutoff = now - window_seconds
    with _AUTH_RATE_LOCK:
        recent = [ts for ts in _AUTH_FAILURES.get(key, []) if ts > cutoff]
        recent.append(now)
        _AUTH_FAILURES[key] = recent


def clear_login_failures(scope: str = "login") -> None:
    key = f"{scope}:{get_client_ip()}"
    with _AUTH_RATE_LOCK:
        _AUTH_FAILURES.pop(key, None)


def reset_login_rate_limits() -> None:
    """Limpa contadores em memória (útil para testes automatizados)."""
    with _AUTH_RATE_LOCK:
        _AUTH_FAILURES.clear()

ROLE_HOMES = {
    "diretoria": "/diretoria",
    "admin_recepcao": "/admin",
    "master": "/admin",
}

DEFAULT_USERS = [
    ("admin", "João Otoni (Master)", "admin", "master"),
    ("priscila", "Priscila (Recepção)", "priscila123", "admin_recepcao"),
    ("jacson", "Sr. Jacson (Diretoria)", "jacson123", "diretoria"),
]

_DEFAULT_PASSWORD_ENV = {
    "admin": "A5_ADMIN_PASSWORD",
    "priscila": "A5_PRISCILA_PASSWORD",
    "jacson": "A5_JACSON_PASSWORD",
}

_KNOWN_WEAK_DEFAULTS = {
    "admin": "admin",
    "priscila": "priscila123",
    "jacson": "jacson123",
}


def home_for_role(role: str) -> str:
    return ROLE_HOMES.get((role or "").strip().lower(), "/login")


def ensure_users_table(cursor_or_conn):
    """Cria tabela `users` se não existir e semeia usuários padrões iniciais (respeitando senhas de ambiente)."""
    cursor_or_conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for username, display_name, default_pw, role in DEFAULT_USERS:
        env_key = _DEFAULT_PASSWORD_ENV.get(username, "")
        initial_pw = (os.environ.get(env_key, "") if env_key else "").strip() or default_pw
        row = cursor_or_conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?)",
            (username,),
        ).fetchone()
        if not row:
            cursor_or_conn.execute(
                "INSERT INTO users (username, display_name, password_hash, role, active) VALUES (?, ?, ?, ?, 1)",
                (username, display_name, generate_password_hash(initial_pw), role),
            )


def get_default_password_warnings(current_user: dict | None = None) -> dict:
    """
    Detecta se o usuário atual (ou qualquer conta ativa, quando Master) ainda utiliza
    uma das senhas padrão iniciais (`admin`, `priscila123`, `jacson123`).
    """
    if not current_user:
        return {"using_default_password": False, "default_password_users": []}

    current_username = (current_user.get("username") or "").strip().lower()
    is_master = current_user.get("role") == "master"

    flagged: list[dict] = []
    current_is_default = False

    with connect() as conn:
        ensure_users_table(conn)
        rows = conn.execute(
            "SELECT username, display_name, password_hash, role FROM users WHERE active = 1"
        ).fetchall()

    for row in rows:
        uname = (row["username"] or "").strip().lower()
        weak_pw = _KNOWN_WEAK_DEFAULTS.get(uname)
        if not weak_pw:
            continue
        if _verify_password(row["password_hash"], weak_pw):
            if uname == current_username:
                current_is_default = True
            if is_master or uname == current_username:
                flagged.append({
                    "username": row["username"],
                    "display_name": row["display_name"],
                    "role": row["role"],
                })

    return {
        "using_default_password": bool(current_is_default or (is_master and flagged)),
        "default_password_users": flagged,
    }


def _verify_password(stored: str, raw: str) -> bool:
    if not stored or not raw:
        return False
    if stored.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(stored, raw)
    return stored == raw


def get_director_setup_status() -> tuple[bool, str]:
    with connect() as conn:
        ensure_users_table(conn)
        row_done = conn.execute("SELECT value FROM settings WHERE key = 'director_first_access_done'").fetchone()
        row_user = conn.execute("SELECT value FROM settings WHERE key = 'director_user'").fetchone()
    done = bool(row_done and row_done["value"] == "1")
    saved_user = row_user["value"].strip() if row_user and row_user["value"] else ""
    return done, saved_user


def authenticate_user(username: str, password: str) -> dict | None:
    """Autentica um usuário na tabela `users` ou na configuração de primeiro acesso da Diretoria."""
    clean_user = (username or "").strip()
    clean_pass = (password or "").strip()
    if not clean_user or not clean_pass:
        return None

    with connect() as conn:
        ensure_users_table(conn)

        # 1. Credenciais personalizadas da Diretoria via Primeiro Acesso (settings)
        row_done = conn.execute("SELECT value FROM settings WHERE key = 'director_first_access_done'").fetchone()
        row_dir_user = conn.execute("SELECT value FROM settings WHERE key = 'director_user'").fetchone()
        row_dir_pass = conn.execute("SELECT value FROM settings WHERE key = 'director_pass'").fetchone()
        if (
            row_done
            and row_done["value"] == "1"
            and row_dir_user
            and row_dir_pass
            and clean_user.lower() == row_dir_user["value"].strip().lower()
            and _verify_password(row_dir_pass["value"].strip(), clean_pass)
        ):
            return {
                "username": row_dir_user["value"].strip(),
                "display_name": "Sr. Jacson (Diretoria)",
                "role": "diretoria",
                "home_route": "/diretoria",
            }

        # 2. Usuários persistidos na tabela `users`
        row = conn.execute(
            "SELECT id, username, display_name, password_hash, role, active FROM users WHERE LOWER(username) = LOWER(?)",
            (clean_user,),
        ).fetchone()
        if row and int(row["active"] or 0) == 1 and _verify_password(row["password_hash"], clean_pass):
            role = row["role"]
            return {
                "id": row["id"],
                "username": row["username"],
                "display_name": row["display_name"],
                "role": role,
                "home_route": home_for_role(role),
            }

    return None


def login_user_session(user: dict):
    session.clear()
    session["user"] = {
        "id": user.get("id"),
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "home_route": home_for_role(user["role"]),
    }
    if user["role"] in ("diretoria", "master"):
        session["diretoria_auth"] = True
        session["diretoria_user"] = user["display_name"]
    else:
        session.pop("diretoria_auth", None)
        session.pop("diretoria_user", None)


def logout_user_session():
    session.pop("user", None)
    session.pop("diretoria_auth", None)
    session.pop("diretoria_user", None)


def get_current_user() -> dict | None:
    user = session.get("user")
    if isinstance(user, dict) and user.get("role"):
        return user
    # Compatibilidade com testes legados que definem session["diretoria_auth"] = True diretamente
    if session.get("diretoria_auth"):
        return {
            "username": session.get("diretoria_user") or "jacson",
            "display_name": session.get("diretoria_user") or "Sr. Jacson (Diretoria)",
            "role": "diretoria",
            "home_route": "/diretoria",
        }
    return None


def require_api_roles(*allowed_roles):
    """Decorator para proteger rotas `/api/...` por perfil autenticado."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"success": False, "error": "Autenticação obrigatória."}), 401
            if allowed_roles and user.get("role") not in allowed_roles:
                return jsonify({"success": False, "error": "Sem permissão para este módulo."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_page_roles(*allowed_roles):
    """Verifica acesso a rotas de página e redireciona conforme perfil."""
    user = get_current_user()
    if not user:
        return None, redirect(url_for("pages.login_page", next=request.path))
    if allowed_roles and user.get("role") not in allowed_roles:
        return None, redirect(home_for_role(user.get("role")))
    return user, None
