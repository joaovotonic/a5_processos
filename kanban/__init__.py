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

from flask import Flask, jsonify

from . import config
from .errors import ApiError
from .extensions import socketio


def create_app():
    app = Flask(__name__, template_folder=config.TEMPLATE_DIR,
                static_folder=config.STATIC_DIR, static_url_path="/static")
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    from .routes import ALL_BLUEPRINTS
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify({"error": err.message}), err.status

    from . import sockets  # noqa: F401  (registra os eventos WebSocket)
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")
    return app
