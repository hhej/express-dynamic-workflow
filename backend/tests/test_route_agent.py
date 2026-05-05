"""Tests for ORCH-03: Route Agent node."""
from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from backend.agent.nodes import route_agent as mod
from backend.agent.nodes.route_agent import route_agent_node
from backend.agent.tools.models import RouteData

_FAKE_ROUTE = RouteData(
    origin="Bangkok",
    destination="Nonthaburi",
    distance_km=15.2,
    duration_min=30,
    traffic_severity=3,
    zone="central-1",
)


def _scripted_llm(response_json: str) -> FakeMessagesListChatModel:
    return FakeMessagesListChatModel(
        responses=[AIMessage(content=response_json)]
    )


def _state_with_route(sample_agent_state):
    s = dict(sample_agent_state)
    s["origin"] = "Bangkok"
    s["destination"] = "Nonthaburi"
    return s


def test_state_updates_route_data_and_trace(
    sample_agent_state, mocker, monkeypatch
):
    mocker.patch.object(mod, "calculate_route", return_value=_FAKE_ROUTE)
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"summary": "15.2 km, 30 min, moderate traffic, central-1.", '
            '"traffic_label": "moderate"}'
        ),
    )

    result = route_agent_node(_state_with_route(sample_agent_state))

    assert set(result.keys()) >= {"route_data", "reasoning_trace"}
    assert result["route_data"]["origin"] == "Bangkok"
    assert result["route_data"]["destination"] == "Nonthaburi"
    assert len(result["reasoning_trace"]) == 1


def test_zone_in_output(sample_agent_state, mocker, monkeypatch):
    mocker.patch.object(mod, "calculate_route", return_value=_FAKE_ROUTE)
    monkeypatch.setattr(
        mod, "get_chat_model",
        lambda **_: _scripted_llm(
            '{"summary": "ok", "traffic_label": "moderate"}'
        ),
    )

    result = route_agent_node(_state_with_route(sample_agent_state))
    assert result["route_data"]["zone"] == "central-1"


def test_trace_schema(sample_agent_state, mocker, monkeypatch):
    mocker.patch.object(mod, "calculate_route", return_value=_FAKE_ROUTE)
    monkeypatch.setattr(
        mod, "get_chat_model",
        lambda **_: _scripted_llm(
            '{"summary": "ok", "traffic_label": "moderate"}'
        ),
    )

    result = route_agent_node(_state_with_route(sample_agent_state))
    entry = result["reasoning_trace"][0]

    required = {
        "step", "agent", "tool", "tool_input", "tool_output",
        "reasoning", "timestamp", "status",
    }
    assert required.issubset(entry.keys())
    assert entry["agent"] == "route_agent"
    assert entry["tool"] == "calculate_route"
    assert entry["status"] == "ok"
    assert entry["tool_input"] == {"origin": "Bangkok", "destination": "Nonthaburi"}
    assert entry["timestamp"].endswith("Z")


def test_missing_origin_or_destination_raises(sample_agent_state):
    """D-10: origin/destination must be pre-extracted by Planner."""
    with pytest.raises(ValueError, match="origin|destination"):
        route_agent_node(sample_agent_state)  # no origin/destination set


def test_gemini_failure_triggers_deterministic_fallback(
    sample_agent_state, mocker, monkeypatch
):
    mocker.patch.object(mod, "calculate_route", return_value=_FAKE_ROUTE)

    # Broken LLM: .invoke() raises to exercise the D-11 fallback path. The
    # route_agent_node uses raw .invoke() + JSON parsing (same approach as
    # fuel_agent_node; see Rule 1 deviation noted in 02-05 SUMMARY).
    class _BrokenLLM:
        def invoke(self, *a, **kw):
            raise RuntimeError("simulated Gemini failure")

    monkeypatch.setattr(mod, "get_chat_model", lambda **_: _BrokenLLM())

    result = route_agent_node(_state_with_route(sample_agent_state))
    entry = result["reasoning_trace"][0]
    assert entry["status"] == "ok"
    assert "central-1" in entry["reasoning"] or "15.2" in entry["reasoning"]


def test_fetched_at_added_to_dump(sample_agent_state, mocker, monkeypatch):
    """D-13: route_agent_node stamps fetched_at (UTC ISO-8601 'Z') into the
    returned route_data dict so planner_node can compute the TTL skip."""
    from datetime import datetime

    mocker.patch.object(mod, "calculate_route", return_value=_FAKE_ROUTE)
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"summary": "ok", "traffic_label": "moderate"}'
        ),
    )

    result = route_agent_node(_state_with_route(sample_agent_state))

    fetched_at = result["route_data"]["fetched_at"]
    assert isinstance(fetched_at, str)
    assert fetched_at.endswith("Z")
    # Parses as ISO-8601 without raising.
    datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Plan 05-09 (gap-2 fix, 2026-05-03): out-of-Bangkok-Metro destinations
# raise ValueError("No Bangkok Metro zone for ...") from
# calculate_route._zone_for_destination. The Phase 3 D-23 retry-allow-list
# excludes ValueError and the Phase 3 D-24 _wrap_error_sink re-raises
# ValueError unchanged, so without an in-node catch the exception
# propagates as an SSE error event with no recovery path. The fix
# selectively catches the zone-miss prefix and converts it to a graceful
# state.errors entry + next_step='respond' (matching the 999.something
# retry-exhaustion sink shape so response_node can render a 'partial'
# clarify response). The D-10 ValueError on missing origin/destination
# MUST still bubble per Phase 2 Plan 05 decision.
# ---------------------------------------------------------------------------


def test_zone_miss_returns_clarify_eligible_state(
    sample_agent_state, mocker, monkeypatch
):
    """gap-2: out-of-Metro destination should NOT raise; instead append a
    structured entry to state.errors and route to respond."""
    state = dict(sample_agent_state)
    state["origin"] = "Bangkok"
    state["destination"] = "Lop Buri"

    mocker.patch.object(
        mod,
        "calculate_route",
        side_effect=ValueError("No Bangkok Metro zone for 'Lop Buri'"),
    )
    # Gemini is never reached on this path (we short-circuit before
    # narration), but install a benign LLM stub anyway so a stray call
    # would fail loudly rather than silently 404 the test.
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"summary": "n/a", "traffic_label": "moderate"}'
        ),
    )

    result = route_agent_node(state)

    # Headline assertion: no raise + the gap-2 contract is honored.
    assert "errors" in result
    assert isinstance(result["errors"], list)
    assert len(result["errors"]) == 1
    err = result["errors"][0]
    assert err["node"] == "route_agent"
    assert err["exception_type"] == "ValueError"
    assert err["message"].startswith("No Bangkok Metro zone")
    assert "timestamp" in err
    assert result["next_step"] == "respond"

    # Trace panel surfaces the cause as a 'warn' status so the FE
    # reasoning panel renders the failure visibly (not silent).
    trace = result.get("reasoning_trace") or []
    assert len(trace) == 1
    assert trace[0]["agent"] == "route_agent"
    assert trace[0]["status"] == "warn"


def test_missing_origin_destination_still_raises(sample_agent_state):
    """gap-2 invariant: the D-10 ValueError on missing origin/destination
    MUST still bubble — only the zone-miss ValueError is caught."""
    # No origin/destination set on the state; the gap-2 catch must NOT
    # swallow this — it surfaces a Planner pre-extraction contract
    # violation eagerly per Phase 2 Plan 05 decision.
    with pytest.raises(ValueError, match="route_agent_node requires both"):
        route_agent_node(dict(sample_agent_state))
