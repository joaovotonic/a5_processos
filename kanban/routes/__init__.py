"""Blueprints HTTP (cada arquivo agrupa as rotas de um assunto)."""
from . import cards, lists, pages, reports, youtube, externos, chat

ALL_BLUEPRINTS = [pages.bp, lists.bp, cards.bp, reports.bp, youtube.bp, externos.bp, chat.bp]
