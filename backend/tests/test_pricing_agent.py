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
        # Phase 999.9: default to HQ so existing tests don't trigger the
        # D-09 silent-default narration path unintentionally.
        "origin_hub_id": "hq-lat-krabang",
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


def test_guards_missing_route_data():
    """gap-4 (UAT 260503-qzx): when planner hallucinates next_step='calculate_price'
    before route_agent ran, pricing_agent must short-circuit gracefully instead of
    raising KeyError on state['route_data']['zone']."""
    state = _full_state()
    state["route_data"] = None

    # Should NOT raise.
    result = pricing_agent_node(state)

    assert result["next_step"] == "respond"
    assert len(result["errors"]) == 1
    err = result["errors"][0]
    assert err["node"] == "pricing_agent"
    assert err["exception_type"] == "KeyError"
    assert "route_data" in err["message"]
    assert err["timestamp"].endswith("Z")

    assert len(result["reasoning_trace"]) == 1
    trace = result["reasoning_trace"][0]
    assert trace["agent"] == "pricing_agent"
    assert trace["status"] == "warn"
    assert trace["tool"] is None

    # Partial-state return must NOT include a surcharge_result key
    # (response_node renders status='partial' on its absence).
    assert "surcharge_result" not in result


def test_guards_missing_fuel_data():
    """gap-4 (UAT 260503-qzx): symmetric to missing route_data — guard fires when
    fuel_data is absent (e.g. fuel_agent skipped or failed silently upstream)."""
    state = _full_state()
    state["fuel_data"] = None

    result = pricing_agent_node(state)

    assert result["next_step"] == "respond"
    assert len(result["errors"]) == 1
    err = result["errors"][0]
    assert err["node"] == "pricing_agent"
    assert err["exception_type"] == "KeyError"
    assert "fuel_data" in err["message"]

    assert result["reasoning_trace"][0]["status"] == "warn"
    assert "surcharge_result" not in result


# ---------------------------------------------------------------------------
# Quick 260509-uwb: bullet-shaped pricing reasoning tests
# ---------------------------------------------------------------------------
#
# Plan: .planning/quick/260509-uwb-upgrade-pricing-agent-to-visibly-reason-/
#       260509-uwb-PLAN.md
#
# These four tests cover Plan Task 3:
#   1. test_emits_bullet_reasoning — happy path, LLM returns valid bullets
#   2. test_bullets_drop_traffic_for_retail_standard — bullet-count adapts
#      to shipping_type (no traffic bullet for retail)
#   3. test_bullets_include_search_context_when_present — news bullet
#      renders when state["search_context"] has a non-empty summary, and
#      is omitted when search_context is missing/None
#   4. test_bullet_shaped_deterministic_fallback — D-11 fallback now emits
#      the same bullet shape (3+ bullets), not a single sentence
#
# Volatility flag is monkeypatched to a constant in each test to keep
# assertions stable against live CSV state.


def _bullet_count(reasoning: str) -> int:
    """Count lines starting with the markdown bullet prefix '- '."""
    return sum(1 for line in reasoning.splitlines() if line.startswith("- "))


def test_emits_bullet_reasoning(mocker, monkeypatch):
    """Happy path: LLM returns {summary, bullets}, trace renders newline-joined.

    Asserts the reasoning string is multi-line bullet markdown (≥3 lines
    starting with '- '), references the rate tier and the volatility word,
    and preserves at least one of the LLM's verbatim bullet substrings.
    """
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )
    monkeypatch.setattr(
        mod, "_compute_volatility_flag", lambda *a, **kw: "normal"
    )

    # Numbers below match calculate_surcharge(base_rate=120, current=31.0,
    # shipping_type='bounce', traffic_severity=2) → pct=0.0754, amount=9.05,
    # total=129.05. The LLM is a narrator, so it must reflect the formula's
    # actual output verbatim.
    llm_payload = (
        '{"summary": "Surcharge 7.54% = 129.05 THB.", "bullets": ['
        '"Base rate 120.00 THB (11-25kg tier, zone central-1, bounce).",'
        '"Diesel at 31.00 THB/L vs baseline 29.94 (+3.54% delta, volatility normal over last 7 days).",'
        '"Bangkok Metro traffic severity 2/5 adds a per-step bump.",'
        '"Final surcharge 7.54% = 9.05 THB; total 129.05 THB."'
        "]}"
    )
    monkeypatch.setattr(
        mod, "get_chat_model", lambda **_: _scripted_llm(llm_payload)
    )

    result = pricing_agent_node(_full_state())
    entry = result["reasoning_trace"][0]
    reasoning = entry["reasoning"]

    # Multi-line bullet markdown.
    assert reasoning.startswith("- "), reasoning
    assert reasoning.count("\n- ") >= 2, (
        f"expected ≥3 bullets, got reasoning:\n{reasoning}"
    )
    assert _bullet_count(reasoning) >= 3

    # Signals present.
    assert "11-25kg" in reasoning
    assert "volatility" in reasoning.lower()

    surcharge = result["surcharge_result"]
    assert f"{surcharge['total']:.2f}" in reasoning

    # LLM bullets preserved verbatim (at least one substring carries through).
    assert "Bangkok Metro traffic severity 2/5" in reasoning


