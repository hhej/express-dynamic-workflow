"""ORCH-07 — parallel Fuel + Route fan-out integration tests.

Verifies:
- D-01 fan-out fires when both fuel + route stale (fresh thread).
- D-01 trace timestamps overlap (<= 1.0s) — demo evidence for ROADMAP §Phase 5.
- D-12 cache-skip preserved on follow-up turns.
- D-03 RetryPolicy + D-24 error sink apply to parallel branches.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from backend.agent.graph import build_graph
from backend.agent.tools.models import FuelData, RateResult, RouteData


def _stateful_factory(*responses_json: str):
    """Return the SAME shared FakeMessagesListChatModel on every call.

    Mirrors the helper in test_graph.py — the shared model cycles its
    responses list across multiple invocations (planner re-loop, repeated
    narration calls, etc.).
    """
    shared = FakeMessagesListChatModel(
        responses=[AIMessage(content=r) for r in responses_json]
    )

    def factory(**_):
        return shared

    return factory


def _planner_response(
    next_step: str = "fetch_fuel",
    *,
    user_intent: str = "surcharge_query",
    shipping_type: str | None = "bounce",
    weight_kg: float | None = 15.0,
    origin: str | None = "Bangkok",
    destination: str | None = "Nonthaburi",
    missing_fields: list[str] | None = None,
    clarification_reason: str | None = None,
) -> str:
    import json
    return json.dumps({
        "user_intent": user_intent,
        "shipping_type": shipping_type,
        "weight_kg": weight_kg,
        "origin": origin,
        "destination": destination,
        "missing_fields": missing_fields or [],
        "next_step": next_step,
        "clarification_reason": clarification_reason,
    })


_NARR_FUEL = '{"summary": "Diesel above baseline", "trend": "above_baseline"}'
_NARR_ROUTE = '{"summary": "Route to Nonthaburi", "traffic_label": "moderate"}'
_NARR_PRICE = '{"summary": "Total 132 THB"}'


def _empty_state(message: str) -> dict:
    return {
        "messages": [{"role": "user", "content": message}],
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


# ---------------------------------------------------------------------------
# Test 1: D-01 / D-02 — both state keys populate after fan-out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fresh_thread_fans_out_fuel_and_route(
    monkeypatch, mocker, in_memory_checkpointer
):
    """Fresh thread, complete user message -> final state has both
    fuel_data and route_data populated. Confirms operator.add reducers
    on reasoning_trace + errors handle the same-superstep parallel
    writes without dropping state."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    # Planner script: turn 1 emits fetch_fuel (Phase 5 promotes to fanout);
    # after fan-out completes, planner re-runs (sees both caches present)
    # and emits calculate_price; then respond.
    planner_responses = [
        _planner_response("fetch_fuel"),       # promoted to fanout_fuel_route
        _planner_response("calculate_price"),  # both caches now present
        _planner_response("respond"),
    ]
    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(*planner_responses),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model", _stateful_factory(_NARR_FUEL),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model", _stateful_factory(_NARR_ROUTE),
    )
    monkeypatch.setattr(
        pricing_mod, "get_chat_model", _stateful_factory(_NARR_PRICE),
    )

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

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "fanout-1"}}
    state = _empty_state(
        "Surcharge for 15kg bounce shipment Bangkok to Nonthaburi"
    )

    final_state = await graph.ainvoke(state, config=cfg)

    assert final_state.get("fuel_data") is not None, "fuel_data dropped"
    assert final_state.get("route_data") is not None, "route_data dropped"
    assert final_state["fuel_data"]["price"] == 31.0
    assert final_state["route_data"]["zone"] == "central-1"


