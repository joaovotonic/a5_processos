"""Integração bidirecional Esteira A5 <-> Chatwoot / WhatsApp."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import quote

from flask import Blueprint, jsonify, make_response, render_template, request

from .. import config
from ..auth import get_current_user, require_api_roles
from ..database import connect
from ..errors import ApiError
from ..services.board import enrich_card
from ..utils import resolve_public_base_url

bp = Blueprint("integrations", __name__)


def _active_integration_token() -> str:
    return (
        os.environ.get("A5_INTEGRATION_TOKEN", config.INTEGRATION_TOKEN).strip()
        or os.environ.get("A5_PDF_INGEST_TOKEN", config.PDF_INGEST_TOKEN).strip()
    )


def compute_chatwoot_dashboard_token() -> str:
    """Token determinístico derivado via HMAC para o Dashboard App embutido no Chatwoot."""
    base_secret = _active_integration_token() or os.environ.get("A5_SECRET_KEY", config.SECRET_KEY)
    return hmac.new(
        base_secret.encode("utf-8"),
        b"a5-chatwoot-dashboard-app-v1",
        hashlib.sha256,
    ).hexdigest()[:32]


def _is_authorized_integration_read() -> bool:
    user = get_current_user()
    if user and user.get("role") in ("admin_recepcao", "diretoria", "master"):
        return True

    expected = _active_integration_token()
    provided_hdr = (
        request.headers.get("X-A5-Integration-Token")
        or request.headers.get("X-A5-Ingest-Token")
        or ""
    ).strip()
    if expected and provided_hdr and hmac.compare_digest(provided_hdr, expected):
        return True

    dash_expected = compute_chatwoot_dashboard_token()
    dash_provided = (
        request.headers.get("X-A5-Dashboard-Token")
        or request.args.get("token")
        or ""
    ).strip()
    if dash_expected and dash_provided and hmac.compare_digest(dash_provided, dash_expected):
        return True

    return False


def _only_digits(value: str | None) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _describe_stage(card: dict) -> tuple[str, str, str]:
    """Retorna (stage_label, badge_tone, suggested_whatsapp_reply) conforme a etapa atual da O.S."""
    os_num = card.get("os_number") or ""
    eq = " ".join(
        p for p in [card.get("equipment_type") or "", card.get("equipment_model") or ""] if p
    ).strip() or "seu equipamento"
    phase = (card.get("pipeline_phase") or "").upper()
    ltitle = (card.get("list_title") or "").upper()
    tech = (card.get("finisher_tech") or card.get("evaluator_tech") or card.get("tech_name") or "").strip()
    seal = (card.get("inmetro_seal") or "").strip()
    labels_upper = {str(lb.get("name") or "").strip().upper() for lb in (card.get("labels") or []) if isinstance(lb, dict)}

    if phase in ("PRONTAS", "FINALIZADAS") or card.get("finished_at") or "FINALIZADA" in ltitle or "PRONTA" in ltitle:
        seal_txt = f" (Lacre IPEM: {seal})" if seal else ""
        return (
            "Pronta para retirada",
            "emerald",
            (
                f"Olá! Aqui é da A5 Tecnologia. Informamos que o equipamento referente à O.S. {os_num} "
                f"({eq}){seal_txt} já está finalizado e pronto para retirada em nossa oficina!"
            ),
        )
    if phase == "NAO_AUTORIZADO" or "NÃO AUTORIZAD" in ltitle or "NAO AUTORIZAD" in ltitle:
        return (
            "Orçamento não autorizado",
            "rose",
            (
                f"Olá! Referente à O.S. {os_num} ({eq}), consta como orçamento não autorizado. "
                f"O equipamento está disponível para retirada ou caso deseje reavaliar o orçamento, estamos à disposição."
            ),
        )
    if phase == "BALANCAS_PENDENTES" or "PENDENTE" in ltitle or "FALTA PEÇA" in labels_upper:
        return (
            "Aguardando peça",
            "orange",
            (
                f"Olá! Sobre a O.S. {os_num} ({eq}), o equipamento encontra-se aprovado e aguardando "
                f"a chegada de peça para conclusão do reparo. Assim que finalizar, avisaremos por aqui!"
            ),
        )
    if phase == "EM_MANUTENCAO":
        who = f" com {tech}" if tech else ""
        return (
            f"Em manutenção{who}",
            "blue",
            (
                f"Olá! Sobre a O.S. {os_num} ({eq}), o equipamento já está em manutenção em nossa bancada"
                f" e passando pelos testes técnicos. Assim que ficar pronto para retirada, avisamos por aqui!"
            ),
        )
    if phase == "APROVADOS" or "APROVAD" in ltitle:
        return (
            "Aprovado (aguardando bancada)",
            "teal",
            (
                f"Olá! Sobre a O.S. {os_num} ({eq}), seu orçamento já está aprovado e o equipamento está "
                f"na fila prioritária para manutenção na bancada. Assim que concluir, avisaremos!"
            ),
        )
    if phase == "ORCAMENTOS_ENVIADOS" or "ENVIAD" in ltitle:
        return (
            "Orçamento enviado (aguardando aprovação)",
            "indigo",
            (
                f"Olá! Sobre a O.S. {os_num} ({eq}), o orçamento já foi concluído e enviado. "
                f"Ficamos no aguardo da sua aprovação para darmos início ao serviço!"
            ),
        )
    if phase == "ORCAMENTOS_FEITOS" or "FEITO" in ltitle:
        return (
            "Orçamento concluído (pronto para envio)",
            "cyan",
            (
                f"Olá! O diagnóstico da O.S. {os_num} ({eq}) já foi finalizado pela nossa equipe técnica "
                f"e o orçamento está sendo encaminhado para sua análise."
            ),
        )
    if phase == "EM_ORCAMENTO" or (card.get("list_is_tech") and not card.get("finished_at")):
        who = f" com {tech}" if tech else ""
        return (
            f"Em diagnóstico / orçamento{who}",
            "sky",
            (
                f"Olá! Sobre a O.S. {os_num} ({eq}), o equipamento já está em análise técnica na bancada "
                f"para elaboração do orçamento. Em breve retornamos com os detalhes!"
            ),
        )
    return (
        "Na fila de orçamento",
        "amber",
        (
            f"Olá! Confirmamos que a O.S. {os_num} ({eq}) deu entrada em nossa oficina e está na fila "
            f"de avaliação técnica para orçamento. Assim que concluirmos o diagnóstico, avisamos por aqui!"
        ),
    )


def _format_card_for_integration(row_dict: dict, base_url: str) -> dict:
    card = enrich_card(row_dict)
    stage_label, badge_tone, suggested_reply = _describe_stage(card)
    safe_os = quote(str(card.get("os_number") or ""), safe="")
    tech = (card.get("finisher_tech") or card.get("evaluator_tech") or card.get("tech_name") or "").strip()
    is_finished = bool(
        card.get("finished_at")
        or (card.get("pipeline_phase") or "").upper() in ("PRONTAS", "FINALIZADAS")
        or "FINALIZADA" in (card.get("list_title") or "").upper()
    )
    photos = (
        (card.get("exit_photos") or [])[:2]
        + (card.get("entry_photos") or [])[:2]
        + (card.get("quote_photos") or [])[:2]
    )[:4]
    return {
        "id": card.get("id"),
        "os_number": card.get("os_number") or "",
        "client_name": card.get("client_name") or "",
        "trade_name": card.get("trade_name") or "",
        "phone": card.get("phone") or "",
        "cnpj_cpf": card.get("cnpj_cpf") or "",
        "equipment_type": card.get("equipment_type") or "",
        "equipment_model": card.get("equipment_model") or "",
        "serial_number": card.get("serial_number") or "",
        "reported_defect": card.get("reported_defect") or "",
        "list_title": card.get("list_title") or "",
        "pipeline_phase": card.get("pipeline_phase") or "",
        "stage_label": stage_label,
        "badge_tone": badge_tone,
        "tech_name": tech,
        "shelf_location": card.get("shelf_location") or "",
        "inmetro_seal": card.get("inmetro_seal") or "",
        "created_at": card.get("created_at") or "",
        "updated_at": card.get("updated_at") or "",
        "finished_at": card.get("finished_at") or "",
        "is_finished": is_finished,
        "timer_label": card.get("timer_label") or "",
        "timer_end_at": card.get("timer_end_at") or "",
        "labels": [lb.get("name") for lb in (card.get("labels") or []) if isinstance(lb, dict) and lb.get("name")],
        "technical_report": (card.get("quote_data") or {}).get("technical_report") or "",
        "solution": card.get("solution") or (card.get("quote_data") or {}).get("solution") or "",
        "photos": photos,
        "public_os_url": f"{base_url}/os/{safe_os}",
        "suggested_whatsapp_reply": suggested_reply,
    }


def lookup_os_records(q: str = "", phone: str = "", limit: int = 8, include_finished: bool = True) -> list[dict]:
    """Busca O.S. por número, nome/fantasia/série/CNPJ ou telefone (com normalização de últimos 8 dígitos)."""
    q_clean = (q or "").strip()
    phone_digits = _only_digits(phone)
    q_digits = _only_digits(q_clean)
    limit = max(1, min(int(limit or 8), 20))

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, l.title AS list_title, l.role AS list_role, l.is_tech AS list_is_tech
            FROM cards c
            LEFT JOIN lists l ON l.id = c.list_id
            WHERE UPPER(COALESCE(l.title, '')) != 'EXCLUIR'
            ORDER BY
                CASE WHEN COALESCE(c.finished_at, '') = '' AND UPPER(COALESCE(l.title, '')) NOT LIKE '%FINALIZADA%' THEN 0 ELSE 1 END,
                COALESCE(c.updated_at, c.created_at) DESC,
                c.id DESC
            """
        ).fetchall()

        client_names_by_phone: set[str] = set()
        if len(phone_digits) >= 8:
            tail8 = phone_digits[-8:]
            for cl in conn.execute("SELECT client_name, trade_name, phone FROM clients WHERE phone IS NOT NULL").fetchall():
                cdig = _only_digits(cl["phone"])
                if len(cdig) >= 8 and cdig.endswith(tail8):
                    if cl["client_name"]:
                        client_names_by_phone.add(cl["client_name"].strip().upper())
                    if cl["trade_name"]:
                        client_names_by_phone.add(cl["trade_name"].strip().upper())

    scored: list[tuple[int, dict]] = []
    q_upper = q_clean.upper()
    q_tokens = [tok for tok in re.split(r"\s+", q_upper) if len(tok) >= 2]
    tail8_phone = phone_digits[-8:] if len(phone_digits) >= 8 else ""

    for r in rows:
        d = dict(r)
        ltitle_up = (d.get("list_title") or "").upper()
        is_fin = bool(d.get("finished_at") or "FINALIZADA" in ltitle_up)
        if not include_finished and is_fin:
            continue

        os_up = (d.get("os_number") or "").strip().upper()
        os_dig = _only_digits(os_up)
        cname_up = (d.get("client_name") or "").strip().upper()
        tname_up = (d.get("trade_name") or "").strip().upper()
        serial_up = (d.get("serial_number") or "").strip().upper()
        cnpj_dig = _only_digits(d.get("cnpj_cpf"))
        card_phone_dig = _only_digits(d.get("phone"))

        score = 0
        if q_clean:
            if os_up == q_upper or (q_digits and os_dig and os_dig == q_digits):
                score = max(score, 100)
            elif q_digits and os_dig and q_digits in os_dig:
                score = max(score, 80)
            elif serial_up and q_upper in serial_up:
                score = max(score, 78)
            elif len(q_digits) >= 6 and cnpj_dig and q_digits in cnpj_dig:
                score = max(score, 75)
            elif q_upper in cname_up or (tname_up and q_upper in tname_up):
                score = max(score, 70)
            elif q_tokens and all((tok in cname_up or tok in tname_up or tok in serial_up or tok in os_up) for tok in q_tokens):
                score = max(score, 62)

        if tail8_phone:
            if len(card_phone_dig) >= 8 and card_phone_dig.endswith(tail8_phone):
                score = max(score, 90)
            elif cname_up and cname_up in client_names_by_phone:
                score = max(score, 68)
            elif tname_up and tname_up in client_names_by_phone:
                score = max(score, 65)

        if not q_clean and not tail8_phone:
            # Sem filtro: retorna as O.S. ativas mais recentes
            score = 20 if not is_fin else 5

        if score > 0:
            # Pequeno bônus para O.S. ainda em andamento
            final_score = score + (5 if not is_fin else 0)
            scored.append((final_score, d))

    scored.sort(key=lambda item: item[0], reverse=True)
    base_url = resolve_public_base_url()
    return [_format_card_for_integration(d, base_url) for _, d in scored[:limit]]


