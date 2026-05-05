"""ORCH-04: Pricing Agent node.

Calls lookup_rate(...) then calculate_surcharge_tool.invoke(...), narrates the
combined result via Gemini (D-09) with a D-11 deterministic-fallback narration,
and emits ONE D-12 trace entry whose ``tool`` field is the compound name
``"lookup_rate+calculate_surcharge"`` (D-08).

D-09 contract: ``ValueError`` raised by ``lookup_rate`` (e.g. unknown
shipping_type/zone, weight outside any tier) propagates uncaught — the
Pricing Agent does NOT swallow lookup misses.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, ValidationError

from backend.agent.llm import get_chat_model
from backend.agent.observability import post_formula_accuracy_score
from backend.agent.prompts.pricing_agent import SYSTEM_PROMPT
from backend.agent.tools.calculate_surcharge_tool import (
    calculate_surcharge_tool,
)
from backend.agent.tools.lookup_rate import lookup_rate
from backend.agent.tools.models import (
    RateResult,
    SurchargeInput,
    SurchargeResult,
)

__all__ = ["pricing_agent_node"]

logger = logging.getLogger(__name__)


class PricingReasoning(BaseModel):
    """Structured narration schema for the Pricing Agent (D-11)."""

    summary: str = Field(description="One-sentence pricing summary")


def _deterministic_narration(
    rate: RateResult, surcharge: SurchargeResult
) -> str:
    """D-11 fallback narration when Gemini parsing fails."""
    cap_note = " (capped)" if surcharge.capped else ""
    return (
        f"Base rate {rate.base_rate:.2f} THB ({rate.rate_tier}); "
        f"surcharge {surcharge.surcharge_pct:.2%} = "
        f"{surcharge.surcharge_amount:.2f} THB; "
        f"total {surcharge.total:.2f} THB{cap_note}."
    )


def _parse_structured(raw: str) -> PricingReasoning:
    """Parse a JSON string into PricingReasoning.

    Strips Markdown code fences Gemini sometimes emits (```json ... ```).
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return PricingReasoning.model_validate(json.loads(text))


def _narrate_with_llm(rate: RateResult, surcharge: SurchargeResult) -> str:
    """Call Gemini; fall back to deterministic narration on any failure (D-11)."""
    try:
        model = get_chat_model()
        response = model.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Rate: {rate.model_dump_json()} | "
                        f"Surcharge: {surcharge.model_dump_json()}"
                    )
                ),
            ]
        )
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = str(content)
        out = _parse_structured(content)
        return out.summary
    except (Exception, ValidationError) as exc:  # D-11 fallback
        logger.warning(
            "pricing_agent Gemini narration failed, using deterministic fallback: %s",
            exc,
        )
        return _deterministic_narration(rate, surcharge)


