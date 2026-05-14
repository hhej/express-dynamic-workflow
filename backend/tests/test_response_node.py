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


def test_ok_prose_includes_origin_hub_label():
    """Phase 999.9 narration-coherence: when state carries origin_hub_id,
    the route phrase reads 'from {hub_label} to zone {dest}', not just
    '{dest} route'. The user must see the origin so the differing base
    rates across hubs are intelligible.
    """
    state = _ok_state()
    state["origin_hub_id"] = "branch-ayutthaya"

    result = response_node(state)
    md = result["final_payload"]["markdown"]

    assert "Phra Nakhon Si Ayutthaya" in md, (
        f"missing origin hub label in user-facing markdown: {md!r}"
    )
    assert "from Phra Nakhon Si Ayutthaya to zone central-1" in md, (
        f"origin->dest framing not surfaced: {md!r}"
    )


def test_ok_markdown_surfaces_pricing_reasoning_bullets():
    """Phase 999.9 narration-coherence: pricing_agent's deterministic
    bullets must appear inline in the user-facing markdown answer (under
    a 'Reasoning' heading), not only in the side trace panel.
    """
    state = _ok_state()
    state["origin_hub_id"] = "hq-lat-krabang"
    state["reasoning_trace"] = [
        {
            "step": 5,
            "agent": "pricing_agent",
            "tool": "lookup_rate+calculate_surcharge",
            "tool_input": {},
            "tool_output": {},
            "reasoning": (
                "- Base rate 120.00 THB (11-25kg tier, from Lat Krabang "
                "Industrial Estate, Bangkok (central-1) to zone central-1, "
                "bounce shipment).\n"
                "- Diesel at 31.00 THB/L is 3.54% above the 29.94 baseline; "
                "volatility normal over the last 7 days.\n"
                "- Bangkok Metro traffic severity 2/5 adds a per-step bump "
                "on top of the fuel delta.\n"
                "- Final surcharge 10.00% = 12.00 THB; total 132.00 THB."
            ),
            "timestamp": "2026-04-25T03:00:00Z",
            "status": "ok",
        }
    ]

    result = response_node(state)
    md = result["final_payload"]["markdown"]

    assert "**Reasoning:**" in md, (
        f"missing inline 'Reasoning' block: {md!r}"
    )
    assert "Base rate 120.00 THB" in md, (
        f"pricing bullet content not inlined into answer: {md!r}"
    )


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


# ---------------------------------------------------------------------------
# Phase 8 D-07 / D-13: search_context always present in final_payload
# (audit Issue 6 backend half — closes drift class where FE could not tell
# `undefined` from `null`).
# ---------------------------------------------------------------------------


def test_response_forwards_search_context_in_final_payload_when_present():
    """D-07: state.search_context flows verbatim into final_payload['search_context']."""
    state = _ok_state()
    state["search_context"] = {
        "query": "q",
        "summary": "s",
        "sources": [],
        "fetched_at": "z",
    }
    out = response_node(state)
    assert out["final_payload"]["search_context"] == state["search_context"]


def test_response_search_context_is_none_in_final_payload_when_absent():
    """D-07: KEY is always present (Pitfall 5 — guards against `state.get(..., {})`
    style regressions); VALUE is None when state lacks the field."""
    state = _ok_state()
    state.pop("search_context", None)
    out = response_node(state)
    assert "search_context" in out["final_payload"]
    assert out["final_payload"]["search_context"] is None


def test_response_deny_path_forwards_search_context_in_final_payload():
    """D-07 symmetry: the deny-path final_payload also forwards search_context
    so provenance survives decline (Plan 05-05 D-11 contract)."""
    state = _ok_state()
    state["approval_decision"] = "deny"
    state["search_context"] = {
        "query": "q",
        "summary": "Diesel held steady.",
        "sources": [],
        "fetched_at": "z",
    }
    out = response_node(state)
    assert out["final_payload"]["search_context"] == state["search_context"]


# ---------------------------------------------------------------------------
# Quick task 260514-vrc — current-turn freshness gate for stale state-leak.
# Sibling fix to .planning/debug/999.12 (duplicate message_id family).
# Boundary heuristic: latest reasoning_trace entry where agent=='response'
# marks the end of the PRIOR turn; entries AFTER that index are the CURRENT
# turn. response_node renders surcharge_result / search_context ONLY when
# pricing_agent / search_agent (respectively) appear in the current-turn
# slice. State is never mutated — the gate is render-time only.
# ---------------------------------------------------------------------------


