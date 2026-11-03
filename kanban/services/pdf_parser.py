"""
Parser resiliente de Ordens de Serviço em PDF geradas pelo sistema Teorema ERP para a A5 Tecnologia.
Suporta extração via pdfplumber com fallback para pypdf e dedução inteligente por regex.
"""
import os
import re
import logging
from typing import Dict, Any

logger = logging.getLogger("kanban.pdf_parser")


def _clean(val: str) -> str:
    if not val:
        return ""
    # Remove múltiplos espaços e caracteres estranhos
    return re.sub(r"\s+", " ", val).strip()


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrai todo o texto do PDF usando pdfplumber com fallback para pypdf."""
    text = ""
    # Tentativa 1: pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages_text).strip()
    except Exception as e:
        logger.warning(f"Falha ao ler PDF com pdfplumber ({pdf_path}): {e}")

    # Tentativa 2 (fallback): pypdf
    if not text:
        try:
            import pypdf
            reader = pypdf.PdfReader(pdf_path)
            pages_text = [p.extract_text() or "" for p in reader.pages]
            text = "\n".join(pages_text).strip()
        except Exception as e:
            logger.warning(f"Falha ao ler PDF com pypdf ({pdf_path}): {e}")

    return text


def parse_os_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Analisa o PDF de Ordem de Serviço do Teorema e extrai:
    - os_number
    - client_name
    - equipment_type / equipment_model
    - serial_number
    - reported_defect
    """
    text = extract_text_from_pdf(pdf_path)
    filename = os.path.basename(pdf_path)
    name_no_ext, _ = os.path.splitext(filename)

    data = {
        "os_number": "",
        "client_name": "",
        "equipment_type": "Balança Toledo Prix",
        "equipment_model": "",
        "serial_number": "",
        "reported_defect": "Defeito informado na O.S. física Teorema",
        "raw_text": text,
        "filename": filename
    }

    # 1. Extração do Número da O.S.
    os_patterns = [
        r"(?:ORDEM\s+DE\s+SERVI[ÇC]O|O\.?S\.?|NUMERO|N[°ºo]\.?)\s*[:#\s]?\s*(\d{3,8})",
        r"(?:O\.?S\.?)\s*[:#\s]?\s*([A-Z0-9\-\/]{3,12})",
        r"N[º°]\s*(\d+)",
    ]
    for pat in os_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            data["os_number"] = m.group(1).strip()
            break

    # Se não achou no texto, procura no nome do arquivo (ex: OS_12345.pdf ou 12345.pdf)
    if not data["os_number"]:
        m = re.search(r"(?:OS|ORDEM)?[_\-\s]?(\d{3,8})", name_no_ext, re.IGNORECASE)
        if m:
            data["os_number"] = m.group(1).strip()

    # 2. Extração do Nome do Cliente / Razão Social
    client_patterns = [
        r"(?:CLIENTE|RAZ[ÃA]O\s+SOCIAL|NOME\/RAZ[ÃA]O|DESTINAT[ÁA]RIO)\s*[:#]?\s*([^\n\r]+)",
        r"(?:SR\(A\)|NOME)\s*[:#]?\s*([^\n\r]+)",
    ]
    for pat in client_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = _clean(m.group(1))
            # Remove sufixos como CNPJ/CPF que possam vir na mesma linha
            candidate = re.split(r"(?:CNPJ|CPF|IE|FONE|TEL|END|DATA)", candidate, flags=re.IGNORECASE)[0]
            candidate = _clean(candidate)
            if len(candidate) > 2:
                data["client_name"] = candidate.upper()
                break

    # Fallback para cliente no nome do arquivo caso não ache (ex: OS_12345_SUPERMERCADO.pdf)
    if not data["client_name"]:
        parts = re.split(r"[_\-\.]", name_no_ext)
        if len(parts) >= 2:
            data["client_name"] = _clean(parts[-1]).upper()

    if not data["client_name"]:
        data["client_name"] = "CLIENTE BALCÃO TEOREMA"

    # 3. Extração do Modelo / Equipamento / Marca
    model_patterns = [
        r"(?:MODELO|EQUIPAMENTO|BALAN[ÇC]A|APARELHO|DESCRI[ÇC][ÃA]O)\s*[:#]?\s*([^\n\r]+)",
        r"(PRIX\s+[0-9A-Z\s\+\-]+)",
        r"(TOLEDO\s+[0-9A-Z\s\+\-]+)",
        r"(ELGIN\s+[0-9A-Z\s\+\-]+)",
        r"(FILIZOLA\s+[0-9A-Z\s\+\-]+)",
        r"(URANO\s+[0-9A-Z\s\+\-]+)",
        r"(RAMUZA\s+[0-9A-Z\s\+\-]+)",
    ]
    for pat in model_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = _clean(m.group(1))
            candidate = re.split(r"(?:SERIE|S[ÉE]RIE|N\/S|COR|CAPACIDADE|DEFEITO)", candidate, flags=re.IGNORECASE)[0]
            candidate = _clean(candidate)
            if len(candidate) > 1:
                data["equipment_model"] = candidate.upper()
                break

    # Marca padrão Prix se detectar Prix
    if "PRIX" in text.upper() and not data["equipment_model"]:
        data["equipment_model"] = "TOLEDO PRIX"

    # 4. Extração do Número de Série
    serial_patterns = [
        r"(?:S[ÉE]RIE|N[°ºo]?\s*S[ÉE]RIE|N\/S|SERIAL|CHASSI)\s*[:#]?\s*([A-Z0-9\-\.]{3,20})",
    ]
    for pat in serial_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = _clean(m.group(1))
            if len(candidate) >= 3:
                data["serial_number"] = candidate.upper()
                break

    # 5. Extração do Defeito Reclamado
    defect_patterns = [
        r"(?:DEFEITO(?:\s+RELATADO|\s+RECLAMADO)?|PROBLEMA|RECLAMA[ÇC][ÃA]O|SOLICITA[ÇC][ÃA]O|MOTIVO)\s*[:#]?\s*([^\n\r]+(?:\n[^\n\r]+)?)",
    ]
    for pat in defect_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = _clean(m.group(1))
            candidate = re.split(r"(?:OBS|OBSERVA[ÇC][ÃA]O|LAUDO|T[ÉE]CNICO|VALOR)", candidate, flags=re.IGNORECASE)[0]
            candidate = _clean(candidate)
            if len(candidate) > 3:
                data["reported_defect"] = candidate
                break

    return data
