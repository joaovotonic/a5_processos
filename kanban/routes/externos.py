"""
Rotas HTTP para o módulo de Chamados Externos e Gestão de Rotas de Rua (A5 Tecnologia).
Suporta turnos de Manhã e Tarde, geração de rotas individuais e conjuntas,
e armazenamento automático de imagens na pasta ./rotas_imagens/.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, send_from_directory

from ..config import ROTAS_IMAGENS_DIR
from ..services.externos import (
    list_external_orders,
    create_external_order,
    update_external_order,
    delete_external_order,
    reschedule_external_orders,
    notify_director_pending_routes,
    save_route_assignments,
    get_grouped_routes,
    get_current_shift,
    format_whatsapp_route_message,
    format_whatsapp_conjunta_message,
    build_route_image_filename,
    save_route_image_file,
    list_saved_route_images,
    export_external_routes_csv,
    KNOWN_FIELD_TECHS
)
from ..realtime import _emit_safe

bp = Blueprint("externos", __name__, url_prefix="/api/externos")


@bp.route("/orders", methods=["GET"])
def get_orders():
    """Lista chamados externos com filtros opcionais de data, turno (Manhã/Tarde), status, técnico ou busca."""
    try:
        from ..services.pdf_watcher import scan_pending_input_folders
        scan_pending_input_folders()
    except Exception:
        pass
    date_filter = request.args.get("date")
    shift_filter = request.args.get("shift")
    status_filter = request.args.get("status")
    technician = request.args.get("technician")
    search = request.args.get("search")
    pending_only = request.args.get("pending_only", "").lower() in ["1", "true", "yes"]

    orders = list_external_orders(
        date_filter=date_filter,
        shift_filter=shift_filter,
        status_filter=status_filter,
        technician=technician,
        search=search,
        pending_only=pending_only
    )
    return jsonify({"success": True, "orders": orders, "count": len(orders)})


@bp.route("/orders", methods=["POST"])
def add_order():
    """Criação manual de chamado externo ou tarefa de rua pela Priscila/Admin."""
    data = request.get_json() or {}
    if not data.get("client_name") and not data.get("tasks_notes"):
        return jsonify({"success": False, "error": "Informe ao menos o Cliente ou a Descrição da Tarefa."}), 400

    if not data.get("route_shift"):
        data["route_shift"] = get_current_shift()

    order = create_external_order(data)
    _emit_safe("external_order_created", {
        "order": order,
        "message": f"Novo chamado externo O.S. {order.get('os_number', 'S/N')} cadastrado!"
    })
    return jsonify({"success": True, "order": order}), 201


@bp.route("/orders/<int:order_id>", methods=["PUT"])
def update_order(order_id):
    """Atualiza dados do chamado externo (técnico, turno, sequência, setor, notas, etc)."""
    data = request.get_json() or {}
    updated = update_external_order(order_id, data)
    if not updated:
        return jsonify({"success": False, "error": "Chamado não encontrado ou sem dados para alterar."}), 404

    _emit_safe("external_order_updated", {"order": updated})
    return jsonify({"success": True, "order": updated})


@bp.route("/orders/<int:order_id>", methods=["DELETE"])
def remove_order(order_id):
    """Exclui um chamado externo."""
    ok = delete_external_order(order_id)
    if not ok:
        return jsonify({"success": False, "error": "Chamado não encontrado."}), 404

    _emit_safe("external_order_deleted", {"order_id": order_id})
    return jsonify({"success": True, "deleted_id": order_id})


@bp.route("/orders/reschedule", methods=["POST"])
def reschedule_orders():
    """
    Transfere um ou mais chamados (ex: não atendidos) para outra data ou outro turno (tarde/amanhã).
    """
    data = request.get_json() or {}
    order_ids = data.get("order_ids") or []
    new_date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    new_shift = data.get("shift") or "tarde"

    if not order_ids:
        return jsonify({"success": False, "error": "Nenhum chamado selecionado para remarcar."}), 400

    count = reschedule_external_orders(order_ids, new_date, new_shift)
    _emit_safe("external_orders_rescheduled", {
        "order_ids": order_ids,
        "new_date": new_date,
        "new_shift": new_shift,
        "count": count
    })
    return jsonify({
        "success": True,
        "count": count,
        "new_date": new_date,
        "new_shift": new_shift
    })


@bp.route("/routes/summary", methods=["GET"])
def route_summary():
    """Retorna o quadro de rota da data e turno selecionados (agrupado por técnico e chamados sem técnico)."""
    try:
        from ..services.pdf_watcher import scan_pending_input_folders
        scan_pending_input_folders()
    except Exception:
        pass
    date_str = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    shift = request.args.get("shift") or get_current_shift()
    summary = get_grouped_routes(date_str, shift=shift)
    return jsonify({
        "success": True,
        "summary": summary,
        "current_shift": shift,
        "available_technicians": KNOWN_FIELD_TECHS
    })


@bp.route("/routes/notify-director", methods=["POST"])
def notify_director():
    """Priscila envia os chamados para o Sr. Jacson na Diretoria para o turno informado."""
    data = request.get_json() or {}
    date_str = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    shift = data.get("shift") or get_current_shift()
    res = notify_director_pending_routes(date_str, shift=shift)
    return jsonify(res)


@bp.route("/routes/save", methods=["POST"])
def save_routes():
    """Salva organização ou finaliza a rota pelo Sr. Jacson para o turno informado."""
    data = request.get_json() or {}
    route_date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    route_shift = data.get("shift") or get_current_shift()
    assignments = data.get("assignments") or []
    finalize = bool(data.get("finalize", False))
    director_name = data.get("director_name") or "Sr. Jacson"

    res = save_route_assignments(
        route_date=route_date,
        assignments=assignments,
        finalize=finalize,
        director_name=director_name,
        route_shift=route_shift
    )
    return jsonify(res)


@bp.route("/whatsapp-text", methods=["GET"])
def whatsapp_text():
    """Gera texto pronto para colar no WhatsApp de cada técnico ou conjunta."""
    date_str = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    shift = request.args.get("shift") or get_current_shift()
    technician = request.args.get("technician")
    summary = get_grouped_routes(date_str, shift=shift)

    techs = summary.get("technicians", {})

    if technician and technician.strip().upper() == "CONJUNTA":
        msg = format_whatsapp_conjunta_message(date_str, techs, shift=shift)
        return jsonify({"success": True, "technician": "CONJUNTA", "message": msg})

    if technician:
        tech_key = technician.strip().upper()
        stops = techs.get(tech_key, [])
        msg = format_whatsapp_route_message(date_str, tech_key, stops, shift=shift)
        return jsonify({"success": True, "technician": tech_key, "message": msg})

    # Se não especificou técnico, gera para todos individualmente e conjunta
    all_msgs = {}
    for t_name, stops in techs.items():
        all_msgs[t_name] = format_whatsapp_route_message(date_str, t_name, stops, shift=shift)
    all_msgs["CONJUNTA"] = format_whatsapp_conjunta_message(date_str, techs, shift=shift)

    return jsonify({"success": True, "messages": all_msgs})


@bp.route("/save-image", methods=["POST"])
def save_image():
    """
    Recebe base64 de imagem renderizada no front-end e salva na pasta ./rotas_imagens/.
    Padroniza os nomes:
    Ex: ROTA_EDSON_MANHA_04-11-2026.png, ROTA_ANTONIO_MANHA_04-11-2026.png, ROTA_CONJUNTA_MANHA_04-11-2026.png
    """
    data = request.get_json() or {}
    image_b64 = data.get("image_base64")
    if not image_b64:
        return jsonify({"success": False, "error": "Imagem não enviada."}), 400

    filename = data.get("filename")
    if not filename:
        date_str = data.get("date") or datetime.now().strftime("%d-%m-%Y")
        shift = data.get("shift") or get_current_shift()
        tech = data.get("tech") or "CONJUNTA"
        filename = build_route_image_filename(date_str, shift, tech)

    res = save_route_image_file(image_b64, filename)
    return jsonify(res)


@bp.route("/images/<path:filename>")
def serve_image(filename):
    """Serve uma imagem da pasta rotas_imagens/."""
    return send_from_directory(ROTAS_IMAGENS_DIR, filename)


@bp.route("/saved-images", methods=["GET"])
def saved_images():
    """Lista as imagens de rotas salvas no servidor."""
    images = list_saved_route_images()
    return jsonify({"success": True, "images": images, "count": len(images)})


@bp.route("/export/csv", methods=["GET"])
def export_csv():
    """Exporta histórico e rotas em formato CSV com compatibilidade total para Excel no Brasil."""
    date_filter = request.args.get("date")
    shift_filter = request.args.get("shift")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    all_records = request.args.get("all", "").lower() in ["1", "true", "yes"]

    if all_records:
        date_filter = None
        date_from = None
        date_to = None
    elif not date_filter and not (date_from and date_to):
        date_filter = datetime.now().strftime("%Y-%m-%d")

    csv_data = export_external_routes_csv(
        date_filter=date_filter,
        shift_filter=shift_filter,
        date_from=date_from,
        date_to=date_to
    )

    filename_suffix = date_filter or (f"{date_from}_a_{date_to}" if date_from else "completo")
    if shift_filter:
        filename_suffix += f"_{shift_filter}"
    filename = f"rotas_externos_{filename_suffix}.csv"

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )


@bp.route("/history", methods=["GET"])
def route_history():
    """Retorna listagem de datas com rotas já cadastradas para histórico."""
    from ..database import connect
    with connect() as conn:
        rows = conn.execute("""
            SELECT 
                route_date,
                route_shift,
                COUNT(*) as total_orders,
                COUNT(DISTINCT technician) as total_techs,
                GROUP_CONCAT(DISTINCT technician) as techs_list,
                MAX(status) as status
            FROM external_orders
            WHERE route_date != ''
            GROUP BY route_date, route_shift
            ORDER BY route_date DESC, route_shift ASC
            LIMIT 60
        """).fetchall()
        history = [dict(r) for r in rows]

    return jsonify({"success": True, "history": history})
