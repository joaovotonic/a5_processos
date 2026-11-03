"""Regras das Ordens de Serviço (cartões): abertura, orçamento digital, aprovação, finalização e cronômetro."""
import json
import sqlite3
from datetime import datetime, timedelta

from .. import rules
from ..config import DEFAULT_EQUIPMENT_TYPE, UPLOAD_FOLDER
from ..database import connect
from ..errors import ApiError, NotFound
from ..utils import adopt_pre_entry_photos, save_os_photos, to_int
from .board import enrich_card, normalize_quote_data

RECEPTION_ACTOR = "Priscila (Recepção)"


def _now():
    return datetime.now().isoformat()


def _add_history(conn, card_id, os_number, from_list, to_list, actor, description, timestamp):
    conn.execute("""
        INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (card_id, os_number, from_list, to_list, actor, description, timestamp))


def _get_list(conn, list_id):
    return conn.execute("SELECT * FROM lists WHERE id = ?", (list_id,)).fetchone()


def _next_position(conn, list_id):
    return conn.execute(
        "SELECT COALESCE(MAX(position), -1) as m FROM cards WHERE list_id = ?", (list_id,)
    ).fetchone()["m"] + 1


def format_parts_summary(parts_items):
    """Formata a lista de peças com código Toledo para texto legível (usado no CSV e resumos)."""
    if not isinstance(parts_items, list) or not parts_items:
        return ""
    lines = []
    for item in parts_items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        desc = str(item.get("description") or "").strip()
        qty = item.get("qty") or 1
        if code and desc:
            lines.append(f"{qty}x [{code}] {desc}")
        elif desc:
            lines.append(f"{qty}x {desc}")
        elif code:
            lines.append(f"{qty}x [{code}]")
    return " | ".join(lines)


# ==============================================================================
# CONSULTAS
# ==============================================================================
def get_card_row_by_os(os_number):
    with connect() as conn:
        return conn.execute("SELECT * FROM cards WHERE os_number = ?", (os_number,)).fetchone()


def get_card_details(os_number):
    """Detalhes completos de uma O.S. com nome da coluna atual, técnicos disponíveis e histórico."""
    with connect() as conn:
        row = conn.execute("""
            SELECT c.*, l.title as list_title, l.role as list_role, l.is_tech as list_is_tech
            FROM cards c
            JOIN lists l ON c.list_id = l.id
            WHERE c.os_number = ?
        """, (os_number,)).fetchone()
        if not row:
            raise NotFound("O.S. não encontrada.")

        card = enrich_card(row)
        card["history"] = [dict(r) for r in conn.execute(
            "SELECT * FROM card_history WHERE card_id = ? ORDER BY id DESC", (card["id"],)
        ).fetchall()]
        card["tech_lists"] = [dict(r) for r in conn.execute(
            "SELECT id, title FROM lists WHERE is_tech = 1 ORDER BY position ASC"
        ).fetchall()]
    return card


# ==============================================================================
# PRÉ-ENTRADA DE FOTOS PELO CELULAR DA RECEPÇÃO (ANTES DE GERAR O.S. NO TEOREMA)
# ==============================================================================
def list_pending_entries():
    """Lista todas as pré-entradas de fotos aguardando abertura de O.S. no sistema Teorema."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM pending_entries ORDER BY id DESC").fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["photos"] = json.loads(item.get("photos_json") or "[]")
        result.append(item)
    return result


def create_pending_entry(fields, photo_files):
    """
    Salva fotos tiradas pela Priscila na recepção com os dados do Cliente e CNPJ
    (antes de gerar o número da O.S. no Teorema). Se já existir uma pré-entrada
    para o mesmo cliente (ou se `entry_id` for informado), anexa as novas fotos nela.
    """
    client_name = (fields.get("client_name") or "").strip().upper()
    if not client_name:
        raise ApiError("Informe o Nome do Cliente para anexar as fotos.")
    if not photo_files or not any(f and f.filename for f in photo_files):
        raise ApiError("Tire ou selecione pelo menos 1 foto do equipamento.")

    now_iso = _now()
    entry_id = to_int(fields.get("entry_id"))

    with connect() as conn:
        # Salva ou atualiza cliente na memória local usando a mesma conexão
        from .clients import save_or_update_client
        save_or_update_client(fields, conn=conn)

        existing = None
        if entry_id:
            existing = conn.execute("SELECT * FROM pending_entries WHERE id = ?", (entry_id,)).fetchone()
        if not existing:
            existing = conn.execute(
                "SELECT * FROM pending_entries WHERE UPPER(TRIM(client_name)) = ? ORDER BY id DESC LIMIT 1",
                (client_name,)
            ).fetchone()

        if existing:
            target_id = existing["id"]
            current_photos = json.loads(existing["photos_json"] or "[]")
            new_urls = save_os_photos(photo_files, f"PRE_{target_id}", stage="pre_entrada")
            if not new_urls:
                raise ApiError("Nenhuma foto válida foi enviada.")
            current_photos.extend(new_urls)
            conn.execute("""
                UPDATE pending_entries
                SET equipment_type = COALESCE(NULLIF(?, ''), equipment_type),
                    equipment_model = COALESCE(NULLIF(?, ''), equipment_model),
                    serial_number = COALESCE(NULLIF(?, ''), serial_number),
                    reported_defect = COALESCE(NULLIF(?, ''), reported_defect),
                    previous_service = COALESCE(NULLIF(?, ''), previous_service),
                    cnpj_cpf = COALESCE(NULLIF(?, ''), cnpj_cpf),
                    trade_name = COALESCE(NULLIF(?, ''), trade_name),
                    phone = COALESCE(NULLIF(?, ''), phone),
                    email = COALESCE(NULLIF(?, ''), email),
                    address = COALESCE(NULLIF(?, ''), address),
                    city_state = COALESCE(NULLIF(?, ''), city_state),
                    accessories_json = COALESCE(NULLIF(?, ''), accessories_json),
                    photos_json = ?
                WHERE id = ?
            """, (
                fields.get("equipment_type", ""),
                fields.get("equipment_model", ""),
                fields.get("serial_number", ""),
                fields.get("reported_defect", ""),
                fields.get("previous_service", ""),
                fields.get("cnpj_cpf", ""),
                fields.get("trade_name", ""),
                fields.get("phone", ""),
                fields.get("email", ""),
                fields.get("address", ""),
                fields.get("city_state", ""),
                fields.get("accessories_json", "[]"),
                json.dumps(current_photos),
                target_id,
            ))
        else:
            cursor = conn.execute("""
                INSERT INTO pending_entries (
                    client_name, equipment_type, equipment_model, serial_number,
                    reported_defect, previous_service, cnpj_cpf, trade_name,
                    phone, email, address, city_state, accessories_json,
                    photos_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?)
            """, (
                client_name,
                fields.get("equipment_type") or DEFAULT_EQUIPMENT_TYPE,
                fields.get("equipment_model", ""),
                fields.get("serial_number", ""),
                fields.get("reported_defect", ""),
                fields.get("previous_service", ""),
                fields.get("cnpj_cpf", ""),
                fields.get("trade_name", ""),
                fields.get("phone", ""),
                fields.get("email", ""),
                fields.get("address", ""),
                fields.get("city_state", ""),
                fields.get("accessories_json", "[]"),
                now_iso,
            ))
            target_id = cursor.lastrowid
            new_urls = save_os_photos(photo_files, f"PRE_{target_id}", stage="pre_entrada")
            if not new_urls:
                conn.execute("DELETE FROM pending_entries WHERE id = ?", (target_id,))
                raise ApiError("Nenhuma foto válida foi enviada.")
            conn.execute(
                "UPDATE pending_entries SET photos_json = ? WHERE id = ?",
                (json.dumps(new_urls), target_id)
            )

        row = conn.execute("SELECT * FROM pending_entries WHERE id = ?", (target_id,)).fetchone()

    item = dict(row)
    item["photos"] = json.loads(item.get("photos_json") or "[]")
    item["accessories"] = json.loads(item.get("accessories_json") or "[]")
    return item