@bp.route("/api/integration/os-lookup", methods=["GET"])
def api_integration_os_lookup():
    """Consulta de O.S. usada pelo comando /os do Chatwoot e pelo Dashboard App lateral."""
    if not _is_authorized_integration_read():
        return jsonify({"success": False, "error": "Token ou sessão inválida."}), 401

    q = (request.args.get("q") or "").strip()
    phone = (request.args.get("phone") or "").strip()
    limit = request.args.get("limit", "8")
    include_finished = (request.args.get("include_finished", "1").strip().lower() not in ("0", "false", "no"))
    try:
        limit_int = int(limit)
    except ValueError:
        limit_int = 8

    items = lookup_os_records(q=q, phone=phone, limit=limit_int, include_finished=include_finished)
    return jsonify({
        "success": True,
        "count": len(items),
        "query": q,
        "phone": phone,
        "items": items,
    })


@bp.route("/integracao/chatwoot", methods=["GET"])
def chatwoot_dashboard_app_page():
    """Painel lateral (Dashboard App) da Esteira A5 embutido diretamente nas conversas do Chatwoot."""
    if not _is_authorized_integration_read():
        return make_response("Acesso não autorizado ao painel de integração Esteira A5.", 401)

    dash_token = compute_chatwoot_dashboard_token()
    chatwoot_origin = os.environ.get("A5_CHATWOOT_PUBLIC_URL", config.CHATWOOT_PUBLIC_URL).strip().rstrip("/") or "https://chat.a5painel.cloud"
    resp = make_response(
        render_template(
            "chatwoot_panel.html",
            dashboard_token=dash_token,
            public_url=resolve_public_base_url(),
            chatwoot_origin=chatwoot_origin,
        )
    )
    resp.headers["Content-Security-Policy"] = f"frame-ancestors 'self' {chatwoot_origin}"
    return resp


