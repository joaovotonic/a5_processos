"""
Motor da Esteira de Produção da A5 Tecnologia.
Gerencia as transições de lista para lista acionadas pelo QR Code da balança e pelas ações da Adm:

1. ORÇAMENTOS -> TEC. [Nome] (1º Scan: Técnico escolhe seu nome -> Inicia Orçamento)
2. TEC. [Nome] -> ORÇAMENTOS FEITOS (2º Scan: Técnico aperta 'ORÇAMENTO OK')
3. ORÇAMENTOS FEITOS -> ORÇAMENTOS ENVIADOS (Priscila aperta 'OK')
4. ORÇAMENTOS ENVIADOS -> APROVADOS (Priscila aperta 'APROVADO' -> Avisa na TV e libera QR Code)
5. APROVADOS -> TEC. [Nome] (3º Scan: Técnico puxa balança aprovada para bancada -> Inicia Manutenção)
6. TEC. [Nome] -> FINALIZADAS (4º Scan: Técnico aperta 'FINALIZAR BALANÇA' -> Notifica Priscila e TV)
"""
from datetime import datetime
import json
import logging
from typing import Dict, Any, Optional

from ..database import connect
from ..errors import ApiError, NotFound
from .. import realtime

logger = logging.getLogger("kanban.esteira")


def _now() -> str:
    return datetime.now().isoformat()


def _parse_iso(iso_str: Optional[str]) -> Optional[datetime]:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except Exception:
        return None


def format_duration(seconds: int) -> str:
    """Converte segundos em formato amigável (ex: '1h 15m' ou '22m' ou '40s')."""
    if seconds <= 0:
        return "0s"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m"
    elif m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _get_list_by_title(conn, title_exact: str):
    """Localiza a lista exata no banco de dados."""
    row = conn.execute("SELECT * FROM lists WHERE title = ? LIMIT 1", (title_exact,)).fetchone()
    if row:
        return dict(row)
    # Busca por aproximação
    row = conn.execute("SELECT * FROM lists WHERE title LIKE ? LIMIT 1", (f"%{title_exact}%",)).fetchone()
    return dict(row) if row else None


def _find_tech_list(conn, tech_name: str):
    """Localiza a coluna do técnico no Kanban pelo nome."""
    t_clean = (tech_name or "").strip().upper()
    if t_clean.startswith("TEC. "):
        t_clean = t_clean[5:].strip()

    rows = conn.execute("SELECT * FROM lists WHERE is_tech = 1 ORDER BY position ASC").fetchall()
    for r in rows:
        title = r["title"].upper()
        if t_clean in title or title.replace("TEC. ", "").strip() == t_clean:
            return dict(r)

    # Busca parcial por partes do nome
    for r in rows:
        for part in t_clean.split():
            if len(part) >= 3 and part in r["title"].upper():
                return dict(r)

    return None


def _next_position(conn, list_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(position), -1) as m FROM cards WHERE list_id = ?",
        (list_id,)
    ).fetchone()
    return (row["m"] if row else -1) + 1


