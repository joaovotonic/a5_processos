"""Leitura do quadro Kanban completo e métricas da gerência."""
import json
import re
from datetime import datetime

from ..config import SLA_HOURS
from ..database import connect


DEFAULT_QUOTE_DATA = {
    "weight_unit": "",
    "accessories": {
        "cabo_alimentacao": "",
        "fonte_externa": "",
        "tampa_impressor": "",
        "rebobinador": "",
        "prato": "",
    },
    "incoming_seal": {"type": "", "number": ""},
    "incoming_stamp": {"type": "", "number": ""},
    "contamination": [],
    "weights_initial": {
        "1kg": "", "5kg": "", "10kg": "", "15kg": "", "20kg": "",
        "40kg": "", "80kg": "", "100kg": "", "200kg": "", "400kg": "",
        "1g": "", "5g": "", "10g": "", "20g": "", "50g": "",
        "100g": "", "200g": "", "500g": "", "1000g": "", "2000g": "",
    },
    "weights_final": {
        "1kg": "", "5kg": "", "10kg": "", "15kg": "", "20kg": "",
        "50kg": "", "80kg": "", "100kg": "", "200kg": "", "400kg": "",
        "1g": "", "5g": "", "10g": "", "20g": "", "50g": "",
        "100g": "", "200g": "", "500g": "", "1000g": "", "2000g": "",
    },
    "technical_report": "",
    "solution": "",
    "parts_items": [],
    "service_checks": {
        "revisao_geral": False,
        "limpeza_externa": False,
        "calibracao_afericao": False,
        "cal_gap_sens": False,
        "calibracao_bater_peso": False,
    },
    "functional_tests": {
        "comunicacao": {"status": "", "note": ""},
        "teclado": {"status": "", "note": ""},
        "impressao": {"status": "", "note": ""},
        "display_traseiro": {"status": "", "note": ""},
    },
}


def detect_weight_unit(equipment_type, equipment_model, quote_data):
    """Detecta se a balança opera em gramas ('g') ou quilos ('kg')."""
    saved_unit = (quote_data or {}).get("weight_unit")
    if saved_unit in ("g", "kg"):
        return saved_unit
    eq_type = (equipment_type or "").upper()
    eq_model = (equipment_model or "").lower()
    if "ANALÍTICA" in eq_type or "ANALITICA" in eq_type or "PRECISÃO" in eq_type or "PRECISAO" in eq_type:
        return "g"
    if re.search(r"\b\d+(?:[.,]\d+)?\s*g\b", eq_model):
        return "g"
    wi = (quote_data or {}).get("weights_initial") or {}
    wf = (quote_data or {}).get("weights_final") or {}
    gram_keys = ("1g", "5g", "10g", "20g", "50g", "100g", "200g", "500g", "1000g", "2000g")
    if any(wi.get(k) for k in gram_keys) or any(wf.get(k) for k in gram_keys):
        return "g"
    return "kg"


