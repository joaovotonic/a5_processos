"""
Ponto de entrada do Sistema Kanban Local - A5 Tecnologia (Toledo Prix).

Execute:  python app.py

Todo o código fica no pacote `kanban/` (veja kanban/__init__.py para o mapa dos arquivos).
"""
from kanban import create_app
from kanban import database as db
from kanban.config import PORT
from kanban.extensions import socketio
from kanban.services.pdf_watcher import start_pdf_watcher
from kanban.utils import get_local_ip

app = create_app()


if __name__ == "__main__":
    db.init_db()
    start_pdf_watcher()
    local_ip = get_local_ip()
    print("=" * 68)
    print("  ESTEIRA DE PRODUÇÃO AUTOMATIZADA - A5 TECNOLOGIA (TOLEDO PRIX)")
    print("=" * 68)
    print(f"  [RECEPÇÃO / KANBAN]   -> http://localhost:{PORT}/admin")
    print(f"  [PAINEL TV OFICINA]   -> http://{local_ip}:{PORT}/tv")
    print(f"  [SALA DO SR. JACSON]  -> http://{local_ip}:{PORT}/diretoria")
    print(f"  [EXEMPLO QR CODE OS]  -> http://{local_ip}:{PORT}/os/12345")
    print("=" * 68)

    socketio.run(app, host="0.0.0.0", port=PORT, debug=False, allow_unsafe_werkzeug=True)