def get_os_status_for_mobile(os_number: str) -> Dict[str, Any]:
    """Retorna os dados da O.S. e a etapa atual para exibição na tela do celular do técnico."""
    clean_os = (os_number or "").strip()
    with connect() as conn:
        card = conn.execute(
            "SELECT c.*, l.title as list_title, l.role as list_role, l.is_tech as list_is_tech "
            "FROM cards c JOIN lists l ON c.list_id = l.id "
            "WHERE c.os_number = ? OR c.id = ?",
            (clean_os, clean_os)
        ).fetchone()

        if not card:
            raise NotFound(f"Ordem de Serviço '{clean_os}' não encontrada.")

        card = dict(card)
        tech_rows = conn.execute("SELECT title FROM lists WHERE is_tech = 1 ORDER BY position ASC").fetchall()
        technicians = [r["title"].replace("TEC. ", "").strip() for r in tech_rows]

    list_title = (card.get("list_title") or "").upper()
    is_tech_col = bool(card.get("list_is_tech"))

    # Determina o estado operacional da esteira
    if "ORÇAMENTO" in list_title and not is_tech_col and "FEITO" not in list_title and "ENVIADO" not in list_title:
        state = "AGUARDANDO_TECNICO_ORCAMENTO"
    elif is_tech_col and card.get("pipeline_phase") == "EM_MANUTENCAO":
        state = "EM_MANUTENCAO_BANCADA"
    elif is_tech_col:
        state = "EM_ORCAMENTO_BANCADA"
    elif "FEITO" in list_title or card.get("pipeline_phase") == "ORCAMENTOS_FEITOS":
        state = "ORCAMENTOS_FEITOS"
    elif "ENVIADO" in list_title or card.get("pipeline_phase") == "ORCAMENTOS_ENVIADOS":
        state = "ORCAMENTOS_ENVIADOS"
    elif "APROVAD" in list_title or card.get("pipeline_phase") == "APROVADOS":
        state = "APROVADOS"
    elif "FINALIZAD" in list_title or "PRONTA" in list_title or card.get("finished_at"):
        state = "FINALIZADAS"
    else:
        state = "OUTRO"

    card["state"] = state
    card["technicians"] = technicians
    card["tempo_orcamento_str"] = format_duration(card.get("tempo_orcamento_segundos") or 0)
    card["tempo_manutencao_str"] = format_duration(card.get("tempo_manutencao_segundos") or 0)
    card["tempo_liquido_str"] = format_duration(card.get("tempo_liquido_segundos") or 0)

    return card


