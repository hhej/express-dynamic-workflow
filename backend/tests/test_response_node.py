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


# ---------------------------------------------------------------------------
# Phase 5 TOOL-05 — search_context "Market context" prefix (D-11)
# ---------------------------------------------------------------------------


def test_response_prepends_market_context_when_present():
    """D-11: search_context.summary is prepended as a 'Market context:' line."""
    state = _ok_state()
    state["surcharge_result"] = None
    state["clarification_reason"] = "missing_inputs"
    state["missing_fields"] = ["weight_kg"]
    state["search_context"] = {
        "query": "diesel",
        "summary": "Prices held steady at 30 THB/L.",
        "sources": [],
        "fetched_at": "2026-05-02T10:00:00Z",
    }

    result = response_node(state)
    md = result["final_payload"]["markdown"]

    assert "Market context:" in md
    assert "Prices held steady at 30 THB/L." in md
    # The market context line is at the top (D-11).
    assert md.startswith("> **Market context:** Prices held steady at 30 THB/L.")


def test_response_no_market_context_when_search_context_none():
    """search_context=None -> markdown shape unchanged (Phase 3 D-11)."""
    state = _ok_state()
    state["surcharge_result"] = None
    state["clarification_reason"] = "missing_inputs"
    state["missing_fields"] = ["weight_kg"]
    state["search_context"] = None

    result = response_node(state)
    md = result["final_payload"]["markdown"]

    assert "Market context:" not in md


def test_response_no_market_context_when_summary_empty():
    """search_context with empty/None summary -> no prefix rendered."""
    state = _ok_state()
    state["surcharge_result"] = None
    state["clarification_reason"] = "missing_inputs"
    state["missing_fields"] = ["weight_kg"]
    state["search_context"] = {
        "query": "x",
        "summary": "",
        "sources": [],
        "fetched_at": "2026-05-02T10:00:00Z",
    }

    result = response_node(state)
    md = result["final_payload"]["markdown"]

    assert "Market context:" not in md

    # And again with summary=None.
    state["search_context"]["summary"] = None
    result = response_node(state)
    md = result["final_payload"]["markdown"]
    assert "Market context:" not in md


def test_response_market_context_with_ok_status_above_table():
    """Happy path: search_context + ok status -> Market context line first,
    then prose, then table."""
    state = _ok_state()
    state["search_context"] = {
        "query": "diesel news",
        "summary": "Crude oil futures eased this week.",
        "sources": [],
        "fetched_at": "2026-05-02T10:00:00Z",
    }

    result = response_node(state)
    md = result["final_payload"]["markdown"]

    # Market context first.
    assert md.startswith("> **Market context:** Crude oil futures eased this week.")
    # Table still present after.
    assert "| Total |" in md


def test_response_market_context_above_cap_callout():
    """When BOTH search_context and capped result are present, Market context
    sits at the very top, then the cap callout, then the rest."""
    state = _ok_state()
    state["surcharge_result"]["capped"] = True
    state["search_context"] = {
        "query": "diesel news",
        "summary": "Refinery shutdown nudges prices.",
        "sources": [],
        "fetched_at": "2026-05-02T10:00:00Z",
    }

    result = response_node(state)
    md = result["final_payload"]["markdown"]

    # Market context first, cap callout immediately after.
    assert md.startswith("> **Market context:** Refinery shutdown nudges prices.")
    assert "> ⚠ Cap/floor applied — review recommended" in md
    # Verify ordering: market context appears before cap callout.
    assert md.index("Market context:") < md.index("Cap/floor applied")


# ---------------------------------------------------------------------------
# Phase 5 ORCH-09 — HITL approve/deny path (D-07)
# ---------------------------------------------------------------------------


def test_response_node_deny_renders_partial_without_table():
    """D-07: approval_decision='deny' -> status='partial', surcharge_result=None,
    prose contains 'declined', NO breakdown table rendered."""
    state = _ok_state()
    state["approval_decision"] = "deny"
    state["surcharge_result"] = {
        "surcharge_pct": 0.10,
        "surcharge_amount": 65.0,
        "total": 715.0,
        "capped": False,
    }
    out = response_node(state)
    fp = out["final_payload"]
    assert fp["status"] == "partial"
    assert fp["surcharge_result"] is None
    assert "declined" in fp["markdown"].lower()
    # No 4-row breakdown table (Phase 3 D-11 contract):
    assert "| Base rate |" not in fp["markdown"]
    assert "| Surcharge % |" not in fp["markdown"]
    assert "| Total |" not in fp["markdown"]


