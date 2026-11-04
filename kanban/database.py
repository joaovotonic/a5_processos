"""Conexão com o SQLite, criação do esquema e dados iniciais."""
import os
import sqlite3
from contextlib import contextmanager

from .config import (
    BACKUP_DIR, DB_DIR, DB_PATH, ENTRADA_PDFS_DIR, ARQUIVADOS_PDFS_DIR,
    ENTRADA_EXTERNOS_DIR, ARQUIVADOS_EXTERNOS_DIR, ROTAS_IMAGENS_DIR
)

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(ENTRADA_PDFS_DIR, exist_ok=True)
os.makedirs(ARQUIVADOS_PDFS_DIR, exist_ok=True)
os.makedirs(ENTRADA_EXTERNOS_DIR, exist_ok=True)
os.makedirs(ARQUIVADOS_EXTERNOS_DIR, exist_ok=True)
os.makedirs(ROTAS_IMAGENS_DIR, exist_ok=True)

# Listas padrões da Esteira de Produção da A5 Tecnologia
INITIAL_LISTS = [
    {"title": "ORÇAMENTOS", "is_tech": 0, "role": "orcamento"},
    {"title": "TEC. João Otoni", "is_tech": 1, "role": "tech"},
    {"title": "TEC. Enzo Gabriel", "is_tech": 1, "role": "tech"},
    {"title": "TEC. Guilherme", "is_tech": 1, "role": "tech"},
    {"title": "TEC. Wisley", "is_tech": 1, "role": "tech"},
    {"title": "TEC. Iago", "is_tech": 1, "role": "tech"},
    {"title": "TEC. ANTONIO", "is_tech": 1, "role": "tech"},
    {"title": "ORÇAMENTOS FEITOS", "is_tech": 0, "role": "orcamentos_feitos"},
    {"title": "ORÇAMENTOS ENVIADOS", "is_tech": 0, "role": "orcamentos_enviados"},
    {"title": "APROVADOS", "is_tech": 0, "role": "aprovados"},
    {"title": "FINALIZADAS", "is_tech": 0, "role": "finalizada"}
]

# Etiquetas padrões com cores semânticas (Hex + classes Tailwind)
INITIAL_LABELS = [
    {"name": "AGUARDANDO", "color": "#F59E0B", "text_color": "#FFFFFF", "priority": 1},
    {"name": "ORÇ. APROVADO", "color": "#10B981", "text_color": "#FFFFFF", "priority": 2},
    {"name": "URGENTE", "color": "#EF4444", "text_color": "#FFFFFF", "priority": 10},
    {"name": "Falta Peça", "color": "#F97316", "text_color": "#FFFFFF", "priority": 3},
    {"name": "EM GARANTIA", "color": "#8B5CF6", "text_color": "#FFFFFF", "priority": 9},
    {"name": "NÃO AUTORIZADO", "color": "#64748B", "text_color": "#FFFFFF", "priority": 0},
    {"name": "FEITO ORÇ.", "color": "#0EA5E9", "text_color": "#FFFFFF", "priority": 2},
    {"name": "AGUARDANDO PAGAMENTO", "color": "#EC4899", "text_color": "#FFFFFF", "priority": 1}
]

DEFAULT_SETTINGS = {
    "tv_muted": "0",
    "admin_theme": "clean",
    "daily_goal": "15",
    "last_backup_date": ""
}


_schema_checked = False


def get_db_connection():
    """Retorna conexão SQLite otimizada com suporte a múltiplos acessos concorrentes (WAL)."""
    global _schema_checked
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    if not _schema_checked:
        _schema_checked = True
        try:
            has_cards = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cards'"
            ).fetchone()
            if has_cards:
                _ensure_cards_columns(conn.cursor())
                _ensure_esteira_lists(conn.cursor())
                _ensure_scale_models(conn.cursor())
                _ensure_external_routes_tables(conn.cursor())
                conn.commit()
        except Exception:
            pass
    return conn


