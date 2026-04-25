"""ORCH-03: Route Agent node.

Wraps calculate_route and narrates the result via Gemini (D-09) with a
D-11 deterministic-fallback narration. Emits one D-12 trace entry.

Reads pre-extracted `origin` and `destination` from state (D-10 — the
Planner in Phase 3 is responsible for populating these). Until the
AgentState TypedDict adds these fields in Phase 3, we read them
tolerantly via state.get().
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from backend.agent.llm import get_chat_model
from backend.agent.prompts.route_agent import SYSTEM_PROMPT
from backend.agent.tools.calculate_route import calculate_route
from backend.agent.tools.models import RouteData

__all__ = ["route_agent_node"]

logger = logging.getLogger(__name__)

_TRAFFIC_LABELS = {1: "light", 2: "moderate", 3: "moderate", 4: "heavy", 5: "severe"}


class RouteReasoning(BaseModel):
    """Structured narration schema for the Route Agent (D-11)."""
    summary: str = Field(description="One-sentence route summary")
    traffic_label: str = Field(
        description="light | moderate | heavy | severe"
    )


def _deterministic_narration(route_data: RouteData) -> str:
    label = _TRAFFIC_LABELS.get(route_data.traffic_severity, "unknown")
    return (
        f"Route {route_data.origin} -> {route_data.destination}: "
        f"{route_data.distance_km:.1f} km, {route_data.duration_min} min, "
        f"{label} traffic (severity {route_data.traffic_severity}), "
        f"zone {route_data.zone}."
    )


def _parse_structured(raw: str) -> RouteReasoning:
    """Parse a JSON string into RouteReasoning.

    Strips Markdown code fences Gemini sometimes emits (```json ... ```).
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return RouteReasoning.model_validate(json.loads(text))


def _narrate_with_llm(route_data: RouteData) -> str:
    """Call Gemini; fall back to deterministic narration on any failure (D-11).

    Uses plain chat invocation + JSON parsing for test-swappability
    (FakeMessagesListChatModel does not implement ``with_structured_output``).
    """
    try:
        model = get_chat_model()
        response = model.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Tool returned: {route_data.model_dump_json()}"
                ),
            ]
        )
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = str(content)
        out = _parse_structured(content)
        return f"{out.summary} (traffic={out.traffic_label})"
    except (Exception, ValidationError) as exc:
        logger.warning(
            "route_agent Gemini narration failed, using deterministic fallback: %s",
            exc,
        )
        return _deterministic_narration(route_data)


def route_agent_node(state: dict) -> dict:
    """Route Agent: compute route, narrate, emit D-12 trace entry.

    Args:
        state: Full AgentState-shaped dict. Must include pre-extracted
            `origin` and `destination` keys (D-10).

    Returns:
        Partial state dict: {"route_data": RouteData.model_dump(),
                             "reasoning_trace": [one_trace_entry]}.

    Raises:
        ValueError: If origin or destination is not set in state (Planner
            failed its pre-extraction contract).
    """
    origin = state.get("origin")
    destination = state.get("destination")
    if not origin or not destination:
        raise ValueError(
            "route_agent_node requires both 'origin' and 'destination' "
            f"in state; got origin={origin!r}, destination={destination!r}"
        )

    route_data = calculate_route(origin, destination)
    reasoning = _narrate_with_llm(route_data)

    prior_steps = len(state.get("reasoning_trace") or [])
    trace_entry = {
        "step": prior_steps + 1,
        "agent": "route_agent",
        "tool": "calculate_route",
        "tool_input": {"origin": origin, "destination": destination},
        "tool_output": route_data.model_dump(),
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "status": "ok",
    }

    # D-13: stamp fetched_at (UTC ISO-8601 'Z') into the dumped dict so
    # planner_node can detect cache-fresh route data. The trace entry's
    # tool_output above intentionally uses the un-annotated dump — the
    # fetched_at field is a state-level annotation, not a tool return.
    route_dump = route_data.model_dump()
    route_dump["fetched_at"] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    return {
        "route_data": route_dump,
        "reasoning_trace": [trace_entry],
    }
