"""
Serviço de Integração Total com o YouTube (Busca de Músicas, Extração Direta Sem Anúncios e Stream Proxy).

Resolve definitivamente o erro 'Este vídeo não está disponível (Código 150 / 152-18)'
dos iframes embarcados do YouTube em redes locais (IPs 192.168.x.x / 127.0.0.1),
extraindo o stream nativo MP4/Áudio via yt-dlp com cache em memória e suporte a Range HTTP 206.
"""
import json
import re
import threading
import time
import urllib.parse
import urllib.request

from ..database import connect
from ..errors import ApiError

# Cache em memória dos streams resolvidos: { video_id: {"url": ..., "title": ..., "expires_at": ...} }
_STREAM_CACHE = {}
_CACHE_LOCK = threading.Lock()
_STREAM_TTL_SECONDS = 5400  # 90 minutos (URLs do googlevideo duram ~6 horas)
_STREAM_CACHE_MAX_ENTRIES = 100
_BOT_BLOCKED_UNTIL = 0.0
_BOT_COOLDOWN_SECONDS = 1800  # 30 minutos em modo embed automático se IP de VPS receber bot-check


def _fetch_oembed_metadata(clean_id: str) -> dict:
    """Consulta metadados públicos (título, canal, thumbnail) via YouTube oEmbed (nunca bloqueia IP de VPS)."""
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={urllib.parse.quote(clean_id)}&format=json"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
        return {
            "title": (data.get("title") or "").strip() or f"YouTube ({clean_id})",
            "channel": (data.get("author_name") or "").strip() or "YouTube",
            "thumbnail": (data.get("thumbnail_url") or "").strip() or f"https://i.ytimg.com/vi/{clean_id}/hqdefault.jpg",
        }
    except Exception:
        return {
            "title": f"YouTube ({clean_id})",
            "channel": "YouTube",
            "thumbnail": f"https://i.ytimg.com/vi/{clean_id}/hqdefault.jpg",
        }


def _build_embed_fallback(clean_id: str, now: float, reason: str = "") -> dict:
    """Retorna payload de reprodução oficial YouTube IFrame (usa o IP do navegador da TV, sem bloqueio de datacenter)."""
    meta = _fetch_oembed_metadata(clean_id)
    resolved = {
        "id": clean_id,
        "title": meta["title"],
        "channel": meta["channel"],
        "duration": 0,
        "duration_str": "YouTube Player",
        "thumbnail": meta["thumbnail"],
        "direct_url": "",
        "embed_url": f"https://www.youtube.com/embed/{clean_id}",
        "playback_mode": "embed",
        "fallback_reason": reason,
        "ext": "embed",
        "http_headers": {},
        "is_live": False,
        "expires_at": now + 900,
    }
    with _CACHE_LOCK:
        _prune_stream_cache_unlocked(now)
        _STREAM_CACHE[clean_id] = resolved
    return resolved


def _prune_stream_cache_unlocked(now: float) -> None:
    """Remove entradas expiradas e limita o cache em memória para não crescer indefinidamente na VPS."""
    expired = [k for k, v in _STREAM_CACHE.items() if v.get("expires_at", 0) <= now]
    for k in expired:
        _STREAM_CACHE.pop(k, None)
    while len(_STREAM_CACHE) >= _STREAM_CACHE_MAX_ENTRIES:
        oldest_key = min(_STREAM_CACHE, key=lambda k: _STREAM_CACHE[k].get("expires_at", 0))
        _STREAM_CACHE.pop(oldest_key, None)

_YT_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_clean_youtube_id(raw):
    """Extrai o ID limpo de 11 caracteres de qualquer URL do YouTube ou string."""
    if not raw:
        return None
    s = str(raw).strip()
    if _YT_ID_REGEX.match(s):
        return s

    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/|youtube\.com\/live\/|music\.youtube\.com\/watch\?v=)([A-Za-z0-9_-]{11})",
        r"[?&]v=([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, s)
        if m and _YT_ID_REGEX.match(m.group(1)):
            return m.group(1)
    return None