def delete_pending_entry(entry_id):
    """Remove uma pré-entrada de fotos e apaga sua pasta temporária."""
    import os
    import shutil
    with connect() as conn:
        row = conn.execute("SELECT * FROM pending_entries WHERE id = ?", (entry_id,)).fetchone()
        if not row:
            raise NotFound("Pré-entrada não encontrada.")
        conn.execute("DELETE FROM pending_entries WHERE id = ?", (entry_id,))
    pre_folder = os.path.join(UPLOAD_FOLDER, f"OS_PRE_{entry_id}")
    shutil.rmtree(pre_folder, ignore_errors=True)


# ==============================================================================
# ABERTURA DE O.S. (RECEPÇÃO)
# ==============================================================================
def create_card(fields, list_id, labels_json, photo_files, pending_entry_id=None):
    """
    Cria uma nova O.S. Retorna (cartão enriquecido, coluna de destino).
    `fields` contém os campos de texto já limpos (incluindo previous_service).
    Se houver pré-entrada de fotos da Priscila (por ID ou mesmo Nome do Cliente),
    puxa automaticamente as fotos para a nova O.S. gerada no Teorema.
    """
    os_number = fields["os_number"]
    if not os_number or not fields["client_name"]:
        raise ApiError("Número da O.S. e Nome do Cliente são obrigatórios.")

    with connect() as conn:
        if conn.execute("SELECT id FROM cards WHERE os_number = ?", (os_number,)).fetchone():
            raise ApiError(f"A O.S. {os_number} já está cadastrada no sistema!")

        # Se não enviou list_id, coloca na primeira lista (ORÇAMENTOS)
        if list_id in (None, ""):
            target_list = conn.execute("SELECT * FROM lists ORDER BY position ASC LIMIT 1").fetchone()
            if not target_list:
                raise ApiError("Nenhuma coluna cadastrada no quadro.")
        else:
            target_list = _get_list(conn, list_id)
            if not target_list:
                raise ApiError("Coluna de destino não encontrada.")

        # Verifica se há fotos de pré-entrada para puxar (por ID selecionado ou pelo nome exato do cliente)
        pre_rows = []
        pid = to_int(pending_entry_id)
        if pid:
            pr = conn.execute("SELECT * FROM pending_entries WHERE id = ?", (pid,)).fetchone()
            if pr:
                pre_rows.append(pr)
        if not pre_rows:
            pre_rows = conn.execute(
                "SELECT * FROM pending_entries WHERE UPPER(TRIM(client_name)) = UPPER(TRIM(?)) ORDER BY id ASC",
                (fields["client_name"],)
            ).fetchall()

        adopted_urls = []
        for pr in pre_rows:
            pr_dict = dict(pr)
            raw_pre_urls = json.loads(pr_dict.get("photos_json") or "[]")
            adopted_urls.extend(adopt_pre_entry_photos(raw_pre_urls, os_number, stage="entrada"))
            # Preenche campos opcionais caso não tenham sido digitados na Nova O.S.
            if not fields.get("equipment_model") and pr_dict.get("equipment_model"):
                fields["equipment_model"] = pr_dict["equipment_model"]
            if not fields.get("serial_number") and pr_dict.get("serial_number"):
                fields["serial_number"] = pr_dict["serial_number"]
            if not fields.get("reported_defect") and pr_dict.get("reported_defect"):
                fields["reported_defect"] = pr_dict["reported_defect"]
            if not fields.get("previous_service") and pr_dict.get("previous_service"):
                fields["previous_service"] = pr_dict["previous_service"]
            if not fields.get("cnpj_cpf") and pr_dict.get("cnpj_cpf"):
                fields["cnpj_cpf"] = pr_dict["cnpj_cpf"]
            if not fields.get("trade_name") and pr_dict.get("trade_name"):
                fields["trade_name"] = pr_dict["trade_name"]
            if not fields.get("phone") and pr_dict.get("phone"):
                fields["phone"] = pr_dict["phone"]
            if not fields.get("email") and pr_dict.get("email"):
                fields["email"] = pr_dict["email"]
            if not fields.get("address") and pr_dict.get("address"):
                fields["address"] = pr_dict["address"]
            if not fields.get("city_state") and pr_dict.get("city_state"):
                fields["city_state"] = pr_dict["city_state"]
            if not fields.get("accessories_json") and pr_dict.get("accessories_json"):
                fields["accessories_json"] = pr_dict["accessories_json"]
            conn.execute("DELETE FROM pending_entries WHERE id = ?", (pr_dict["id"],))

        photo_urls = adopted_urls + save_os_photos(photo_files, os_number, stage="entrada")
        now_iso = _now()

        # Salva ou atualiza o cliente na base permanente
        from .clients import save_or_update_client
        save_or_update_client(fields, conn=conn)

        # Define estado inicial do fluxo conforme a coluna escolhida na abertura
        quote_status = "pending_claim"
        tech_name = ""
        evaluator_tech = ""
        quote_started_at = None
        if rules.is_approved_list(target_list):
            quote_status = "approved"
        elif rules.is_tech_list(target_list):
            quote_status = "in_progress"
            tech_name = target_list["title"]
            evaluator_tech = target_list["title"]
            quote_started_at = now_iso

        try:
            cursor = conn.execute("""
                INSERT INTO cards (
                    os_number, client_name, equipment_type, equipment_model,
                    serial_number, shelf_location, reported_defect, previous_service,
                    cnpj_cpf, trade_name, phone, email, address, city_state, accessories_json,
                    quote_status, tech_name, evaluator_tech, quote_started_at,
                    list_id, position, labels_json, entry_photos_json,
                    created_at, updated_at, moved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                os_number, fields["client_name"], fields["equipment_type"] or DEFAULT_EQUIPMENT_TYPE,
                fields["equipment_model"], fields["serial_number"], fields.get("shelf_location", ""),
                fields["reported_defect"], fields.get("previous_service", ""),
                fields.get("cnpj_cpf", ""), fields.get("trade_name", ""),
                fields.get("phone", ""), fields.get("email", ""),
                fields.get("address", ""), fields.get("city_state", ""),
                fields.get("accessories_json", "[]"),
                quote_status, tech_name, evaluator_tech, quote_started_at,
                target_list["id"], _next_position(conn, target_list["id"]),
                labels_json, json.dumps(photo_urls), now_iso, now_iso, now_iso
            ))
        except sqlite3.IntegrityError:
            raise ApiError(f"A O.S. {os_number} já está cadastrada no sistema!")
        card_id = cursor.lastrowid

        _add_history(conn, card_id, os_number, "RECEPÇÃO", target_list["title"],
                     RECEPTION_ACTOR, "Abertura de O.S.", now_iso)

        new_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(new_row), target_list


# ==============================================================================
# MOVIMENTAÇÃO ENTRE COLUNAS (DRAG-AND-DROP)
# ==============================================================================
def move_card(card_id, target_list_id, new_position, actor, ordered_card_ids=None):
    """
    Move o cartão para outra coluna (ou reordena na mesma) e sincroniza o estado do orçamento/finalização.
    Retorna (cartão enriquecido, coluna de destino, mudou_de_coluna).
    """
    if target_list_id is None:
        raise ApiError("Coluna de destino não informada.")

    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")

        new_list = _get_list(conn, target_list_id)
        if not new_list:
            raise NotFound("Coluna de destino não encontrada.")
        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else ""

        now_iso = _now()
        list_changed = card_row["list_id"] != target_list_id

        tech_name = new_list["title"] if rules.is_tech_list(new_list) else card_row["tech_name"]
        evaluator_tech = card_row["evaluator_tech"] or ""
        finisher_tech = card_row["finisher_tech"] or ""
        quote_started_at = card_row["quote_started_at"]
        quote_status = card_row["quote_status"] or "pending_claim"
        finished_at = card_row["finished_at"]

        if list_changed:
            upper_new = (new_list["title"] or "").strip().upper()
            if rules.is_finished_list(new_list) or rules.is_ready_list(new_list):
                finished_at = card_row["finished_at"] or now_iso
                quote_status = "finished"
            elif rules.is_approved_list(new_list):
                finished_at = None
                quote_status = "approved"
            elif rules.is_orcamento_entry_list(new_list):
                finished_at = None
                quote_status = "pending_claim"
            elif rules.is_tech_list(new_list):
                finished_at = None
                if quote_status in ("done", "approved", "finished") or (old_list and rules.is_approved_list(old_list)):
                    quote_status = "approved"
                    finisher_tech = new_list["title"]
                else:
                    quote_status = "in_progress"
                    if not evaluator_tech:
                        evaluator_tech = new_list["title"]
                    if not quote_started_at:
                        quote_started_at = now_iso
            elif "ANALISE" in upper_new or "ANÁLISE" in upper_new or "ENVIADO" in upper_new:
                finished_at = None
                quote_status = "done"
            else:
                finished_at = None

        conn.execute("""
            UPDATE cards
            SET list_id = ?, position = ?, tech_name = ?,
                evaluator_tech = ?, finisher_tech = ?,
                quote_started_at = ?, quote_status = ?,
                updated_at = ?,
                moved_at = CASE WHEN ? THEN ? ELSE moved_at END,
                finished_at = ?
            WHERE id = ?
        """, (
            target_list_id, new_position, tech_name,
            evaluator_tech, finisher_tech,
            quote_started_at, quote_status,
            now_iso, 1 if list_changed else 0, now_iso, finished_at, card_id
        ))

        if isinstance(ordered_card_ids, list):
            for idx, cid in enumerate(ordered_card_ids):
                conn.execute("UPDATE cards SET position = ? WHERE id = ?", (idx, cid))

        if list_changed:
            _add_history(conn, card_id, card_row["os_number"], old_title, new_list["title"], actor,
                         f"Movido de '{old_title}' para '{new_list['title']}'", now_iso)

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(updated_row), new_list, list_changed


# ==============================================================================
# FLUXO QR CODE MOBILE: 1. ASSUMIR O.S. (ORÇAMENTO OU FINALIZAÇÃO)
# ==============================================================================
def claim_card_mobile(os_number, tech_name, phase="quote", force_switch=False):
    """
    Acionado quando o técnico lê o QR Code e seleciona seu nome:
    - Move o cartão automaticamente para a coluna da bancada dele no Kanban
    - Em fase 'quote': trava o orçamento para esse técnico e grava Início Data/Hora
    - Em fase 'finalization': registra o técnico finalizador e move para a bancada dele
    """
    if not os_number:
        raise ApiError("Número da O.S. não informado.")
    if not tech_name:
        raise ApiError("Selecione qual técnico vai realizar o serviço.")

    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE os_number = ?", (os_number,)).fetchone()
        if not card_row:
            raise NotFound(f"O.S. {os_number} não encontrada.")

        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else "RECEPÇÃO"

        # Procura a coluna correspondente ao técnico no Kanban
        tech_list = conn.execute(
            "SELECT * FROM lists WHERE is_tech = 1 AND UPPER(title) = UPPER(?) LIMIT 1",
            (tech_name,)
        ).fetchone()
        if not tech_list:
            tech_list = conn.execute(
                "SELECT * FROM lists WHERE is_tech = 1 AND UPPER(title) LIKE ? LIMIT 1",
                (f"%{tech_name.upper()}%",)
            ).fetchone()

        target_list_id = tech_list["id"] if tech_list else card_row["list_id"]
        target_title = tech_list["title"] if tech_list else old_title
        final_tech_name = tech_list["title"] if tech_list else tech_name
        new_pos = _next_position(conn, target_list_id) if target_list_id != card_row["list_id"] else card_row["position"]

        now_iso = _now()

        if phase == "finalization" or card_row["quote_status"] == "approved":
            new_status = "approved"
            evaluator_tech = card_row["evaluator_tech"] or final_tech_name
            finisher_tech = final_tech_name
            quote_started_at = card_row["quote_started_at"] or now_iso
            action_desc = f"Iniciou execução/finalização na bancada ({final_tech_name})"
        else:
            # Se já está em orçamento com outro técnico, impede sobrescrever sem aviso (a menos que force_switch=True)
            current_eval = (card_row["evaluator_tech"] or "").strip()
            if (not force_switch
                    and card_row["quote_status"] == "in_progress"
                    and current_eval
                    and current_eval.upper() != final_tech_name.upper()):
                raise ApiError(f"Esta O.S. já está bloqueada em orçamento com {current_eval}.")

            new_status = "in_progress"
            evaluator_tech = final_tech_name
            finisher_tech = card_row["finisher_tech"] or ""
            quote_started_at = card_row["quote_started_at"] or now_iso
            action_desc = f"Assumiu O.S. via QR Code para Orçamento (movido para '{target_title}')"

        conn.execute("""
            UPDATE cards
            SET list_id = ?, position = ?, tech_name = ?,
                evaluator_tech = ?, finisher_tech = ?,
                quote_status = ?, quote_started_at = ?,
                updated_at = ?, moved_at = ?
            WHERE id = ?
        """, (
            target_list_id, new_pos, final_tech_name,
            evaluator_tech, finisher_tech,
            new_status, quote_started_at,
            now_iso, now_iso, card_row["id"]
        ))

        _add_history(conn, card_row["id"], os_number, old_title, target_title,
                     final_tech_name, action_desc, now_iso)

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_row["id"],)).fetchone()

    return enrich_card(updated_row)


# ==============================================================================
# FLUXO QR CODE MOBILE: 2. SALVAR / CONCLUIR ORÇAMENTO DIGITAL
# ==============================================================================
def submit_quote_mobile(os_number, tech_name, quote_payload, label_before_files, finalize_quote=True, quote_photo_files=None):
    """
    Salva todos os dados da Folha de Orçamento Digital preenchidos no celular:
    - Acessórios (Cabo, Fonte, Tampa, Rebobinador, Prato)
    - Lacre e Selo de entrada (IPEM / A5 + Nº)
    - Presença de (Poeira, Sujeira, Umidade, Baratas, Gordura)
    - Testes de Pesos Inicial (1kg a 400kg)
    - Laudo Técnico (defeitos apresentados para o cliente)
    - Peças Substituídas com Quantidade e Código Toledo
    - Checks de Serviço (Revisão Geral, Limpeza Externa, Calibração/Aferição, Cal. Gap Sens, Bater Peso)
    - Checks de Testes (Comunicação, Teclado, Impressão, Display Traseiro)
    - Foto(s) da Etiqueta Antes
    - [F-07] Foto(s) do Laudo / Evidências p/ Orçamento (sujeira p/ Revisão Geral, placa queimada, peças danificadas)
    Se finalize_quote=True, encerra o orçamento (bloqueia a tela até aprovação) e move para ANALISES FEITAS.
    """
    if not os_number:
        raise ApiError("Número da O.S. não informado.")

    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE os_number = ?", (os_number,)).fetchone()
        if not card_row:
            raise NotFound(f"O.S. {os_number} não localizada.")

        current_quote = normalize_quote_data(card_row["quote_data_json"])
        incoming_quote = normalize_quote_data(quote_payload)

        # Preserva solução e pesos finais caso já existam
        if not incoming_quote.get("solution") and current_quote.get("solution"):
            incoming_quote["solution"] = current_quote["solution"]
        if all(not v for v in incoming_quote["weights_final"].values()):
            incoming_quote["weights_final"] = current_quote["weights_final"]

        if finalize_quote and not incoming_quote["technical_report"].strip():
            raise ApiError("Preencha o Laudo Técnico (defeitos apresentados) antes de concluir o orçamento.")

        # Salva fotos da Etiqueta Antes
        before_photos = json.loads(card_row["label_before_photos_json"] or "[]")
        if label_before_files:
            before_photos.extend(save_os_photos(label_before_files, os_number, stage="etiqueta_antes"))

        # [F-07] Salva fotos de Laudo / Evidências do Orçamento (sujeira, placa queimada, etc.)
        quote_photos = json.loads(card_row["quote_photos_json"] or "[]")
        if quote_photo_files:
            quote_photos.extend(save_os_photos(quote_photo_files, os_number, stage="laudo_orcamento"))

        now_iso = _now()
        final_eval_tech = tech_name or card_row["evaluator_tech"] or card_row["tech_name"] or "Técnico"
        parts_summary = format_parts_summary(incoming_quote["parts_items"]) or card_row["parts_used"]
        sc = incoming_quote["service_checks"]
        pop_cal = 1 if (sc.get("calibracao_afericao") or sc.get("calibracao_bater_peso")) else card_row["pop_calibration"]
        pop_clean = 1 if (sc.get("limpeza_externa") or sc.get("revisao_geral")) else card_row["pop_cleaning"]

        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else "BANCADA"
        target_list_id = card_row["list_id"]
        target_title = old_title
        new_pos = card_row["position"]
        new_status = "done" if finalize_quote else "in_progress"
        quote_finished_at = now_iso if finalize_quote else card_row["quote_finished_at"]

        if finalize_quote:
            # Move automaticamente para ANALISES FEITAS (se existir) para a Priscila enviar o orçamento ao cliente
            analise_list = conn.execute(
                "SELECT id, title FROM lists WHERE UPPER(title) LIKE '%ANALISE%' OR UPPER(title) LIKE '%ANÁLISE%' ORDER BY position ASC LIMIT 1"
            ).fetchone()
            if analise_list:
                target_list_id = analise_list["id"]
                target_title = analise_list["title"]
                new_pos = _next_position(conn, target_list_id)

        conn.execute("""
            UPDATE cards
            SET list_id = ?,
                position = ?,
                tech_name = ?,
                evaluator_tech = ?,
                quote_status = ?,
                quote_started_at = COALESCE(quote_started_at, ?),
                quote_finished_at = ?,
                quote_data_json = ?,
                label_before_photos_json = ?,
                quote_photos_json = ?,
                parts_used = ?,
                root_cause = ?,
                pop_calibration = ?,
                pop_cleaning = ?,
                updated_at = ?,
                moved_at = ?
            WHERE id = ?
        """, (
            target_list_id, new_pos, final_eval_tech, final_eval_tech,
            new_status, now_iso, quote_finished_at,
            json.dumps(incoming_quote, ensure_ascii=False),
            json.dumps(before_photos),
            json.dumps(quote_photos),
            parts_summary,
            incoming_quote["technical_report"].strip() or card_row["root_cause"],
            pop_cal, pop_clean,
            now_iso, now_iso, card_row["id"]
        ))

        if finalize_quote:
            _add_history(
                conn, card_row["id"], os_number, old_title, target_title, final_eval_tech,
                f"Orçamento digital concluído via QR Code ({len(incoming_quote['parts_items'])} peça(s))",
                now_iso
            )

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_row["id"],)).fetchone()

    return enrich_card(updated_row)


# ==============================================================================
# APROVAÇÃO DO ORÇAMENTO PELA RECEPÇÃO (LIBERA FINALIZAÇÃO NO QR CODE)
# ==============================================================================
def approve_card_quote(card_id, actor=RECEPTION_ACTOR):
    """
    Marca o orçamento como aprovado pelo cliente e move a O.S. para a coluna APROVADAS,
    liberando a tela de finalização no QR Code do técnico.
    """
    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")

        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else ""

        apr_list = conn.execute(
            "SELECT * FROM lists WHERE role = 'aprovada' OR UPPER(title) LIKE '%APROVADA%' ORDER BY position ASC LIMIT 1"
        ).fetchone()

        target_list_id = apr_list["id"] if apr_list else card_row["list_id"]
        target_title = apr_list["title"] if apr_list else old_title
        new_pos = _next_position(conn, target_list_id) if target_list_id != card_row["list_id"] else card_row["position"]
        now_iso = _now()

        conn.execute("""
            UPDATE cards
            SET list_id = ?, position = ?, quote_status = 'approved',
                updated_at = ?, moved_at = ?
            WHERE id = ?
        """, (target_list_id, new_pos, now_iso, now_iso, card_id))

        _add_history(
            conn, card_id, card_row["os_number"], old_title, target_title,
            actor, "Orçamento aprovado pelo cliente — liberado para finalização", now_iso
        )

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(updated_row)


def reopen_card_quote(card_id, actor=RECEPTION_ACTOR):
    """
    [F-01] Reabre o orçamento da O.S. para edição antes ou durante a aprovação,
    retornando para `quote_status = 'in_progress'` e movendo de volta para a bancada do técnico avaliador (se houver).
    """
    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")

        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else ""

        eval_tech = (card_row["evaluator_tech"] or card_row["tech_name"] or "").strip()
        tech_list = None
        if eval_tech:
            tech_list = conn.execute(
                "SELECT * FROM lists WHERE is_tech = 1 AND UPPER(title) = UPPER(?) LIMIT 1",
                (eval_tech,)
            ).fetchone()

        target_list_id = tech_list["id"] if tech_list else card_row["list_id"]
        target_title = tech_list["title"] if tech_list else old_title
        new_pos = _next_position(conn, target_list_id) if target_list_id != card_row["list_id"] else card_row["position"]
        now_iso = _now()

        conn.execute("""
            UPDATE cards
            SET list_id = ?, position = ?, quote_status = 'in_progress',
                reopen_requested = 0, reopen_requested_by = '', reopen_requested_at = NULL,
                finished_at = NULL, updated_at = ?, moved_at = ?
            WHERE id = ?
        """, (target_list_id, new_pos, now_iso, now_iso, card_id))

        _add_history(
            conn, card_id, card_row["os_number"], old_title, target_title,
            actor, "Orçamento reaberto para edição", now_iso
        )

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(updated_row)


def request_reopen_card_quote(card_id, actor="Técnico (QR Mobile)"):
    """
    Solicita à Priscila (Recepção) a liberação para reabrir e editar o orçamento da O.S.
    Não reabre a O.S. diretamente — aguarda aprovação no painel Admin.
    """
    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")

        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else ""
        now_iso = _now()
        req_actor = (actor or card_row["evaluator_tech"] or card_row["tech_name"] or "Técnico").strip()

        conn.execute("""
            UPDATE cards
            SET reopen_requested = 1,
                reopen_requested_by = ?,
                reopen_requested_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (req_actor, now_iso, now_iso, card_id))

        _add_history(
            conn, card_id, card_row["os_number"], old_title, old_title,
            req_actor, "Solicitou liberação da Recepção para reabrir/editar o orçamento", now_iso
        )

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(updated_row)


