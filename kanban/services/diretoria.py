"""
Serviço de Relatórios de Produtividade, Métricas de Tempos e Chamados da Diretoria (Sr. Jacson).
Calcula KPIs consolidados, desempenho individual de cada técnico e tempo líquido de bancada por O.S.
Inclui também o marco de início oficial (reset_and_start_official_metrics) após organização manual do Kanban.
"""
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, Any, List, Optional

from ..database import connect
from .esteira import format_duration

logger = logging.getLogger("kanban.diretoria")

DEFAULT_TECHS = ["Enzo Gabriel", "Guilherme", "Wisley", "João Otoni", "Iago", "ANTONIO"]


def reset_and_start_official_metrics(actor: str = "Priscila (Recepção)") -> Dict[str, Any]:
    """
    Congela o estado organizado manualmente no Kanban como linha de base (baseline)
    e inicia a contabilização oficial de produtividade do zero a partir deste exato instante.
    - Mantém 100% dos cartões nas colunas e posições em que a Priscila organizou.
    - Sincroniza pipeline_phase e quote_status de cada cartão com sua coluna atual.
    - Zera contadores anteriores de orçamentos/finalizadas para que o relatório do Sr. Jacson,
      o painel de Gerência e o Placar da TV passem a contabilizar somente o que acontecer daqui para frente.
    """
    now_dt = datetime.now()
    now_iso = now_dt.isoformat()
    baseline_iso = "2000-01-01T00:00:00"

    summary_by_column: Dict[str, int] = {}
    total_cards = 0

    with connect() as conn:
        # 1. Salva o marco temporal oficial nas configurações do banco
        conn.execute("""
            INSERT INTO settings (key, value) VALUES ('metrics_start_at', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (now_iso,))

        # 2. Sincroniza os cartões em lote por coluna (muito rápido para milhares de cartões)
        lists_rows = conn.execute("""
            SELECT l.id, l.title, l.role, l.is_tech, COUNT(c.id) as cnt
            FROM lists l
            LEFT JOIN cards c ON c.list_id = l.id
            GROUP BY l.id
            ORDER BY l.position ASC
        """).fetchall()

        for lr in lists_rows:
            lid = lr["id"]
            l_title = (lr["title"] or "").strip()
            l_upper = l_title.upper()
            l_role = (lr["role"] or "").strip().lower()
            is_tech = int(lr["is_tech"] or 0) == 1
            cnt = int(lr["cnt"] or 0)
            total_cards += cnt
            if cnt > 0:
                summary_by_column[l_title] = cnt

            if l_role in ("finalizada", "pronta") or "FINALIZAD" in l_upper or "PRONTA" in l_upper:
                conn.execute("""
                    UPDATE cards
                    SET pipeline_phase = 'PRONTAS',
                        quote_status = 'finished',
                        finished_at = ?,
                        moved_at = ?,
                        fim_orcamento = NULL,
                        fim_manutencao = NULL,
                        quote_finished_at = NULL,
                        tempo_orcamento_segundos = 0,
                        tempo_manutencao_segundos = 0,
                        tempo_liquido_segundos = 0
                    WHERE list_id = ?
                """, (baseline_iso, baseline_iso, lid))

            elif l_role in ("nao_autorizados", "nao_autorizado") or "AUTORIZADO" in l_upper or "CANCELAD" in l_upper:
                conn.execute("""
                    UPDATE cards
                    SET pipeline_phase = 'NAO_AUTORIZADO',
                        quote_status = 'cancelled',
                        finished_at = NULL,
                        fim_orcamento = NULL,
                        fim_manutencao = NULL,
                        quote_finished_at = NULL,
                        tempo_orcamento_segundos = 0,
                        tempo_manutencao_segundos = 0,
                        tempo_liquido_segundos = 0,
                        moved_at = ?
                    WHERE list_id = ?
                """, (now_iso, lid))

            elif is_tech:
                conn.execute("""
                    UPDATE cards
                    SET pipeline_phase = CASE
                            WHEN quote_status = 'approved' OR pipeline_phase = 'EM_MANUTENCAO' OR labels_json LIKE '%"APROVADO"%'
                            THEN 'EM_MANUTENCAO' ELSE 'EM_ORCAMENTO'
                        END,
                        quote_status = CASE
                            WHEN quote_status = 'approved' OR pipeline_phase = 'EM_MANUTENCAO' OR labels_json LIKE '%"APROVADO"%'
                            THEN 'approved' ELSE 'in_progress'
                        END,
                        tech_name = ?,
                        evaluator_tech = CASE
                            WHEN quote_status = 'approved' OR pipeline_phase = 'EM_MANUTENCAO' OR labels_json LIKE '%"APROVADO"%'
                            THEN evaluator_tech ELSE ?
                        END,
                        finisher_tech = CASE
                            WHEN quote_status = 'approved' OR pipeline_phase = 'EM_MANUTENCAO' OR labels_json LIKE '%"APROVADO"%'
                            THEN ? ELSE finisher_tech
                        END,
                        quote_started_at = ?,
                        inicio_orcamento = ?,
                        inicio_manutencao = CASE
                            WHEN quote_status = 'approved' OR pipeline_phase = 'EM_MANUTENCAO' OR labels_json LIKE '%"APROVADO"%'
                            THEN ? ELSE NULL
                        END,
                        fim_orcamento = NULL,
                        fim_manutencao = NULL,
                        quote_finished_at = NULL,
                        finished_at = NULL,
                        tempo_orcamento_segundos = 0,
                        tempo_manutencao_segundos = 0,
                        tempo_liquido_segundos = 0,
                        moved_at = ?
                    WHERE list_id = ?
                """, (l_title, l_title, l_title, now_iso, now_iso, now_iso, now_iso, lid))

            elif l_role in ("aprovados", "aprovada") or "APROVAD" in l_upper:
                conn.execute("""
                    UPDATE cards
                    SET pipeline_phase = 'APROVADOS',
                        quote_status = 'approved',
                        finished_at = NULL,
                        fim_orcamento = NULL,
                        fim_manutencao = NULL,
                        quote_finished_at = NULL,
                        tempo_orcamento_segundos = 0,
                        tempo_manutencao_segundos = 0,
                        tempo_liquido_segundos = 0,
                        moved_at = ?
                    WHERE list_id = ?
                """, (now_iso, lid))

            elif l_role == "orcamentos_enviados" or "ENVIADO" in l_upper:
                conn.execute("""
                    UPDATE cards
                    SET pipeline_phase = 'ORCAMENTOS_ENVIADOS',
                        quote_status = 'done',
                        finished_at = NULL,
                        fim_orcamento = NULL,
                        fim_manutencao = NULL,
                        quote_finished_at = NULL,
                        tempo_orcamento_segundos = 0,
                        tempo_manutencao_segundos = 0,
                        tempo_liquido_segundos = 0,
                        moved_at = ?
                    WHERE list_id = ?
                """, (now_iso, lid))

            elif l_role == "orcamentos_feitos" or "FEITO" in l_upper or "ANALISE" in l_upper or "ANÁLISE" in l_upper:
                conn.execute("""
                    UPDATE cards
                    SET pipeline_phase = 'ORCAMENTOS_FEITOS',
                        quote_status = 'done',
                        finished_at = NULL,
                        fim_orcamento = NULL,
                        fim_manutencao = NULL,
                        quote_finished_at = NULL,
                        tempo_orcamento_segundos = 0,
                        tempo_manutencao_segundos = 0,
                        tempo_liquido_segundos = 0,
                        moved_at = ?
                    WHERE list_id = ?
                """, (now_iso, lid))

            else:
                conn.execute("""
                    UPDATE cards
                    SET pipeline_phase = 'ORCAMENTOS_A_FAZER',
                        quote_status = 'pending_claim',
                        tech_name = '',
                        evaluator_tech = '',
                        finisher_tech = '',
                        finished_at = NULL,
                        inicio_orcamento = NULL,
                        fim_orcamento = NULL,
                        inicio_manutencao = NULL,
                        fim_manutencao = NULL,
                        quote_started_at = NULL,
                        quote_finished_at = NULL,
                        tempo_orcamento_segundos = 0,
                        tempo_manutencao_segundos = 0,
                        tempo_liquido_segundos = 0,
                        moved_at = ?
                    WHERE list_id = ?
                """, (now_iso, lid))

        # 3. Limpa histórico antigo de reorganização para começar limpo a partir do marco oficial
        conn.execute("DELETE FROM card_history;")

    return {
        "success": True,
        "metrics_start_at": now_iso,
        "total_cards_synced": total_cards,
        "summary_by_column": summary_by_column
    }


def get_director_productivity_report(
    period: str = "today",
    tech_filter: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Gera o relatório executivo completo para a tela da Diretoria (/diretoria).
    Retorna KPIs consolidados, tabela de técnicos e lista analítica de O.S.
    Respeita estritamente o marco `metrics_start_at` para não misturar cartões antigos
    organizados manualmente com a produção real da oficina.
    """
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    # Define o range de datas baseado no filtro
    if period == "today":
        date_start = today_str + "T00:00:00"
        date_end = today_str + "T23:59:59"
    elif period == "week":
        start_dt = now - timedelta(days=7)
        date_start = start_dt.strftime("%Y-%m-%d") + "T00:00:00"
        date_end = today_str + "T23:59:59"
    elif period == "month":
        date_start = now.strftime("%Y-%m-01") + "T00:00:00"
        date_end = today_str + "T23:59:59"
    elif period == "custom" and start_date and end_date:
        date_start = f"{start_date}T00:00:00"
        date_end = f"{end_date}T23:59:59"
    else:  # 'all'
        date_start = "2000-01-01T00:00:00"
        date_end = "2099-12-31T23:59:59"

    with connect() as conn:
        cutoff_row = conn.execute("SELECT value FROM settings WHERE key = 'metrics_start_at'").fetchone()
        metrics_start_at = (cutoff_row["value"] if cutoff_row else "") or ""

        effective_start = max(date_start, metrics_start_at) if metrics_start_at else date_start

        # Busca cartões que tiveram orçamento concluído, finalização ou atividade real dentro do período pós-marco
        query = """
            SELECT c.*, l.title as list_title, l.role as list_role, l.is_tech as list_is_tech
            FROM cards c
            JOIN lists l ON c.list_id = l.id
            WHERE (
                (c.finished_at IS NOT NULL AND c.finished_at != '' AND c.finished_at BETWEEN ? AND ?)
                OR (c.fim_manutencao IS NOT NULL AND c.fim_manutencao != '' AND c.fim_manutencao BETWEEN ? AND ?)
                OR (c.fim_orcamento IS NOT NULL AND c.fim_orcamento != '' AND c.fim_orcamento BETWEEN ? AND ?)
                OR (c.quote_finished_at IS NOT NULL AND c.quote_finished_at != '' AND c.quote_finished_at BETWEEN ? AND ?)
                OR (l.is_tech = 1 AND (
                    (c.inicio_orcamento IS NOT NULL AND c.inicio_orcamento BETWEEN ? AND ?)
                    OR (c.inicio_manutencao IS NOT NULL AND c.inicio_manutencao BETWEEN ? AND ?)
                ))
            )
        """
        params = [
            effective_start, date_end,
            effective_start, date_end,
            effective_start, date_end,
            effective_start, date_end,
            effective_start, date_end,
            effective_start, date_end,
        ]

        if tech_filter:
            query += " AND (c.tech_name LIKE ? OR c.evaluator_tech LIKE ? OR c.finisher_tech LIKE ?)"
            p = f"%{tech_filter}%"
            params.extend([p, p, p])

        query += " ORDER BY c.updated_at DESC, c.id DESC"
        rows = conn.execute(query, params).fetchall()

        # Busca a lista oficial de técnicos para o resumo por técnico
        tech_rows = conn.execute("SELECT title FROM lists WHERE is_tech = 1 ORDER BY position ASC").fetchall()
        tech_names = [r["title"].replace("TEC. ", "").strip() for r in tech_rows]
        if not tech_names:
            tech_names = DEFAULT_TECHS[:]

        # Consulta específica para balanças paradas aguardando resposta do cliente hoje
        paradas_row = conn.execute("""
            SELECT COUNT(*) as c FROM cards c
            JOIN lists l ON c.list_id = l.id
            WHERE c.pipeline_phase = 'ORCAMENTOS_ENVIADOS'
               OR l.title LIKE '%ENVIADO%'
        """).fetchone()
        balancas_aguardando_cliente = paradas_row["c"] if paradas_row else 0

    cards_list = []
    total_prontas = 0
    total_orcamentos_feitos = 0
    soma_tempo_orc = 0
    soma_tempo_man = 0
    qtd_com_tempo_orc = 0
    qtd_com_tempo_man = 0

    # Inicializa estatísticas individuais por técnico
    tech_stats = {
        name: {
            "name": name,
            "orcamentos_count": 0,
            "prontas_count": 0,
            "tempo_total_segundos": 0,
            "tempo_medio_segundos": 0
        }
        for name in tech_names
    }

    for r in rows:
        c = dict(r)
        os_num = c["os_number"]
        eval_tech = c.get("evaluator_tech") or c.get("tech_name") or ""
        fin_tech = c.get("finisher_tech") or c.get("tech_name") or ""
        display_tech = fin_tech or eval_tech or "Oficina"
        phase = c.get("pipeline_phase") or "ORCAMENTOS_A_FAZER"

        t_orc = int(c.get("tempo_orcamento_segundos") or 0)
        t_man = int(c.get("tempo_manutencao_segundos") or 0)

        # Se houver timestamps mas tempo zerado, calcula na hora
        if t_orc == 0 and c.get("inicio_orcamento") and c.get("fim_orcamento"):
            try:
                dt_ini = datetime.fromisoformat(c["inicio_orcamento"])
                dt_fim = datetime.fromisoformat(c["fim_orcamento"])
                t_orc = max(1, int((dt_fim - dt_ini).total_seconds()))
            except Exception:
                pass

        if t_man == 0 and c.get("inicio_manutencao") and c.get("fim_manutencao"):
            try:
                dt_ini = datetime.fromisoformat(c["inicio_manutencao"])
                dt_fim = datetime.fromisoformat(c["fim_manutencao"])
                t_man = max(1, int((dt_fim - dt_ini).total_seconds()))
            except Exception:
                pass

        t_liq = t_orc + t_man

        orc_ts = c.get("fim_orcamento") or c.get("quote_finished_at") or ""
        fin_ts = c.get("finished_at") or c.get("fim_manutencao") or ""

        has_orc_feito = bool(orc_ts and effective_start <= orc_ts <= date_end)
        is_pronta = bool(
            fin_ts
            and effective_start <= fin_ts <= date_end
            and (c.get("list_role") in ("pronta", "finalizada") or phase == "PRONTAS" or c.get("finished_at"))
        )

        if is_pronta:
            total_prontas += 1
        if has_orc_feito:
            total_orcamentos_feitos += 1

        if has_orc_feito and t_orc > 0:
            soma_tempo_orc += t_orc
            qtd_com_tempo_orc += 1

        if is_pronta and t_man > 0:
            soma_tempo_man += t_man
            qtd_com_tempo_man += 1

        # Acumula Orçamentos Feitos para o técnico avaliador
        if has_orc_feito and eval_tech:
            for t_key in tech_stats:
                if t_key.upper() in eval_tech.upper():
                    tech_stats[t_key]["orcamentos_count"] += 1
                    tech_stats[t_key]["tempo_total_segundos"] += t_orc
                    break

        # Acumula Balanças Prontas para o técnico finalizador
        if is_pronta and fin_tech:
            for t_key in tech_stats:
                if t_key.upper() in fin_tech.upper():
                    tech_stats[t_key]["prontas_count"] += 1
                    tech_stats[t_key]["tempo_total_segundos"] += t_man
                    break

        cards_list.append({
            "os_number": os_num,
            "client_name": c["client_name"],
            "equipment_model": c.get("equipment_model") or c.get("equipment_type") or "Balança Toledo",
            "serial_number": c.get("serial_number") or "",
            "tech_name": display_tech.replace("TEC. ", "").strip(),
            "phase": phase,
            "list_title": c.get("list_title") or "",
            "tempo_orcamento_str": format_duration(t_orc) if t_orc > 0 else "-",
            "tempo_manutencao_str": format_duration(t_man) if t_man > 0 else "-",
            "tempo_liquido_str": format_duration(t_liq) if t_liq > 0 else "-",
            "tempo_liquido_segundos": t_liq,
            "created_at": c.get("created_at", "")[:16].replace("T", " "),
            "finished_at": (c.get("finished_at") or "")[:16].replace("T", " ") if is_pronta else "Em andamento"
        })

    # Calcula médias dos técnicos
    for t_key, stats in tech_stats.items():
        total_ops = stats["orcamentos_count"] + stats["prontas_count"]
        if total_ops > 0 and stats["tempo_total_segundos"] > 0:
            stats["tempo_medio_segundos"] = int(stats["tempo_total_segundos"] / total_ops)
        stats["tempo_total_str"] = format_duration(stats["tempo_total_segundos"])
        stats["tempo_medio_str"] = format_duration(stats["tempo_medio_segundos"])

    media_orc_seg = int(soma_tempo_orc / qtd_com_tempo_orc) if qtd_com_tempo_orc > 0 else 0
    media_man_seg = int(soma_tempo_man / qtd_com_tempo_man) if qtd_com_tempo_man > 0 else 0

    return {
        "period": period,
        "metrics_start_at": metrics_start_at,
        "kpis": {
            "total_prontas": total_prontas,
            "total_orcamentos_feitos": total_orcamentos_feitos,
            "tempo_medio_orcamento_str": format_duration(media_orc_seg) if media_orc_seg > 0 else "0m",
            "tempo_medio_manutencao_str": format_duration(media_man_seg) if media_man_seg > 0 else "0m",
            "balancas_aguardando_cliente": balancas_aguardando_cliente
        },
        "technicians_performance": list(tech_stats.values()),
        "os_details": cards_list
    }