def test_response_node_approve_renders_status_ok():
    """approval_decision='approve' (post-resume) -> standard status='ok' with
    breakdown table preserved."""
    state = _ok_state()
    state["approval_decision"] = "approve"
    state["surcharge_result"] = {
        "surcharge_pct": 0.10,
        "surcharge_amount": 65.0,
        "total": 715.0,
        "capped": False,
    }
    out = response_node(state)
    fp = out["final_payload"]
    assert fp["status"] == "ok"
    # Standard breakdown table appears.
    assert "| Total |" in fp["markdown"]


def test_response_node_deny_with_market_context_keeps_prefix():
    """Deny path still honours D-11 Market context prefix when present."""
    state = _ok_state()
    state["approval_decision"] = "deny"
    state["surcharge_result"] = {
        "surcharge_pct": 0.10,
        "surcharge_amount": 65.0,
        "total": 715.0,
        "capped": False,
    }
    state["search_context"] = {
        "query": "diesel news",
        "summary": "Diesel held steady.",
        "sources": [],
        "fetched_at": "2026-05-02T10:00:00Z",
    }
    out = response_node(state)
    md = out["final_payload"]["markdown"]
    assert md.startswith("> **Market context:** Diesel held steady.")
    assert "declined" in md.lower()
    assert "| Total |" not in md


# ---------------------------------------------------------------------------
# Plan 05-10 / gap-3 (2026-05-03): UAT test 6 — response_node mis-renders
# the clarify prose ("I need a bit more information to calculate your
# surcharge.") when search_agent has populated search_context but no
# surcharge_result was produced. Fix: new status='search_only' branch
# rendering deterministic news prose ("Here's the latest market context.")
# below the Market context blockquote prefix (D-11).
# ---------------------------------------------------------------------------


def test_response_renders_news_prose_for_search_only_flow():
    """gap-3: search_context populated, surcharge_result=None, no errors,
    no clarification_reason → status='search_only' with the news prose,
    NOT the misleading 'I need a bit more information' clarify prose.
    The Market context blockquote prepends above (D-11)."""
    state = _ok_state()
    state["surcharge_result"] = None
    state["clarification_reason"] = None
    state["errors"] = []
    state["search_context"] = {
        "query": "diesel news",
        "summary": "Diesel up 3% on supply concerns",
        "sources": [
            {
                "title": "T1",
                "url": "U1",
                "snippet": "S1",
            }
        ],
        "fetched_at": "2026-05-03T10:00:00Z",
    }

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    # Status is search_only (the new value), NOT clarify.
    assert payload["status"] == "search_only"
    # surcharge_result remains None.
    assert payload["surcharge_result"] is None
    # Markdown starts with the Market context blockquote.
    assert md.startswith("> **Market context:** Diesel up 3% on supply concerns")
    # Markdown contains the new news prose.
    assert "Here's the latest market context" in md
    # Markdown does NOT contain the misleading clarify prose.
    assert "I need a bit more information to calculate your surcharge" not in md


def test_response_renders_news_prose_even_when_loop_budget_exhausted():
    """gap-3 defensive: if a future regression re-introduces the loop AND
    the search_context still got populated, the search-only branch fires
    BEFORE the clarify branch — so the user still sees the news prose,
    not the misleading 'planner_loop_budget_exhausted' clarify prose."""
    state = _ok_state()
    state["surcharge_result"] = None
    state["clarification_reason"] = "planner_loop_budget_exhausted"
    state["errors"] = []
    state["search_context"] = {
        "query": "diesel news",
        "summary": "Refinery shutdown nudges prices.",
        "sources": [],
        "fetched_at": "2026-05-03T10:00:00Z",
    }

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    assert payload["status"] == "search_only"
    assert "Here's the latest market context" in md
    assert "I need a bit more information to calculate your surcharge" not in md
    # Market context blockquote is still prepended.
    assert md.startswith("> **Market context:** Refinery shutdown nudges prices.")