def normalize_quote_data(raw):
    """Mescla o JSON salvo do orçamento com a estrutura padrão da folha técnica."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except Exception:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}

    merged = json.loads(json.dumps(DEFAULT_QUOTE_DATA))
    if raw.get("weight_unit") in ("g", "kg"):
        merged["weight_unit"] = raw.get("weight_unit")

    for k in ("accessories", "incoming_seal", "incoming_stamp", "weights_initial", "weights_final", "service_checks"):
        if isinstance(raw.get(k), dict):
            merged[k].update(raw[k])

    if isinstance(raw.get("functional_tests"), dict):
        for test_key, test_val in raw["functional_tests"].items():
            if test_key in merged["functional_tests"] and isinstance(test_val, dict):
                merged["functional_tests"][test_key].update(test_val)

    if isinstance(raw.get("contamination"), list):
        merged["contamination"] = raw["contamination"]
    if isinstance(raw.get("parts_items"), list):
        merged["parts_items"] = raw["parts_items"]
    if raw.get("technical_report") is not None:
        merged["technical_report"] = str(raw.get("technical_report") or "")
    if raw.get("solution") is not None:
        merged["solution"] = str(raw.get("solution") or "")
    return merged


def _compute_mobile_stage(card):
    if card.get("finished_at"):
        return "finished"
    q_status = (card.get("quote_status") or "pending_claim").strip()
    if q_status == "approved":
        return "finalization"
    if q_status == "done":
        return "waiting_approval"
    if q_status == "in_progress":
        return "quoting"
    return "claim"


def enrich_card(row_dict):
    """Converte campos JSON do cartão e calcula indicadores de SLA (24h), prioridade e estágio do QR Code."""
    card = dict(row_dict)
    if card.get("os_number"):
        from ..utils import format_os_number
        card["os_number"] = format_os_number(card["os_number"])
    card["labels"] = json.loads(card.get("labels_json") or "[]")
    card["entry_photos"] = json.loads(card.get("entry_photos_json") or "[]")
    card["exit_photos"] = json.loads(card.get("exit_photos_json") or "[]")
    card["label_before_photos"] = json.loads(card.get("label_before_photos_json") or "[]")
    card["label_after_photos"] = json.loads(card.get("label_after_photos_json") or "[]")
    card["quote_photos"] = json.loads(card.get("quote_photos_json") or "[]")
    qd = normalize_quote_data(card.get("quote_data_json"))
    qd["weight_unit"] = detect_weight_unit(card.get("equipment_type"), card.get("equipment_model"), qd)
    card["quote_data"] = qd
    card["quote_status"] = card.get("quote_status") or "pending_claim"
    card["admin_notes"] = card.get("admin_notes") or ""
    card["reopen_requested"] = int(card.get("reopen_requested") or 0)
    card["reopen_requested_by"] = card.get("reopen_requested_by") or ""
    card["reopen_requested_at"] = card.get("reopen_requested_at")
    card["mobile_stage"] = _compute_mobile_stage(card)

    # Cálculo de SLA (> 24 horas parado na mesma coluna)
    moved_at_str = card.get("moved_at") or card.get("created_at")
    try:
        moved_dt = datetime.fromisoformat(moved_at_str)
        hours_in_stage = (datetime.now() - moved_dt).total_seconds() / 3600.0
    except Exception:
        hours_in_stage = 0.0

    card["hours_in_stage"] = round(hours_in_stage, 1)
    card["sla_expired"] = hours_in_stage >= SLA_HOURS and card.get("finished_at") is None

    # Identifica se tem etiqueta crítica (URGENTE ou EM GARANTIA)
    label_names = [lbl.get("name", "").upper() for lbl in card["labels"]]
    card["is_urgent"] = "URGENTE" in label_names
    card["is_warranty"] = "EM GARANTIA" in label_names

    return card


def get_full_board():
    """Retorna todo o estado do Kanban (Listas, Cartões ordenados, Etiquetas e Placar do Dia)."""
    from ..backup import perform_daily_backup
    perform_daily_backup(force=False)

    now_dt = datetime.now()
    today_prefix = f"{now_dt.strftime('%Y-%m-%d')}%"

    with connect() as conn:
        # [F-03] Limpa automaticamente cronômetros expirados há mais de 60s caso nenhuma TV estivesse aberta
        active_timers = conn.execute(
            "SELECT id, timer_end_at FROM cards WHERE timer_end_at IS NOT NULL AND timer_end_at != ''"
        ).fetchall()
        for t_row in active_timers:
            try:
                end_dt = datetime.fromisoformat(t_row["timer_end_at"])
                if (now_dt - end_dt).total_seconds() > 60:
                    conn.execute("UPDATE cards SET timer_end_at = NULL WHERE id = ?", (t_row["id"],))
            except Exception:
                conn.execute("UPDATE cards SET timer_end_at = NULL WHERE id = ?", (t_row["id"],))

        lists = [dict(r) for r in conn.execute("SELECT * FROM lists ORDER BY position ASC").fetchall()]
        labels = [dict(r) for r in conn.execute("SELECT * FROM labels ORDER BY priority DESC").fetchall()]
        raw_cards = conn.execute("SELECT * FROM cards ORDER BY position ASC, id ASC").fetchall()
        settings = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings").fetchall()}
        raw_pending = conn.execute("SELECT * FROM pending_entries ORDER BY id DESC").fetchall()

        pending_entries = []
        for pr in raw_pending:
            p_item = dict(pr)
            p_item["photos"] = json.loads(p_item.get("photos_json") or "[]")
            pending_entries.append(p_item)

        # Produtividade do dia (O.S. finalizadas hoje)
        finished_today = conn.execute(
            "SELECT COUNT(*) as total FROM cards WHERE finished_at LIKE ?", (today_prefix,)
        ).fetchone()["total"]

        # Produtividade de hoje por técnico
        tech_scores_today = [dict(r) for r in conn.execute("""
            SELECT tech_name, COUNT(*) as count
            FROM cards
            WHERE finished_at LIKE ? AND tech_name != ''
            GROUP BY tech_name
            ORDER BY count DESC
        """, (today_prefix,)).fetchall()]

    list_map = {lst["id"]: lst for lst in lists}
    cards_by_list = {lst["id"]: [] for lst in lists}
    for r in raw_cards:
        c = enrich_card(r)
        parent_lst = list_map.get(c["list_id"])
        if parent_lst:
            c["list_title"] = parent_lst.get("title", "")
            c["list_role"] = parent_lst.get("role", "")
            c["list_is_tech"] = parent_lst.get("is_tech", 0)
        if c["list_id"] in cards_by_list:
            cards_by_list[c["list_id"]].append(c)

    for lst in lists:
        lst["cards"] = cards_by_list.get(lst["id"], [])
        lst["card_count"] = len(lst["cards"])

    return {
        "lists": lists,
        "labels": labels,
        "settings": settings,
        "pending_entries": pending_entries,
        "stats": {
            "finished_today": finished_today,
            "tech_scores_today": tech_scores_today,
            "total_active": sum(len(l["cards"]) for l in lists if l["role"] != "finalizada")
        }
    }


def get_analytics_summary():
    """Retorna métricas consolidadas (diária, mensal, anual e ranking de técnicos) para /gerencia."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")
    year_str = now.strftime("%Y")

    def count_finished(prefix):
        return conn.execute(
            "SELECT COUNT(*) as c FROM cards WHERE finished_at LIKE ?", (f"{prefix}%",)
        ).fetchone()["c"]

    with connect() as conn:
        daily_count = count_finished(today_str)
        monthly_count = count_finished(month_str)
        yearly_count = count_finished(year_str)

        # Ranking de técnicos no mês
        tech_ranking = [dict(r) for r in conn.execute("""
            SELECT COALESCE(NULLIF(tech_name, ''), 'Não Informado') as tech,
                   COUNT(*) as total
            FROM cards
            WHERE finished_at LIKE ?
            GROUP BY tech
            ORDER BY total DESC
        """, (f"{month_str}%",)).fetchall()]

        finished_cards = conn.execute("""
            SELECT created_at, finished_at FROM cards
            WHERE finished_at IS NOT NULL AND finished_at != ''
        """).fetchall()

        recent_history = [dict(r) for r in conn.execute(
            "SELECT * FROM card_history ORDER BY id DESC LIMIT 100"
        ).fetchall()]

    # Tempo médio de ciclo (criação até finalização)
    durations = []
    for fc in finished_cards:
        try:
            diff_hours = (datetime.fromisoformat(fc["finished_at"])
                          - datetime.fromisoformat(fc["created_at"])).total_seconds() / 3600.0
            if diff_hours >= 0:
                durations.append(diff_hours)
        except Exception:
            pass

    avg_hours = round(sum(durations) / len(durations), 1) if durations else 0.0

    return {
        "daily_count": daily_count,
        "monthly_count": monthly_count,
        "yearly_count": yearly_count,
        "avg_Lead_time_hours": avg_hours,  # nome usado pelo gerencia.html
        "tech_ranking": tech_ranking,
        "recent_history": recent_history
    }

