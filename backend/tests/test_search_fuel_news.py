"""TOOL-05 — search_fuel_news tool unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.agent.tools import search_fuel_news as sfn


@pytest.fixture(autouse=True)
def _reset_cache():
    sfn._clear_cache()
    yield
    sfn._clear_cache()


@pytest.fixture
def fake_tavily(monkeypatch):
    client = MagicMock()
    client.search.return_value = {
        "query": "diesel news",
        "answer": "Diesel prices held steady this week.",
        "results": [
            {
                "title": "Weekly diesel report",
                "url": "https://example.com/diesel",
                "content": "Retail diesel B7 unchanged at 30 THB/L. " * 20,
                "published_date": "2026-05-01",
            },
        ],
    }
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-fake-key")
    monkeypatch.setattr(
        "tavily.TavilyClient",
        lambda *a, **kw: client,
        raising=True,
    )
    return client


def test_search_fuel_news_returns_search_result(fake_tavily):
    result = sfn.search_fuel_news(query="What's diesel doing this week?")
    assert result.summary == "Diesel prices held steady this week."
    assert len(result.sources) == 1
    assert result.sources[0].title == "Weekly diesel report"
    assert result.sources[0].url == "https://example.com/diesel"
    assert result.sources[0].published_at == "2026-05-01"
    assert len(result.sources[0].snippet) <= 240
    assert result.fetched_at.endswith("Z")


def test_search_fuel_news_normalizes_query(fake_tavily):
    a = sfn.search_fuel_news(query="What is DIESEL doing today")
    b = sfn.search_fuel_news(query="what is diesel    doing today")
    # Same normalized key → same cached result, single Tavily call.
    assert a is b
    assert fake_tavily.search.call_count == 1


def test_search_fuel_news_caches_repeat_calls(fake_tavily):
    sfn.search_fuel_news(query="diesel news")
    sfn.search_fuel_news(query="diesel news")
    assert fake_tavily.search.call_count == 1


def test_search_fuel_news_raises_on_missing_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        sfn.search_fuel_news(query="anything")


def test_search_fuel_news_strips_long_snippets(fake_tavily):
    result = sfn.search_fuel_news(query="diesel")
    assert len(result.sources[0].snippet) == 240


def test_search_fuel_news_converts_tavily_exception_to_runtime_error(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    client = MagicMock()
    client.search.side_effect = ValueError("tavily 429 rate limit")
    monkeypatch.setattr(
        "tavily.TavilyClient",
        lambda *a, **kw: client,
        raising=True,
    )
    with pytest.raises(RuntimeError, match="Tavily search failed"):
        sfn.search_fuel_news(query="diesel")
