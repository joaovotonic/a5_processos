"""Rotas de páginas web (telas do sistema)."""
import json

from flask import Blueprint, redirect, render_template, request, url_for

from ..config import PORT
from ..database import connect
from ..services.board import enrich_card
from ..services.cards import get_card_row_by_os
from ..utils import get_local_ip

bp = Blueprint("pages", __name__)


@bp.route("/", methods=["GET", "POST"])
def index():
    """Redireciona a raiz para o painel da recepção."""
    return redirect(url_for("pages.admin_page"))


@bp.route("/admin")
def admin_page():
    """1. Rota Admin / Recepção (Operado pela Priscila)."""
    return render_template("admin.html", local_ip=get_local_ip(), port=PORT)


@bp.route("/tv")
@bp.route("/painel-tv")
def tv_page():
    """2. Rota TV Oficina (Dashboard Visual e Sonoro Dark Mode Glassmorphism)."""
    return render_template("tv.html", local_ip=get_local_ip(), port=PORT)


@bp.route("/saida")
def saida_page():
    """3. Rota Bancada Mobile (Acessada via QR Code pelos celulares dos técnicos)."""
    os_num = request.args.get("os", "").strip()
    return render_template("saida.html", os_number=os_num, local_ip=get_local_ip())


@bp.route("/scanner")
def scanner_page():
    """Rota Mobile PWA de Leitura de QR Code na Esteira de Produção pelos técnicos."""
    with connect() as conn:
        tech_rows = conn.execute("SELECT title FROM lists WHERE is_tech = 1 ORDER BY position ASC").fetchall()
    technicians = []
    for r in tech_rows:
        t = r["title"].replace("TEC. ", "").strip()
        if t and t not in technicians:
            technicians.append(t)
    # Lista de técnicos padrão se banco estiver zerado
    if not technicians:
        technicians = ["Enzo Gabriel", "Guilherme", "Wisley", "João Otoni", "Iago", "ANTONIO", "SR. JACSON"]
    return render_template("scanner.html", technicians=technicians, local_ip=get_local_ip(), port=PORT)


@bp.route("/recepcao")
@bp.route("/recepcao-fotos")
def recepcao_fotos_page():
    """Rota Mobile da Recepção (Priscila) para tirar fotos e cadastrar cliente via CNPJ antes do Teorema."""
    return render_template("recepcao_fotos.html", local_ip=get_local_ip(), port=PORT)


@bp.route("/comprovante-entrada/<int:entry_id>")
def comprovante_entrada_page(entry_id):
    """Comprovante oficial de entrega em balcão (estilo O.S. Teorema em A4) para assinatura do cliente."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM pending_entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        return "Pré-entrada não encontrada.", 404
    entry = dict(row)
    entry["accessories"] = json.loads(entry.get("accessories_json") or "[]")
    entry["photos"] = json.loads(entry.get("photos_json") or "[]")
    return render_template("comprovante_entrada.html", entry=entry, is_os=False)


@bp.route("/comprovante-os/<path:os_number>")
def comprovante_os_page(os_number):
    """Comprovante oficial de O.S. (estilo Teorema em A4) com o número oficial do Teorema."""
    row = get_card_row_by_os(os_number)
    if not row:
        return "O.S. não encontrada.", 404
    card = enrich_card(row)
    card["accessories"] = json.loads(card.get("accessories_json") or "[]")
    return render_template("comprovante_entrada.html", entry=card, is_os=True)


@bp.route("/consulta")
def consulta_page():
    """4. Rota Consulta Rápida (Para balcão e vendedores, sem permissão de edição)."""
    return render_template("consulta.html")


@bp.route("/gerencia")
def gerencia_page():
    """5. Rota Gerência & Histórico (Métricas, gráficos, ranking e backups)."""
    return render_template("gerencia.html")


@bp.route("/diretoria")
@bp.route("/chamado")
def diretoria_page():
    """6. Rota Painel da Diretoria do Sr. Jacson (Intercom na TV + Relatório Executivo de Produtividade e Tempos)."""
    with connect() as conn:
        tech_rows = conn.execute("SELECT title FROM lists WHERE is_tech = 1 ORDER BY position ASC").fetchall()
    technicians = []
    for r in tech_rows:
        t = r["title"].replace("TEC. ", "").strip()
        if t and t not in technicians:
            technicians.append(t)
    if not technicians:
        technicians = ["Enzo Gabriel", "Guilherme", "Wisley", "João Otoni", "Iago", "ANTONIO"]
    return render_template("diretoria.html", technicians=technicians, local_ip=get_local_ip(), port=PORT)


@bp.route("/apresentacao")
def apresentacao_page():
    """7. Apresentação Executiva Comercial do Sistema A5 Kanban para o Sr. Jacson."""
    return render_template("apresentacao.html", local_ip=get_local_ip(), port=PORT)


@bp.route("/etiqueta/<path:os_number>")
def etiqueta_page(os_number):
    """Gera a visualização de impressão térmica 60x40mm com QR Code da O.S."""
    row = get_card_row_by_os(os_number)
    if not row:
        return "Ordem de Serviço não encontrada.", 404

    card = enrich_card(row)
    card["accessories"] = json.loads(card.get("accessories_json") or "[]")
    qr_url = f"http://{get_local_ip()}:{PORT}/scanner?os={card['os_number']}"
    return render_template("etiqueta.html", card=card, qr_url=qr_url)


@bp.route("/folha/<path:os_number>")
def folha_page(os_number):
    """Visualização/impressão da Folha Digital de Orçamento e Serviço (espelho da folha física)."""
    row = get_card_row_by_os(os_number)
    if not row:
        return "Ordem de Serviço não encontrada.", 404

    card = enrich_card(row)
    return render_template("folha.html", card=card)

