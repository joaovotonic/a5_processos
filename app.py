"""
Ponto de entrada do Sistema Kanban Local - A5 Tecnologia (Toledo Prix).

Execute:  python app.py

Todo o código fica no pacote `kanban/` (veja kanban/__init__.py para o mapa dos arquivos).
"""
import importlib.util
import os

# Monkey-patch do gevent precisa rodar ANTES de importar sockets/urllib/threading
_async_mode_env = os.environ.get("A5_SOCKETIO_ASYNC_MODE", "").strip().lower()
_proxy_or_tunnel_env = (
    os.environ.get("A5_TUNNEL_MODE", "").strip().lower() in {"1", "true", "yes"}
    or os.environ.get("A5_BEHIND_PROXY", "").strip().lower() in {"1", "true", "yes"}
)
if (_async_mode_env == "gevent" or (not _async_mode_env and _proxy_or_tunnel_env)):
    try:
        from gevent import monkey as _gevent_monkey
        _gevent_monkey.patch_all()
    except ImportError:
        pass

from kanban import create_app
from kanban.config import (
    BEHIND_PROXY,
    DB_PATH,
    DEFAULT_SECRET_KEY,
    PORT,
    PUBLIC_URL,
    SECRET_KEY,
    SOCKETIO_ASYNC_MODE,
    TUNNEL_MODE,
    TUNNEL_PUBLIC_HOSTNAME,
)
from kanban.extensions import socketio
from kanban.utils import get_local_ip


def validate_runtime_configuration():
    if not (TUNNEL_MODE or BEHIND_PROXY):
        return
    if TUNNEL_MODE and not TUNNEL_PUBLIC_HOSTNAME and not PUBLIC_URL:
        raise RuntimeError(
            "Defina A5_TUNNEL_PUBLIC_HOSTNAME ou A5_PUBLIC_URL com o endereço público configurado."
        )
    if not os.environ.get("A5_SECRET_KEY") or SECRET_KEY == DEFAULT_SECRET_KEY or len(SECRET_KEY) < 24:
        raise RuntimeError(
            "Defina uma A5_SECRET_KEY forte e persistente (>= 24 caracteres) para rodar atrás de proxy/túnel."
        )
    if SOCKETIO_ASYNC_MODE != "gevent":
        raise RuntimeError("O modo produção (Tunnel/Proxy) exige A5_SOCKETIO_ASYNC_MODE=gevent.")
    if TUNNEL_MODE and not os.path.isfile(DB_PATH):
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