def deny_reopen_card_quote(card_id, actor=RECEPTION_ACTOR):
    """Recusa a solicitação de reabertura do orçamento feita pelo técnico."""
    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")

        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else ""
        now_iso = _now()

        conn.execute("""
            UPDATE cards
            SET reopen_requested = 0,
                reopen_requested_by = '',
                reopen_requested_at = NULL,
                updated_at = ?
            WHERE id = ?
        """, (now_iso, card_id))

        _add_history(
            conn, card_id, card_row["os_number"], old_title, old_title,
            actor, "Solicitação de reabertura do orçamento recusada pela Recepção", now_iso
        )

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(updated_row)


def send_card_quote(card_id, actor=RECEPTION_ACTOR):
    """
    Acionado quando a Priscila envia o orçamento ao cliente (estando em ANALISES FEITAS):
    Move a O.S. para 'ORÇAMENTOS ENVIADOS' e garante a etiqueta 'FEITO ORÇ.' / 'AGUARDANDO'.
    """
    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")

        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else ""

        env_list = conn.execute("""
            SELECT * FROM lists
            WHERE UPPER(title) LIKE '%ENVIADO%'
            ORDER BY position ASC LIMIT 1
        """).fetchone()

        target_list_id = env_list["id"] if env_list else card_row["list_id"]
        target_title = env_list["title"] if env_list else old_title
        new_pos = _next_position(conn, target_list_id) if target_list_id != card_row["list_id"] else card_row["position"]
        now_iso = _now()

        labels = json.loads(card_row["labels_json"] or "[]")
        if not any(l.get("name") == "FEITO ORÇ." for l in labels):
            lbl_row = conn.execute("SELECT * FROM labels WHERE name = 'FEITO ORÇ.'").fetchone()
            if lbl_row:
                labels.append({
                    "name": lbl_row["name"],
                    "color": lbl_row["color"],
                    "text_color": lbl_row["text_color"],
                    "priority": lbl_row["priority"],
                })

        conn.execute("""
            UPDATE cards
            SET list_id = ?, position = ?, quote_status = 'done',
                labels_json = ?, updated_at = ?, moved_at = ?
            WHERE id = ?
        """, (target_list_id, new_pos, json.dumps(labels, ensure_ascii=False), now_iso, now_iso, card_id))

        _add_history(
            conn, card_id, card_row["os_number"], old_title, target_title,
            actor, "Orçamento enviado ao cliente pela Recepção", now_iso
        )

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(updated_row)


