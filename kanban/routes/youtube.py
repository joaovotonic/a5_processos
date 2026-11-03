"""Rotas HTTP de Integração com o YouTube (Pesquisa de Músicas, Stream Nativo Sem Anúncios e Conta Premium)."""
import urllib.error
import urllib.request
from flask import Blueprint, Response, jsonify, request, stream_with_context

from ..errors import ApiError
from ..services import youtube as yt_service
from ..utils import json_body

bp = Blueprint("api_youtube", __name__, url_prefix="/api/youtube")


@bp.route("/search", methods=["GET"])
def api_youtube_search():
    """Pesquisa músicas, artistas, shows ao vivo ou álbuns no YouTube."""
    q = (request.args.get("q") or "").strip()
    limit = request.args.get("limit", 8)
    if not q:
        return jsonify({"results": []})
    results = yt_service.search_youtube(q, limit=limit)
    return jsonify({"results": results})


@bp.route("/info/<video_id>", methods=["GET"])
def api_youtube_info(video_id):
    """Retorna metadados da música/vídeo e prepara o stream em cache."""
    force = request.args.get("refresh") == "1"
    info = yt_service.resolve_video_stream(video_id, force_refresh=force)
    clean_id = info["id"]
    return jsonify({
        "success": True,
        "video": {
            "id": clean_id,
            "title": info["title"],
            "channel": info["channel"],
            "duration": info["duration"],
            "duration_str": info["duration_str"],
            "thumbnail": info["thumbnail"],
            "is_live": info["is_live"],
            "stream_url": f"/api/youtube/stream/{clean_id}",
            "direct_url": info["direct_url"],
        },
        "account": yt_service.get_youtube_account_status(),
    })


@bp.route("/stream/<video_id>", methods=["GET"])
def api_youtube_stream(video_id):
    """
    Proxy de streaming de vídeo/áudio MP4 com suporte a HTTP Range (206 Partial Content).
    Permite tocar qualquer música ou show no player nativo da TV sem bloqueio de embed e sem anúncios.
    """
    info = yt_service.resolve_video_stream(video_id)
    range_header = request.headers.get("Range")

    def _open_upstream(stream_info):
        headers = {
            "User-Agent": stream_info.get("http_headers", {}).get(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            ),
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        if range_header:
            headers["Range"] = range_header
        req = urllib.request.Request(stream_info["direct_url"], headers=headers)
        return urllib.request.urlopen(req, timeout=15)

    try:
        upstream = _open_upstream(info)
    except urllib.error.HTTPError as err:
        if err.code in (401, 403, 410):
            info = yt_service.resolve_video_stream(video_id, force_refresh=True)
            upstream = _open_upstream(info)
        else:
            raise ApiError(f"Erro ao abrir stream do YouTube (HTTP {err.code}).", status=502)
    except Exception as exc:
        raise ApiError(f"Falha de conexão com o stream do YouTube: {exc}", status=502)

    status_code = upstream.status
    resp_headers = {
        "Content-Type": upstream.headers.get("Content-Type", "video/mp4"),
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache",
    }
    for hdr in ("Content-Length", "Content-Range"):
        val = upstream.headers.get(hdr)
        if val:
            resp_headers[hdr] = val

    def _generate():
        try:
            while True:
                chunk = upstream.read(65536)
                if not chunk:
                    break
                yield chunk
        except Exception:
            pass
        finally:
            try:
                upstream.close()
            except Exception:
                pass

    return Response(stream_with_context(_generate()), status=status_code, headers=resp_headers)


@bp.route("/account", methods=["GET", "POST"])
def api_youtube_account():
    """Consulta ou vincula a sessão do YouTube Premium / Navegador."""
    if request.method == "GET":
        return jsonify({"success": True, "account": yt_service.get_youtube_account_status()})

    data = json_body()
    mode = data.get("mode", "premium_direct")
    browser = data.get("browser", "")
    email = data.get("email", "")
    acc = yt_service.save_youtube_account_status(mode=mode, browser=browser, email=email)
    return jsonify({"success": True, "account": acc})

