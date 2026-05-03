"""Integration tests for the assembled StateGraph (ORCH-08, ORCH-10).

Covers:
- D-23 retry filter unit (test_value_error_skips_retry)
- D-22 RetryPolicy retries httpx.HTTPError exactly once (test_retry_policy_retries_httpx_error)
- D-24 retry-exhaustion sink routes to Response with status='partial'
  (test_retry_exhaustion_routes_to_response_partial)
- ORCH-10 baseline checkpointer persistence (test_checkpointer_persists_across_invocations)
- D-12 cache reuse end-to-end via checkpointer (test_followup_reuses_cached_fuel)
- Cross-cutting happy path (test_full_surcharge_query_integration)
- Cross-cutting cache demo for route counter (test_followup_only_runs_pricing)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from backend.agent.graph import build_graph, phase3_retry_on
from backend.agent.tools.models import FuelData, RateResult, RouteData


def _scripted_llm(*responses_json: str) -> FakeMessagesListChatModel:
    return FakeMessagesListChatModel(
        responses=[AIMessage(content=r) for r in responses_json]
    )


def _stateful_factory(*responses_json: str):
    """Build a get_chat_model replacement that returns the SAME shared
    FakeMessagesListChatModel on every call.

    FakeMessagesListChatModel cycles through its responses list, so a
    shared instance plays back the script in order across multiple node
    invocations. The lambda-based factory used elsewhere in the suite
    would instantiate a fresh model on every call and replay only the
    FIRST response — that would break planner-loop scripting.
    """
    shared = _scripted_llm(*responses_json)

    def factory(**_):
        return shared

    return factory


def _planner_response(
    next_step: str,
    *,
    user_intent: str = "surcharge_query",
    shipping_type: str | None = "bounce",
    weight_kg: float | None = 15.0,
    origin: str | None = "Bangkok",
    destination: str | None = "Nonthaburi",
    missing_fields: list[str] | None = None,
    clarification_reason: str | None = None,
) -> str:
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


_NARR = '{"summary": "OK", "trend": "above_baseline"}'
_NARR_R = '{"summary": "OK", "traffic_label": "moderate"}'
_NARR_P = '{"summary": "Total 132 THB"}'


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
# Test 1: D-23 retry filter unit test
# ---------------------------------------------------------------------------


def test_value_error_skips_retry():
    """phase3_retry_on filter MUST return False on ValueError/RuntimeError
    and True on the enumerated transient-network classes."""
    assert phase3_retry_on(ValueError("nope")) is False
    assert phase3_retry_on(RuntimeError("nope")) is False
    assert phase3_retry_on(httpx.HTTPError("x")) is True
    assert phase3_retry_on(httpx.TimeoutException("x")) is True


# ---------------------------------------------------------------------------
# Test 2: RetryPolicy retries httpx.HTTPError exactly once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_policy_retries_httpx_error(monkeypatch, mocker):
    """D-22 + D-23: a transient httpx.HTTPError on fetch_fuel_price should
    cause the fuel_agent node to retry exactly once (max_attempts=2 means
    1 retry after the original attempt) and then succeed."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod

    # Planner: routes fetch_fuel then respond after fuel returns.
    planner_llm_responses = [
        _planner_response("fetch_fuel"),
        _planner_response("respond"),
    ]
    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(*planner_llm_responses),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model",
        _stateful_factory(_NARR),
    )

    call_counter = {"n": 0}
    fake_fuel = FuelData(
        price=31.0, date="2026-04-25", source="eppo_live",
        baseline=29.94, delta_pct=0.0354,
    )

    def flaky_fetch():
        call_counter["n"] += 1
        if call_counter["n"] == 1:
            raise httpx.HTTPError("transient")
        return fake_fuel

    mocker.patch.object(fuel_mod, "fetch_fuel_price", side_effect=flaky_fetch)

    graph = build_graph(checkpointer=None)
    state = _empty_state("Surcharge for 15kg Bounce Bangkok to Nonthaburi")
    result = await graph.ainvoke(state)

    # RetryPolicy retried the httpx.HTTPError exactly once -> 2 total calls.
    assert call_counter["n"] == 2
    assert result["fuel_data"]["price"] == 31.0