@contextmanager
def connect():
    """
    Abre uma conexão que é SEMPRE fechada ao final do bloco `with`.
    Faz commit se tudo deu certo e rollback se ocorreu qualquer erro,
    evitando que uma requisição com falha deixe o banco travado (database is locked).
    """
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Inicializa o esquema do banco de dados e popula as listas e etiquetas iniciais."""
    from .backup import perform_daily_backup

    with connect() as conn:
        cursor = conn.cursor()

        # 1. Tabela de Colunas / Listas do Kanban
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                position INTEGER NOT NULL,
                is_tech INTEGER DEFAULT 0,
                role TEXT DEFAULT 'processo',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Tabela de Etiquetas (Labels)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                color TEXT NOT NULL,
                text_color TEXT DEFAULT '#FFFFFF',
                priority INTEGER DEFAULT 1
            )
        """)

        # 3. Tabela Principal de Cartões (Ordens de Serviço - O.S.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                os_number TEXT NOT NULL UNIQUE,
                client_name TEXT NOT NULL,
                equipment_type TEXT NOT NULL,
                equipment_model TEXT DEFAULT '',
                serial_number TEXT DEFAULT '',
                shelf_location TEXT DEFAULT '',
                reported_defect TEXT DEFAULT '',
                list_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                labels_json TEXT DEFAULT '[]',
                entry_photos_json TEXT DEFAULT '[]',
                exit_photos_json TEXT DEFAULT '[]',

                -- Dados de Orçamento Digital e Fechamento Técnico (POP)
                previous_service TEXT DEFAULT '',
                quote_status TEXT DEFAULT 'pending_claim',
                evaluator_tech TEXT DEFAULT '',
                finisher_tech TEXT DEFAULT '',
                quote_started_at TEXT DEFAULT NULL,
                quote_finished_at TEXT DEFAULT NULL,
                quote_data_json TEXT DEFAULT '{}',
                quote_photos_json TEXT DEFAULT '[]',
                label_before_photos_json TEXT DEFAULT '[]',
                label_after_photos_json TEXT DEFAULT '[]',
                tech_name TEXT DEFAULT '',
                pop_calibration INTEGER DEFAULT 0,
                pop_cleaning INTEGER DEFAULT 0,
                inmetro_seal TEXT DEFAULT '',
                parts_used TEXT DEFAULT '',
                root_cause TEXT DEFAULT '',
                tech_notes TEXT DEFAULT '',
                admin_notes TEXT DEFAULT '',
                reopen_requested INTEGER DEFAULT 0,
                reopen_requested_by TEXT DEFAULT '',
                reopen_requested_at TEXT DEFAULT NULL,

                -- Controle de Cronômetro de Estufa / Testes
                timer_end_at TEXT DEFAULT NULL,
                timer_label TEXT DEFAULT '',

                -- Controle de Tempo / SLA
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                moved_at TEXT NOT NULL,
                finished_at TEXT DEFAULT NULL,

                FOREIGN KEY (list_id) REFERENCES lists (id) ON DELETE CASCADE
            )
        """)

        # 4. Tabela de Histórico de Movimentações e Auditoria
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS card_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                os_number TEXT NOT NULL,
                from_list TEXT,
                to_list TEXT,
                actor TEXT DEFAULT 'Sistema',
                action_description TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE
            )
        """)

        # 5. Tabela de Configurações Globais (Tema, Mute da TV, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # 6. Tabela de Pré-Entradas de Fotos da Recepção (antes de gerar Nº da O.S. no Teorema)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                equipment_type TEXT DEFAULT 'Balança Toledo Prix',
                equipment_model TEXT DEFAULT '',
                serial_number TEXT DEFAULT '',
                shelf_location TEXT DEFAULT '',
                reported_defect TEXT DEFAULT '',
                previous_service TEXT DEFAULT '',
                photos_json TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)

        # Popula Listas Iniciais se estiver vazio
        if cursor.execute("SELECT COUNT(*) as count FROM lists").fetchone()["count"] == 0:
            for idx, item in enumerate(INITIAL_LISTS):
                cursor.execute(
                    "INSERT INTO lists (title, position, is_tech, role) VALUES (?, ?, ?, ?)",
                    (item["title"], idx, item["is_tech"], item["role"])
                )

        # Popula Etiquetas Iniciais se estiver vazio
        if cursor.execute("SELECT COUNT(*) as count FROM labels").fetchone()["count"] == 0:
            for label in INITIAL_LABELS:
                cursor.execute(
                    "INSERT INTO labels (name, color, text_color, priority) VALUES (?, ?, ?, ?)",
                    (label["name"], label["color"], label["text_color"], label["priority"])
                )

        # Configurações padrões
        for k, v in DEFAULT_SETTINGS.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # Migração automática para bancos existentes (adiciona colunas novas sem perder dados)
        _ensure_cards_columns(cursor)
        _ensure_esteira_lists(cursor)
        _ensure_scale_models(cursor)
        _ensure_external_routes_tables(cursor)

    perform_daily_backup()


