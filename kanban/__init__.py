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
import gzip
import os

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from . import config
from .errors import ApiError
from .extensions import socketio


def create_app():
    app = Flask(__name__, template_folder=config.TEMPLATE_DIR, static_folder=None)
    behind_https_proxy = config.TUNNEL_MODE or config.BEHIND_PROXY
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        MAX_CONTENT_LENGTH=config.MAX_CONTENT_LENGTH,
        TEMPLATES_AUTO_RELOAD=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=behind_https_proxy,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if behind_https_proxy:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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

    @app.get("/assets/<path:filename>")
    def serve_frontend_assets(filename):
        assets_dir = os.path.join(config.FRONTEND_DIST_DIR, "assets")
        return send_from_directory(assets_dir, filename.replace("\\", "/"), max_age=31536000)

    @app.get("/favicon.svg")
    @app.get("/favicon.ico")
    def serve_frontend_favicon():
        svg_path = os.path.join(config.FRONTEND_DIST_DIR, "favicon.svg")
        if os.path.isfile(svg_path):
            return send_from_directory(config.FRONTEND_DIST_DIR, "favicon.svg")
        return send_from_directory(os.path.join(config.STATIC_DIR, "img"), "logo_a5.svg")

    @app.get("/healthz")
    def health_check():
        return jsonify({"service": "a5-kanban", "status": "ok"})

    from .routes import ALL_BLUEPRINTS
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify({"error": err.message}), err.status

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        csp = response.headers.get("Content-Security-Policy", "")
        if "frame-ancestors" not in csp.lower():
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    @app.after_request
    def compress_large_responses(response):
        # Comprime respostas JSON/texto grandes quando não houver proxy comprimindo (ex: Caddy com A5_DISABLE_PYTHON_GZIP=1)
        if config.DISABLE_PYTHON_GZIP:
            return response
        if (
            response.status_code < 200
            or response.status_code >= 300
            or response.direct_passthrough
            or "Content-Encoding" in response.headers
            or "gzip" not in (request.headers.get("Accept-Encoding") or "").lower()
        ):
            return response
        mimetype = (response.mimetype or "").lower()
        if not (mimetype.startswith("application/json") or mimetype.startswith("text/html") or mimetype.startswith("application/javascript") or mimetype.startswith("text/css")):
            return response
        data = response.get_data()
        if not data or len(data) < 1024:
            return response
        compressed = gzip.compress(data, compresslevel=5)
        response.set_data(compressed)
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(len(compressed))
        vary = response.headers.get("Vary")
        response.headers["Vary"] = f"{vary}, Accept-Encoding" if vary else "Accept-Encoding"
        return response

    from . import sockets  # noqa: F401  (registra os eventos WebSocket)
    socketio.init_app(
        app,
        cors_allowed_origins=None,
        async_mode=config.SOCKETIO_ASYNC_MODE,
    )
    return app
