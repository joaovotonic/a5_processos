"""
Avisos em tempo real (WebSocket) para todas as telas: quadro atualizado e
anúncios sonoros/visuais da TV da oficina (os textos falados ficam todos aqui).
"""
import re

from .extensions import socketio
from .services.board import get_full_board
from .services.tts import get_neural_audio_base64, VOICE_JACSON, VOICE_RECEPTION, VOICE_OFICINA


def _emit_safe(event, *args, **kwargs):
    """Emite evento SocketIO somente se o servidor estiver inicializado."""
    if getattr(socketio, "server", None) is not None:
        try:
            socketio.emit(event, *args, **kwargs)
        except Exception:
            pass


def broadcast_board():
    """Envia o quadro completo para todas as telas e o retorna."""
    board = get_full_board()
    _emit_safe("board_updated", board)
    return board


def _announce(payload, voice=None):
    """
    Emite anúncio para a TV. Se o payload não tiver gravação de microfone (audio_base64),
    sintetiza fala neural humana de estúdio (Edge-TTS) para reprodução cristalina.
    """
    if not payload.get("audio_base64") and payload.get("tts_text"):
        chosen_voice = voice or (VOICE_JACSON if payload.get("type") == "director_call" else VOICE_RECEPTION)
        neural_audio = get_neural_audio_base64(payload["tts_text"], voice=chosen_voice)
        if neural_audio:
            payload["audio_base64"] = neural_audio
            payload["is_neural_audio"] = True

    _emit_safe("tv_announcement", payload)


def announce_arrival(card, stage, intro=""):
    os_num = str(card.get("os_number") or "").strip()
    stage_low = str(stage or "").strip().lower()
    if "aprovad" in stage_low:
        tts_text = f"O.S. {os_num} aprovada."
    elif "não autorizado" in stage_low or "nao autorizado" in stage_low or "fechamento" in stage_low:
        tts_text = f"O.S. {os_num} não autorizada."
    elif "orçamento" in stage_low or "orcamento" in stage_low:
        tts_text = f"O.S. {os_num} para orçamento."
    else:
        tts_text = f"O.S. {os_num} para {stage}."

    _announce({
        "type": "new_arrival",
        "os_number": os_num,
        "client_name": card.get("client_name") or "",
        "equipment_type": card.get("equipment_type") or "",
        "stage": stage,
        "is_urgent": bool(card.get("is_urgent") or card.get("is_warranty")),
        "tts_text": tts_text,
    })


def _clean_tech_speech_name(tech_name):
    """Extrai o nome limpo do técnico (sem prefixos repetidos) para locução breve."""
    raw = str(tech_name or "").strip()
    clean = re.sub(r"^(?:TEC\.?|TÉC\.?|SR\.?|ADM\.?)\s+", "", raw, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\s*\([^)]*\)", "", clean).strip()
    return clean.title() if clean else ""


def _finished_tts_text(os_number, tech_name):
    clean_tech = _clean_tech_speech_name(tech_name)
    if not clean_tech or clean_tech.lower() in ("oficina", "recepção", "recepcao", "sistema", "priscila"):
        return f"O.S. {os_number} finalizada."
    return f"O.S. {os_number} finalizada pelo técnico {clean_tech}."


def announce_finished_on_board(card, actor, finished_today):
    """O.S. arrastada para FINALIZADAS pela recepção."""
    os_num = str(card.get("os_number") or "").strip()
    tech_display = card.get("tech_name") or actor
    _announce({
        "type": "os_finished",
        "os_number": os_num,
        "client_name": card.get("client_name") or "",
        "tech_name": tech_display,
        "finished_today": finished_today,
        "tts_text": _finished_tts_text(os_num, card.get("tech_name")),
    })


def announce_finished_mobile(os_number, client_name, tech_name, inmetro_seal, finished_today):
    """O.S. finalizada pelo técnico no celular (QR Code)."""
    _announce({
        "type": "os_finished",
        "os_number": os_number,
        "client_name": client_name,
        "tech_name": tech_name,
        "inmetro_seal": inmetro_seal,
        "finished_today": finished_today,
        "tts_text": _finished_tts_text(os_number, tech_name),
    })