# ==============================================================================
# ETAPA 1: TÉCNICO INICIA ORÇAMENTO (Move para o nome do técnico)
# ==============================================================================
def claim_orcamento(os_number: str, tech_name: str) -> Dict[str, Any]:
    clean_os = (os_number or "").strip()
    clean_tech = (tech_name or "").strip()
    if not clean_tech:
        raise ApiError("Selecione o seu nome para iniciar o orçamento.", status=400)

    now_iso = _now()
    with connect() as conn:
        card = conn.execute("SELECT c.*, l.title as list_title FROM cards c JOIN lists l ON c.list_id = l.id WHERE c.os_number = ?", (clean_os,)).fetchone()
        if not card:
            raise NotFound(f"O.S. {clean_os} não encontrada.")
        card = dict(card)
        card_id = card["id"]

        tech_col = _find_tech_list(conn, clean_tech)
        dest_list_id = tech_col["id"] if tech_col else card["list_id"]
        dest_title = tech_col["title"] if tech_col else f"TEC. {clean_tech}"
        pos = _next_position(conn, dest_list_id)

        conn.execute("""
            UPDATE cards
            SET tech_name = ?,
                evaluator_tech = ?,
                pipeline_phase = 'EM_ORCAMENTO',
                inicio_orcamento = ?,
                list_id = ?,
                position = ?,
                moved_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (clean_tech, clean_tech, now_iso, dest_list_id, pos, now_iso, now_iso, card_id))

        conn.execute("""
            INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
            VALUES (?, ?, ?, ?, ?, 'Iniciou Diagnóstico e Orçamento da Balança', ?)
        """, (card_id, clean_os, card["list_title"], dest_title, clean_tech, now_iso))

    realtime.broadcast_board()
    return {
        "success": True,
        "message": f"O.S. {clean_os} atribuída a {clean_tech}! Iniciando orçamento.",
        "phase": "EM_ORCAMENTO",
        "action": "inicio_orcamento"
    }


# ==============================================================================
# ETAPA 2: TÉCNICO FINALIZA ORÇAMENTO (Aperta 'ORÇAMENTO OK' -> Move para ORÇAMENTOS FEITOS)
# ==============================================================================
def concluir_orcamento(os_number: str) -> Dict[str, Any]:
    clean_os = (os_number or "").strip()
    now_iso = _now()
    now_dt = datetime.now()

    with connect() as conn:
        card = conn.execute("SELECT c.*, l.title as list_title FROM cards c JOIN lists l ON c.list_id = l.id WHERE c.os_number = ?", (clean_os,)).fetchone()
        if not card:
            raise NotFound(f"O.S. {clean_os} não encontrada.")
        card = dict(card)
        card_id = card["id"]
        tech_name = card.get("tech_name") or "Técnico"

        inicio_dt = _parse_iso(card.get("inicio_orcamento")) or now_dt
        tempo_orc_seg = max(1, int((now_dt - inicio_dt).total_seconds()))

        dest_col = _get_list_by_title(conn, "ORÇAMENTOS FEITOS")
        dest_list_id = dest_col["id"] if dest_col else card["list_id"]
        dest_title = dest_col["title"] if dest_col else "ORÇAMENTOS FEITOS"
        pos = _next_position(conn, dest_list_id)

        conn.execute("""
            UPDATE cards
            SET fim_orcamento = ?,
                tempo_orcamento_segundos = ?,
                pipeline_phase = 'ORCAMENTOS_FEITOS',
                list_id = ?,
                position = ?,
                moved_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (now_iso, tempo_orc_seg, dest_list_id, pos, now_iso, now_iso, card_id))

        dur_str = format_duration(tempo_orc_seg)
        conn.execute("""
            INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (card_id, clean_os, card["list_title"], dest_title, tech_name,
              f"Orçamento Concluído ({dur_str}). Movido para ORÇAMENTOS FEITOS.", now_iso))

        # Notifica a Priscila na recepção
        realtime.notify_admin({
            "type": "orcamento_pronto",
            "title": "Orçamento Concluído",
            "message": f"O técnico {tech_name} concluiu o orçamento da O.S. {clean_os} ({dur_str}). Liberar envio ao cliente.",
            "os_number": clean_os,
            "tech_name": tech_name,
            "duration": dur_str
        })

    realtime.broadcast_board()
    return {
        "success": True,
        "message": f"Orçamento da O.S. {clean_os} concluído com sucesso ({dur_str})!",
        "phase": "ORCAMENTOS_FEITOS",
        "action": "fim_orcamento"
    }


# ==============================================================================
# ETAPA 3 & 4: AÇÕES DA ADM NO KANBAN (OK -> ENVIADOS | APROVADO -> APROVADOS + TV)
# ==============================================================================
def adm_enviar_cliente(os_number: str) -> Dict[str, Any]:
    clean_os = (os_number or "").strip()
    now_iso = _now()

    with connect() as conn:
        card = conn.execute("SELECT c.*, l.title as list_title FROM cards c JOIN lists l ON c.list_id = l.id WHERE c.os_number = ?", (clean_os,)).fetchone()
        if not card:
            raise NotFound(f"O.S. {clean_os} não encontrada.")
        card = dict(card)
        card_id = card["id"]

        dest_col = _get_list_by_title(conn, "ORÇAMENTOS ENVIADOS")
        dest_list_id = dest_col["id"] if dest_col else card["list_id"]
        dest_title = dest_col["title"] if dest_col else "ORÇAMENTOS ENVIADOS"
        pos = _next_position(conn, dest_list_id)

        conn.execute("""
            UPDATE cards
            SET pipeline_phase = 'ORCAMENTOS_ENVIADOS',
                list_id = ?,
                position = ?,
                moved_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (dest_list_id, pos, now_iso, now_iso, card_id))

        conn.execute("""
            INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
            VALUES (?, ?, ?, ?, 'Priscila (Recepção)', 'Orçamento Enviado ao Cliente', ?)
        """, (card_id, clean_os, card["list_title"], dest_title, now_iso))

    realtime.broadcast_board()
    return {"success": True, "message": f"O.S. {clean_os} movida para ORÇAMENTOS ENVIADOS.", "phase": "ORCAMENTOS_ENVIADOS"}