# ---------------------------------------------------------------------------
# Test 2: D-01 success criterion — fuel/route trace timestamps within 1.0s
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trace_timestamps_overlap(
    monkeypatch, mocker, in_memory_checkpointer
):
    """fuel_agent and route_agent timestamps on the parallel turn must be
    within 1.0 second of each other — the demo evidence for ROADMAP §Phase 5
    success criterion 1 (visible parallelism)."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    planner_responses = [
        _planner_response("fetch_fuel"),
        _planner_response("calculate_price"),
        _planner_response("respond"),
    ]
    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(*planner_responses),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model", _stateful_factory(_NARR_FUEL),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model", _stateful_factory(_NARR_ROUTE),
    )
    monkeypatch.setattr(
        pricing_mod, "get_chat_model", _stateful_factory(_NARR_PRICE),
    )

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

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "fanout-2"}}
    state = _empty_state(
        "Surcharge for 15kg bounce shipment Bangkok to Nonthaburi"
    )
    final_state = await graph.ainvoke(state, config=cfg)

    traces = final_state.get("reasoning_trace") or []
    fuel_t = next(t for t in traces if t.get("agent") == "fuel_agent")
    route_t = next(t for t in traces if t.get("agent") == "route_agent")
    fuel_ts = datetime.fromisoformat(
        fuel_t["timestamp"].replace("Z", "+00:00")
    )
    route_ts = datetime.fromisoformat(
        route_t["timestamp"].replace("Z", "+00:00")
    )
    delta_s = abs((fuel_ts - route_ts).total_seconds())
    assert delta_s < 1.0, (
        f"fuel/route timestamps {delta_s}s apart — likely sequential, "
        f"not parallel"
    )


# ---------------------------------------------------------------------------
# Test 3: D-12 — turn 2 with cached fuel + route uses sequential cache-skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_skips_fanout(
    monkeypatch, mocker, in_memory_checkpointer
):
    """Turn 2 of the same thread (with both caches populated by turn 1)
    must NOT re-fetch fuel or route — the D-12 cache-skip cascade routes
    sequentially through pricing without firing the parallel fan-out."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    # Planner: turn 1 fanout + calc + respond; turn 2 directly to calc
    # (cache-skip cascade); respond.
    planner_responses = [
        _planner_response("fetch_fuel"),       # turn 1 -> fanout
        _planner_response("calculate_price"),  # turn 1 -> after fanout
        _planner_response("respond"),          # turn 1 -> done
        _planner_response("calculate_price",   # turn 2 -> cache-skip
                          shipping_type="retail_fast"),
        _planner_response("respond",
                          shipping_type="retail_fast"),
    ]
    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(*planner_responses),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model",
        _stateful_factory(_NARR_FUEL, _NARR_FUEL),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model",
        _stateful_factory(_NARR_ROUTE, _NARR_ROUTE),
    )
    monkeypatch.setattr(
        pricing_mod, "get_chat_model",
        _stateful_factory(_NARR_PRICE, _NARR_PRICE),
    )

    fuel_calls = {"n": 0}
    route_calls = {"n": 0}

    def count_fuel():
        fuel_calls["n"] += 1
        return FuelData(
            price=31.0, date="2026-05-01", source="eppo_live",
            baseline=29.94, delta_pct=0.0354,
        )

    def count_route(origin, destination):
        route_calls["n"] += 1
        return RouteData(
            origin=origin, destination=destination,
            distance_km=18.5, duration_min=30,
            traffic_severity=2, zone="central-1",
        )

    mocker.patch.object(fuel_mod, "fetch_fuel_price", side_effect=count_fuel)
    mocker.patch.object(route_mod, "calculate_route", side_effect=count_route)
    mocker.patch.object(
        pricing_mod, "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg",
        ),
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "fanout-3"}}

    # Turn 1: fans out, populates fuel + route caches.
    state = _empty_state(
        "Surcharge for 15kg bounce shipment Bangkok to Nonthaburi"
    )
    await graph.ainvoke(state, config=cfg)
    assert fuel_calls["n"] == 1
    assert route_calls["n"] == 1

    # Turn 2: same thread, cached caches; D-12 cache-skip MUST avoid
    # both fuel and route re-fetches.
    followup = {
        "messages": [
            {"role": "user", "content": "What about Retail Fast?"}
        ]
    }
    await graph.ainvoke(followup, config=cfg)

    # If fan-out had fired again, the counters would be 2; if cache-skip
    # honoured the freshness check, they stay at 1.
    assert fuel_calls["n"] == 1, (
        "fuel_data was re-fetched on turn 2 — D-12 cache-skip not honoured"
    )
    assert route_calls["n"] == 1, (
        "route_data was re-fetched on turn 2 — D-12 cache-skip not honoured"
    )


# ---------------------------------------------------------------------------
# Test 4: D-03 / D-24 — one branch fails, other succeeds + error sink
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_branch_fails_other_succeeds(
    monkeypatch, mocker, in_memory_checkpointer
):
    """When route_agent's calculate_route persistently raises an httpx.HTTPError,
    RetryPolicy exhausts and the D-24 error sink writes a state.errors entry
    + forces next_step='respond'. fuel_agent's branch still populates
    state.fuel_data successfully — operator.add on errors carries the parallel
    write safely.
    """
    import httpx
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod

    planner_responses = [
        _planner_response("fetch_fuel"),  # promoted to fanout
        # After fan-out: errors present -> planner short-circuits to respond
        # (D-24 guard at top of planner_node).
    ]
    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(*planner_responses),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model", _stateful_factory(_NARR_FUEL),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model", _stateful_factory(_NARR_ROUTE),
    )

    mocker.patch.object(
        fuel_mod, "fetch_fuel_price",
        return_value=FuelData(
            price=31.0, date="2026-05-01", source="eppo_live",
            baseline=29.94, delta_pct=0.0354,
        ),
    )
    # Route persistently raises a retryable httpx.HTTPError so RetryPolicy
    # exhausts and the D-24 wrapper writes errors[] + next_step='respond'.
    mocker.patch.object(
        route_mod, "calculate_route",
        side_effect=httpx.HTTPError("maps down"),
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "fanout-4"}}
    state = _empty_state(
        "Surcharge for 15kg bounce shipment Bangkok to Nonthaburi"
    )
    final_state = await graph.ainvoke(state, config=cfg)

    # Fuel branch succeeded.
    assert final_state.get("fuel_data") is not None, (
        "fuel branch state lost despite running in parallel with failing route"
    )
    assert final_state["fuel_data"]["price"] == 31.0
    # Route branch error sinked.
    errors = final_state.get("errors") or []
    assert any(e.get("node") == "route_agent" for e in errors), (
        f"expected route_agent error in state.errors, got {errors}"
    )
