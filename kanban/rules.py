"""Regras de negócio sobre as colunas do Kanban (qual coluna é o quê)."""

# Colunas que geram aviso de "chegou para ..." na TV, identificadas pelo papel (role)
_ARRIVAL_BY_ROLE = {"orcamento": "ORÇAMENTO", "aprovada": "APROVADA", "aprovados": "APROVADA"}
# Colunas criadas pela tela com esses nomes exatos também avisam
_ARRIVAL_BY_TITLE = {"ORÇAMENTOS": "ORÇAMENTO", "APROVADAS": "APROVADA", "APROVADOS": "APROVADA"}


def arrival_stage(lst):
    """
    Retorna "ORÇAMENTO" ou "APROVADA" se a coluna deve anunciar chegadas na TV, senão None.
    Usa o papel da coluna (continua funcionando se ela for renomeada) e, como reserva,
    o nome exato. Colunas como "ORÇAMENTOS ENVIADOS" e "ORÇAMENTOS NÃO AUTORIZADOS" não anunciam.
    """
    if lst is None:
        return None
    role = (lst.get("role") or "").lower()
    stage = _ARRIVAL_BY_ROLE.get(role)
    if stage:
        return stage
    return _ARRIVAL_BY_TITLE.get((lst.get("title") or "").strip().upper())


def is_finished_list(lst):
    """Coluna de serviços concluídos (FINALIZADAS)."""
    if lst is None:
        return False
    return lst.get("role") == "finalizada" or "FINALIZADA" in (lst.get("title") or "").upper()


def is_ready_list(lst):
    """Coluna de balanças prontas aguardando conferência final da Priscila (BALANÇAS PRONTAS)."""
    if lst is None:
        return False
    return lst.get("role") == "pronta" or "PRONTA" in (lst.get("title") or "").upper()


def is_approved_list(lst):
    """Coluna de serviços aprovados pelo cliente (APROVADAS ou APROVADOS)."""
    if lst is None:
        return False
    role = (lst.get("role") or "").lower()
    title = (lst.get("title") or "").upper()
    return "aprovad" in role or "APROVAD" in title


def is_orcamento_entry_list(lst):
    """Coluna inicial de fila de orçamentos (ORÇAMENTOS)."""
    if lst is None:
        return False
    return lst["role"] == "orcamento" or (lst["title"] or "").strip().upper() == "ORÇAMENTOS"


def is_tech_list(lst):
    """Coluna de bancada de um técnico."""
    return lst is not None and lst["is_tech"] == 1

