---
name: 260509-utd Context
description: Locked decisions for guardrail hardening against adversarial classmate testing
type: context
---

# Quick Task 260509-utd: Upgrade guardrails to harden agent against adversarial team testing - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Task Boundary

Upgrade the agent's guardrails so it withstands adversarial probing from classmate teams during the MADT7204 evaluation. Project grading rewards robustness — "not getting wrecked" is itself a scored dimension. The work targets the existing LangGraph multi-agent pipeline (Planner → Fuel/Route/Pricing → Response) and must remain demoable on Gemini 2.0 Flash free tier.

</domain>

<decisions>
## Implementation Decisions

### Threat scope (all four prioritized)
Defend against the full set of attacks classmates are likely to attempt:
- **Prompt injection / system-prompt leak** — "ignore previous instructions", role-play jailbreaks, "print your system prompt", instruction override via tool outputs
- **Off-topic / domain abuse** — questions outside fuel/route/surcharge/logistics for Bangkok
- **Tool / cost bombing** — adversarial inputs that cause loops, mass Google Maps calls, or burn Gemini RPM quota
- **Output manipulation / unsafe surcharge** — crafted weight/zone/shipping_type inputs that try to force negative surcharge, bypass caps, or produce nonsense quotes

### Enforcement layer (two-layer defense)
- **Layer 1 — System prompt hardening:** strengthen each agent's prompt (`backend/agent/prompts/`) with explicit refusal rules, scope boundaries, no-leak directives, no-tool-call-on-suspicious-input rules
- **Layer 2 — Dedicated LangGraph guard node:** add a pre-router `guard_input` node that classifies user message and rejects adversarial/off-topic/abuse before any specialist agent runs; add a post-pricing `guard_output` node that validates surcharge result invariants (cap range, sign, fields present) before responding

Explicitly NOT in scope: external guard libraries (LLM Guard, NeMo Guardrails), hard Python invariants beyond what the guard nodes need.

### Failure response style
**Polite refusal + redirect.** When a guard trips, the agent returns a short branded message in the form: *"I can only help with Express fuel surcharge and Bangkok logistics questions. Try asking about a shipment, route, or current diesel price instead."* This keeps the demo professional in front of judges while making the refusal visible and explainable in the reasoning trace.

### Domain strictness (logistics + fuel)
**Logistics-only PLUS fuel-related queries.** The agent already has a `search_fuel_news` tool via Tavily, so fuel-price/market questions are in-scope even when not tied to a specific shipment. Allowed topics: fuel surcharge, route/shipment quoting for Bangkok, diesel price trends, fuel market news, shipping types (bounce/retail_standard/retail_fast), zones (central-1/2/3). Out-of-scope: general code, weather, math homework, recipes, anything unrelated to Express logistics or fuel.

### Claude's Discretion
- Exact taxonomy of refusal categories used inside the guard node (Claude picks during planning — should be small, e.g. `injection`, `off_topic`, `abuse`, `unsafe_output`)
- Whether the input-guard uses an LLM call (Gemini classification) or a rules-first/LLM-fallback hybrid — research phase will inform the recommendation
- Format of `reasoning_trace` entries when a guard trips (must be visible to user via existing trace panel)
- Per-turn tool-call counter implementation detail (likely a counter in `AgentState`)
- Wording of refusal copy — keep on-brand for Express, polite, demoable

</decisions>

<specifics>
## Specific Ideas

- The agent must remain robust on **Gemini 2.0 Flash free tier (15 RPM)** — guard logic should not double LLM calls per turn unnecessarily
- Existing `reasoning_trace` panel in the frontend should surface guard decisions transparently — judges should *see* the agent refusing, not silently ignore
- Existing surcharge cap logic (`-5%` to `+15%`, see `backend/agent/tools/calculate_surcharge.py` per CLAUDE.md) is the canonical source of truth for output validation — output guard should re-check this rather than re-derive
- Langfuse already traces every agent step — guard activations should be tagged so we can review attack attempts post-demo
- Tavily-backed `search_fuel_news` justifies fuel topics being in-domain even without a shipment context

</specifics>

<canonical_refs>
## Canonical References

- `backend/agent/prompts/` — agent prompt templates that need hardening
- `backend/agent/state.py` — `AgentState` TypedDict (likely needs `guard_decision`, `tool_call_count` fields)
- `backend/agent/nodes/` — existing node implementations; new `guard_input_node.py` and `guard_output_node.py` slot in here
- `backend/agent/tools/calculate_surcharge.py` — surcharge cap logic (output-guard truth source)
- `CLAUDE.md` § Architecture / Cross-Cutting Concerns — error handling and validation conventions
- LangGraph conditional routing docs — for inserting guard nodes into the existing graph

</canonical_refs>