def test_bullets_drop_traffic_for_retail_standard(mocker, monkeypatch):
    """retail_standard: no traffic bullet; bullet count == 3 (no search_context)."""
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )
    monkeypatch.setattr(
        mod, "_compute_volatility_flag", lambda *a, **kw: "normal"
    )

    # LLM emits a 3-bullet response (no traffic, no news) — exercises the
    # "LLM bullets win when valid 3-5 length" branch in _narrate_with_llm.
    # Numbers reflect calculate_surcharge(base_rate=120, current=31.0,
    # shipping_type='retail_standard', traffic=2) → pct=0.0177, total=122.12.
    llm_payload = (
        '{"summary": "Surcharge 1.77% = 122.12 THB.", "bullets": ['
        '"Base rate 120.00 THB for retail_standard in zone central-1.",'
        '"Diesel at 31.00 THB/L vs baseline 29.94 (+3.54% delta, volatility normal).",'
        '"Final surcharge 1.77% = 2.12 THB; total 122.12 THB."'
        "]}"
    )
    monkeypatch.setattr(
        mod, "get_chat_model", lambda **_: _scripted_llm(llm_payload)
    )

    state = _full_state()
    state["shipping_type"] = "retail_standard"

    result = pricing_agent_node(state)
    reasoning = result["reasoning_trace"][0]["reasoning"]

    # No traffic bullet anywhere.
    assert "traffic" not in reasoning.lower(), reasoning
    # Exactly 3 bullets — base + fuel/volatility + final, no traffic, no news.
    assert _bullet_count(reasoning) == 3, (
        f"expected 3 bullets, got {_bullet_count(reasoning)}: {reasoning!r}"
    )


def test_bullets_include_search_context_when_present(mocker, monkeypatch):
    """News bullet renders when search_context.summary is non-empty.

    Also asserts the same setup with search_context=None drops the bullet.
    Uses the deterministic fallback path (LLM raises) so we exercise
    _build_bullets directly without LLM stub gymnastics — the whole point
    of D-11 is that fallback carries the same signals.
    """
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )
    monkeypatch.setattr(
        mod, "_compute_volatility_flag", lambda *a, **kw: "normal"
    )

    class _BrokenLLM:
        def invoke(self, *a, **kw):
            raise RuntimeError("simulated Gemini failure")

    monkeypatch.setattr(mod, "get_chat_model", lambda **_: _BrokenLLM())

    # --- Variant 1: search_context present with non-empty summary ---
    state = _full_state()
    state["search_context"] = {
        "query": "diesel news",
        "summary": "Brent up 3% on OPEC cuts.",
        "sources": [],
        "fetched_at": "2026-05-09T03:00:00Z",
    }

    result = pricing_agent_node(state)
    reasoning = result["reasoning_trace"][0]["reasoning"]

    # Substring of the search summary appears in the reasoning.
    assert (
        "Brent up 3%" in reasoning or "OPEC cuts" in reasoning
    ), reasoning
    # 5 bullets total: base + fuel/volatility + traffic (bounce) + news + final.
    assert _bullet_count(reasoning) == 5, reasoning

    # --- Variant 2: search_context absent → no news bullet ---
    state2 = _full_state()
    state2["search_context"] = None

    result2 = pricing_agent_node(state2)
    reasoning2 = result2["reasoning_trace"][0]["reasoning"]

    assert "Brent up 3%" not in reasoning2
    assert "OPEC cuts" not in reasoning2
    # 4 bullets: base + fuel/volatility + traffic (bounce) + final, no news.
    assert _bullet_count(reasoning2) == 4, reasoning2


