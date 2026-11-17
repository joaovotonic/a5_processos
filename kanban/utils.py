"""Utilitários de rede, arquivos e leitura de dados das requisições."""
import os
import re
import shutil
import socket
import uuid
from datetime import datetime

from flask import request
from werkzeug.utils import secure_filename

from .config import ALLOWED_PHOTO_EXTENSIONS, BASE_DIR, UPLOAD_FOLDER


def format_os_number(os_number: str) -> str:
    """
    Padroniza o número da O.S. para o formato oficial da A5 Tecnologia (6 dígitos).
    Exemplos:
      '0000026797' -> '026797'
      '0000026791' -> '026791'
      '26797'      -> '026797'
      '026797'     -> '026797'
      '997452'     -> '997452'
    """
    raw = str(os_number or "").strip()
    if not raw or raw.startswith("TEO-") or raw.upper().startswith("S/N"):
        return raw
    m_suf = re.match(r"^0*(\d+)(-[A-Za-z0-9]+)$", raw)
    if m_suf:
        base = m_suf.group(1).lstrip("0") or "0"
        if len(base) < 6:
            base = base.zfill(6)
        return f"{base}{m_suf.group(2).upper()}"
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw
    trimmed = digits.lstrip("0") or "0"
    if len(trimmed) < 6:
        return trimmed.zfill(6)
    return trimmed



# ==============================================================================
# REDE
# ==============================================================================
def _is_loopback_host(host: str) -> bool:
    clean = (host or "").split(":")[0].strip().lower()
    return clean in {"", "localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}


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


def resolve_public_base_url() -> str:
    """
    Resolve a URL base alcançável pelo celular (QR Code da O.S. e Pré-Entrada):
    1. Se a requisição chegou via proxy/túnel (Cloudflare Tunnel / trycloudflare), usa X-Forwarded-Host.
    2. Se TUNNEL_MODE + TUNNEL_PUBLIC_HOSTNAME estiver ativo (mesmo acessado via localhost no servidor), usa o domínio HTTPS público.
    3. Se o host da requisição atual já for público/LAN (não loopback), usa ele próprio.
    4. Se acessado via localhost/127.0.0.1 localmente, substitui pelo IP real da rede Wi-Fi/LAN para o celular conseguir abrir.
    """
    from .config import PORT, TUNNEL_MODE, TUNNEL_PUBLIC_HOSTNAME

    xf_host = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    if xf_host and not _is_loopback_host(xf_host):
        xf_proto = (request.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip().lower()
        if xf_proto not in ("http", "https"):
            xf_proto = "https"
        return f"{xf_proto}://{xf_host}".rstrip("/")

    if TUNNEL_MODE and TUNNEL_PUBLIC_HOSTNAME:
        clean_host = TUNNEL_PUBLIC_HOSTNAME.replace("https://", "").replace("http://", "").strip("/")
        return f"https://{clean_host}"

    req_host = (request.host or "").strip()
    if req_host and not _is_loopback_host(req_host):
        cf_vis = request.headers.get("CF-Visitor") or ""
        scheme = "https" if (request.scheme == "https" or '"https"' in cf_vis) else "http"
        return f"{scheme}://{req_host}".rstrip("/")

    return f"http://{get_local_ip()}:{PORT}"


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

