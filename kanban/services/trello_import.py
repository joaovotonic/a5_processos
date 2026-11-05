"""
Importador oficial do JSON exportado do Trello (json_oficina.json) para o banco SQLite A5 Kanban.
Limpa dados de teste anteriores, padroniza listas, etiquetas, O.S., clientes, datas (fuso Manaus UTC-4)
e reconstrói histórico de técnicos a partir das actions do Trello.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..backup import perform_daily_backup
from ..config import BACKUP_DIR, BASE_DIR, DEFAULT_EQUIPMENT_TYPE
from ..database import INITIAL_LABELS, INITIAL_LISTS, connect
from ..utils import format_os_number

MANAUS_TZ = timezone(timedelta(hours=-4))

# Mapeamento semântico de etiquetas do Trello para o padrão A5 Kanban
LABEL_COLOR_MAP = {
    "FINALIZADO": ("#10B981", "#FFFFFF", 2),
    "AGUARDANDO": ("#F59E0B", "#FFFFFF", 1),
    "EM GARANTIA": ("#8B5CF6", "#FFFFFF", 9),
    "ORÇAMENTO ENVIADO": ("#0EA5E9", "#FFFFFF", 2),
    "NÃO AUTORIZADO": ("#EF4444", "#FFFFFF", 0),
    "ORÇ. APROVADO": ("#10B981", "#FFFFFF", 3),
    "SEM CONSERTO": ("#EC4899", "#FFFFFF", 1),
    "URGENTE": ("#EF4444", "#FFFFFF", 10),
    "RETORNO": ("#06B6D4", "#FFFFFF", 4),
    "FALTA PEÇA": ("#F97316", "#FFFFFF", 3),
    "FEITO ORC.": ("#0EA5E9", "#FFFFFF", 2),
    "FEITO ORÇ.": ("#0EA5E9", "#FFFFFF", 2),
    "EM TESTES": ("#64748B", "#FFFFFF", 2),
    "EM SERVIÇO": ("#3B82F6", "#FFFFFF", 2),
    "AGUARDANDO PAGAMENTO": ("#EC4899", "#FFFFFF", 1),
}

# Mapeamento de nomes de listas de técnicos do Trello para nomes limpos de técnicos
TECH_LIST_TO_NAME = {
    "TEC. JOÃO OTONI PIRES": "João Otoni",
    "TEC. JOÃO OTONI": "João Otoni",
    "TEC. ENZO PIRES": "Enzo Gabriel",
    "TEC. ENZO GABRIEL": "Enzo Gabriel",
    "TEC. GUILHERME PIRES": "Guilherme",
    "TEC. GUILHERME": "Guilherme",
    "TEC. WISLEY PIRES": "Wisley",
    "TEC. WISLEY": "Wisley",
    "TEC. IAGO PIRES": "Iago",
    "TEC. IAGO": "Iago",
    "TEC. ANTONIO": "ANTONIO",
    "TEC. ANTONIO SERGIO": "ANTONIO",
    "TEC. KAIO": "Kaio",
}


def _utc_to_manaus_iso(iso_str: Optional[str]) -> str:
    """Converte timestamp ISO UTC do Trello (ex: 2026-11-04T20:40:38.060Z) para ISO local Manaus (UTC-4)."""
    if not iso_str:
        return datetime.now(MANAUS_TZ).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        local_dt = dt.astimezone(MANAUS_TZ).replace(tzinfo=None)
        return local_dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return datetime.now(MANAUS_TZ).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S")


def _objectid_to_manaus_iso(oid: str, fallback_iso: str) -> str:
    """Extrai a data de criação exata dos primeiros 8 caracteres hexadecimais do ID do cartão no Trello."""
    try:
        if oid and len(oid) >= 8:
            ts = int(oid[:8], 16)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(MANAUS_TZ).replace(tzinfo=None)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        pass
    return fallback_iso


def parse_trello_card_title(raw_name: str, trello_list_name: str = "") -> Dict[str, str]:
    """
    Analisa o título do cartão do Trello no padrão da A5 Tecnologia.
    Exemplos:
      'O.S. 026550/PONTES EMPREEND.' -> os='026550', client='PONTES EMPREEND.'
      'O.S. 026758/MERCADINHO PALMEIRA*IMPRESSORA' -> os='026758', client='MERCADINHO PALMEIRA', note='IMPRESSORA'
      'O.S. 026806/MERCANTIL REAL*NÃO PRECISA DA FONTE' -> os='026806', client='MERCANTIL REAL', note='NÃO PRECISA DA FONTE'
      '22690 - DB DISTRITO - 2098' -> os='022690', client='DB DISTRITO', model='2098'
    """
    text = (raw_name or "").strip()

    # 1. Extrai número da O.S.
    os_raw = ""
    remainder = text

    # Caso tenha duas O.S. juntas ex: "O.S. 026434/026435 ATACADÃO CIDADE NOVA"
    m_double = re.match(r"^(?:O\.?S\.?\s*[\-:]?\s*)?(\d{4,7})\s*/\s*(\d{4,7})\s*(?:[/\-–—]\s*|\s+)(.+)$", text, re.IGNORECASE)
    extra_os_note = ""
    if m_double:
        os_raw = m_double.group(1)
        extra_os_note = f"O.S. Conjunta: {m_double.group(1)}/{m_double.group(2)}"
        remainder = m_double.group(3).strip()
    else:
        m_std = re.match(r"^(?:O\.?S\.?\s*[\-:]?\s*|ORÇ\.?\s*)?(\d{3,7})\s*(?:[/\-–—;]\s*|\s+)(.+)$", text, re.IGNORECASE)
        if m_std:
            os_raw = m_std.group(1)
            remainder = m_std.group(2).strip()
        else:
            m_any = re.search(r"\b(\d{4,7})\b", text)
            if m_any:
                os_raw = m_any.group(1)
                before = text[:m_any.start()].strip(" /-–—*:")
                after = text[m_any.end():].strip(" /-–—*:")
                remainder = after if after else before
            else:
                os_raw = ""
                remainder = text

    os_formatted = format_os_number(os_raw) if os_raw else ""

    # 2. Separa observações após '*'
    notes_list = []
    if extra_os_note:
        notes_list.append(extra_os_note)

    if "*" in remainder:
        parts = [p.strip() for p in remainder.split("*") if p.strip()]
        client_part = parts[0] if parts else remainder
        for p in parts[1:]:
            notes_list.append(p)
    else:
        client_part = remainder

    # 3. Verifica se há barra secundária indicando observação (ex: "SUPER NOVA MANÔA/POR UMA FONTE" ou "DB PARAÍBA/AGUARDANDO PAGAMENTO")
    if "/" in client_part:
        subparts = [sp.strip() for sp in client_part.split("/") if sp.strip()]
        if len(subparts) >= 2:
            # Se a segunda parte parecer defeito, pagamento ou instrução
            second_upper = subparts[1].upper()
            if any(k in second_upper for k in ("FONTE", "ERRO", "AGUARDANDO", "PAGAMENTO", "FOI PRA", "CERTIFICADO", "GARANTIA", "CARTÃO", "DDF", "TECLADO", "RETORNO")):
                client_part = subparts[0]
                notes_list.extend(subparts[1:])

    # 4. Limpa prefixos ou traços residuais no nome do cliente
    client_clean = client_part.strip(" /-–—*:")
    if not client_clean:
        client_clean = text

    # 5. Detecta tipo e modelo de equipamento
    full_upper = f"{text} {trello_list_name}".upper()
    eq_type = DEFAULT_EQUIPMENT_TYPE
    eq_model = ""

    if "8217" in full_upper:
        eq_model = "8217"
    elif "2098" in full_upper:
        eq_model = "2098"
        if client_clean.endswith("- 2098"):
            client_clean = client_clean[:-6].strip()
    elif "2099" in full_upper:
        eq_model = "2099"
        if client_clean.endswith("- 2099"):
            client_clean = client_clean[:-6].strip()
    elif "PRIX 6" in full_upper:
        eq_model = "Prix 6"
    elif "PRIX 5" in full_upper:
        eq_model = "Prix 5"
    elif "PRIX 4" in full_upper:
        eq_model = "Prix 4"
    elif "PRIX 3" in full_upper:
        eq_model = "Prix 3"
    elif "ADVANCED" in full_upper:
        eq_model = "Advanced"

    if "IMPRESSORA" in full_upper:
        eq_type = "Impressora Térmica"
    elif "FATIADOR" in full_upper:
        eq_type = "Fatiador"
    elif "PALETEIRA" in full_upper:
        eq_type = "Paleteira Pesadora"
    elif "LEITOR" in full_upper:
        eq_type = "Leitor de Código de Barras"
    elif "RELÓGIO" in full_upper or "RELOGIO" in full_upper:
        eq_type = "Relógio"
    elif "UPX" in full_upper:
        eq_type = "Balança UPX"
    elif "LABELA" in full_upper:
        eq_model = eq_model or "Labela"

    notes_str = " | ".join(notes_list)

    return {
        "os_number": os_formatted,
        "client_name": client_clean.upper(),
        "equipment_type": eq_type,
        "equipment_model": eq_model,
        "notes": notes_str,
    }


def import_trello_json(json_path: str) -> Dict[str, Any]:
    """
    Executa a importação completa do arquivo JSON do Trello para o banco SQLite local.
    Zera os cartões antigos e reconstrói listas, etiquetas, cartões, clientes, histórico e backup.
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    trello_lists = {l["id"]: l["name"].strip() for l in data.get("lists", [])}
    trello_cards = data.get("cards", [])
    trello_actions = data.get("actions", [])

    # 1. Analisa as actions do Trello em ordem cronológica para descobrir qual técnico atendeu cada cartão
    card_tech_info: Dict[str, Dict[str, str]] = {}
    card_moves_history: Dict[str, List[Dict[str, str]]] = {}

    sorted_actions = sorted(trello_actions, key=lambda a: a.get("date") or "")
    for act in sorted_actions:
        if act.get("type") != "updateCard":
            continue
        adata = act.get("data") or {}
        if "listBefore" not in adata or "listAfter" not in adata:
            continue
        cid = (adata.get("card") or {}).get("id")
        if not cid:
            continue
        l_before = (adata.get("listBefore") or {}).get("name", "").strip()
        l_after = (adata.get("listAfter") or {}).get("name", "").strip()
        move_dt = _utc_to_manaus_iso(act.get("date"))

        card_moves_history.setdefault(cid, []).append({
            "from_list": l_before,
            "to_list": l_after,
            "timestamp": move_dt,
        })

        info = card_tech_info.setdefault(cid, {"evaluator": "", "finisher": "", "last_tech": ""})
        for lname in (l_before.upper(), l_after.upper()):
            if lname in TECH_LIST_TO_NAME:
                t_clean = TECH_LIST_TO_NAME[lname]
                if not info["evaluator"]:
                    info["evaluator"] = t_clean
                info["last_tech"] = t_clean
                if "FINALIZAD" in l_after.upper():
                    info["finisher"] = t_clean

    with connect() as conn:
        cursor = conn.cursor()

        # 2. Zera cartões, histórico, rotas externas de teste e pré-entradas anteriores
        cursor.execute("DELETE FROM card_history;")
        cursor.execute("DELETE FROM cards;")
        cursor.execute("DELETE FROM pending_entries;")
        cursor.execute("DELETE FROM clients;")
        cursor.execute("DELETE FROM external_orders;")
        cursor.execute("DELETE FROM external_routes;")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('cards', 'card_history', 'pending_entries', 'clients', 'external_orders', 'external_routes');")

        # 3. Padroniza as listas da esteira na ordem oficial
        cursor.execute("DELETE FROM lists;")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'lists';")

        standard_lists = [
            {"title": "ORÇAMENTOS", "is_tech": 0, "role": "orcamento"},
            {"title": "TEC. João Otoni", "is_tech": 1, "role": "tech"},
            {"title": "TEC. Enzo Gabriel", "is_tech": 1, "role": "tech"},
            {"title": "TEC. Guilherme", "is_tech": 1, "role": "tech"},
            {"title": "TEC. Wisley", "is_tech": 1, "role": "tech"},
            {"title": "TEC. IAGO", "is_tech": 1, "role": "tech"},
            {"title": "TEC. ANTONIO", "is_tech": 1, "role": "tech"},
            {"title": "ORÇAMENTOS FEITOS", "is_tech": 0, "role": "orcamentos_feitos"},
            {"title": "ORÇAMENTOS ENVIADOS", "is_tech": 0, "role": "orcamentos_enviados"},
            {"title": "APROVADOS", "is_tech": 0, "role": "aprovados"},
            {"title": "NÃO AUTORIZADOS", "is_tech": 0, "role": "nao_autorizados"},
            {"title": "FINALIZADAS", "is_tech": 0, "role": "finalizada"},
        ]
        # Mantém capitalização amigável usada no sistema
        standard_lists[5]["title"] = "TEC. Iago"

        list_id_by_title: Dict[str, int] = {}
        for idx, item in enumerate(standard_lists):
            cursor.execute(
                "INSERT INTO lists (title, position, is_tech, role) VALUES (?, ?, ?, ?)",
                (item["title"], idx, item["is_tech"], item["role"])
            )
            list_id_by_title[item["title"].upper()] = cursor.lastrowid

        # 4. Padroniza etiquetas na tabela labels
        cursor.execute("DELETE FROM labels;")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'labels';")
        for lbl_name, (bg_color, txt_color, prio) in LABEL_COLOR_MAP.items():
            if lbl_name == "FEITO ORC.":
                continue  # evita duplicar com FEITO ORÇ.
            cursor.execute(
                "INSERT INTO labels (name, color, text_color, priority) VALUES (?, ?, ?, ?)",
                (lbl_name, bg_color, txt_color, prio)
            )

        # 5. Filtra cartões abertos (não arquivados) e ordena por posição do Trello
        open_cards = [c for c in trello_cards if not c.get("closed")]
        open_cards.sort(key=lambda c: float(c.get("pos") or 0))

        used_os_numbers = set()
        position_counters: Dict[int, int] = {lid: 0 for lid in list_id_by_title.values()}
        imported_count = 0
        imported_by_list: Dict[str, int] = {}
        unique_clients = set()

        for c in open_cards:
            cid = c.get("id", "")
            t_list_name = trello_lists.get(c.get("idList"), "").strip()
            t_list_upper = t_list_name.upper()

            # Ignora cartão de template
            if t_list_upper == "TEMPLATE BASE":
                continue

            raw_name = (c.get("name") or "").strip()
            if not raw_name:
                continue

            parsed = parse_trello_card_title(raw_name, t_list_name)
            base_os = parsed["os_number"]
            client_name = parsed["client_name"]
            eq_type = parsed["equipment_type"]
            eq_model = parsed["equipment_model"]
            extra_notes = parsed["notes"]

            # Processa etiquetas do cartão
            card_labels = []
            card_label_names_upper = set()
            for t_lbl in c.get("labels", []):
                lname = (t_lbl.get("name") or "").strip()
                if not lname:
                    continue
                lname_upper = lname.upper()
                if lname_upper == "FEITO ORC.":
                    lname = "FEITO ORÇ."
                    lname_upper = "FEITO ORÇ."
                color_info = LABEL_COLOR_MAP.get(lname_upper, ("#64748B", "#FFFFFF", 1))
                card_labels.append({
                    "name": lname.upper(),
                    "color": color_info[0],
                    "text_color": color_info[1],
                    "priority": color_info[2],
                })
                card_label_names_upper.add(lname_upper)

            # Se o texto mencionar AGUARDANDO PAGAMENTO, adiciona etiqueta correspondente
            if "AGUARDANDO PAGAMENTO" in raw_name.upper() and "AGUARDANDO PAGAMENTO" not in card_label_names_upper:
                c_info = LABEL_COLOR_MAP["AGUARDANDO PAGAMENTO"]
                card_labels.append({
                    "name": "AGUARDANDO PAGAMENTO",
                    "color": c_info[0],
                    "text_color": c_info[1],
                    "priority": c_info[2],
                })
                card_label_names_upper.add("AGUARDANDO PAGAMENTO")

            # Se o texto mencionar (RETORNO) e não tiver etiqueta RETORNO
            if "RETORNO" in raw_name.upper() and "RETORNO" not in card_label_names_upper:
                c_info = LABEL_COLOR_MAP["RETORNO"]
                card_labels.append({
                    "name": "RETORNO",
                    "color": c_info[0],
                    "text_color": c_info[1],
                    "priority": c_info[2],
                })
                card_label_names_upper.add("RETORNO")

            # Determina a coluna de destino no nosso Kanban, pipeline_phase e quote_status
            target_col_title = "FINALIZADAS"
            pipeline_phase = "FINALIZADAS"
            quote_status = "approved"
            is_finished = False

            if t_list_upper == "FINALIZADAS":
                target_col_title = "FINALIZADAS"
                pipeline_phase = "FINALIZADAS"
                quote_status = "approved"
                is_finished = True
            elif t_list_upper == "ORCAMENTOS":
                target_col_title = "ORÇAMENTOS"
                pipeline_phase = "ORCAMENTOS_A_FAZER"
                quote_status = "pending_claim"
            elif t_list_upper == "ANALISES FEITAS":
                target_col_title = "ORÇAMENTOS FEITOS"
                pipeline_phase = "ORCAMENTOS_FEITOS"
                quote_status = "done"
            elif t_list_upper == "ORCAMENTOS ENVIADOS":
                target_col_title = "ORÇAMENTOS ENVIADOS"
                pipeline_phase = "ORCAMENTOS_ENVIADOS"
                quote_status = "done"
            elif t_list_upper == "APROVADAS":
                target_col_title = "APROVADOS"
                pipeline_phase = "ORCAMENTOS_APROVADOS"
                quote_status = "approved"
            elif "NÃO AUTORIZAD" in t_list_upper or "NAO AUTORIZAD" in t_list_upper:
                target_col_title = "NÃO AUTORIZADOS"
                pipeline_phase = "NAO_AUTORIZADO"
                quote_status = "cancelled"
            elif t_list_upper in TECH_LIST_TO_NAME:
                t_mapped = TECH_LIST_TO_NAME[t_list_upper]
                target_col_title = f"TEC. {t_mapped}".upper()
                pipeline_phase = "EM_ORCAMENTO"
                quote_status = "in_progress"
            elif t_list_upper == "PENDÊNCIAS":
                # Todos os 13 cartões de PENDÊNCIAS têm etiqueta FINALIZADO (aguardando pagamento/retirada)
                target_col_title = "FINALIZADAS"
                pipeline_phase = "FINALIZADAS"
                quote_status = "approved"
                is_finished = True
                if "PENDÊNCIAS" not in extra_notes.upper():
                    extra_notes = f"PENDÊNCIAS: {extra_notes}".strip(": ")
            elif t_list_upper == "DB 8217":
                if "FINALIZADO" in card_label_names_upper:
                    target_col_title = "FINALIZADAS"
                    pipeline_phase = "FINALIZADAS"
                    quote_status = "approved"
                    is_finished = True
                else:
                    target_col_title = "APROVADOS"
                    pipeline_phase = "ORCAMENTOS_APROVADOS"
                    quote_status = "approved"
            elif t_list_upper == "SR. JACSON":
                if "ORÇ. APROVADO" in card_label_names_upper:
                    target_col_title = "APROVADOS"
                    pipeline_phase = "ORCAMENTOS_APROVADOS"
                    quote_status = "approved"
                else:
                    target_col_title = "ORÇAMENTOS FEITOS"
                    pipeline_phase = "ORCAMENTOS_FEITOS"
                    quote_status = "done"
                extra_notes = f"SR. JACSON | {extra_notes}".strip(" |")

            target_list_id = list_id_by_title.get(target_col_title, list_id_by_title["FINALIZADAS"])

            # Garante número de O.S. único sem perder nenhum cartão (ex: retornos da mesma O.S.)
            if not base_os:
                # Cartão sem dígitos (ex: 'VERIFICAR BALANÇA DA LFC')
                slug = re.sub(r"[^A-Z0-9]", "", client_name)[:6] or "TRELLO"
                final_os = f"S/N-{slug}"
            else:
                final_os = base_os

            if final_os in used_os_numbers:
                if "RETORNO" in raw_name.upper() or "VOLTOU" in raw_name.upper():
                    candidate = f"{final_os}-R"
                else:
                    candidate = f"{final_os}-2"
                seq = 2
                while candidate in used_os_numbers:
                    seq += 1
                    candidate = f"{final_os}-{seq}"
                final_os = candidate

            used_os_numbers.add(final_os)

            # Datas de criação e última movimentação
            last_act_iso = _utc_to_manaus_iso(c.get("dateLastActivity"))
            created_iso = _objectid_to_manaus_iso(cid, last_act_iso)
            finished_iso = last_act_iso if is_finished else None

            # Técnicos reconstruídos das actions ou da lista atual
            t_info = card_tech_info.get(cid, {})
            evaluator_tech = t_info.get("evaluator", "")
            finisher_tech = t_info.get("finisher", "")
            tech_name = t_info.get("last_tech", "")

            if t_list_upper in TECH_LIST_TO_NAME:
                cur_tech = TECH_LIST_TO_NAME[t_list_upper]
                tech_name = cur_tech
                if not evaluator_tech:
                    evaluator_tech = cur_tech

            # Se o texto mencionar o técnico (ex: "EDSON TROCOU A PCI")
            if not tech_name and "EDSON" in raw_name.upper():
                tech_name = "Edson"

            # Descrição e observações
            desc_clean = (c.get("desc") or "").strip()
            # Ignora se a descrição for apenas o template vazio
            if "📅 DATA DE ENTRADA:" in desc_clean and "(Ex: não pesa" in desc_clean:
                desc_clean = ""

            reported_defect = extra_notes
            if desc_clean:
                reported_defect = f"{extra_notes} | {desc_clean}".strip(" |") if extra_notes else desc_clean

            admin_notes = extra_notes

            pos = position_counters[target_list_id]
            position_counters[target_list_id] += 1

            cursor.execute("""
                INSERT INTO cards (
                    os_number, client_name, equipment_type, equipment_model,
                    serial_number, shelf_location, reported_defect,
                    list_id, position, labels_json,
                    quote_status, pipeline_phase,
                    evaluator_tech, finisher_tech, tech_name,
                    admin_notes,
                    created_at, updated_at, moved_at, finished_at,
                    fim_manutencao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                final_os,
                client_name,
                eq_type,
                eq_model,
                "",
                "",
                reported_defect,
                target_list_id,
                pos,
                json.dumps(card_labels, ensure_ascii=False),
                quote_status,
                pipeline_phase,
                evaluator_tech,
                finisher_tech,
                tech_name,
                admin_notes,
                created_iso,
                last_act_iso,
                last_act_iso,
                finished_iso,
                finished_iso,
            ))
            new_card_id = cursor.lastrowid
            imported_count += 1
            imported_by_list[target_col_title] = imported_by_list.get(target_col_title, 0) + 1

            if client_name and len(client_name) >= 2:
                unique_clients.add(client_name)

            # Registra histórico de movimentações do Trello na tabela card_history
            moves = card_moves_history.get(cid, [])
            if moves:
                for mv in moves:
                    cursor.execute("""
                        INSERT INTO card_history (
                            card_id, os_number, from_list, to_list, actor, action_description, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        new_card_id,
                        final_os,
                        mv["from_list"],
                        mv["to_list"],
                        "Trello (Histórico)",
                        f"Movido de '{mv['from_list']}' para '{mv['to_list']}'",
                        mv["timestamp"],
                    ))
            else:
                cursor.execute("""
                    INSERT INTO card_history (
                        card_id, os_number, from_list, to_list, actor, action_description, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_card_id,
                    final_os,
                    "Trello",
                    target_col_title,
                    "Importação Trello",
                    f"Importado do Trello na lista '{target_col_title}'",
                    last_act_iso,
                ))

        # 6. Popula a tabela de clientes para autocompletar imediato na recepção/admin
        now_iso = datetime.now(MANAUS_TZ).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S")
        for cl_name in sorted(unique_clients):
            cursor.execute("""
                INSERT INTO clients (client_name, trade_name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (cl_name, cl_name, now_iso, now_iso))

    # 7. Limpa dumps antigos de teste na pasta backups/ e gera um novo dump JSON + DB atualizado
    if os.path.exists(BACKUP_DIR):
        for fname in os.listdir(BACKUP_DIR):
            fpath = os.path.join(BACKUP_DIR, fname)
            if os.path.isfile(fpath) and (fname.endswith(".json") or fname.endswith(".db")):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    backup_file = perform_daily_backup(force=True)

    return {
        "success": True,
        "total_imported": imported_count,
        "unique_clients": len(unique_clients),
        "by_list": imported_by_list,
        "backup_file": backup_file,
    }


if __name__ == "__main__":
    import sys
    target_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "json_oficina.json")
    result = import_trello_json(target_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))

