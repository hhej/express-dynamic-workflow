"""ORCH-style Search Agent node (TOOL-05).

Mirrors the Phase 2 ``fuel_agent_node`` / ``route_agent_node`` shape:

- Calls :func:`search_fuel_news` to get a :class:`SearchResult`.
- Narrates via Gemini with a D-11 deterministic-fallback path that
  guarantees an ``ok``-status trace entry whenever the tool succeeds.
- Emits exactly ONE D-12-shape ``reasoning_trace`` entry.
- Populates ``state.search_context`` (D-11 shape — ``SearchResult.model_dump()``).

D-12 graceful failure: any :class:`RuntimeError` from the tool (missing
key, Tavily quota/auth/network) is converted to ``search_context=None``
plus a ``status="warn"`` trace entry; the planner continues unblocked.
Search NEVER blocks the surcharge response.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from backend.agent.llm import get_chat_model
from backend.agent.prompts.search_agent import SYSTEM_PROMPT
from backend.agent.tools.models import SearchResult
from backend.agent.tools.search_fuel_news import search_fuel_news

__all__ = ["search_agent_node"]

logger = logging.getLogger(__name__)

_DEFAULT_QUERY = "Thailand diesel fuel price news"


class SearchReasoning(BaseModel):
    """Structured narration schema (D-11)."""

    summary: str = Field(description="1-2 sentence market context")


def _last_user_message(state: dict) -> str:
    """Return the most recent user message content, or '' when none."""
    for m in reversed(state.get("messages") or []):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def _deterministic_narration(result: SearchResult) -> str:
    """D-11 fallback when LLM narration fails or returns invalid JSON."""
    if result.summary:
        return result.summary
    if result.sources:
        top = result.sources[0]
        snippet = top.snippet[:160] if top.snippet else top.title
        return snippet
    return "No recent news found about Thailand diesel prices."


def _parse_structured(raw: str) -> SearchReasoning:
    """Parse JSON narration; strip optional ```json fences (Gemini quirk)."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return SearchReasoning.model_validate(json.loads(text))


def _narrate_with_llm(result: SearchResult) -> str:
    """Gemini narration with D-11 deterministic fallback.

    Mirrors fuel_agent / route_agent: raw ``model.invoke()`` + JSON parse
    rather than ``with_structured_output`` so the FakeMessagesListChatModel
    test seam works (Phase 2 Plan 05 decision).
    """
    try:
        model = get_chat_model()
        user_payload = json.dumps(
            {
                "query": result.query,
                "tavily_summary": result.summary,
                "sources": [
                    {"title": s.title, "snippet": s.snippet[:160]}
                    for s in result.sources[:3]
                ],
            },
            ensure_ascii=False,
        )
        response = model.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_payload),
            ]
        )
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = str(content)
        parsed = _parse_structured(content)
        return parsed.summary
    except (Exception, ValidationError) as exc:  # D-11 fallback
        logger.warning(
            "search_agent Gemini narration failed, using deterministic fallback: %s",
            exc,
        )
        return _deterministic_narration(result)


def search_agent_node(state: dict) -> dict:
    """Search → narrate → populate search_context + emit one trace entry.

    Args:
        state: Full AgentState-shaped dict.

    Returns:
        Partial state dict::

            {
                "search_context": SearchResult.model_dump() | None,
                "reasoning_trace": [one_trace_entry],
            }

        On Tavily failure ``search_context`` is ``None`` and the trace
        entry has ``status="warn"`` (D-12 graceful failure).
    """
    query = _last_user_message(state) or _DEFAULT_QUERY
    prior = len(state.get("reasoning_trace") or [])
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    try:
        result = search_fuel_news(query=query, max_results=5)
    except RuntimeError as exc:
        logger.warning("search_fuel_news failed: %s", exc)
        return {
            "search_context": None,
            "reasoning_trace": [
                {
                    "step": prior + 1,
                    "agent": "search_agent",
                    "tool": "search_fuel_news",
                    "tool_input": {"query": query},
                    "tool_output": {"error": str(exc)},
                    "reasoning": "Search failed; continuing without market context.",
                    "timestamp": timestamp,
                    "status": "warn",
                }
            ],
            # Quick task 260509-utd UTD-04: per-turn cost-bombing counter.
            # Count failed attempts too — a misbehaving Tavily key shouldn't
            # let an attacker bypass the cap by triggering RuntimeError loops.
            # Emit +1 DELTA (operator.add reducer in AgentState).
            "tool_call_count": 1,
        }

    narration = _narrate_with_llm(result)

    return {
        "search_context": result.model_dump(),
        "reasoning_trace": [
            {
                "step": prior + 1,
                "agent": "search_agent",
                "tool": "search_fuel_news",
                "tool_input": {"query": query, "max_results": 5},
                "tool_output": {
                    "summary_present": bool(result.summary),
                    "sources_count": len(result.sources),
                    "fetched_at": result.fetched_at,
                },
                "reasoning": narration,
                "timestamp": timestamp,
                "status": "ok",
            }
        ],
        # Quick task 260509-utd UTD-04: per-turn cost-bombing counter.
        # Emit +1 DELTA (operator.add reducer in AgentState).
        "tool_call_count": 1,
    }
