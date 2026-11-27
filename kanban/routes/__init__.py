"""Blueprints HTTP (cada arquivo agrupa as rotas de um assunto)."""
from . import auth, cards, lists, pages, reports, youtube, externos, chat, system, integrations

ALL_BLUEPRINTS = [auth.bp, pages.bp, lists.bp, cards.bp, reports.bp, youtube.bp, externos.bp, chat.bp, system.bp, integrations.bp]
