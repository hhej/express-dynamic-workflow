"""Quick task 260509-utd Task 2: tool_call_count increment unit tests.

The fuel/route/search/pricing nodes must each emit ``tool_call_count: 1``
(a +1 DELTA) on every invocation. The state schema applies an
``operator.add`` reducer so the running total survives the Phase 5 D-01
parallel fan-out (fuel + route both writing in the same superstep).
The planner is a router (not a tool-caller) and MUST NOT touch the
counter.

End-to-end test that the counter trips guard_input at MAX_TOOL_CALLS_PER_TURN
lives in test_graph.py (Task 3) per the cross-reference in the plan.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agent.tools.models import (
    FuelData,
    RateResult,
    RouteData,
    SearchResult,
    SurchargeResult,
)


def _state_for_fuel() -> dict:
    return {
        "messages": [{"role": "user", "content": "diesel today?"}],
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
        "approval_decision": None,
        "search_context": None,
        "guard_decision": None,
        "tool_call_count": 2,
    }


def test_fuel_agent_increments_count(monkeypatch, mocker):
    """fuel_agent_node returns dict with tool_call_count = prior + 1."""
    from backend.agent.nodes import fuel_agent as fuel_mod
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage

    mocker.patch.object(
        fuel_mod, "fetch_fuel_price",
        return_value=FuelData(price=31.0, date="2026-04-25",
                              source="eppo_live", baseline=29.94,
                              delta_pct=0.0354),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model",
        lambda **_: FakeMessagesListChatModel(responses=[
            AIMessage(content='{"summary":"OK","trend":"above_baseline"}'),
        ]),
    )

    state = _state_for_fuel()
    out = fuel_mod.fuel_agent_node(state)
    assert out.get("tool_call_count") == 1, (
        "fuel_agent must emit a +1 delta (operator.add reducer aggregates)"
    )


def test_route_agent_increments_count(monkeypatch, mocker):
    from backend.agent.nodes import route_agent as route_mod
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage

    mocker.patch.object(
        route_mod, "calculate_route",
        return_value=RouteData(origin="Bangkok", destination="Nonthaburi",
                               distance_km=18.0, duration_min=30,
                               traffic_severity=2, zone="central-1"),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model",
        lambda **_: FakeMessagesListChatModel(responses=[
            AIMessage(content='{"summary":"OK","traffic_label":"moderate"}'),
        ]),
    )

    state = _state_for_fuel()
    state.update({"origin": "Bangkok", "destination": "Nonthaburi"})
    out = route_mod.route_agent_node(state)
    assert out.get("tool_call_count") == 1


def test_search_agent_increments_count(monkeypatch, mocker):
    from backend.agent.nodes import search_agent as search_mod
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage

    mocker.patch.object(
        search_mod, "search_fuel_news",
        return_value=SearchResult(
            query="diesel", summary="Stable.", sources=[],
            fetched_at="2026-05-09T03:00:00Z",
        ),
    )
    monkeypatch.setattr(
        search_mod, "get_chat_model",
        lambda **_: FakeMessagesListChatModel(responses=[
            AIMessage(content='{"summary":"Stable diesel context."}'),
        ]),
    )

    state = _state_for_fuel()
    out = search_mod.search_agent_node(state)
    assert out.get("tool_call_count") == 1


def test_pricing_agent_increments_count(monkeypatch, mocker):
    from backend.agent.nodes import pricing_agent as pricing_mod
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage

    mocker.patch.object(
        pricing_mod, "lookup_rate",
        return_value=RateResult(base_rate=120.0, currency="THB",
                                rate_tier="11-25kg"),
    )
    monkeypatch.setattr(
        pricing_mod, "get_chat_model",
        lambda **_: FakeMessagesListChatModel(responses=[
            AIMessage(content='{"summary":"Total 132 THB"}'),
        ]),
    )

    state = _state_for_fuel()
    state.update({
        "shipping_type": "bounce",
        "weight_kg": 15.0,
        "fuel_data": {"price": 31.0, "baseline": 29.94, "delta_pct": 0.0354},
        "route_data": {"zone": "central-1", "traffic_severity": 2},
    })
    out = pricing_mod.pricing_agent_node(state)
    assert out.get("tool_call_count") == 1


def test_planner_does_not_increment(monkeypatch):
    """Planner is a router, not a tool-caller — MUST NOT bump the counter."""
    from backend.agent.nodes import planner as planner_mod
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage
    import json

    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        lambda **_: FakeMessagesListChatModel(responses=[
            AIMessage(content=json.dumps({
                "user_intent": "surcharge_query",
                "shipping_type": "bounce",
                "weight_kg": 15.0,
                "origin": "Bangkok",
                "destination": "Nonthaburi",
                "missing_fields": [],
                "next_step": "fetch_fuel",
                "clarification_reason": None,
            })),
        ]),
    )

    state = _state_for_fuel()
    out = planner_mod.planner_node(state)
    assert "tool_call_count" not in out, (
        "Planner is a router, not a tool-caller — MUST NOT modify tool_call_count"
    )
