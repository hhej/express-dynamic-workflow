"""TOOL-05 — Search Agent node unit tests."""
from __future__ import annotations

import pytest  # noqa: F401  (kept for future fixtures)

from backend.agent.nodes import search_agent as sa_mod
from backend.agent.tools.models import SearchResult, SearchSource


def _scripted_llm(monkeypatch, content: str = "not json — forces fallback"):
    """Patch get_chat_model to a FakeMessagesListChatModel with one response.

    Default content is invalid JSON so the D-11 fallback path is exercised
    deterministically — the agent's reasoning should equal the SearchResult
    summary (or deterministic-fallback narration).
    """
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage

    monkeypatch.setattr(
        sa_mod,
        "get_chat_model",
        lambda **_: FakeMessagesListChatModel(
            responses=[AIMessage(content=content)]
        ),
    )


def test_search_agent_populates_context(monkeypatch):
    result = SearchResult(
        query="diesel news",
        summary="Diesel prices held steady this week.",
        sources=[
            SearchSource(
                title="Weekly diesel",
                url="https://x",
                snippet="snip",
                published_at="2026-05-01",
            ),
        ],
        fetched_at="2026-05-02T10:00:00Z",
    )
    monkeypatch.setattr(
        sa_mod, "search_fuel_news", lambda query, max_results=5: result
    )
    _scripted_llm(monkeypatch)
    state = {
        "messages": [{"role": "user", "content": "What's driving diesel?"}],
        "reasoning_trace": [],
    }
    out = sa_mod.search_agent_node(state)
    assert out["search_context"]["query"] == "diesel news"
    assert (
        out["search_context"]["summary"] == "Diesel prices held steady this week."
    )
    assert len(out["reasoning_trace"]) == 1
    assert out["reasoning_trace"][0]["status"] == "ok"
    assert out["reasoning_trace"][0]["agent"] == "search_agent"


def test_search_failure_graceful_warn(monkeypatch):
    def boom(query, max_results=5):
        raise RuntimeError("Tavily 429 quota exceeded")

    monkeypatch.setattr(sa_mod, "search_fuel_news", boom)
    state = {
        "messages": [{"role": "user", "content": "diesel?"}],
        "reasoning_trace": [],
    }
    out = sa_mod.search_agent_node(state)
    assert out["search_context"] is None
    assert len(out["reasoning_trace"]) == 1
    entry = out["reasoning_trace"][0]
    assert entry["status"] == "warn"
    assert "Tavily 429" in entry["tool_output"]["error"]
    assert entry["agent"] == "search_agent"


def test_search_agent_uses_last_user_message_as_query(monkeypatch):
    captured: dict = {}

    def fake_search(query, max_results=5):
        captured["query"] = query
        return SearchResult(query=query, summary="ok", sources=[], fetched_at="z")

    monkeypatch.setattr(sa_mod, "search_fuel_news", fake_search)
    _scripted_llm(monkeypatch)
    state = {
        "messages": [
            {"role": "assistant", "content": "earlier"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "Why is diesel up this week?"},
        ],
        "reasoning_trace": [],
    }
    sa_mod.search_agent_node(state)
    assert captured["query"] == "Why is diesel up this week?"


def test_search_agent_falls_back_to_default_query(monkeypatch):
    captured: dict = {}

    def fake_search(query, max_results=5):
        captured["query"] = query
        return SearchResult(query=query, summary="ok", sources=[], fetched_at="z")

    monkeypatch.setattr(sa_mod, "search_fuel_news", fake_search)
    _scripted_llm(monkeypatch)
    state = {"messages": [], "reasoning_trace": []}
    sa_mod.search_agent_node(state)
    assert captured["query"] == "Thailand diesel fuel price news"


def test_search_agent_emits_exactly_one_trace_entry(monkeypatch):
    monkeypatch.setattr(
        sa_mod,
        "search_fuel_news",
        lambda query, max_results=5: SearchResult(
            query=query, summary="x", sources=[], fetched_at="z"
        ),
    )
    _scripted_llm(monkeypatch)
    state = {
        "messages": [{"role": "user", "content": "diesel"}],
        "reasoning_trace": [],
    }
    out = sa_mod.search_agent_node(state)
    assert len(out["reasoning_trace"]) == 1


def test_search_agent_summary_in_reasoning(monkeypatch):
    monkeypatch.setattr(
        sa_mod,
        "search_fuel_news",
        lambda query, max_results=5: SearchResult(
            query=query,
            summary="prices held steady",
            sources=[],
            fetched_at="z",
        ),
    )
    # Force fallback so reasoning == result.summary deterministically.
    _scripted_llm(monkeypatch, content="not json")
    state = {
        "messages": [{"role": "user", "content": "diesel"}],
        "reasoning_trace": [],
    }
    out = sa_mod.search_agent_node(state)
    assert out["reasoning_trace"][0]["reasoning"] == "prices held steady"
