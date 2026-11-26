"""Rotas administrativas de sistema: atualização controlada via GitHub e ingestão remota de PDFs."""
from __future__ import annotations

import hmac
import os
import uuid
from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from ..auth import get_current_user, require_api_roles
from ..config import ENTRADA_EXTERNOS_DIR, ENTRADA_PDFS_DIR, PDF_INGEST_TOKEN
from ..errors import ApiError
from ..services.updater import apply_github_update, check_github_updates

bp = Blueprint("api_system", __name__, url_prefix="/api")


@bp.route("/system/update-status", methods=["GET"])
@require_api_roles("admin_recepcao", "master")
def api_system_update_status():
    """Verifica se há novos commits no GitHub sem alterar o servidor."""
    force = request.args.get("force", "").strip().lower() in ("1", "true", "yes")
    status = check_github_updates(force=force)
    return jsonify(status)


@bp.route("/system/apply-update", methods=["POST"])
@require_api_roles("admin_recepcao", "master")
def api_system_apply_update():
    """Aplica atualização pendente do GitHub (com backup automático do banco) e reinicia o servidor."""
    user = get_current_user() or {}
    actor = user.get("display_name") or user.get("username") or "Admin"
    auto_restart = not bool(current_app.config.get("TESTING"))
    res = apply_github_update(actor=actor, auto_restart=auto_restart)
    return jsonify(res), (200 if res.get("success") else 500)


def _is_authorized_for_pdf_ingest() -> bool:
    """Aceita sessão autenticada (admin_recepcao/master) OU header X-A5-Ingest-Token configurado."""
    user = get_current_user()
    if user and user.get("role") in ("admin_recepcao", "master"):
        return True

    expected = os.environ.get("A5_PDF_INGEST_TOKEN", PDF_INGEST_TOKEN).strip()
    provided = (request.headers.get("X-A5-Ingest-Token") or "").strip()
    if expected and provided and hmac.compare_digest(provided, expected):
        return True
    return False


@bp.route("/ingest-pdf", methods=["POST"])
def api_ingest_pdf():
    """
    Recebe um PDF do Teorema ERP enviado pelo agente da recepção (ou upload manual no /admin)
    e dispara imediatamente o mesmo fluxo do pdf_watcher (`oficina` ou `externo`).
    """
    if not _is_authorized_for_pdf_ingest():
        return jsonify({"success": False, "error": "Token ou sessão inválida para envio de PDF."}), 401

    pdf_file = request.files.get("file") or request.files.get("pdf")
    if not pdf_file or not pdf_file.filename:
        raise ApiError("Nenhum arquivo PDF enviado.", status=400)

    orig_name = secure_filename(os.path.basename(pdf_file.filename))
    if not orig_name.lower().endswith(".pdf"):
        raise ApiError("Apenas arquivos .pdf são aceitos.", status=400)

    raw_bytes = pdf_file.read()
    if not raw_bytes or len(raw_bytes) > 20 * 1024 * 1024:
        raise ApiError("Arquivo PDF vazio ou excede o limite de 20 MB.", status=400)
    if not raw_bytes.lstrip().startswith(b"%PDF-"):
        raise ApiError("O arquivo enviado não possui cabeçalho PDF válido.", status=400)

    kind = (request.form.get("kind") or request.args.get("kind") or "oficina").strip().lower()
    if kind not in ("oficina", "externo"):
        raise ApiError("Parâmetro 'kind' deve ser 'oficina' ou 'externo'.", status=400)

    target_dir = ENTRADA_EXTERNOS_DIR if kind == "externo" else ENTRADA_PDFS_DIR
    os.makedirs(target_dir, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex[:8]}_{orig_name}"
    dest_path = os.path.join(target_dir, unique_name)
    tmp_path = f"{dest_path}.part"
    with open(tmp_path, "wb") as f:
        f.write(raw_bytes)
    os.replace(tmp_path, dest_path)

    from ..services.pdf_watcher import process_external_pdf_file, process_pdf_file

    processed = process_external_pdf_file(dest_path) if kind == "externo" else process_pdf_file(dest_path)
    return jsonify({
        "success": True,
        "processed": bool(processed),
        "kind": kind,
        "filename": orig_name,
    }), 200
