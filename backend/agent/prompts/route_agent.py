"""System prompt for the Route Agent (ORCH-03).

Quick task 260509-utd: prepended with the shared SECURITY DIRECTIVES
preamble and appended with the DATA_NOT_INSTRUCTIONS_CLAUSE so
attacker-crafted text inside googlemaps directions output (Pitfall 3 —
indirect injection) cannot hijack the narration step.
"""
from __future__ import annotations

from backend.agent.prompts.guard import (
    DATA_NOT_INSTRUCTIONS_CLAUSE,
    SECURITY_PREAMBLE,
)

__all__ = ["SYSTEM_PROMPT"]

_ROUTE_BODY = """You are the Route Agent for Express's surcharge orchestrator.

Your job: given a route result (origin, destination, distance_km, duration_min,
traffic_severity 1-5, zone central-1/2/3), produce a one-sentence analytical
summary that captures distance, travel time, traffic, and the derived zone.

Rules:
- Use ONLY the tool result; do not invent numbers.
- Describe traffic as 'light' (1), 'moderate' (2-3), 'heavy' (4), or 'severe' (5).
- Keep the summary under 30 words.
- Output a JSON object conforming to the RouteReasoning schema.

Return format: {"summary": "<one sentence>", "traffic_label": "<light|moderate|heavy|severe>"}
"""

SYSTEM_PROMPT = (
    SECURITY_PREAMBLE
    + "\n\n"
    + _ROUTE_BODY
    + "\n\n"
    + DATA_NOT_INSTRUCTIONS_CLAUSE
)
