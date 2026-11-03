"""
Serviço de Esteira de Produção e Máquina de Estados Inteligente da A5 Tecnologia.
Controla os ciclos de vida das Ordens de Serviço:
1. ORCAMENTOS_A_FAZER -> EM_ORCAMENTO (1º Scan pelo Técnico)
2. EM_ORCAMENTO -> ORCAMENTOS_FEITOS (2º Scan pelo Técnico)
3. ORCAMENTOS_FEITOS -> ORCAMENTOS_ENVIADOS (Ação da Adm: "Enviado ao Cliente")
4. ORCAMENTOS_ENVIADOS -> APROVADOS (Ação da Adm: "Aprovado", com aviso sonoro na TV)
5. APROVADOS -> EM_MANUTENCAO (3º Scan pelo Técnico para puxar à bancada)
6. EM_MANUTENCAO -> PRONTAS (4º Scan pelo Técnico com consolidação de tempos e comemoração na TV)
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
    """Converte segundos em string legível (ex: '1h 25m' ou '42m' ou '35s')."""
    if seconds <= 0:
        return "0s"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m"
    elif m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _get_list_by_role_or_title(conn, role: str, title_part: Optional[str] = None):
    """Localiza uma coluna pelo papel (role) ou título."""
    if title_part:
        row = conn.execute(
            "SELECT * FROM lists WHERE role = ? AND title LIKE ? ORDER BY position ASC LIMIT 1",
            (role, f"%{title_part}%")
        ).fetchone()
        if row:
            return dict(row)

    row = conn.execute(
        "SELECT * FROM lists WHERE role = ? ORDER BY position ASC LIMIT 1",
        (role,)
    ).fetchone()
    if row:
        return dict(row)

    if title_part:
        row = conn.execute(
            "SELECT * FROM lists WHERE title LIKE ? ORDER BY position ASC LIMIT 1",
            (f"%{title_part}%",)
        ).fetchone()
        if row:
            return dict(row)

    return None


def _find_tech_list(conn, tech_name: str):
    """Localiza a coluna do técnico no Kanban pelo nome."""
    t_clean = (tech_name or "").strip().upper()
    # Remove prefixo TEC. se tiver
    if t_clean.startswith("TEC. "):
        t_clean = t_clean[5:].strip()

    rows = conn.execute("SELECT * FROM lists WHERE is_tech = 1 ORDER BY position ASC").fetchall()
    for r in rows:
        title = r["title"].upper()
        if t_clean in title or title.replace("TEC. ", "").strip() == t_clean:
            return dict(r)

    # Se não achou exato, busca parcial
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


def process_qr_scan(os_query: str, tech_name: str) -> Dict[str, Any]:
    """
    Processa a leitura do QR Code na esteira e avança a máquina de estados.
    Suporta busca por número de OS ou ID numérico.
    """
    clean_os = (os_query or "").strip()
    clean_tech = (tech_name or "").strip()

    if not clean_os:
        raise ApiError("Número de O.S. não informado na leitura do QR Code.", status=400)
    if not clean_tech:
        raise ApiError("Selecione o seu nome de técnico no topo antes de escanear.", status=400)

    now_iso = _now()
    now_dt = datetime.now()

    with connect() as conn:
        # Busca o cartão por os_number ou por id
        card = conn.execute(
            "SELECT c.*, l.title as list_title, l.role as list_role, l.is_tech as list_is_tech "
            "FROM cards c JOIN lists l ON c.list_id = l.id "
            "WHERE c.os_number = ? OR c.id = ?",
            (clean_os, clean_os)
        ).fetchone()

        if not card:
            raise NotFound(f"Ordem de Serviço '{clean_os}' não encontrada no sistema.")

        card = dict(card)
        card_id = card["id"]
        os_number = card["os_number"]
        current_phase = card.get("pipeline_phase") or "ORCAMENTOS_A_FAZER"
        list_role = card.get("list_role")
        is_tech_col = bool(card.get("list_is_tech"))

        # Localiza a lista de trabalho do técnico
        tech_col = _find_tech_list(conn, clean_tech)
        if not tech_col:
            # Se não encontrou coluna com o nome, pega a primeira coluna de técnico disponível
            tech_col = conn.execute("SELECT * FROM lists WHERE is_tech = 1 LIMIT 1").fetchone()
            if tech_col:
                tech_col = dict(tech_col)

        # ==============================================================================
        # 1º SCAN: Card está em ORCAMENTOS_A_FAZER (ou lista inicial de orçamentos)
        # ==============================================================================
        if current_phase == "ORCAMENTOS_A_FAZER" or (list_role == "orcamento" and not is_tech_col):
            dest_list_id = tech_col["id"] if tech_col else card["list_id"]
            dest_list_title = tech_col["title"] if tech_col else card["list_title"]
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
                VALUES (?, ?, ?, ?, ?, '1º Scan: Iniciou diagnóstico e orçamento', ?)
            """, (card_id, os_number, card["list_title"], dest_list_title, clean_tech, now_iso))

            msg = f"O.S. {os_number} vinculada a você! Fase iniciada: EM ORÇAMENTO."
            action_code = "inicio_orcamento"
            next_phase = "EM_ORCAMENTO"

        # ==============================================================================
        # 2º SCAN: Card está na coluna do Técnico na fase EM_ORCAMENTO
        # ==============================================================================
        elif current_phase == "EM_ORCAMENTO":
            # Calcula o tempo gasto no orçamento
            inicio_dt = _parse_iso(card.get("inicio_orcamento")) or now_dt
            tempo_orc_seg = max(1, int((now_dt - inicio_dt).total_seconds()))

            # Move para a lista ANALISES FEITAS (role 'processo' ou título com 'ANALISE' ou 'FEITO')
            dest_col = _get_list_by_role_or_title(conn, "processo", "ANALISES FEITAS")
            if not dest_col:
                dest_col = _get_list_by_role_or_title(conn, "processo", "FEITOS")
            dest_list_id = dest_col["id"] if dest_col else card["list_id"]
            dest_list_title = dest_col["title"] if dest_col else "ANALISES FEITAS"
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
            """, (card_id, os_number, card["list_title"], dest_list_title, clean_tech,
                  f"2º Scan: Orçamento concluído em {dur_str}. Enviado para análise da Recepção.", now_iso))

            # Notifica a recepção (Priscila)
            realtime.notify_admin({
                "type": "orcamento_pronto",
                "title": "Orçamento Concluído",
                "message": f"O técnico {clean_tech} concluiu o orçamento da O.S. {os_number} ({dur_str}). Pronto para envio ao cliente.",
                "os_number": os_number,
                "tech_name": clean_tech,
                "duration": dur_str
            })

            msg = f"Orçamento da O.S. {os_number} finalizado em {dur_str}! Movido para ANALISES FEITAS."
            action_code = "fim_orcamento"
            next_phase = "ORCAMENTOS_FEITOS"

        # ==============================================================================
        # 3º SCAN: Card está em APROVADOS (aguardando técnico puxar para reparo)
        # ==============================================================================
        elif current_phase == "APROVADOS" or list_role == "aprovada":
            dest_list_id = tech_col["id"] if tech_col else card["list_id"]
            dest_list_title = tech_col["title"] if tech_col else card["list_title"]
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
                VALUES (?, ?, ?, ?, ?, '3º Scan: Puxou balança aprovada para bancada (EM MANUTENÇÃO)', ?)
            """, (card_id, os_number, card["list_title"], dest_list_title, clean_tech, now_iso))

            realtime.notify_admin({
                "type": "manutencao_iniciada",
                "title": "Manutenção Iniciada",
                "message": f"O técnico {clean_tech} puxou a O.S. {os_number} aprovada para a bancada.",
                "os_number": os_number,
                "tech_name": clean_tech
            })

            msg = f"O.S. {os_number} puxada para sua bancada! Fase iniciada: EM MANUTENÇÃO."
            action_code = "inicio_manutencao"
            next_phase = "EM_MANUTENCAO"

        # ==============================================================================
        # 4º SCAN: Card está na coluna do Técnico na fase EM_MANUTENCAO
        # ==============================================================================
        elif current_phase == "EM_MANUTENCAO":
            inicio_man_dt = _parse_iso(card.get("inicio_manutencao")) or now_dt
            tempo_man_seg = max(1, int((now_dt - inicio_man_dt).total_seconds()))

            tempo_orc_seg = card.get("tempo_orcamento_segundos") or 0
            tempo_liq_seg = tempo_orc_seg + tempo_man_seg

            # Move para BALANÇAS PRONTAS
            dest_col = _get_list_by_role_or_title(conn, "pronta", "BALANÇAS PRONTAS")
            dest_list_id = dest_col["id"] if dest_col else card["list_id"]
            dest_list_title = dest_col["title"] if dest_col else "BALANÇAS PRONTAS"
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
            """, (card_id, os_number, card["list_title"], dest_list_title, clean_tech,
                  f"4º Scan: Manutenção finalizada em {dur_man_str} (Tempo Líquido: {dur_liq_str}). Pronta para entrega.", now_iso))

            # Contagem de balanças prontas hoje para o placar da TV
            today_prefix = now_dt.strftime("%Y-%m-%d")
            finished_today = conn.execute(
                "SELECT COUNT(*) as c FROM cards WHERE finished_at LIKE ?",
                (f"{today_prefix}%",)
            ).fetchone()["c"]

            # Comemoração e anúncio sonoro neural na TV
            realtime.announce_finished_mobile(
                os_number=os_number,
                client_name=card["client_name"],
                tech_name=clean_tech,
                inmetro_seal=card.get("inmetro_seal") or "",
                finished_today=finished_today
            )

            # Notifica a recepção
            realtime.notify_admin({
                "type": "balanca_pronta",
                "title": "Balança Pronta!",
                "message": f"O técnico {clean_tech} finalizou a O.S. {os_number}. Tempo líquido: {dur_liq_str}.",
                "os_number": os_number,
                "tech_name": clean_tech,
                "finished_today": finished_today
            })

            msg = f"🎉 Parabéns! O.S. {os_number} concluída! Manutenção: {dur_man_str} | Tempo Líquido: {dur_liq_str}."
            action_code = "fim_manutencao"
            next_phase = "PRONTAS"

        # ==============================================================================
        # CASOS INTERMEDIÁRIOS (Aguardando cliente ou já pronta)
        # ==============================================================================
        elif current_phase == "ORCAMENTOS_FEITOS":
            msg = f"A O.S. {os_number} já teve o orçamento concluído. Aguardando a Recepção enviar ao cliente."
            action_code = "aguardando_envio"
            next_phase = current_phase

        elif current_phase == "ORCAMENTOS_ENVIADOS":
            msg = f"A O.S. {os_number} está com orçamento enviado ao cliente. Aguardando aprovação."
            action_code = "aguardando_aprovacao"
            next_phase = current_phase

        elif current_phase == "PRONTAS" or list_role in ("pronta", "finalizada"):
            msg = f"A O.S. {os_number} já está concluída e pronta para retirada."
            action_code = "ja_finalizada"
            next_phase = current_phase

        else:
            msg = f"O.S. {os_number} está na fase '{current_phase}'."
            action_code = "sem_acao"
            next_phase = current_phase

    # Atualiza todas as telas conectadas via WebSocket
    board = realtime.broadcast_board()

    return {
        "success": True,
        "action": action_code,
        "phase": next_phase,
        "message": msg,
        "os_number": os_number,
        "client_name": card["client_name"],
        "equipment_model": card.get("equipment_model") or card.get("equipment_type"),
        "tech_name": clean_tech,
        "board": board
    }


def advance_admin_pipeline(os_number: str, action: str, actor: str = "Priscila (Recepção)") -> Dict[str, Any]:
    """
    Ações diretas da Recepção/Adm para movimentação das O.S.:
    - action='enviar_cliente': move de ORCAMENTOS_FEITOS -> ORCAMENTOS_ENVIADOS
    - action='aprovar': move de ORCAMENTOS_ENVIADOS -> APROVADOS (com anúncio na TV)
    """
    clean_os = (os_number or "").strip()
    action = (action or "").strip().lower()
    now_iso = _now()

    with connect() as conn:
        card = conn.execute(
            "SELECT c.*, l.title as list_title FROM cards c JOIN lists l ON c.list_id = l.id WHERE c.os_number = ?",
            (clean_os,)
        ).fetchone()

        if not card:
            raise NotFound(f"O.S. {clean_os} não encontrada.")

        card = dict(card)
        card_id = card["id"]

        if action == "enviar_cliente":
            dest_col = _get_list_by_role_or_title(conn, "processo", "ORÇAMENTOS ENVIADOS")
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
                VALUES (?, ?, ?, ?, ?, 'Orçamento enviado ao cliente', ?)
            """, (card_id, clean_os, card["list_title"], dest_title, actor, now_iso))

            msg = f"O.S. {clean_os} marcada como Enviada ao Cliente."
            new_phase = "ORCAMENTOS_ENVIADOS"

        elif action == "aprovar":
            dest_col = _get_list_by_role_or_title(conn, "aprovada", "APROVADAS")
            dest_list_id = dest_col["id"] if dest_col else card["list_id"]
            dest_title = dest_col["title"] if dest_col else "APROVADAS"
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
                VALUES (?, ?, ?, ?, ?, 'Orçamento Aprovado pelo Cliente', ?)
            """, (card_id, clean_os, card["list_title"], dest_title, actor, now_iso))

            # Dispara anúncio sonoro neural e visual na Smart TV da oficina!
            realtime.announce_arrival({
                "os_number": clean_os,
                "client_name": card["client_name"],
                "equipment_type": card.get("equipment_model") or card.get("equipment_type"),
                "is_urgent": True,
                "is_warranty": False
            }, "conserto aprovado pelo cliente", intro="Atenção oficina!")

            msg = f"O.S. {clean_os} Aprovada! Anúncio sonoro emitido para a oficina."
            new_phase = "APROVADOS"

        else:
            raise ApiError(f"Ação de administração inválida: '{action}'.", status=400)

    board = realtime.broadcast_board()
    return {
        "success": True,
        "os_number": clean_os,
        "phase": new_phase,
        "message": msg,
        "board": board
    }