# ---------------------------------------------------------------------------
# Test 3: D-24 retry-exhaustion sink routes to Response with status='partial'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_exhaustion_routes_to_response_partial(monkeypatch, mocker):
    """When fetch_fuel_price persistently raises httpx.HTTPError, RetryPolicy
    exhausts; the D-24 wrapper writes errors[] and forces next_step='respond';
    Response Node then renders status='partial'."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod

    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(_planner_response("fetch_fuel")),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model",
        _stateful_factory(_NARR),
    )
    mocker.patch.object(
        fuel_mod, "fetch_fuel_price",
        side_effect=httpx.HTTPError("permanent"),
    )

    graph = build_graph(checkpointer=None)
    state = _empty_state("Surcharge for 15kg Bounce Bangkok to Nonthaburi")
    result = await graph.ainvoke(state)

    assert len(result["errors"]) >= 1
    assert result["errors"][0]["node"] == "fuel_agent"
    assert result["errors"][0]["exception_type"] == "HTTPError"
    # Response Node ran with status="partial"
    assert result["final_payload"]["status"] == "partial"


# ---------------------------------------------------------------------------
# Test 4: ORCH-10 baseline — checkpointer persists state across invocations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpointer_persists_across_invocations(
    monkeypatch, mocker, in_memory_checkpointer,
):
    """Full happy-path chain runs once with thread_id=t1; aget_state then
    returns the persisted snapshot (fuel_data + route_data) without
    re-running the graph."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    planner_responses = [
        _planner_response("fetch_fuel"),
        _planner_response("fetch_route"),
        _planner_response("calculate_price"),
        _planner_response("respond"),
    ]
    monkeypatch.setattr(planner_mod, "get_chat_model",
                        _stateful_factory(*planner_responses))
    monkeypatch.setattr(fuel_mod, "get_chat_model",
                        _stateful_factory(_NARR))
    monkeypatch.setattr(route_mod, "get_chat_model",
                        _stateful_factory(_NARR_R))
    monkeypatch.setattr(pricing_mod, "get_chat_model",
                        _stateful_factory(_NARR_P))
    mocker.patch.object(
        fuel_mod, "fetch_fuel_price",
        return_value=FuelData(price=31.0, date="2026-04-25",
                              source="eppo_live", baseline=29.94,
                              delta_pct=0.0354),
    )
    mocker.patch.object(
        route_mod, "calculate_route",
        return_value=RouteData(origin="Bangkok",
                               destination="Nonthaburi",
                               distance_km=18.0, duration_min=30,
                               traffic_severity=2, zone="central-1"),
    )
    mocker.patch.object(
        pricing_mod, "lookup_rate",
        return_value=RateResult(base_rate=120.0, currency="THB",
                                rate_tier="11-25kg"),
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "t1"}}
    state = _empty_state("15kg Bounce Bangkok Nonthaburi")
    result1 = await graph.ainvoke(state, config=cfg)
    assert result1["surcharge_result"] is not None

    # Read snapshot — state survives in checkpointer
    snapshot = await graph.aget_state(cfg)
    assert snapshot.values["fuel_data"]["price"] == 31.0
    assert snapshot.values["route_data"]["zone"] == "central-1"