def finalize_card_admin(card_id, actor=RECEPTION_ACTOR):
    """
    Acionado pela Priscila após conferir uma balança em 'BALANÇAS PRONTAS':
    Move definitivamente a O.S. para 'FINALIZADAS'.
    """
    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")

        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else ""

        fin_list = conn.execute("""
            SELECT * FROM lists
            WHERE role = 'finalizada' OR UPPER(title) LIKE '%FINALIZADA%'
            ORDER BY position DESC LIMIT 1
        """).fetchone()

        target_list_id = fin_list["id"] if fin_list else card_row["list_id"]
        target_title = fin_list["title"] if fin_list else old_title
        new_pos = _next_position(conn, target_list_id) if target_list_id != card_row["list_id"] else card_row["position"]
        now_iso = _now()
        fin_at = card_row["finished_at"] or now_iso

        conn.execute("""
            UPDATE cards
            SET list_id = ?, position = ?, quote_status = 'finished',
                reopen_requested = 0, finished_at = ?, updated_at = ?, moved_at = ?
            WHERE id = ?
        """, (target_list_id, new_pos, fin_at, now_iso, now_iso, card_id))

        _add_history(
            conn, card_id, card_row["os_number"], old_title, target_title,
            actor, "Conferido pela Recepção e arquivado em FINALIZADAS", now_iso
        )

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(updated_row)


