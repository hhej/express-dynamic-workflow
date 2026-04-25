"""Tests for ORCH-05: Response Node.

Covers D-10 (final_payload shape with markdown/surcharge_result/capped/status),
D-11 (locked markdown structure: prose + 4-row table + italic footer), and
the cap-callout prepend rule.
"""
from __future__ import annotations

from backend.agent.nodes.response_node import response_node


def _ok_state() -> dict:
    return {
        "messages": [],
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
        "surcharge_result": {
            "surcharge_pct": 0.10,
            "surcharge_amount": 12.0,
            "total": 132.0,
            "capped": False,
        },
        "reasoning_trace": [],
        "next_step": "respond",
        "origin": "Bangkok",
        "destination": "Nonthaburi",
        "user_intent": "surcharge_query",
        "missing_fields": [],
        "clarification_reason": None,
        "errors": [],
    }


def test_renders_locked_markdown_structure():
    """D-11: prose + 4-row markdown table with exact row labels; status=ok."""
    result = response_node(_ok_state())

    payload = result["final_payload"]
    md = payload["markdown"]

    assert payload["status"] == "ok"
    assert payload["capped"] is False
    assert "| Base rate |" in md
    assert "| Surcharge % |" in md
    assert "| Surcharge amount |" in md
    assert "| Total |" in md


def test_partial_status_on_errors():
    """state.errors is non-empty -> status='partial' and markdown surfaces it."""
    state = _ok_state()
    state["errors"] = [
        {
            "node": "fuel_agent",
            "exception_type": "HTTPError",
            "message": "boom",
            "timestamp": "2026-04-25T03:00:00Z",
        }
    ]

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    assert payload["status"] == "partial"
    # Failure should be acknowledged somewhere in the prose.
    assert "fuel_agent" in md or "Could not complete" in md or "partial" in md.lower()


def test_clarify_status():
    """clarification_reason set + no surcharge_result -> status='clarify'."""
    state = _ok_state()
    state["surcharge_result"] = None
    state["clarification_reason"] = "missing_weight"
    state["missing_fields"] = ["weight_kg"]

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    assert payload["status"] == "clarify"
    # Markdown should ask user for the missing field.
    assert "weight" in md.lower() or "provide" in md.lower()


def test_cap_callout_prepended():
    """surcharge_result.capped=True -> markdown starts with cap callout."""
    state = _ok_state()
    state["surcharge_result"]["capped"] = True

    result = response_node(state)
    md = result["final_payload"]["markdown"]

    assert md.startswith("> ⚠ Cap/floor applied — review recommended")
    assert result["final_payload"]["capped"] is True
