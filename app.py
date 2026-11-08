"""
Ponto de entrada do Sistema Kanban Local - A5 Tecnologia (Toledo Prix).

Execute:  python app.py

Todo o código fica no pacote `kanban/` (veja kanban/__init__.py para o mapa dos arquivos).
"""
import importlib.util
import os

from kanban import create_app
from kanban.config import (
    DB_PATH,
    PORT,
    SOCKETIO_ASYNC_MODE,
    TUNNEL_MODE,
    TUNNEL_PUBLIC_HOSTNAME,
)
from kanban.extensions import socketio
from kanban.utils import get_local_ip


def validate_runtime_configuration():
    if not TUNNEL_MODE:
        return
    if not TUNNEL_PUBLIC_HOSTNAME:
        raise RuntimeError(
            "Defina A5_TUNNEL_PUBLIC_HOSTNAME com o endereço Access configurado."
        )
    if not os.environ.get("A5_SECRET_KEY"):
        raise RuntimeError("Defina uma A5_SECRET_KEY persistente para o modo Tunnel.")
    if SOCKETIO_ASYNC_MODE != "gevent":
        raise RuntimeError("O modo Tunnel exige A5_SOCKETIO_ASYNC_MODE=gevent.")
    if not os.path.isfile(DB_PATH):
        raise RuntimeError(
            f"Banco de dados não encontrado em {DB_PATH}; "
            "o modo Tunnel não inicia com um banco vazio."
        )
    if (
        importlib.util.find_spec("gevent") is None
        or importlib.util.find_spec("geventwebsocket") is None
    ):
        raise RuntimeError(
            "Dependências de produção ausentes. Execute pip install -r requirements.txt."
        )

validate_runtime_configuration()
app = create_app()


if __name__ == "__main__":
    from kanban import database as db
    from kanban.services.pdf_watcher import start_pdf_watcher

    db.init_db()
    start_pdf_watcher()
    local_ip = get_local_ip()
    print("=" * 68)
    print("  ESTEIRA DE PRODUÇÃO AUTOMATIZADA - A5 TECNOLOGIA (TOLEDO PRIX)")
    print("=" * 68)
    if TUNNEL_MODE:
        print(f"  [ACESSO EXTERNO]      -> https://{TUNNEL_PUBLIC_HOSTNAME}/admin")
        print(f"  [ORIGEM DO TUNNEL]    -> http://127.0.0.1:{PORT}")
    print(f"  [RECEPÇÃO / KANBAN]   -> http://localhost:{PORT}/admin")
    print(f"  [PAINEL TV OFICINA]   -> http://{local_ip}:{PORT}/tv")
    print(f"  [SALA DO SR. JACSON]  -> http://{local_ip}:{PORT}/diretoria")
    print(f"  [EXEMPLO QR CODE OS]  -> http://{local_ip}:{PORT}/os/12345")
    print("=" * 68)

    server_options = {}
    if SOCKETIO_ASYNC_MODE == "threading":
        server_options["allow_unsafe_werkzeug"] = True
    socketio.run(
        app,
        host="0.0.0.0",
        port=PORT,
        debug=False,
        **server_options,
    )
