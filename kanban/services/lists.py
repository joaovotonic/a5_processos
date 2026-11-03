"""Regras das colunas (listas) do quadro Kanban."""
from ..database import connect
from ..errors import ApiError


def create_list(title, is_tech):
    """Cria uma nova coluna no final do quadro (+ Adicionar outra lista)."""
    if not title:
        raise ApiError("O título da lista é obrigatório.")
    with connect() as conn:
        max_pos = conn.execute("SELECT COALESCE(MAX(position), -1) as m FROM lists").fetchone()["m"]
        conn.execute(
            "INSERT INTO lists (title, position, is_tech, role) VALUES (?, ?, ?, ?)",
            (title, max_pos + 1, 1 if is_tech else 0, "tech" if is_tech else "processo")
        )


def rename_list(list_id, new_title):
    if not new_title:
        raise ApiError("Título inválido.")
    with connect() as conn:
        conn.execute("UPDATE lists SET title = ? WHERE id = ?", (new_title, list_id))


def delete_list(list_id):
    """Remove uma coluna vazia (colunas com cartões não podem ser excluídas)."""
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM cards WHERE list_id = ?", (list_id,)).fetchone()["c"]
        if count > 0:
            raise ApiError("Mova os cartões antes de excluir esta coluna.")
        conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))


def reorder_lists(ordered_ids):
    """Salva a nova ordem das colunas."""
    with connect() as conn:
        for idx, lid in enumerate(ordered_ids):
            conn.execute("UPDATE lists SET position = ? WHERE id = ?", (idx, lid))

