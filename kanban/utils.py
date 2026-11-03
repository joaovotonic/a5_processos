"""Utilitários de rede, arquivos e leitura de dados das requisições."""
import os
import shutil
import socket
import uuid
from datetime import datetime

from flask import request
from werkzeug.utils import secure_filename

from .config import ALLOWED_PHOTO_EXTENSIONS, BASE_DIR, UPLOAD_FOLDER


# ==============================================================================
# REDE
# ==============================================================================
def get_local_ip():
    """Descobre automaticamente o IP da placa de rede/Wi-Fi local do PC da Recepção."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# ==============================================================================
# FOTOS
# ==============================================================================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS


def save_os_photos(files, os_number, stage="entrada"):
    """
    Salva fotos organizadas por pasta da O.S.:
    /static/uploads/OS_1050/entrada/entrada_20261028_142057_591_a1b2c3.jpg
    /static/uploads/OS_1050/saida/saida_20261028_143206_349_d4e5f6.jpg

    O sufixo aleatório evita que fotos enviadas no mesmo milissegundo
    sobrescrevam umas às outras.
    """
    safe_os = secure_filename(f"OS_{os_number}")
    target_dir = os.path.join(UPLOAD_FOLDER, safe_os, stage)
    os.makedirs(target_dir, exist_ok=True)

    saved_urls = []
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            filename = f"{stage}_{timestamp}_{uuid.uuid4().hex[:6]}.{ext}"
            file.save(os.path.join(target_dir, filename))
            saved_urls.append(f"/static/uploads/{safe_os}/{stage}/{filename}")
    return saved_urls


def adopt_pre_entry_photos(pre_urls, os_number, stage="entrada"):
    """
    Move fotos capturadas na pré-entrada (/recepcao-fotos, antes de abrir no Teorema)
    para a pasta definitiva da O.S. (/static/uploads/OS_<os_number>/entrada/) e limpa a pasta temporária.
    """
    if not pre_urls:
        return []
    safe_os = secure_filename(f"OS_{os_number}")
    target_dir = os.path.join(UPLOAD_FOLDER, safe_os, stage)
    os.makedirs(target_dir, exist_ok=True)

    adopted_urls = []
    pre_roots = set()
    for url in pre_urls:
        if not isinstance(url, str) or not url.startswith("/static/uploads/"):
            continue
        rel_path = url.lstrip("/").replace("/", os.sep)
        src_path = os.path.join(BASE_DIR, rel_path)
        if os.path.isfile(src_path):
            filename = os.path.basename(src_path)
            if filename.startswith("pre_entrada_"):
                filename = "entrada_" + filename[len("pre_entrada_"):]
            dest_path = os.path.join(target_dir, filename)
            try:
                shutil.move(src_path, dest_path)
                adopted_urls.append(f"/static/uploads/{safe_os}/{stage}/{filename}")
                parts = url.strip("/").split("/")
                if len(parts) >= 3 and parts[2].startswith("OS_PRE_"):
                    pre_roots.add(os.path.join(UPLOAD_FOLDER, parts[2]))
            except Exception:
                adopted_urls.append(url)
        else:
            adopted_urls.append(url)

    for pre_root in pre_roots:
        try:
            shutil.rmtree(pre_root, ignore_errors=True)
        except Exception:
            pass

    return adopted_urls


# ==============================================================================
# LEITURA SEGURA DE DADOS DA REQUISIÇÃO
# ==============================================================================
def json_body():
    """Corpo JSON da requisição ou {} (nunca lança erro 415/400)."""
    return request.get_json(silent=True) or {}


def request_data():
    """Dados de formulário (multipart/urlencoded) ou, se não houver, o corpo JSON."""
    if request.files or request.form:
        return request.form
    return json_body()


def get_text(data, key, default=""):
    """Lê um campo como texto sem espaços nas pontas; None/ausente vira `default`."""
    value = data.get(key)
    if value is None:
        return default
    return str(value).strip()


def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_checked(value):
    """Checkbox de formulário marcado ("1", "true" ou "on")."""
    return 1 if value in ["1", "true", "on"] else 0

