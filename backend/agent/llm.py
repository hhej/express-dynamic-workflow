"""Gemini chat-model factory (test-swappable).

All Phase 2+ agent nodes obtain their Gemini model via get_chat_model().
Tests patch this factory to return a FakeMessagesListChatModel, so no
live Gemini quota is ever consumed by automated tests (D-16).
"""
from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI

from backend.config import GEMINI_MODEL

__all__ = ["get_chat_model"]


def get_chat_model(**overrides) -> ChatGoogleGenerativeAI:
    """Return a configured ChatGoogleGenerativeAI instance.

    Args:
        **overrides: Any keyword arguments forwarded to the ChatGoogleGenerativeAI
            constructor, overriding defaults (e.g., model, temperature, max_retries).

    Returns:
        ChatGoogleGenerativeAI configured with temperature=0 (determinism for
        D-12 trace reproducibility) and max_retries=0 (we own the retry policy
        at the node level per D-11).
    """
    defaults = dict(model=GEMINI_MODEL, temperature=0.0, max_retries=0)
    defaults.update(overrides)
    return ChatGoogleGenerativeAI(**defaults)
