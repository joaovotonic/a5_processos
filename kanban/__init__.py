"""
Sistema Kanban Local - A5 Tecnologia (Toledo Prix).

Organização do pacote:
    config.py       caminhos, porta e chaves
    database.py     conexão SQLite, esquema e dados iniciais
    backup.py       backup diário automático
    rules.py        regras das colunas (orçamento, aprovada, finalizada, técnico)
    realtime.py     avisos WebSocket e textos falados na TV
    sockets.py      eventos WebSocket recebidos das telas
    services/       regras de negócio e SQL (cartões, listas, quadro, relatórios)
    routes/         rotas HTTP (páginas e API), sem SQL
"""
import os

from flask import Flask, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from . import config
from .errors import ApiError
from .extensions import socketio


def create_app():
    app = Flask(__name__, template_folder=config.TEMPLATE_DIR, static_folder=None)
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        MAX_CONTENT_LENGTH=config.MAX_CONTENT_LENGTH,
        TEMPLATES_AUTO_RELOAD=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=config.TUNNEL_MODE,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config.TUNNEL_MODE:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    @app.get("/static/<path:filename>", endpoint="static")
    def serve_static_file(filename):
        normalized_filename = filename.replace("\\", "/")
        if normalized_filename.startswith("uploads/"):
            return send_from_directory(
                config.UPLOAD_FOLDER,
                normalized_filename[len("uploads/"):],
            )
        return send_from_directory(config.STATIC_DIR, normalized_filename)

    @app.get("/healthz")
    def health_check():
        return jsonify({"service": "a5-kanban", "status": "ok"})

    from .routes import ALL_BLUEPRINTS
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify({"error": err.message}), err.status

    from . import sockets  # noqa: F401  (registra os eventos WebSocket)
    socketio.init_app(
        app,
        cors_allowed_origins=None,
        async_mode=config.SOCKETIO_ASYNC_MODE,
    )
    return app
