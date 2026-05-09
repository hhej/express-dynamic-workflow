"""ORCH-09 — HITL approval gate tests (D-04/D-05/D-07/D-08).

Plan 05-05 Task 1 RED phase: tests written before implementation.

Covers:
- D-04 bypass path (low-value totals): no trace, no interrupt, sets approve.
- D-05 interrupt path (high-value totals): emits warn-status pre-trace and
  calls langgraph.types.interrupt() with the surcharge_result + threshold.
- D-08 trace shape: pre-pause status='warn'; post-resume status='ok' with
  the user decision recorded.
- D-07 resume contract: True -> approval_decision='approve';
  False (or anything not in ('approve', True)) -> 'deny'.
- Pitfall 6 graph topology: pricing_agent -> hitl_gate -> response replaces
  the Phase 3 pricing_agent -> planner edge.
"""
from __future__ import annotations

import pytest

from backend.agent.nodes import hitl_gate as hitl_mod


def test_low_value_total_bypasses_gate(mock_pricing_low):
    """D-04: total <= threshold -> approve without interrupt or trace."""
    state = {"surcharge_result": mock_pricing_low, "reasoning_trace": []}
    result = hitl_mod.hitl_gate_node(state)
    assert result == {"approval_decision": "approve"}
    # No trace entry on the bypass path.
    assert "reasoning_trace" not in result


def test_high_value_total_pauses_for_approval(mock_pricing_high, monkeypatch):
    """D-05: total > threshold triggers interrupt(); tested by patching
    interrupt to a sentinel exception.
    """
    captured: dict = {}

    class InterruptSentinel(Exception):
        pass

    def fake_interrupt(payload):
        captured["payload"] = payload
        raise InterruptSentinel()

    monkeypatch.setattr(hitl_mod, "interrupt", fake_interrupt)
    state = {"surcharge_result": mock_pricing_high, "reasoning_trace": []}
    with pytest.raises(InterruptSentinel):
        hitl_mod.hitl_gate_node(state)
    assert captured["payload"]["type"] == "approval_required"
    assert captured["payload"]["surcharge_result"] == mock_pricing_high
    assert captured["payload"]["threshold"] > 0


def test_high_value_total_emits_pre_pause_trace_entry(
    mock_pricing_high, monkeypatch
):
    """D-08: pre-pause trace entry status='warn' with threshold + total
    in tool_input. We patch interrupt to RETURN False (deny) so the
    function runs to completion and exposes the full reasoning_trace.
    """
    monkeypatch.setattr(hitl_mod, "interrupt", lambda payload: False)
    state = {"surcharge_result": mock_pricing_high, "reasoning_trace": []}
    result = hitl_mod.hitl_gate_node(state)
    traces = result["reasoning_trace"]
    assert len(traces) == 2
    pre = traces[0]
    assert pre["agent"] == "hitl_gate"
    assert pre["tool"] == "interrupt"
    assert pre["status"] == "warn"
    assert pre["tool_input"]["threshold"] > 0
    assert pre["tool_input"]["total"] == mock_pricing_high["total"]
    assert pre["tool_output"]["decision_pending"] is True


def test_resume_approve_writes_approval_decision(
    mock_pricing_high, monkeypatch
):
    """D-08 resume: True -> approval_decision='approve' + post-trace
    status='ok' with decision recorded."""
    monkeypatch.setattr(hitl_mod, "interrupt", lambda payload: True)
    state = {"surcharge_result": mock_pricing_high, "reasoning_trace": []}
    result = hitl_mod.hitl_gate_node(state)
    assert result["approval_decision"] == "approve"
    post = result["reasoning_trace"][1]
    assert post["status"] == "ok"
    assert post["tool_output"]["decision"] == "approve"


def test_resume_deny_writes_approval_decision(
    mock_pricing_high, monkeypatch
):
    """D-07 resume: False -> approval_decision='deny'."""
    monkeypatch.setattr(hitl_mod, "interrupt", lambda payload: False)
    state = {"surcharge_result": mock_pricing_high, "reasoning_trace": []}
    result = hitl_mod.hitl_gate_node(state)
    assert result["approval_decision"] == "deny"
    post = result["reasoning_trace"][1]
    assert post["tool_output"]["decision"] == "deny"


def test_graph_topology_pricing_to_hitl_to_response(in_memory_checkpointer):
    """Pitfall 6 (Phase 5) + Quick task 260509-utd: verify
    pricing -> guard_output -> hitl_gate -> response replaces
    the original Phase 3 pricing -> planner edge AND the Phase 5
    pricing -> hitl_gate direct edge.
    """
    from backend.agent.graph import build_graph
    graph = build_graph(in_memory_checkpointer)
    gobj = graph.get_graph()
    edges = [(e.source, e.target) for e in gobj.edges]
    # Quick task 260509-utd UTD-03: guard_output sits between pricing
    # and hitl_gate so the cap/floor/schema invariants are re-validated
    # before the optional human-in-the-loop pause.
    assert ("pricing_agent", "guard_output") in edges
    assert ("guard_output", "hitl_gate") in edges
    assert ("hitl_gate", "response") in edges
    # The Phase 5 direct pricing -> hitl_gate edge must be REPLACED
    # (not augmented) so guard_output cannot be bypassed.
    assert ("pricing_agent", "hitl_gate") not in edges
    assert ("pricing_agent", "planner") not in edges
