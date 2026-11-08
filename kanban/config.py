"""Configurações centrais do sistema (caminhos, porta e chaves)."""
import os

# Raiz do projeto (pasta que contém app.py, templates/, static/, database/ e backups/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.abspath(os.environ.get("A5_DATA_DIR", BASE_DIR))

TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_FOLDER = os.path.join(DATA_DIR, "static", "uploads")

ENTRADA_PDFS_DIR = os.path.join(DATA_DIR, "entrada_pdfs")
ARQUIVADOS_PDFS_DIR = os.path.join(DATA_DIR, "arquivados_pdfs")

ENTRADA_EXTERNOS_DIR = os.path.join(DATA_DIR, "entrada_chamados_externos")
ARQUIVADOS_EXTERNOS_DIR = os.path.join(DATA_DIR, "arquivados_chamados_externos")
ROTAS_IMAGENS_DIR = os.path.join(DATA_DIR, "rotas_imagens")

DB_DIR = os.path.join(DATA_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "a5_kanban.db")
TOLEDO_PARTS_PATH = os.path.join(DB_DIR, "toledo_parts.json")
BACKUP_DIR = os.path.abspath(os.environ.get("A5_BACKUP_DIR", os.path.join(DATA_DIR, "backups")))
MAX_BACKUP_FILES = 60  # 30 pares (.db + .json)

PORT = int(os.environ.get("A5_PORT", "5000"))
TUNNEL_MODE = os.environ.get("A5_TUNNEL_MODE", "").strip().lower() in {"1", "true", "yes"}
TUNNEL_PUBLIC_HOSTNAME = os.environ.get("A5_TUNNEL_PUBLIC_HOSTNAME", "").strip().lower()
SOCKETIO_ASYNC_MODE = os.environ.get(
    "A5_SOCKETIO_ASYNC_MODE",
    "gevent" if TUNNEL_MODE else "threading",
).strip().lower()
if SOCKETIO_ASYNC_MODE not in {"threading", "gevent"}:
    raise ValueError("A5_SOCKETIO_ASYNC_MODE deve ser 'threading' ou 'gevent'.")

# Pode ser sobrescrita pela variável de ambiente A5_SECRET_KEY
SECRET_KEY = os.environ.get("A5_SECRET_KEY", "a5-tecnologia-toledo-prix-secret-key-2025")
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # Limite de 50MB por envio de fotos

ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "jfif", "bmp", "heic", "heif"}

DEFAULT_EQUIPMENT_TYPE = "Balança Toledo Prix"
SLA_HOURS = 24.0
