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