def pricing_agent_node(
    state: dict, config: Optional[RunnableConfig] = None
) -> dict:
    """Pricing Agent: rate lookup + surcharge tool + D-12 trace entry.

    Phase 5 (Plan 05-02 / OBS-03): after a successful surcharge_result
    is built, fire-and-forget ``post_formula_accuracy_score(...)`` (D-15).
    The trace_id is read from ``config["metadata"]["langfuse_trace_id"]``
    seeded by the chat handler's ``_make_config``. Auto-eval failures
    are swallowed inside ``post_formula_accuracy_score`` AND are guarded
    here by a try/except — the user response is never affected.

    Args:
        state: Full AgentState-shaped dict. Required state keys:
            ``shipping_type``, ``weight_kg``, ``fuel_data.price``,
            ``route_data.zone``, ``route_data.traffic_severity``.
        config: LangGraph RunnableConfig — second positional arg LangGraph
            passes when nodes declare it. Optional so the node remains
            invokable from unit tests without a config (auto-eval is
            silently skipped in that path).

    Returns:
        Partial state dict::

            {
                "surcharge_result": SurchargeResult.model_dump(),
                "reasoning_trace": [one_compound_trace_entry],
            }

    Raises:
        ValueError: Propagates from ``lookup_rate`` per D-09 (no rate found,
            invalid weight, etc.). Pricing Agent does NOT wrap this.
    """
    # Defense-in-depth (gap-4 fix from UAT 260503-qzx, 2026-05-03):
    # A misbehaving planner LLM may emit next_step="calculate_price" before
    # route_agent or fuel_agent have run. Without this guard, the subscript
    # reads below raise KeyError ('route_data' or 'fuel_data') which
    # propagates as an SSE error event with no recovery path. Catch the
    # missing-input case here, emit a D-24 error-sink entry, and route to
    # response_node so the user sees a status='partial' answer.
    # Do NOT route back to planner (loop risk with a misbehaving planner).
    route_data = state.get("route_data")
    fuel_data = state.get("fuel_data")
    if not route_data or not fuel_data:
        missing = []
        if not route_data:
            missing.append("route_data")
        if not fuel_data:
            missing.append("fuel_data")
        msg = f"missing {' and '.join(missing)}"
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        prior_steps = len(state.get("reasoning_trace") or [])
        warn_trace = {
            "step": prior_steps + 1,
            "agent": "pricing_agent",
            "tool": None,
            "tool_input": None,
            "tool_output": None,
            "reasoning": (
                f"Pricing agent invoked before required inputs were populated "
                f"({msg}). Planner likely routed to calculate_price prematurely; "
                f"short-circuiting to response with a partial answer."
            ),
            "timestamp": ts,
            "status": "warn",
        }
        return {
            "errors": [{
                "node": "pricing_agent",
                "exception_type": "KeyError",
                "message": msg,
                "timestamp": ts,
            }],
            "next_step": "respond",
            "reasoning_trace": [warn_trace],
        }

    shipping_type = state["shipping_type"]
    weight_kg = state["weight_kg"]
    zone = state["route_data"]["zone"]
    current_diesel_price = state["fuel_data"]["price"]
    traffic_severity = state["route_data"]["traffic_severity"]

    # D-09: let ValueError from lookup_rate propagate (no swallowing).
    rate = lookup_rate(shipping_type, zone, weight_kg)

    surcharge_input = SurchargeInput(
        base_rate=rate.base_rate,
        current_diesel_price=current_diesel_price,
        shipping_type=shipping_type,
        traffic_severity=traffic_severity,
    )

    raw = calculate_surcharge_tool.invoke(surcharge_input.model_dump())
    if isinstance(raw, SurchargeResult):
        surcharge = raw
    elif isinstance(raw, dict):
        surcharge = SurchargeResult.model_validate(raw)
    else:
        # Pydantic-shaped object — try model_validate via dict cast.
        surcharge = SurchargeResult.model_validate(
            raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
        )

    reasoning = _narrate_with_llm(rate, surcharge)

    prior_steps = len(state.get("reasoning_trace") or [])
    trace_entry = {
        "step": prior_steps + 1,
        "agent": "pricing_agent",
        "tool": "lookup_rate+calculate_surcharge",
        "tool_input": surcharge_input.model_dump(),
        "tool_output": surcharge.model_dump(),
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "status": "ok",
    }

    # OBS-03: fire-and-forget formula accuracy auto-eval (D-15).
    # Reads trace_id from RunnableConfig metadata seeded by chat handler
    # (_make_config in routes/chat.py). When invoked outside the chat
    # path (unit tests, scripts) config is None → skip silently.
    try:
        metadata = (config or {}).get("metadata") or {}
        trace_id = metadata.get("langfuse_trace_id")
        if trace_id:
            post_formula_accuracy_score(
                trace_id=trace_id,
                base_rate=rate.base_rate,
                current_diesel_price=current_diesel_price,
                shipping_type=shipping_type,
                traffic_severity=int(traffic_severity),
                agent_result=surcharge.model_dump(),
            )
    except Exception as exc:  # noqa: BLE001 — D-15 fire-and-forget invariant
        logger.warning("formula_accuracy hook (non-fatal): %s", exc)

    return {
        "surcharge_result": surcharge.model_dump(),
        "reasoning_trace": [trace_entry],
    }
