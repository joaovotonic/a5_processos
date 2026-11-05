"""
Serviço em Background para Monitoramento de Pastas de PDFs (Watchdog + Polling Resiliente).
Monitora:
1) ./entrada_pdfs/ (Entrada de Balanças na Esteira / Oficina)
   - Extrai dados das Ordens de Serviço do Teorema via pdf_parser
   - Insere ou reativa o card no topo da coluna ORÇAMENTOS com pipeline_phase='ORCAMENTOS_A_FAZER'
   - Move o arquivo para ./arquivados_pdfs/YYYY-MM/
   - Dispara eventos SocketIO em tempo real (TV e auto-impressão da etiqueta na Adm)
2) ./entrada_chamados_externos/ (Entrada de Chamados Externos / Rotas de Rua)
   - Extrai O.S., Cliente, Setor, Modelo e Defeito via parse_external_os_pdf
   - Insere na fila de chamados externos da data atual e turno atual do PC (< 11h manhã, >= 11h tarde)
   - Move o arquivo para ./arquivados_chamados_externos/YYYY-MM/
   - Dispara eventos SocketIO em tempo real para Admin e Diretoria
"""
import os
import re
import shutil
import time
import logging
import threading
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..config import ENTRADA_PDFS_DIR, ARQUIVADOS_PDFS_DIR, ENTRADA_EXTERNOS_DIR, ARQUIVADOS_EXTERNOS_DIR
from ..database import connect
from ..services.pdf_parser import parse_os_pdf
from ..services.externos import parse_external_os_pdf, create_external_order, format_external_os_number

logger = logging.getLogger("kanban.pdf_watcher")

_observer = None
_poll_thread = None
_stop_event = threading.Event()
_lock = threading.Lock()
_in_progress_files = set()


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


def _wait_for_pdf_ready(pdf_path: str, max_attempts: int = 12, delay: float = 0.25) -> bool:
    """
    Aguarda o arquivo PDF terminar de ser gravado e liberado pelo Windows Explorer / OneDrive / Teorema.
    Retorna True quando o arquivo possui tamanho > 0 estável e pode ser aberto para leitura.
    """
    last_size = -1
    for _ in range(max_attempts):
        if not os.path.isfile(pdf_path):
            return False
        try:
            curr_size = os.path.getsize(pdf_path)
            if curr_size > 0 and curr_size == last_size:
                with open(pdf_path, "rb") as f:
                    header = f.read(8)
                    if header:
                        return True
            last_size = curr_size
        except (PermissionError, OSError):
            pass
        time.sleep(delay)

    # Última tentativa direta se o arquivo existir e tiver bytes
    try:
        if os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0:
            with open(pdf_path, "rb") as f:
                f.read(4)
            return True
    except Exception:
        pass
    return False


def _archive_pdf_file(pdf_path: str, archive_root_dir: str, os_number: str) -> str:
    """
    Move o PDF consumido da pasta de entrada para a pasta de arquivados (YYYY-MM).
    Se o arquivo de destino já existir, sobrescreve com segurança.
    """
    now_dt = datetime.now()
    month_dir = os.path.join(archive_root_dir, now_dt.strftime("%Y-%m"))
    os.makedirs(month_dir, exist_ok=True)

    base_name = os.path.basename(pdf_path)
    prefix = f"OS_{os_number}_"
    dest_filename = base_name if base_name.startswith(prefix) else f"{prefix}{base_name}"
    dest_path = os.path.join(month_dir, dest_filename)

    for _ in range(6):
        try:
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    dest_filename = f"OS_{os_number}_{now_dt.strftime('%H%M%S')}_{base_name}"
                    dest_path = os.path.join(month_dir, dest_filename)
            shutil.move(pdf_path, dest_path)
            return os.path.relpath(dest_path, os.path.dirname(archive_root_dir))
        except Exception:
            try:
                shutil.copy2(pdf_path, dest_path)
                os.remove(pdf_path)
                return os.path.relpath(dest_path, os.path.dirname(archive_root_dir))
            except Exception:
                time.sleep(0.3)

    logger.warning(f"Não foi possível mover {pdf_path} para {dest_path}")
    return pdf_path


