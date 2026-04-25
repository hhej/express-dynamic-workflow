"""ORCH-01: Planner node.

Implements:
- D-01: PlannerOutput Pydantic schema (next_step + extracted inputs).
- D-02: One-retry Gemini parse fallback to next_step=clarify on persistent
  parse failure.
- D-04: PLANNER_MAX_ITERATIONS loop budget — when reasoning_trace already has
  >= PLANNER_MAX_ITERATIONS - 1 entries, force next_step=respond WITHOUT
  calling Gemini.
- D-12: Cache-aware skip — when state.fuel_data is fresher than
  FUEL_DATA_TTL_SECONDS, override LLM-emitted next_step=fetch_fuel; when
  state.route_data origin/destination match the merged values, override
  next_step=fetch_route.
- 999.1 fix (2026-04-25): post-LLM recompute of missing_fields and
  next_step from merged values so follow-up turns honour cached state.
- 999.3 fix (2026-04-25): trace tool_output reflects post-override
  next_step and merged extraction fields, not the raw LLM emission.

Test seam: tests monkeypatch ``get_chat_model`` in this module's namespace
and feed scripted ``FakeMessagesListChatModel`` instances; mirrors the
Phase 2 fuel/route agent test pattern (D-16 — no live Gemini in CI).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from backend.agent.llm import get_chat_model
from backend.agent.prompts.planner import SYSTEM_PROMPT
from backend.config import FUEL_DATA_TTL_SECONDS, PLANNER_MAX_ITERATIONS

__all__ = ["planner_node", "PlannerOutput"]

logger = logging.getLogger(__name__)


class PlannerOutput(BaseModel):
    """Locked Planner output schema (D-01).

    The model is permissive on optional extraction fields (any may be None
    when the user did not provide them) but enforces the next_step
    vocabulary via Literal — invalid next_step values raise ValidationError
    and trigger the D-02 retry/fallback path.
    """

    user_intent: Literal[
        "surcharge_query", "followup_query", "clarification", "out_of_scope"
    ]
    shipping_type: Optional[str] = None
    weight_kg: Optional[float] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    next_step: Literal[
        "fetch_fuel",
        "fetch_route",
        "calculate_price",
        "clarify",
        "respond",
        "search_context",
    ]
    clarification_reason: Optional[str] = None


def _fuel_fresh(state: dict) -> bool:
    """True if state.fuel_data has a fetched_at < FUEL_DATA_TTL_SECONDS old."""
    fd = state.get("fuel_data")
    if not fd or "fetched_at" not in fd:
        return False
    try:
        fetched = datetime.fromisoformat(
            fd["fetched_at"].replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return False
    age_s = (datetime.now(timezone.utc) - fetched).total_seconds()
    return age_s < FUEL_DATA_TTL_SECONDS


def _route_matches(
    state: dict, origin: Optional[str], destination: Optional[str]
) -> bool:
    """True if state.route_data has matching origin and destination."""
    rd = state.get("route_data")
    if not rd or not origin or not destination:
        return False
    return rd.get("origin") == origin and rd.get("destination") == destination


def _loop_budget_exhausted(state: dict) -> bool:
    """D-04: True when reasoning_trace already has >= MAX-1 entries.

    Rough proxy: 1 planner step + ≤4 specialist steps + 1 respond = ≤6
    (PLANNER_MAX_ITERATIONS default). Once we have 5 entries, the *next*
    planner invocation would push us over budget — force respond instead.
    """
    return (
        len(state.get("reasoning_trace") or []) >= PLANNER_MAX_ITERATIONS - 1
    )


def _parse_structured(raw: str) -> PlannerOutput:
    """Parse a JSON string into PlannerOutput.

    Strips Markdown code fences Gemini sometimes emits (```json ... ```).
    Mirrors the helper in fuel_agent for consistency.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return PlannerOutput.model_validate(json.loads(text))


