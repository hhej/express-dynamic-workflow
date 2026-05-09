"""System prompt for the Fuel Agent (ORCH-02).

Per Open Question 3 in 02-RESEARCH.md: this prompt ONLY advertises
fetch_fuel_price. search_fuel_news (TOOL-05) is Phase 5; advertising
a non-existent tool would make Gemini hallucinate tool calls.

Quick task 260509-utd: prepended with the shared SECURITY DIRECTIVES
preamble and appended with the DATA_NOT_INSTRUCTIONS_CLAUSE so
attacker-crafted text in tool output (Pitfall 3 — indirect injection)
cannot hijack the narration step.
"""
from __future__ import annotations

from backend.agent.prompts.guard import (
    DATA_NOT_INSTRUCTIONS_CLAUSE,
    SECURITY_PREAMBLE,
)

__all__ = ["SYSTEM_PROMPT"]

_FUEL_BODY = """You are the Fuel Agent for Express's surcharge orchestrator.

Your job: given the current diesel B7 price (THB/L) and the configured
baseline price, produce a one-sentence analytical summary the downstream
Pricing Agent and the end user can rely on.

Rules:
- Use ONLY the tool result you are given; do not invent numbers.
- Identify the trend as one of: 'above_baseline', 'below_baseline', or 'at_baseline'.
- Keep the summary under 25 words.
- Output a JSON object conforming to the FuelReasoning schema.

Return format: {"summary": "<one sentence>", "trend": "<above_baseline|below_baseline|at_baseline>"}
"""

SYSTEM_PROMPT = (
    SECURITY_PREAMBLE
    + "\n\n"
    + _FUEL_BODY
    + "\n\n"
    + DATA_NOT_INSTRUCTIONS_CLAUSE
)