def cancel_card(card_id, actor=RECEPTION_ACTOR, reason="Cancelado pela Recepção"):
    """
    Cancela o atendimento de uma O.S.:
    - Move o cartão para a coluna 'ORÇAMENTOS NÃO AUTORIZADOS' (ou role nao_autorizado)
    - Define quote_status = 'cancelled'
    - Adiciona a etiqueta 'NÃO AUTORIZADO'
    - Registra no histórico de movimentação
    """
    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")

        old_list = _get_list(conn, card_row["list_id"])
        old_title = old_list["title"] if old_list else ""

        cancel_list = conn.execute("""
            SELECT * FROM lists 
            WHERE role = 'nao_autorizado' 
               OR UPPER(title) LIKE '%NÃO AUTORIZADO%' 
               OR UPPER(title) LIKE '%NAO AUTORIZADO%' 
               OR UPPER(title) LIKE '%CANCELAD%'
            ORDER BY position ASC LIMIT 1
        """).fetchone()

        target_list_id = cancel_list["id"] if cancel_list else card_row["list_id"]
        target_title = cancel_list["title"] if cancel_list else old_title
        new_pos = _next_position(conn, target_list_id) if target_list_id != card_row["list_id"] else card_row["position"]
        now_iso = _now()

        # Atualiza etiquetas garantindo a presença de 'NÃO AUTORIZADO'
        labels = json.loads(card_row["labels_json"] or "[]")
        if not any(l.get("name") == "NÃO AUTORIZADO" for l in labels):
            nao_aut_label = conn.execute("SELECT * FROM labels WHERE name = 'NÃO AUTORIZADO'").fetchone()
            if nao_aut_label:
                labels.append({
                    "name": nao_aut_label["name"],
                    "color": nao_aut_label["color"],
                    "text_color": nao_aut_label["text_color"],
                    "priority": nao_aut_label["priority"]
                })
            else:
                labels.append({
                    "name": "NÃO AUTORIZADO",
                    "color": "#64748B",
                    "text_color": "#FFFFFF",
                    "priority": 0
                })

        conn.execute("""
            UPDATE cards
            SET list_id = ?, position = ?, quote_status = 'cancelled',
                labels_json = ?, updated_at = ?, moved_at = ?
            WHERE id = ?
        """, (target_list_id, new_pos, json.dumps(labels, ensure_ascii=False), now_iso, now_iso, card_id))

        _add_history(
            conn, card_id, card_row["os_number"], old_title, target_title,
            actor, f"O.S. Cancelada / Não autorizada ({reason})", now_iso
        )

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(updated_row)


