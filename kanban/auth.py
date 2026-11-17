"""Autenticação multiperfil (Priscila / Recepção, Sr. Jacson / Diretoria e Master) e guardas de API."""
from functools import wraps

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .database import connect

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


def home_for_role(role: str) -> str:
    return ROLE_HOMES.get((role or "").strip().lower(), "/login")


def ensure_users_table(cursor_or_conn):
    """Cria tabela `users` se não existir e semeia usuários padrões iniciais."""
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
        row = cursor_or_conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?)",
            (username,),
        ).fetchone()
        if not row:
            cursor_or_conn.execute(
                "INSERT INTO users (username, display_name, password_hash, role, active) VALUES (?, ?, ?, ?, 1)",
                (username, display_name, generate_password_hash(default_pw), role),
            )


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
