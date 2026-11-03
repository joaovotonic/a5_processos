"""API de relatórios da gerência: métricas, exportação CSV e backup."""
from flask import Blueprint, Response, jsonify, request, send_file

from ..backup import perform_daily_backup
from ..services.board import get_analytics_summary
from ..services.reports import build_os_csv

bp = Blueprint("api_reports", __name__, url_prefix="/api")


@bp.route("/analytics", methods=["GET"])
def analytics():
    """Dados para o painel /gerencia."""
    return jsonify(get_analytics_summary())


@bp.route("/export/csv", methods=["GET"])
def export_csv():
    """Exporta relatório completo de O.S. para Excel (CSV UTF-8 com BOM)."""
    content, filename = build_os_csv(request.args.get("period", "all"))  # day, month, year, all
    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@bp.route("/backup/download", methods=["GET"])
def download_backup():
    """Gera um backup imediato e faz download do arquivo .db."""
    return send_file(perform_daily_backup(force=True), as_attachment=True)


@bp.route("/diretoria/report", methods=["GET"])
def api_diretoria_report():
    """Relatório executivo dinâmico de produtividade e tempos da esteira para o Sr. Jacson."""
    from ..services.diretoria import get_director_productivity_report
    period = request.args.get("period", "today")
    tech_filter = request.args.get("tech", "").strip()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    report = get_director_productivity_report(
        period=period,
        tech_filter=tech_filter,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify(report)

