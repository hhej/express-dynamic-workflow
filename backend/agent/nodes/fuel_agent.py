"""ORCH-02: Fuel Agent node.

Wraps fetch_fuel_price and narrates the result via Gemini (D-09), with
D-11 deterministic-fallback narration when the LLM fails. Emits one D-12
schema reasoning_trace entry.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from backend.agent.llm import get_chat_model
from backend.agent.prompts.fuel_agent import SYSTEM_PROMPT
from backend.agent.tools.fetch_fuel_price import fetch_fuel_price
from backend.agent.tools.models import FuelData

__all__ = ["fuel_agent_node"]

logger = logging.getLogger(__name__)


class FuelReasoning(BaseModel):
    """Structured narration schema for the Fuel Agent (D-11)."""
    summary: str = Field(description="One-sentence summary of the fuel price")
    trend: str = Field(
        description="above_baseline | below_baseline | at_baseline"
    )


def _deterministic_narration(fuel_data: FuelData) -> str:
    """D-11 fallback narration when Gemini parsing fails."""
    if fuel_data.delta_pct > 0:
        direction = "above"
    elif fuel_data.delta_pct < 0:
        direction = "below"
    else:
        direction = "at"
    return (
        f"Current diesel B7 is {fuel_data.price:.2f} THB/L "
        f"({abs(fuel_data.delta_pct):.2%} {direction} baseline "
        f"{fuel_data.baseline:.2f}). Source: {fuel_data.source}."
    )


def _parse_structured(raw: str) -> FuelReasoning:
    """Parse JSON string into FuelReasoning.

    Strips Markdown code fences Gemini sometimes emits (```json ... ```).
    """
    text = raw.strip()
    if text.startswith("```"):
        # Strip fenced code block
        lines = text.splitlines()
        # Drop first fence
        lines = lines[1:]
        # Drop trailing fence if present
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return FuelReasoning.model_validate(json.loads(text))


def _narrate_with_llm(fuel_data: FuelData) -> str:
    """Call Gemini; fall back to deterministic narration on any failure (D-11).

    Uses plain chat invocation + JSON parsing rather than
    ``.with_structured_output`` because (a) the fake chat models used in
    tests do not implement structured-output helpers, and (b) our system
    prompt already instructs the model to emit JSON matching the schema.
    """
    try:
        model = get_chat_model()
        response = model.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Tool returned: {fuel_data.model_dump_json()}"
                ),
            ]
        )
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = str(content)
        out = _parse_structured(content)
        return f"{out.summary} (trend={out.trend})"
    except (Exception, ValidationError) as exc:  # D-11 fallback
        logger.warning(
            "fuel_agent Gemini narration failed, using deterministic fallback: %s",
            exc,
        )
        return _deterministic_narration(fuel_data)


def fuel_agent_node(state: dict) -> dict:
    """Fuel Agent: fetch current diesel price, narrate, emit D-12 trace entry.

    Args:
        state: Full AgentState-shaped dict.

    Returns:
        Partial state dict: {"fuel_data": FuelData.model_dump(),
                             "reasoning_trace": [one_trace_entry]}.
        LangGraph merges via the Annotated[List[dict], operator.add] reducer
        (see Phase 2 Pitfall 1 / backend/agent/state.py).
    """
    fuel_data = fetch_fuel_price()
    reasoning = _narrate_with_llm(fuel_data)

    prior_steps = len(state.get("reasoning_trace") or [])
    trace_entry = {
        "step": prior_steps + 1,
        "agent": "fuel_agent",
        "tool": "fetch_fuel_price",
        "tool_input": {},
        "tool_output": fuel_data.model_dump(),
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "status": "ok",
    }

    # D-13: stamp fetched_at (UTC ISO-8601 'Z') into the dumped dict so
    # planner_node can compute the FUEL_DATA_TTL_SECONDS skip. The
    # FuelData Pydantic model itself does not carry this field — it is a
    # state-level annotation, not part of the tool's return shape.
    fuel_dump = fuel_data.model_dump()
    fuel_dump["fetched_at"] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    return {
        "fuel_data": fuel_dump,
        "reasoning_trace": [trace_entry],
    }
