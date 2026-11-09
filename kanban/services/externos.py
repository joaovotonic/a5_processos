"""
Serviço de Gestão de Chamados Externos e Rotas de Rua (A5 Tecnologia).
Controla o fluxo entre Recepção/Admin (Priscila) e Diretoria (Sr. Jacson),
organizando chamados por turnos (Manhã e Tarde), técnicos (Edson, Antonio, Enzo, João, duplas),
sequenciamento por bairros, geração de texto/cards para WhatsApp, cards conjuntos
e persistência automática de imagens na pasta dedicada ./rotas_imagens/.
"""
import io
import re
import csv
import base64
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..config import ARQUIVADOS_EXTERNOS_DIR, ROTAS_IMAGENS_DIR
from ..database import connect
from ..services.pdf_parser import extract_text_from_pdf, _clean
from ..utils import format_os_number

logger = logging.getLogger("kanban.externos")


# Técnicos e equipes de campo permitidas
KNOWN_FIELD_TECHS = [
    "EDSON",
    "ANTONIO",
    "ENZO",
    "JOAO",
    "ENZO / JOAO",
    "ENZO / EDSON",
    "EDSON / ANTONIO",
    "GUILHERME",
    "WISLEY",
    "IAGO"
]


def get_current_shift() -> str:
    """
    Retorna o turno padrão da rota com base no horário do computador:
    - Se antes das 11h: 'manha'
    - Se a partir das 11h: 'tarde'
    """
    return "manha" if datetime.now().hour < 11 else "tarde"


def format_external_os_number(os_num: str) -> str:
    """
    Padroniza o número da O.S. de chamados externos:
    Remove zeros à esquerda excedentes (ex: '0000026803' -> '26803', '026803' -> '26803').
    Mantém intacto se for alfanumérico (ex: 'TEST26802').
    """
    raw = str(os_num or "").strip()
    if not raw:
        return ""
    if raw.isdigit():
        clean = raw.lstrip("0")
        return clean if clean else "0"
    m = re.match(r"^0+(\d+)$", raw)
    if m:
        return m.group(1)
    return raw