def _normalize_speech_name(tech_name):
    """Normaliza o nome do funcionário/técnico para pronúncia natural no sintetizador de voz (TTS)."""
    t_name = (tech_name or "Oficina").strip()
    if t_name.upper().startswith("TODOS"):
        return "toda a equipe da oficina"
    elif t_name.upper().startswith("SR. "):
        return "Senhor " + t_name[4:].title()
    elif t_name.upper().startswith("TEC. "):
        return "Técnico " + t_name[5:].title()
    elif t_name.upper().startswith("ADM. "):
        return t_name[5:].title()

    clean = re.sub(r"\s*\([^)]*\)", "", t_name).strip()
    return clean.title() if clean else t_name.title()


def announce_call_tech(tech_name, reason):
    speech_name = _normalize_speech_name(tech_name)
    clean_reason = (reason or "Comparecer na recepção").strip()
    if clean_reason.lower().startswith("comparecer"):
        tts_text = f"Atenção, {speech_name}. Por favor, {clean_reason.lower()}."
    else:
        tts_text = f"Atenção, {speech_name}. Por favor, comparecer na recepção: {clean_reason}."

    _announce({
        "type": "call_alert",
        "title": "CHAMADO NA RECEPÇÃO",
        "tech_name": tech_name or "Oficina",
        "reason": clean_reason,
        "is_urgent": True,
        "tts_text": tts_text,
    })


def announce_director_call(tech_name, message="", is_urgent=False, audio_base64=None, sender="Sr. Jacson"):
    """Chamado ou áudio enviado pelo Sr. Jacson para a TV da oficina."""
    title = "🚨 CHAMADO URGENTE DO SR. JACSON" if is_urgent else "📢 MENSAGEM DO SR. JACSON"
    clean_msg = (message or "").strip()
    speech_name = _normalize_speech_name(tech_name)

    if clean_msg:
        tts_text = f"Atenção, {speech_name}. Mensagem do Senhor Jacson: {clean_msg}."
    else:
        tts_text = f"Atenção, {speech_name}. Por favor, comparecer à sala do Senhor Jacson."

    is_voice_rec = bool(audio_base64)

    _announce({
        "type": "director_call",
        "title": title,
        "tech_name": tech_name or "Oficina",
        "reason": clean_msg or "Comparecer à Sala do Sr. Jacson",
        "is_urgent": bool(is_urgent),
        "tts_text": tts_text,
        "audio_base64": audio_base64,
        "is_voice_record": is_voice_rec,
        "sender": sender or "Sr. Jacson"
    }, voice=VOICE_JACSON)


def announce_bench_support(tech_name, os_number):
    _announce({
        "type": "support_alert",
        "title": "APOIO SOLICITADO NA BANCADA",
        "tech_name": tech_name,
        "os_number": os_number,
        "is_urgent": True,
        "tts_text": f"Atenção oficina. {tech_name} solicita apoio técnico na bancada para a O.S. {os_number}."
    })


def announce_timer_done(os_number, client_name, label):
    clean_label = (label or "Estufa").strip()
    ending = "Retirar equipamento da estufa." if "estufa" in clean_label.lower() else "Conferir equipamento na bancada."
    _announce({
        "type": "timer_done",
        "os_number": os_number,
        "client_name": client_name,
        "label": clean_label,
        "is_urgent": True,
        "tts_text": f"Atenção oficina! Tempo de {clean_label} concluído para a O.S. {os_number}, cliente {client_name}. {ending}"
    })


def notify_timer_started(os_number, client_name, minutes, end_time, label):
    _emit_safe("timer_started", {
        "os_number": os_number,
        "client_name": client_name,
        "minutes": minutes,
        "end_time": end_time,
        "label": label
    })


def notify_tv_mute(muted):
    _emit_safe("tv_mute_changed", {"muted": muted})


def notify_admin(payload):
    """Envia uma notificação em tempo real para o painel Admin da Recepção (Priscila)."""
    _emit_safe("admin_notification", payload)


def emit_tv_mini_alert(os_number, client_name, label_name, color="#EF4444"):
    """
    Envia notificação pequena e discreta para a TV da oficina quando uma O.S.
    em Orçamentos é marcada com URGÊNCIA ou EM GARANTIA.
    """
    clean_label = str(label_name or "").strip()
    payload = {
        "os_number": str(os_number or ""),
        "client_name": str(client_name or ""),
        "label_name": clean_label,
        "color": color,
        "is_urgent": "URG" in clean_label.upper(),
        "is_warranty": "GARANTIA" in clean_label.upper(),
        "message": f"O.S. {os_number} ({client_name}) marcada como {clean_label} na fila de Orçamentos!"
    }
    _emit_safe("tv_mini_alert", payload)


