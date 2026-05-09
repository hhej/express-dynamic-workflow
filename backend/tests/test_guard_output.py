"""Quick task 260509-utd Task 2: guard_output_node unit tests.

Coverage map (PLAN behaviors -> requirement IDs):
- test_passthrough_valid              -> GUARD-OUT-04
- test_rejects_pct_overflow           -> GUARD-OUT-01
- test_rejects_pct_underflow          -> GUARD-OUT-01 (extension)
- test_rejects_nonpositive_total      -> GUARD-OUT-02
- test_rejects_negative_total         -> GUARD-OUT-02 (extension)
- test_rejects_missing_field          -> GUARD-OUT-03
- test_rejects_unknown_shipping_type  -> UTD-03 SHIPPING_MULTIPLIERS check
- test_rejects_nonpositive_weight     -> UTD-03 weight invariant
- test_violation_emits_trace          -> Pitfall 5 trace tagging
- test_passthrough_emits_no_trace     -> zero-overhead allow path
"""
from __future__ import annotations

from backend.agent.nodes.guard_output import (
    _route_from_guard_output,
    guard_output_node,
)


def _ok_state(**overrides) -> dict:
    base = {
        "messages": [],
        "fuel_data": {},
        "route_data": {},
        "shipping_type": "bounce",
        "weight_kg": 15.0,
        "surcharge_result": {
            "surcharge_pct": 0.10,
            "surcharge_amount": 50.0,
            "total": 250.0,
            "capped": False,
        },
        "reasoning_trace": [],
        "next_step": "",
        "origin": "Bangkok",
        "destination": "Nonthaburi",
        "user_intent": None,
        "missing_fields": [],
        "clarification_reason": None,
        "errors": [],
        "final_payload": None,
        "approval_decision": None,
        "search_context": None,
        "guard_decision": None,
        "tool_call_count": 3,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Pass-through (allow path is zero-overhead)
# ---------------------------------------------------------------------------


def test_passthrough_valid():
    out = guard_output_node(_ok_state())
    assert out["guard_decision"] == {
        "layer": "output",
        "category": "allow",
        "refused": False,
        "violations": [],
    }
    # Allow path leaves next_step alone so the natural pricing -> hitl_gate
    # -> response edge proceeds.
    assert "next_step" not in out


def test_passthrough_emits_no_trace():
    out = guard_output_node(_ok_state())
    assert "reasoning_trace" not in out
    assert _route_from_guard_output({"guard_decision": out["guard_decision"]}) == "hitl_gate"


# ---------------------------------------------------------------------------
# Refusals: surcharge_pct
# ---------------------------------------------------------------------------


def test_rejects_pct_overflow():
    state = _ok_state(surcharge_result={
        "surcharge_pct": 0.20,   # above SURCHARGE_CAP (0.15)
        "surcharge_amount": 100.0,
        "total": 600.0,
        "capped": False,
    })
    out = guard_output_node(state)
    assert out["guard_decision"]["refused"] is True
    assert out["guard_decision"]["category"] == "unsafe_output"
    assert out["next_step"] == "respond"
    assert any(
        "surcharge_pct" in v and "0.15" in v
        for v in out["guard_decision"]["violations"]
    ), out["guard_decision"]["violations"]
    assert _route_from_guard_output({"guard_decision": out["guard_decision"]}) == "response"


def test_rejects_pct_underflow():
    state = _ok_state(surcharge_result={
        "surcharge_pct": -0.10,
        "surcharge_amount": -10.0,
        "total": 100.0,
        "capped": False,
    })
    out = guard_output_node(state)
    assert out["guard_decision"]["refused"] is True


# ---------------------------------------------------------------------------
# Refusals: total
# ---------------------------------------------------------------------------


def test_rejects_nonpositive_total():
    state = _ok_state(surcharge_result={
        "surcharge_pct": 0.05,
        "surcharge_amount": 0.0,
        "total": 0.0,
        "capped": False,
    })
    out = guard_output_node(state)
    assert out["guard_decision"]["refused"] is True
    assert any("total" in v for v in out["guard_decision"]["violations"])


def test_rejects_negative_total():
    state = _ok_state(surcharge_result={
        "surcharge_pct": 0.05,
        "surcharge_amount": -100.0,
        "total": -50.0,
        "capped": False,
    })
    out = guard_output_node(state)
    assert out["guard_decision"]["refused"] is True


# ---------------------------------------------------------------------------
# Refusals: schema
# ---------------------------------------------------------------------------


def test_rejects_missing_field():
    state = _ok_state(surcharge_result={
        "surcharge_pct": 0.05,
        "surcharge_amount": 10.0,
        "total": 100.0,
        # 'capped' missing
    })
    out = guard_output_node(state)
    assert out["guard_decision"]["refused"] is True
    assert any(
        "missing field 'capped'" in v
        for v in out["guard_decision"]["violations"]
    )


def test_rejects_unknown_shipping_type():
    state = _ok_state(shipping_type="premium")
    out = guard_output_node(state)
    assert out["guard_decision"]["refused"] is True
    assert any(
        "shipping_type" in v and "premium" in v
        for v in out["guard_decision"]["violations"]
    )


def test_rejects_nonpositive_weight():
    state = _ok_state(weight_kg=0)
    out = guard_output_node(state)
    assert out["guard_decision"]["refused"] is True
    assert any(
        "weight_kg" in v for v in out["guard_decision"]["violations"]
    )


# ---------------------------------------------------------------------------
# Trace shape (Pitfall 5)
# ---------------------------------------------------------------------------


def test_violation_emits_trace():
    state = _ok_state(weight_kg=0)
    out = guard_output_node(state)
    trace = out["reasoning_trace"]
    assert len(trace) == 1
    entry = trace[0]
    assert entry["agent"] == "guard_output", (
        "Pitfall 5: guard entries MUST tag agent='guard_output', not 'planner'"
    )
    assert entry["status"] == "warn"
