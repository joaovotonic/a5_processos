"""API REST das colunas (listas) do quadro."""
from flask import Blueprint, jsonify, request

from .. import realtime
from ..auth import get_current_user, require_api_roles
from ..services import lists as lists_service
from ..services.board import DEFAULT_FINISHED_BOARD_LIMIT, get_full_board, sanitize_board_for_tv
from ..utils import get_text, json_body, to_int

bp = Blueprint("api_lists", __name__, url_prefix="/api")


@bp.route("/board", methods=["GET"])
def get_board():
    """Retorna todos os dados do quadro Kanban (sanitizado se sem login, completo para equipe autenticada)."""
    try:
        from ..services.pdf_watcher import scan_pending_input_folders
        scan_pending_input_folders()
    except Exception:
        pass
    all_finished = request.args.get("all_finished", "").strip().lower() in ("1", "true", "yes")
    user = get_current_user()
    if user:
        board = get_full_board(finished_limit=None if all_finished else DEFAULT_FINISHED_BOARD_LIMIT)
        return jsonify(board)
    board = get_full_board(finished_limit=0)
    return jsonify(sanitize_board_for_tv(board))


@bp.route("/lists", methods=["POST"])
@require_api_roles("admin_recepcao", "master")
def create_list():
    """Cria uma nova lista/coluna dinamicamente (+ Adicionar outra lista)."""
    data = json_body()
    lists_service.create_list(get_text(data, "title").upper(), bool(data.get("is_tech")))
    return jsonify({"success": True, "board": realtime.broadcast_board()})


@bp.route("/lists/<int:list_id>", methods=["PUT"])
@require_api_roles("admin_recepcao", "master")
def rename_list(list_id):
    """Renomeia uma lista existente."""
    lists_service.rename_list(list_id, get_text(json_body(), "title").upper())
    return jsonify({"success": True, "board": realtime.broadcast_board()})


@bp.route("/lists/<int:list_id>", methods=["DELETE"])
@require_api_roles("admin_recepcao", "master")
def delete_list(list_id):
    """Remove uma lista vazia."""
    lists_service.delete_list(list_id)
    return jsonify({"success": True, "board": realtime.broadcast_board()})


@bp.route("/lists/reorder", methods=["POST"])
@require_api_roles("admin_recepcao", "master")
def reorder_lists():
    """Salva a nova ordem das colunas quando arrastadas no painel Admin."""
    raw_ids = json_body().get("list_ids") or []
    ordered_ids = [lid for lid in (to_int(x) for x in raw_ids) if lid is not None]
    lists_service.reorder_lists(ordered_ids)
    realtime.broadcast_board()
    return jsonify({"success": True})

