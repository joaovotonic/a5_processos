"""API REST de Autenticação Multi-Perfil e Gestão de Acessos."""
from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from ..auth import (
    authenticate_user,
    check_login_rate_limit,
    clear_login_failures,
    ensure_users_table,
    get_current_user,
    get_default_password_warnings,
    get_director_setup_status,
    home_for_role,
    login_user_session,
    logout_user_session,
    record_login_failure,
    require_api_roles,
)
from ..config import PORT, TUNNEL_MODE
from ..database import connect
from ..utils import get_local_ip, json_body, resolve_public_base_url

bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")


@bp.route("/me", methods=["GET"])
def auth_me():
    user = get_current_user()
    first_done, saved_dir_user = get_director_setup_status()
    pw_warn = get_default_password_warnings(user)
    return jsonify({
        "authenticated": bool(user),
        "user": user,
        "director_first_access_done": first_done,
        "director_saved_user": saved_dir_user,
        "using_default_password": pw_warn["using_default_password"],
        "default_password_users": pw_warn["default_password_users"],
        "config": {
            "public_url": resolve_public_base_url(),
            "local_ip": get_local_ip(),
            "port": PORT,
            "tunnel_mode": TUNNEL_MODE,
        },
    })


@bp.route("/login", methods=["POST"])
def auth_login():
    allowed, retry_after = check_login_rate_limit("login")
    if not allowed:
        return jsonify({
            "success": False,
            "error": f"Muitas tentativas de login. Aguarde {retry_after}s e tente novamente.",
        }), 429

    data = json_body()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    user = authenticate_user(username, password)
    if not user:
        record_login_failure("login")
        return jsonify({"success": False, "error": "Usuário ou senha incorretos."}), 401

    clear_login_failures("login")
    login_user_session(user)
    return jsonify({
        "success": True,
        "user": user,
        "redirect_to": home_for_role(user["role"]),
    })


@bp.route("/logout", methods=["POST"])
def auth_logout():
    logout_user_session()
    return jsonify({"success": True})


@bp.route("/setup-director", methods=["POST"])
def auth_setup_director():
    """Configura usuário e senha da Diretoria no Primeiro Acesso (ou redefine pelo Master)."""
    data = json_body()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    confirm_password = (data.get("confirm_password") or "").strip()

    first_done, _ = get_director_setup_status()
    current = get_current_user()
    if first_done and (not current or current.get("role") != "master"):
        return jsonify({"success": False, "error": "Primeiro acesso da Diretoria já foi concluído."}), 403

    if not username:
        return jsonify({"success": False, "error": "Digite o nome de usuário desejado."}), 400
    if not password or len(password) < 4:
        return jsonify({"success": False, "error": "A senha deve ter pelo menos 4 caracteres."}), 400
    if confirm_password and password != confirm_password:
        return jsonify({"success": False, "error": "A confirmação de senha não confere."}), 400

    hashed = generate_password_hash(password)
    with connect() as conn:
        ensure_users_table(conn)
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_user', ?)", (username,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_pass', ?)", (hashed,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_first_access_done', '1')")
        conn.execute(
            "UPDATE users SET username = ?, password_hash = ? WHERE role = 'diretoria'",
            (username, hashed),
        )

    user = {
        "username": username,
        "display_name": "Sr. Jacson (Diretoria)",
        "role": "diretoria",
        "home_route": "/diretoria",
    }
    login_user_session(user)
    return jsonify({"success": True, "user": user, "redirect_to": "/diretoria"})


@bp.route("/change-password", methods=["POST"])
@require_api_roles("admin_recepcao", "diretoria", "master")
def auth_change_password():
    current = get_current_user()
    data = json_body()
    new_password = (data.get("new_password") or "").strip()
    target_username = (data.get("username") or current["username"]).strip()

    if not new_password or len(new_password) < 4:
        return jsonify({"success": False, "error": "A nova senha deve ter pelo menos 4 caracteres."}), 400

    if target_username.lower() != current["username"].lower() and current.get("role") != "master":
        return jsonify({"success": False, "error": "Apenas o Master pode alterar a senha de outro usuário."}), 403

    hashed = generate_password_hash(new_password)
    with connect() as conn:
        ensure_users_table(conn)
        row = conn.execute("SELECT id, role FROM users WHERE LOWER(username) = LOWER(?)", (target_username,)).fetchone()
        if not row:
            return jsonify({"success": False, "error": "Usuário não encontrado."}), 404
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, row["id"]))
        if row["role"] == "diretoria":
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_pass', ?)", (hashed,))
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_user', ?)", (target_username,))
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_first_access_done', '1')")

    return jsonify({"success": True, "message": "Senha atualizada com sucesso."})


@bp.route("/users", methods=["GET"])
@require_api_roles("master")
def list_users():
    with connect() as conn:
        ensure_users_table(conn)
        rows = conn.execute(
            "SELECT id, username, display_name, role, active, created_at FROM users ORDER BY id ASC"
        ).fetchall()
    return jsonify({"success": True, "users": [dict(r) for r in rows]})
