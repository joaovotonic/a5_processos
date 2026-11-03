"""
Serviço de Relatórios de Produtividade, Métricas de Tempos e Chamados da Diretoria (Sr. Jacson).
Calcula KPIs consolidados, desempenho individual de cada técnico e tempo líquido de bancada por O.S.
"""
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List, Optional

from ..database import connect
from .esteira import format_duration

logger = logging.getLogger("kanban.diretoria")

DEFAULT_TECHS = ["Enzo Gabriel", "Guilherme", "Wisley", "João Otoni", "Iago", "ANTONIO"]


def get_director_productivity_report(
    period: str = "today",
    tech_filter: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Gera o relatório executivo completo para a tela da Diretoria (/diretoria).
    Retorna KPIs consolidados, tabela de técnicos e lista analítica de O.S.
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
        # Busca todas as ordens de serviço no período selecionado
        query = """
            SELECT c.*, l.title as list_title, l.role as list_role, l.is_tech as list_is_tech
            FROM cards c
            JOIN lists l ON c.list_id = l.id
            WHERE (
                (c.created_at BETWEEN ? AND ?)
                OR (c.moved_at BETWEEN ? AND ?)
                OR (c.finished_at BETWEEN ? AND ?)
                OR (c.inicio_orcamento BETWEEN ? AND ?)
                OR (c.inicio_manutencao BETWEEN ? AND ?)
            )
        """
        params = [date_start, date_end, date_start, date_end, date_start, date_end, date_start, date_end, date_start, date_end]

        if tech_filter:
            query += " AND (c.tech_name LIKE ? OR c.evaluator_tech LIKE ? OR c.finisher_tech LIKE ?)"
            p = f"%{tech_filter}%"
            params.extend([p, p, p])

        query += " ORDER BY c.id DESC"
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
        tech = c.get("tech_name") or c.get("evaluator_tech") or c.get("finisher_tech") or "Oficina"
        phase = c.get("pipeline_phase") or "ORCAMENTOS_A_FAZER"

        t_orc = c.get("tempo_orcamento_segundos") or 0
        t_man = c.get("tempo_manutencao_segundos") or 0
        t_liq = c.get("tempo_liquido_segundos") or (t_orc + t_man)

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

        is_pronta = bool(c.get("finished_at") or phase == "PRONTAS" or c.get("list_role") in ("pronta", "finalizada"))
        has_orc_feito = bool(c.get("fim_orcamento") or phase in ("ORCAMENTOS_FEITOS", "ORCAMENTOS_ENVIADOS", "APROVADOS", "EM_MANUTENCAO", "PRONTAS"))

        if is_pronta:
            total_prontas += 1
        if has_orc_feito:
            total_orcamentos_feitos += 1

        if t_orc > 0:
            soma_tempo_orc += t_orc
            qtd_com_tempo_orc += 1

        if t_man > 0:
            soma_tempo_man += t_man
            qtd_com_tempo_man += 1

        # Acumula por técnico
        for t_key in tech_stats:
            if t_key.upper() in tech.upper():
                if has_orc_feito:
                    tech_stats[t_key]["orcamentos_count"] += 1
                if is_pronta:
                    tech_stats[t_key]["prontas_count"] += 1
                tech_stats[t_key]["tempo_total_segundos"] += t_liq
                break

        cards_list.append({
            "os_number": os_num,
            "client_name": c["client_name"],
            "equipment_model": c.get("equipment_model") or c.get("equipment_type") or "Balança Toledo",
            "serial_number": c.get("serial_number") or "",
            "tech_name": tech,
            "phase": phase,
            "list_title": c.get("list_title") or "",
            "tempo_orcamento_str": format_duration(t_orc) if t_orc > 0 else "-",
            "tempo_manutencao_str": format_duration(t_man) if t_man > 0 else "-",
            "tempo_liquido_str": format_duration(t_liq) if t_liq > 0 else "-",
            "tempo_liquido_segundos": t_liq,
            "created_at": c.get("created_at", "")[:16].replace("T", " "),
            "finished_at": (c.get("finished_at") or "")[:16].replace("T", " ") if c.get("finished_at") else "Em andamento"
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
