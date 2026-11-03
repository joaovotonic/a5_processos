"""Blueprints HTTP (cada arquivo agrupa as rotas de um assunto)."""
from . import cards, lists, pages, reports, youtube

ALL_BLUEPRINTS = [pages.bp, lists.bp, cards.bp, reports.bp, youtube.bp]


