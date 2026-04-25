"""Tests for ORCH-02: Fuel Agent node."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from backend.agent.nodes import fuel_agent as mod
from backend.agent.nodes.fuel_agent import fuel_agent_node
from backend.agent.tools.models import FuelData

_FAKE_FUEL = FuelData(
    price=31.00,
    date="2026-04-18",
    unit="THB/L",
    source="eppo_cached_csv",
    baseline=29.94,
    delta_pct=0.0354,
)


def _scripted_llm(response_json: str) -> FakeMessagesListChatModel:
    return FakeMessagesListChatModel(
        responses=[AIMessage(content=response_json)]
    )


def test_state_updates_fuel_data_and_trace(
    sample_agent_state, mocker, monkeypatch
):
    mocker.patch.object(mod, "fetch_fuel_price", return_value=_FAKE_FUEL)
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"summary": "Diesel 3.5% above baseline.", "trend": "above_baseline"}'
        ),
    )

    result = fuel_agent_node(sample_agent_state)

    assert set(result.keys()) >= {"fuel_data", "reasoning_trace"}
    assert result["fuel_data"]["price"] == 31.00
    assert result["fuel_data"]["source"] == "eppo_cached_csv"
    assert isinstance(result["reasoning_trace"], list)
    assert len(result["reasoning_trace"]) == 1


def test_trace_entry_matches_d12_schema(
    sample_agent_state, mocker, monkeypatch
):
    mocker.patch.object(mod, "fetch_fuel_price", return_value=_FAKE_FUEL)
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"summary": "Diesel 3.5% above baseline.", "trend": "above_baseline"}'
        ),
    )

    result = fuel_agent_node(sample_agent_state)
    entry = result["reasoning_trace"][0]

    required_keys = {
        "step", "agent", "tool", "tool_input", "tool_output",
        "reasoning", "timestamp", "status",
    }
    assert required_keys.issubset(entry.keys())
    assert entry["agent"] == "fuel_agent"
    assert entry["tool"] == "fetch_fuel_price"
    assert entry["status"] == "ok"
    assert entry["timestamp"].endswith("Z")
    assert entry["tool_output"]["price"] == 31.00


def test_gemini_failure_triggers_deterministic_fallback(
    sample_agent_state, mocker, monkeypatch
):
    mocker.patch.object(mod, "fetch_fuel_price", return_value=_FAKE_FUEL)

    # Replace get_chat_model with a model whose invoke raises (simulating a
    # transient Gemini failure / unreachable API). Also models the case where
    # .with_structured_output() is unavailable, since the node uses raw
    # .invoke() + JSON parsing.
    class _BrokenLLM:
        def invoke(self, *a, **kw):
            raise RuntimeError("simulated Gemini failure")

    monkeypatch.setattr(mod, "get_chat_model", lambda **_: _BrokenLLM())

    result = fuel_agent_node(sample_agent_state)
    entry = result["reasoning_trace"][0]

    assert entry["status"] == "ok"  # deterministic fallback still ok
    # Deterministic narration mentions the numeric price and a direction.
    reasoning = entry["reasoning"].lower()
    assert "31" in entry["reasoning"] or "above" in reasoning
    assert "baseline" in reasoning


def test_reasoning_includes_trend_from_llm_when_successful(
    sample_agent_state, mocker, monkeypatch
):
    mocker.patch.object(mod, "fetch_fuel_price", return_value=_FAKE_FUEL)
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"summary": "Diesel 3.5% above baseline.", "trend": "above_baseline"}'
        ),
    )

    result = fuel_agent_node(sample_agent_state)
    assert "above_baseline" in result["reasoning_trace"][0]["reasoning"]


@pytest.mark.skip(
    reason="Wave 0 placeholder; D-13 implementation lands in Plan 03-02"
)
def test_fetched_at_added_to_dump():
    # Implemented in Plan 03-02 -- fuel_agent_node decorates fuel_data dump
    # with `fetched_at` (UTC ISO 8601) so planner_node can compute TTL skip.
    ...