def test_response_node_gates_stale_surcharge_on_search_turn():
    """260514-vrc: state.surcharge_result populated from a PRIOR turn must
    NOT render in the current turn when only search_agent ran this turn.
    Boundary: reasoning_trace = [..., pricing_agent, response, search_agent].
    Expected: status='search_only', final_payload.surcharge_result=None,
    markdown is the news prose (no breakdown table).
    """
    state = _ok_state()
    state["surcharge_result"] = {
        "surcharge_pct": 0.10,
        "surcharge_amount": 12.0,
        "total": 132.0,
        "capped": False,
    }
    state["search_context"] = {
        "query": "diesel news",
        "summary": "Refinery shutdown nudges prices.",
        "sources": [],
        "fetched_at": "2026-05-14T10:00:00Z",
    }
    # Prior turn: pricing ran, response wrapped it up.
    # Current turn: search_agent only.
    state["reasoning_trace"] = [
        {
            "step": 1,
            "agent": "pricing_agent",
            "tool": "calculate_surcharge",
            "tool_input": {},
            "tool_output": {},
            "reasoning": "prior turn pricing",
            "timestamp": "2026-05-14T09:59:00Z",
            "status": "ok",
        },
        {
            "step": 2,
            "agent": "response",
            "tool": None,
            "tool_input": {"status": "ok"},
            "tool_output": {},
            "reasoning": "prior turn response",
            "timestamp": "2026-05-14T09:59:30Z",
            "status": "ok",
        },
        {
            "step": 3,
            "agent": "search_agent",
            "tool": "search_fuel_news",
            "tool_input": {},
            "tool_output": {},
            "reasoning": "current turn search",
            "timestamp": "2026-05-14T10:00:00Z",
            "status": "ok",
        },
    ]

    # Capture pre-call state identity to verify NO mutation.
    pre_call_surcharge = state["surcharge_result"]
    pre_call_search_ctx = state["search_context"]

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    # Gate fired: stale surcharge nulled in final_payload.
    assert payload["status"] == "search_only", (
        f"expected status='search_only' (stale surcharge gated, fresh search), got: {payload['status']!r}; md={md!r}"
    )
    assert payload["surcharge_result"] is None, (
        f"stale surcharge_result leaked into final_payload: {payload['surcharge_result']!r}"
    )

    # Markdown has the news prose, NOT the breakdown table.
    assert "Here's the latest market context" in md
    assert "| Base rate |" not in md, f"stale base rate leaked into markdown: {md!r}"
    assert "| Surcharge % |" not in md
    assert "| Surcharge amount |" not in md
    assert "| Total |" not in md
    # Market context blockquote prepends (D-11 contract preserved).
    assert md.startswith("> **Market context:** Refinery shutdown nudges prices.")

    # State NOT mutated — same dict identity, same contents.
    assert state["surcharge_result"] is pre_call_surcharge
    assert state["search_context"] is pre_call_search_ctx
    assert state["surcharge_result"]["total"] == 132.0


def test_response_node_gates_stale_surcharge_on_clarify_turn():
    """260514-vrc: state.surcharge_result from a PRIOR turn must NOT render
    when the current turn has neither pricing_agent NOR search_agent
    entries (pure clarify turn — planner asked for missing inputs).
    Expected: status='clarify', final_payload.surcharge_result=None,
    markdown is the clarify prose (no breakdown table).
    """
    state = _ok_state()
    state["surcharge_result"] = {
        "surcharge_pct": 0.10,
        "surcharge_amount": 12.0,
        "total": 132.0,
        "capped": False,
    }
    state["clarification_reason"] = "missing_weight"
    state["missing_fields"] = ["weight_kg"]
    # Prior turn: pricing ran. Current turn: nothing (planner emitted clarify).
    state["reasoning_trace"] = [
        {
            "step": 1,
            "agent": "pricing_agent",
            "tool": "calculate_surcharge",
            "tool_input": {},
            "tool_output": {},
            "reasoning": "prior turn pricing",
            "timestamp": "2026-05-14T09:59:00Z",
            "status": "ok",
        },
        {
            "step": 2,
            "agent": "response",
            "tool": None,
            "tool_input": {"status": "ok"},
            "tool_output": {},
            "reasoning": "prior turn response",
            "timestamp": "2026-05-14T09:59:30Z",
            "status": "ok",
        },
        # Current turn: only a planner entry, no pricing, no search.
        {
            "step": 3,
            "agent": "planner",
            "tool": None,
            "tool_input": {},
            "tool_output": {"next_step": "clarify"},
            "reasoning": "current turn — clarify",
            "timestamp": "2026-05-14T10:00:00Z",
            "status": "ok",
        },
    ]

    pre_call_surcharge = state["surcharge_result"]

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    assert payload["status"] == "clarify", (
        f"expected status='clarify' (stale surcharge gated, no fresh agents), got: {payload['status']!r}; md={md!r}"
    )
    assert payload["surcharge_result"] is None, (
        f"stale surcharge_result leaked: {payload['surcharge_result']!r}"
    )
    # Clarify prose, no breakdown table.
    assert "weight" in md.lower() or "provide" in md.lower()
    assert "| Base rate |" not in md
    assert "| Total |" not in md

    # State unchanged.
    assert state["surcharge_result"] is pre_call_surcharge
    assert state["surcharge_result"]["total"] == 132.0


def test_response_node_renders_fresh_pricing_when_pricing_ran_this_turn():
    """260514-vrc defensive marker: the freshness gate must NOT regress
    the single-turn happy path. When the current turn has a pricing_agent
    entry (and no prior response entry), state.surcharge_result still
    renders normally as status='ok' with the breakdown table.

    This complements test_renders_locked_markdown_structure (which uses
    an EMPTY reasoning_trace via the _ok_state fixture and exercises the
    backward-compat shim) by also covering the EXPLICIT-trace happy
    path — a single-turn flow where reasoning_trace has real entries
    including the current-turn pricing_agent entry.
    """
    state = _ok_state()
    # surcharge_result already set by _ok_state(). Trace records the
    # current-turn pricing_agent entry; NO prior response entry.
    state["reasoning_trace"] = [
        {
            "step": 1,
            "agent": "planner",
            "tool": None,
            "tool_input": {},
            "tool_output": {},
            "reasoning": "planner",
            "timestamp": "2026-05-14T10:00:00Z",
            "status": "ok",
        },
        {
            "step": 2,
            "agent": "pricing_agent",
            "tool": "calculate_surcharge",
            "tool_input": {},
            "tool_output": {},
            "reasoning": "current turn pricing",
            "timestamp": "2026-05-14T10:00:01Z",
            "status": "ok",
        },
    ]

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    assert payload["status"] == "ok", (
        f"expected status='ok' (fresh pricing this turn), got: {payload['status']!r}; md={md!r}"
    )
    assert payload["surcharge_result"] == state["surcharge_result"]
    assert "| Base rate |" in md
    assert "| Total |" in md
