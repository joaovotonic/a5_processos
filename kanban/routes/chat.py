"""
Rotas HTTP e eventos em tempo real para o Chat Direto entre
Recepção/Admin (Priscila) e Diretoria (Sr. Jacson).
"""
from datetime import datetime
from flask import Blueprint, request, jsonify

from ..database import connect
from ..realtime import _emit_safe

bp = Blueprint("chat", __name__, url_prefix="/api/chat")


def _format_chat_row(row) -> dict:
    d = dict(row)
    created = d.get("created_at") or ""
    time_str = ""
    date_str = ""
    if created:
        try:
            dt = datetime.fromisoformat(created)
            time_str = dt.strftime("%H:%M")
            date_str = dt.strftime("%d/%m")
        except Exception:
            time_str = created[11:16] if len(created) >= 16 else created
    d["time_str"] = time_str
    d["date_str"] = date_str
    return d


@bp.route("/messages", methods=["GET"])
def get_chat_messages():
    """Retorna histórico recente de mensagens entre Priscila e Sr. Jacson e contagem de não lidas."""
    limit = min(max(int(request.args.get("limit", 100) or 100), 10), 300)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM chat_messages
                ORDER BY id DESC
                LIMIT ?
            ) ORDER BY id ASC
            """,
            (limit,)
        ).fetchall()

        unread_jacson = conn.execute(
            "SELECT COUNT(*) as cnt FROM chat_messages WHERE sender != 'jacson' AND is_read = 0"
        ).fetchone()["cnt"]

        unread_priscila = conn.execute(
            "SELECT COUNT(*) as cnt FROM chat_messages WHERE sender != 'priscila' AND is_read = 0"
        ).fetchone()["cnt"]

    messages = [_format_chat_row(r) for r in rows]
    return jsonify({
        "success": True,
        "messages": messages,
        "unread_for_jacson": unread_jacson,
        "unread_for_priscila": unread_priscila
    })


@bp.route("/messages", methods=["POST"])
def send_chat_message():
    """Envia uma nova mensagem no chat Priscila <-> Sr. Jacson e notifica via WebSocket."""
    data = request.get_json() or {}
    sender = (data.get("sender") or "").strip().lower()
    if sender not in ("jacson", "priscila"):
        sender = "jacson" if "jacson" in (data.get("sender_name") or "").lower() else "priscila"

    default_name = "Sr. Jacson (Diretoria)" if sender == "jacson" else "Priscila (Recepção)"
    sender_name = (data.get("sender_name") or default_name).strip()
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"success": False, "error": "Digite uma mensagem para enviar."}), 400

    now_iso = datetime.now().isoformat()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO chat_messages (sender, sender_name, message, is_read, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (sender, sender_name, message, now_iso)
        )
        msg_id = cur.lastrowid
        row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (msg_id,)).fetchone()

    msg_obj = _format_chat_row(row)
    _emit_safe("chat_message_received", msg_obj)
    return jsonify({"success": True, "message": msg_obj}), 201


@bp.route("/read", methods=["POST"])
def mark_chat_read():
    """Marca as mensagens recebidas pelo visualizador ('jacson' ou 'priscila') como lidas."""
    data = request.get_json() or {}
    viewer = (data.get("viewer") or "").strip().lower()
    if viewer not in ("jacson", "priscila"):
        return jsonify({"success": False, "error": "Visualizador inválido."}), 400

    with connect() as conn:
        conn.execute(
            "UPDATE chat_messages SET is_read = 1 WHERE sender != ? AND is_read = 0",
            (viewer,)
        )

    _emit_safe("chat_messages_read", {"viewer": viewer})
    return jsonify({"success": True, "viewer": viewer})
