"""Rotas de páginas web da Esteira de Produção A5 Tecnologia."""
import json
import os
from urllib.parse import quote
from flask import Blueprint, Response, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth import (
    authenticate_user,
    ensure_users_table,
    get_current_user,
    get_director_setup_status,
    home_for_role,
    login_user_session,
    logout_user_session,
    require_page_roles,
)
from ..config import FRONTEND_DIST_DIR, PORT, TUNNEL_MODE
from ..database import connect
from ..errors import NotFound
from ..services.board import enrich_card
from ..services.cards import get_card_row_by_os
from ..utils import get_local_ip, resolve_public_base_url

bp = Blueprint("pages", __name__)

CALL_TARGETS = [
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


def _get_intake_url() -> str:
    return f"{resolve_public_base_url()}/recepcao-fotos"


def _render_spa(extra_config=None):
    """Serve a SPA React compilada (frontend/dist/index.html) injetando configuração dinâmica."""
    dist_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    first_done, saved_dir_user = get_director_setup_status()
    payload = {
        "intakeUrl": _get_intake_url(),
        "localIp": get_local_ip(),
        "port": PORT,
        "tunnelMode": TUNNEL_MODE,
        "user": get_current_user(),
        "directorFirstAccessDone": first_done,
        "directorSavedUser": saved_dir_user,
        "callTargets": CALL_TARGETS,
    }
    if extra_config:
        payload.update(extra_config)

    config_script = f"<script>window.__A5_CONFIG__ = {json.dumps(payload, ensure_ascii=False)};</script>"
    if os.path.isfile(dist_index):
        with open(dist_index, "r", encoding="utf-8") as f:
            html = f.read()
        if "</head>" in html:
            html = html.replace("</head>", f"  {config_script}\n  </head>", 1)
        else:
            html = config_script + html
        return Response(html, mimetype="text/html; charset=utf-8")

    # Fallback caso frontend ainda não tenha sido compilado em ambiente de teste
    return (
        f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>{config_script}</head>"
        f"<body><div id='root'>Frontend não compilado (execute npm run build em frontend/).</div></body></html>"
    )


@bp.route("/", methods=["GET", "POST"])
def index():
    """Redireciona para o painel do usuário autenticado ou para a tela de login."""
    user = get_current_user()
    if user:
        return redirect(home_for_role(user.get("role")))
    return redirect(url_for("pages.login_page"))


@bp.route("/login", methods=["GET"])
def login_page():
    """Tela unificada de login (Jacson -> Diretoria, Priscila -> Admin, Master -> Ambos)."""
    user = get_current_user()
    if user:
        return redirect(home_for_role(user.get("role")))
    return _render_spa({"page": "login"})


@bp.route("/logout", methods=["GET"])
def logout_page():
    logout_user_session()
    return redirect(url_for("pages.login_page"))


@bp.route("/admin")
def admin_page():
    """1. Painel Kanban da Esteira de Produção (Priscila / Recepção ou Master)."""
    user, err_resp = require_page_roles("admin_recepcao", "master")
    if err_resp:
        return err_resp
    return _render_spa({"page": "admin", "user": user})


@bp.route("/recepcao-fotos")
def reception_photos_page():
    """Tela mobile para registrar fotos antes de abrir a O.S. no Teorema (pública sem login)."""
    return render_template("recepcao_fotos.html")


@bp.route("/tv")
@bp.route("/painel-tv")
def tv_page():
    """2. TV da Oficina (Painel Visual e Sonoro com YouTube e Edge-TTS - sem login)."""
    return render_template("tv.html", local_ip=get_local_ip(), port=PORT)


@bp.route("/os/<path:os_number>")
def os_mobile_page(os_number):
    """3. Tela Mobile aberta ao ler o QR Code da balança pelo celular (sem login)."""
    from ..services.esteira import get_os_status_for_mobile
    try:
        card = get_os_status_for_mobile(os_number)
    except NotFound:
        return (
            render_template(
                "os_tecnico.html",
                card={
                    "os_number": os_number,
                    "client_name": "Ordem de Serviço não encontrada",
                    "equipment_type": "Verifique o número da etiqueta",
                    "equipment_model": "",
                    "serial_number": "",
                    "reported_defect": f"Nenhuma O.S. ativa localizada para o código '{os_number}'.",
                    "created_at": "",
                    "list_title": "NÃO LOCALIZADA",
                    "state": "NAO_ENCONTRADA",
                    "technicians": [],
                    "tech_name": "",
                },
                local_ip=get_local_ip(),
                port=PORT,
            ),
            404,
        )
    return render_template("os_tecnico.html", card=card, local_ip=get_local_ip(), port=PORT)


@bp.route("/diretoria", methods=["GET", "POST"])
@bp.route("/chamado", methods=["GET", "POST"])
def diretoria_page():
    """4. Painel da Diretoria do Sr. Jacson (Exclusivo para Diretoria ou Master)."""
    if request.method == "POST":
        action = request.form.get("action")
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        confirm_password = (request.form.get("confirm_password") or "").strip()

        if action == "first_access":
            if not username or not password:
                return redirect(url_for("pages.login_page"))
            if confirm_password and password != confirm_password:
                return redirect(url_for("pages.login_page"))
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
            login_user_session({
                "username": username,
                "display_name": "Sr. Jacson (Diretoria)",
                "role": "diretoria",
                "home_route": "/diretoria",
            })
            return redirect(url_for("pages.diretoria_page"))

        user = authenticate_user(username, password)
        if user and user["role"] in ("diretoria", "master"):
            login_user_session(user)
            return redirect(url_for("pages.diretoria_page"))
        return redirect(url_for("pages.login_page"))

    user, err_resp = require_page_roles("diretoria", "master")
    if err_resp:
        return err_resp

    return _render_spa({"page": "diretoria", "user": user})


@bp.route("/diretoria/logout")
def diretoria_logout():
    """Encerra a sessão da Diretoria e redireciona para o login unificado."""
    logout_user_session()
    return redirect(url_for("pages.login_page"))


@bp.route("/etiqueta/<path:os_number>")
def etiqueta_page(os_number):
    """5. Etiqueta Térmica 60x40mm com QR Code de transferência de listas (sem login)."""
    row = get_card_row_by_os(os_number)
    if not row:
        return "Ordem de Serviço não encontrada.", 404

    card = enrich_card(row)
    card["accessories"] = json.loads(card.get("accessories_json") or "[]")
    safe_os = quote(str(card["os_number"]), safe="")
    qr_url = f"{resolve_public_base_url()}/os/{safe_os}"
    return render_template("etiqueta.html", card=card, qr_url=qr_url)