def process_pdf_file(pdf_path: str) -> bool:
    """
    Processa um arquivo PDF individual colocado em ./entrada_pdfs/ (Entrada de Balança).
    Retorna True se consumido com sucesso.
    """
    if not pdf_path or not pdf_path.lower().endswith(".pdf") or not os.path.isfile(pdf_path):
        return False

    norm_path = os.path.abspath(pdf_path)
    with _lock:
        if norm_path in _in_progress_files:
            return False
        _in_progress_files.add(norm_path)

    try:
        if not _wait_for_pdf_ready(pdf_path):
            return False

        from ..utils import format_os_number
        data = parse_os_pdf(pdf_path)
        os_number = format_os_number(data.get("os_number") or "")
        now_iso = datetime.now().isoformat()
        now_dt = datetime.now()

        if not os_number:
            os_number = f"TEO-{now_dt.strftime('%H%M%S')}"

        # 1. Move o arquivo processado para arquivados_pdfs/YYYY-MM/
        relative_dest = _archive_pdf_file(pdf_path, ARQUIVADOS_PDFS_DIR, os_number)

        # 2. Inserção ou reativação na coluna ORÇAMENTOS do SQLite
        card_id = None
        with connect() as conn:
            target_list_id = _get_target_list_id(conn)
            clean_digits = re.sub(r"\D", "", os_number).lstrip("0") or "0"
            existing = conn.execute(
                "SELECT id, list_id, pipeline_phase FROM cards WHERE os_number = ? OR os_number = ? OR os_number = ? OR os_number = ?",
                (os_number, clean_digits, clean_digits.zfill(10), clean_digits.zfill(6))
            ).fetchone()

            # Desloca posições na coluna ORÇAMENTOS para colocar a nova O.S. no topo (position = 0)
            conn.execute("UPDATE cards SET position = position + 1 WHERE list_id = ?", (target_list_id,))

            if existing:
                card_id = existing["id"]
                conn.execute("""
                    UPDATE cards
                    SET os_number = ?,
                        client_name = COALESCE(NULLIF(?, ''), client_name),
                        equipment_type = COALESCE(NULLIF(?, ''), equipment_type),
                        equipment_model = COALESCE(NULLIF(?, ''), equipment_model),
                        serial_number = COALESCE(NULLIF(?, ''), serial_number),
                        reported_defect = COALESCE(NULLIF(?, ''), reported_defect),
                        list_id = ?,
                        position = 0,
                        pipeline_phase = 'ORCAMENTOS_A_FAZER',
                        finished_at = NULL,
                        pdf_source_path = ?,
                        pdf_imported_at = ?,
                        updated_at = ?,
                        moved_at = ?
                    WHERE id = ?
                """, (
                    os_number,
                    data.get("client_name") or "",
                    data.get("equipment_type") or "Balança Toledo Prix",
                    data.get("equipment_model") or "",
                    data.get("serial_number") or "",
                    data.get("reported_defect") or "",
                    target_list_id,
                    relative_dest,
                    now_iso,
                    now_iso,
                    now_iso,
                    card_id
                ))
                conn.execute("""
                    INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
                    VALUES (?, ?, 'Entrada Automática PDF', 'ORÇAMENTOS', 'Serviço Watchdog PDF', 'O.S. recebida via pasta entrada_pdfs e posicionada em ORÇAMENTOS', ?)
                """, (card_id, os_number, now_iso))
            else:
                cur = conn.execute("""
                    INSERT INTO cards (
                        os_number, client_name, equipment_type, equipment_model,
                        serial_number, reported_defect, list_id, position,
                        pipeline_phase, pdf_source_path, pdf_imported_at,
                        created_at, updated_at, moved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'ORCAMENTOS_A_FAZER', ?, ?, ?, ?, ?)
                """, (
                    os_number,
                    data.get("client_name") or "CLIENTE TEOREMA",
                    data.get("equipment_type") or "Balança Toledo Prix",
                    data.get("equipment_model") or "",
                    data.get("serial_number") or "",
                    data.get("reported_defect") or "",
                    target_list_id,
                    relative_dest,
                    now_iso,
                    now_iso,
                    now_iso,
                    now_iso
                ))
                card_id = cur.lastrowid

                conn.execute("""
                    INSERT INTO card_history (card_id, os_number, from_list, to_list, actor, action_description, timestamp)
                    VALUES (?, ?, 'Entrada Automática', 'ORÇAMENTOS', 'Serviço Watchdog PDF', 'O.S. importada via PDF do Teorema', ?)
                """, (card_id, os_number, now_iso))

        logger.info(f"O.S. {os_number} inserida na esteira (ORÇAMENTOS) com sucesso a partir de {pdf_path}")

        # 3. Disparo de eventos SocketIO e notificações
        try:
            from .. import realtime

            realtime.broadcast_board()

            realtime._emit_safe("os_pdf_imported", {
                "os_number": os_number,
                "client_name": data.get("client_name") or "",
                "equipment_model": data.get("equipment_model") or "",
                "serial_number": data.get("serial_number") or "",
                "label_url": f"/etiqueta/{os_number}"
            })

            card_mock = {
                "os_number": os_number,
                "client_name": data.get("client_name") or "",
                "equipment_type": data.get("equipment_model") or data.get("equipment_type") or "Balança Toledo Prix",
                "is_urgent": False,
                "is_warranty": False
            }
            realtime.announce_arrival(card_mock, "orçamento inicial da esteira", intro="Atenção oficina! Nova O.S. importada do Teorema.")
        except Exception as e:
            logger.warning(f"Erro ao emitir notificações de tempo real para O.S. {os_number}: {e}")

        return True

    except Exception as exc:
        logger.error(f"Erro fatal ao processar PDF {pdf_path}: {exc}", exc_info=True)
        return False
    finally:
        with _lock:
            _in_progress_files.discard(norm_path)


