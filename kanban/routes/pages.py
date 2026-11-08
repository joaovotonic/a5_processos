"""Rotas de páginas web da Esteira de Produção A5 Tecnologia."""
import json
from flask import Blueprint, redirect, render_template, request, session, url_for

from ..config import PORT, TUNNEL_MODE, TUNNEL_PUBLIC_HOSTNAME
from ..database import connect
from ..services.board import enrich_card
from ..services.cards import get_card_row_by_os
from ..utils import get_local_ip

bp = Blueprint("pages", __name__)


@bp.route("/", methods=["GET", "POST"])
def index():
    """Redireciona a raiz para o painel Kanban da esteira (Priscila)."""
    return redirect(url_for("pages.admin_page"))


@bp.route("/admin")
def admin_page():
    """1. Painel Kanban da Esteira de Produção (Operado pela Priscila / Adm)."""
    intake_url = f"{request.url_root.rstrip('/')}/recepcao-fotos"
    if TUNNEL_MODE and TUNNEL_PUBLIC_HOSTNAME:
        intake_url = f"https://{TUNNEL_PUBLIC_HOSTNAME}/recepcao-fotos"
    return render_template(
        "admin.html",
        local_ip=get_local_ip(),
        port=PORT,
        intake_url=intake_url,
    )


@bp.route("/recepcao-fotos")
def reception_photos_page():
    """Tela mobile para registrar fotos antes de abrir a O.S. no Teorema."""
    return render_template("recepcao_fotos.html")


@bp.route("/tv")
@bp.route("/painel-tv")
def tv_page():
    """2. TV da Oficina (Painel Visual e Sonoro com YouTube e Edge-TTS)."""
    return render_template("tv.html", local_ip=get_local_ip(), port=PORT)


@bp.route("/os/<path:os_number>")
def os_mobile_page(os_number):
    """3. Tela Mobile aberta ao ler o QR Code da balança pelo celular."""
    from ..services.esteira import get_os_status_for_mobile
    card = get_os_status_for_mobile(os_number)
    return render_template("os_tecnico.html", card=card, local_ip=get_local_ip(), port=PORT)


@bp.route("/diretoria", methods=["GET", "POST"])
@bp.route("/chamado", methods=["GET", "POST"])
def diretoria_page():
    """4. Painel da Diretoria do Sr. Jacson (Relatórios Executivos + Chamada de Técnicos na TV)."""
    with connect() as conn:
        row_done = conn.execute("SELECT value FROM settings WHERE key = 'director_first_access_done'").fetchone()
        row_user = conn.execute("SELECT value FROM settings WHERE key = 'director_user'").fetchone()
        row_pass = conn.execute("SELECT value FROM settings WHERE key = 'director_pass'").fetchone()

    first_access_done = bool(row_done and row_done["value"] == "1")
    saved_user = row_user["value"].strip() if row_user and row_user["value"] else ""
    saved_pass = row_pass["value"].strip() if row_pass and row_pass["value"] else ""

    if request.method == "POST":
        action = request.form.get("action")
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        confirm_password = (request.form.get("confirm_password") or "").strip()

        # 1. Login mestre / admin (João) sempre aceito em qualquer modo
        if username.lower() == "admin" and password == "admin":
            session["diretoria_auth"] = True
            session["diretoria_user"] = "Administrador"
            return redirect(url_for("pages.diretoria_page"))

        # 2. Fluxo de Primeiro Acesso (Criação de usuário e senha pelo Sr. Jacson)
        if action == "first_access":
            if not username:
                return render_template(
                    "diretoria_login.html",
                    mode="setup",
                    error="Por favor, digite o nome de usuário desejado.",
                    first_access_done=first_access_done,
                    port=PORT
                )
            if not password:
                return render_template(
                    "diretoria_login.html",
                    mode="setup",
                    error="Por favor, digite uma senha para o seu acesso.",
                    first_access_done=first_access_done,
                    port=PORT
                )
            if confirm_password and password != confirm_password:
                return render_template(
                    "diretoria_login.html",
                    mode="setup",
                    error="A confirmação de senha não confere com a senha digitada.",
                    first_access_done=first_access_done,
                    port=PORT
                )

            from werkzeug.security import generate_password_hash
            hashed_pass = generate_password_hash(password)
            with connect() as conn:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_user', ?)", (username,))
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_pass', ?)", (hashed_pass,))
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('director_first_access_done', '1')")

            session["diretoria_auth"] = True
            session["diretoria_user"] = username
            return redirect(url_for("pages.diretoria_page"))

        # 3. Fluxo de Login Normal
        if saved_user and saved_pass and username.lower() == saved_user.lower():
            from werkzeug.security import check_password_hash
            if check_password_hash(saved_pass, password) or saved_pass == password:
                session["diretoria_auth"] = True
                session["diretoria_user"] = saved_user
                return redirect(url_for("pages.diretoria_page"))

        # Erro de credenciais inválidas
        target_mode = "login" if (action == "login" or first_access_done) else "setup"
        return render_template(
            "diretoria_login.html",
            mode=target_mode,
            error="Usuário ou senha incorretos. Acesso restrito à Diretoria.",
            first_access_done=first_access_done,
            port=PORT
        )

    if not session.get("diretoria_auth"):
        mode = request.args.get("mode")
        if not mode:
            mode = "login" if first_access_done else "setup"
        return render_template(
            "diretoria_login.html",
            mode=mode,
            error=None,
            first_access_done=first_access_done,
            port=PORT
        )

    call_targets = [
        {"name": "João Otoni", "role": "Técnico", "target": "João Otoni"},
        {"name": "Wisley", "role": "Técnico", "target": "Wisley"},
        {"name": "Guilherme", "role": "Técnico", "target": "Guilherme"},
        {"name": "Arthur", "role": "ADM", "target": "Arthur (ADM)"},
        {"name": "Priscila", "role": "ADM", "target": "Priscila (ADM)"},
        {"name": "Roosevelt", "role": "ADM", "target": "Roosevelt (ADM)"},
        {"name": "Iago", "role": "Técnico", "target": "Iago"},
        {"name": "Enzo", "role": "Técnico", "target": "Enzo"},
        {"name": "Edson", "role": "Técnico", "target": "Edson"},
        {"name": "Antonio", "role": "Técnico", "target": "Antonio"},
    ]
    return render_template(
        "diretoria.html",
        call_targets=call_targets,
        local_ip=get_local_ip(),
        port=PORT,
    )


@bp.route("/diretoria/logout")
def diretoria_logout():
    """Encerra a sessão da Diretoria e redireciona para a tela de login."""
    session.pop("diretoria_auth", None)
    return redirect(url_for("pages.diretoria_page"))


@bp.route("/etiqueta/<path:os_number>")
def etiqueta_page(os_number):
    """5. Etiqueta Térmica 60x40mm com QR Code de transferência de listas."""
    row = get_card_row_by_os(os_number)
    if not row:
        return "Ordem de Serviço não encontrada.", 404

    card = enrich_card(row)
    card["accessories"] = json.loads(card.get("accessories_json") or "[]")
    qr_url = url_for("pages.os_mobile_page", os_number=card["os_number"], _external=True)
    if TUNNEL_MODE and TUNNEL_PUBLIC_HOSTNAME:
        qr_url = f"https://{TUNNEL_PUBLIC_HOSTNAME}/os/{card['os_number']}"
    return render_template("etiqueta.html", card=card, qr_url=qr_url)
