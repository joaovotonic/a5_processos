"""Acervo pesquisável de O.S. em PDF (sincronizado da recepção + arquivados da Esteira)."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from datetime import datetime
from typing import Any

from werkzeug.utils import secure_filename

from .. import config
from ..database import connect

logger = logging.getLogger("kanban.pdf_library")

MAX_LIBRARY_PDF_BYTES = 35 * 1024 * 1024  # 35 MB


def _norm(text: str | None) -> str:
    """Remove acentos e normaliza espaços em minúsculas para busca resiliente."""
    raw = str(text or "")
    nfkd = unicodedata.normalize("NFKD", raw)
    stripped = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _only_digits(value: str | None) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _os_key(value: str | None) -> str:
    dig = _only_digits(value)
    return dig.lstrip("0") or dig


def ensure_pdf_library_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pdf_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sha256 TEXT UNIQUE NOT NULL,
            source_rel_path TEXT DEFAULT '',
            stored_rel_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            file_mtime REAL DEFAULT 0,
            os_number TEXT DEFAULT '',
            client_name TEXT DEFAULT '',
            equipment_type TEXT DEFAULT '',
            equipment_model TEXT DEFAULT '',
            serial_number TEXT DEFAULT '',
            reported_defect TEXT DEFAULT '',
            doc_date TEXT DEFAULT '',
            search_text TEXT DEFAULT '',
            indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pdf_lib_os ON pdf_library(os_number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pdf_lib_mtime ON pdf_library(file_mtime DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pdf_lib_rel ON pdf_library(source_rel_path)")


def _fast_extract_pdf_text(pdf_path: str, max_pages: int = 3) -> str:
    """Extração rápida via pypdf (ideal para indexação em massa), com fallback pdfplumber."""
    text = ""
    try:
        import pypdf

        reader = pypdf.PdfReader(pdf_path)
        chunks = []
        for page in reader.pages[:max_pages]:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(chunks).strip()
    except Exception as exc:
        logger.debug("pypdf falhou em %s: %s", pdf_path, exc)

    if len(text) < 25:
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                chunks = []
                for page in pdf.pages[:max_pages]:
                    chunks.append(page.extract_text() or "")
                fb = "\n".join(chunks).strip()
                if fb:
                    text = fb
        except Exception as exc:
            logger.debug("pdfplumber falhou em %s: %s", pdf_path, exc)

    return text


def _extract_metadata_from_pdf(pdf_path: str, orig_filename: str, source_rel_path: str = "") -> dict[str, str]:
    """Extrai O.S., cliente, modelo da balança, série, defeito, data e texto pesquisável."""
    text = _fast_extract_pdf_text(pdf_path)
    filename = orig_filename or os.path.basename(pdf_path)
    name_no_ext = os.path.splitext(filename)[0]
    rel_clean = (source_rel_path or "").replace("\\", "/")

    os_number = ""
    client_name = ""
    equipment_type = ""
    equipment_model = ""
    serial_number = ""
    reported_defect = ""
    doc_date = ""

    # 1. Número da O.S. (no texto do PDF ou no nome do arquivo)
    os_patterns = [
        r"Ordem\s+de\s+Servi[çc]o\s*[:#]?\s*(\d{3,14})",
        r"(?:ORDEM\s+DE\s+SERVI[ÇC]O|O\.?\s*S\.?)\s*[:#\-\s]?\s*(\d{3,14})",
        r"\b(0{2,6}\d{4,10})\b",
    ]
    for pat in os_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            os_number = m.group(1).strip()
            break
    if not os_number:
        for pat in (r"(?:O\.?\s*S\.?)\s*[:#\-_\s]*(\d{3,14})", r"\b(\d{5,10})\b"):
            m = re.search(pat, filename, re.IGNORECASE)
            if m:
                os_number = m.group(1).strip()
                break
    if os_number and len(os_number) > 6 and os_number.startswith("0"):
        trimmed = os_number.lstrip("0")
        os_number = trimmed.zfill(6) if len(trimmed) <= 6 else trimmed

    # 2. Cliente (no texto do PDF)
    client_patterns = [
        r"Cliente\s*:\s*([^\n\r]{3,100})",
        r"Raz[ãa]o\s+Social\s*:\s*([^\n\r]{3,100})",
        r"Nome\s*/\s*Raz[ãa]o\s*:\s*([^\n\r]{3,100})",
    ]
    for pat in client_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            cand = re.split(r"\s+(?:CNPJ|CPF|Fone|Tel|Endere[çc]o|Data|Insc)\b", m.group(1), flags=re.I)[0]
            cand = re.sub(r"^\d+\s*[-–]\s*", "", cand).strip(" :-–")
            if len(cand) >= 3:
                client_name = cand[:120]
                break

    if not client_name:
        # Tenta extrair do nome do arquivo (ex: "O.S. 027132 Lindopan.pdf")
        cleaned_name = re.sub(r"^(?:OS[_\s\-\.]*)?(?:O\.?\s*S\.?\s*)?\d{3,14}\s*[-_\.]*\s*", "", name_no_ext, flags=re.I)
        cleaned_name = re.sub(r"^[0-9a-f]{8}_", "", cleaned_name, flags=re.I)
        cleaned_name = re.sub(r"^(?:OS[_\s\-\.]*)?(?:O\.?\s*S\.?\s*)?\d{3,14}\s*[-_\.]*\s*", "", cleaned_name, flags=re.I)
        cleaned_name = cleaned_name.replace("_", " ").strip(" -_.")
        if len(cleaned_name) >= 3:
            client_name = cleaned_name[:120]
        elif "/" in rel_clean:
            parent_dir = rel_clean.rsplit("/", 1)[0].rsplit("/", 1)[-1].strip()
            if len(parent_dir) >= 3 and not re.match(r"^\d{4}(?:[-_]\d{2})?$", parent_dir):
                client_name = parent_dir[:120]

    # 3. Modelo da Balança / Equipamento
    model_patterns = [
        r"(?:Equipamento|Produto|Descri[çc][ãa]o\s+do\s+Equipamento)\s*:\s*([^\n\r]{3,100})",
        r"Modelo\s*:\s*([^\n\r]{2,80})",
        r"\b((?:PRIX|TOLEDO|URANO|FILIZOLA|BALMAK|ELGIN|RAMUZA|MICHELETTI|UPX|DIGIPESO)\s+[A-Z0-9\-\/\.\s]{1,35})",
    ]
    for pat in model_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            cand = re.split(r"\s+(?:N[°ºo]\.?\s*S[ée]rie|S[ée]rie|Patrim|Capacidade|Marca)\b", m.group(1), flags=re.I)[0]
            cand = re.sub(r"\s+", " ", cand).strip(" :-–")
            if len(cand) >= 2:
                equipment_model = cand[:90]
                break

    if re.search(r"\b(balan[çc]a|prix|toledo|urano|filizola|balmak|elgin|ramuza|micheletti)\b", text + " " + equipment_model, re.I):
        equipment_type = "Balança"
    elif re.search(r"\b(impressora|etiquetadora|coletor|leitor)\b", text + " " + equipment_model, re.I):
        equipment_type = "Equipamento Automação"

    # 4. Número de série
    for pat in (
        r"(?:N[°ºo]\.?\s*(?:de\s*)?S[ée]rie|S[ée]rie|Serial)\s*[:#]?\s*([A-Z0-9\-\/]{4,30})",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            cand = m.group(1).strip()
            if cand.upper() not in ("NAO", "N/A", "N/I", "SEM", "INFORMADO"):
                serial_number = cand[:40]
                break

    # 5. Defeito relatado
    for pat in (
        r"(?:Defeito\s*(?:Relatado|Informado|Reclamado)?|Problema\s*Relatado|Observa[çc][õo]es)\s*:\s*([^\n\r]{4,180})",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            reported_defect = re.sub(r"\s+", " ", m.group(1)).strip(" :-–")[:200]
            break

    # 6. Data do documento (YYYY-MM-DD)
    for pat in (
        r"(?:Data\s*(?:de\s*)?(?:Entrada|Abertura|Emiss[ãa]o)?|Abertura)\s*[:#]?\s*(\d{2})/(\d{2})/(\d{4})",
        r"\b(\d{2})/(\d{2})/(20\d{2})\b",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
            if 1 <= int(mm) <= 12 and 1 <= int(dd) <= 31:
                doc_date = f"{yyyy}-{mm}-{dd}"
                break

    search_parts = [
        os_number,
        _os_key(os_number),
        client_name,
        equipment_type,
        equipment_model,
        serial_number,
        reported_defect,
        filename,
        rel_clean,
        text[:2200],
    ]
    search_text = _norm(" ".join(p for p in search_parts if p))

    return {
        "os_number": os_number,
        "client_name": client_name,
        "equipment_type": equipment_type,
        "equipment_model": equipment_model,
        "serial_number": serial_number,
        "reported_defect": reported_defect,
        "doc_date": doc_date,
        "search_text": search_text,
    }


def check_existing_hashes(hashes: list[str]) -> list[str]:
    clean = [str(h or "").strip().lower() for h in hashes if str(h or "").strip()]
    if not clean:
        return []
    clean = clean[:200]
    placeholders = ",".join("?" for _ in clean)
    with connect() as conn:
        ensure_pdf_library_table(conn)
        rows = conn.execute(
            f"SELECT sha256 FROM pdf_library WHERE sha256 IN ({placeholders})",
            clean,
        ).fetchall()
    return [r["sha256"] for r in rows]


def store_and_index_uploaded_pdf(
    raw_bytes: bytes,
    orig_filename: str,
    source_rel_path: str = "",
    file_mtime: float | None = None,
) -> dict[str, Any]:
    """Salva PDF no acervo (deduplicado por SHA-256) e indexa metadados no SQLite."""
    if not raw_bytes or len(raw_bytes) > MAX_LIBRARY_PDF_BYTES:
        raise ValueError("PDF vazio ou excede o limite de 35 MB.")
    if not raw_bytes.lstrip().startswith(b"%PDF-"):
        raise ValueError("Arquivo não possui cabeçalho %PDF- válido.")

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    now_ts = datetime.now().timestamp()
    mtime_val = float(file_mtime) if file_mtime and float(file_mtime) > 0 else now_ts
    rel_clean = (source_rel_path or orig_filename or "").replace("\\", "/").strip("/")
    clean_name = os.path.basename(orig_filename or "documento.pdf").strip() or "documento.pdf"

    with connect() as conn:
        ensure_pdf_library_table(conn)
        existing = conn.execute(
            "SELECT id, stored_rel_path, os_number, client_name, equipment_model, file_mtime FROM pdf_library WHERE sha256 = ?",
            (sha256,),
        ).fetchone()
        if existing:
            # Atualiza path/mtime caso o arquivo tenha sido renomeado ou movido mantendo mesmo conteúdo
            if rel_clean and (mtime_val > float(existing["file_mtime"] or 0)):
                conn.execute(
                    "UPDATE pdf_library SET source_rel_path = ?, file_mtime = ? WHERE id = ?",
                    (rel_clean, mtime_val, existing["id"]),
                )
            return {
                "id": existing["id"],
                "sha256": sha256,
                "deduplicated": True,
                "os_number": existing["os_number"] or "",
                "client_name": existing["client_name"] or "",
                "equipment_model": existing["equipment_model"] or "",
            }

    try:
        month_folder = datetime.fromtimestamp(mtime_val).strftime("%Y-%m")
    except Exception:
        month_folder = datetime.now().strftime("%Y-%m")

    target_dir = os.path.join(config.PDF_LIBRARY_DIR, month_folder)
    os.makedirs(target_dir, exist_ok=True)

    safe_tail = secure_filename(clean_name) or "documento.pdf"
    if not safe_tail.lower().endswith(".pdf"):
        safe_tail += ".pdf"
    stored_name = f"{sha256[:12]}_{safe_tail[:110]}"
    abs_path = os.path.join(target_dir, stored_name)
    tmp_path = f"{abs_path}.part"
    with open(tmp_path, "wb") as fh:
        fh.write(raw_bytes)
    os.replace(tmp_path, abs_path)

    stored_rel_path = os.path.relpath(abs_path, config.DATA_DIR).replace("\\", "/")
    meta = _extract_metadata_from_pdf(abs_path, clean_name, rel_clean)

    with connect() as conn:
        ensure_pdf_library_table(conn)
        cur = conn.execute(
            """
            INSERT OR REPLACE INTO pdf_library (
                sha256, source_rel_path, stored_rel_path, filename,
                file_size, file_mtime, os_number, client_name,
                equipment_type, equipment_model, serial_number,
                reported_defect, doc_date, search_text, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                sha256,
                rel_clean,
                stored_rel_path,
                clean_name,
                len(raw_bytes),
                mtime_val,
                meta["os_number"],
                meta["client_name"],
                meta["equipment_type"],
                meta["equipment_model"],
                meta["serial_number"],
                meta["reported_defect"],
                meta["doc_date"],
                meta["search_text"],
            ),
        )
        new_id = cur.lastrowid

    return {
        "id": new_id,
        "sha256": sha256,
        "deduplicated": False,
        "os_number": meta["os_number"],
        "client_name": meta["client_name"],
        "equipment_model": meta["equipment_model"],
    }