def process_external_pdf_file(pdf_path: str) -> bool:
    """
    Processa um arquivo PDF de chamado externo colocado em ./entrada_chamados_externos/.
    Retorna True se consumido com sucesso.
    """
    if not pdf_path or not pdf_path.lower().endswith(".pdf") or not os.path.isfile(pdf_path):
        return False

    norm_path = os.path.abspath(pdf_path)
    with _lock:
        if norm_path in _in_progress_files:
            return False
        _in_progress_files.add(norm_path)

    try:
        if not _wait_for_pdf_ready(pdf_path):
            return False

        data = parse_external_os_pdf(pdf_path)
        os_number = format_external_os_number(data.get("os_number") or "")
        now_dt = datetime.now()

        if not os_number:
            os_number = f"EXT-{now_dt.strftime('%H%M%S')}"
            data["os_number"] = os_number

        # 1. Arquiva o PDF externo na pasta dedicada por Ano-Mês
        relative_dest = _archive_pdf_file(pdf_path, ARQUIVADOS_EXTERNOS_DIR, os_number)
        data["pdf_source_path"] = relative_dest

        # 2. Cria ou atualiza o chamado externo na data de hoje e turno atual
        created_order = create_external_order(data)
        logger.info(f"Chamado externo O.S. {os_number} ({data.get('client_name')}) importado com sucesso!")

        # 3. Emite notificação Socket.IO em tempo real
        try:
            from ..realtime import _emit_safe
            _emit_safe("external_order_created", {
                "order": created_order,
                "message": f"Novo chamado externo O.S. {os_number} ({data.get('client_name')}) recebido!"
            })
        except Exception as e:
            logger.warning(f"Erro ao emitir socketio para chamado externo {os_number}: {e}")

        return True

    except Exception as exc:
        logger.error(f"Erro ao processar PDF externo {pdf_path}: {exc}", exc_info=True)
        return False
    finally:
        with _lock:
            _in_progress_files.discard(norm_path)