def _ensure_esteira_lists(cursor):
    """Garante que as colunas da esteira estejam alinhadas com o fluxo exato de produção."""
    cursor.execute("UPDATE lists SET title = 'ORÇAMENTOS FEITOS', role = 'orcamentos_feitos' WHERE title = 'ANALISES FEITAS' OR role = 'orcamentos_feitos';")
    cursor.execute("UPDATE lists SET title = 'ORÇAMENTOS ENVIADOS', role = 'orcamentos_enviados' WHERE title = 'ORÇAMENTOS ENVIADOS';")
    cursor.execute("UPDATE lists SET title = 'APROVADOS', role = 'aprovados' WHERE title = 'APROVADAS' OR title = 'APROVADOS';")
    cursor.execute("UPDATE lists SET title = 'FINALIZADAS', role = 'finalizada' WHERE title = 'BALANÇAS PRONTAS' OR title = 'FINALIZADAS';")
    # Remove colunas desnecessárias do kanban antigo se existirem
    cursor.execute("DELETE FROM lists WHERE title IN ('SR. JACSON', 'PENDÊNCIAS', 'BALANÇAS PRONTAS');")

    # Deduplica a lista 'FINALIZADAS', mantendo uma única coluna oficial
    fin_lists = cursor.execute("SELECT id FROM lists WHERE title = 'FINALIZADAS' OR role = 'finalizada' ORDER BY id ASC").fetchall()
    if len(fin_lists) > 1:
        primary_id = fin_lists[0]["id"]
        for dup in fin_lists[1:]:
            cursor.execute("UPDATE cards SET list_id = ? WHERE list_id = ?", (primary_id, dup["id"]))
            cursor.execute("DELETE FROM lists WHERE id = ?", (dup["id"],))


def _ensure_cards_columns(cursor):
    """Garante que todas as colunas do fluxo de orçamento digital existam em bancos já criados."""
    existing = {row["name"] for row in cursor.execute("PRAGMA table_info(cards)").fetchall()}
    new_columns = [
        ("previous_service", "TEXT DEFAULT ''"),
        ("quote_status", "TEXT DEFAULT 'pending_claim'"),
        ("evaluator_tech", "TEXT DEFAULT ''"),
        ("finisher_tech", "TEXT DEFAULT ''"),
        ("quote_started_at", "TEXT DEFAULT NULL"),
        ("quote_finished_at", "TEXT DEFAULT NULL"),
        ("quote_data_json", "TEXT DEFAULT '{}'"),
        ("quote_photos_json", "TEXT DEFAULT '[]'"),
        ("label_before_photos_json", "TEXT DEFAULT '[]'"),
        ("label_after_photos_json", "TEXT DEFAULT '[]'"),
        ("admin_notes", "TEXT DEFAULT ''"),
        ("reopen_requested", "INTEGER DEFAULT 0"),
        ("reopen_requested_by", "TEXT DEFAULT ''"),
        ("reopen_requested_at", "TEXT DEFAULT NULL"),
        ("cnpj_cpf", "TEXT DEFAULT ''"),
        ("trade_name", "TEXT DEFAULT ''"),
        ("phone", "TEXT DEFAULT ''"),
        ("email", "TEXT DEFAULT ''"),
        ("address", "TEXT DEFAULT ''"),
        ("city_state", "TEXT DEFAULT ''"),
        ("accessories_json", "TEXT DEFAULT '[]'"),
        ("pipeline_phase", "TEXT DEFAULT 'ORCAMENTOS_A_FAZER'"),
        ("inicio_orcamento", "TEXT DEFAULT NULL"),
        ("fim_orcamento", "TEXT DEFAULT NULL"),
        ("inicio_manutencao", "TEXT DEFAULT NULL"),
        ("fim_manutencao", "TEXT DEFAULT NULL"),
        ("tempo_orcamento_segundos", "INTEGER DEFAULT 0"),
        ("tempo_manutencao_segundos", "INTEGER DEFAULT 0"),
        ("tempo_liquido_segundos", "INTEGER DEFAULT 0"),
        ("pdf_source_path", "TEXT DEFAULT ''"),
        ("pdf_imported_at", "TEXT DEFAULT NULL"),
    ]
    for col_name, col_def in new_columns:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE cards ADD COLUMN {col_name} {col_def}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_pipeline_phase ON cards(pipeline_phase);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_os_number ON cards(os_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_tech_name ON cards(tech_name);")

    # Garante a criação da tabela de clientes locais para histórico e autocompletar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj_cpf TEXT DEFAULT '',
            client_name TEXT NOT NULL,
            trade_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city_state TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clients_cnpj ON clients (cnpj_cpf)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clients_name ON clients (client_name)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            equipment_type TEXT DEFAULT 'Balança Toledo Prix',
            equipment_model TEXT DEFAULT '',
            serial_number TEXT DEFAULT '',
            shelf_location TEXT DEFAULT '',
            reported_defect TEXT DEFAULT '',
            previous_service TEXT DEFAULT '',
            photos_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        )
    """)

    pending_existing = {row["name"] for row in cursor.execute("PRAGMA table_info(pending_entries)").fetchall()}
    for col_name, col_def in [
        ("cnpj_cpf", "TEXT DEFAULT ''"),
        ("trade_name", "TEXT DEFAULT ''"),
        ("phone", "TEXT DEFAULT ''"),
        ("email", "TEXT DEFAULT ''"),
        ("address", "TEXT DEFAULT ''"),
        ("city_state", "TEXT DEFAULT ''"),
        ("accessories_json", "TEXT DEFAULT '[]'"),
        ("entry_protocol", "TEXT DEFAULT ''"),
    ]:
        if col_name not in pending_existing:
            cursor.execute(f"ALTER TABLE pending_entries ADD COLUMN {col_name} {col_def}")


def _ensure_scale_models(cursor):
    """Cria tabela scale_models e popula com os modelos da Toledo, analíticas e industriais."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scale_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            model_name TEXT NOT NULL,
            capacity_str TEXT DEFAULT '',
            equipment_type TEXT DEFAULT 'Balança Toledo Prix',
            unit TEXT DEFAULT 'kg',
            division_rule_json TEXT DEFAULT '{}',
            description TEXT DEFAULT ''
        )
    """)
    cnt = cursor.execute("SELECT COUNT(*) as count FROM scale_models").fetchone()["count"]
    if cnt == 0:
        import json
        from .services.scales import DEFAULT_SCALE_MODELS
        for item in DEFAULT_SCALE_MODELS:
            cursor.execute("""
                INSERT INTO scale_models (brand, model_name, capacity_str, equipment_type, unit, division_rule_json, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item["brand"],
                item["model_name"],
                item["capacity_str"],
                item["equipment_type"],
                item["unit"],
                json.dumps(item.get("division_rule", {}), ensure_ascii=False),
                item.get("description", "")
            ))


