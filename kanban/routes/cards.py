"""API REST das Ordens de Serviço (cartões), orçamento digital, catálogo Toledo, finalização e cronômetro."""
from flask import Blueprint, jsonify, request

from .. import realtime, rules
from ..config import DEFAULT_EQUIPMENT_TYPE
from ..errors import ApiError
from ..services import cards as cards_service
from ..services.parts import search_parts
from ..utils import get_text, is_checked, json_body, request_data, to_float, to_int

bp = Blueprint("api_cards", __name__, url_prefix="/api")


@bp.route("/parts/search", methods=["GET"])
def api_search_parts():
    """Busca instantânea nos 2.662 códigos e descritivos da Matriz de Peças Toledo."""
    q = request.args.get("q", "").strip()
    limit = to_int(request.args.get("limit"), 30) or 30
    return jsonify({"parts": search_parts(q, limit=min(limit, 100))})


@bp.route("/scales/search", methods=["GET"])
def api_search_scales():
    """Busca rápida no catálogo e banco de dados de modelos de balanças e divisões."""
    from ..services.scales import search_scale_models
    q = request.args.get("q", "").strip()
    limit = to_int(request.args.get("limit"), 25) or 25
    return jsonify({"scales": search_scale_models(q, limit=min(limit, 50))})



from ..services import clients as clients_service


@bp.route("/cnpj/<path:cnpj>", methods=["GET"])
def lookup_cnpj(cnpj):
    """Consulta CNPJ em tempo real na Receita Federal (via BrasilAPI) com cache no banco local."""
    data = clients_service.fetch_cnpj_info(cnpj)
    if "error" in data:
        return jsonify({"success": False, "error": data["error"]}), 400
    return jsonify({"success": True, "source": data.get("source"), "client": data.get("data")})


@bp.route("/clients/search", methods=["GET"])
def search_clients():
    """Autocompletar de clientes cadastrados por Nome, Fantasia, CNPJ ou Telefone."""
    q = request.args.get("q", "").strip()
    return jsonify({"clients": clients_service.search_clients(q)})


