"""Eventos WebSocket (tempo real entre Recepção, celulares e TV)."""
from . import realtime
from .database import connect
from .extensions import socketio
from .services.cards import finish_timer


@socketio.on("call_tech_reception")
def handle_call_tech(data):
    """Priscila chama um técnico específico (ou todos) na recepção."""
    data = data or {}
    realtime.announce_call_tech(
        data.get("tech_name", "Técnico"),
        data.get("reason", "Comparecer na recepção"),
    )


@socketio.on("director_call_tech")
def handle_director_call(data):
    """Sr. Jacson chama membro da equipe com mensagem ou áudio."""
    data = data or {}
    realtime.announce_director_call(
        tech_name=data.get("tech_name", "Oficina"),
        message=data.get("message", ""),
        is_urgent=bool(data.get("is_urgent", False)),
        audio_base64=data.get("audio_base64"),
        sender=data.get("sender", "Sr. Jacson")
    )


@socketio.on("request_bench_support")
def handle_bench_support(data):
    """Técnico solicita apoio na bancada pelo celular."""
    data = data or {}
    realtime.announce_bench_support(data.get("tech_name", "Técnico"), data.get("os_number", ""))


@socketio.on("timer_finished_alert")
def handle_timer_finished(data):
    """
    Disparado pela TV quando o cronômetro de estufa/teste chega a zero.
    Se houver mais de uma TV aberta, só o primeiro aviso é anunciado.
    """
    data = data or {}
    os_number = data.get("os_number", "")
    card_row = finish_timer(os_number)
    if card_row is None:
        return

    realtime.announce_timer_done(
        os_number,
        data.get("client_name") or card_row["client_name"],
        data.get("label") or card_row["timer_label"] or "Estufa",
    )
    realtime.broadcast_board()


@socketio.on("panic_silence_tv")
def handle_panic_silence(data):
    """Botão de Pânico/Silenciador acionado pela Priscila para cortar o som da TV imediatamente."""
    muted = bool((data or {}).get("muted"))
    with connect() as conn:
        conn.execute("UPDATE settings SET value = ? WHERE key = 'tv_muted'", ("1" if muted else "0",))
    realtime.notify_tv_mute(muted)