def adm_aprovar(os_number: str) -> Dict[str, Any]:
    clean_os = (os_number or "").strip()
    now_iso = _now()

    with connect() as conn:
        card = conn.execute("SELECT c.*, l.title as list_title FROM cards c JOIN lists l ON c.list_id = l.id WHERE c.os_number = ?", (clean_os,)).fetchone()
        if not card:
            raise NotFound(f"O.S. {clean_os} não encontrada.")
        card = dict(card)
        card_id = card["id"]

        dest_col = _get_list_by_title(conn, "APROVADOS")
        dest_list_id = dest_col["id"] if dest_col else card["list_id"]
        dest_title = dest_col["title"] if dest_col else "APROVADOS"
        pos = _next_position(conn, dest_list_id)

        conn.execute("""
            UPDATE cards
            SET pipeline_phase = 'APROVADOS',
                list_id = ?,
                position = ?,
                moved_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (dest_list_id, pos, now_iso, now_iso, card_id))

        conn.execute("""
            INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
            VALUES (?, ?, ?, ?, 'Priscila (Recepção)', 'Orçamento Aprovado pelo Cliente', ?)
        """, (card_id, clean_os, card["list_title"], dest_title, now_iso))

        # Notifica na TV com Edge-TTS e aviso sonoro!
        realtime.announce_arrival({
            "os_number": clean_os,
            "client_name": card["client_name"],
            "equipment_type": card.get("equipment_model") or card.get("equipment_type"),
            "is_urgent": True,
            "is_warranty": False
        }, "conserto aprovado pelo cliente", intro="Atenção oficina!")

    realtime.broadcast_board()
    return {"success": True, "message": f"O.S. {clean_os} APROVADA! Anúncio despachado para a TV e QR Code liberado.", "phase": "APROVADOS"}


# ==============================================================================
# ETAPA 5: TÉCNICO PUXA BALANÇA APROVADA PARA MANUTENÇÃO (Move para o nome do técnico)
# ==============================================================================
def claim_manutencao(os_number: str, tech_name: str) -> Dict[str, Any]:
    clean_os = (os_number or "").strip()
    clean_tech = (tech_name or "").strip()
    if not clean_tech:
        raise ApiError("Selecione o seu nome para iniciar a manutenção.", status=400)

    now_iso = _now()
    with connect() as conn:
        card = conn.execute("SELECT c.*, l.title as list_title FROM cards c JOIN lists l ON c.list_id = l.id WHERE c.os_number = ?", (clean_os,)).fetchone()
        if not card:
            raise NotFound(f"O.S. {clean_os} não encontrada.")
        card = dict(card)
        card_id = card["id"]

        tech_col = _find_tech_list(conn, clean_tech)
        dest_list_id = tech_col["id"] if tech_col else card["list_id"]
        dest_title = tech_col["title"] if tech_col else f"TEC. {clean_tech}"
        pos = _next_position(conn, dest_list_id)

        conn.execute("""
            UPDATE cards
            SET tech_name = ?,
                finisher_tech = ?,
                pipeline_phase = 'EM_MANUTENCAO',
                inicio_manutencao = ?,
                list_id = ?,
                position = ?,
                moved_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (clean_tech, clean_tech, now_iso, dest_list_id, pos, now_iso, now_iso, card_id))

        conn.execute("""
            INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
            VALUES (?, ?, ?, ?, ?, 'Puxou balança aprovada para bancada (EM MANUTENÇÃO)', ?)
        """, (card_id, clean_os, card["list_title"], dest_title, clean_tech, now_iso))

        # Notifica a recepção
        realtime.notify_admin({
            "type": "manutencao_iniciada",
            "title": "Manutenção Iniciada",
            "message": f"O técnico {clean_tech} puxou a O.S. {clean_os} para manutenção na bancada.",
            "os_number": clean_os,
            "tech_name": clean_tech
        })

    realtime.broadcast_board()
    return {
        "success": True,
        "message": f"O.S. {clean_os} em manutenção na sua bancada!",
        "phase": "EM_MANUTENCAO",
        "action": "inicio_manutencao"
    }