@bp.route("/api/integration/notify-whatsapp", methods=["POST"])
@require_api_roles("admin_recepcao", "master", "diretoria")
def api_integration_notify_whatsapp():
    """Envia aviso de status de O.S. para o cliente no WhatsApp via ponte Chatwoot/Evolution."""
    data = request.get_json(silent=True) or {}
    phone = (data.get("phone") or "").strip()
    message = (data.get("message") or "").strip()
    os_number = (data.get("os_number") or "").strip()
    client_name = (data.get("client_name") or "").strip()
    inbox = (data.get("inbox") or "laboratorio").strip().lower()

    digits = _only_digits(phone)
    if len(digits) < 8:
        raise ApiError("Informe um número de WhatsApp válido (com DDD).", status=400)
    if not message:
        raise ApiError("A mensagem não pode estar vazia.", status=400)

    bridge_base = os.environ.get("A5_CHATWOOT_BRIDGE_URL", config.CHATWOOT_BRIDGE_URL).strip().rstrip("/")
    bridge_token = _active_integration_token()
    if not bridge_base or not bridge_token:
        raise ApiError("Ponte Chatwoot/WhatsApp não configurada no servidor.", status=503)

    payload = json.dumps({
        "phone": digits,
        "message": message,
        "os_number": os_number,
        "client_name": client_name,
        "inbox": inbox,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{bridge_base}/internal/send-whatsapp",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Bridge-Token": bridge_token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            res_json = json.loads(raw) if raw else {"success": True}
            return jsonify(res_json), 200
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        try:
            err_data = json.loads(body)
            err_msg = err_data.get("error") or body
        except Exception:
            err_msg = body or f"HTTP {exc.code}"
        return jsonify({"success": False, "error": f"Falha ao enviar via Chatwoot/WhatsApp: {err_msg}"}), 502
    except Exception as exc:
        return jsonify({"success": False, "error": f"Ponte WhatsApp indisponível: {exc}"}), 502
