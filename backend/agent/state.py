"""Agent state schema for the LangGraph orchestrator (ORCH-06)."""
from __future__ import annotations

import operator
from typing import List, Literal, Optional, TypedDict

from typing_extensions import Annotated


class AgentState(TypedDict):
    """Central state for the LangGraph agent graph.

    All agent nodes read from and write to this state dict.
    Fields use snake_case per project conventions.
    """

    messages: List[dict]
    """Conversation history (upgrade to BaseMessage in Phase 3)."""

    fuel_data: Optional[dict]
    """FuelData.model_dump() output, or None."""

    route_data: Optional[dict]
    """RouteData.model_dump() output, or None."""

    shipping_type: Optional[str]
    """One of: bounce, retail_standard, retail_fast."""

    weight_kg: Optional[float]
    """Shipment weight in kg."""

    surcharge_result: Optional[dict]
    """SurchargeResult.model_dump() output, or None."""

    reasoning_trace: Annotated[List[dict], operator.add]
    """Steps taken by agents for transparency.

    Uses operator.add as the LangGraph reducer so multiple nodes (including
    parallel Send nodes in Phase 5) can each append their own trace entry
    without stomping each other's writes. See Phase 2 Pitfall 1.
    """

    next_step: str
    """Routing key for conditional edges."""

    origin: Optional[str]
    """Origin location extracted by Planner (D-05). Read by route_agent_node."""

    destination: Optional[str]
    """Destination location extracted by Planner (D-05)."""

    user_intent: Optional[str]
    """Planner-classified intent: surcharge_query | followup_query | clarification | out_of_scope (D-07)."""

    missing_fields: List[str]
    """Fields the user did not provide; populated by Planner for clarify path (D-05)."""

    clarification_reason: Optional[str]
    """Why Planner emitted next_step='clarify' (e.g., 'missing_weight', 'planner_parse_failed') (D-05/D-06)."""

    errors: Annotated[List[dict], operator.add]
    """Retry-exhausted error sink (D-24). Uses operator.add reducer so multiple
    nodes can append. Entry shape: {node, exception_type, message, timestamp}."""

    final_payload: Optional[dict]
    """Final user-facing payload rendered by response_node (D-10). Shape:
    {markdown: str, surcharge_result: dict|None, capped: bool,
    status: 'ok'|'partial'|'clarify'}. Plan 03-04 SSE handler detects this
    key via astream_events to emit the final response chunk."""

    approval_decision: Optional[Literal["approve", "deny"]]
    """D-07 (Phase 5): user's HITL decision when surcharge_result.total
    exceeds HITL_TOTAL_THB_THRESHOLD. None when the gate did not fire
    or has not yet resolved. Written by hitl_gate_node; read by
    response_node to render approve (status='ok' with breakdown) or
    deny (status='partial' with decline prose) paths."""

    search_context: Optional[dict]
    """D-11 (Phase 5): Tavily search result for news/market intent
    queries. None when the planner did not route to search_context or
    when the Tavily call failed. Shape (matches SearchResult Pydantic
    model in backend/agent/tools/models.py):
        {
          "query": str,
          "summary": Optional[str],
          "sources": List[{"title": str, "url": str, "snippet": str,
                           "published_at": Optional[str]}],
          "fetched_at": str  # ISO-8601 UTC 'Z' per Phase 3 D-13
        }
    Written by search_agent_node; read by response_node to prepend a
    market-context line above the prose answer."""

    guard_decision: Optional[dict]
    """Quick task 260509-utd: last verdict from guard_input or guard_output.

    Shape::

        {
          "layer": "input" | "output",
          "category": str,           # see GuardCategory in guard_input.py
          "refused": bool,
          "violations": List[str],   # populated by guard_output only
        }

    Read by ``response_node`` to render the polite-refusal copy when
    ``refused=True`` (status='refused' for input layer, 'guard_failed'
    for output). No reducer — last-write-wins is correct because each
    node reads + writes its own decision and only one guard runs per
    superstep.
    """

    tool_call_count: Annotated[int, operator.add]
    """Quick task 260509-utd: per-turn cumulative tool invocation count.

    Bumped by fuel/route/search/pricing agents — each emits ``+1`` from
    its own return dict (NOT the absolute new value); the ``operator.add``
    reducer aggregates concurrent writes correctly under the Phase 5 D-01
    parallel fan-out (fuel + route both bump in the same superstep). On
    sequential supersteps the reducer simply accumulates one delta at a
    time, so the running total still equals the number of tool calls
    across the turn. Checked by ``guard_input`` against
    ``MAX_TOOL_CALLS_PER_TURN`` to defend against cost-bombing inputs.

    ``guard_input`` resets the counter at the start of a fresh user turn
    by emitting a NEGATIVE delta equal to ``-state.tool_call_count`` (so
    the new accumulated total lands at 0). This stays consistent with
    the operator.add contract — the alternative of using a non-additive
    reducer would break under fan-out (two concurrent writes per step).
    """

    origin_hub_id: Optional[str]
    """Phase 999.9 (D-08/D-09/D-10): chosen origin hub identifier (e.g.,
    'hq-lat-krabang', 'branch-bang-na'). Resolved by Planner from
    prose extraction (D-10) or seeded from ChatRequest.origin_hub_id
    (D-08) at the API boundary. Pricing Agent reads this to derive
    origin_zone via origin_zone_for(hub_id) before calling lookup_rate.

    None means dropdown not yet picked AND prose did not specify —
    pricing_agent silently defaults to 'hq-lat-krabang' (D-09) and
    narrates the assumption in the reasoning trace. The API boundary
    ALSO defaults to 'hq-lat-krabang' (Pitfall 1 mitigation), so in
    practice state.origin_hub_id is always non-None at planner entry."""