# ==============================================================================
# ETAPA 6: TÉCNICO FINALIZA A BALANÇA ('FINALIZAR BALANÇA' -> Move para FINALIZADAS)
# ==============================================================================
def finalizar_balanca(os_number: str) -> Dict[str, Any]:
    clean_os = (os_number or "").strip()
    now_iso = _now()
    now_dt = datetime.now()

    with connect() as conn:
        card = conn.execute("SELECT c.*, l.title as list_title FROM cards c JOIN lists l ON c.list_id = l.id WHERE c.os_number = ?", (clean_os,)).fetchone()
        if not card:
            raise NotFound(f"O.S. {clean_os} não encontrada.")
        card = dict(card)
        card_id = card["id"]
        tech_name = card.get("tech_name") or "Técnico"

        inicio_man_dt = _parse_iso(card.get("inicio_manutencao")) or now_dt
        tempo_man_seg = max(1, int((now_dt - inicio_man_dt).total_seconds()))
        tempo_orc_seg = card.get("tempo_orcamento_segundos") or 0
        tempo_liq_seg = tempo_orc_seg + tempo_man_seg

        dest_col = _get_list_by_title(conn, "FINALIZADAS")
        dest_list_id = dest_col["id"] if dest_col else card["list_id"]
        dest_title = dest_col["title"] if dest_col else "FINALIZADAS"
        pos = _next_position(conn, dest_list_id)

        conn.execute("""
            UPDATE cards
            SET fim_manutencao = ?,
                tempo_manutencao_segundos = ?,
                tempo_liquido_segundos = ?,
                pipeline_phase = 'PRONTAS',
                finished_at = ?,
                list_id = ?,
                position = ?,
                moved_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (now_iso, tempo_man_seg, tempo_liq_seg, now_iso, dest_list_id, pos, now_iso, now_iso, card_id))

        dur_man_str = format_duration(tempo_man_seg)
        dur_liq_str = format_duration(tempo_liq_seg)

        conn.execute("""
            INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (card_id, clean_os, card["list_title"], dest_title, tech_name,
              f"Manutenção Concluída ({dur_man_str}). Tempo Líquido: {dur_liq_str}. Movida para FINALIZADAS.", now_iso))

        today_prefix = now_dt.strftime("%Y-%m-%d")
        finished_today = conn.execute(
            "SELECT COUNT(*) as c FROM cards WHERE finished_at LIKE ?",
            (f"{today_prefix}%",)
        ).fetchone()["c"]

        # Anuncia na TV da oficina
        realtime.announce_finished_mobile(
            os_number=clean_os,
            client_name=card["client_name"],
            tech_name=tech_name,
            inmetro_seal=card.get("inmetro_seal") or "",
            finished_today=finished_today
        )

        # Notifica a Priscila na recepção
        realtime.notify_admin({
            "type": "balanca_finalizada",
            "title": "🎉 Balança Finalizada!",
            "message": f"O técnico {tech_name} finalizou a balança da O.S. {clean_os} ({card['client_name']}). Movida para FINALIZADAS.",
            "os_number": clean_os,
            "tech_name": tech_name,
            "finished_today": finished_today,
            "tempo_liquido": dur_liq_str
        })

    realtime.broadcast_board()
    return {
        "success": True,
        "message": f"🎉 Balança O.S. {clean_os} finalizada com sucesso! Tempo líquido: {dur_liq_str}.",
        "phase": "PRONTAS",
        "action": "fim_manutencao",
        "tempo_liquido_str": dur_liq_str
    }


# ==============================================================================
# EXCLUSÃO DE O.S. (Solicitado pelo usuário para a Priscila)
# ==============================================================================
def delete_card_by_os(os_number: str) -> Dict[str, Any]:
    clean_os = (os_number or "").strip()
    with connect() as conn:
        card = conn.execute("SELECT id, os_number, client_name FROM cards WHERE os_number = ?", (clean_os,)).fetchone()
        if not card:
            raise NotFound(f"O.S. {clean_os} não encontrada para exclusão.")
        card_id = card["id"]
        conn.execute("DELETE FROM card_history WHERE card_id = ?", (card_id,))
        conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))

    logger.info(f"O.S. {clean_os} excluída com sucesso pela recepção.")
    realtime.broadcast_board()
    return {"success": True, "message": f"O.S. {clean_os} excluída com sucesso."}


