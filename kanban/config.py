"""Configurações centrais do sistema (caminhos, porta e chaves)."""
import os

# Raiz do projeto (pasta que contém app.py, templates/, static/, database/ e backups/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_FOLDER = os.path.join(STATIC_DIR, "uploads")

ENTRADA_PDFS_DIR = os.path.join(BASE_DIR, "entrada_pdfs")
ARQUIVADOS_PDFS_DIR = os.path.join(BASE_DIR, "arquivados_pdfs")

DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "a5_kanban.db")
TOLEDO_PARTS_PATH = os.path.join(DB_DIR, "toledo_parts.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
MAX_BACKUP_FILES = 60  # 30 pares (.db + .json)

PORT = 5000

# Pode ser sobrescrita pela variável de ambiente A5_SECRET_KEY
SECRET_KEY = os.environ.get("A5_SECRET_KEY", "a5-tecnologia-toledo-prix-secret-key-2025")
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # Limite de 50MB por envio de fotos

ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "jfif", "bmp", "heic", "heif"}

DEFAULT_EQUIPMENT_TYPE = "Balança Toledo Prix"
SLA_HOURS = 24.0

