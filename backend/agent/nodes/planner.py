"""ORCH-01: Planner node.

Implements:
- D-01: PlannerOutput Pydantic schema (next_step + extracted inputs).
- D-02: One-retry Gemini parse fallback to next_step=clarify on persistent
  parse failure.
- D-04: PLANNER_MAX_ITERATIONS loop budget — when the CURRENT turn (entries
  since last agent='response') already contains >= PLANNER_MAX_ITERATIONS - 1
  planner-tagged entries, force next_step=respond WITHOUT calling Gemini.
  Windowed per turn (999.4 fix 2026-04-25) so cross-turn reasoning_trace
  accumulation doesn't short-circuit turn 2 of a same-thread conversation.
- D-12: Cache-aware skip — when state.fuel_data is fresher than
  FUEL_DATA_TTL_SECONDS, override LLM-emitted next_step=fetch_fuel; when
  state.route_data origin/destination match the merged values, override
  next_step=fetch_route.
- 999.1 fix (2026-04-25): post-LLM recompute of missing_fields and
  next_step from merged values so follow-up turns honour cached state.
- 999.3 fix (2026-04-25): trace tool_output reflects post-override
  next_step and merged extraction fields, not the raw LLM emission.
- 999.4 fix (2026-04-25): _loop_budget_exhausted now windows the count to
  planner-tagged entries within the current turn, not the cumulative trace.

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
from backend.agent.prompts.guard import REFUSAL_COPY
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
        "surcharge_query",
        "followup_query",
        "clarification",
        "out_of_scope",
        "news_query",
    ]
    shipping_type: Optional[str] = None
    weight_kg: Optional[float] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    # Phase 999.9 D-10: structured hub identifier extracted from prose
    # ("ship from Bang Na to Nonthaburi" -> "branch-bang-na"). Null when
    # the user did not mention a hub; the post-processor falls back to
    # the dropdown / API-boundary default.
    origin_hub_id: Optional[str] = None
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
    """True if state.route_data matches the (origin, destination) pair.

    Phase 999.9 D-04: cache hit is driven by ``origin_hub_id`` when
    available — the route_data's ``origin_hub_id`` field is set by
    calculate_route from its argument; ``state["origin_hub_id"]`` is
    seeded by the API boundary or planner extraction. The legacy
    free-text ``state["origin"]`` is no longer load-bearing for
    routing, so we fall back to the legacy origin compare ONLY when
    neither side carries an ``origin_hub_id`` (e.g., pre-999.9 cached
    entries replayed in tests).
    """
    rd = state.get("route_data")
    if not rd or not destination:
        return False
    if rd.get("destination") != destination:
        return False
    state_hub = state.get("origin_hub_id")
    rd_hub = rd.get("origin_hub_id")
    if state_hub and rd_hub:
        return rd_hub == state_hub
    # Legacy fallback: compare on free-text origin. Used only when neither
    # side has hub_id information (pre-999.9 RouteData payloads).
    if not origin:
        return False
    return rd.get("origin") == origin


def _loop_budget_exhausted(state: dict) -> bool:
    """D-04: True when planner has run >= MAX-1 times in the CURRENT turn.

    999.4 fix (2026-04-25): the reasoning_trace reducer is operator.add
    (Phase 2 design — cumulative trace for the UI panel persists across
    turns), so a length-only check would short-circuit turn 2 of a
    same-thread conversation before the planner LLM is invoked. D-04's
    documented intent is to cap planner *iterations within one user
    request*, so we window the count to "entries since the most recent
    agent='response' entry" (or the entire trace if no response yet).
    """
    trace = state.get("reasoning_trace") or []
    last_response_idx = -1
    for i in range(len(trace) - 1, -1, -1):
        if trace[i].get("agent") == "response":
            last_response_idx = i
            break
    current_turn = trace[last_response_idx + 1:]
    planner_count = sum(
        1 for e in current_turn if e.get("agent") == "planner"
    )
    return planner_count >= PLANNER_MAX_ITERATIONS - 1


def _set_guard_refusal(category: str) -> dict:
    """Phase 999.10 D-01/D-09/D-10: build the guard_decision dict that the
    planner emits on its two new refusal triggers (out_of_scope user_intent
    and parse_failed retry exhaustion).

    Returns the state-partial dict to merge into the planner's return value.
    The shape MUST match guard_input_node's verdict shape (guard_input.py
    lines 218-223) so response_node's existing refusal branch (response_node
    .py:243) renders REFUSAL_COPY with status='refused' (layer='input').

    D-10: layer stays 'input' for planner-tripped refusals too — category
    is the differentiator, not layer.
    """
    return {
        "next_step": "respond",
        "guard_decision": {
            "layer": "input",
            "refused": True,
            "category": category,
            "violations": [],
        },
    }


_REFUSAL_PROSE_PREFIX = REFUSAL_COPY.split("?")[0][:48].strip()


def _parse_structured(raw: str) -> PlannerOutput:
    """Parse a JSON string into PlannerOutput.

    Strips Markdown code fences Gemini sometimes emits (```json ... ```).
    Mirrors the helper in fuel_agent for consistency.

    Phase 999.10 prose-refusal salvage: SECURITY_PREAMBLE rule 1 tells
    Gemini to return REFUSAL_COPY verbatim as prose for out-of-scope
    inputs. The planner SYSTEM_PROMPT contract (D-01) requires JSON.
    When Gemini obeys the higher-priority security rule over the schema
    contract, this helper recognises the canonical refusal prose and
    synthesises an out_of_scope PlannerOutput so D-04 (planner_off_topic)
    fires instead of D-05 (planner_parse_failed). The user-facing
    contract is identical either way; this preserves observability
    granularity in guard_decision.category.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if text.startswith(_REFUSAL_PROSE_PREFIX):
        return PlannerOutput(
            user_intent="out_of_scope",
            next_step="respond",
            clarification_reason="out_of_scope_user_request",
        )
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

    # gap-3 fix (2026-05-03): when search_agent has already populated
    # state.search_context for a news/out-of-scope query, the next planner
    # iteration should advance to respond — NOT re-route to search_context
    # again, which would loop until D-04 budget exhausts (UAT test 6).
    # The guard accepts BOTH 'news_query' (the new dedicated intent value
    # added by this plan) AND 'out_of_scope' (the legacy bucket the LLM
    # uses today before being retrained on the updated SYSTEM_PROMPT).
    # Surcharge queries with search_context (a future hybrid flow) MUST
    # NOT short-circuit here because the user still wants a surcharge.
    # We append a minimal trace entry so observability sees "planner ran
    # twice, second was a short-circuit" — informative for Langfuse demos
    # AND consumed by the integration test's planner_count == 2 assertion.
    if (
        state.get("search_context") is not None
        and state.get("user_intent") in {"news_query", "out_of_scope"}
    ):
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        prior_steps = len(state.get("reasoning_trace") or [])
        short_circuit_trace = {
            "step": prior_steps + 1,
            "agent": "planner",
            "tool": None,
            "tool_input": None,
            "tool_output": None,
            "reasoning": "search_context populated; routing to respond",
            "timestamp": ts,
            "status": "ok",
        }
        return {
            "next_step": "respond",
            "reasoning_trace": [short_circuit_trace],
        }

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
                # Phase 999.10 D-05: parse_failed exhaustion now refuses
                # (unconditionally on this branch) instead of clarifying.
                # Refusal is rendered by response_node via state.guard_decision.
                logger.info(
                    "planner refusing on parse_failed exhaustion"
                )
                return _set_guard_refusal("planner_parse_failed")

    assert parsed is not None  # for type checkers; loop break/return covers all paths

    # Phase 999.10 D-04: when the LLM classified the message as out_of_scope,
    # short-circuit to the response_node refusal branch via guard_decision.
    # This replaces the pre-999.10 fall-through where out_of_scope ran the
    # full 999.1 merge + 999.3 trace emission and surfaced as
    # next_step='clarify' (the generic clarify copy).
    # D-11: planner emits NO refusal trace entry of its own — response_node
    # emits the refusal trace tagged agent='response' (mirrors existing
    # guard_input -> response_node refusal flow).
    if parsed.user_intent == "out_of_scope":
        logger.info(
            "planner refusing on user_intent=out_of_scope"
        )
        return _set_guard_refusal("planner_off_topic")

    # Phase 999.9 D-10 / RESEARCH Pattern 2: validate origin_hub_id against
    # the _HUB_INDEX allowlist. On invalid, set to None so the 999.1 merge
    # falls through to state.get("origin_hub_id"), then to the API-boundary
    # default 'hq-lat-krabang' if the chat handler did not seed one.
    if parsed.origin_hub_id is not None:
        from backend.agent.tools.hubs import _HUB_INDEX
        if parsed.origin_hub_id not in _HUB_INDEX:
            logger.warning(
                "planner emitted invalid origin_hub_id=%r; allowed=%s; "
                "discarding (will fall back via 999.1 merge)",
                parsed.origin_hub_id, sorted(_HUB_INDEX),
            )
            parsed.origin_hub_id = None

    # gap-1 fix (2026-05-03): null-out hallucinated extraction fields on
    # followup_query turns BEFORE the 999.1 merge picks them up. The 999.1
    # merge is a null-only coalesce (`parsed.X or state.get("X")`); if the
    # LLM hallucinates truthy values for fields the user did not mention,
    # the merge will accept them. The planner SYSTEM_PROMPT now instructs
    # the LLM to emit null for unmentioned fields on followup_query, but
    # we defensively null them out here too in case Gemini ignores the
    # contract. This branch is null-only — explicit overrides (non-null
    # parsed.X on a followup) still win because we only erase parsed.X
    # when the prior state has a value AND the user message does not
    # contain a recognisable shipping_type / origin / destination token.
    if parsed.user_intent == "followup_query":
        last_user_text = (last_user.get("content") or "").lower()
        # shipping_type tokens
        if (
            parsed.shipping_type
            and state.get("shipping_type")
            and parsed.shipping_type.lower() not in last_user_text
            and not any(
                tok in last_user_text
                for tok in ("bounce", "retail_standard", "retail standard",
                            "retail_fast", "retail fast")
            )
        ):
            parsed.shipping_type = None
        # destination — if prior state has destination and user message
        # does not contain that destination's token NOR any "to <X>" pattern,
        # null it out so the inherited destination wins
        prior_dest = state.get("destination")
        if (
            parsed.destination
            and prior_dest
            and prior_dest.lower() not in last_user_text
            and parsed.destination.lower() not in last_user_text
        ):
            parsed.destination = None
        # origin — same logic
        prior_origin = state.get("origin")
        if (
            parsed.origin
            and prior_origin
            and prior_origin.lower() not in last_user_text
            and parsed.origin.lower() not in last_user_text
        ):
            parsed.origin = None
        # weight_kg — if user message contains digits and parsed.weight_kg
        # is non-null, accept it; otherwise null it out so prior weight inherits.
        # We trust digits as the explicit override signal.
        if (
            parsed.weight_kg is not None
            and state.get("weight_kg") is not None
            and not any(c.isdigit() for c in last_user_text)
        ):
            parsed.weight_kg = None
        # Phase 999.9 / Pitfall 2: origin_hub_id follow-up inheritance. If
        # parsed.origin_hub_id is non-null but the user message doesn't
        # contain any of the 10 hub-address tokens AND prior state has a
        # different hub_id, null out the parsed value so the prior wins
        # via the 999.1 merge below. Mirrors the shipping_type / origin /
        # destination patterns above (D-08 token-detection allow-list).
        prior_hub = state.get("origin_hub_id")
        if (
            parsed.origin_hub_id
            and prior_hub
            and prior_hub != parsed.origin_hub_id
        ):
            from backend.agent.tools.hubs import _HUB_INDEX
            hub_mentioned = False
            for h_data in _HUB_INDEX.values():
                # Check ALL comma-separated address tokens (e.g.,
                # "Mueang Nonthaburi, Nonthaburi" yields "mueang nonthaburi"
                # AND "nonthaburi"). Users typically refer to the province
                # rather than the muang prefix.
                addr_lower = h_data["address"].lower()
                tokens = [
                    tok.strip() for tok in addr_lower.split(",") if tok.strip()
                ]
                # Also include the bare province (e.g., "nonthaburi") split
                # off the leading "mueang " prefix.
                expanded = list(tokens)
                for tok in tokens:
                    if tok.startswith("mueang "):
                        expanded.append(tok[len("mueang "):].strip())
                if any(tok and tok in last_user_text for tok in expanded):
                    hub_mentioned = True
                    break
            if not hub_mentioned:
                parsed.origin_hub_id = None

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
    # Phase 999.9 D-10 / Pitfall 2: 999.1 null-only merge for origin_hub_id.
    # The API boundary seeds 'hq-lat-krabang' as a default, so the merged
    # value is almost always non-None at planner exit (Pitfall 1).
    merged_origin_hub_id = parsed.origin_hub_id or state.get("origin_hub_id")

    # 999.1 fix: recompute missing_fields from merged values, not from the
    # LLM's per-message emission.
    missing: List[str] = []
    if not merged_shipping:
        missing.append("shipping_type")
    if merged_weight is None:
        missing.append("weight_kg")
    # Phase 999.9 D-09/D-10: origin is satisfied if EITHER prose-level
    # origin OR origin_hub_id is set. The API boundary seeds
    # origin_hub_id='hq-lat-krabang' as a default (Pitfall 1), and the
    # dropdown supplies it for non-HQ branches — in both cases the
    # downstream graph (route_agent, pricing_agent) reads origin_hub_id
    # directly via origin_string_for(), so prose-origin is decorative.
    if not merged_origin and not merged_origin_hub_id:
        missing.append("origin")
    if not merged_destination:
        missing.append("destination")

    # 999.1 fix: if the LLM said clarify but the merged state has all four
    # fields, promote next_step to fetch_fuel so the existing D-12 override
    # below can cascade to fetch_route / calculate_price based on cache state.
    next_step = parsed.next_step
    if next_step == "clarify" and not missing:
        next_step = "fetch_fuel"

    # Phase 5 D-01: parallel fan-out promotion. When the LLM emits
    # fetch_fuel or fetch_route (signalling a surcharge_query path) AND
    # neither fuel nor route is cached, promote next_step to the
    # "fanout_fuel_route" sentinel. The list-returning conditional edge
    # in graph.py picks this up and schedules both nodes in the same
    # superstep. Required pre-conditions: shipping_type, weight, origin,
    # destination all present (otherwise we'd race ahead of clarification).
    if (
        next_step in ("fetch_fuel", "fetch_route")
        and not _fuel_fresh(state)
        and not _route_matches(state, merged_origin, merged_destination)
        and merged_shipping
        and merged_weight is not None
        and (merged_origin or merged_origin_hub_id)
        and merged_destination
    ):
        next_step = "fanout_fuel_route"

    # D-12 cache-aware override on (possibly promoted) next_step. Uses
    # merged_origin/merged_destination so route-cache hits work on
    # follow-ups where origin/destination were inherited from prior state.
    # Note: when next_step="fanout_fuel_route" (Phase 5 D-01) neither branch
    # below matches, so the sequential cache-skip cascade is preserved.
    #
    # Phase 5 D-09: search_context is intent-driven, not state-driven —
    # skip the cache-aware override entirely so news/market questions
    # always reach the search_agent regardless of fuel/route cache state.
    if next_step != "search_context":
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
        # Phase 999.9 D-10: surface the merged hub_id so downstream
        # agents (route_agent, pricing_agent) read the consistent value.
        "origin_hub_id": merged_origin_hub_id,
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
                    "origin_hub_id": merged_origin_hub_id,  # Phase 999.9
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
