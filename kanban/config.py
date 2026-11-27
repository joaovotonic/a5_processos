"""Configurações centrais do sistema (caminhos, porta e chaves)."""
import os

# Raiz do projeto (pasta que contém app.py, templates/, static/, database/ e backups/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.abspath(os.environ.get("A5_DATA_DIR", BASE_DIR))

TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")
UPLOAD_FOLDER = os.path.join(DATA_DIR, "static", "uploads")

ENTRADA_PDFS_DIR = os.path.join(DATA_DIR, "entrada_pdfs")
ARQUIVADOS_PDFS_DIR = os.path.join(DATA_DIR, "arquivados_pdfs")

ENTRADA_EXTERNOS_DIR = os.path.join(DATA_DIR, "entrada_chamados_externos")
ARQUIVADOS_EXTERNOS_DIR = os.path.join(DATA_DIR, "arquivados_chamados_externos")
PDF_LIBRARY_DIR = os.path.join(DATA_DIR, "biblioteca_pdfs")
ROTAS_IMAGENS_DIR = os.path.join(DATA_DIR, "rotas_imagens")

DB_DIR = os.path.join(DATA_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "a5_kanban.db")
TOLEDO_PARTS_PATH = os.path.join(DB_DIR, "toledo_parts.json")
BACKUP_DIR = os.path.abspath(os.environ.get("A5_BACKUP_DIR", os.path.join(DATA_DIR, "backups")))
MAX_BACKUP_FILES = 60  # 30 pares (.db + .json)

PORT = int(os.environ.get("A5_PORT", "5000"))
TUNNEL_MODE = os.environ.get("A5_TUNNEL_MODE", "").strip().lower() in {"1", "true", "yes"}
BEHIND_PROXY = os.environ.get("A5_BEHIND_PROXY", "").strip().lower() in {"1", "true", "yes"}
TUNNEL_PUBLIC_HOSTNAME = os.environ.get("A5_TUNNEL_PUBLIC_HOSTNAME", "").strip().lower()
PUBLIC_URL = os.environ.get("A5_PUBLIC_URL", "").strip().rstrip("/")
DISABLE_PYTHON_GZIP = os.environ.get("A5_DISABLE_PYTHON_GZIP", "").strip().lower() in {"1", "true", "yes"}
SOCKETIO_ASYNC_MODE = os.environ.get(
    "A5_SOCKETIO_ASYNC_MODE",
    "gevent" if (TUNNEL_MODE or BEHIND_PROXY) else "threading",
).strip().lower()
if SOCKETIO_ASYNC_MODE not in {"threading", "gevent"}:
    raise ValueError("A5_SOCKETIO_ASYNC_MODE deve ser 'threading' ou 'gevent'.")

# Pode ser sobrescrita pela variável de ambiente A5_SECRET_KEY (obrigatória em produção/proxy)
DEFAULT_SECRET_KEY = "a5-tecnologia-toledo-prix-secret-key-2025"
SECRET_KEY = os.environ.get("A5_SECRET_KEY", DEFAULT_SECRET_KEY)

# Integrações opcionais de produção/VPS
PDF_INGEST_TOKEN = os.environ.get("A5_PDF_INGEST_TOKEN", "").strip()
INTEGRATION_TOKEN = os.environ.get("A5_INTEGRATION_TOKEN", "").strip()
CHATWOOT_BRIDGE_URL = os.environ.get("A5_CHATWOOT_BRIDGE_URL", "http://gemini-assistant:4000").strip().rstrip("/")
CHATWOOT_PUBLIC_URL = os.environ.get("A5_CHATWOOT_PUBLIC_URL", "https://chat.a5painel.cloud").strip().rstrip("/")
GITHUB_TOKEN = os.environ.get("A5_GITHUB_TOKEN", "").strip()
UPDATE_BRANCH = os.environ.get("A5_UPDATE_BRANCH", "main").strip() or "main"
YT_COOKIES_FILE = os.environ.get("A5_YT_COOKIES_FILE", os.path.join(DB_DIR, "yt_cookies.txt")).strip()
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # Limite de 50MB por envio de fotos

ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "jfif", "bmp", "heic", "heif"}

DEFAULT_EQUIPMENT_TYPE = "Balança Toledo Prix"
SLA_HOURS = 24.0
