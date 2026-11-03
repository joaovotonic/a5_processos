"""
Serviço de Gestão de Clientes e Consulta de CNPJ em Tempo Real (BrasilAPI)
A5 Tecnologia • Módulo Recepção & Balcão
"""

import json
import re
import urllib.request
import urllib.error
from datetime import datetime
from ..database import connect


def clean_doc(doc_str):
    """Remove caracteres não numéricos de CPF ou CNPJ."""
    return re.sub(r"\D", "", doc_str or "")


def _now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_or_update_client(client_data, conn=None):
    """
    Salva ou atualiza os dados de um cliente no banco de dados local.
    Usado para guardar clientes de forma permanente e permitir autocompletar futuro.
    Suporta conexão reutilizada para evitar 'database is locked' no SQLite.
    """
    client_name = (client_data.get("client_name") or "").strip().upper()
    if not client_name:
        return None

    raw_doc = clean_doc(client_data.get("cnpj_cpf"))
    trade_name = (client_data.get("trade_name") or "").strip().upper()
    phone = (client_data.get("phone") or "").strip()
    email = (client_data.get("email") or "").strip()
    address = (client_data.get("address") or "").strip().upper()
    city_state = (client_data.get("city_state") or "").strip().upper()
    now = _now_iso()

    def _execute(db_conn):
        existing = None
        if raw_doc:
            existing = db_conn.execute("SELECT * FROM clients WHERE cnpj_cpf = ?", (raw_doc,)).fetchone()
        if not existing:
            existing = db_conn.execute(
                "SELECT * FROM clients WHERE UPPER(client_name) = ? LIMIT 1",
                (client_name,)
            ).fetchone()

        if existing:
            db_conn.execute("""
                UPDATE clients
                SET cnpj_cpf = COALESCE(NULLIF(?, ''), cnpj_cpf),
                    client_name = ?,
                    trade_name = COALESCE(NULLIF(?, ''), trade_name),
                    phone = COALESCE(NULLIF(?, ''), phone),
                    email = COALESCE(NULLIF(?, ''), email),
                    address = COALESCE(NULLIF(?, ''), address),
                    city_state = COALESCE(NULLIF(?, ''), city_state),
                    updated_at = ?
                WHERE id = ?
            """, (
                raw_doc,
                client_name,
                trade_name,
                phone,
                email,
                address,
                city_state,
                now,
                existing["id"]
            ))
            client_id = existing["id"]
        else:
            cur = db_conn.execute("""
                INSERT INTO clients (
                    cnpj_cpf, client_name, trade_name, phone, email, address, city_state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                raw_doc,
                client_name,
                trade_name,
                phone,
                email,
                address,
                city_state,
                now,
                now
            ))
            client_id = cur.lastrowid

        row = db_conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return dict(row) if row else None

    if conn is not None:
        return _execute(conn)
    with connect() as new_conn:
        return _execute(new_conn)


def search_clients(query, limit=10):
    """Busca clientes por Nome, Nome Fantasia, CNPJ/CPF ou Telefone no banco local."""
    q = (query or "").strip()
    if not q:
        return []

    q_clean = clean_doc(q)
    q_like = f"%{q}%"

    with connect() as conn:
        rows = conn.execute("""
            SELECT * FROM clients
            WHERE client_name LIKE ?
               OR trade_name LIKE ?
               OR (? != '' AND cnpj_cpf LIKE ?)
               OR phone LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (q_like, q_like, q_clean, f"%{q_clean}%", q_like, limit)).fetchall()

    return [dict(r) for r in rows]


def fetch_cnpj_info(cnpj_input):
    """
    Busca informações oficiais da empresa pelo CNPJ.
    1. Verifica primeiro se já temos o CNPJ na base local.
    2. Se não tiver, consulta a BrasilAPI em tempo real (dados públicos oficiais da Receita Federal).
    3. Salva no banco local para consultas instantâneas futuras.
    """
    clean = clean_doc(cnpj_input)
    if len(clean) != 14:
        return {"error": "CNPJ deve conter exatamente 14 dígitos numéricos."}

    # 1. Verifica no banco local
    with connect() as conn:
        local_row = conn.execute("SELECT * FROM clients WHERE cnpj_cpf = ?", (clean,)).fetchone()
        if local_row and local_row["client_name"]:
            return {
                "source": "local_database",
                "data": dict(local_row)
            }

    # 2. Consulta BrasilAPI
    url = f"https://brasilapi.com.br/api/cnpj/v1/{clean}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "A5-Tecnologia-Kanban/2.0"}
    )

    try:
        with urllib.request.urlopen(req, timeout=4.5) as resp:
            if resp.status == 200:
                raw_data = json.loads(resp.read().decode("utf-8"))
                
                razao = (raw_data.get("razao_social") or "").strip().upper()
                fantasia = (raw_data.get("nome_fantasia") or "").strip().upper() or razao
                
                logradouro = raw_data.get("logradouro", "").strip()
                numero = raw_data.get("numero", "").strip()
                bairro = raw_data.get("bairro", "").strip()
                cep = raw_data.get("cep", "").strip()
                municipio = raw_data.get("municipio", "").strip().upper()
                uf = raw_data.get("uf", "").strip().upper()
                
                tel1 = raw_data.get("ddd_telefone_1", "").strip()
                email = (raw_data.get("email") or "").strip().lower()

                address = f"{logradouro}, {numero} - {bairro} CEP: {cep}".strip()
                city_state = f"{municipio} / {uf}".strip() if municipio else ""

                client_obj = {
                    "cnpj_cpf": clean,
                    "client_name": razao,
                    "trade_name": fantasia,
                    "phone": tel1,
                    "email": email,
                    "address": address,
                    "city_state": city_state,
                }

                # Salva localmente
                saved = save_or_update_client(client_obj)

                return {
                    "source": "brasil_api",
                    "data": saved or client_obj
                }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"error": "CNPJ não encontrado na base da Receita Federal."}
        return {"error": f"Receita Federal retornou status {e.code}."}
    except Exception as err:
        return {"error": f"Tempo limite ou falha ao consultar CNPJ: {str(err)}"}
