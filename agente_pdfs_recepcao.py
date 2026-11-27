"""
Agente leve para o PC da Recepção (Windows) — Envia PDFs do Teorema ERP para a VPS.

1) Fila de entrada da Esteira (move para ./enviados_vps/AAAA-MM/ após confirmar):
   - ./entrada_pdfs/               -> POST /api/ingest-pdf (kind=oficina)
   - ./entrada_chamados_externos/  -> POST /api/ingest-pdf (kind=externo)

2) Espelho Somente-Leitura do Acervo de O.S. em PDF (NUNCA move nem apaga arquivos!):
   - Padrão: C:\\Users\\Servidor\\OneDrive\\Técnico (e qualquer pasta em A5_PDF_LIBRARY_DIRS)
   - Sobe todo o histórico existente (mais recentes primeiro) e sincroniza continuamente
     qualquer PDF novo ou atualizado para a VPS (POST /api/integration/pdf-library/upload),
     permitindo consultar e enviar PDFs pelo Chatwoot (/pdf e /enviarpdf) 24h/dia!

Variáveis de ambiente:
  A5_VPS_URL           (padrão: https://a5painel.cloud)
  A5_PDF_INGEST_TOKEN  (obrigatório — mesmo valor configurado no .env da VPS)
  A5_PDF_LIBRARY_DIRS  (opcional — pastas separadas por ';' para espelhar PDFs)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
import threading
import time
from datetime import datetime

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VPS_URL = os.environ.get("A5_VPS_URL", "https://a5painel.cloud").strip().rstrip("/")
INGEST_TOKEN = os.environ.get("A5_PDF_INGEST_TOKEN", "").strip()
POLL_SECONDS = float(os.environ.get("A5_AGENT_POLL_SECONDS", "2.0"))
LIBRARY_SCAN_SECONDS = float(os.environ.get("A5_LIBRARY_SCAN_SECONDS", "15.0"))

WATCH_DIRS = [
    ("oficina", os.path.join(BASE_DIR, "entrada_pdfs")),
    ("externo", os.path.join(BASE_DIR, "entrada_chamados_externos")),
]
SENT_ARCHIVE_DIR = os.path.join(BASE_DIR, "enviados_vps")

DEFAULT_LIBRARY_CANDIDATES = [
    r"C:\Users\Servidor\OneDrive\Técnico",
    os.path.join(os.path.expanduser("~"), "OneDrive", "Técnico"),
]

AGENT_HOME = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
    "A5Processos",
)
LIBRARY_STATE_FILE = os.path.join(AGENT_HOME, "pdf-library-sync-state.json")
MAX_PDF_BYTES = 35 * 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AGENTE-PDF] %(levelname)s %(message)s",
)
logger = logging.getLogger("a5.pdf_agent")


def _resolve_library_dirs() -> list[str]:
    env_dirs = os.environ.get("A5_PDF_LIBRARY_DIRS", "").strip()
    candidates: list[str] = []
    if env_dirs:
        candidates.extend(p.strip().strip('"') for p in env_dirs.split(";") if p.strip())
    else:
        candidates.extend(DEFAULT_LIBRARY_CANDIDATES)

    resolved: list[str] = []
    seen: set[str] = set()
    for p in candidates:
        norm = os.path.normcase(os.path.abspath(p))
        if norm not in seen and os.path.isdir(p):
            seen.add(norm)
            resolved.append(os.path.abspath(p))
    return resolved


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


def _load_library_state() -> dict[str, dict]:
    try:
        if os.path.isfile(LIBRARY_STATE_FILE):
            with open(LIBRARY_STATE_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
    except Exception as exc:
        logger.warning("[BIBLIOTECA] Não foi possível ler estado salvo: %s", exc)
    return {}


def _save_library_state(state: dict[str, dict]) -> None:
    try:
        os.makedirs(AGENT_HOME, exist_ok=True)
        tmp = f"{LIBRARY_STATE_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False)
        os.replace(tmp, LIBRARY_STATE_FILE)
    except Exception as exc:
        logger.warning("[BIBLIOTECA] Não foi possível salvar estado: %s", exc)


def _sha256_file(path: str) -> tuple[str, int] | tuple[None, int]:
    h = hashlib.sha256()
    total = 0
    first_chunk = b""
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(262144)
            if not chunk:
                break
            if not first_chunk:
                first_chunk = chunk[:16]
                if not first_chunk.lstrip().startswith(b"%PDF-"):
                    return None, 0
            total += len(chunk)
            if total > MAX_PDF_BYTES:
                return None, total
            h.update(chunk)
    return (h.hexdigest(), total) if total > 0 else (None, 0)


def _sync_library_pass(lib_dirs: list[str], state: dict[str, dict], session: requests.Session) -> None:
    candidates: list[tuple[float, str, str, int]] = []
    for root_dir in lib_dirs:
        root_tag = os.path.basename(root_dir.rstrip("\\/")) or "acervo"
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Ignora pastas ocultas/temporárias
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in ("$recycle.bin", "system volume information")]
            for fn in filenames:
                if not fn.lower().endswith(".pdf") or fn.startswith("~$") or fn.startswith("."):
                    continue
                abs_path = os.path.join(dirpath, fn)
                try:
                    st = os.stat(abs_path)
                except OSError:
                    continue
                if st.st_size <= 0 or st.st_size > MAX_PDF_BYTES:
                    continue
                rel = os.path.relpath(abs_path, root_dir).replace("\\", "/")
                state_key = f"{root_tag}/{rel}"
                prev = state.get(state_key)
                if prev and abs(float(prev.get("mtime", 0)) - st.st_mtime) < 1.0 and int(prev.get("size", 0)) == st.st_size:
                    continue
                candidates.append((st.st_mtime, abs_path, state_key, st.st_size))

    if not candidates:
        return

    # Envia os mais recentes PRIMEIRO para as O.S. atuais ficarem disponíveis imediatamente!
    candidates.sort(key=lambda item: item[0], reverse=True)
    total_pending = len(candidates)
    if total_pending > 5:
        logger.info("[BIBLIOTECA] %d PDF(s) novos/pendentes encontrados. Sincronizando dos mais recentes para os mais antigos...", total_pending)

    headers = {"X-A5-Ingest-Token": INGEST_TOKEN}
    check_url = f"{VPS_URL}/api/integration/pdf-library/check"
    upload_url = f"{VPS_URL}/api/integration/pdf-library/upload"

    synced_count = 0
    # Processa em lotes de 25 para dedup via /check antes de subir bytes
    for start in range(0, total_pending, 25):
        batch = candidates[start : start + 25]
        hashed_items: list[tuple[float, str, str, int, str]] = []
        for mtime, abs_path, state_key, size in batch:
            try:
                # Se o arquivo foi modificado nos últimos 3s, aguarda estabilizar
                if (time.time() - mtime) < 3.0 and not _wait_file_stable(abs_path, attempts=6, delay=0.3):
                    continue
                digest, real_size = _sha256_file(abs_path)
                if digest:
                    hashed_items.append((mtime, abs_path, state_key, real_size, digest))
            except OSError:
                continue

        if not hashed_items:
            continue

        existing_hashes: set[str] = set()
        try:
            chk_resp = session.post(
                check_url,
                headers=headers,
                json={"hashes": [x[4] for x in hashed_items]},
                timeout=20,
            )
            if chk_resp.status_code == 200:
                existing_hashes = set(chk_resp.json().get("existing") or [])
        except Exception as exc:
            logger.warning("[BIBLIOTECA] Falha de rede ao consultar hashes: %s", exc)
            return

        dirty_state = False
        for mtime, abs_path, state_key, size, digest in hashed_items:
            if digest in existing_hashes:
                state[state_key] = {"mtime": mtime, "size": size, "sha256": digest}
                synced_count += 1
                dirty_state = True
                continue

            fname = os.path.basename(abs_path)
            try:
                with open(abs_path, "rb") as fh:
                    up_resp = session.post(
                        upload_url,
                        headers=headers,
                        data={
                            "source_rel_path": state_key,
                            "file_mtime": str(mtime),
                            "sha256": digest,
                        },
                        files={"file": (fname, fh, "application/pdf")},
                        timeout=60,
                    )
                if up_resp.status_code == 200 and up_resp.json().get("success"):
                    state[state_key] = {"mtime": mtime, "size": size, "sha256": digest}
                    synced_count += 1
                    dirty_state = True
                    if total_pending <= 10 or synced_count % 25 == 0 or synced_count == total_pending:
                        logger.info("[BIBLIOTECA] (%d/%d) Sincronizado: %s", synced_count, total_pending, state_key)
                else:
                    logger.warning("[BIBLIOTECA] VPS recusou %s (HTTP %s): %s", fname, up_resp.status_code, up_resp.text[:160])
            except Exception as exc:
                logger.warning("[BIBLIOTECA] Falha ao subir %s: %s", fname, exc)
                if dirty_state:
                    _save_library_state(state)
                return

        if dirty_state:
            _save_library_state(state)


def _library_sync_worker(lib_dirs: list[str]) -> None:
    state = _load_library_state()
    session = requests.Session()
    logger.info("[BIBLIOTECA] Espelho somente-leitura ativo (%d já sincronizados no índice local):", len(state))
    for d in lib_dirs:
        logger.info("[BIBLIOTECA] Monitorando (somente leitura): %s", d)

    while True:
        try:
            _sync_library_pass(lib_dirs, state, session)
        except Exception as exc:
            logger.warning("[BIBLIOTECA] Erro no ciclo de sincronização: %s", exc)
        time.sleep(LIBRARY_SCAN_SECONDS)


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

    lib_dirs = _resolve_library_dirs()
    if lib_dirs:
        t = threading.Thread(target=_library_sync_worker, args=(lib_dirs,), daemon=True, name="a5-pdf-library-sync")
        t.start()
    else:
        logger.info("[BIBLIOTECA] Pasta de acervo não encontrada neste PC (configure A5_PDF_LIBRARY_DIRS se desejar).")

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
