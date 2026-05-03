"""OBS-01 / OBS-03 — observability.py helpers.

Coverage:
- get_callback_handler returns None in no-op mode (D-13).
- seed_trace_id is deterministic given the same (thread_id, turn_idx).
- post_formula_accuracy_score posts value=1.0 on match, 0.0 on divergence.
- post_formula_accuracy_score swallows internal errors (fire-and-forget D-15).
"""
from __future__ import annotations

from unittest.mock import MagicMock


def test_callback_handler_no_op_mode(mock_langfuse):
    """D-13: missing keys → None handler."""
    from backend.agent.observability import get_callback_handler

    assert get_callback_handler() is None
    assert get_callback_handler(trace_id="0123456789abcdef0123456789abcdef") is None


def test_seed_trace_id_deterministic(mock_langfuse):
    """D-14: same (thread_id, turn_idx) → same trace_id (no-op hash mode)."""
    from backend.agent.observability import seed_trace_id

    a = seed_trace_id("abc-123", 0)
    b = seed_trace_id("abc-123", 0)
    c = seed_trace_id("abc-123", 1)
    assert a == b
    assert a != c
    assert len(a) == 32 and all(ch in "0123456789abcdef" for ch in a)


def test_formula_accuracy_match(monkeypatch):
    """D-15: oracle == agent → value=1.0 Score posted."""
    from backend.agent import observability as obs

    client = MagicMock()
    monkeypatch.setattr(obs, "get_langfuse_client", lambda: client)
    # Use the same inputs the Phase 1 pure function would compute against.
    # Construct an agent_result whose total exactly matches the oracle by
    # invoking the oracle ourselves and reading its total.
    from backend.agent.tools.calculate_surcharge import calculate_surcharge

    oracle = calculate_surcharge(
        base_rate=100.0,
        current_diesel_price=29.94,  # baseline -> 0% surcharge
        shipping_type="bounce",
        traffic_severity=1,
    )
    obs.post_formula_accuracy_score(
        trace_id="t1",
        base_rate=100.0,
        current_diesel_price=29.94,
        shipping_type="bounce",
        traffic_severity=1,
        agent_result={"total": oracle.total},
    )
    client.create_score.assert_called_once()
    kwargs = client.create_score.call_args.kwargs
    assert kwargs["trace_id"] == "t1"
    assert kwargs["name"] == "formula_accuracy"
    assert kwargs["value"] == 1.0


def test_formula_accuracy_divergence(monkeypatch):
    """D-15: oracle != agent → value=0.0 Score posted with reason."""
    from backend.agent import observability as obs

    client = MagicMock()
    monkeypatch.setattr(obs, "get_langfuse_client", lambda: client)
    obs.post_formula_accuracy_score(
        trace_id="t2",
        base_rate=100.0,
        current_diesel_price=29.94,
        shipping_type="bounce",
        traffic_severity=1,
        agent_result={"total": 999.0},  # deliberately wrong
    )
    client.create_score.assert_called_once()
    kwargs = client.create_score.call_args.kwargs
    assert kwargs["value"] == 0.0
    assert kwargs["comment"] is not None
    assert "oracle=" in kwargs["comment"]


def test_formula_accuracy_swallows_errors(monkeypatch, caplog):
    """D-15: any internal exception is logged + swallowed."""
    import logging

    from backend.agent import observability as obs

    client = MagicMock()
    client.create_score.side_effect = RuntimeError("network down")
    monkeypatch.setattr(obs, "get_langfuse_client", lambda: client)
    # Ensure the warning emitted by observability.py is captured.
    caplog.set_level(logging.WARNING, logger="backend.agent.observability")
    # Should NOT raise.
    obs.post_formula_accuracy_score(
        trace_id="t3",
        base_rate=100.0,
        current_diesel_price=29.94,
        shipping_type="bounce",
        traffic_severity=1,
        agent_result={"total": 100.0},
    )
    assert "auto-eval failed" in caplog.text.lower()
