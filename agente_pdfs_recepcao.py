"""
Agente leve para o PC da Recepção (Windows) — Envia PDFs do Teorema ERP para a VPS.

Monitora continuamente:
  - ./entrada_pdfs/               -> POST /api/ingest-pdf (kind=oficina)
  - ./entrada_chamados_externos/  -> POST /api/ingest-pdf (kind=externo)

Quando o envio é confirmado (HTTP 200), move o PDF para ./enviados_vps/AAAA-MM/.
Se a internet oscilar, tenta novamente automaticamente a cada 3 segundos sem perder nenhum PDF.

Variáveis de ambiente:
  A5_VPS_URL           (padrão: https://a5painel.cloud)
  A5_PDF_INGEST_TOKEN  (obrigatório — mesmo valor configurado no .env da VPS)
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import time
from datetime import datetime

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VPS_URL = os.environ.get("A5_VPS_URL", "https://a5painel.cloud").strip().rstrip("/")
INGEST_TOKEN = os.environ.get("A5_PDF_INGEST_TOKEN", "").strip()
POLL_SECONDS = float(os.environ.get("A5_AGENT_POLL_SECONDS", "2.0"))

WATCH_DIRS = [
    ("oficina", os.path.join(BASE_DIR, "entrada_pdfs")),
    ("externo", os.path.join(BASE_DIR, "entrada_chamados_externos")),
]
SENT_ARCHIVE_DIR = os.path.join(BASE_DIR, "enviados_vps")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AGENTE-PDF] %(levelname)s %(message)s",
)
logger = logging.getLogger("a5.pdf_agent")


def _wait_file_stable(path: str, attempts: int = 10, delay: float = 0.25) -> bool:
    last_size = -1
    for _ in range(attempts):
        if not os.path.isfile(path):
            return False
        try:
            size = os.path.getsize(path)
            if size > 0 and size == last_size:
                with open(path, "rb") as f:
                    if f.read(5).startswith(b"%PDF-"):
                        return True
            last_size = size
        except OSError:
            pass
        time.sleep(delay)
    return False


def _archive_sent(pdf_path: str, kind: str) -> None:
    month_dir = os.path.join(SENT_ARCHIVE_DIR, kind, datetime.now().strftime("%Y-%m"))
    os.makedirs(month_dir, exist_ok=True)
    base_name = os.path.basename(pdf_path)
    dest = os.path.join(month_dir, base_name)
    if os.path.exists(dest):
        ts = datetime.now().strftime("%H%M%S")
        dest = os.path.join(month_dir, f"{ts}_{base_name}")
    try:
        shutil.move(pdf_path, dest)
    except Exception:
        shutil.copy2(pdf_path, dest)
        os.remove(pdf_path)


def _send_pdf(pdf_path: str, kind: str) -> bool:
    if not _wait_file_stable(pdf_path):
        return False

    endpoint = f"{VPS_URL}/api/ingest-pdf"
    filename = os.path.basename(pdf_path)
    try:
        with open(pdf_path, "rb") as f:
            resp = requests.post(
                endpoint,
                headers={"X-A5-Ingest-Token": INGEST_TOKEN},
                data={"kind": kind},
                files={"file": (filename, f, "application/pdf")},
                timeout=30,
            )
        if resp.status_code == 200 and resp.json().get("success"):
            _archive_sent(pdf_path, kind)
            logger.info("Enviado (%s): %s -> %s", kind, filename, endpoint)
            return True
        logger.warning("Servidor recusou %s (HTTP %s): %s", filename, resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        logger.warning("Falha de rede ao enviar %s: %s", filename, exc)
        return False


def main() -> int:
    if not INGEST_TOKEN:
        logger.error("Defina a variável A5_PDF_INGEST_TOKEN antes de iniciar o agente.")
        return 1

    for _, folder in WATCH_DIRS:
        os.makedirs(folder, exist_ok=True)
    os.makedirs(SENT_ARCHIVE_DIR, exist_ok=True)

    logger.info("Agente de PDFs ativo -> %s", VPS_URL)
    for kind, folder in WATCH_DIRS:
        logger.info("Monitorando (%s): %s", kind, folder)

    while True:
        for kind, folder in WATCH_DIRS:
            try:
                for fname in sorted(os.listdir(folder)):
                    if fname.lower().endswith(".pdf"):
                        _send_pdf(os.path.join(folder, fname), kind)
            except Exception as exc:
                logger.warning("Erro ao varrer %s: %s", folder, exc)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