def test_bullet_shaped_deterministic_fallback(mocker, monkeypatch):
    """D-11 fallback now emits BULLET shape (3+ bullets), not a single sentence.

    Mirrors test_gemini_failure_deterministic_fallback but asserts the
    enriched fallback contract: 3+ bullets, contains rate tier, the
    volatility-flag word, and the surcharge total — proving fallback
    bullets carry the same signals as the LLM happy path.
    """
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )
    monkeypatch.setattr(
        mod, "_compute_volatility_flag", lambda *a, **kw: "normal"
    )

    class _BrokenLLM:
        def invoke(self, *a, **kw):
            raise RuntimeError("simulated Gemini failure")

    monkeypatch.setattr(mod, "get_chat_model", lambda **_: _BrokenLLM())

    result = pricing_agent_node(_full_state())
    entry = result["reasoning_trace"][0]
    reasoning = entry["reasoning"]

    # D-11 invariant: trace status stays 'ok' even on Gemini failure.
    assert entry["status"] == "ok"

    # Bullet-shaped (≥3 bullet lines starting with '- ').
    assert reasoning.startswith("- "), reasoning
    assert _bullet_count(reasoning) >= 3, reasoning

    # Carries the same signals the LLM path would emit.
    surcharge = result["surcharge_result"]
    assert "11-25kg" in reasoning
    # Volatility flag word — pinned to "normal" via monkeypatch above.
    assert "normal" in reasoning.lower()
    # Surcharge total numerically present.
    assert f"{surcharge['total']:.2f}" in reasoning


# ---------------------------------------------------------------------------
# Phase 999.9 D-05/D-09 — origin_hub_id resolution + silent-default narration
# ---------------------------------------------------------------------------
#
# Plan: .planning/phases/999.9-hq-branch-origin-model-real-world-hub-to-
#       destination-shipping/999.9-02-PLAN.md
#
# These four tests cover Plan 999.9-02 Task 1 D-05/D-09 contract:
#   1. test_pricing_agent_resolves_hub_id_to_origin_zone — origin_hub_id
#      drives origin_zone via origin_zone_for; lookup_rate receives the
#      4-arg form
#   2. test_pricing_agent_default_to_hq_when_none — D-09 narration bullet
#      fires when state.origin_hub_id is None at entry
#   3. test_pricing_agent_no_default_bullet_when_hub_provided — D-09
#      bullet does NOT fire when caller supplied a hub_id
#   4. test_pricing_agent_unknown_hub_raises — origin_zone_for ValueError
#      propagates per D-09 lookup-miss precedent (no swallowing)


def test_pricing_agent_resolves_hub_id_to_origin_zone(
    mocker, monkeypatch, mock_hubs_json
):
    """state.origin_hub_id='branch-ayutthaya' (central-2) + dest_zone=central-1
    → lookup_rate must receive origin_zone='central-2' as 2nd positional arg.
    """
    monkeypatch.setattr(
        mod, "_compute_volatility_flag", lambda *a, **kw: "normal"
    )

    spy = mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=106.0, currency="THB", rate_tier="5-10kg"
        ),
    )

    class _BrokenLLM:
        def invoke(self, *a, **kw):
            raise RuntimeError("simulated Gemini failure")

    monkeypatch.setattr(mod, "get_chat_model", lambda **_: _BrokenLLM())

    state = _full_state()
    state["origin_hub_id"] = "branch-ayutthaya"  # central-2 per mock_hubs_json
    state["weight_kg"] = 5.0

    result = pricing_agent_node(state)

    # lookup_rate was called with the 4-arg signature; origin_zone was
    # derived via origin_zone_for("branch-ayutthaya") = "central-2".
    spy.assert_called_once()
    call_args = spy.call_args
    # Support either positional or keyword form; assert positional.
    assert call_args.args == ("bounce", "central-2", "central-1", 5.0), (
        f"unexpected lookup_rate call: {call_args}"
    )

    # Surcharge result is computed against the returned 106.0 base_rate.
    assert result["surcharge_result"] is not None
    # No D-09 bullet because origin_hub_id was provided (not None at entry).
    reasoning = result["reasoning_trace"][0]["reasoning"]
    assert "Origin unspecified" not in reasoning