@bp.route("/clients", methods=["POST"])
def save_client():
    """Salva ou atualiza os dados de um cliente manualmente."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    client = clients_service.save_or_update_client(payload)
    return jsonify({"success": True, "client": client})


@bp.route("/pending-entries", methods=["GET"])
def get_pending_entries():
    """Lista as pré-entradas de fotos tiradas na recepção aguardando geração de O.S. no Teorema."""
    return jsonify({"pending_entries": cards_service.list_pending_entries()})


@bp.route("/pending-entries", methods=["POST"])
def create_pending_entry():
    """Salva fotos tiradas pela Priscila no celular (/recepcao-fotos) com os dados de CNPJ, Cliente e Acessórios."""
    form = request.form
    fields = {
        "entry_id": form.get("entry_id"),
        "client_name": get_text(form, "client_name").upper(),
        "cnpj_cpf": get_text(form, "cnpj_cpf"),
        "trade_name": get_text(form, "trade_name").upper(),
        "phone": get_text(form, "phone"),
        "email": get_text(form, "email"),
        "address": get_text(form, "address"),
        "city_state": get_text(form, "city_state"),
        "accessories_json": form.get("accessories_json", "[]"),
        "equipment_type": get_text(form, "equipment_type", DEFAULT_EQUIPMENT_TYPE),
        "equipment_model": get_text(form, "equipment_model"),
        "serial_number": get_text(form, "serial_number"),
        "reported_defect": get_text(form, "reported_defect"),
        "previous_service": get_text(form, "previous_service"),
    }
    entry = cards_service.create_pending_entry(fields, request.files.getlist("entry_photos"))
    board = realtime.broadcast_board()
    return jsonify({"success": True, "entry": entry, "board": board})


@bp.route("/pending-entries/<int:entry_id>", methods=["DELETE"])
def delete_pending_entry(entry_id):
    """Remove uma pré-entrada de fotos da recepção."""
    cards_service.delete_pending_entry(entry_id)
    board = realtime.broadcast_board()
    return jsonify({"success": True, "board": board})


@bp.route("/cards", methods=["POST"])
def create_card():
    """
    Cria uma nova Ordem de Serviço (O.S.) pela Recepção (Priscila).
    Aceita multipart/form-data com fotos de entrada, Serviço Feito Anteriormente
    e vínculo automático com fotos de pré-entrada tiradas no celular antes do Teorema.
    """
    form = request.form
    fields = {
        "os_number": get_text(form, "os_number"),
        "client_name": get_text(form, "client_name").upper(),
        "cnpj_cpf": get_text(form, "cnpj_cpf"),
        "trade_name": get_text(form, "trade_name").upper(),
        "phone": get_text(form, "phone"),
        "email": get_text(form, "email"),
        "address": get_text(form, "address"),
        "city_state": get_text(form, "city_state"),
        "accessories_json": form.get("accessories_json", "[]"),
        "equipment_type": get_text(form, "equipment_type", DEFAULT_EQUIPMENT_TYPE),
        "equipment_model": get_text(form, "equipment_model"),
        "serial_number": get_text(form, "serial_number"),
        "shelf_location": get_text(form, "shelf_location"),
        "reported_defect": get_text(form, "reported_defect"),
        "previous_service": get_text(form, "previous_service"),
    }
    card, target_list = cards_service.create_card(
        fields,
        list_id=form.get("list_id"),
        labels_json=form.get("labels_json", "[]"),
        photo_files=request.files.getlist("entry_photos"),
        pending_entry_id=form.get("pending_entry_id"),
    )

    board = realtime.broadcast_board()

    # Se já entrou direto em ORÇAMENTOS ou APROVADAS, avisa a TV da oficina!
    stage = rules.arrival_stage(target_list)
    if stage:
        realtime.announce_arrival(card, stage, intro="Atenção oficina.")

    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/cards/<path:os_number>", methods=["GET"])
def get_card_by_os(os_number):
    """Busca os detalhes completos de uma O.S. específica (usado no QR Code /saida e modal)."""
    return jsonify(cards_service.get_card_details(os_number))


@bp.route("/cards/<int:card_id>/move", methods=["POST"])
def move_card(card_id):
    """
    Move um cartão de uma coluna para outra (Drag-and-Drop da Priscila ou clique rápido)
    e dispara os gatilhos sonoros e visuais na TV da Oficina.
    """
    data = json_body()
    raw_ids = data.get("ordered_card_ids")
    ordered_ids = None
    if isinstance(raw_ids, list):
        ordered_ids = [cid for cid in (to_int(x) for x in raw_ids) if cid is not None]

    actor = data.get("actor") or "Recepção"
    card, new_list, list_changed = cards_service.move_card(
        card_id,
        target_list_id=to_int(data.get("target_list_id")),
        new_position=to_int(data.get("new_position"), 0),
        actor=actor,
        ordered_card_ids=ordered_ids,
    )

    board = realtime.broadcast_board()

    if list_changed:
        stage = rules.arrival_stage(new_list)
        if stage:
            realtime.announce_arrival(card, stage, intro="Atenção.")
        elif rules.is_finished_list(new_list):
            realtime.announce_finished_on_board(card, actor, board["stats"]["finished_today"])

    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/cards/<int:card_id>/approve-quote", methods=["POST"])
def approve_quote(card_id):
    """Aprova o orçamento da O.S., move para APROVADAS e libera a tela de finalização no QR Code."""
    data = json_body()
    actor = data.get("actor") or "Priscila (Recepção)"
    card = cards_service.approve_card_quote(card_id, actor=actor)
    board = realtime.broadcast_board()
    realtime.announce_arrival(card, "APROVADA", intro="Atenção.")
    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/cards/<int:card_id>/reopen-quote", methods=["POST"])
def reopen_quote(card_id):
    """Reabre o orçamento de uma O.S. para edição (liberado pela Recepção)."""
    data = json_body()
    actor = data.get("actor") or "Priscila (Recepção)"
    card = cards_service.reopen_card_quote(card_id, actor=actor)
    board = realtime.broadcast_board()
    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/cards/<int:card_id>/request-reopen", methods=["POST"])
def request_reopen_quote(card_id):
    """Solicita à Recepção (Priscila) a liberação para reabrir/editar o orçamento no celular."""
    data = json_body()
    actor = data.get("actor") or "Técnico (QR Mobile)"
    card = cards_service.request_reopen_card_quote(card_id, actor=actor)
    board = realtime.broadcast_board()
    realtime.notify_admin({
        "type": "reopen_request",
        "card_id": card["id"],
        "os_number": card["os_number"],
        "client_name": card["client_name"],
        "tech_name": card.get("reopen_requested_by") or actor,
        "message": f"🔔 Pedido de Reabertura! {card.get('reopen_requested_by') or actor} solicita liberação para editar o orçamento da O.S. {card['os_number']} ({card['client_name']}).",
    })
    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/cards/<int:card_id>/deny-reopen", methods=["POST"])
def deny_reopen_quote(card_id):
    """Recusa a solicitação de reabertura do orçamento."""
    data = json_body()
    actor = data.get("actor") or "Priscila (Recepção)"
    card = cards_service.deny_reopen_card_quote(card_id, actor=actor)
    board = realtime.broadcast_board()
    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/cards/<int:card_id>/send-quote", methods=["POST"])
def send_quote_route(card_id):
    """Marca que a Priscila enviou o orçamento ao cliente e move para ORÇAMENTOS ENVIADOS."""
    data = json_body()
    actor = data.get("actor") or "Priscila (Recepção)"
    card = cards_service.send_card_quote(card_id, actor=actor)
    board = realtime.broadcast_board()
    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/cards/<int:card_id>/finalize-admin", methods=["POST"])
def finalize_admin_route(card_id):
    """Move a O.S. de BALANÇAS PRONTAS para FINALIZADAS após conferência da Priscila."""
    data = json_body()
    actor = data.get("actor") or "Priscila (Recepção)"
    card = cards_service.finalize_card_admin(card_id, actor=actor)
    board = realtime.broadcast_board()
    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/cards/<int:card_id>/cancel", methods=["POST"])
def cancel_card(card_id):
    """Cancela o atendimento de uma O.S., movendo para ORÇAMENTOS NÃO AUTORIZADOS."""
    data = json_body()
    actor = data.get("actor") or "Priscila (Recepção)"
    reason = data.get("reason") or "Cancelado pela Recepção"
    card = cards_service.cancel_card(card_id, actor=actor, reason=reason)
    board = realtime.broadcast_board()
    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/cards/<int:card_id>/toggle-label", methods=["POST"])
def toggle_card_label(card_id):
    """Alterna (marca/desmarca) uma etiqueta na balança."""
    data = json_body()
    label_name = (data.get("name") or data.get("label_name") or "").strip()
    color = (data.get("color") or "").strip() or None
    actor = data.get("actor") or "Priscila (Recepção)"
    result = cards_service.toggle_card_label(card_id, label_name, color=color, actor=actor)
    return jsonify(result)


@bp.route("/cards/<int:card_id>/update", methods=["POST"])
def update_card(card_id):
    """Atualiza etiquetas, Nº da O.S., dados do cliente, anotações da Priscila, prateleira ou fotos."""
    card = cards_service.update_card(
        card_id,
        request_data(),
        request.files.getlist("entry_photos"),
        quote_photo_files=request.files.getlist("quote_photos"),
    )
    return jsonify({"success": True, "card": card, "board": realtime.broadcast_board()})


@bp.route("/cards/<int:card_id>", methods=["DELETE", "POST"])
def delete_card(card_id):
    """Remove uma O.S. cadastrada por engano (requer autorização de admin: admin / admin)."""
    data = {}
    try:
        data = request_data() or {}
    except Exception:
        data = {}

    username = (data.get("username") or data.get("login") or request.args.get("username") or request.args.get("login") or "").strip()
    password = (data.get("password") or data.get("senha") or request.args.get("password") or request.args.get("senha") or "").strip()

    if username != "admin" or password != "admin":
        raise ApiError("Acesso negado: Login ou senha incorretos para exclusão de O.S.", status=403)

    cards_service.delete_card(card_id)
    return jsonify({"success": True, "board": realtime.broadcast_board()})


@bp.route("/saida/assumir", methods=["POST"])
def claim_os_mobile():
    """
    Acionado quando o técnico lê o QR Code e escolhe seu nome:
    Move automaticamente o cartão para a coluna dele e trava o orçamento para ele.
    """
    data = request_data()
    os_number = get_text(data, "os_number")
    tech_name = get_text(data, "tech_name")
    phase = get_text(data, "phase", "quote")
    force_switch = str(data.get("force_switch", "0")).lower() in ("1", "true", "on")

    card = cards_service.claim_card_mobile(os_number, tech_name, phase=phase, force_switch=force_switch)
    board = realtime.broadcast_board()
    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/saida/orcamento", methods=["POST"])
def submit_quote_mobile():
    """
    Salva ou finaliza a Folha Digital de Orçamento preenchida pelo técnico no celular via QR Code.
    Quando finalizado, move o cartão para ANALISES FEITAS e bloqueia até aprovação do cliente.
    """
    data = request_data()
    os_number = get_text(data, "os_number")
    tech_name = get_text(data, "tech_name")
    quote_payload = data.get("quote_data_json") or data.get("quote_data") or "{}"
    finalize_flag = str(data.get("finalize", "1")).lower() not in ("0", "false")

    label_before_files = request.files.getlist("label_before_photos")
    quote_photo_files = request.files.getlist("quote_photos")
    card = cards_service.submit_quote_mobile(
        os_number,
        tech_name,
        quote_payload,
        label_before_files,
        finalize_quote=finalize_flag,
        quote_photo_files=quote_photo_files,
    )
    board = realtime.broadcast_board()
    if finalize_flag:
        eval_name = card.get("evaluator_tech") or card.get("tech_name") or tech_name or "Técnico"
        realtime.notify_admin({
            "type": "quote_done",
            "card_id": card["id"],
            "os_number": card["os_number"],
            "client_name": card["client_name"],
            "tech_name": eval_name,
            "message": f"📋 Análise Feita! O técnico {eval_name} concluiu o orçamento da O.S. {card['os_number']} ({card['client_name']}) e enviou para ANALISES FEITAS.",
        })
    return jsonify({"success": True, "card": card, "board": board})


@bp.route("/saida/finalizar", methods=["POST"])
def finish_os_mobile():
    """
    Rota acionada pelo celular do técnico (/saida) ao concluir a manutenção após aprovação:
    - Salva fotos da Etiqueta Depois e fotos da balança pronta e lacrada
    - Salva Solução, Lacre Colocado, Testes de Pesos Final e Checklist POP
    - Move o cartão automaticamente para BALANÇAS PRONTAS (para conferência da Priscila)
    - Dispara confetes, som de conquista, TTS e soma +1 no placar da TV
    """
    f = request.form
    form = {
        "os_number": get_text(f, "os_number"),
        "tech_name": get_text(f, "tech_name"),
        "pop_calibration": is_checked(f.get("pop_calibration")),
        "pop_cleaning": is_checked(f.get("pop_cleaning")),
        "inmetro_seal": get_text(f, "inmetro_seal"),
        "parts_used": get_text(f, "parts_used"),
        "root_cause": get_text(f, "root_cause"),
        "solution": get_text(f, "solution"),
        "tech_notes": get_text(f, "tech_notes"),
        "shelf_location": get_text(f, "shelf_location"),
        "weights_final_json": f.get("weights_final_json"),
    }
    card_row, final_tech = cards_service.finish_card_mobile(
        form,
        request.files.getlist("exit_photos"),
        label_after_files=request.files.getlist("label_after_photos"),
    )

    board = realtime.broadcast_board()
    realtime.announce_finished_mobile(
        form["os_number"], card_row["client_name"], final_tech,
        form["inmetro_seal"], board["stats"]["finished_today"]
    )
    realtime.notify_admin({
        "type": "tech_finished",
        "card_id": card_row["id"],
        "os_number": form["os_number"],
        "client_name": card_row["client_name"],
        "tech_name": final_tech,
        "inmetro_seal": form["inmetro_seal"],
        "message": f"✅ Balança Pronta! O técnico {final_tech} concluiu o serviço da O.S. {form['os_number']} ({card_row['client_name']}) — movida para BALANÇAS PRONTAS.",
    })
    return jsonify({"success": True, "board": board})


@bp.route("/timer/start", methods=["POST"])
def start_timer():
    """Inicia um cronômetro de estufa/teste para uma O.S."""
    data = json_body()
    os_number = get_text(data, "os_number")
    minutes = to_float(data.get("minutes", 30))
    if minutes is None:
        raise ApiError("Tempo do cronômetro inválido.")
    label = get_text(data, "label", "Estufa de Placa")

    card_row, end_time = cards_service.start_timer(os_number, minutes, label)

    realtime.broadcast_board()
    realtime.notify_timer_started(os_number, card_row["client_name"], minutes, end_time, label)
    return jsonify({"success": True, "end_time": end_time})


@bp.route("/timer/cancel", methods=["POST"])
def cancel_timer():
    """Cancela o cronômetro ativo de uma O.S."""
    data = json_body()
    os_number = get_text(data, "os_number")
    cards_service.finish_timer(os_number)
    board = realtime.broadcast_board()
    return jsonify({"success": True, "board": board})


@bp.route("/director/call", methods=["POST"])
def director_call():
    """Dispara chamado ou áudio de voz do Sr. Jacson para a TV."""
    data = json_body()
    tech_name = data.get("tech_name") or "Oficina"
    message = data.get("message") or ""
    is_urgent = bool(data.get("is_urgent", False))
    audio_base64 = data.get("audio_base64")
    sender = data.get("sender") or "Sr. Jacson"

    realtime.announce_director_call(
        tech_name=tech_name,
        message=message,
        is_urgent=is_urgent,
        audio_base64=audio_base64,
        sender=sender
    )
    return jsonify({"success": True})


@bp.route("/esteira/claim-orcamento", methods=["POST"])
def api_claim_orcamento():
    from ..services.esteira import claim_orcamento
    data = json_body()
    os_number = data.get("os_number") or ""
    tech_name = data.get("tecnico") or ""
    return jsonify(claim_orcamento(os_number, tech_name))


@bp.route("/esteira/concluir-orcamento", methods=["POST"])
def api_concluir_orcamento():
    from ..services.esteira import concluir_orcamento
    data = json_body()
    os_number = data.get("os_number") or ""
    return jsonify(concluir_orcamento(os_number))


@bp.route("/esteira/adm-enviar-cliente", methods=["POST"])
def api_adm_enviar_cliente():
    from ..services.esteira import adm_enviar_cliente
    data = json_body()
    os_number = data.get("os_number") or ""
    return jsonify(adm_enviar_cliente(os_number))


@bp.route("/esteira/adm-aprovar", methods=["POST"])
def api_adm_aprovar():
    from ..services.esteira import adm_aprovar
    data = json_body()
    os_number = data.get("os_number") or ""
    return jsonify(adm_aprovar(os_number))


@bp.route("/esteira/adm-nao-autorizar", methods=["POST"])
def api_adm_nao_autorizar():
    from ..services.esteira import adm_nao_autorizar
    data = json_body()
    os_number = data.get("os_number") or ""
    reason = data.get("reason") or ""
    return jsonify(adm_nao_autorizar(os_number, reason=reason))


@bp.route("/esteira/fechar-balanca", methods=["POST"])
def api_fechar_balanca():
    from ..services.esteira import fechar_balanca
    data = json_body()
    os_number = data.get("os_number") or ""
    tech_name = data.get("tech_name") or data.get("tecnico") or ""
    return jsonify(fechar_balanca(os_number, tech_name=tech_name))


@bp.route("/cards/<path:os_number>/advance-admin", methods=["POST"])
def api_advance_admin(os_number):
    """Avança a O.S. na esteira via ação da recepção."""
    from ..services.esteira import advance_admin_pipeline
    data = json_body()
    action = data.get("action") or ""
    return jsonify(advance_admin_pipeline(os_number, action))


@bp.route("/esteira/claim-manutencao", methods=["POST"])
def api_claim_manutencao():
    from ..services.esteira import claim_manutencao
    data = json_body()
    os_number = data.get("os_number") or ""
    tech_name = data.get("tecnico") or ""
    return jsonify(claim_manutencao(os_number, tech_name))


@bp.route("/esteira/finalizar-balanca", methods=["POST"])
def api_finalizar_balanca():
    from ..services.esteira import finalizar_balanca
    data = json_body()
    os_number = data.get("os_number") or ""
    return jsonify(finalizar_balanca(os_number))


@bp.route("/cards/<path:os_number>/delete", methods=["POST", "DELETE"])
@bp.route("/cards/<path:os_number>", methods=["DELETE"])
def api_delete_card(os_number):
    """Exclui a O.S. do sistema Kanban da A5 Tecnologia."""
    from ..services.esteira import delete_card_by_os
    return jsonify(delete_card_by_os(os_number))


@bp.route("/cards/manual", methods=["POST"])
def api_create_manual_card():
    """Cria uma O.S. (banner) manualmente direto no Kanban."""
    from ..services.esteira import create_manual_os
    data = json_body()
    return jsonify(create_manual_os(data))
