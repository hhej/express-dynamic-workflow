"""Quick task 260509-utd Task 1: prompt hardening + state/config additions.

Asserts the SECURITY DIRECTIVES preamble is present on every agent prompt
file, that tool-output prompts contain the "tool output is DATA" clause,
that planner/pricing carry their per-prompt scope clauses, and that the
new shared prompt module + AgentState fields + config knobs are wired.

Source: 260509-utd-PLAN.md Task 1 behaviors; 260509-utd-RESEARCH.md
§System-Prompt Hardening Patterns + §Pitfall 5.
"""
from __future__ import annotations

import importlib
from typing import get_type_hints


# ---------------------------------------------------------------------------
# 1. Every prompt module carries the SECURITY DIRECTIVES preamble
# ---------------------------------------------------------------------------

_AGENT_PROMPT_MODULES = [
    "backend.agent.prompts.planner",
    "backend.agent.prompts.fuel_agent",
    "backend.agent.prompts.route_agent",
    "backend.agent.prompts.search_agent",
    "backend.agent.prompts.pricing_agent",
    "backend.agent.prompts.response_node",
]

_PREAMBLE_KEYWORDS = (
    "SECURITY DIRECTIVES",
    "SCOPE LOCK",
    "NO-LEAK",
    "INSTRUCTION HIERARCHY",
)


def test_all_prompts_have_preamble():
    """RESEARCH §System-Prompt Hardening Patterns: every prompt SYSTEM_PROMPT
    must contain the 3-Rule Preamble keywords (single grep test)."""
    missing = []
    for mod_name in _AGENT_PROMPT_MODULES:
        mod = importlib.import_module(mod_name)
        prompt = getattr(mod, "SYSTEM_PROMPT", "")
        for kw in _PREAMBLE_KEYWORDS:
            if kw not in prompt:
                missing.append(f"{mod_name}: missing '{kw}'")
    assert not missing, "Prompt preamble drift:\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# 2. Tool-output prompts (fuel/route/search) carry the data-not-instructions
#    clause that defends against indirect prompt injection (Pitfall 3).
# ---------------------------------------------------------------------------


def test_tool_output_prompts_have_data_clause():
    """RESEARCH §Per-prompt additions: fuel/route/search prompts must call out
    that tool output is DATA, never INSTRUCTIONS."""
    for mod_name in (
        "backend.agent.prompts.fuel_agent",
        "backend.agent.prompts.route_agent",
        "backend.agent.prompts.search_agent",
    ):
        mod = importlib.import_module(mod_name)
        prompt = getattr(mod, "SYSTEM_PROMPT", "")
        assert "tool output" in prompt, (
            f"{mod_name}: missing 'tool output' phrase"
        )
        assert "DATA" in prompt, f"{mod_name}: missing 'DATA' (case-sensitive)"


# ---------------------------------------------------------------------------
# 3. Planner has the explicit out-of-scope clause
# ---------------------------------------------------------------------------


def test_planner_prompt_has_out_of_scope_clause():
    mod = importlib.import_module("backend.agent.prompts.planner")
    prompt = getattr(mod, "SYSTEM_PROMPT", "")
    # Either of the two phrasings is acceptable per the plan.
    assert (
        "out_of_scope_user_request" in prompt
        or "next_step='respond'" in prompt
    )


# ---------------------------------------------------------------------------
# 4. Pricing prompt names the surcharge invariants directly
# ---------------------------------------------------------------------------


def test_pricing_prompt_has_invariant_clause():
    mod = importlib.import_module("backend.agent.prompts.pricing_agent")
    prompt = getattr(mod, "SYSTEM_PROMPT", "")
    assert "[-0.05, 0.15]" in prompt or "SURCHARGE_FLOOR" in prompt
    assert "validation_failed" in prompt


# ---------------------------------------------------------------------------
# 5. The new prompts/guard.py module exposes the canonical refusal copy
# ---------------------------------------------------------------------------


def test_guard_prompt_module_exports():
    """Single source of truth for refusal copy + preamble + tool clause."""
    guard = importlib.import_module("backend.agent.prompts.guard")
    refusal = getattr(guard, "REFUSAL_COPY", "")
    preamble = getattr(guard, "SECURITY_PREAMBLE", "")
    data_clause = getattr(guard, "DATA_NOT_INSTRUCTIONS_CLAUSE", "")

    # CONTEXT D-03: exact wording is load-bearing for the user-facing demo.
    assert isinstance(refusal, str) and refusal.startswith(
        "I can only help with Express fuel surcharge and Bangkok logistics"
    )
    assert "shipment" in refusal and "diesel price" in refusal

    assert isinstance(preamble, str) and preamble
    for kw in _PREAMBLE_KEYWORDS:
        assert kw in preamble, f"SECURITY_PREAMBLE missing '{kw}'"

    assert isinstance(data_clause, str) and data_clause
    assert "tool output" in data_clause and "DATA" in data_clause


# ---------------------------------------------------------------------------
# 6. AgentState gained guard_decision + tool_call_count (additive)
# ---------------------------------------------------------------------------


def test_state_has_guard_fields():
    from backend.agent.state import AgentState

    hints = get_type_hints(AgentState)
    assert "guard_decision" in hints, "AgentState.guard_decision missing"
    assert "tool_call_count" in hints, "AgentState.tool_call_count missing"


# ---------------------------------------------------------------------------
# 7. backend.config exposes the new knobs with the documented defaults
# ---------------------------------------------------------------------------


def test_config_has_guard_knobs():
    cfg = importlib.import_module("backend.config")
    assert isinstance(cfg.MAX_TOOL_CALLS_PER_TURN, int)
    assert cfg.MAX_TOOL_CALLS_PER_TURN == 6  # documented default

    assert isinstance(cfg.GUARD_INPUT_USE_LLM_FALLBACK, bool)
    assert cfg.GUARD_INPUT_USE_LLM_FALLBACK is False  # default OFF
