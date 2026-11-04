"""Regras de negócio sobre as colunas do Kanban (qual coluna é o quê)."""

# Colunas que geram aviso de "chegou para ..." na TV, identificadas pelo papel (role)
_ARRIVAL_BY_ROLE = {"orcamento": "ORÇAMENTO", "aprovada": "APROVADA", "aprovados": "APROVADA"}
# Colunas criadas pela tela com esses nomes exatos também avisam
_ARRIVAL_BY_TITLE = {"ORÇAMENTOS": "ORÇAMENTO", "APROVADAS": "APROVADA", "APROVADOS": "APROVADA"}


def _as_dict(lst):
    if lst is None:
        return {}
    if isinstance(lst, dict):
        return lst
    try:
        return dict(lst)
    except Exception:
        return {}


def arrival_stage(lst):
    """
    Retorna "ORÇAMENTO" ou "APROVADA" se a coluna deve anunciar chegadas na TV, senão None.
    Usa o papel da coluna (continua funcionando se ela for renomeada) e, como reserva,
    o nome exato. Colunas como "ORÇAMENTOS ENVIADOS" e "ORÇAMENTOS NÃO AUTORIZADOS" não anunciam.
    """
    if lst is None:
        return None
    d = _as_dict(lst)
    role = (d.get("role") or "").lower()
    stage = _ARRIVAL_BY_ROLE.get(role)
    if stage:
        return stage
    return _ARRIVAL_BY_TITLE.get((d.get("title") or "").strip().upper())


def is_finished_list(lst):
    """Coluna de serviços concluídos (FINALIZADAS)."""
    if lst is None:
        return False
    d = _as_dict(lst)
    return d.get("role") == "finalizada" or "FINALIZADA" in (d.get("title") or "").upper()


def is_ready_list(lst):
    """Coluna de balanças prontas aguardando conferência final da Priscila (BALANÇAS PRONTAS)."""
    if lst is None:
        return False
    d = _as_dict(lst)
    return d.get("role") == "pronta" or "PRONTA" in (d.get("title") or "").upper()


def is_approved_list(lst):
    """Coluna de serviços aprovados pelo cliente (APROVADAS ou APROVADOS)."""
    if lst is None:
        return False
    d = _as_dict(lst)
    role = (d.get("role") or "").lower()
    title = (d.get("title") or "").upper()
    return "aprovad" in role or "APROVAD" in title


def is_orcamento_entry_list(lst):
    """Coluna inicial de fila de orçamentos (ORÇAMENTOS)."""
    if lst is None:
        return False
    d = _as_dict(lst)
    return d.get("role") == "orcamento" or (d.get("title") or "").strip().upper() == "ORÇAMENTOS"


def is_tech_list(lst):
    """Coluna de bancada de um técnico."""
    if lst is None:
        return False
    d = _as_dict(lst)
    return d.get("is_tech") == 1


def is_nao_autorizados_list(lst):
    """Coluna de orçamentos não autorizados pelo cliente."""
    if lst is None:
        return False
    d = _as_dict(lst)
    role = (d.get("role") or "").lower()
    title = (d.get("title") or "").upper()
    return "nao_autorizado" in role or "NÃO AUTORIZAD" in title or "NAO AUTORIZAD" in title


