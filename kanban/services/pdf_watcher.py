"""
Serviço em Background para Monitoramento de Pasta de PDFs (Watchdog).
Monitora ./entrada_pdfs/, extrai dados das Ordens de Serviço do Teorema via pdf_parser,
insere o card no SQLite com pipeline_phase='ORCAMENTOS_A_FAZER', move o arquivo para ./arquivados_pdfs/
e dispara eventos SocketIO em tempo real (TV e auto-impressão da etiqueta na Adm).
"""
import os
import shutil
import time
import logging
import threading
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..config import ENTRADA_PDFS_DIR, ARQUIVADOS_PDFS_DIR
from ..database import connect
from ..services.pdf_parser import parse_os_pdf

logger = logging.getLogger("kanban.pdf_watcher")

_observer = None
_watcher_thread = None
_lock = threading.Lock()
_processed_files = set()


def _get_target_list_id(conn):
    """Busca o ID da coluna de ORÇAMENTOS inicial."""
    row = conn.execute("SELECT id FROM lists WHERE role = 'orcamento' ORDER BY position ASC LIMIT 1").fetchone()
    if row:
        return row["id"]
    row = conn.execute("SELECT id FROM lists WHERE title LIKE '%ORÇAMENTO%' ORDER BY position ASC LIMIT 1").fetchone()
    if row:
        return row["id"]
    row = conn.execute("SELECT id FROM lists ORDER BY position ASC LIMIT 1").fetchone()
    return row["id"] if row else 1


def _next_position(conn, list_id):
    row = conn.execute("SELECT COALESCE(MAX(position), -1) as m FROM cards WHERE list_id = ?", (list_id,)).fetchone()
    return (row["m"] if row else -1) + 1