# ==============================================================================
# EDIÇÃO (ETIQUETAS, DADOS DO CLIENTE, SERVIÇO ANTERIOR, PRATELEIRA, FOTOS) E EXCLUSÃO
# ==============================================================================
def update_card(card_id, data, photo_files, quote_photo_files=None):
    """Atualiza os campos enviados (incluindo Nº O.S., Tipo, Anotações da Priscila, etc.)."""
    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")

        def field(key):
            value = data.get(key)
            return (card_row[key] or "") if value is None else str(value).strip()

        new_os_number = field("os_number") or card_row["os_number"]
        if new_os_number != card_row["os_number"]:
            clash = conn.execute(
                "SELECT id FROM cards WHERE os_number = ? AND id != ?", (new_os_number, card_id)
            ).fetchone()
            if clash:
                raise ApiError(f"Já existe outra O.S. cadastrada com o número {new_os_number}!")

        labels_json = data.get("labels_json")
        if labels_json is None:
            labels_json = card_row["labels_json"]
        elif isinstance(labels_json, list):
            labels_json = json.dumps(labels_json)

        quote_data_raw = data.get("quote_data_json")
        if quote_data_raw is None:
            quote_data_json = card_row["quote_data_json"] or "{}"
        else:
            norm = normalize_quote_data(quote_data_raw)
            quote_data_json = json.dumps(norm, ensure_ascii=False)

        quote_status = data.get("quote_status") or card_row["quote_status"] or "pending_claim"

        entry_photos = json.loads(card_row["entry_photos_json"] or "[]")
        if photo_files:
            entry_photos.extend(save_os_photos(photo_files, new_os_number, stage="entrada"))

        quote_photos = json.loads(card_row["quote_photos_json"] or "[]")
        if quote_photo_files:
            quote_photos.extend(save_os_photos(quote_photo_files, new_os_number, stage="laudo_orcamento"))

        new_client = field("client_name").upper()
        if not new_client:
            raise ApiError("O nome do cliente não pode ficar vazio.")

        now_iso = _now()
        conn.execute("""
            UPDATE cards
            SET os_number = ?, client_name = ?, equipment_type = ?, equipment_model = ?,
                serial_number = ?, shelf_location = ?, reported_defect = ?,
                previous_service = ?, admin_notes = ?, labels_json = ?, quote_data_json = ?,
                quote_status = ?, entry_photos_json = ?, quote_photos_json = ?, updated_at = ?
            WHERE id = ?
        """, (
            new_os_number, new_client, field("equipment_type"), field("equipment_model"),
            field("serial_number"), field("shelf_location"), field("reported_defect"),
            field("previous_service"), field("admin_notes"), labels_json, quote_data_json,
            quote_status, json.dumps(entry_photos), json.dumps(quote_photos), now_iso, card_id
        ))

        if new_os_number != card_row["os_number"]:
            conn.execute("UPDATE card_history SET os_number = ? WHERE card_id = ?", (new_os_number, card_id))
            old_list = _get_list(conn, card_row["list_id"])
            old_title = old_list["title"] if old_list else ""
            _add_history(
                conn, card_id, new_os_number, old_title, old_title,
                RECEPTION_ACTOR, f"Nº da O.S. corrigido de '{card_row['os_number']}' para '{new_os_number}'", now_iso
            )

        updated_row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    return enrich_card(updated_row)


