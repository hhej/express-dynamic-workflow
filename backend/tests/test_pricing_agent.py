"""Tests for ORCH-04: Pricing Agent node.

Covers D-08 (compound trace entry tool='lookup_rate+calculate_surcharge'),
D-09 (ValueError from lookup_rate propagates uncaught — Pricing Agent does
NOT swallow lookup misses), and D-11 (deterministic narration fallback when
Gemini fails).
"""
from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from backend.agent.nodes import pricing_agent as mod
from backend.agent.nodes.pricing_agent import pricing_agent_node
from backend.agent.tools.models import RateResult


def _scripted_llm(response_json: str) -> FakeMessagesListChatModel:
    return FakeMessagesListChatModel(
        responses=[AIMessage(content=response_json)]
    )


def _full_state() -> dict:
    return {
        "messages": [{"role": "user", "content": "15kg Bounce Bangkok-Nonthaburi"}],
        "fuel_data": {
            "price": 31.0,
            "baseline": 29.94,
            "delta_pct": 0.0354,
            "date": "2026-04-18",
            "unit": "THB/L",
            "source": "eppo_cached_csv",
            "fetched_at": "2026-04-25T03:00:00Z",
        },
        "route_data": {
            "origin": "Bangkok",
            "destination": "Nonthaburi",
            "distance_km": 18.0,
            "duration_min": 30,
            "traffic_severity": 2,
            "zone": "central-1",
            "fetched_at": "2026-04-25T03:00:00Z",
        },
        "shipping_type": "bounce",
        "weight_kg": 15.0,
        "surcharge_result": None,
        "reasoning_trace": [],
        "next_step": "",
        "origin": "Bangkok",
        "destination": "Nonthaburi",
        "user_intent": "surcharge_query",
        "missing_fields": [],
        "clarification_reason": None,
        "errors": [],
    }


def test_computes_surcharge_and_emits_trace(mocker, monkeypatch):
    """Pricing Agent looks up rate, calls surcharge tool, narrates,
    and emits ONE trace entry with tool='lookup_rate+calculate_surcharge'."""
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm(
            '{"summary": "Surcharge 4% on 120 THB base = 124.80 THB."}'
        ),
    )

    result = pricing_agent_node(_full_state())

    assert "surcharge_result" in result
    assert isinstance(result["surcharge_result"], dict)
    assert "surcharge_pct" in result["surcharge_result"]
    assert "total" in result["surcharge_result"]
    assert "capped" in result["surcharge_result"]

    assert len(result["reasoning_trace"]) == 1
    entry = result["reasoning_trace"][0]
    assert entry["agent"] == "pricing_agent"
    assert entry["tool"] == "lookup_rate+calculate_surcharge"
    assert entry["status"] == "ok"
    assert entry["timestamp"].endswith("Z")


def test_bubbles_value_error_from_lookup_rate(mocker, monkeypatch):
    """D-09: lookup_rate ValueError propagates — Pricing Agent does NOT wrap."""
    mocker.patch.object(
        mod, "lookup_rate", side_effect=ValueError("no rate")
    )
    # Gemini factory should never be called, but provide a stub anyway.
    monkeypatch.setattr(
        mod, "get_chat_model", lambda **_: _scripted_llm('{"summary": "x"}')
    )

    with pytest.raises(ValueError, match="no rate"):
        pricing_agent_node(_full_state())


def test_gemini_failure_deterministic_fallback(mocker, monkeypatch):
    """D-11: Gemini failure -> deterministic narration; trace stays status='ok'.

    The deterministic narration mentions the surcharge total or pct
    numerically, sourced from the surcharge tool's actual output.
    """
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )

    class _BrokenLLM:
        def invoke(self, *a, **kw):
            raise RuntimeError("simulated Gemini failure")

    monkeypatch.setattr(mod, "get_chat_model", lambda **_: _BrokenLLM())

    result = pricing_agent_node(_full_state())
    entry = result["reasoning_trace"][0]

    assert entry["status"] == "ok"
    # Deterministic narration includes a numeric reference (total or pct).
    surcharge = result["surcharge_result"]
    reasoning = entry["reasoning"]
    # Either the total or the pct (rounded) shows up in the narration.
    total_str = f"{surcharge['total']:.2f}"
    assert (
        total_str in reasoning
        or f"{surcharge['surcharge_pct']:.2%}" in reasoning
        or f"{surcharge['surcharge_pct']*100:.1f}" in reasoning
        or "120" in reasoning  # base rate
    )