def process_pdf_file(pdf_path: str):
    """Processa um arquivo PDF individual com proteção contra leituras concorrentes."""
    if not os.path.isfile(pdf_path) or not pdf_path.lower().endswith(".pdf"):
        return

    with _lock:
        norm_path = os.path.abspath(pdf_path)
        if norm_path in _processed_files:
            return
        _processed_files.add(norm_path)

    # Aguarda o arquivo terminar de ser gravado no disco pelo Teorema/Sistema
    file_size = -1
    for _ in range(10):
        try:
            curr_size = os.path.getsize(pdf_path)
            if curr_size > 0 and curr_size == file_size:
                break
            file_size = curr_size
        except Exception:
            pass
        time.sleep(0.4)

    try:
        data = parse_os_pdf(pdf_path)
        os_number = data.get("os_number") or ""
        now_iso = datetime.now().isoformat()
        now_dt = datetime.now()

        # Se não tiver número de OS, gera um identificador sequencial provisório do Teorema
        if not os_number:
            os_number = f"TEO-{now_dt.strftime('%H%M%S')}"

        # 1. Garante a pasta de arquivamento por Ano-Mês
        month_dir = os.path.join(ARQUIVADOS_PDFS_DIR, now_dt.strftime("%Y-%m"))
        os.makedirs(month_dir, exist_ok=True)
        dest_filename = f"OS_{os_number}_{os.path.basename(pdf_path)}"
        dest_path = os.path.join(month_dir, dest_filename)

        # Move o arquivo processado
        try:
            shutil.move(pdf_path, dest_path)
            relative_dest = os.path.relpath(dest_path, os.path.dirname(ARQUIVADOS_PDFS_DIR))
        except Exception as e:
            logger.warning(f"Não foi possível mover o arquivo {pdf_path}: {e}")
            relative_dest = pdf_path

        # 2. Inserção ou atualização no SQLite
        card_id = None
        with connect() as conn:
            existing = conn.execute("SELECT id FROM cards WHERE os_number = ?", (os_number,)).fetchone()
            if existing:
                card_id = existing["id"]
                conn.execute("""
                    UPDATE cards
                    SET client_name = COALESCE(NULLIF(?, ''), client_name),
                        equipment_model = COALESCE(NULLIF(?, ''), equipment_model),
                        serial_number = COALESCE(NULLIF(?, ''), serial_number),
                        reported_defect = COALESCE(NULLIF(?, ''), reported_defect),
                        pdf_source_path = ?,
                        pdf_imported_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    data["client_name"],
                    data["equipment_model"],
                    data["serial_number"],
                    data["reported_defect"],
                    relative_dest,
                    now_iso,
                    now_iso,
                    card_id
                ))
            else:
                target_list_id = _get_target_list_id(conn)
                pos = _next_position(conn, target_list_id)
                cur = conn.execute("""
                    INSERT INTO cards (
                        os_number, client_name, equipment_type, equipment_model,
                        serial_number, reported_defect, list_id, position,
                        pipeline_phase, pdf_source_path, pdf_imported_at,
                        created_at, updated_at, moved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ORCAMENTOS_A_FAZER', ?, ?, ?, ?, ?)
                """, (
                    os_number,
                    data["client_name"] or "CLIENTE TEOREMA",
                    data["equipment_type"] or "Balança Toledo Prix",
                    data["equipment_model"],
                    data["serial_number"],
                    data["reported_defect"],
                    target_list_id,
                    pos,
                    relative_dest,
                    now_iso,
                    now_iso,
                    now_iso,
                    now_iso
                ))
                card_id = cur.lastrowid

                # Histórico de auditoria
                conn.execute("""
                    INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
                    VALUES (?, ?, 'Entrada Automática', 'ORÇAMENTOS', 'Serviço Watchdog PDF', 'O.S. importada via PDF do Teorema', ?)
                """, (card_id, os_number, now_iso))

        logger.info(f"O.S. {os_number} inserida na esteira com sucesso a partir de {pdf_path}")

        # 3. Disparo de eventos SocketIO e notificações
        try:
            from .. import realtime
            from ..extensions import socketio

            # Atualiza todas as telas
            realtime.broadcast_board()

            # Notifica a tela da Adm (Priscila) para acionar a impressão da etiqueta térmica
            realtime._emit_safe("os_pdf_imported", {
                "os_number": os_number,
                "client_name": data["client_name"],
                "equipment_model": data["equipment_model"],
                "serial_number": data["serial_number"],
                "label_url": f"/etiqueta/{os_number}"
            })

            # Anuncia a chegada na TV da oficina
            card_mock = {
                "os_number": os_number,
                "client_name": data["client_name"],
                "equipment_type": data["equipment_model"] or data["equipment_type"],
                "is_urgent": False,
                "is_warranty": False
            }
            realtime.announce_arrival(card_mock, "orçamento inicial da esteira", intro="Atenção oficina! Nova O.S. importada do Teorema.")
        except Exception as e:
            logger.warning(f"Erro ao emitir notificações de tempo real para O.S. {os_number}: {e}")

    except Exception as exc:
        logger.error(f"Erro fatal ao processar PDF {pdf_path}: {exc}", exc_info=True)


class PdfDropHandler(FileSystemEventHandler):
    """Handler acionado quando um arquivo é solto na pasta entrada_pdfs."""

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            # Roda o processamento em thread separada para não travar o loop de eventos
            threading.Thread(target=process_pdf_file, args=(event.src_path,), daemon=True).start()

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            threading.Thread(target=process_pdf_file, args=(event.dest_path,), daemon=True).start()


def start_pdf_watcher():
    """Inicia o monitoramento contínuo da pasta ./entrada_pdfs/."""
    global _observer
    os.makedirs(ENTRADA_PDFS_DIR, exist_ok=True)
    os.makedirs(ARQUIVADOS_PDFS_DIR, exist_ok=True)

    if _observer is not None:
        return

    # Processa arquivos que já estejam porventura na pasta de entrada
    for fname in os.listdir(ENTRADA_PDFS_DIR):
        if fname.lower().endswith(".pdf"):
            full_p = os.path.join(ENTRADA_PDFS_DIR, fname)
            threading.Thread(target=process_pdf_file, args=(full_p,), daemon=True).start()

    _observer = Observer()
    handler = PdfDropHandler()
    _observer.schedule(handler, ENTRADA_PDFS_DIR, recursive=False)
    _observer.start()
    logger.info(f"Monitor Watchdog de PDFs iniciado em: {ENTRADA_PDFS_DIR}")


def stop_pdf_watcher():
    """Para o monitoramento de PDFs de forma limpa."""
    global _observer
    if _observer:
        try:
            _observer.stop()
            _observer.join(timeout=2.0)
        except Exception:
            pass
        _observer = None
        logger.info("Monitor Watchdog de PDFs finalizado.")