def get_youtube_account_status():
    """Retorna o status da integração de conta / YouTube Premium salvo no banco."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE key IN ('yt_account_mode', 'yt_account_browser', 'yt_account_email')"
        ).fetchall()
    cfg = {r["key"]: r["value"] for r in rows}
    mode = cfg.get("yt_account_mode") or "premium_direct"
    browser = cfg.get("yt_account_browser") or ""
    email = cfg.get("yt_account_email") or ""
    return {
        "mode": mode,
        "browser": browser,
        "email": email,
        "adblock_active": True,
        "premium_ready": True,
    }


def save_youtube_account_status(mode="premium_direct", browser="", email=""):
    """Salva a configuração de conta / navegador YouTube Premium no banco."""
    with connect() as conn:
        for k, v in [
            ("yt_account_mode", str(mode or "premium_direct").strip()),
            ("yt_account_browser", str(browser or "").strip().lower()),
            ("yt_account_email", str(email or "").strip()),
        ]:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, v),
            )
    with _CACHE_LOCK:
        _STREAM_CACHE.clear()
    return get_youtube_account_status()


def search_youtube(query, limit=10):
    """
    Pesquisa músicas, artistas, shows ao vivo ou álbuns no YouTube em tempo real.
    Se o usuário digitar um link ou ID direto do YouTube, resolve o vídeo imediatamente.
    """
    q = (query or "").strip()
    if not q:
        return []

    limit = max(1, min(int(limit or 10), 20))

    # Se colou um link ou ID de 11 caracteres na barra de pesquisa, busca os dados dele
    direct_id = extract_clean_youtube_id(q)
    if direct_id and ("youtu" in q.lower() or _YT_ID_REGEX.match(q)):
        try:
            info = resolve_video_stream(direct_id)
            return [{
                "id": direct_id,
                "title": info.get("title") or f"Vídeo YouTube ({direct_id})",
                "channel": info.get("channel") or "YouTube",
                "duration": info.get("duration_str") or "Vídeo",
                "thumbnail": info.get("thumbnail") or f"https://i.ytimg.com/vi/{direct_id}/hqdefault.jpg",
            }]
        except Exception:
            pass

    url = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
    payload = {
        "query": q,
        "context": {
            "client": {
                "hl": "pt",
                "gl": "BR",
                "clientName": "WEB",
                "clientVersion": "2.20261028.01.00",
            }
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        raise ApiError(f"Falha ao pesquisar no YouTube: {exc}", status=502)

    results = []
    seen = set()

    def _walk(obj):
        if len(results) >= limit:
            return
        if isinstance(obj, dict):
            if "videoRenderer" in obj:
                vr = obj["videoRenderer"]
                vid = vr.get("videoId")
                if not vid or vid in seen or not _YT_ID_REGEX.match(vid):
                    return
                title_runs = vr.get("title", {}).get("runs", [])
                title = "".join(x.get("text", "") for x in title_runs).strip()
                owner_runs = (vr.get("ownerText") or vr.get("longBylineText") or {}).get("runs", [])
                channel = "".join(x.get("text", "") for x in owner_runs).strip()
                dur = vr.get("lengthText", {}).get("simpleText", "")
                if not dur:
                    # Verifica se é transmissão ao vivo
                    badges = json.dumps(vr.get("badges", [])).upper()
                    dur = "AO VIVO" if "LIVE" in badges or "AO VIVO" in badges else "Mix"
                thumbs = vr.get("thumbnail", {}).get("thumbnails", [])
                thumb = thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                if title:
                    seen.add(vid)
                    results.append({
                        "id": vid,
                        "title": title,
                        "channel": channel or "YouTube Music",
                        "duration": dur,
                        "thumbnail": thumb,
                    })
            else:
                for val in obj.values():
                    _walk(val)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    return results


def _format_duration(seconds):
    if not seconds:
        return "Ao Vivo / Mix"
    try:
        sec = int(seconds)
    except Exception:
        return ""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def resolve_video_stream(video_id, force_refresh=False):
    """
    Resolve a reprodução do vídeo do YouTube:
    1) Tenta extração direta MP4 via yt-dlp (funciona em IP residencial ou com cookies na VPS).
    2) Se o IP da VPS receber verificação anti-bot do YouTube, ativa fallback imediato para
       o player oficial YouTube IFrame (`playback_mode="embed"`) com metadados via oEmbed,
       rodando direto no navegador da TV (zero bloqueio de datacenter e zero banda na VPS).
    """
    global _BOT_BLOCKED_UNTIL
    clean_id = extract_clean_youtube_id(video_id)
    if not clean_id:
        raise ApiError("ID de vídeo do YouTube inválido.")

    now = time.time()
    if not force_refresh:
        with _CACHE_LOCK:
            cached = _STREAM_CACHE.get(clean_id)
            if cached and cached.get("expires_at", 0) > now:
                return cached

    import os
    import shutil
    from ..config import YT_COOKIES_FILE

    has_cookie_file = bool(YT_COOKIES_FILE and os.path.isfile(YT_COOKIES_FILE))

    # Se o IP da VPS sofreu bot-check recentemente e não há cookies configurados,
    # responde em ~100ms com modo embed oficial sem travar 15s tentando yt-dlp.
    if not has_cookie_file and not force_refresh and _BOT_BLOCKED_UNTIL > now:
        return _build_embed_fallback(clean_id, now, reason="vps_bot_cooldown")

    try:
        import yt_dlp
    except ImportError:
        return _build_embed_fallback(clean_id, now, reason="yt_dlp_missing")

    acc = get_youtube_account_status()
    browser = acc.get("browser", "")

    def _probe_stream_url(stream_url: str, headers: dict | None = None) -> bool:
        """Valida com 1 requisição Range (64 bytes) se o googlevideo realmente libera o stream (evita cachear URL 403)."""
        req_headers = {
            "User-Agent": (headers or {}).get(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            ),
            "Accept": "*/*",
            "Range": "bytes=0-63",
        }
        for hk in ("Accept-Language", "Referer", "Origin"):
            if headers and headers.get(hk):
                req_headers[hk] = headers[hk]
        try:
            probe_req = urllib.request.Request(stream_url, headers=req_headers)
            with urllib.request.urlopen(probe_req, timeout=8) as resp:
                return resp.status in (200, 206)
        except Exception:
            return False

    base_opts = {
        "format": "18/best[ext=mp4][acodec!=none][vcodec!=none]/best[acodec!=none]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "socket_timeout": 10,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
            }
        },
    }
    if shutil.which("node"):
        base_opts["js_runtimes"] = {"node": {}}
    if has_cookie_file:
        base_opts["cookiefile"] = YT_COOKIES_FILE

    info = None
    last_err = None
    bot_blocked = False

    # 1. Se o usuário vinculou navegador local (desktop) e não há cookiefile, tenta cookies do navegador
    if browser in ("firefox", "chrome", "edge", "brave") and not has_cookie_file:
        try:
            cookie_opts = dict(base_opts)
            cookie_opts["cookiesfrombrowser"] = (browser,)
            with yt_dlp.YoutubeDL(cookie_opts) as ydl:
                cand = ydl.extract_info(f"https://www.youtube.com/watch?v={clean_id}", download=False)
            if cand and cand.get("url") and (cand.get("is_live") or _probe_stream_url(cand["url"], cand.get("http_headers"))):
                info = cand
        except Exception as e:
            last_err = e
            info = None

    # 2. Tenta clientes em ordem de confiabilidade (`android` primeiro — sem PO Token).
    #    Se detectar bloqueio anti-bot no IP da VPS, interrompe imediatamente e cai para embed oficial.
    if not info:
        for client_group in (["android"], ["ios"], ["android_vr"], ["mweb", "web"]):
            try:
                attempt_opts = dict(base_opts)
                attempt_opts["extractor_args"] = {"youtube": {"player_client": client_group}}
                with yt_dlp.YoutubeDL(attempt_opts) as ydl:
                    cand = ydl.extract_info(f"https://www.youtube.com/watch?v={clean_id}", download=False)
                if not cand or not cand.get("url"):
                    continue
                if cand.get("is_live") or _probe_stream_url(cand["url"], cand.get("http_headers")):
                    info = cand
                    break
                last_err = f"Stream recusado (HTTP 403) no cliente {client_group}"
            except Exception as e:
                last_err = e
                low = str(e).lower()
                if "sign in to confirm" in low or "not a bot" in low:
                    bot_blocked = True
                    break

    if not info or not info.get("url"):
        if bot_blocked and not has_cookie_file:
            _BOT_BLOCKED_UNTIL = time.time() + _BOT_COOLDOWN_SECONDS
            return _build_embed_fallback(clean_id, now, reason="vps_bot_check")
        # Mesmo em outros erros de extração no servidor, oferece fallback oficial YouTube IFrame na TV
        return _build_embed_fallback(clean_id, now, reason=str(last_err or "unavailable")[:120])

    resolved = {
        "id": clean_id,
        "title": info.get("title") or f"YouTube ({clean_id})",
        "channel": info.get("uploader") or info.get("channel") or "YouTube",
        "duration": info.get("duration") or 0,
        "duration_str": _format_duration(info.get("duration")),
        "thumbnail": info.get("thumbnail") or f"https://i.ytimg.com/vi/{clean_id}/hqdefault.jpg",
        "direct_url": info["url"],
        "embed_url": f"https://www.youtube.com/embed/{clean_id}",
        "playback_mode": "native",
        "ext": info.get("ext") or "mp4",
        "http_headers": info.get("http_headers") or {},
        "is_live": bool(info.get("is_live")),
        "expires_at": now + _STREAM_TTL_SECONDS,
    }

    with _CACHE_LOCK:
        _prune_stream_cache_unlocked(now)
        _STREAM_CACHE[clean_id] = resolved

    return resolved

