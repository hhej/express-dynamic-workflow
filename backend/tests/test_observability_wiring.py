"""OBS-01 / OBS-03 — end-to-end wiring tests.

Distinct from test_observability.py (helper unit tests in Plan 05-01) —
these tests assert chat.py and pricing_agent.py CALL the helpers with
the right arguments and threading the trace_id correctly.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# -----------------------------------------------------------------------------
# Task 1: chat.py _make_config wiring (Plan 05-02)
# -----------------------------------------------------------------------------


def test_chat_attaches_callback_when_enabled(monkeypatch):
    """Plan 05-02 Task 1 — when keys present, _make_config returns a config with [handler]."""
    from backend.api.routes import chat as chat_mod

    fake_handler = MagicMock(name="CallbackHandler")
    monkeypatch.setattr(
        chat_mod, "get_callback_handler", lambda trace_id=None: fake_handler
    )
    monkeypatch.setattr(
        chat_mod, "seed_trace_id", lambda thread_id, turn_idx: "deadbeef" * 4
    )
    cfg = chat_mod._make_config("t-1", 0)
    assert cfg["callbacks"] == [fake_handler]
    assert cfg["configurable"]["thread_id"] == "t-1"
    assert cfg["metadata"]["langfuse_session_id"] == "t-1"
    assert cfg["metadata"]["langfuse_trace_id"] == "deadbeef" * 4
    assert cfg["metadata"]["langfuse_user_id"] == "demo"
    assert "express-surcharge" in cfg["metadata"]["langfuse_tags"]
    assert "turn-0" in cfg["metadata"]["langfuse_tags"]
    assert cfg["metadata"]["langfuse_trace_name"] == "express-surcharge-agent"
    assert cfg["run_name"] == "express-surcharge-agent"


def test_chat_skips_callback_when_disabled(monkeypatch):
    """D-13: when keys missing, callbacks list is empty."""
    from backend.api.routes import chat as chat_mod

    monkeypatch.setattr(
        chat_mod, "get_callback_handler", lambda trace_id=None: None
    )
    monkeypatch.setattr(
        chat_mod, "seed_trace_id", lambda thread_id, turn_idx: "abc" * 11 + "x"
    )
    cfg = chat_mod._make_config("t-2", 3)
    assert cfg["callbacks"] == []
    assert cfg["metadata"]["langfuse_trace_id"] == "abc" * 11 + "x"
    assert "turn-3" in cfg["metadata"]["langfuse_tags"]


# -----------------------------------------------------------------------------
# Task 2: pricing_agent.py auto-eval wiring (Plan 05-02)
# -----------------------------------------------------------------------------


def _full_pricing_state() -> dict:
    """A full AgentState shaped for pricing_agent_node to run end-to-end."""
    return {
        "messages": [{"role": "user", "content": "15kg Bounce Bangkok-Nonthaburi"}],
        "fuel_data": {
            "price": 30.0,
            "baseline": 29.94,
            "delta_pct": 0.002,
            "date": "2026-05-01",
            "unit": "THB/L",
            "source": "eppo_live",
        },
        "route_data": {
            "origin": "Bangkok",
            "destination": "Nonthaburi",
            "distance_km": 18.5,
            "duration_min": 30,
            "traffic_severity": 2,
            "zone": "central-1",
        },
        "shipping_type": "bounce",
        "weight_kg": 15.0,
        "surcharge_result": None,
        "reasoning_trace": [],
        "next_step": "",
        "errors": [],
    }


def _patch_pricing_llm(monkeypatch, pa_mod):
    """Force the pricing narration into the deterministic fallback path."""
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage

    monkeypatch.setattr(
        pa_mod,
        "get_chat_model",
        lambda **_: FakeMessagesListChatModel(
            responses=[AIMessage(content="not json — forces fallback")]
        ),
    )


def _patch_lookup_rate(monkeypatch, pa_mod):
    """Patch lookup_rate to return a deterministic RateResult so the node
    runs end-to-end without depending on the seeded SQLite file."""
    from backend.agent.tools.models import RateResult

    monkeypatch.setattr(
        pa_mod,
        "lookup_rate",
        lambda *a, **kw: RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )


def test_pricing_invokes_auto_eval(monkeypatch):
    """OBS-03: pricing_agent_node calls post_formula_accuracy_score with right inputs."""
    from backend.agent.nodes import pricing_agent as pa_mod

    captured: dict = {}

    def fake_post(*, trace_id, base_rate, current_diesel_price,
                  shipping_type, traffic_severity, agent_result):
        captured["trace_id"] = trace_id
        captured["base_rate"] = base_rate
        captured["current_diesel_price"] = current_diesel_price
        captured["shipping_type"] = shipping_type
        captured["traffic_severity"] = traffic_severity
        captured["agent_total"] = agent_result["total"]

    monkeypatch.setattr(pa_mod, "post_formula_accuracy_score", fake_post)
    _patch_lookup_rate(monkeypatch, pa_mod)
    _patch_pricing_llm(monkeypatch, pa_mod)

    state = _full_pricing_state()
    config = {"metadata": {"langfuse_trace_id": "trace-xyz-123"}}

    result = pa_mod.pricing_agent_node(state, config)

    assert "surcharge_result" in result
    # Auto-eval was invoked with the right inputs.
    assert captured["trace_id"] == "trace-xyz-123"
    assert captured["base_rate"] == 120.0
    assert captured["current_diesel_price"] == 30.0
    assert captured["shipping_type"] == "bounce"
    assert captured["traffic_severity"] == 2
    assert captured["agent_total"] == result["surcharge_result"]["total"]


def test_pricing_skips_auto_eval_when_no_trace_id(monkeypatch):
    """When config is None (unit test) — auto-eval is skipped silently."""
    from backend.agent.nodes import pricing_agent as pa_mod

    called = {"n": 0}

    def fake_post(**_):
        called["n"] += 1

    monkeypatch.setattr(pa_mod, "post_formula_accuracy_score", fake_post)
    _patch_lookup_rate(monkeypatch, pa_mod)
    _patch_pricing_llm(monkeypatch, pa_mod)

    # No config = no trace_id = skip.
    pa_mod.pricing_agent_node(_full_pricing_state(), None)
    assert called["n"] == 0

    # Config without metadata.langfuse_trace_id also skips.
    pa_mod.pricing_agent_node(_full_pricing_state(), {"metadata": {}})
    assert called["n"] == 0


def test_pricing_swallows_auto_eval_exception(monkeypatch):
    """D-15 fire-and-forget: even if post_formula_accuracy_score raises, the node returns surcharge_result."""
    from backend.agent.nodes import pricing_agent as pa_mod

    def boom(**_):
        raise RuntimeError("langfuse offline")

    monkeypatch.setattr(pa_mod, "post_formula_accuracy_score", boom)
    _patch_lookup_rate(monkeypatch, pa_mod)
    _patch_pricing_llm(monkeypatch, pa_mod)

    config = {"metadata": {"langfuse_trace_id": "x"}}
    # MUST NOT raise.
    result = pa_mod.pricing_agent_node(_full_pricing_state(), config)
    assert "surcharge_result" in result
