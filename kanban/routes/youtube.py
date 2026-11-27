"""Rotas HTTP de Integração com o YouTube (Pesquisa de Músicas, Stream Nativo Sem Anúncios e Conta Premium)."""
import urllib.error
import urllib.parse
import urllib.request
from flask import Blueprint, Response, jsonify, request, stream_with_context

from ..auth import require_api_roles
from ..errors import ApiError
from ..services import youtube as yt_service
from ..utils import json_body

bp = Blueprint("api_youtube", __name__, url_prefix="/api/youtube")

_ALLOWED_YT_BROWSERS = {"", "firefox", "chrome", "edge", "brave"}
_ALLOWED_YT_MODES = {"premium_direct", "browser_cookies"}


def _enforce_same_origin_proxy():
    """Bloqueia hotlink externo (cross-site) para evitar uso da VPS como proxy aberto de YouTube."""
    sec_fetch_site = (request.headers.get("Sec-Fetch-Site") or "").strip().lower()
    if sec_fetch_site == "cross-site":
        raise ApiError("Acesso externo (cross-site) bloqueado.", status=403)

    referer = (request.headers.get("Referer") or "").strip()
    if referer:
        ref_host = (urllib.parse.urlparse(referer).netloc or "").lower()
        req_host = (request.headers.get("X-Forwarded-Host") or request.host or "").split(",")[0].strip().lower()
        if ref_host and req_host and ref_host != req_host:
            raise ApiError("Origem não autorizada para streaming.", status=403)


@bp.route("/search", methods=["GET"])
def api_youtube_search():
    """Pesquisa músicas, artistas, shows ao vivo ou álbuns no YouTube."""
    _enforce_same_origin_proxy()
    q = (request.args.get("q") or "").strip()
    limit = request.args.get("limit", 8)
    if not q:
        return jsonify({"results": []})
    results = yt_service.search_youtube(q, limit=limit)
    return jsonify({"results": results})


@bp.route("/info/<video_id>", methods=["GET"])
def api_youtube_info(video_id):
    """Retorna metadados da música/vídeo e prepara o stream em cache."""
    _enforce_same_origin_proxy()
    force = request.args.get("refresh") == "1"
    info = yt_service.resolve_video_stream(video_id, force_refresh=force)
    clean_id = info["id"]
    playback_mode = info.get("playback_mode") or ("native" if info.get("direct_url") else "embed")
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
            "playback_mode": playback_mode,
            "stream_url": f"/api/youtube/stream/{clean_id}" if playback_mode == "native" else "",
            "direct_url": info.get("direct_url") or "",
            "embed_url": info.get("embed_url") or f"https://www.youtube.com/embed/{clean_id}",
        },
        "account": yt_service.get_youtube_account_status(),
    })


@bp.route("/stream/<video_id>", methods=["GET"])
def api_youtube_stream(video_id):
    """
    Proxy de streaming de vídeo/áudio MP4 com suporte a HTTP Range (206 Partial Content).
    Permite tocar qualquer música ou show no player nativo da TV sem bloqueio de embed e sem anúncios.
    """
    _enforce_same_origin_proxy()
    info = yt_service.resolve_video_stream(video_id)
    if not info.get("direct_url"):
        raise ApiError("Stream direto indisponível no IP da VPS (use o player embed oficial).", status=502)
    range_header = request.headers.get("Range")

    def _open_upstream(stream_info):
        upstream_hdrs = stream_info.get("http_headers") or {}
        headers = {
            "User-Agent": upstream_hdrs.get(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            ),
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        for hk in ("Accept-Language", "Referer", "Origin"):
            if upstream_hdrs.get(hk):
                headers[hk] = upstream_hdrs[hk]
        if range_header:
            headers["Range"] = range_header
        req = urllib.request.Request(stream_info["direct_url"], headers=headers)
        return urllib.request.urlopen(req, timeout=15)

    try:
        upstream = _open_upstream(info)
    except urllib.error.HTTPError as err:
        if err.code in (401, 403, 410):
            try:
                info = yt_service.resolve_video_stream(video_id, force_refresh=True)
                upstream = _open_upstream(info)
            except urllib.error.HTTPError as retry_err:
                raise ApiError(f"Erro ao abrir stream do YouTube (HTTP {retry_err.code}).", status=502)
            except Exception as retry_exc:
                raise ApiError(f"Falha ao reabrir stream do YouTube: {retry_exc}", status=502)
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


@bp.route("/account", methods=["GET"])
def api_youtube_account_get():
    """Consulta o status da integração do YouTube."""
    return jsonify({"success": True, "account": yt_service.get_youtube_account_status()})


@bp.route("/account", methods=["POST"])
@require_api_roles("admin_recepcao", "diretoria", "master")
def api_youtube_account_post():
    """Vincula a sessão do YouTube Premium / Navegador (somente equipe autenticada)."""
    data = json_body()
    mode = str(data.get("mode") or "premium_direct").strip().lower()
    browser = str(data.get("browser") or "").strip().lower()
    email = str(data.get("email") or "").strip()[:120]
    if mode not in _ALLOWED_YT_MODES:
        raise ApiError("Modo de conta YouTube inválido.", status=400)
    if browser not in _ALLOWED_YT_BROWSERS:
        raise ApiError("Navegador não suportado.", status=400)
    acc = yt_service.save_youtube_account_status(mode=mode, browser=browser, email=email)
    return jsonify({"success": True, "account": acc})