def delete_card(card_id):
    """[F-02] Remove uma O.S. cadastrada por engano."""
    with connect() as conn:
        card_row = conn.execute("SELECT id, os_number FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not card_row:
            raise NotFound("Cartão não encontrado.")
        conn.execute("DELETE FROM card_history WHERE card_id = ?", (card_id,))
        conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))


# ==============================================================================
# FINALIZAÇÃO PELO CELULAR DO TÉCNICO (QR CODE /saida)
# ==============================================================================
def finish_card_mobile(form, photo_files, label_after_files=None):
    """
    Salva checklist POP, Solução, Lacre Colocado, Testes de Pesos Final,
    foto da Etiqueta Depois e fotos de saída, e move a O.S. para BALANÇAS PRONTAS
    (para conferência final da Priscila antes de arquivar em FINALIZADAS).
    Retorna (linha original do cartão, nome final do técnico).
    """
    os_number = form["os_number"]
    if not os_number:
        raise ApiError("Número da O.S. não informado.")

    solution_or_cause = form.get("solution") or form.get("root_cause") or ""
    if not (form["pop_calibration"] and form["pop_cleaning"] and form["inmetro_seal"] and solution_or_cause):
        raise ApiError("Preencha todo o Checklist POP (Calibração, Limpeza, Lacre Colocado e Solução/Causa).")

    with connect() as conn:
        card_row = conn.execute("SELECT * FROM cards WHERE os_number = ?", (os_number,)).fetchone()
        if not card_row:
            raise NotFound(f"O.S. {os_number} não localizada.")

        # Envia primeiro para BALANÇAS PRONTAS para a Priscila conferir antes de FINALIZADAS
        fin_list = (
            conn.execute(
                "SELECT id, title FROM lists WHERE role = 'pronta' OR UPPER(title) LIKE '%PRONTA%' ORDER BY position ASC LIMIT 1"
            ).fetchone()
            or conn.execute(
                "SELECT id, title FROM lists WHERE role = 'finalizada' OR UPPER(title) LIKE '%FINALIZADA%' LIMIT 1"
            ).fetchone()
            or conn.execute("SELECT id, title FROM lists ORDER BY position DESC LIMIT 1").fetchone()
        )
        if not fin_list:
            raise ApiError("Nenhuma coluna cadastrada no quadro.")

        old_list = _get_list(conn, card_row["list_id"])

        # Salva fotos de saída tiradas pela câmera do celular
        exit_photos = json.loads(card_row["exit_photos_json"] or "[]")
        exit_photos += save_os_photos(photo_files, os_number, stage="saida")

        # Salva fotos da Etiqueta Depois (se enviadas)
        after_photos = json.loads(card_row["label_after_photos_json"] or "[]")
        if label_after_files:
            after_photos += save_os_photos(label_after_files, os_number, stage="etiqueta_depois")

        # Atualiza dados estruturados da folha (Solução + Testes de Peso Final)
        quote_data = normalize_quote_data(card_row["quote_data_json"])
        if form.get("solution"):
            quote_data["solution"] = form["solution"]
        elif form.get("root_cause") and not quote_data.get("solution"):
            quote_data["solution"] = form["root_cause"]

        weights_final_raw = form.get("weights_final_json")
        if weights_final_raw:
            try:
                wf = json.loads(weights_final_raw) if isinstance(weights_final_raw, str) else weights_final_raw
                if isinstance(wf, dict):
                    quote_data["weights_final"].update(wf)
            except Exception:
                pass

        now_iso = _now()
        final_tech = form["tech_name"] or card_row["finisher_tech"] or card_row["tech_name"] or "Técnico"
        evaluator_tech = card_row["evaluator_tech"] or card_row["tech_name"] or final_tech
        parts_used = form["parts_used"] or format_parts_summary(quote_data.get("parts_items")) or card_row["parts_used"]
        root_cause = form.get("root_cause") or quote_data.get("technical_report") or card_row["root_cause"] or solution_or_cause
        tech_notes = form.get("tech_notes") or quote_data.get("solution") or card_row["tech_notes"]
        new_pos = _next_position(conn, fin_list["id"]) if fin_list["id"] != card_row["list_id"] else card_row["position"]

        conn.execute("""
            UPDATE cards
            SET list_id = ?,
                position = ?,
                tech_name = ?,
                evaluator_tech = ?,
                finisher_tech = ?,
                quote_status = 'finished',
                quote_data_json = ?,
                label_after_photos_json = ?,
                pop_calibration = ?,
                pop_cleaning = ?,
                inmetro_seal = ?,
                parts_used = ?,
                root_cause = ?,
                tech_notes = ?,
                shelf_location = COALESCE(NULLIF(?, ''), shelf_location),
                exit_photos_json = ?,
                timer_end_at = NULL,
                updated_at = ?,
                moved_at = ?,
                finished_at = ?
            WHERE id = ?
        """, (
            fin_list["id"], new_pos, final_tech, evaluator_tech, final_tech,
            json.dumps(quote_data, ensure_ascii=False),
            json.dumps(after_photos),
            form["pop_calibration"], form["pop_cleaning"],
            form["inmetro_seal"], parts_used, root_cause, tech_notes,
            form["shelf_location"], json.dumps(exit_photos),
            now_iso, now_iso, now_iso, card_row["id"]
        ))

        _add_history(conn, card_row["id"], os_number,
                     old_list["title"] if old_list else "BANCADA", fin_list["title"], final_tech,
                     f"Serviço finalizado via QR Code Mobile (Lacre: {form['inmetro_seal']})", now_iso)

    return card_row, final_tech