# ---------------------------------------------------------------------------
# Test 5: D-12 cache reuse end-to-end — follow-up turn skips fetch_fuel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_followup_reuses_cached_fuel(
    monkeypatch, mocker, in_memory_checkpointer,
):
    """Turn 1: full chain populates fuel_data with fetched_at.
    Turn 2 (same thread_id): planner emits next_step='calculate_price'
    directly (cache fresh); fetch_fuel_price MUST NOT be called again."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    planner_responses = [
        _planner_response("fetch_fuel"),
        _planner_response("fetch_route"),
        _planner_response("calculate_price"),
        _planner_response("respond"),
        # Turn 2:
        _planner_response("calculate_price", shipping_type="retail_fast"),
        _planner_response("respond", shipping_type="retail_fast"),
    ]
    monkeypatch.setattr(planner_mod, "get_chat_model",
                        _stateful_factory(*planner_responses))
    monkeypatch.setattr(fuel_mod, "get_chat_model",
                        _stateful_factory(_NARR, _NARR))
    monkeypatch.setattr(route_mod, "get_chat_model",
                        _stateful_factory(_NARR_R, _NARR_R))
    monkeypatch.setattr(pricing_mod, "get_chat_model",
                        _stateful_factory(_NARR_P, _NARR_P))

    fuel_calls = {"n": 0}

    def count_fetch():
        fuel_calls["n"] += 1
        return FuelData(
            price=31.0, date="2026-04-25", source="eppo_live",
            baseline=29.94, delta_pct=0.0354,
        )

    mocker.patch.object(fuel_mod, "fetch_fuel_price", side_effect=count_fetch)
    mocker.patch.object(
        route_mod, "calculate_route",
        return_value=RouteData(origin="Bangkok",
                               destination="Nonthaburi",
                               distance_km=18.0, duration_min=30,
                               traffic_severity=2, zone="central-1"),
    )
    mocker.patch.object(
        pricing_mod, "lookup_rate",
        return_value=RateResult(base_rate=120.0, currency="THB",
                                rate_tier="11-25kg"),
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "t-followup"}}
    state = _empty_state("15kg Bounce Bangkok Nonthaburi")
    await graph.ainvoke(state, config=cfg)
    assert fuel_calls["n"] == 1

    # Turn 2: append a follow-up message; checkpoint replay supplies
    # fuel_data/route_data automatically.
    followup = {
        "messages": [
            {"role": "user", "content": "What about Retail Fast?"}
        ]
    }
    await graph.ainvoke(followup, config=cfg)
    # fetch_fuel_price MUST NOT have been called again (D-12 cache reuse).
    assert fuel_calls["n"] == 1


# ---------------------------------------------------------------------------
# Test 6: Cross-cutting happy path — full markdown rendered with all 4 rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_surcharge_query_integration(
    monkeypatch, mocker, in_memory_checkpointer,
):
    """End-to-end: planner -> fuel -> route -> pricing -> response with all
    tools mocked. Final markdown contains the 4 D-11 row labels, status='ok',
    and surcharge_result has a non-None total."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    planner_responses = [
        _planner_response("fetch_fuel"),
        _planner_response("fetch_route"),
        _planner_response("calculate_price"),
        _planner_response("respond"),
    ]
    monkeypatch.setattr(planner_mod, "get_chat_model",
                        _stateful_factory(*planner_responses))
    monkeypatch.setattr(fuel_mod, "get_chat_model",
                        _stateful_factory(_NARR))
    monkeypatch.setattr(route_mod, "get_chat_model",
                        _stateful_factory(_NARR_R))
    monkeypatch.setattr(pricing_mod, "get_chat_model",
                        _stateful_factory(_NARR_P))
    mocker.patch.object(
        fuel_mod, "fetch_fuel_price",
        return_value=FuelData(price=31.0, date="2026-04-25",
                              source="eppo_live", baseline=29.94,
                              delta_pct=0.0354),
    )
    mocker.patch.object(
        route_mod, "calculate_route",
        return_value=RouteData(origin="Bangkok",
                               destination="Nonthaburi",
                               distance_km=18.0, duration_min=30,
                               traffic_severity=2, zone="central-1"),
    )
    mocker.patch.object(
        pricing_mod, "lookup_rate",
        return_value=RateResult(base_rate=120.0, currency="THB",
                                rate_tier="11-25kg"),
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "t-happy"}}
    state = _empty_state("15kg Bounce Bangkok Nonthaburi")
    result = await graph.ainvoke(state, config=cfg)

    assert result["surcharge_result"] is not None
    assert result["surcharge_result"]["total"] is not None
    payload = result["final_payload"]
    assert payload["status"] == "ok"
    md = payload["markdown"]
    assert "| Base rate |" in md
    assert "| Surcharge % |" in md
    assert "| Surcharge amount |" in md
    assert "| Total |" in md