def test_pricing_agent_default_to_hq_when_none(mocker, monkeypatch):
    """D-09: state omits origin_hub_id (None at entry); the trace narration
    contains the literal "Origin unspecified — defaulted to HQ Lat Krabang."
    """
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )
    monkeypatch.setattr(
        mod, "_compute_volatility_flag", lambda *a, **kw: "normal"
    )

    class _BrokenLLM:
        def invoke(self, *a, **kw):
            raise RuntimeError("simulated Gemini failure")

    monkeypatch.setattr(mod, "get_chat_model", lambda **_: _BrokenLLM())

    state = _full_state()
    state["origin_hub_id"] = None  # explicit None (D-09 trigger)

    result = pricing_agent_node(state)

    reasoning = result["reasoning_trace"][0]["reasoning"]
    assert "Origin unspecified — defaulted to HQ Lat Krabang." in reasoning, (
        f"D-09 bullet missing from trace narration: {reasoning!r}"
    )


def test_pricing_agent_no_default_bullet_when_hub_provided(
    mocker, monkeypatch
):
    """D-09 inverse: state provides origin_hub_id → no "Origin unspecified" bullet."""
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )
    monkeypatch.setattr(
        mod, "_compute_volatility_flag", lambda *a, **kw: "normal"
    )

    class _BrokenLLM:
        def invoke(self, *a, **kw):
            raise RuntimeError("simulated Gemini failure")

    monkeypatch.setattr(mod, "get_chat_model", lambda **_: _BrokenLLM())

    state = _full_state()
    state["origin_hub_id"] = "branch-bang-na"  # explicit non-None

    result = pricing_agent_node(state)

    reasoning = result["reasoning_trace"][0]["reasoning"]
    assert "Origin unspecified" not in reasoning, (
        f"D-09 bullet should NOT fire when hub_id provided: {reasoning!r}"
    )


def test_bullet_one_includes_origin_hub_label_and_zone(
    mocker, monkeypatch, mock_hubs_json
):
    """Phase 999.9 narration-coherence: bullet 1 must mention the origin
    hub label + origin zone + destination zone, so the user can see why
    the base rate differs across hubs.
    """
    monkeypatch.setattr(
        mod, "_compute_volatility_flag", lambda *a, **kw: "normal"
    )
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=106.0, currency="THB", rate_tier="5-10kg"
        ),
    )

    class _BrokenLLM:
        def invoke(self, *a, **kw):
            raise RuntimeError("simulated Gemini failure")

    monkeypatch.setattr(mod, "get_chat_model", lambda **_: _BrokenLLM())

    state = _full_state()
    state["origin_hub_id"] = "branch-ayutthaya"  # central-2 per mock_hubs_json
    state["weight_kg"] = 5.0

    result = pricing_agent_node(state)

    reasoning = result["reasoning_trace"][0]["reasoning"]
    # Bullet 1 must contain the hub label and BOTH origin + destination zones.
    assert "Phra Nakhon Si Ayutthaya" in reasoning, (
        f"missing origin hub label in narration: {reasoning!r}"
    )
    assert "central-2" in reasoning, (
        f"missing origin zone in narration: {reasoning!r}"
    )
    assert "zone central-1" in reasoning, (
        f"missing destination zone framing: {reasoning!r}"
    )


def test_pricing_agent_unknown_hub_raises(mocker, monkeypatch):
    """D-09 lookup-miss precedent: origin_zone_for raises ValueError on an
    invalid hub_id; pricing_agent_node does NOT swallow it (matches the
    lookup_rate ValueError contract).
    """
    # We expect the ValueError to surface BEFORE lookup_rate runs, but
    # install a stub anyway so a stray call would fail loudly.
    mocker.patch.object(
        mod,
        "lookup_rate",
        return_value=RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg"
        ),
    )
    monkeypatch.setattr(
        mod, "_compute_volatility_flag", lambda *a, **kw: "normal"
    )
    monkeypatch.setattr(
        mod,
        "get_chat_model",
        lambda **_: _scripted_llm('{"summary": "n/a"}'),
    )

    state = _full_state()
    state["origin_hub_id"] = "definitely-not-a-real-hub"

    with pytest.raises(ValueError, match="unknown hub_id"):
        pricing_agent_node(state)