# ==============================================================================
# CRONÔMETRO DE ESTUFA / TESTE
# ==============================================================================
def start_timer(os_number, minutes, label):
    """Inicia o cronômetro. Retorna (linha do cartão, horário de término ISO)."""
    end_time = (datetime.now() + timedelta(minutes=minutes)).isoformat()
    with connect() as conn:
        card_row = conn.execute(
            "SELECT client_name, tech_name FROM cards WHERE os_number = ?", (os_number,)
        ).fetchone()
        if not card_row:
            raise NotFound("O.S. não encontrada.")
        conn.execute(
            "UPDATE cards SET timer_end_at = ?, timer_label = ? WHERE os_number = ?",
            (end_time, label, os_number)
        )
    return card_row, end_time


def finish_timer(os_number):
    """
    Encerra o cronômetro da O.S. Retorna a linha do cartão se havia um cronômetro ativo,
    ou None se ele já tinha sido encerrado (ex.: outra TV aberta já avisou).
    """
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE cards SET timer_end_at = NULL WHERE os_number = ? AND timer_end_at IS NOT NULL",
            (os_number,)
        )
        if cursor.rowcount == 0:
            return None
        return conn.execute(
            "SELECT client_name, timer_label FROM cards WHERE os_number = ?", (os_number,)
        ).fetchone()
