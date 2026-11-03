"""Catálogo de Peças Originais Toledo Prix (2.662 códigos e descritivos)."""
import json
import os
import unicodedata

from ..config import TOLEDO_PARTS_PATH

_FALLBACK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "toledo_parts.json")
_catalog_cache = None


def _normalize(text):
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def load_parts_catalog():
    """Carrega o catálogo de peças Toledo em memória (cacheado)."""
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache

    path = TOLEDO_PARTS_PATH if os.path.exists(TOLEDO_PARTS_PATH) else _FALLBACK_PATH
    if not os.path.exists(path):
        _catalog_cache = []
        return _catalog_cache

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    _catalog_cache = [
        {
            "code": item["code"],
            "description": item["description"],
            "_search": _normalize(f"{item['code']} {item['description']}"),
            "_code_norm": _normalize(item["code"]),
        }
        for item in raw
    ]
    return _catalog_cache


def search_parts(query="", limit=30):
    """
    Busca peças Toledo por código ou descrição (suporta múltiplos termos, ex: 'teclado prix 5').
    Coloca correspondências exatas ou por prefixo de código no topo.
    """
    catalog = load_parts_catalog()
    q = _normalize(query)
    if not q:
        return [{"code": p["code"], "description": p["description"]} for p in catalog[:limit]]

    terms = [t for t in q.split() if t]
    exact_or_prefix = []
    partial = []

    for item in catalog:
        if all(t in item["_search"] for t in terms):
            entry = {"code": item["code"], "description": item["description"]}
            if item["_code_norm"].startswith(terms[0]):
                exact_or_prefix.append(entry)
            else:
                partial.append(entry)

    results = exact_or_prefix + partial
    return results[:limit]