def index_local_archived_pdf(abs_pdf_path: str, source_label: str = "") -> bool:
    """Indexa no `pdf_library` um PDF já arquivado em DATA_DIR (sem duplicar o arquivo em disco)."""
    if not abs_pdf_path or not os.path.isfile(abs_pdf_path):
        return False
    try:
        with open(abs_pdf_path, "rb") as fh:
            raw = fh.read()
        if not raw or not raw.lstrip().startswith(b"%PDF-"):
            return False
        sha256 = hashlib.sha256(raw).hexdigest()
        with connect() as conn:
            ensure_pdf_library_table(conn)
            exists = conn.execute("SELECT 1 FROM pdf_library WHERE sha256 = ?", (sha256,)).fetchone()
            if exists:
                return False

        rel_stored = os.path.relpath(abs_pdf_path, config.DATA_DIR).replace("\\", "/")
        fname = os.path.basename(abs_pdf_path)
        mtime = os.path.getmtime(abs_pdf_path)
        meta = _extract_metadata_from_pdf(abs_pdf_path, fname, source_label or rel_stored)
        with connect() as conn:
            ensure_pdf_library_table(conn)
            conn.execute(
                """
                INSERT OR IGNORE INTO pdf_library (
                    sha256, source_rel_path, stored_rel_path, filename,
                    file_size, file_mtime, os_number, client_name,
                    equipment_type, equipment_model, serial_number,
                    reported_defect, doc_date, search_text, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    sha256,
                    source_label or rel_stored,
                    rel_stored,
                    fname,
                    len(raw),
                    mtime,
                    meta["os_number"],
                    meta["client_name"],
                    meta["equipment_type"],
                    meta["equipment_model"],
                    meta["serial_number"],
                    meta["reported_defect"],
                    meta["doc_date"],
                    meta["search_text"],
                ),
            )
        return True
    except Exception as exc:
        logger.warning("Erro ao indexar PDF arquivado %s: %s", abs_pdf_path, exc)
        return False


def index_all_existing_archived_pdfs() -> int:
    """Varre ARQUIVADOS_PDFS_DIR e ARQUIVADOS_EXTERNOS_DIR para indexar PDFs já existentes na VPS."""
    count = 0
    for root_dir in (config.ARQUIVADOS_PDFS_DIR, config.ARQUIVADOS_EXTERNOS_DIR):
        if not os.path.isdir(root_dir):
            continue
        for dirpath, _, filenames in os.walk(root_dir):
            for fn in filenames:
                if fn.lower().endswith(".pdf"):
                    if index_local_archived_pdf(os.path.join(dirpath, fn)):
                        count += 1
    return count


def resolve_safe_pdf_path(pdf_id: int) -> tuple[str | None, str]:
    """Retorna (caminho_absoluto_seguro, nome_arquivo) validando que está dentro de DATA_DIR."""
    with connect() as conn:
        ensure_pdf_library_table(conn)
        row = conn.execute(
            "SELECT stored_rel_path, filename FROM pdf_library WHERE id = ?",
            (int(pdf_id),),
        ).fetchone()
    if not row:
        return None, ""
    rel = (row["stored_rel_path"] or "").replace("\\", "/").lstrip("/")
    candidate = os.path.realpath(os.path.join(config.DATA_DIR, rel))
    allowed_roots = [
        os.path.realpath(config.PDF_LIBRARY_DIR),
        os.path.realpath(config.ARQUIVADOS_PDFS_DIR),
        os.path.realpath(config.ARQUIVADOS_EXTERNOS_DIR),
    ]
    if not any(candidate == r or candidate.startswith(r + os.sep) for r in allowed_roots):
        return None, ""
    if not os.path.isfile(candidate):
        return None, ""
    return candidate, row["filename"] or os.path.basename(candidate)


def get_library_stats() -> dict[str, Any]:
    with connect() as conn:
        ensure_pdf_library_table(conn)
        row = conn.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(file_size), 0) AS total_bytes, MAX(file_mtime) AS newest_mtime FROM pdf_library"
        ).fetchone()
    return {
        "total_pdfs": int(row["total"] or 0),
        "total_bytes": int(row["total_bytes"] or 0),
        "total_mb": round((row["total_bytes"] or 0) / (1024 * 1024), 2),
        "newest_mtime": float(row["newest_mtime"] or 0),
    }


def search_pdf_library(q: str = "", phone: str = "", limit: int = 8) -> list[dict[str, Any]]:
    """
    Pesquisa PDFs no acervo por nome do cliente, nº da O.S., balança/modelo, série ou telefone,
    cruzando com o status ao vivo da Esteira A5 e ordenando pelos mais recentes primeiro.
    """
    from ..routes.integrations import _describe_stage
    from ..services.board import enrich_card
    from ..utils import resolve_public_base_url

    q_norm = _norm(q)
    q_digits = _only_digits(q)
    q_os = _os_key(q) if len(q_digits) >= 4 else ""
    q_tokens = [tok for tok in re.split(r"\s+", q_norm) if len(tok) >= 2]
    phone_digits = _only_digits(phone)
    tail8 = phone_digits[-8:] if len(phone_digits) >= 8 else ""
    limit = max(1, min(int(limit or 8), 20))

    with connect() as conn:
        ensure_pdf_library_table(conn)

        # Carrega cards da Esteira indexados por os_key para cruzar status/modelo/técnico ao vivo
        card_rows = conn.execute(
            """
            SELECT c.*, l.title AS list_title, l.role AS list_role, l.is_tech AS list_is_tech
            FROM cards c
            LEFT JOIN lists l ON l.id = c.list_id
            WHERE UPPER(COALESCE(l.title, '')) != 'EXCLUIR'
            """
        ).fetchall()

        cards_by_os_key: dict[str, dict] = {}
        phone_os_keys: set[str] = set()
        phone_client_tokens: set[str] = set()

        for cr in card_rows:
            cd = dict(cr)
            okey = _os_key(cd.get("os_number"))
            if okey and okey not in cards_by_os_key:
                cards_by_os_key[okey] = cd
            if tail8:
                cp = _only_digits(cd.get("phone"))
                if len(cp) >= 8 and cp.endswith(tail8):
                    if okey:
                        phone_os_keys.add(okey)
                    cn = _norm(cd.get("client_name"))
                    if len(cn) >= 3:
                        phone_client_tokens.add(cn)

        if tail8:
            for cl in conn.execute("SELECT client_name, trade_name, phone FROM clients WHERE phone IS NOT NULL").fetchall():
                cp = _only_digits(cl["phone"])
                if len(cp) >= 8 and cp.endswith(tail8):
                    for nm in (cl["client_name"], cl["trade_name"]):
                        n_nm = _norm(nm)
                        if len(n_nm) >= 3:
                            phone_client_tokens.add(n_nm)

        # Busca candidatos no SQLite (pré-filtro rápido para não carregar 10k textos inteiros)
        if q_tokens:
            like_clauses = " AND ".join("search_text LIKE ?" for _ in q_tokens[:6])
            like_params = [f"%{tok}%" for tok in q_tokens[:6]]
            pdf_rows = conn.execute(
                f"SELECT * FROM pdf_library WHERE {like_clauses} ORDER BY file_mtime DESC, id DESC LIMIT 120",
                like_params,
            ).fetchall()
            # Se a busca com AND estrito vier vazia (ex: usuário digitou nome + palavra extra), relaxa com OR
            if not pdf_rows and len(q_tokens) > 1:
                or_clauses = " OR ".join("search_text LIKE ?" for _ in q_tokens[:6])
                pdf_rows = conn.execute(
                    f"SELECT * FROM pdf_library WHERE {or_clauses} ORDER BY file_mtime DESC, id DESC LIMIT 120",
                    like_params,
                ).fetchall()
        else:
            pdf_rows = conn.execute(
                "SELECT * FROM pdf_library ORDER BY file_mtime DESC, id DESC LIMIT 200"
            ).fetchall()

    matched: list[tuple[int, float, dict]] = []
    for pr in pdf_rows:
        pd = dict(pr)
        pkey = _os_key(pd.get("os_number"))
        client_norm = _norm(pd.get("client_name"))
        fname_norm = _norm(pd.get("filename"))
        rel_norm = _norm(pd.get("source_rel_path"))
        search_norm = pd.get("search_text") or ""

        relevance = 0
        if q_norm:
            if q_os and pkey and pkey == q_os:
                relevance = 100
            elif q_tokens and all((t in client_norm or t in fname_norm or t in rel_norm) for t in q_tokens):
                relevance = 85
            elif q_tokens and all(t in search_norm for t in q_tokens):
                relevance = 70
            elif q_tokens:
                hits = sum(1 for t in q_tokens if t in search_norm)
                if hits > 0:
                    relevance = 40 + hits * 8
        elif tail8:
            if pkey and pkey in phone_os_keys:
                relevance = 95
            elif any((tok in client_norm or tok in fname_norm or tok in search_norm) for tok in phone_client_tokens):
                relevance = 80
        else:
            relevance = 50

        if relevance <= 0:
            continue

        # Agrupamento por faixa de relevância + ordenação pela data mais recente dentro da faixa
        tier = 2 if relevance >= 95 else (1 if relevance >= 70 else 0)
        mtime = float(pd.get("file_mtime") or 0)
        matched.append((tier, mtime, pd))

    # Mais relevante primeiro (ex: O.S. exata), e entre todos do cliente -> MAIS RECENTE NO TOPO!
    matched.sort(key=lambda item: (item[0], item[1], int(item[2].get("id") or 0)), reverse=True)

    base_url = resolve_public_base_url()
    results: list[dict[str, Any]] = []
    for idx, (_, mtime, pd) in enumerate(matched[:limit]):
        pkey = _os_key(pd.get("os_number"))
        linked_card = cards_by_os_key.get(pkey) if pkey else None
        stage_label = ""
        tech_name = ""
        inmetro_seal = ""
        public_os_url = ""
        eq_type = pd.get("equipment_type") or ""
        eq_model = pd.get("equipment_model") or ""
        serial = pd.get("serial_number") or ""
        client = pd.get("client_name") or ""
        defect = pd.get("reported_defect") or ""
        os_num = pd.get("os_number") or ""

        if linked_card:
            enriched = enrich_card(linked_card)
            stage_label, _, _ = _describe_stage(enriched)
            tech_name = (enriched.get("finisher_tech") or enriched.get("evaluator_tech") or enriched.get("tech_name") or "").strip()
            inmetro_seal = (enriched.get("inmetro_seal") or "").strip()
            os_num = enriched.get("os_number") or os_num
            client = enriched.get("client_name") or client
            eq_type = enriched.get("equipment_type") or eq_type
            eq_model = enriched.get("equipment_model") or eq_model
            serial = enriched.get("serial_number") or serial
            defect = enriched.get("reported_defect") or defect
            public_os_url = f"{base_url}/os/{os_num}"

        try:
            date_br = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y") if mtime > 0 else ""
        except Exception:
            date_br = ""
        if pd.get("doc_date") and not date_br:
            parts = str(pd["doc_date"]).split("-")
            if len(parts) == 3:
                date_br = f"{parts[2]}/{parts[1]}/{parts[0]}"

        size_kb = round((int(pd.get("file_size") or 0)) / 1024, 1)
        results.append({
            "id": pd["id"],
            "is_latest": idx == 0,
            "os_number": os_num,
            "client_name": client or os.path.splitext(pd.get("filename") or "")[0],
            "equipment_type": eq_type,
            "equipment_model": eq_model,
            "serial_number": serial,
            "reported_defect": defect,
            "stage_label": stage_label,
            "tech_name": tech_name,
            "inmetro_seal": inmetro_seal,
            "public_os_url": public_os_url,
            "filename": pd.get("filename") or "",
            "source_rel_path": pd.get("source_rel_path") or "",
            "file_size": int(pd.get("file_size") or 0),
            "size_kb": size_kb,
            "file_mtime": mtime,
            "date_br": date_br,
            "doc_date": pd.get("doc_date") or "",
        })

    return results