def scan_pending_input_folders() -> dict:
    """
    Varre imediatamente as pastas ./entrada_pdfs/ e ./entrada_chamados_externos/
    e consome quaisquer arquivos .pdf pendentes.
    Pode ser chamada pelo loop de background ou sob demanda nas rotas da API.
    """
    os.makedirs(ENTRADA_PDFS_DIR, exist_ok=True)
    os.makedirs(ARQUIVADOS_PDFS_DIR, exist_ok=True)
    os.makedirs(ENTRADA_EXTERNOS_DIR, exist_ok=True)
    os.makedirs(ARQUIVADOS_EXTERNOS_DIR, exist_ok=True)

    consumed_scale = 0
    consumed_external = 0

    try:
        for fname in os.listdir(ENTRADA_PDFS_DIR):
            if fname.lower().endswith(".pdf"):
                full_p = os.path.join(ENTRADA_PDFS_DIR, fname)
                if process_pdf_file(full_p):
                    consumed_scale += 1
    except Exception as e:
        logger.warning(f"Erro ao varrer pasta entrada_pdfs: {e}")

    try:
        for fname in os.listdir(ENTRADA_EXTERNOS_DIR):
            if fname.lower().endswith(".pdf"):
                full_p = os.path.join(ENTRADA_EXTERNOS_DIR, fname)
                if process_external_pdf_file(full_p):
                    consumed_external += 1
    except Exception as e:
        logger.warning(f"Erro ao varrer pasta entrada_chamados_externos: {e}")

    return {"scale_pdfs": consumed_scale, "external_pdfs": consumed_external}


class ExternalPdfDropHandler(FileSystemEventHandler):
    """Handler acionado quando um arquivo é solto na pasta entrada_chamados_externos."""

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            threading.Thread(target=process_external_pdf_file, args=(event.src_path,), daemon=True).start()

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            threading.Thread(target=process_external_pdf_file, args=(event.dest_path,), daemon=True).start()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            threading.Thread(target=process_external_pdf_file, args=(event.src_path,), daemon=True).start()


class PdfDropHandler(FileSystemEventHandler):
    """Handler acionado quando um arquivo é solto na pasta entrada_pdfs."""

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            threading.Thread(target=process_pdf_file, args=(event.src_path,), daemon=True).start()

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            threading.Thread(target=process_pdf_file, args=(event.dest_path,), daemon=True).start()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            threading.Thread(target=process_pdf_file, args=(event.src_path,), daemon=True).start()


def _poll_folders_loop():
    """Loop contínuo em background (a cada 1.5s) para garantir consumo mesmo em pastas OneDrive/Rede."""
    while not _stop_event.is_set():
        try:
            scan_pending_input_folders()
        except Exception as e:
            logger.debug(f"Erro no loop de polling de PDFs: {e}")
        _stop_event.wait(1.5)


def start_pdf_watcher():
    """Inicia o monitoramento contínuo (Watchdog + Polling) das pastas ./entrada_pdfs/ e ./entrada_chamados_externos/."""
    global _observer, _poll_thread
    os.makedirs(ENTRADA_PDFS_DIR, exist_ok=True)
    os.makedirs(ARQUIVADOS_PDFS_DIR, exist_ok=True)
    os.makedirs(ENTRADA_EXTERNOS_DIR, exist_ok=True)
    os.makedirs(ARQUIVADOS_EXTERNOS_DIR, exist_ok=True)

    _stop_event.clear()

    # Varredura imediata inicial
    threading.Thread(target=scan_pending_input_folders, daemon=True).start()

    if _observer is None:
        try:
            _observer = Observer()
            handler = PdfDropHandler()
            ext_handler = ExternalPdfDropHandler()
            _observer.schedule(handler, ENTRADA_PDFS_DIR, recursive=False)
            _observer.schedule(ext_handler, ENTRADA_EXTERNOS_DIR, recursive=False)
            _observer.start()
            logger.info(f"Monitor Watchdog de PDFs iniciado em: {ENTRADA_PDFS_DIR} e {ENTRADA_EXTERNOS_DIR}")
        except Exception as e:
            logger.warning(f"Watchdog Observer falhou ao iniciar (usando polling contínuo): {e}")
            _observer = None

    if _poll_thread is None or not _poll_thread.is_alive():
        _poll_thread = threading.Thread(target=_poll_folders_loop, name="PdfFoldersPollThread", daemon=True)
        _poll_thread.start()


def stop_pdf_watcher():
    """Para o monitoramento de PDFs de forma limpa."""
    global _observer, _poll_thread
    _stop_event.set()
    if _observer:
        try:
            _observer.stop()
            _observer.join(timeout=2.0)
        except Exception:
            pass
        _observer = None
    _poll_thread = None
    logger.info("Monitor Watchdog de PDFs finalizado.")