# ==============================================================================
# CRIAÇÃO MANUAL DE BANNER (Caso a Priscila precise criar direto no Kanban)
# ==============================================================================
def create_manual_os(data: Dict[str, Any]) -> Dict[str, Any]:
    os_number = (data.get("os_number") or "").strip()
    client_name = (data.get("client_name") or "CLIENTE BALCÃO").strip().upper()
    equipment_model = (data.get("equipment_model") or "").strip()
    serial_number = (data.get("serial_number") or "").strip().upper()
    reported_defect = (data.get("reported_defect") or "Defeito informado na recepção").strip()
    target_list_id = data.get("list_id")

    if not os_number:
        now_dt = datetime.now()
        os_number = f"A5-{now_dt.strftime('%H%M%S')}"

    now_iso = _now()
    with connect() as conn:
        existing = conn.execute("SELECT id FROM cards WHERE os_number = ?", (os_number,)).fetchone()
        if existing:
            raise ApiError(f"Já existe uma O.S. com o número {os_number}.", status=400)

        if not target_list_id:
            first_list = _get_list_by_title(conn, "ORÇAMENTOS")
            target_list_id = first_list["id"] if first_list else 1

        pos = _next_position(conn, target_list_id)
        cur = conn.execute("""
            INSERT INTO cards (
                os_number, client_name, equipment_type, equipment_model,
                serial_number, reported_defect, list_id, position,
                pipeline_phase, created_at, updated_at, moved_at
            ) VALUES (?, ?, 'Balança Toledo Prix', ?, ?, ?, ?, ?, 'ORCAMENTOS_A_FAZER', ?, ?, ?)
        """, (
            os_number, client_name, equipment_model, serial_number, reported_defect,
            target_list_id, pos, now_iso, now_iso, now_iso
        ))
        card_id = cur.lastrowid

        conn.execute("""
            INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
            VALUES (?, ?, 'Abertura Manual', 'ORÇAMENTOS', 'Priscila (Recepção)', 'Banner criado manualmente no painel', ?)
        """, (card_id, os_number, now_iso))

    realtime.broadcast_board()
    return {
        "success": True,
        "os_number": os_number,
        "client_name": client_name,
        "label_url": f"/etiqueta/{os_number}",
        "message": f"O.S. {os_number} criada com sucesso!"
    }


# ==============================================================================
# WRAPPERS DE COMPATIBILIDADE E AUTOMAÇÃO DE SCAN
# ==============================================================================
def process_qr_scan(os_number: str, tech_name: str = "") -> Dict[str, Any]:
    """
    Roteador inteligente da máquina de estados acionado pelo QR Code.
    Identifica a fase atual da balança e avança para a próxima etapa da esteira.
    """
    status = get_os_status_for_mobile(os_number)
    state = status.get("state")
    phase = status.get("pipeline_phase") or ""

    if state == "AGUARDANDO_TECNICO_ORCAMENTO" or phase == "ORCAMENTOS_A_FAZER":
        return claim_orcamento(os_number, tech_name or status.get("tech_name") or "Oficina")
    elif state == "EM_ORCAMENTO_BANCADA" or phase == "EM_ORCAMENTO":
        return concluir_orcamento(os_number)
    elif state == "APROVADOS" or phase == "APROVADOS":
        return claim_manutencao(os_number, tech_name or status.get("tech_name") or "Oficina")
    elif state == "EM_MANUTENCAO_BANCADA" or phase == "EM_MANUTENCAO":
        return finalizar_balanca(os_number)
    else:
        return {
            "success": False,
            "message": f"O.S. em fase '{phase}' ({state}) não aceita avanço automático por scan.",
            "phase": phase
        }


def advance_admin_pipeline(os_number: str, action: str) -> Dict[str, Any]:
    """Avança a O.S. através das ações da recepção (Priscila)."""
    clean_action = (action or "").strip().lower()
    if clean_action in ("enviar_cliente", "enviado", "ok", "enviados"):
        return adm_enviar_cliente(os_number)
    elif clean_action in ("aprovar", "aprovado", "aprovados"):
        return adm_aprovar(os_number)
    raise ApiError(f"Ação administrativa desconhecida: '{action}'", status=400)

