"""Relatórios: exportação CSV para o Excel."""
import csv
import io
from datetime import datetime

from ..database import connect
from .board import normalize_quote_data

CSV_HEADER = [
    "Nº O.S.", "Cliente", "Equipamento", "Modelo", "Nº de Série", "Coluna Atual",
    "Técnico Responsável", "Técnico Avaliador", "Técnico Finalizador",
    "Serviço Feito Anteriormente", "Lacre IPEM A5", "Peças Utilizadas",
    "Laudo Técnico / Causa", "Solução Executada", "Data Entrada", "Data Finalização"
]

# Formato de data usado no filtro LIKE de cada período
_PERIOD_FORMATS = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}


def build_os_csv(period="all"):
    """
    Gera o relatório de O.S. (CSV com ; e BOM UTF-8 para o Excel reconhecer acentos).
    period: day, month, year ou all. Retorna (conteúdo, nome do arquivo).
    """
    now = datetime.now()
    query = """
        SELECT c.os_number, c.client_name, c.equipment_type, c.equipment_model,
               c.serial_number, l.title as current_stage, c.tech_name,
               c.evaluator_tech, c.finisher_tech, c.previous_service,
               c.inmetro_seal, c.parts_used, c.root_cause, c.tech_notes,
               c.quote_data_json, c.created_at, c.finished_at
        FROM cards c
        LEFT JOIN lists l ON c.list_id = l.id
    """
    params = ()
    if period in _PERIOD_FORMATS:
        query += " WHERE c.created_at LIKE ? OR c.finished_at LIKE ?"
        p = f"{now.strftime(_PERIOD_FORMATS[period])}%"
        params = (p, p)
    query += " ORDER BY c.id DESC"

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    output = io.StringIO()
    output.write("\ufeff")  # BOM para o Microsoft Excel reconhecer acentos automaticamente
    writer = csv.writer(output, delimiter=";")
    writer.writerow(CSV_HEADER)
    for r in rows:
        qd = normalize_quote_data(r["quote_data_json"])
        laudo = qd.get("technical_report") or r["root_cause"] or ""
        solucao = qd.get("solution") or r["tech_notes"] or ""
        writer.writerow([
            r["os_number"],
            r["client_name"],
            r["equipment_type"],
            r["equipment_model"],
            r["serial_number"] or "",
            r["current_stage"],
            r["tech_name"],
            r["evaluator_tech"] or r["tech_name"] or "",
            r["finisher_tech"] or (r["tech_name"] if r["finished_at"] else ""),
            r["previous_service"] or "",
            r["inmetro_seal"],
            r["parts_used"],
            laudo,
            solucao,
            r["created_at"],
            r["finished_at"] or "Em andamento",
        ])

    filename = f"relatorio_a5_tecnologia_{period}_{now.strftime('%Y%m%d')}.csv"
    return output.getvalue(), filename

