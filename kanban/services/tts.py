"""
Serviço de Síntese de Voz Neural (Edge-TTS / Microsoft Azure Neural) para a TV.
Gera locuções humanas em Português do Brasil com entonação e respiração naturais,
utilizando cache em disco para latência de milissegundos e fallback seguro.
"""
import asyncio
import base64
import concurrent.futures
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "database", "tts_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Vozes Neurais em Português do Brasil
VOICE_JACSON = "pt-BR-AntonioNeural"       # Voz masculina madura e executiva
VOICE_RECEPTION = "pt-BR-FranciscaNeural"   # Voz feminina natural e amigável
VOICE_OFICINA = "pt-BR-AntonioNeural"       # Alertas operacionais gerais


def get_neural_audio_base64(text: str, voice: str = VOICE_JACSON) -> str | None:
    """
    Sintetiza texto em fala neural (MP3) e retorna como data URI Base64.
    Retorna None em caso de falha ou indisponibilidade de rede (ativando o fallback do navegador).
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return None

    try:
        h = hashlib.md5(f"{voice}:{clean_text}".encode("utf-8")).hexdigest()
        cache_path = os.path.join(CACHE_DIR, f"{h}.mp3")

        if not os.path.exists(cache_path):
            import edge_tts

            async def _synthesize():
                comm = edge_tts.Communicate(clean_text, voice)
                await comm.save(cache_path)

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        pool.submit(lambda: asyncio.run(_synthesize())).result(timeout=6.0)
                else:
                    loop.run_until_complete(_synthesize())
            except RuntimeError:
                asyncio.run(_synthesize())

        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            with open(cache_path, "rb") as f:
                raw = f.read()
            if raw:
                b64 = base64.b64encode(raw).decode("ascii")
                return f"data:audio/mp3;base64,{b64}"

    except Exception as exc:
        logger.warning("Falha na síntese neural Edge-TTS para '%s': %s", clean_text[:40], exc)

    return None