def parse_external_os_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Analisa um PDF de O.S. externa do Teorema e extrai os campos exatos
    da planilha de rota da A5 Tecnologia:
    - Cliente (Nome Fantasia ou Razão)
    - Data Abertura de O.S. (DD/MM/YYYY)
    - Horário (HH:MM)
    - O.S. (número sem zeros extras, ex: 26803)
    - Setor (extraído prioritariamente do descritivo do defeito, ex: RECEBIMENTO, ROTISSERIE)
    - Mod. Equip. (ex: PRIX 6, PL 3000, 8217 LIGHT...)
    - Defeito (descritivo do defeito limpo, sem nome do solicitante)
    - Tarefas a serem realizadas (observações adicionais)
    """
    text = extract_text_from_pdf(pdf_path)
    now_dt = datetime.now()
    shift = get_current_shift()

    data = {
        "os_number": "",
        "client_name": "",
        "open_date": now_dt.strftime("%d/%m/%Y"),
        "open_time": now_dt.strftime("%H:%M"),
        "sector": "",
        "equipment_model": "",
        "reported_defect": "",
        "tasks_notes": "",
        "technician": "",
        "route_date": now_dt.strftime("%Y-%m-%d"),
        "route_shift": shift,
        "status": "pending_route",
        "raw_text": text
    }

    # 1. Número da O.S. (extrai e remove zeros à esquerda: 0000026803 -> 26803)
    os_patterns = [
        r"Ordem\s+de\s+Servi[çc]o\s*:\s*(\d{3,14})",
        r"(?:ORDEM\s+DE\s+SERVI[ÇC]O|O\.?S\.?|NUMERO|N[°ºo]\.?)\s*[:#\s]?\s*(\d{3,14})",
        r"\b(0{2,6}\d{4,10})\b",
    ]
    for pat in os_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            data["os_number"] = format_external_os_number(m.group(1).strip())
            break

    if not data["os_number"] and pdf_path:
        fname_no_ext = os.path.splitext(os.path.basename(pdf_path))[0]
        m_fn = re.search(r"(?:O\.?S\.?|ORDEM)?[_\-\s]*(\d{4,14})", fname_no_ext, re.IGNORECASE)
        if m_fn:
            data["os_number"] = format_external_os_number(m_fn.group(1).strip())

    # 2. Cliente (Fantasia prioritário)
    fantasia_patterns = [
        r"Fantasia\s*:\s*([^\n\r]+)",
        r"(?:NOME\s+FANTASIA|FANTASIA)\s*[:#]?\s*([^\n\r]+)",
    ]
    for pat in fantasia_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            cand = _clean(m.group(1))
            cand = re.sub(r"^\d+\s*[-–—]\s*", "", cand)
            cand = re.split(r"(?:CNPJ|CPF|IE|FONE|TEL|END|DATA|TELEFONE)", cand, flags=re.IGNORECASE)[0]
            cand = _clean(cand)
            if cand and cand.upper() not in ["-", "--", "SEM", "NÃO INFORMADO", "NAO INFORMADO", "N/I", "N/A"]:
                data["client_name"] = cand.upper()
                break

    if not data["client_name"]:
        client_patterns = [
            r"Cliente\s*:\s*([^\n\r]+)",
            r"(?:CLIENTE|RAZ[ÃA]O\s+SOCIAL|NOME\/RAZ[ÃA]O|DESTINAT[ÁA]RIO)\s*[:#]?\s*([^\n\r]+)",
        ]
        for pat in client_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                cand = _clean(m.group(1))
                cand = re.sub(r"^\d+\s*[-–—]\s*", "", cand)
                cand = re.split(r"(?:CNPJ|CPF|IE|FONE|TEL|END|DATA|TELEFONE)", cand, flags=re.IGNORECASE)[0]
                cand = _clean(cand)
                if len(cand) > 2:
                    data["client_name"] = cand.upper()
                    break

    # 3. Data de Abertura (DD/MM/YYYY) — exibida na planilha, mantendo route_date como a data atual de entrada na rota
    date_m = re.search(r"Data\s+(?:de\s+)?abertura\s*:\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if not date_m:
        date_m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text)
    if date_m:
        data["open_date"] = date_m.group(1)

    # 4. Horário de abertura da O.S. (mantendo route_shift pelo horário atual do PC: < 11h manhã, >= 11h tarde)
    time_m = re.search(r"\b(\d{2}:\d{2})(?::\d{2})?\b", text)
    if time_m:
        data["open_time"] = time_m.group(1)

    # 5. Modelo de Equipamento
    model_patterns = [
        r"MARCA\s*(?:\/|E)?\s*MODELO\s*:\s*([^\n\r]+)",
        r"(?:MODELO|EQUIPAMENTO)\s*[:#]?\s*([^\n\r]+)",
        r"\b(PRIX\s+[0-9A-Z\s\+\-\/]+)\b",
        r"\b(PL\s*[-–—]?\s*\d{3,5}(?:/\d+)?)\b",
        r"\b(8217\s+[A-Z0-9\s]+)\b",
        r"\b(TOLEDO\s+[0-9A-Z\s\+\-\/]+)\b",
    ]
    for pat in model_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            cand = _clean(m.group(1))
            cand = re.split(r"(?:PATRIM[ÔO]NIO|END\.?\s*REDE|CAPACIDADE|N[º°]\s*INMETRO|SELO|SERIE|DEFEITO)", cand, flags=re.IGNORECASE)[0]
            cand = _clean(cand).upper()
            if len(cand) > 1:
                cand = re.sub(r"^TOLEDO\s*[-–—]?\s*", "", cand)
                cand = re.sub(r"^PL\s*[-–—]?\s*(\d+)(?:/\d+)?", r"PL \1", cand)
                data["equipment_model"] = cand.strip()
                break

    # 6 & 7. Descritivo do Defeito & Setor da Balança
    # O descritivo do Teorema traz o defeito, o setor da balança e por vezes quem solicitou.
    # Ex: "BALANÇA DO ATACADÃO JAPIIM, SETOR RECEBIMENTO, ELA ESTÁ INOPERANTE, POIS O CLIENTE DEIXOU O PRAZO DE CALIBRAÇÃO EXPIRAR. CHAMADO SOLICITADO PELO ADM LUIZ."
    raw_defect_text = ""
    m_def = re.search(
        r"Defeito\s*:\s*([\s\S]*?)(?=(?:Reduzido|S\s*E\s*R\s*V\s*I\s*Ç\s*O\s*S|I\s*T\s*E\s*N\s*S|Vl\s*Total|Descri[çc][ãa]o:|\Z))",
        text,
        re.IGNORECASE
    )
    if m_def:
        raw_lines = [l.strip() for l in m_def.group(1).strip().split("\n")]
        clean_lines = [l for l in raw_lines if l and l != "."]
        if clean_lines:
            raw_defect_text = " ".join(clean_lines)

    if not raw_defect_text:
        cand_defect = re.search(r"(?:DEFEITO|PROBLEMA|RECLAMA[ÇC][ÃA]O)\s*[:#]?\s*([^\n\r]+)", text, re.IGNORECASE)
        if cand_defect:
            raw_defect_text = _clean(cand_defect.group(1))

    # Extrai o setor da balança prioritariamente do descritivo do defeito
    extracted_sector = ""
    if raw_defect_text:
        m_sec = re.search(
            r"SETOR\s*(?:DE\s*)?[:\-]?\s*([A-Z0-9\s/\+\-]+?)(?=[,;:\.\n\r]|ELA\b|ELE\b|EST[AÁ]\b|POIS\b|COM\b|N[ÃA]O\b|CHAMADO\b|SOLICITADO\b|SOLICITANTE\b|CONTATO\b|$)",
            raw_defect_text,
            re.IGNORECASE
        )
        if m_sec:
            cand = _clean(m_sec.group(1)).upper()
            if len(cand) > 1:
                extracted_sector = cand

        if not extracted_sector:
            m_known = re.search(
                r"\b(ROTISSERIE|RECEBIMENTO|PEIXARIA|A[ÇC]OUGUE|FLV|PADARIA|HORTIFRUTI|LATIC[ÍI]NIOS|FRIOS|ESTOQUE|DEPOSITO|DEPÓSITO|FRENTE\s+DE\s+CAIXA|CAIXA\s+\d+|CHECKOUT\s*\d*|TODAS\s+AS\s+BALAN[ÇC]AS|BALC[ÃA]O)\b",
                raw_defect_text,
                re.IGNORECASE
            )
            if m_known:
                extracted_sector = m_known.group(0).strip().upper()

    # Fallback se não encontrou no descritivo do defeito: busca no texto geral da OS
    if not extracted_sector:
        sector_patterns = [
            r"(?:SETOR|DEPARTAMENTO|DEPTO|LOCAL)\s*[:#]?\s*([A-Z0-9\s\.\-]{3,25})",
            r"\b(ROTISSERIE|RECEBIMENTO|PEIXARIA|A[ÇC]OUGUE|FLV|PADARIA|HORTIFRUTI|LATIC[ÍI]NIOS|FRIOS|ESTOQUE|DEPOSITO|DEPÓSITO|FRENTE\s+DE\s+CAIXA|CAIXA\s+\d+|CHECKOUT\s*\d*)\b",
        ]
        for pat in sector_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                found_sec = _clean(m.group(1) if m.lastindex else m.group(0)).upper()
                if len(found_sec) > 1 and "DATA" not in found_sec:
                    extracted_sector = found_sec
                    break

    data["sector"] = extracted_sector

    # Limpeza do defeito reclamado:
    # 1. Remove solicitante ("Nao precisa pegar o nome de quem solicitou")
    clean_def = raw_defect_text.strip()
    solicitante_patterns = [
        r"[\s,;\.\-]*(?:CHAMADO\s+)?SOLICITADO\s+(?:POR|PELO|PELA|PELOS|PELAS)\s+[\w\s\.\-]+(?:\.|$)",
        r"[\s,;\.\-]*SOLICITANTE\s*[:\-]\s*[\w\s\.\-]+(?:\.|$)",
        r"[\s,;\.\-]*SOL\.\s*POR\s*[:\-]?\s*[\w\s\.\-]+(?:\.|$)",
        r"[\s,;\.\-]*CONTATO\s*[:\-]?\s*(?:SR\.?|SRA\.?)?\s*[\w\s\.\-]+(?:\.|$)",
        r"[\s,;\.\-]*QUEM\s+SOLICITOU\s*[:\-]?\s*[\w\s\.\-]+(?:\.|$)",
    ]
    for s_pat in solicitante_patterns:
        clean_def = re.sub(s_pat, "", clean_def, flags=re.IGNORECASE)

    # 2. Remove prefixos redundantes de balança / cliente / setor do defeito
    clean_def = re.sub(r"^\s*BALAN[ÇC]A\s+(?:DO\s+|DA\s+|DE\s+)?[^,;:\.\n\r]+[,;:\.]?\s*", "", clean_def, flags=re.IGNORECASE)
    clean_def = re.sub(r"^\s*BALAN[ÇC]A\s+SETOR\s+[^,;:\.\n\r]+[,;:\.]?\s*", "", clean_def, flags=re.IGNORECASE)
    clean_def = re.sub(r"^\s*SETOR\s*(?:DE\s*)?[:\-]?\s*[^,;:\.\n\r]+[,;:\.]?\s*", "", clean_def, flags=re.IGNORECASE)

    # Se o nome do setor ainda ficou no início seguido de hífen/dois pontos (ex: 'ROTISSERIE - TECLADO TRAVANDO')
    if extracted_sector and clean_def.upper().startswith(extracted_sector):
        clean_def = clean_def[len(extracted_sector):].lstrip(" :;,-")

    clean_def = clean_def.strip(" ,;.-")
    data["reported_defect"] = clean_def.upper() if clean_def else raw_defect_text.upper()

    return data


def list_external_orders(
    date_filter: Optional[str] = None,
    shift_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    technician: Optional[str] = None,
    search: Optional[str] = None,
    pending_only: bool = False
) -> List[Dict[str, Any]]:
    """Consulta chamados externos com filtros opcionais incluindo turno (Manhã / Tarde)."""
    query = "SELECT * FROM external_orders WHERE 1=1"
    params = []

    if pending_only:
        # Chamados pendentes permanecem visíveis independente de data ou turno para nunca serem esquecidos
        query += " AND (status IN ('pending_route', 'pending_director') OR technician IS NULL OR TRIM(technician) = '' OR COALESCE(attendance_status, 'pending') = 'not_attended')"
    else:
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        if date_filter:
            query += " AND (route_date = ? OR open_date = ?)"
            params.extend([date_filter, date_filter])

        if shift_filter:
            query += " AND (route_shift = ? OR route_shift = '' OR route_shift IS NULL)"
            params.append(shift_filter.lower())

    if technician:
        query += " AND UPPER(technician) = ?"
        params.append(technician.strip().upper())

    if search:
        s = f"%{search.strip()}%"
        query += " AND (client_name LIKE ? OR os_number LIKE ? OR sector LIKE ? OR equipment_model LIKE ? OR reported_defect LIKE ? OR tasks_notes LIKE ?)"
        params.extend([s, s, s, s, s, s])

    query += " ORDER BY route_date DESC, route_shift ASC, technician ASC, route_order ASC, id ASC"

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def create_external_order(data: Dict[str, Any]) -> Dict[str, Any]:
    """Cria um novo chamado externo (manual ou via parser de PDF) com suporte a turnos."""
    now_iso = datetime.now().isoformat()
    now_dt = datetime.now()

    os_num = format_external_os_number(data.get("os_number") or "")
    client = (data.get("client_name") or "CLIENTE EXTERNO").strip().upper()
    open_date = (data.get("open_date") or now_dt.strftime("%d/%m/%Y")).strip()
    open_time = (data.get("open_time") or now_dt.strftime("%H:%M")).strip()
    sector = (data.get("sector") or "").strip().upper()
    model = (data.get("equipment_model") or "").strip().upper()
    defect = (data.get("reported_defect") or "").strip().upper()
    tasks = (data.get("tasks_notes") or "").strip()
    tech = (data.get("technician") or "").strip().upper()
    route_date = (data.get("route_date") or now_dt.strftime("%Y-%m-%d")).strip()
    route_shift = (data.get("route_shift") or get_current_shift()).lower().strip()
    route_order = int(data.get("route_order") or 0)
    status = data.get("status") or ("routed" if tech else "pending_route")
    attendance_status = (data.get("attendance_status") or "pending").lower().strip()
    unattended_reason = (data.get("unattended_reason") or "").strip()
    pdf_source = data.get("pdf_source_path") or ""

    with connect() as conn:
        # Se veio de PDF e já existe o mesmo número de O.S. pendente na mesma data de rota, atualiza em vez de duplicar
        if pdf_source and os_num:
            existing = conn.execute("""
                SELECT id FROM external_orders
                WHERE os_number = ? AND route_date = ? AND status IN ('pending_route', 'pending_director')
                ORDER BY id DESC LIMIT 1
            """, (os_num, route_date)).fetchone()
            if existing:
                oid = existing["id"]
                conn.execute("""
                    UPDATE external_orders
                    SET client_name = COALESCE(NULLIF(?, ''), client_name),
                        open_date = COALESCE(NULLIF(?, ''), open_date),
                        open_time = COALESCE(NULLIF(?, ''), open_time),
                        sector = COALESCE(NULLIF(?, ''), sector),
                        equipment_model = COALESCE(NULLIF(?, ''), equipment_model),
                        reported_defect = COALESCE(NULLIF(?, ''), reported_defect),
                        route_shift = ?,
                        pdf_source_path = ?,
                        pdf_imported_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    client, open_date, open_time, sector, model, defect,
                    route_shift, pdf_source, now_iso, now_iso, oid
                ))
                row = conn.execute("SELECT * FROM external_orders WHERE id = ?", (oid,)).fetchone()
                return dict(row) if row else {}

        cur = conn.execute("""
            INSERT INTO external_orders (
                os_number, client_name, open_date, open_time, sector,
                equipment_model, reported_defect, tasks_notes, technician,
                route_date, route_shift, route_order, status, attendance_status,
                unattended_reason, pdf_source_path, pdf_imported_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            os_num, client, open_date, open_time, sector,
            model, defect, tasks, tech,
            route_date, route_shift, route_order, status, attendance_status,
            unattended_reason, pdf_source,
            now_iso if pdf_source else None, now_iso, now_iso
        ))
        order_id = cur.lastrowid
        row = conn.execute("SELECT * FROM external_orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else {}


def update_external_order(order_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Atualiza dados de um chamado externo (técnico, turno, sequência, setor, notas, attendance_status, etc)."""
    now_iso = datetime.now().isoformat()
    allowed_fields = {
        "os_number", "client_name", "open_date", "open_time", "sector",
        "equipment_model", "reported_defect", "tasks_notes", "technician",
        "route_date", "route_shift", "route_order", "status", "attendance_status",
        "unattended_reason"
    }

    # Quando um chamado for marcado como 'não atendido', ele retorna automaticamente
    # para a fila de 'chamados externos aguardando rota' (unassigned / pending_route)
    if data.get("attendance_status") and str(data.get("attendance_status")).strip().lower() == "not_attended":
        data["technician"] = None
        data["route_order"] = 0
        data["status"] = "pending_route"
        data["route_shift"] = ""
    elif data.get("attendance_status") and str(data.get("attendance_status")).strip().lower() == "attended":
        data["unattended_reason"] = ""
    elif "technician" in data:
        tech_val = str(data.get("technician") or "").strip()
        if not tech_val:
            data["technician"] = None if data.get("technician") is None else ""
            data["route_order"] = 0
            data["status"] = "pending_route"
            data["route_shift"] = ""
        else:
            if "status" not in data:
                data["status"] = "routed"
            if "attendance_status" not in data:
                data["attendance_status"] = "pending"

    updates = []
    params = []
    for k, v in data.items():
        if k in allowed_fields:
            if k in ["client_name", "sector", "equipment_model", "reported_defect", "technician"] and isinstance(v, str):
                v = v.strip().upper()
            elif k in ["route_shift", "attendance_status"] and isinstance(v, str):
                v = v.strip().lower()
            elif k == "os_number" and isinstance(v, str) and v.strip():
                v = format_external_os_number(v.strip())
            elif k == "route_order":
                v = int(v or 0)
            updates.append(f"{k} = ?")
            params.append(v)

    if not updates:
        return None

    updates.append("updated_at = ?")
    params.append(now_iso)
    params.append(order_id)

    with connect() as conn:
        conn.execute(f"UPDATE external_orders SET {', '.join(updates)} WHERE id = ?", params)
        row = conn.execute("SELECT * FROM external_orders WHERE id = ?", (order_id,)).fetchone()
        if row and ("technician" in data or "route_order" in data):
            r_date = row["route_date"]
            r_shift = (row["route_shift"] or get_current_shift()).lower()
            if r_date:
                conn.execute(
                    "UPDATE external_routes SET status = 'draft', updated_at = ? WHERE route_date = ? AND route_shift = ? AND status = 'finalized'",
                    (now_iso, r_date, r_shift)
                )
        return dict(row) if row else None


def reschedule_external_orders(order_ids: List[int], new_date: str, new_shift: str) -> int:
    """
    Transfere um ou mais chamados (ex: não atendidos) para outra data ou outro turno (ex: tarde).
    Reseta attendance_status para 'pending' e route_order para 0 para reorganização.
    """
    if not order_ids:
        return 0
    now_iso = datetime.now().isoformat()
    clean_ids = [int(i) for i in order_ids if str(i).isdigit()]
    if not clean_ids:
        return 0
    placeholders = ",".join(["?"] * len(clean_ids))
    params = [new_date, new_shift.lower().strip(), now_iso] + clean_ids

    with connect() as conn:
        res = conn.execute(f"""
            UPDATE external_orders
            SET route_date = ?, route_shift = ?, attendance_status = 'pending', route_order = 0, technician = NULL, status = 'pending_route', updated_at = ?
            WHERE id IN ({placeholders})
        """, params)
        return res.rowcount


def delete_external_order(order_id: int) -> bool:
    """Exclui um chamado externo pelo ID."""
    with connect() as conn:
        res = conn.execute("DELETE FROM external_orders WHERE id = ?", (order_id,))
        return res.rowcount > 0


def notify_director_pending_routes(date_str: str, shift: Optional[str] = None) -> Dict[str, Any]:
    """
    Acionado quando a Priscila (Admin) clica em 'Enviar para Sr. Jacson'.
    Marca todos os chamados pendentes (independente da data) como 'pending_director'
    e emite evento WebSocket com alerta sonoro para a Diretoria.
    """
    now_iso = datetime.now().isoformat()
    shift_val = (shift or get_current_shift()).lower()

    with connect() as conn:
        conn.execute("""
            UPDATE external_orders
            SET status = 'pending_director', route_shift = ?, updated_at = ?
            WHERE status IN ('pending_route', 'pending_director')
               OR technician IS NULL
               OR TRIM(technician) = ''
               OR COALESCE(attendance_status, 'pending') = 'not_attended'
        """, (shift_val, now_iso))

        # Registra ou atualiza na tabela external_routes com chave (route_date, route_shift)
        existing_route = conn.execute(
            "SELECT id FROM external_routes WHERE route_date = ? AND route_shift = ?",
            (date_str, shift_val)
        ).fetchone()

        if existing_route:
            conn.execute("UPDATE external_routes SET status = 'pending_director', updated_at = ? WHERE id = ?", (now_iso, existing_route["id"]))
        else:
            conn.execute("""
                INSERT INTO external_routes (route_date, route_shift, status, created_at, updated_at)
                VALUES (?, ?, 'pending_director', ?, ?)
            """, (date_str, shift_val, now_iso, now_iso))

        orders = conn.execute("""
            SELECT * FROM external_orders
            WHERE (route_date = ? AND (route_shift = ? OR route_shift = '' OR route_shift IS NULL))
               OR status IN ('pending_route', 'pending_director')
               OR technician IS NULL
               OR TRIM(technician) = ''
               OR COALESCE(attendance_status, 'pending') = 'not_attended'
            ORDER BY id ASC
        """, (date_str, shift_val)).fetchall()
        order_list = [dict(o) for o in orders]

    shift_label = "MANHÃ" if shift_val == "manha" else "TARDE"

    try:
        from ..realtime import _emit_safe
        _emit_safe("external_routes_sent_to_director", {
            "route_date": date_str,
            "route_shift": shift_val,
            "shift_label": shift_label,
            "total_calls": len(order_list),
            "sent_at": now_iso,
            "message": f"Priscila enviou {len(order_list)} chamado(s) de {shift_label} para montagem de rota!"
        })
    except Exception as e:
        logger.warning(f"Falha ao emitir socketio para diretoria: {e}")

    return {
        "success": True,
        "route_date": date_str,
        "route_shift": shift_val,
        "shift_label": shift_label,
        "total_calls": len(order_list),
        "orders": order_list
    }


def save_route_assignments(
    route_date: str,
    assignments: List[Dict[str, Any]],
    finalize: bool = False,
    director_name: str = "Sr. Jacson",
    route_shift: Optional[str] = None
) -> Dict[str, Any]:
    """
    Salva a organização das rotas feita pelo Sr. Jacson na Diretoria para o turno informado.
    Aceita tanto lista plana de paradas quanto lista agrupada por técnico {'technician': ..., 'orders': [...]}.
    """
    now_iso = datetime.now().isoformat()
    new_status = "routed" if finalize else "draft"
    shift_val = (route_shift or get_current_shift()).lower()

    flat_items: List[Dict[str, Any]] = []
    for item in assignments:
        if isinstance(item.get("orders"), list):
            tech_name = (item.get("technician") or "").strip().upper()
            for sub_idx, sub_order in enumerate(item["orders"], start=1):
                merged = dict(sub_order)
                merged["technician"] = tech_name
                if not merged.get("route_order"):
                    merged["route_order"] = sub_idx
                flat_items.append(merged)
        else:
            flat_items.append(item)

    with connect() as conn:
        for idx, item in enumerate(flat_items):
            order_id = item.get("id")
            if not order_id:
                continue
            tech = (item.get("technician") or "").strip().upper()
            order_pos = int(item.get("route_order") or (idx + 1))
            tasks = (item.get("tasks_notes") or "").strip()
            sector = (item.get("sector") or "").strip().upper()

            update_clause = """
                UPDATE external_orders
                SET technician = ?,
                    route_order = ?,
                    tasks_notes = COALESCE(NULLIF(?, ''), tasks_notes),
                    sector = COALESCE(NULLIF(?, ''), sector),
                    route_date = ?,
                    route_shift = ?,
                    status = ?,
                    attendance_status = 'pending',
                    updated_at = ?
                WHERE id = ?
            """
            conn.execute(update_clause, (tech, order_pos, tasks, sector, route_date, shift_val, new_status, now_iso, order_id))

        existing_route = conn.execute(
            "SELECT id FROM external_routes WHERE route_date = ? AND route_shift = ?",
            (route_date, shift_val)
        ).fetchone()

        if existing_route:
            if finalize:
                conn.execute("""
                    UPDATE external_routes
                    SET status = 'finalized',
                        finalized_at = ?,
                        finalized_by = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (now_iso, director_name, now_iso, existing_route["id"]))
            else:
                conn.execute("""
                    UPDATE external_routes
                    SET status = 'draft',
                        updated_at = ?
                    WHERE id = ?
                """, (now_iso, existing_route["id"]))
        else:
            conn.execute("""
                INSERT INTO external_routes (route_date, route_shift, status, finalized_at, finalized_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                route_date,
                shift_val,
                "finalized" if finalize else "draft",
                now_iso if finalize else None,
                director_name if finalize else "",
                now_iso,
                now_iso
            ))

        rows = conn.execute("""
            SELECT * FROM external_orders
            WHERE route_date = ? AND (route_shift = ? OR route_shift = '' OR route_shift IS NULL)
            ORDER BY technician ASC, route_order ASC, id ASC
        """, (route_date, shift_val)).fetchall()
        updated_orders = [dict(r) for r in rows]

    shift_label = "MANHÃ" if shift_val == "manha" else "TARDE"

    if finalize:
        try:
            from ..realtime import _emit_safe
            _emit_safe("external_routes_finalized", {
                "route_date": route_date,
                "route_shift": shift_val,
                "shift_label": shift_label,
                "finalized_by": director_name,
                "finalized_at": now_iso,
                "total_orders": len(updated_orders),
                "message": f"Sr. Jacson finalizou e liberou as rotas da {shift_label} de {route_date}! Prontas para envio via WhatsApp."
            })
        except Exception as e:
            logger.warning(f"Falha ao emitir socketio de rotas finalizadas: {e}")

    return {
        "success": True,
        "route_date": route_date,
        "route_shift": shift_val,
        "shift_label": shift_label,
        "finalized": finalize,
        "total_orders": len(updated_orders),
        "orders": updated_orders
    }


def get_grouped_routes(date_str: str, shift: Optional[str] = None) -> Dict[str, Any]:
    """
    Retorna os chamados agrupados por técnico para a data e turno selecionados.
    REGRA DE OURO: Qualquer chamado pendente (ou que ficou pendente/não atendido em qualquer outro dia)
    retorna automaticamente e permanece sempre visível em 'unassigned' ('Chamados Externos Aguardando Rota' /
    'Aguardando Distribuição'), independente da data selecionada (passada, presente ou futura),
    preservando sua data de abertura (open_date).
    """
    shift_val = (shift or get_current_shift()).lower()
    now_iso = datetime.now().isoformat()
    today_str = datetime.now().strftime("%Y-%m-%d")

    with connect() as conn:
        # Chamados de DIAS JÁ ENCERRADOS (anteriores ao dia de HOJE no relógio do servidor) que não foram
        # concluídos ('attended') voltam automaticamente para 'chamados externos aguardando rota', mantendo
        # a data de abertura. NUNCA mexe em rotas de hoje/futuras e nem na data que está sendo visualizada
        # (para a Priscila poder marcar os atendidos sem que os demais técnicos sumam).
        conn.execute("""
            UPDATE external_orders
            SET technician = '',
                route_order = 0,
                status = 'pending_route',
                route_shift = '',
                updated_at = ?
            WHERE route_date != ''
              AND route_date < ?
              AND route_date != ?
              AND COALESCE(attendance_status, 'pending') != 'attended'
              AND (
                  (technician IS NOT NULL AND TRIM(technician) != '')
                  OR status NOT IN ('pending_route', 'pending_director')
              )
        """, (now_iso, today_str, date_str))

        route_info = conn.execute(
            "SELECT * FROM external_routes WHERE route_date = ? AND route_shift = ?",
            (date_str, shift_val)
        ).fetchone()

        # 1. Paradas já atribuídas a técnicos para esta data e turno (todos os técnicos da rota)
        routed_rows = conn.execute("""
            SELECT * FROM external_orders
            WHERE route_date = ?
              AND technician IS NOT NULL
              AND TRIM(technician) != ''
              AND status NOT IN ('pending_route', 'pending_director')
              AND COALESCE(attendance_status, 'pending') != 'not_attended'
              AND (route_shift = ? OR route_shift = '' OR route_shift IS NULL)
            ORDER BY technician ASC, route_order ASC, id ASC
        """, (date_str, shift_val)).fetchall()

        # 2. Chamados pendentes ("Aguardando Rota" / "Aguardando Distribuição") de QUALQUER data ou turno.
        # Só entra aqui quem realmente está sem técnico / pendente / não atendido — nunca uma parada
        # que está atribuída a um técnico em outra rota.
        pending_rows = conn.execute("""
            SELECT * FROM external_orders
            WHERE technician IS NULL
               OR TRIM(technician) = ''
               OR status IN ('pending_route', 'pending_director')
               OR COALESCE(attendance_status, 'pending') = 'not_attended'
            ORDER BY id ASC
        """).fetchall()

    tech_groups: Dict[str, List[Dict[str, Any]]] = {}
    routed_ids = set()

    for r in routed_rows:
        item = dict(r)
        tech = (item.get("technician") or "").strip().upper()
        if tech:
            if tech not in tech_groups:
                tech_groups[tech] = []
            tech_groups[tech].append(item)
            routed_ids.add(item["id"])

    unassigned: List[Dict[str, Any]] = []
    for r in pending_rows:
        item = dict(r)
        if item["id"] in routed_ids:
            continue
        # Garante que chamados vindos de outros dias não atendidos apareçam limpos como aguardando rota
        item["technician"] = ""
        if item.get("status") not in ("pending_route", "pending_director"):
            item["status"] = "pending_route"
        unassigned.append(item)

    shift_label = "MANHÃ" if shift_val == "manha" else "TARDE"

    return {
        "route_date": date_str,
        "route_shift": shift_val,
        "shift_label": shift_label,
        "status": route_info["status"] if route_info else "draft",
        "finalized_at": route_info["finalized_at"] if route_info else None,
        "finalized_by": route_info["finalized_by"] if route_info else "",
        "technicians": tech_groups,
        "unassigned": unassigned,
        "total_calls": len(routed_ids) + len(unassigned)
    }


def format_whatsapp_route_message(date_str: str, technician_name: str, stops: List[Dict[str, Any]], shift: str = "manha") -> str:
    """Gera o texto formatado para envio direto no WhatsApp do técnico ou grupo."""
    shift_label = "MANHÃ" if shift.lower() == "manha" else "TARDE"
    lines = []
    lines.append(f"🚚 *ROTA DE EXTERNOS - {shift_label} - {date_str}*")
    lines.append(f"👨‍🔧 *TÉCNICO / EQUIPE: {technician_name.upper()}*")
    lines.append("=" * 32)

    for idx, stop in enumerate(stops, start=1):
        order_seq = stop.get("route_order") or idx
        client = stop.get("client_name") or "CLIENTE"
        os_num = stop.get("os_number") or "S/N"
        hora = stop.get("open_time") or "--:--"
        sector = stop.get("sector") or ""
        model = stop.get("equipment_model") or ""
        defect = stop.get("reported_defect") or ""
        tasks = stop.get("tasks_notes") or ""

        lines.append(f"📍 *{order_seq}ª PARADA: {client}*")
        lines.append(f"   ▫️ *O.S.:* {os_num} | *Horário:* {hora}")
        if sector or model:
            sec_model = f"{sector} - {model}".strip(" -")
            lines.append(f"   ▫️ *Setor / Equip.:* {sec_model}")
        if defect:
            lines.append(f"   ▫️ *Defeito:* {defect}")
        if tasks:
            lines.append(f"   ⚠️ *TAREFA:* {tasks.upper()}")
        lines.append("─" * 28)

    lines.append("🏁 *Retorno à Firma após finalização dos atendimentos.*")
    return "\n".join(lines)


def format_whatsapp_conjunta_message(date_str: str, technicians_dict: Dict[str, List[Dict[str, Any]]], shift: str = "manha") -> str:
    """Gera texto com todas as rotas unificadas para envio no grupo geral da equipe."""
    shift_label = "MANHÃ" if shift.lower() == "manha" else "TARDE"
    lines = []
    lines.append(f"🚚 *ROTA GERAL DE EXTERNOS (CONJUNTA) - {shift_label} - {date_str}*")
    lines.append("=" * 36)

    for tech_name, stops in technicians_dict.items():
        lines.append(f"\n👨‍🔧 *TÉCNICO: {tech_name.upper()}* ({len(stops)} paradas)")
        lines.append("─" * 30)
        for idx, stop in enumerate(stops, start=1):
            order_seq = stop.get("route_order") or idx
            client = stop.get("client_name") or "CLIENTE"
            os_num = stop.get("os_number") or "S/N"
            sector = stop.get("sector") or ""
            tasks = stop.get("tasks_notes") or ""
            sec_str = f" [{sector}]" if sector else ""
            task_str = f" ⚠️ *{tasks}*" if tasks else ""
            lines.append(f"• {order_seq}ª: {client}{sec_str} (OS: {os_num}){task_str}")

    lines.append("\n🏁 *Todos retornam à firma ao finalizar os atendimentos.*")
    return "\n".join(lines)


def build_route_image_filename(date_str: str, shift: str, tech_or_conjunta: str) -> str:
    """
    Gera nome padronizado de arquivo para salvar na pasta de imagens:
    Exemplos:
    - ROTA_EDSON_MANHA_04-11-2026.png
    - ROTA_ANTONIO_MANHA_04-11-2026.png
    - ROTA_CONJUNTA_MANHA_04-11-2026.png
    - ROTA_EDSON_TARDE_04-11-2026.png
    - ROTA_ANTONIO_TARDE_04-11-2026.png
    - ROTA_CONJUNTA_TARDE_04-11-2026.png
    """
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        parts = date_str.split("-")
        clean_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
    else:
        clean_date = date_str.replace("/", "-")
    shift_clean = "MANHA" if shift.lower() == "manha" else "TARDE"
    tech_clean = re.sub(r"[^A-Z0-9]", "_", tech_or_conjunta.upper()).strip("_")
    return f"ROTA_{tech_clean}_{shift_clean}_{clean_date}.png"


def save_route_image_file(image_base64: str, filename: str) -> Dict[str, Any]:
    """
    Decodifica base64 da imagem e salva na pasta dedicada rotas_imagens/.
    """
    os.makedirs(ROTAS_IMAGENS_DIR, exist_ok=True)
    # Remove prefixo de data URI caso venha do canvas
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]

    file_bytes = base64.b64decode(image_base64)
    file_path = os.path.join(ROTAS_IMAGENS_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    logger.info(f"Imagem de rota salva com sucesso: {file_path} ({len(file_bytes)} bytes)")
    return {
        "success": True,
        "filename": filename,
        "path": file_path,
        "size": len(file_bytes),
        "url": f"/api/externos/images/{filename}"
    }


def list_saved_route_images() -> List[Dict[str, Any]]:
    """Lista as imagens salvas na pasta rotas_imagens/ ordenadas das mais recentes para as mais antigas."""
    os.makedirs(ROTAS_IMAGENS_DIR, exist_ok=True)
    results = []
    for f in os.listdir(ROTAS_IMAGENS_DIR):
        if f.lower().endswith((".png", ".jpg", ".jpeg")):
            full_p = os.path.join(ROTAS_IMAGENS_DIR, f)
            st = os.stat(full_p)
            results.append({
                "filename": f,
                "url": f"/api/externos/images/{f}",
                "size_kb": round(st.st_size / 1024, 1),
                "created_at": datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M"),
                "timestamp": st.st_mtime
            })
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results


def export_external_routes_csv(
    date_filter: Optional[str] = None,
    shift_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Gera conteúdo CSV formatado para Excel no Brasil:
    - Delimitador: ponto e vírgula (;)
    - Encoding: UTF-8 com BOM (\ufeff)
    - Colunas: Cliente;Data Abertura de O.S.;Horário;O.S.;Setor;Mod. Equip.;Defeito;Técnico;Tarefas a serem realizadas
    """
    query = "SELECT * FROM external_orders WHERE 1=1"
    params = []

    if date_filter:
        query += " AND (route_date = ? OR open_date = ?)"
        params.extend([date_filter, date_filter])
    elif date_from and date_to:
        query += " AND route_date BETWEEN ? AND ?"
        params.extend([date_from, date_to])

    if shift_filter:
        query += " AND (route_shift = ? OR route_shift = '' OR route_shift IS NULL)"
        params.append(shift_filter.lower())

    query += " ORDER BY route_date DESC, route_shift ASC, technician ASC, route_order ASC, id ASC"

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    headers = [
        "Cliente",
        "Data Abertura de O.S.",
        "Horário",
        "O.S.",
        "Setor",
        "Mod. Equip.",
        "Defeito",
        "Técnico",
        "Tarefas a serem realizadas"
    ]
    writer.writerow(headers)

    for r in rows:
        writer.writerow([
            r["client_name"] or "",
            r["open_date"] or "",
            r["open_time"] or "",
            r["os_number"] or "",
            r["sector"] or "",
            r["equipment_model"] or "",
            r["reported_defect"] or "",
            r["technician"] or "",
            r["tasks_notes"] or ""
        ])

    return output.getvalue()
