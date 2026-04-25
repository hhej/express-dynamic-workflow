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
    """No fuel_data, no route_data -> Planner emits next_step=fetch_fuel and
    extracts shipping_type, weight_kg, origin, destination from the message."""
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

    assert result["next_step"] == "fetch_fuel"
    assert result["shipping_type"] == "bounce"
    assert result["weight_kg"] == 15
    assert result["origin"] == "Bangkok"
    assert result["destination"] == "Nonthaburi"
    assert result["user_intent"] == "surcharge_query"
    assert result["reasoning_trace"][0]["agent"] == "planner"


def test_skips_fetch_when_fuel_fresh(monkeypatch):
    """D-12: state.fuel_data has fresh fetched_at; LLM says fetch_fuel but
    Planner OVERRIDES to fetch_route (because route_data is missing)."""
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
    # LLM ran and the post-LLM merge promoted clarify -> fetch_fuel (999.1).
    # Either way, the path through the LLM produced a real next_step (not the
    # short-circuit "respond" + budget-exhausted clarification_reason).
    assert result["next_step"] == "fetch_fuel"
    # The new planner entry was appended (not the empty short-circuit return).
    assert "reasoning_trace" in result
    assert result["reasoning_trace"][0]["agent"] == "planner"


def test_parse_failure_falls_back_to_clarify(monkeypatch):
    """D-02: Gemini returns invalid JSON twice; Planner returns next_step=clarify
    with clarification_reason='planner_parse_failed' and emits no trace entry."""
    state = _user_state("Surcharge for 15kg Bounce Bangkok to Nonthaburi")
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm("not json", "still not json"),
    )

    result = planner_node(state)

    assert result["next_step"] == "clarify"
    assert result["clarification_reason"] == "planner_parse_failed"


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

    # 999.1: promoted from clarify to fetch_fuel (no caches in state).
    assert result["next_step"] == "fetch_fuel"
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
    next_step ('fetch_route'), not the raw LLM emission ('fetch_fuel')."""
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

    # 999.1: promotion to fetch_fuel (no caches; merge fills weight_kg).
    assert result["next_step"] == "fetch_fuel"
    trace_output = result["reasoning_trace"][0]["tool_output"]
    # 999.3: trace shows merged weight, not the LLM's null.
    assert trace_output["weight_kg"] == 15.0
    # 999.3: trace shows recomputed empty missing_fields, not the LLM's
    # ["weight_kg"].
    assert trace_output["missing_fields"] == []
    # 999.3: trace next_step matches the post-override return value.
    assert trace_output["next_step"] == "fetch_fuel"
