"""Tests for ORCH-01: Planner node.

Covers D-01 (PlannerOutput schema), D-02 (one-retry parse fallback to clarify),
D-04 (PLANNER_MAX_ITERATIONS loop budget guard), and D-12 (cache-aware skip
of fetch_fuel / fetch_route when state.fuel_data / state.route_data is fresh).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from backend.agent.nodes import planner as mod
from backend.agent.nodes.planner import planner_node


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _scripted_llm(*responses_json: str) -> FakeMessagesListChatModel:
    return FakeMessagesListChatModel(
        responses=[AIMessage(content=r) for r in responses_json]
    )


def _user_state(content: str, **overrides) -> dict:
    base = {
        "messages": [{"role": "user", "content": content}],
        "fuel_data": None,
        "route_data": None,
        "shipping_type": None,
        "weight_kg": None,
        "surcharge_result": None,
        "reasoning_trace": [],
        "next_step": "",
        "origin": None,
        "destination": None,
        "user_intent": None,
        "missing_fields": [],
        "clarification_reason": None,
        "errors": [],
    }
    base.update(overrides)
    return base


def test_routes_to_fetch_fuel_on_fresh_query(monkeypatch):
    """No fuel_data, no route_data, all extraction fields present -> Phase 5
    D-01 promotes next_step to 'fanout_fuel_route' (parallel Fuel + Route
    fan-out). Extraction fields are still surfaced unchanged.

    Phase 3 baseline asserted next_step='fetch_fuel'; Phase 5 ORCH-07 adds the
    fan-out promotion right before the D-12 cache-skip block, so a fresh
    thread with complete inputs now emits the parallel sentinel instead of the
    sequential fetch_fuel routing.
    """
    state = _user_state("Surcharge for 15kg Bounce Bangkok to Nonthaburi")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 15, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    # Phase 5 D-01: fan-out sentinel replaces fetch_fuel on a fresh thread
    # with both caches absent and all extraction fields present.
    assert result["next_step"] == "fanout_fuel_route"
    assert result["shipping_type"] == "bounce"
    assert result["weight_kg"] == 15
    assert result["origin"] == "Bangkok"
    assert result["destination"] == "Nonthaburi"
    assert result["user_intent"] == "surcharge_query"
    assert result["reasoning_trace"][0]["agent"] == "planner"


def test_skips_fetch_when_fuel_fresh(monkeypatch):
    """D-12: state.fuel_data has fresh fetched_at; LLM says fetch_fuel but
    Planner OVERRIDES to fetch_route (because route_data is missing).

    Phase 11 / FIX-02: state must carry at least one prior logistics
    field (here: shipping_type='bounce' from a prior follow-up turn)
    so the destination-less short-circuit (added in 999.11-03) does
    NOT fire. The legit-baseline bug fix only short-circuits when
    state has NO logistics fields — a follow-up surcharge with a
    prior shipping_type extracted must still flow into the cache-aware
    override + fetch_route routing exercised by this test.
    """
    state = _user_state(
        "Surcharge for 15kg Bounce Bangkok to Nonthaburi",
        fuel_data={
            "price": 31.0,
            "baseline": 29.94,
            "delta_pct": 0.0354,
            "date": "2026-04-18",
            "unit": "THB/L",
            "source": "eppo_cached_csv",
            "fetched_at": _now_iso_z(),
        },
        shipping_type="bounce",  # FIX-02: prior logistics field present
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 15, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    # D-12: fuel is fresh, so fetch_fuel is skipped; route is not cached, so
    # next_step becomes fetch_route.
    assert result["next_step"] == "fetch_route"
    assert result["reasoning_trace"][0]["agent"] == "planner"


def test_emits_clarify_on_missing_fields(monkeypatch):
    """LLM returns next_step=clarify with missing_fields=['weight_kg'];
    Planner returns next_step=clarify and surfaces the clarification_reason."""
    state = _user_state("How much is shipping Bangkok to Nonthaburi via Bounce?")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": null, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": ["weight_kg"], '
            '"next_step": "clarify", '
            '"clarification_reason": "missing_weight"}'
        ),
    )

    result = planner_node(state)

    assert result["next_step"] == "clarify"
    assert result["clarification_reason"] == "missing_weight"
    assert "weight_kg" in result["missing_fields"]
    assert result["reasoning_trace"][0]["agent"] == "planner"


def test_origin_hub_id_satisfies_origin_requirement(monkeypatch):
    """Phase 999.9 D-09/D-10 regression: when prose has no origin but the
    API boundary or dropdown supplies origin_hub_id, the planner must
    treat origin as satisfied (no missing_fields=['origin']) and route to
    fanout_fuel_route, not clarify.

    Reproduces the Wave 4 human-verify gap where Flow 2a (dropdown only,
    no prose origin) and Flow 4 (default-seeded HQ, no prose origin)
    both clarified instead of computing surcharge.
    """
    state = _user_state(
        "Ship 5kg bounce to Nonthaburi",
        origin_hub_id="branch-ayutthaya",
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 5, '
            '"origin": null, "destination": "Nonthaburi", '
            '"origin_hub_id": null, '
            '"missing_fields": ["origin"], '
            '"next_step": "clarify", '
            '"clarification_reason": "Missing origin"}'
        ),
    )

    result = planner_node(state)

    assert "origin" not in result["missing_fields"]
    assert result["missing_fields"] == []
    assert result["origin_hub_id"] == "branch-ayutthaya"
    assert result["next_step"] == "fanout_fuel_route"


def test_loop_budget_exhaustion_forces_respond(monkeypatch):
    """D-04 (windowed per turn, 999.4): when the CURRENT turn already contains
    >= PLANNER_MAX_ITERATIONS-1 planner-tagged entries (with no intervening
    agent='response' entry), Planner returns next_step=respond WITHOUT calling
    Gemini."""
    # PLANNER_MAX_ITERATIONS default is 6, so 5 planner-tagged entries in the
    # current turn (no response yet) triggers the guard.
    state = _user_state(
        "Anything",
        reasoning_trace=[
            {"step": i + 1, "agent": "planner"} for i in range(5)
        ],
    )

    mock_factory = MagicMock()
    monkeypatch.setattr(mod, "get_chat_model", mock_factory)

    result = planner_node(state)

    assert result["next_step"] == "respond"
    assert result["clarification_reason"] == "planner_loop_budget_exhausted"
    # No Gemini call should occur
    assert mock_factory.call_count == 0


def test_loop_budget_resets_after_response_entry(monkeypatch):
    """999.4: per-turn windowing — a 6-entry trace ending in agent='response'
    means turn 2 starts fresh; planner_count_in_current_turn = 0, so the
    guard MUST NOT fire and the LLM MUST be invoked."""
    # Simulate a complete turn 1: planner + fuel + planner + route + pricing + response (6 entries).
    # Note: agent values are the trace tags written by each node.
    state = _user_state(
        "What if Retail Standard?",
        shipping_type="bounce",
        weight_kg=15.0,
        origin="Bangkok",
        destination="Pathum Thani",
        reasoning_trace=[
            {"step": 1, "agent": "planner"},
            {"step": 2, "agent": "fuel_agent"},
            {"step": 3, "agent": "planner"},
            {"step": 4, "agent": "route_agent"},
            {"step": 5, "agent": "pricing_agent"},
            {"step": 6, "agent": "response"},
        ],
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "followup_query", '
            '"shipping_type": "retail_standard", "weight_kg": null, '
            '"origin": null, "destination": null, '
            '"missing_fields": ["weight_kg", "origin", "destination"], '
            '"next_step": "clarify", '
            '"clarification_reason": "missing_inputs"}'
        ),
    )

    result = planner_node(state)

    # Guard did NOT fire — clarification_reason is NOT the budget-exhaustion sentinel.
    assert result.get("clarification_reason") != "planner_loop_budget_exhausted"
    # LLM ran; 999.1 merge fills the missing fields from prior state, then
    # Phase 5 D-01 promotes the resulting fetch_fuel to fanout_fuel_route
    # because both caches are absent and all four extraction fields are present.
    # Either way, the path through the LLM produced a real next_step (not the
    # short-circuit "respond" + budget-exhausted clarification_reason).
    assert result["next_step"] == "fanout_fuel_route"
    # The new planner entry was appended (not the empty short-circuit return).
    assert "reasoning_trace" in result
    assert result["reasoning_trace"][0]["agent"] == "planner"


def test_parse_failure_refuses_unconditionally(monkeypatch):
    """Phase 999.10 D-05: Gemini returns invalid JSON twice; planner now
    refuses via state.guard_decision (category='planner_parse_failed') and
    routes to respond instead of returning clarify-with-reason. Refusal is
    UNCONDITIONAL on this branch (no further conditioning on user message)."""
    state = _user_state("Surcharge for 15kg Bounce Bangkok to Nonthaburi")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm("not json", "still not json"),
    )

    result = planner_node(state)

    assert result["next_step"] == "respond"
    assert result["guard_decision"] == {
        "layer": "input",
        "refused": True,
        "category": "planner_parse_failed",
        "violations": [],
    }
    # No clarification_reason: refusal replaces the old clarify path.
    assert result.get("clarification_reason") in (None, "")


# ---------------------------------------------------------------------------
# 999.1 / 999.3 regression tests (added 2026-04-25 via quick task 260425-vyj)
# ---------------------------------------------------------------------------


def test_followup_merges_prior_state_promotes_clarify_to_fetch(monkeypatch):
    """999.1: on a parameter-switch follow-up, the LLM emits clarify-with-nulls
    because it only sees the latest user message; the post-LLM merge fills the
    gaps from prior state, and the recompute MUST promote next_step to
    fetch_fuel (no caches in state) instead of clarify."""
    state = _user_state(
        "What if Retail Standard?",
        shipping_type="bounce",
        weight_kg=15.0,
        origin="Bangkok",
        destination="Pathum Thani",
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "followup_query", '
            '"shipping_type": "retail_standard", "weight_kg": null, '
            '"origin": null, "destination": null, '
            '"missing_fields": ["weight_kg", "origin", "destination"], '
            '"next_step": "clarify", '
            '"clarification_reason": "missing_inputs"}'
        ),
    )

    result = planner_node(state)

    # 999.1: promoted from clarify to fetch_fuel; Phase 5 D-01 then promotes
    # again to fanout_fuel_route (no caches, all 4 merged fields present).
    assert result["next_step"] == "fanout_fuel_route"
    # 999.1: missing_fields recomputed from merged values, not from LLM emission.
    assert result["missing_fields"] == []
    # Merge produces the new shipping_type from LLM + inherited fields from state.
    assert result["shipping_type"] == "retail_standard"
    assert result["weight_kg"] == 15.0
    assert result["origin"] == "Bangkok"
    assert result["destination"] == "Pathum Thani"


def test_followup_with_full_cache_routes_calculate_price(monkeypatch):
    """999.1 + D-12: full prior state with fresh fuel_data and matching
    route_data; LLM emits clarify-with-nulls (parameter-switch reproducer);
    promotion to fetch_fuel + D-12 cascade should route to calculate_price."""
    state = _user_state(
        "What if Retail Standard?",
        shipping_type="bounce",
        weight_kg=15.0,
        origin="Bangkok",
        destination="Pathum Thani",
        fuel_data={
            "price": 31.0,
            "baseline": 29.94,
            "delta_pct": 0.0354,
            "date": "2026-04-25",
            "unit": "THB/L",
            "source": "eppo_live",
            "fetched_at": _now_iso_z(),
        },
        route_data={
            "origin": "Bangkok",
            "destination": "Pathum Thani",
            "distance_km": 32.0,
            "duration_min": 45,
            "traffic_severity": 2,
            "zone": "central-1",
        },
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "followup_query", '
            '"shipping_type": "retail_standard", "weight_kg": null, '
            '"origin": null, "destination": null, '
            '"missing_fields": ["weight_kg", "origin", "destination"], '
            '"next_step": "clarify", '
            '"clarification_reason": "missing_inputs"}'
        ),
    )

    result = planner_node(state)

    # D-12 cascade: clarify -> fetch_fuel (promotion) -> fuel_fresh skip ->
    # _route_matches uses merged_origin/destination -> calculate_price.
    assert result["next_step"] == "calculate_price"
    assert result["shipping_type"] == "retail_standard"
    assert result["weight_kg"] == 15.0
    assert result["origin"] == "Bangkok"
    assert result["destination"] == "Pathum Thani"


def test_trace_tool_output_reflects_post_override_next_step(monkeypatch):
    """999.3: D-12 overrides LLM-emitted fetch_fuel to fetch_route (route not
    cached, fuel fresh); the trace tool_output MUST reflect the post-override
    next_step ('fetch_route'), not the raw LLM emission ('fetch_fuel').

    Phase 11 / FIX-02: state pre-populates shipping_type='bounce' so the
    destination-less short-circuit does NOT fire (a true follow-up
    surcharge always carries >= 1 prior logistics field).
    """
    state = _user_state(
        "Surcharge for 15kg Bounce Bangkok to Nonthaburi",
        fuel_data={
            "price": 31.0,
            "baseline": 29.94,
            "delta_pct": 0.0354,
            "date": "2026-04-25",
            "unit": "THB/L",
            "source": "eppo_live",
            "fetched_at": _now_iso_z(),
        },
        shipping_type="bounce",  # FIX-02: prior logistics field present
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 15, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    assert result["next_step"] == "fetch_route"
    # 999.3 fix: trace tool_output reflects the actually-routed step,
    # not the raw LLM emission.
    trace_output = result["reasoning_trace"][0]["tool_output"]
    assert trace_output["next_step"] == "fetch_route"
    # Merged extraction fields are present (==parsed values for this case).
    assert trace_output["shipping_type"] == "bounce"
    assert trace_output["weight_kg"] == 15
    assert trace_output["origin"] == "Bangkok"
    assert trace_output["destination"] == "Nonthaburi"


def test_trace_tool_output_reflects_merged_inherited_fields(monkeypatch):
    """999.3 + 999.1: state has prior weight_kg=15; LLM emits null weight_kg
    plus missing_fields=['weight_kg'] plus next_step=clarify. The trace
    tool_output MUST reflect the merged weight_kg (15.0) and the recomputed
    empty missing_fields list, not the raw LLM emission."""
    state = _user_state(
        "Bounce Bangkok to Nonthaburi",
        weight_kg=15.0,
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "followup_query", '
            '"shipping_type": "bounce", "weight_kg": null, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": ["weight_kg"], '
            '"next_step": "clarify", '
            '"clarification_reason": "missing_weight"}'
        ),
    )

    result = planner_node(state)

    # 999.1: promotion to fetch_fuel; Phase 5 D-01 then promotes to
    # fanout_fuel_route (no caches; merge fills weight_kg; all 4 fields present).
    assert result["next_step"] == "fanout_fuel_route"
    trace_output = result["reasoning_trace"][0]["tool_output"]
    # 999.3: trace shows merged weight, not the LLM's null.
    assert trace_output["weight_kg"] == 15.0
    # 999.3: trace shows recomputed empty missing_fields, not the LLM's
    # ["weight_kg"].
    assert trace_output["missing_fields"] == []
    # 999.3: trace next_step matches the post-override return value.
    assert trace_output["next_step"] == "fanout_fuel_route"


# ---------------------------------------------------------------------------
# Phase 5 ORCH-07 fan-out routing
# ---------------------------------------------------------------------------


def test_planner_fanout_when_both_stale(monkeypatch):
    """D-01: both fuel + route missing -> next_step='fanout_fuel_route'."""
    state = _user_state(
        "calc 15kg bounce BKK->Nonthaburi"
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 15, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    assert result["next_step"] == "fanout_fuel_route"
    assert result["origin"] == "Bangkok"
    assert result["destination"] == "Nonthaburi"
    assert result["shipping_type"] == "bounce"
    assert result["weight_kg"] == 15


def test_planner_no_fanout_when_fuel_fresh(monkeypatch):
    """D-12: fresh fuel_data -> next_step='fetch_route' (sequential, no fan-out).

    Phase 11 / FIX-02: state pre-populates shipping_type='bounce' so the
    destination-less short-circuit does NOT fire — this test models a
    follow-up surcharge with cached fuel + prior shipping_type extracted.
    """
    # Fresh fuel_data; fetched_at is now -> not stale per FUEL_DATA_TTL_SECONDS=3600.
    state = _user_state(
        "calc",
        fuel_data={
            "price": 30.0,
            "baseline": 29.94,
            "delta_pct": 0.002,
            "date": "2026-05-01",
            "unit": "THB/L",
            "source": "eppo_live",
            "fetched_at": _now_iso_z(),
        },
        shipping_type="bounce",  # FIX-02: prior logistics field present
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 15, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    # fetch_fuel was promoted to fetch_route per D-12 cache-skip; NOT fanout
    # because fuel is fresh.
    assert result["next_step"] == "fetch_route"


def test_planner_no_fanout_when_route_matches(monkeypatch):
    """D-12: matching route_data -> next_step='fetch_fuel' (sequential, no fan-out)."""
    state = _user_state(
        "calc",
        route_data={
            "origin": "Bangkok",
            "destination": "Nonthaburi",
            "distance_km": 18.5,
            "duration_min": 30,
            "traffic_severity": 2,
            "zone": "central-1",
        },
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 15, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "fetch_route", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    assert result["next_step"] == "fetch_fuel"


def test_planner_no_fanout_when_clarify_path(monkeypatch):
    """User message missing required fields -> clarify, no fan-out."""
    state = _user_state("what's a surcharge?")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "clarification", '
            '"shipping_type": null, "weight_kg": null, '
            '"origin": null, "destination": null, '
            '"missing_fields": ["shipping_type", "weight_kg", "origin", "destination"], '
            '"next_step": "clarify", '
            '"clarification_reason": "missing_inputs"}'
        ),
    )

    result = planner_node(state)

    assert result["next_step"] == "clarify"


def test_planner_trace_entry_records_fanout(monkeypatch):
    """999.3 fix invariant: tool_output reflects post-override next_step."""
    state = _user_state("calc 15kg bounce Bangkok->Nonthaburi")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 15, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    trace = result["reasoning_trace"]
    assert len(trace) == 1
    assert trace[0]["agent"] == "planner"
    # 999.3 fix: tool_output uses post-override next_step.
    assert trace[0]["tool_output"]["next_step"] == "fanout_fuel_route"


# ---------------------------------------------------------------------------
# Phase 5 TOOL-05 search_context routing
# ---------------------------------------------------------------------------


def test_planner_emits_search_context_for_news_intent(monkeypatch):
    """D-09: planner passes search_context next_step through unchanged.

    The cache-aware override block must NOT downgrade search_context to
    fetch_route just because route_data is missing — search is intent-driven,
    not state-driven.
    """
    state = _user_state("What's driving diesel prices this week?")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": null, "weight_kg": null, '
            '"origin": null, "destination": null, '
            '"missing_fields": [], '
            '"next_step": "search_context", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    assert result["next_step"] == "search_context"


def test_planner_search_context_bypasses_cache_override(monkeypatch):
    """D-09: even with fresh fuel_data + matching route_data the planner
    does NOT downgrade search_context to calculate_price — search runs."""
    state = _user_state(
        "Why is diesel up?",
        shipping_type="bounce",
        weight_kg=15.0,
        origin="Bangkok",
        destination="Nonthaburi",
        fuel_data={
            "price": 31.0,
            "baseline": 29.94,
            "delta_pct": 0.0354,
            "date": "2026-05-01",
            "unit": "THB/L",
            "source": "eppo_live",
            "fetched_at": _now_iso_z(),
        },
        route_data={
            "origin": "Bangkok",
            "destination": "Nonthaburi",
            "distance_km": 18.5,
            "duration_min": 30,
            "traffic_severity": 2,
            "zone": "central-1",
        },
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 15, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "search_context", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    assert result["next_step"] == "search_context"


def test_graph_routes_search_context_to_search_agent():
    """D-10: _route_from_planner maps search_context → search_agent."""
    from backend.agent.graph import _route_from_planner

    assert (
        _route_from_planner({"next_step": "search_context"}) == "search_agent"
    )


# ---------------------------------------------------------------------------
# Plan 05-08 / gap-1 (2026-05-03): on follow-up turns the LLM may hallucinate
# truthy values for fields the user did not mention (e.g. shipping_type=
# "retail_standard" and destination="Chiang Mai" when user only said "What
# about 25kg instead?"). The 999.1 merge is null-only (`parsed.X or
# state.get("X")`), so it short-circuits and the hallucinated value wins.
# The fix nulls out parsed.X BEFORE the 999.1 merge when:
# - parsed.user_intent == "followup_query"
# - prior state has a value for X
# - user message text does not contain a recognisable token for X
# Explicit overrides (LLM emits non-null AND user message contains a token)
# are preserved — this is null-only inheritance, never override.
# ---------------------------------------------------------------------------


def test_followup_inherits_unmentioned_fields(monkeypatch):
    """gap-1: prior turn has full state; follow-up message says only "What
    about 25kg instead?"; LLM hallucinates shipping_type='retail_standard'
    and destination='Chiang Mai'. Planner MUST null those hallucinated
    values out and inherit prior bounce + Nonthaburi.
    """
    state = _user_state(
        "What about 25kg instead?",
        shipping_type="bounce",
        weight_kg=15.0,
        origin="Bangkok",
        destination="Nonthaburi",
        fuel_data={
            "price": 31.0,
            "baseline": 29.94,
            "delta_pct": 0.0354,
            "date": "2026-05-03",
            "unit": "THB/L",
            "source": "eppo_live",
            "fetched_at": _now_iso_z(),
        },
        route_data={
            "origin": "Bangkok",
            "destination": "Nonthaburi",
            "distance_km": 19.2,
            "duration_min": 30,
            "traffic_severity": 1,
            "zone": "central-1",
        },
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "followup_query", '
            '"shipping_type": "retail_standard", "weight_kg": 25, '
            '"origin": null, "destination": "Chiang Mai", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    # Hallucinated values nulled out, prior state inherited via 999.1 merge.
    assert result["shipping_type"] == "bounce"
    assert result["weight_kg"] == 25
    assert result["origin"] == "Bangkok"
    assert result["destination"] == "Nonthaburi"


def test_followup_explicit_override_wins_over_inheritance(monkeypatch):
    """gap-1: when the user explicitly says "switch to retail_fast" the LLM
    correctly emits non-null shipping_type='retail_fast' and null for the
    other three fields. The inheritance branch MUST NOT erase the explicit
    override; the other three MUST inherit from prior state.
    """
    state = _user_state(
        "Switch to retail_fast",
        shipping_type="bounce",
        weight_kg=15.0,
        origin="Bangkok",
        destination="Nonthaburi",
        fuel_data={
            "price": 31.0,
            "baseline": 29.94,
            "delta_pct": 0.0354,
            "date": "2026-05-03",
            "unit": "THB/L",
            "source": "eppo_live",
            "fetched_at": _now_iso_z(),
        },
        route_data={
            "origin": "Bangkok",
            "destination": "Nonthaburi",
            "distance_km": 19.2,
            "duration_min": 30,
            "traffic_severity": 1,
            "zone": "central-1",
        },
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "followup_query", '
            '"shipping_type": "retail_fast", "weight_kg": null, '
            '"origin": null, "destination": null, '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    # Explicit override on shipping_type wins; the other three inherit.
    assert result["shipping_type"] == "retail_fast"
    assert result["weight_kg"] == 15.0
    assert result["origin"] == "Bangkok"
    assert result["destination"] == "Nonthaburi"


# ---------------------------------------------------------------------------
# Plan 05-10 / gap-3 (2026-05-03): UAT test 6 — news/trend queries (e.g.
# "Why are diesel prices rising this week?") trigger the planner to re-route
# to search_context 5 times in a row until the loop-budget guard exhausts.
# After search_agent populates state.search_context, the planner re-runs the
# LLM, which AGAIN classifies the user message as out_of_scope/news →
# re-emits next_step="search_context" → router re-dispatches to search_agent
# → loop until D-04 budget guard fires.
# Fix: when state.search_context is not None AND user_intent is in
# {"news_query", "out_of_scope"}, planner short-circuits to next_step="respond"
# BEFORE the Gemini call. The early-return appends a minimal trace entry so
# observability shows "planner ran twice, second was a short-circuit".
# ---------------------------------------------------------------------------


def test_planner_early_returns_when_search_context_populated(monkeypatch):
    """gap-3: with search_context populated and user_intent='out_of_scope',
    the planner short-circuits to respond WITHOUT calling Gemini.

    We do NOT mock get_chat_model — if the early-return fails, the unmocked
    call would raise (proving the guard fired)."""
    state = _user_state(
        "Why are diesel prices rising?",
        user_intent="out_of_scope",
        search_context={
            "query": "diesel news",
            "summary": "Diesel prices up 3% on supply concerns",
            "sources": [
                {
                    "title": "EPPO weekly diesel report",
                    "url": "https://example.com/diesel",
                    "snippet": "Diesel B7 retail price held at 30 THB/L.",
                    "published_at": "2026-05-01",
                }
            ],
            "fetched_at": "2026-05-03T10:00:00Z",
        },
        reasoning_trace=[
            {"step": 1, "agent": "planner"},
            {"step": 2, "agent": "search_agent"},
        ],
    )

    result = planner_node(state)

    assert result["next_step"] == "respond"
    assert result.get("clarification_reason") is None
    # The early-return appends a minimal trace entry recording the short-circuit.
    assert len(result["reasoning_trace"]) == 1
    assert result["reasoning_trace"][0]["agent"] == "planner"
    assert (
        result["reasoning_trace"][0]["reasoning"]
        == "search_context populated; routing to respond"
    )


def test_planner_early_returns_for_news_query_intent_too(monkeypatch):
    """gap-3: same as above but user_intent='news_query' (the new dedicated
    intent value). The early-return guard accepts BOTH values for backward
    compatibility."""
    state = _user_state(
        "Why are diesel prices rising?",
        user_intent="news_query",
        search_context={
            "query": "diesel news",
            "summary": "Refinery shutdown nudges prices up.",
            "sources": [],
            "fetched_at": "2026-05-03T10:00:00Z",
        },
        reasoning_trace=[
            {"step": 1, "agent": "planner"},
            {"step": 2, "agent": "search_agent"},
        ],
    )

    result = planner_node(state)

    assert result["next_step"] == "respond"
    assert result.get("clarification_reason") is None
    assert len(result["reasoning_trace"]) == 1
    assert result["reasoning_trace"][0]["agent"] == "planner"
    assert (
        result["reasoning_trace"][0]["reasoning"]
        == "search_context populated; routing to respond"
    )


def test_planner_does_not_short_circuit_for_surcharge_query_with_search_context(
    monkeypatch,
):
    """gap-3 defensive: if a future flow somehow has both search_context AND
    surcharge_query intent, the early-return MUST NOT fire because the user
    still wants a surcharge calculation. The LLM should be invoked normally."""
    mock_factory = MagicMock()
    mock_factory.return_value = _scripted_llm(
        '{"user_intent": "surcharge_query", '
        '"shipping_type": "bounce", "weight_kg": 15, '
        '"origin": "Bangkok", "destination": "Nonthaburi", '
        '"missing_fields": [], '
        '"next_step": "fetch_fuel", '
        '"clarification_reason": null}'
    )
    monkeypatch.setattr(mod, "get_chat_model", mock_factory)

    state = _user_state(
        "Surcharge for 15kg Bounce Bangkok to Nonthaburi",
        user_intent="surcharge_query",
        search_context={
            "query": "diesel news",
            "summary": "Diesel prices up 3%.",
            "sources": [],
            "fetched_at": "2026-05-03T10:00:00Z",
        },
    )

    result = planner_node(state)

    # LLM was called — early-return did NOT fire.
    assert mock_factory.call_count >= 1
    # Result has full extraction fields, not the short-circuit shape.
    assert result["shipping_type"] == "bounce"
    assert result["weight_kg"] == 15
    assert "user_intent" in result


# ---------------------------------------------------------------------------
# Phase 999.9 D-10 — Planner extracts origin_hub_id from prose, validates
# against allowlist, inherits across follow-up turns
# ---------------------------------------------------------------------------
#
# Plan: .planning/phases/999.9-hq-branch-origin-model-real-world-hub-to-
#       destination-shipping/999.9-02-PLAN.md (Task 2)
#
# These six tests cover D-10 prose extraction, allowlist validation
# (Pattern 2), 999.1 merge for origin_hub_id, and the D-08 follow-up
# token-detection clause (Pitfall 2).


def test_planner_includes_hub_shortlist_in_prompt():
    """SYSTEM_PROMPT must contain all 10 hub_ids so the LLM can extract them."""
    from backend.agent.prompts.planner import SYSTEM_PROMPT

    expected_hubs = [
        "hq-lat-krabang",
        "branch-bang-na",
        "branch-nonthaburi",
        "branch-pathum-thani",
        "branch-samut-prakan",
        "branch-ayutthaya",
        "branch-nakhon-pathom",
        "branch-samut-sakhon",
        "branch-ratchaburi",
        "branch-lop-buri",
    ]
    for hub_id in expected_hubs:
        assert hub_id in SYSTEM_PROMPT, (
            f"hub_id {hub_id!r} missing from SYSTEM_PROMPT"
        )
    # Also assert the section header is present.
    assert "Origin hub extraction (Phase 999.9 D-10)" in SYSTEM_PROMPT


def test_planner_extracts_origin_hub_id_from_prose(monkeypatch):
    """Happy path: LLM emits a valid origin_hub_id; planner_node returns it."""
    state = _user_state("Surcharge for 5kg Bounce from Bang Na to Nonthaburi")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 5, '
            '"origin": "Bang Na", "destination": "Nonthaburi", '
            '"origin_hub_id": "branch-bang-na", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    assert result["origin_hub_id"] == "branch-bang-na"
    # Trace tool_output mirrors the merged value.
    trace_output = result["reasoning_trace"][0]["tool_output"]
    assert trace_output["origin_hub_id"] == "branch-bang-na"


def test_planner_invalid_hub_id_falls_back_to_none(monkeypatch, caplog):
    """Allowlist validation: invalid hub_id is discarded with a warning;
    falls through to merge → state.origin_hub_id (None here).
    """
    import logging

    state = _user_state("Ship 5kg Bounce to Nonthaburi")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 5, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"origin_hub_id": "fake-hub-9001", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    with caplog.at_level(logging.WARNING, logger="backend.agent.nodes.planner"):
        result = planner_node(state)

    assert result["origin_hub_id"] is None, (
        f"invalid hub_id should be discarded; got {result['origin_hub_id']!r}"
    )
    # A warning was logged about the invalid hub_id.
    assert any(
        "invalid origin_hub_id" in rec.message for rec in caplog.records
    ), f"expected invalid-hub warning in logs, got: {[r.message for r in caplog.records]}"


def test_planner_followup_inherits_origin_hub_id(monkeypatch):
    """Pitfall 2 / 999.1 merge: follow-up turn with null origin_hub_id
    inherits from prior state.
    """
    state = _user_state(
        "What about 25kg?",
        shipping_type="bounce",
        weight_kg=15.0,
        origin="Bangkok",
        destination="Nonthaburi",
        origin_hub_id="branch-bang-na",
        # Cache fuel + route so 999.1 merge cascade reaches calculate_price
        # (otherwise we get fanout_fuel_route which is fine but less direct).
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "followup_query", '
            '"shipping_type": null, "weight_kg": 25, '
            '"origin": null, "destination": null, '
            '"origin_hub_id": null, '
            '"missing_fields": [], '
            '"next_step": "calculate_price", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    # 999.1 merge: hub_id inherited from prior state.
    assert result["origin_hub_id"] == "branch-bang-na"
    assert result["weight_kg"] == 25  # explicit override from LLM


def test_planner_followup_explicit_hub_in_prose_wins(monkeypatch):
    """Pitfall 2: when the user explicitly mentions a different hub in prose,
    parsed.origin_hub_id wins over prior state.
    """
    state = _user_state(
        "What about from Nonthaburi?",
        shipping_type="bounce",
        weight_kg=15.0,
        origin="Bangkok",
        destination="Nonthaburi",
        origin_hub_id="branch-bang-na",
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "followup_query", '
            '"shipping_type": null, "weight_kg": null, '
            '"origin": null, "destination": null, '
            '"origin_hub_id": "branch-nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "fetch_route", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    # Explicit prose override wins (user mentioned "Nonthaburi", which is
    # in the address tokens for branch-nonthaburi).
    assert result["origin_hub_id"] == "branch-nonthaburi"


def test_planner_followup_unmentioned_hub_nulled_out(monkeypatch):
    """D-08 token detection: LLM hallucinates an origin_hub_id that the user
    did NOT mention in prose; the D-08 clause nulls it out so prior wins.
    """
    state = _user_state(
        "What about 25kg?",  # No hub mention in user message.
        shipping_type="bounce",
        weight_kg=15.0,
        origin="Bangkok",
        destination="Nonthaburi",
        origin_hub_id="branch-bang-na",
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "followup_query", '
            '"shipping_type": null, "weight_kg": 25, '
            '"origin": null, "destination": null, '
            # LLM hallucinates a different hub — but user message has
            # no hub-address token (only "25kg").
            '"origin_hub_id": "branch-ratchaburi", '
            '"missing_fields": [], '
            '"next_step": "calculate_price", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    # D-08 token-detection nulled the hallucinated value; prior wins via merge.
    assert result["origin_hub_id"] == "branch-bang-na"


# ---------------------------------------------------------------------------
# Phase 999.10 — Planner bypass refusal paths (GUARD-07)
#
# Plan: .planning/phases/999.10-guard-input-bypass-paths-return-inconsistent-
#       refusal-copy/999.10-02-planner-refusal-paths-PLAN.md
#
# Covers D-04 (LLM emits user_intent='out_of_scope' -> refuse via
# guard_decision.category='planner_off_topic') and confirms end-to-end the
# planner -> response_node refusal pipeline yields REFUSAL_COPY with
# status='refused'.
# ---------------------------------------------------------------------------


def test_planner_refuses_on_out_of_scope_intent(monkeypatch):
    """D-04: when Gemini emits user_intent='out_of_scope', planner_node
    returns next_step='respond' AND state.guard_decision with category
    'planner_off_topic' — so response_node's refusal branch renders
    REFUSAL_COPY with status='refused'."""
    state = _user_state("What's the weather in Bangkok today?")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "out_of_scope", '
            '"shipping_type": null, "weight_kg": null, '
            '"origin": null, "destination": null, '
            '"missing_fields": [], '
            '"next_step": "respond", '
            '"clarification_reason": "out_of_scope_user_request"}'
        ),
    )

    result = planner_node(state)

    assert result["next_step"] == "respond"
    assert result["guard_decision"] == {
        "layer": "input",
        "refused": True,
        "category": "planner_off_topic",
        "violations": [],
    }
    # No clarification_reason / clarify-path artifacts on the refusal branch.
    assert result.get("clarification_reason") in (None, "")
    # No origin_hub_id / extraction-merge artifacts because the refusal
    # short-circuits BEFORE the 999.1 merge.
    assert "shipping_type" not in result
    assert "weight_kg" not in result


def test_planner_refusal_routes_response_to_REFUSAL_COPY(monkeypatch):
    """D-08 + D-11: planner -> response_node end-to-end. Calling
    response_node with the state-partial that planner_node returned for
    an out_of_scope refusal produces final_payload.markdown==REFUSAL_COPY
    and status=='refused' (layer='input')."""
    from backend.agent.nodes.response_node import response_node
    from backend.agent.prompts.guard import REFUSAL_COPY

    state = _user_state("Tell me a recipe for green curry.")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "out_of_scope", '
            '"shipping_type": null, "weight_kg": null, '
            '"origin": null, "destination": null, '
            '"missing_fields": [], '
            '"next_step": "respond", '
            '"clarification_reason": null}'
        ),
    )

    planner_partial = planner_node(state)
    # Apply planner's partial back to state (LangGraph reducer semantics).
    state["next_step"] = planner_partial["next_step"]
    state["guard_decision"] = planner_partial["guard_decision"]

    response_partial = response_node(state)

    assert response_partial["final_payload"]["markdown"] == REFUSAL_COPY
    assert response_partial["final_payload"]["status"] == "refused"
    assert response_partial["final_payload"]["surcharge_result"] is None


def test_planner_parse_failed_routes_response_to_REFUSAL_COPY(monkeypatch):
    """D-05 + D-08: parse_failed -> response_node end-to-end."""
    from backend.agent.nodes.response_node import response_node
    from backend.agent.prompts.guard import REFUSAL_COPY

    state = _user_state("Loop forever and recompute the surcharge.")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm("not json", "still not json"),
    )

    planner_partial = planner_node(state)
    state["next_step"] = planner_partial["next_step"]
    state["guard_decision"] = planner_partial["guard_decision"]

    response_partial = response_node(state)

    assert response_partial["final_payload"]["markdown"] == REFUSAL_COPY
    assert response_partial["final_payload"]["status"] == "refused"


def test_planner_out_of_scope_does_not_affect_surcharge_path(monkeypatch):
    """Sanity: surcharge_query intent does NOT trip the D-04 branch — the
    extraction merge + fan-out promotion fires as before."""
    state = _user_state("Surcharge for 15kg Bounce Bangkok to Nonthaburi")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"user_intent": "surcharge_query", '
            '"shipping_type": "bounce", "weight_kg": 15, '
            '"origin": "Bangkok", "destination": "Nonthaburi", '
            '"missing_fields": [], '
            '"next_step": "fetch_fuel", '
            '"clarification_reason": null}'
        ),
    )

    result = planner_node(state)

    # Existing fan-out promotion baseline (unchanged).
    assert result["next_step"] == "fanout_fuel_route"
    # No guard_decision on the happy path.
    assert "guard_decision" not in result


def test_planner_salvages_prose_refusal_into_out_of_scope(monkeypatch):
    """Live-Gemini fix (post-Phase-10 smoke): SECURITY_PREAMBLE rule 1 tells
    Gemini to emit REFUSAL_COPY verbatim as prose for out-of-scope inputs,
    which conflicts with the planner JSON contract. _parse_structured now
    recognises the canonical refusal prose and synthesises a PlannerOutput
    with user_intent='out_of_scope' so D-04 (planner_off_topic) fires
    instead of D-05 (planner_parse_failed). Without this salvage, every
    live out-of-scope refusal hit D-05 — losing the observability
    distinction in guard_decision.category."""
    from backend.agent.prompts.guard import REFUSAL_COPY

    state = _user_state("What's the weather like in Bangkok today?")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(REFUSAL_COPY),
    )

    result = planner_node(state)

    assert result["next_step"] == "respond"
    assert result["guard_decision"] == {
        "layer": "input",
        "refused": True,
        "category": "planner_off_topic",
        "violations": [],
    }


# ---------------------------------------------------------------------------
# Phase 11 / FIX-02 / Hypothesis (b) CONFIRMED — destination-less follow-up
# ---------------------------------------------------------------------------


def test_planner_does_not_loop_on_destination_less_baseline_query(monkeypatch):
    """D-10 pinning test: Phase 11 / FIX-02 — pins planner re-loop root cause.

    When fuel_data is already populated and the user's message has no
    extractable destination, the second planner invocation MUST route
    to respond — not loop back through fetch_route (which would
    ValueError) or fetch_fuel (which would re-fetch fresh fuel for no
    reason).

    Live symptom captured in
    .planning/phases/999.11-.../999.11-03-EVIDENCE.md row 4: the LLM
    emits fetch_fuel + user_intent=surcharge_query on the second pass;
    the cache-aware override at planner.py:500-509 unconditionally
    promotes next_step to fetch_route because _route_matches returns
    False on destination=None. route_agent then ValueErrors on the
    missing destination, the error sink emits a `done` event, the
    client times out at 60s and sees a 0-byte body.

    Fix (this plan): a destination-less short-circuit BEFORE the LLM
    invoke routes to respond when fuel_data is populated AND no
    logistics fields (destination, shipping_type, weight_kg) are
    present. This is exactly the legit-baseline shape and never fires
    on real surcharge queries (which always carry >= 1 logistics field).
    """
    # The CONFIRMED-trigger LLM emission (per EVIDENCE.md row 4): the live
    # LLM emits fetch_fuel + user_intent=surcharge_query on the second
    # planner pass. The short-circuit fires BEFORE the LLM is invoked,
    # so the script content is irrelevant — but we install a MagicMock
    # to detect any leakage (assertion below).
    mock_factory = MagicMock()
    mock_factory.return_value = _scripted_llm(
        '{"user_intent": "surcharge_query", '
        '"shipping_type": null, "weight_kg": null, '
        '"origin": null, "destination": null, '
        '"origin_hub_id": null, '
        '"missing_fields": [], '
        '"next_step": "fetch_fuel", '
        '"clarification_reason": null}'
    )
    monkeypatch.setattr(mod, "get_chat_model", mock_factory)

    state = _user_state(
        "What's the current diesel price in Bangkok?",
        fuel_data={
            "price": 39.95,
            "baseline": 36.31,
            "delta_pct": 0.1002,
            "date": "2026-05-11",
            "unit": "THB/L",
            "source": "eppo_cached_csv",
            "fetched_at": _now_iso_z(),
        },
        route_data=None,
        destination=None,
        origin=None,
        shipping_type=None,
        weight_kg=None,
        origin_hub_id="hq-lat-krabang",
        reasoning_trace=[
            {
                "step": 1,
                "agent": "planner",
                "tool": None,
                "tool_input": {},
                "tool_output": {"next_step": "fetch_fuel"},
                "reasoning": "Intent=surcharge_query; routing to fetch_fuel",
                "timestamp": _now_iso_z(),
                "status": "ok",
            },
            {
                "step": 2,
                "agent": "fuel_agent",
                "tool": "fetch_fuel_price",
                "tool_input": None,
                "tool_output": {"price": 39.95, "source": "eppo_cached_csv"},
                "reasoning": "Diesel above baseline",
                "timestamp": _now_iso_z(),
                "status": "ok",
            },
        ],
    )

    out = planner_node(state)

    assert out["next_step"] == "respond", (
        f"FIX-02 regression: destination-less follow-up re-routed to "
        f"{out['next_step']!r} after fuel was fetched — would hang"
    )
    # Short-circuit fires BEFORE the LLM is invoked.
    assert mock_factory.call_count == 0, (
        "Short-circuit must run BEFORE the LLM is called — invoking the "
        "LLM defeats the purpose (wasted token call, plus the cache-aware "
        "override at planner.py:500-509 would still mis-route the result)"
    )
    # The short-circuit emits one trace entry for observability.
    new_entries = [
        e for e in out.get("reasoning_trace", [])
        if isinstance(e, dict) and e.get("step") == 3
    ]
    assert len(new_entries) == 1, (
        f"expected exactly 1 short-circuit trace entry at step=3; "
        f"got {len(new_entries)}: {new_entries!r}"
    )
    assert new_entries[0]["agent"] == "planner"
    assert new_entries[0]["status"] == "ok"


# ---------------------------------------------------------------------------
# Phase 11 / FIX-02 defense-in-depth — tool_call_count reducer invariant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_call_count_reducer_aggregates_parallel_writes(
    monkeypatch, mocker, in_memory_checkpointer
):
    """defense-in-depth invariant: Phase 11 / FIX-02 — additive coverage, not the D-10 pin.

    Phase 5 D-01 fan-out sends fuel + route in the same superstep.
    Both emit ``tool_call_count: 1``. The Annotated[int, operator.add]
    reducer MUST aggregate both deltas to >= 2, not lose one
    (last-write-wins) and not double-count (custom merger bug).

    This test is independent of the (b) verdict — it pins the
    reducer invariant so a future state-schema refactor cannot
    silently regress.

    Mirrors backend/tests/test_parallel_fanout.py
    ::test_fresh_thread_fans_out_fuel_and_route line-for-line for the
    setup; the load-bearing assertion is on
    ``final_state["tool_call_count"] >= 2``.
    """
    import json
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod
    from backend.agent.tools.models import FuelData, RateResult, RouteData

    def _planner_resp(next_step: str) -> str:
        return json.dumps({
            "user_intent": "surcharge_query",
            "shipping_type": "bounce",
            "weight_kg": 15.0,
            "origin": "Bangkok",
            "destination": "Nonthaburi",
            "missing_fields": [],
            "next_step": next_step,
            "clarification_reason": None,
        })

    # Stateful shared LLM cycling through planner responses across turn.
    planner_responses = [
        _planner_resp("fetch_fuel"),       # promoted to fanout_fuel_route
        _planner_resp("calculate_price"),  # after fanout — both caches present
        _planner_resp("respond"),
    ]
    planner_llm = FakeMessagesListChatModel(
        responses=[AIMessage(content=r) for r in planner_responses]
    )
    fuel_llm = FakeMessagesListChatModel(responses=[
        AIMessage(content='{"summary":"Diesel above baseline","trend":"above_baseline"}'),
    ])
    route_llm = FakeMessagesListChatModel(responses=[
        AIMessage(content='{"summary":"Route to Nonthaburi","traffic_label":"moderate"}'),
    ])
    pricing_llm = FakeMessagesListChatModel(responses=[
        AIMessage(content='{"summary":"Total 132 THB"}'),
    ])

    monkeypatch.setattr(planner_mod, "get_chat_model", lambda **_: planner_llm)
    monkeypatch.setattr(fuel_mod, "get_chat_model", lambda **_: fuel_llm)
    monkeypatch.setattr(route_mod, "get_chat_model", lambda **_: route_llm)
    monkeypatch.setattr(pricing_mod, "get_chat_model", lambda **_: pricing_llm)

    mocker.patch.object(
        fuel_mod, "fetch_fuel_price",
        return_value=FuelData(
            price=31.0, date="2026-05-01", source="eppo_live",
            baseline=29.94, delta_pct=0.0354,
        ),
    )
    mocker.patch.object(
        route_mod, "calculate_route",
        return_value=RouteData(
            origin="Bangkok", destination="Nonthaburi",
            distance_km=18.5, duration_min=30,
            traffic_severity=2, zone="central-1",
        ),
    )
    mocker.patch.object(
        pricing_mod, "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg",
        ),
    )

    from backend.agent.graph import build_graph
    graph = build_graph(checkpointer=in_memory_checkpointer)
    config = {"configurable": {"thread_id": "reducer-pin-1"}}
    initial_state = {
        "messages": [
            {"role": "user",
             "content": "Surcharge for 15kg bounce shipment Bangkok to Nonthaburi"},
        ],
        "fuel_data": None,
        "route_data": None,
        "shipping_type": None,
        "weight_kg": None,
        "surcharge_result": None,
        "reasoning_trace": [],
        "next_step": "",
        "origin": None,
        "destination": None,
        "user_intent": None,
        "missing_fields": [],
        "clarification_reason": None,
        "errors": [],
        "final_payload": None,
    }

    final_state = await graph.ainvoke(initial_state, config=config)
    assert final_state["tool_call_count"] >= 2, (
        f"reducer lost a parallel write: got {final_state['tool_call_count']}, expected >= 2"
    )

