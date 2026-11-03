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
    print("  SISTEMA ESTEIRA DE PRODUÇÃO - A5 TECNOLOGIA (TOLEDO PRIX)")
    print("=" * 68)
    print(f"  [RECEPÇÃO / PRISCILA] -> http://localhost:{PORT}/admin")
    print(f"  [PAINEL TV OFICINA]   -> http://{local_ip}:{PORT}/painel-tv")
    print(f"  [SCANNER MOBILE QR]   -> http://{local_ip}:{PORT}/scanner")
    print(f"  [BANCADA MOBILE QR]   -> http://{local_ip}:{PORT}/saida")
    print(f"  [CONSULTA BALCÃO]     -> http://{local_ip}:{PORT}/consulta")
    print(f"  [SALA DO SR. JACSON]  -> http://{local_ip}:{PORT}/diretoria")
    print(f"  [FOTOS RECEPÇÃO]      -> http://{local_ip}:{PORT}/recepcao-fotos")
    print(f"  [APRESENTAÇÃO EXEC.]  -> http://{local_ip}:{PORT}/apresentacao")
    print("=" * 68)

    socketio.run(app, host="0.0.0.0", port=PORT, debug=False, allow_unsafe_werkzeug=True)