def _ensure_external_routes_tables(cursor):
    """Cria tabelas de chamados externos e rotas de rua se não existirem e aplica migrações."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS external_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            os_number TEXT DEFAULT '',
            client_name TEXT NOT NULL,
            open_date TEXT DEFAULT '',
            open_time TEXT DEFAULT '',
            sector TEXT DEFAULT '',
            equipment_model TEXT DEFAULT '',
            reported_defect TEXT DEFAULT '',
            tasks_notes TEXT DEFAULT '',
            technician TEXT DEFAULT '',
            route_date TEXT DEFAULT '',
            route_shift TEXT DEFAULT 'manha',
            route_order INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending_route',
            attendance_status TEXT DEFAULT 'pending',
            unattended_reason TEXT DEFAULT '',
            pdf_source_path TEXT DEFAULT '',
            pdf_imported_at TEXT DEFAULT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_orders_route_date ON external_orders(route_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_orders_technician ON external_orders(technician);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_orders_status ON external_orders(status);")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS external_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_date TEXT NOT NULL,
            route_shift TEXT DEFAULT 'manha',
            technician TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT '',
            finalized_at TEXT DEFAULT NULL,
            finalized_by TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_routes_date ON external_routes(route_date);")

    # Migrações seguras de colunas caso as tabelas já tenham sido criadas
    order_cols = {row["name"] for row in cursor.execute("PRAGMA table_info(external_orders)").fetchall()}
    if "route_shift" not in order_cols:
        cursor.execute("ALTER TABLE external_orders ADD COLUMN route_shift TEXT DEFAULT 'manha'")
    if "attendance_status" not in order_cols:
        cursor.execute("ALTER TABLE external_orders ADD COLUMN attendance_status TEXT DEFAULT 'pending'")
    if "unattended_reason" not in order_cols:
        cursor.execute("ALTER TABLE external_orders ADD COLUMN unattended_reason TEXT DEFAULT ''")

    route_cols = {row["name"] for row in cursor.execute("PRAGMA table_info(external_routes)").fetchall()}
    if "route_shift" not in route_cols:
        cursor.execute("ALTER TABLE external_routes ADD COLUMN route_shift TEXT DEFAULT 'manha'")