# ---------------------------------------------------------------------------
# Test 7: Cross-cutting cache demo — route also cached on follow-up
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_followup_only_runs_pricing(
    monkeypatch, mocker, in_memory_checkpointer,
):
    """Same scaffolding as test 5; additionally asserts route_calls == 1
    after turn 2 (route_data also cached, planner D-12 override skips
    fetch_route)."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    planner_responses = [
        _planner_response("fetch_fuel"),
        _planner_response("fetch_route"),
        _planner_response("calculate_price"),
        _planner_response("respond"),
        # Turn 2:
        _planner_response("calculate_price", shipping_type="retail_fast"),
        _planner_response("respond", shipping_type="retail_fast"),
    ]
    monkeypatch.setattr(planner_mod, "get_chat_model",
                        _stateful_factory(*planner_responses))
    monkeypatch.setattr(fuel_mod, "get_chat_model",
                        _stateful_factory(_NARR, _NARR))
    monkeypatch.setattr(route_mod, "get_chat_model",
                        _stateful_factory(_NARR_R, _NARR_R))
    monkeypatch.setattr(pricing_mod, "get_chat_model",
                        _stateful_factory(_NARR_P, _NARR_P))

    fuel_calls = {"n": 0}
    route_calls = {"n": 0}

    def count_fuel():
        fuel_calls["n"] += 1
        return FuelData(
            price=31.0, date="2026-04-25", source="eppo_live",
            baseline=29.94, delta_pct=0.0354,
        )

    def count_route(origin, destination):
        route_calls["n"] += 1
        return RouteData(
            origin=origin, destination=destination,
            distance_km=18.0, duration_min=30,
            traffic_severity=2, zone="central-1",
        )

    mocker.patch.object(fuel_mod, "fetch_fuel_price", side_effect=count_fuel)
    mocker.patch.object(route_mod, "calculate_route", side_effect=count_route)
    mocker.patch.object(
        pricing_mod, "lookup_rate",
        return_value=RateResult(base_rate=120.0, currency="THB",
                                rate_tier="11-25kg"),
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "t-followup-2"}}
    state = _empty_state("15kg Bounce Bangkok Nonthaburi")
    await graph.ainvoke(state, config=cfg)
    assert fuel_calls["n"] == 1
    assert route_calls["n"] == 1

    followup = {
        "messages": [
            {"role": "user", "content": "What about Retail Fast?"}
        ]
    }
    await graph.ainvoke(followup, config=cfg)
    # Both caches reused on turn 2.
    assert fuel_calls["n"] == 1
    assert route_calls["n"] == 1


# ---------------------------------------------------------------------------
# Test 8: 999.1 E2E regression — parameter-switch follow-up routes through
# pricing despite the LLM emitting clarify-with-nulls (added 2026-04-25 via
# quick task 260425-vyj).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_followup_param_switch_routes_through_pricing(
    monkeypatch, mocker, in_memory_checkpointer,
):
    """999.1 E2E: turn 1 populates fuel_data + route_data + shipping_type
    on thread t-vyj-followup. Turn 2 sends "What if I switched it to a
    Bounce shipment instead?"; the planner LLM (only seeing the latest
    user message) emits next_step=clarify with shipping_type=bounce and
    null weight_kg/origin/destination. Without the 999.1 fix the graph
    routes to clarify and surcharge_result stays None. With the fix the
    post-LLM merge fills the gaps from prior state, the recompute
    promotes next_step to fetch_fuel, the D-12 cascade hits the fuel +
    route caches, and the graph routes through pricing.
    """
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    # D-04 loop budget is now windowed per turn (999.4 fix 2026-04-25):
    # turn 1's reasoning_trace ending in agent='response' resets the
    # planner-iteration count for turn 2, so default PLANNER_MAX_ITERATIONS=6
    # no longer short-circuits the follow-up planner LLM call. No monkeypatch
    # needed — passing this test against the default budget is the strongest
    # signal the D-04 fix actually closes the cross-turn short-circuit gap.

    # Phase 5 D-01: turn 1's first fetch_fuel emission is promoted to
    # 'fanout_fuel_route', which schedules fuel + route in the same
    # superstep. Planner is then re-entered just once more — after fanout
    # the cascade promotes to calculate_price.
    # Phase 5 ORCH-09 (Plan 05-05) Pitfall 6: pricing -> hitl_gate -> response
    # REPLACES the Phase 3 pricing -> planner edge, so planner is NOT
    # re-invoked after pricing within a single turn. Turn 1 therefore needs
    # only 2 planner LLM responses, not 3.
    turn1 = [
        _planner_response(
            "fetch_fuel", shipping_type="retail_standard",
            weight_kg=50.0, origin="Bangkok",
            destination="Pathum Thani",
        ),
        _planner_response(
            "calculate_price", shipping_type="retail_standard",
            weight_kg=50.0, origin="Bangkok",
            destination="Pathum Thani",
        ),
    ]
    # Turn 2 reproducer shape: only shipping_type extracted, others null,
    # next_step=clarify, user_intent=followup_query — exactly what the
    # live LLM emitted on 2026-04-25 smoke testing. Phase 5 Pitfall 6:
    # pricing -> hitl_gate -> response, so only the FIRST planner LLM call
    # is consumed on turn 2 (no post-pricing planner re-invocation).
    turn2 = [
        _planner_response(
            "clarify",
            user_intent="followup_query",
            shipping_type="bounce",
            weight_kg=None, origin=None, destination=None,
            missing_fields=["weight_kg", "origin", "destination"],
            clarification_reason="missing_inputs",
        ),
    ]
    planner_responses = turn1 + turn2

    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(*planner_responses),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model",
        _stateful_factory(_NARR, _NARR),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model",
        _stateful_factory(_NARR_R, _NARR_R),
    )
    monkeypatch.setattr(
        pricing_mod, "get_chat_model",
        _stateful_factory(_NARR_P, _NARR_P),
    )

    fuel_calls = {"n": 0}
    route_calls = {"n": 0}
    lookup_calls = {"n": 0}

    def count_fuel():
        fuel_calls["n"] += 1
        return FuelData(
            price=31.0, date="2026-04-25", source="eppo_live",
            baseline=29.94, delta_pct=0.0354,
        )

    def count_route(origin, destination):
        route_calls["n"] += 1
        return RouteData(
            origin=origin, destination=destination,
            distance_km=32.0, duration_min=45,
            traffic_severity=2, zone="central-1",
        )

    def count_lookup(*args, **kwargs):
        lookup_calls["n"] += 1
        return RateResult(
            base_rate=300.0, currency="THB", rate_tier="26-50kg",
        )

    mocker.patch.object(fuel_mod, "fetch_fuel_price", side_effect=count_fuel)
    mocker.patch.object(route_mod, "calculate_route", side_effect=count_route)
    mocker.patch.object(
        pricing_mod, "lookup_rate", side_effect=count_lookup,
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "t-vyj-followup"}}

    # Turn 1 — establishes caches.
    state = _empty_state(
        "Calculate surcharge for 50kg retail_standard from "
        "Bangkok to Pathum Thani"
    )
    result1 = await graph.ainvoke(state, config=cfg)
    assert result1["surcharge_result"] is not None
    assert fuel_calls["n"] == 1
    assert route_calls["n"] == 1
    assert lookup_calls["n"] == 1

    # Turn 2 — parameter-switch follow-up; reproduces the 999.1 bug shape.
    followup = {
        "messages": [
            {
                "role": "user",
                "content": "What if I switched it to a Bounce shipment "
                           "instead?",
            }
        ]
    }
    result2 = await graph.ainvoke(followup, config=cfg)

    # Headline assertion: graph routed through pricing despite the LLM's
    # clarify emission (without the 999.1 fix this would be None).
    assert result2["surcharge_result"] is not None
    assert result2["shipping_type"] == "bounce"
    # D-12 cache hits: fuel + route NOT re-fetched on turn 2.
    assert fuel_calls["n"] == 1
    assert route_calls["n"] == 1
    # Rate re-looked-up because shipping_type changed.
    assert lookup_calls["n"] == 2
    # Final payload renders successfully.
    assert result2["final_payload"]["status"] == "ok"


# ---------------------------------------------------------------------------
# Test 9: Plan 05-08 gap-1 E2E — reproduces UAT test 3 failure verbatim.
# Q1: "Surcharge for 15kg bounce Bangkok to Nonthaburi" populates caches +
# shipping_type=bounce + destination=Nonthaburi. Q2: "What about 25kg
# instead?" — the LLM hallucinates shipping_type=retail_standard +
# destination=Chiang Mai (truthy, so 999.1 merge accepts the hallucinations).
# With the gap-1 fix, the new inheritance branch nulls out those
# hallucinations, the 999.1 merge inherits bounce + Nonthaburi, and the
# resulting surcharge uses the right multiplier.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_followup_25kg_preserves_bounce_and_nonthaburi(
    monkeypatch, mocker, in_memory_checkpointer,
):
    """gap-1 E2E reproducer for UAT test 3: a 25kg follow-up MUST inherit
    shipping_type='bounce' and destination='Nonthaburi' from the prior turn
    even when the planner LLM hallucinates retail_standard and Chiang Mai.
    """
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    # Turn 1: standard surcharge — fan-out promotion then post-fanout
    # cascade promotes to calculate_price (one extra planner call after
    # the parallel fuel+route superstep).
    turn1 = [
        _planner_response(
            "fetch_fuel",
            shipping_type="bounce",
            weight_kg=15.0,
            origin="Bangkok",
            destination="Nonthaburi",
        ),
        _planner_response(
            "calculate_price",
            shipping_type="bounce",
            weight_kg=15.0,
            origin="Bangkok",
            destination="Nonthaburi",
        ),
    ]
    # Turn 2: the deliberately hallucinated emission matching the UAT
    # bug shape. weight_kg=25 (legitimately changed by the user), but
    # shipping_type='retail_standard' and destination='Chiang Mai' are
    # hallucinated. user_intent='followup_query' triggers the gap-1
    # inheritance branch.
    turn2 = [
        _planner_response(
            "fetch_fuel",
            user_intent="followup_query",
            shipping_type="retail_standard",
            weight_kg=25.0,
            origin=None,
            destination="Chiang Mai",
        ),
    ]
    planner_responses = turn1 + turn2

    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(*planner_responses),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model",
        _stateful_factory(_NARR, _NARR),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model",
        _stateful_factory(_NARR_R, _NARR_R),
    )
    monkeypatch.setattr(
        pricing_mod, "get_chat_model",
        _stateful_factory(_NARR_P, _NARR_P),
    )

    fuel_calls = {"n": 0}
    route_calls = {"n": 0}
    lookup_calls = {"n": 0}

    def count_fuel():
        fuel_calls["n"] += 1
        return FuelData(
            price=31.0, date="2026-05-03", source="eppo_live",
            baseline=29.94, delta_pct=0.0354,
        )

    def count_route(origin, destination):
        route_calls["n"] += 1
        return RouteData(
            origin=origin, destination=destination,
            distance_km=19.2, duration_min=30,
            traffic_severity=1, zone="central-1",
        )

    def count_lookup(*args, **kwargs):
        lookup_calls["n"] += 1
        return RateResult(
            base_rate=140.0, currency="THB", rate_tier="11-25kg",
        )

    mocker.patch.object(fuel_mod, "fetch_fuel_price", side_effect=count_fuel)
    mocker.patch.object(route_mod, "calculate_route", side_effect=count_route)
    mocker.patch.object(
        pricing_mod, "lookup_rate", side_effect=count_lookup,
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "t-uat-test3"}}

    # Turn 1 — establishes caches + shipping_type=bounce +
    # destination=Nonthaburi.
    state = _empty_state(
        "Surcharge for 15kg bounce Bangkok to Nonthaburi"
    )
    result1 = await graph.ainvoke(state, config=cfg)
    assert result1["surcharge_result"] is not None
    assert result1["shipping_type"] == "bounce"
    assert result1["destination"] == "Nonthaburi"
    assert fuel_calls["n"] == 1
    assert route_calls["n"] == 1

    # Turn 2 — UAT bug reproducer: "What about 25kg instead?" with the
    # planner LLM scripted to hallucinate retail_standard + Chiang Mai.
    followup = {
        "messages": [
            {"role": "user", "content": "What about 25kg instead?"}
        ]
    }
    result2 = await graph.ainvoke(followup, config=cfg)

    # Headline assertion: gap-1 fix preserved bounce + Nonthaburi despite
    # the LLM's hallucinations. Without the fix shipping_type would be
    # 'retail_standard' and destination would be 'Chiang Mai'.
    snapshot = await graph.aget_state(cfg)
    assert snapshot.values["shipping_type"] == "bounce"
    assert snapshot.values["destination"] == "Nonthaburi"
    assert snapshot.values["weight_kg"] == 25.0
    # And the post-turn-2 result echoes the same.
    assert result2["shipping_type"] == "bounce"
    assert result2["destination"] == "Nonthaburi"
    assert result2["weight_kg"] == 25.0
    # D-12 cache hits: fuel + route NOT re-fetched on turn 2 (route still
    # matches prior Bangkok->Nonthaburi after inheritance).
    assert fuel_calls["n"] == 1
    assert route_calls["n"] == 1
    # Rate re-looked-up for the new 25kg weight tier.
    assert lookup_calls["n"] == 2


# ---------------------------------------------------------------------------
# Plan 05-09 — gap-2 E2E regression (2026-05-03)
#
# UAT test 4 reproducer: a Bangkok -> Lop Buri query with the calculate_route
# tool stubbed to raise the same ValueError the live tool raises for
# out-of-Bangkok-Metro destinations. Without the gap-2 fix the exception
# bubbles through _wrap_error_sink (which re-raises ValueError unchanged)
# and out the SSE error channel, dead-ending the user. With the fix
# route_agent_node catches the zone-miss prefix, appends to state.errors,
# returns next_step='respond' — Planner short-circuits on errors (D-24)
# and Response renders a 'partial' clarify response naming route_agent.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_out_of_metro_destination_renders_clarify(
    monkeypatch, mocker, in_memory_checkpointer,
):
    """gap-2 E2E: Bangkok -> Lop Buri produces status='partial' clarify
    prose mentioning route_agent; NO uncaught ValueError reaches the
    SSE error channel."""
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod

    # Phase 5 D-01: with all extraction fields present and both caches
    # stale on a fresh thread, the planner promotes fetch_fuel to
    # fanout_fuel_route. Fuel runs successfully; route_agent catches the
    # zone-miss ValueError, appends to state.errors, returns
    # next_step='respond'. Planner is re-entered, sees state.errors, and
    # short-circuits to respond. So we need TWO planner LLM responses:
    # the initial fanout-trigger and the post-error short-circuit (the
    # latter is actually consumed by the D-24 errors guard before the
    # LLM call, but we provide it defensively).
    planner_responses = [
        _planner_response(
            "fetch_fuel",
            shipping_type="retail_fast",
            weight_kg=200.0,
            origin="Bangkok",
            destination="Lop Buri",
        ),
        _planner_response(
            "respond",
            shipping_type="retail_fast",
            weight_kg=200.0,
            origin="Bangkok",
            destination="Lop Buri",
        ),
    ]
    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(*planner_responses),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model",
        _stateful_factory(_NARR),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model",
        _stateful_factory(_NARR_R),
    )

    # Fuel succeeds (so the parallel fan-out exercises the route ValueError
    # path concurrently with a successful fuel fetch — operator.add reducer
    # safely merges both branches).
    mocker.patch.object(
        fuel_mod, "fetch_fuel_price",
        return_value=FuelData(
            price=31.0, date="2026-04-25", source="eppo_live",
            baseline=29.94, delta_pct=0.0354,
        ),
    )

    # Route raises the same ValueError the live tool raises for
    # destinations outside the central-1/2/3 zone set.
    def raise_zone_miss(origin, destination):
        raise ValueError(f"No Bangkok Metro zone for {destination!r}")

    mocker.patch.object(
        route_mod, "calculate_route", side_effect=raise_zone_miss,
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "t-gap2-lop-buri"}}
    state = _empty_state(
        "Surcharge for 200kg retail_fast Bangkok to Lop Buri"
    )

    # CRITICAL: this must NOT raise — the gap-2 fix converts the ValueError
    # to a graceful state.errors entry inside route_agent_node, BEFORE
    # _wrap_error_sink sees it.
    result = await graph.ainvoke(state, config=cfg)

    # No surcharge produced (route data missing -> can't calculate).
    assert result["surcharge_result"] is None

    # state.errors populated by route_agent
    assert len(result["errors"]) >= 1
    route_err = next(
        (e for e in result["errors"] if e.get("node") == "route_agent"),
        None,
    )
    assert route_err is not None
    assert route_err["exception_type"] == "ValueError"
    assert route_err["message"].startswith("No Bangkok Metro zone")

    # Response Node rendered status='partial' clarify response.
    payload = result["final_payload"]
    assert payload["status"] == "partial"
    assert payload["surcharge_result"] is None
    md = payload["markdown"]
    assert "Could not complete analysis" in md
    assert "route_agent" in md


# ---------------------------------------------------------------------------
# Plan 05-10 / gap-3 E2E (2026-05-03): UAT test 6 reproducer.
# News/trend queries previously triggered planner_count=5, search_agent_count=5
# (D-04 budget exhaust), AND the response prose mis-rendered "I need a bit more
# information to calculate your surcharge. (planner_loop_budget_exhausted)".
# Fix: planner early-returns when state.search_context is populated AND
# user_intent in {news_query, out_of_scope}; response_node renders the new
# 'search_only' status prose ("Here's the latest market context.") with the
# Market context blockquote prepended (D-11).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_news_query_no_loop_renders_market_context(
    monkeypatch, mocker, in_memory_checkpointer,
):
    """gap-3 E2E: a news query produces ONE search_agent invocation +
    exactly TWO planner invocations (initial routing + early-return short-
    circuit) — NOT 5 + 5 with the misleading clarify prose. Final markdown
    contains the Market context blockquote summary and does NOT contain
    "I need a bit more information to calculate your surcharge".
    """
    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import search_agent as search_mod
    from backend.agent.tools.models import SearchResult, SearchSource

    # Single planner LLM response: news_query → search_context. With the
    # gap-3 fix, the second planner re-entry early-returns BEFORE calling the
    # LLM, so we only need one scripted response.
    planner_responses = [
        _planner_response(
            "search_context",
            user_intent="news_query",
            shipping_type=None,
            weight_kg=None,
            origin=None,
            destination=None,
        ),
    ]
    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(*planner_responses),
    )
    # search_agent narration LLM — invalid JSON forces deterministic fallback
    # so reasoning == result.summary.
    monkeypatch.setattr(
        search_mod, "get_chat_model",
        _stateful_factory("not json"),
    )

    fake_search = SearchResult(
        query="Why are diesel prices rising this week?",
        summary="Diesel prices up 3% on supply concerns this week",
        sources=[
            SearchSource(
                title="EPPO weekly diesel report",
                url="https://example.com/diesel",
                snippet="Diesel B7 retail price up 3%.",
                published_at="2026-05-01",
            ),
            SearchSource(
                title="Bangkok Post fuel update",
                url="https://example.com/bp-fuel",
                snippet="Refinery shutdown nudges Thai diesel prices.",
                published_at="2026-05-02",
            ),
        ],
        fetched_at="2026-05-03T10:00:00Z",
    )
    mocker.patch.object(
        search_mod, "search_fuel_news", return_value=fake_search,
    )

    graph = build_graph(checkpointer=in_memory_checkpointer)
    cfg = {"configurable": {"thread_id": "t-gap3-news"}}
    state = _empty_state("Why are diesel prices rising this week?")
    result = await graph.ainvoke(state, config=cfg)

    # Final payload exists.
    final_payload = result["final_payload"]
    assert final_payload is not None

    # Count planner + search_agent invocations from the reasoning_trace.
    trace = result["reasoning_trace"]
    planner_count = sum(1 for e in trace if e.get("agent") == "planner")
    search_agent_count = sum(
        1 for e in trace if e.get("agent") == "search_agent"
    )

    # Headline assertions: NO loop. Exactly 2 planner steps (initial routing +
    # short-circuit early-return) and exactly 1 search_agent invocation.
    assert planner_count == 2
    assert search_agent_count == 1

    # The clarification_reason MUST NOT be the budget-exhaustion sentinel.
    assert (
        result.get("clarification_reason") != "planner_loop_budget_exhausted"
    )

    # Markdown contains the Market context blockquote summary.
    md = final_payload["markdown"]
    assert "Diesel prices up 3% on supply concerns this week" in md

    # Markdown does NOT contain the misleading clarify prose.
    assert "I need a bit more information to calculate your surcharge" not in md

    # Status is NOT 'clarify' — it's either 'ok' or 'search_only'.
    assert final_payload["status"] != "clarify"
