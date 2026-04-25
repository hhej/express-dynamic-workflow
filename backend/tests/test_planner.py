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
    """D-04: when reasoning_trace already has >= PLANNER_MAX_ITERATIONS-1
    entries, Planner returns next_step=respond WITHOUT calling Gemini."""
    # PLANNER_MAX_ITERATIONS default is 6, so 5 prior trace entries triggers.
    state = _user_state(
        "Anything",
        reasoning_trace=[{"step": i + 1, "agent": "x"} for i in range(5)],
    )

    mock_factory = MagicMock()
    monkeypatch.setattr(mod, "get_chat_model", mock_factory)

    result = planner_node(state)

    assert result["next_step"] == "respond"
    assert result["clarification_reason"] == "planner_loop_budget_exhausted"
    # No Gemini call should occur
    assert mock_factory.call_count == 0


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
