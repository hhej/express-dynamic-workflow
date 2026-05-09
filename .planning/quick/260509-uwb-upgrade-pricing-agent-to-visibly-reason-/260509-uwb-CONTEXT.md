---
name: Quick 260509-uwb Context
description: Locked decisions for Pricing Agent reasoning upgrade
type: quick-task-context
---

# Quick Task 260509-uwb: Upgrade Pricing Agent reasoning - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Task Boundary

Make the Pricing Agent feel agentic by visibly reasoning over fuel volatility window, traffic severity, and search-context signals when computing surcharge — and reflect that reasoning in the trace shown to the user. The current `_narrate_with_llm` in [backend/agent/nodes/pricing_agent.py](backend/agent/nodes/pricing_agent.py) emits a single 30-word sentence; the underlying formula is deterministic and uses fuel-delta + traffic only.

**In scope:** Pricing Agent node, prompt, and any helper that feeds it richer state-derived signals.
**Out of scope:** Route/HQ-branch model (backlogged 999.9), regional scale-up (backlogged 999.8), formula changes, frontend trace renderer changes (already supports multi-step trace entries).

</domain>

<decisions>
## Implementation Decisions

### Formula scope — Narration only
- **Locked:** The deterministic surcharge formula in [backend/agent/tools/calculate_surcharge.py](backend/agent/tools/calculate_surcharge.py) does NOT change.
- All existing formula_accuracy auto-eval and surcharge tests must continue to pass unchanged.
- The Pricing Agent's job here is to *narrate over* the same numbers more transparently, weighing inputs the formula already considers (fuel delta, traffic) plus new context signals (volatility window, news context) for explanation only.

### Reasoning depth — Multi-step bullets
- **Locked:** Pricing Agent narration becomes 3–5 short bullets walking the signals:
  1. Base rate from rate table (zone × ship-type × weight tier)
  2. Fuel delta (current vs baseline) + volatility flag (7d window)
  3. Traffic severity factor (when bounce / non-trivial)
  4. News/search-context relevance flag (if Tavily context present in state)
  5. Final surcharge percentage and total, with cap/floor note when triggered
- Replaces the existing 1-sentence summary in `PricingReasoning.summary`. Schema gains a `bullets: list[str]` field.
- Trace entry's `reasoning` field becomes a newline-joined or list-rendered version of the bullets so the existing trace UI handles it without changes.

### Signal sources — Existing state only
- **Locked:** No new external API calls from Pricing Agent. Stay under the 15 RPM Gemini free-tier ceiling.
- **Volatility signal:** Compute from `data/raw/eppo_diesel_prices.csv` — last 7 days vs current price. Categorize as `low` / `normal` / `high` using a simple std-dev-from-mean threshold. Read once per node invocation; cheap (CSV is small).
- **News context:** Read from `state.search_context` if present (already populated by the Search Agent in the existing graph). Pricing Agent does NOT call Tavily directly. If no search_context exists, the bullet for news is omitted gracefully (not "no data" — just not rendered).

### Claude's Discretion
- Exact std-dev threshold for `low/normal/high` volatility (will pick something defensible — e.g., `>0.5 * mean_abs_delta` = high, `<0.2 * mean_abs_delta` = low).
- Bullet formatting (markdown `-` vs numbered) — will match what the existing frontend trace renderer displays cleanly.
- Whether to still keep the `summary` field (1-sentence) alongside `bullets` for backward compat — defaulting to YES so existing UI surfaces that don't render bullets still work.

</decisions>

<specifics>
## Specific Ideas

- The Pricing Agent's deterministic-fallback narration `_deterministic_narration` in [backend/agent/nodes/pricing_agent.py:47-57](backend/agent/nodes/pricing_agent.py#L47-L57) should also produce the bullet list (so D-11 fallback still feels rich, not a degraded one-liner).
- `PricingReasoning` Pydantic schema in [backend/agent/nodes/pricing_agent.py:41-44](backend/agent/nodes/pricing_agent.py#L41-L44) gains `bullets: list[str]` — keep `summary: str` for compatibility.
- `SYSTEM_PROMPT` in [backend/agent/prompts/pricing_agent.py](backend/agent/prompts/pricing_agent.py) needs to instruct the LLM to emit JSON with both `summary` and `bullets`, given the augmented context (volatility flag, search_context excerpt).
- Helper function `_compute_volatility_flag(history_csv_path: str, current_price: float) -> Literal["low","normal","high"]` lives near the node. Pure, testable, no I/O beyond CSV read.

</specifics>

<canonical_refs>
## Canonical References

- [docs/architecture.md](docs/architecture.md) — surcharge formula contract (UNCHANGED by this task)
- [backend/agent/nodes/pricing_agent.py](backend/agent/nodes/pricing_agent.py) — primary edit target
- [backend/agent/prompts/pricing_agent.py](backend/agent/prompts/pricing_agent.py) — prompt update
- [data/raw/eppo_diesel_prices.csv](data/raw/eppo_diesel_prices.csv) — volatility data source
- D-11 contract (deterministic fallback) and D-15 (formula_accuracy auto-eval) — must remain green

</canonical_refs>
