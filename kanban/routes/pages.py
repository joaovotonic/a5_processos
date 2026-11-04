"""Rotas de páginas web da Esteira de Produção A5 Tecnologia."""
import json
from flask import Blueprint, redirect, render_template, request, session, url_for

from ..config import PORT
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
    return render_template("admin.html", local_ip=get_local_ip(), port=PORT)


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
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        if username.lower() == "admin" and password == "admin":
            session["diretoria_auth"] = True
            return redirect(url_for("pages.diretoria_page"))
        return render_template("diretoria_login.html", error="Usuário ou senha incorretos. Acesso restrito à Diretoria.", port=PORT)

    if not session.get("diretoria_auth"):
        return render_template("diretoria_login.html", error=None, port=PORT)

    with connect() as conn:
        tech_rows = conn.execute("SELECT title FROM lists WHERE is_tech = 1 ORDER BY position ASC").fetchall()
    technicians = []
    for r in tech_rows:
        t = r["title"].replace("TEC. ", "").strip()
        if t and t not in technicians:
            technicians.append(t)
    if not technicians:
        technicians = ["João Otoni", "Enzo Gabriel", "Guilherme", "Wisley", "Iago", "ANTONIO"]
    return render_template("diretoria.html", technicians=technicians, local_ip=get_local_ip(), port=PORT)


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
    qr_url = f"http://{get_local_ip()}:{PORT}/os/{card['os_number']}"
    return render_template("etiqueta.html", card=card, qr_url=qr_url)
