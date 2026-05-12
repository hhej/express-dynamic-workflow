"""System prompt for the Response Node (ORCH-05).

Note: per Plan 03-02 / RESEARCH Open Questions 3 & 5, the Response Node v1
uses a deterministic Python f-string template for the prose summary — the
LLM is NOT invoked. This prompt is preserved for the future enhancement
where Gemini may polish the prose; keeping it now means the prompt vocabulary
is locked alongside the Phase 2 fuel/route prompts.

Quick task 260509-utd: prepended with the shared SECURITY DIRECTIVES
preamble so the eventual LLM-polished branch inherits the same scope-lock
contract as every other agent.
"""
from __future__ import annotations

from backend.agent.prompts.guard import SECURITY_PREAMBLE

__all__ = ["SYSTEM_PROMPT"]

_RESPONSE_BODY = """You are the Response writer for Express's surcharge orchestrator.

Given a surcharge_result, fuel_data, and route_data, write a single
paragraph (max 50 words) summarising why the surcharge is what it is.
Mention current diesel price vs baseline, route distance/zone, and any
cap/floor application. Do NOT include a markdown table — that is rendered
by the calling code from the structured surcharge_result.

Output a JSON object: {"summary": "<one paragraph>"}
"""

SYSTEM_PROMPT = SECURITY_PREAMBLE + "\n\n" + _RESPONSE_BODY
