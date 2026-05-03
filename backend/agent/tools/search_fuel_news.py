"""TOOL-05: Tavily-backed fuel news / market trends search.

D-09 trigger semantics: planner routes to ``search_context`` ONLY for
news/trend questions (e.g. "why is fuel up", "diesel news this week").
Standard ``surcharge_query`` and ``followup_query`` NEVER trigger search.

D-12 graceful failure: any Tavily error (network, quota, auth) raises
a ``RuntimeError`` that ``search_agent_node`` converts to a warn-status
trace entry; ``search_context`` stays ``None``; the planner continues
unblocked. Search NEVER blocks the surcharge response.

D-12 caching: in-process :class:`TTLCache` (default 30 min, configurable
via :data:`backend.config.SEARCH_CACHE_TTL_SECONDS`) keyed on the
normalized query + ``max_results``. Mirrors the Phase 2 D-07 route-cache
pattern so semantically identical queries share results.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Tuple

from backend.agent.tools._cache import TTLCache
from backend.agent.tools.models import SearchResult, SearchSource
from backend.config import SEARCH_CACHE_TTL_SECONDS

__all__ = ["search_fuel_news", "_normalize_query", "_clear_cache"]

logger = logging.getLogger(__name__)

# Module-level cache shared across callers. Tests reset via _clear_cache().
_CACHE: TTLCache = TTLCache(ttl_seconds=SEARCH_CACHE_TTL_SECONDS)

_WS_RE = re.compile(r"\s+")

# Hard ceiling for snippet length (Pitfall 2 mitigation: huge Tavily
# `content` payloads bloat reasoning_trace JSON in Langfuse + frontend).
_SNIPPET_MAX = 240


def _normalize_query(query: str) -> str:
    """Pitfall 3 mitigation: lowercase + strip + collapse multi-space.

    Ensures semantically identical queries hash to the same cache key
    (e.g. ``"What is DIESEL doing today?"`` and
    ``"what is diesel    doing today"`` resolve to one entry).
    """
    return _WS_RE.sub(" ", query.strip()).lower()


def _clear_cache() -> None:
    """Test-only — reset the module-level cache."""
    _CACHE.clear()


def _client():
    """Lazy Tavily client construction.

    Tests monkeypatch ``tavily.TavilyClient`` directly so the import is
    deferred to call time (D-16: no SDK import at module load).

    Raises:
        RuntimeError: when ``TAVILY_API_KEY`` is unset/empty.
    """
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is empty — search_fuel_news cannot run"
        )
    from tavily import TavilyClient  # type: ignore[import-untyped]
    return TavilyClient(api_key)


def search_fuel_news(query: str, max_results: int = 5) -> SearchResult:
    """Tavily news search for fuel market context.

    Args:
        query: User-supplied question. Normalized for cache hashing.
        max_results: Hard ceiling on returned sources (1..10).

    Returns:
        :class:`SearchResult` with optional 1-line summary + ranked sources.

    Raises:
        RuntimeError: when ``TAVILY_API_KEY`` is missing or any Tavily
            call failure (network, quota, auth) occurs. The
            ``search_agent_node`` catches this and converts to a
            warn-status trace entry (D-12).
    """
    norm = _normalize_query(query)
    key: Tuple[str, int] = (norm, max_results)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    try:
        raw = _client().search(
            query=query,
            topic="news",
            max_results=max_results,
            include_answer="basic",
            search_depth="basic",
        )
    except RuntimeError:
        # Missing-key path bubbles unchanged — already RuntimeError shape.
        raise
    except Exception as exc:  # noqa: BLE001 — convert ANY Tavily failure
        logger.warning("Tavily search failed: %s", exc)
        raise RuntimeError(f"Tavily search failed: {exc}") from exc

    sources = []
    for r in (raw.get("results") or []):
        content = (r.get("content") or "")[:_SNIPPET_MAX]
        sources.append(
            SearchSource(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=content,
                published_at=r.get("published_date"),
            )
        )
    result = SearchResult(
        query=query,
        summary=raw.get("answer"),
        sources=sources,
        fetched_at=datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    )
    _CACHE.set(key, result)
    return result