def planner_node(state: dict) -> dict:
    """Planner node: classify intent, extract inputs, route to next agent.

    Args:
        state: Full AgentState-shaped dict.

    Returns:
        Partial state dict with extracted fields, ``next_step``, and (on
        successful parse) one D-12 trace entry. Returns *no* trace entry
        for the D-04 budget-exhausted path or the D-02 parse-failed
        fallback — both are explicit operational fallbacks.
    """
    # D-24: if a downstream node's error sink already populated state.errors,
    # immediately route to respond so the Response Node can render
    # status='partial'. This guard runs BEFORE the Gemini call so we don't
    # consume a planner-loop iteration on a state we know is already done.
    if state.get("errors"):
        return {"next_step": "respond"}

    # D-04 loop budget guard runs BEFORE any Gemini call.
    if _loop_budget_exhausted(state):
        return {
            "next_step": "respond",
            "clarification_reason": "planner_loop_budget_exhausted",
        }

    messages = state.get("messages") or []
    last_user = next(
        (m for m in reversed(messages) if m.get("role") == "user"), None
    )
    if not last_user:
        return {
            "next_step": "clarify",
            "clarification_reason": "no_user_message",
        }

    # D-02: one-retry Gemini parse, then fall back to clarify.
    parsed: Optional[PlannerOutput] = None
    for attempt in (1, 2):
        try:
            model = get_chat_model()
            response = model.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=last_user["content"]),
                ]
            )
            content = getattr(response, "content", response)
            if not isinstance(content, str):
                content = str(content)
            parsed = _parse_structured(content)
            break
        except (Exception, ValidationError) as exc:
            logger.warning(
                "planner parse attempt %d failed: %s", attempt, exc
            )
            if attempt == 2:
                return {
                    "next_step": "clarify",
                    "clarification_reason": "planner_parse_failed",
                }

    assert parsed is not None  # for type checkers; loop break/return covers all paths

    # 999.1 fix: merge parsed (latest user message) with prior state values
    # BEFORE deciding next_step. The LLM only sees the latest user message,
    # so on follow-up turns it emits null for unmentioned fields and routes
    # to clarify; the post-LLM merge fills the gaps from prior state and
    # the recompute below promotes next_step accordingly.
    merged_shipping = parsed.shipping_type or state.get("shipping_type")
    merged_weight = (
        parsed.weight_kg
        if parsed.weight_kg is not None
        else state.get("weight_kg")
    )
    merged_origin = parsed.origin or state.get("origin")
    merged_destination = parsed.destination or state.get("destination")

    # 999.1 fix: recompute missing_fields from merged values, not from the
    # LLM's per-message emission.
    missing: List[str] = []
    if not merged_shipping:
        missing.append("shipping_type")
    if merged_weight is None:
        missing.append("weight_kg")
    if not merged_origin:
        missing.append("origin")
    if not merged_destination:
        missing.append("destination")

    # 999.1 fix: if the LLM said clarify but the merged state has all four
    # fields, promote next_step to fetch_fuel so the existing D-12 override
    # below can cascade to fetch_route / calculate_price based on cache state.
    next_step = parsed.next_step
    if next_step == "clarify" and not missing:
        next_step = "fetch_fuel"

    # D-12 cache-aware override on (possibly promoted) next_step. Uses
    # merged_origin/merged_destination so route-cache hits work on
    # follow-ups where origin/destination were inherited from prior state.
    if next_step == "fetch_fuel" and _fuel_fresh(state):
        # Fuel is cached and fresh — advance to next logical step.
        if _route_matches(state, merged_origin, merged_destination):
            # Route also cached: only need pricing (assuming inputs present).
            if merged_shipping and merged_weight is not None:
                next_step = "calculate_price"
            else:
                next_step = "clarify"
        else:
            next_step = "fetch_route"
    elif next_step == "fetch_route" and _route_matches(
        state, merged_origin, merged_destination
    ):
        next_step = "calculate_price" if _fuel_fresh(state) else "fetch_fuel"

    prior = len(state.get("reasoning_trace") or [])
    return {
        "user_intent": parsed.user_intent,
        "shipping_type": merged_shipping,
        "weight_kg": merged_weight,
        "origin": merged_origin,
        "destination": merged_destination,
        "missing_fields": missing,
        "clarification_reason": parsed.clarification_reason,
        "next_step": next_step,
        "reasoning_trace": [
            {
                "step": prior + 1,
                "agent": "planner",
                "tool": None,
                "tool_input": {},
                # 999.3 fix: trace tool_output reflects post-override
                # next_step + merged extraction fields, not the raw LLM
                # emission. Mirrors what this function returns to the graph.
                "tool_output": {
                    "user_intent": parsed.user_intent,
                    "shipping_type": merged_shipping,
                    "weight_kg": merged_weight,
                    "origin": merged_origin,
                    "destination": merged_destination,
                    "missing_fields": missing,
                    "next_step": next_step,
                    "clarification_reason": parsed.clarification_reason,
                },
                "reasoning": (
                    f"Intent={parsed.user_intent}; routing to {next_step}"
                ),
                "timestamp": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "status": "ok",
            }
        ],
    }
