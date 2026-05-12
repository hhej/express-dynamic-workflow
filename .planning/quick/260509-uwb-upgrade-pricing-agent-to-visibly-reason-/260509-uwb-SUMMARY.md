---
phase: quick-260509-uwb
plan: 01
subsystem: backend.agent.nodes.pricing_agent
tags: [agentic-feel, reasoning-trace, narration, volatility, search-context, d-11]
dependency_graph:
  requires:
    - backend/agent/tools/calculate_surcharge.py (formula — UNCHANGED contract)
    - backend/agent/tools/models.py (RateResult / SurchargeResult / SearchResult — UNCHANGED contract)
    - backend/agent/state.py (search_context field already present since Phase 5)
    - data/raw/eppo_diesel_prices.csv (volatility window source)
  provides:
    - Multi-step bullet reasoning in pricing trace entries (3-5 bullets per turn)
    - 7-day diesel volatility classifier (low/normal/high)
    - search_context summary surfaced in pricing reasoning when present
    - Bullet-shaped D-11 deterministic fallback (no longer a degraded one-liner)
  affects:
    - frontend/components/trace/TraceStep.tsx (renders the multi-line reasoning string verbatim — no FE change required)
    - Langfuse trace observations (richer reasoning text on each pricing span)
tech-stack:
  added: []
  patterns:
    - "LLM-as-narrator with deterministic seed bullets — node builds the bullet list itself, hands it to Gemini as part of the input payload, prefers LLM rephrasing only when it returns 3-5 valid items, otherwise falls back to the seed."
    - "Pure-ish CSV reader for derived signals — _compute_volatility_flag never raises, returns 'normal' on any I/O or parse error so the pricing agent stays robust."
    - "Bullet predicates encode formula coverage — traffic bullet only when shipping_type='bounce', news bullet only when state['search_context'].summary is non-empty. Mirrors the formula's actual input dependencies."
key-files:
  created: []
  modified:
    - backend/agent/nodes/pricing_agent.py
    - backend/agent/prompts/pricing_agent.py
    - backend/tests/test_pricing_agent.py
decisions:
  - "Volatility thresholds: recent_delta > 0.5 * mean_abs_delta (with mean > 0) → 'high'; < 0.2 * mean_abs_delta → 'low'; else 'normal'. Defensible defaults from CONTEXT D-Discretion; calibrated against the live EPPO CSV (current 39.95 THB/L vs 7-day window starting at 40.20 → 'high' when window movement is small, 'normal' otherwise)."
  - "LLM-bullets-win predicate is strict (must be 3-5 items, all non-empty) — borderline emissions (e.g., a 2-bullet response or empty list) fall through to the deterministic seed, keeping the trace consistently rich."
  - "Search context bullet truncates to 120 chars with '...' suffix — keeps the reasoning panel tight while preserving lede signal from Tavily's one-line summary."
  - "Both LLM-success and LLM-failure paths return newline-joined `- bullet` markdown — single source of truth for what the trace renders, no degraded fallback shape."
  - "summary field kept in PricingReasoning schema (D-04 backward compat) — pre-260509 LLM emissions of just `{\"summary\": \"...\"}` parse cleanly via `bullets: list[str] = Field(default_factory=list)`, then fall through to seed bullets in the join step."
metrics:
  duration: 6min
  completed: "2026-05-09T15:30:00Z"
  tasks: 3
  files: 3
  test_count_delta: "+4 (5 → 9 in test_pricing_agent.py; full suite 248 → 260, includes the 4 new pricing + drift from intervening commits)"
---

# Quick 260509-uwb: Upgrade Pricing Agent reasoning Summary

**One-liner:** Pricing Agent now emits 3-5 bulleted reasoning steps (base rate, fuel + 7-day volatility, traffic-when-bounce, market-context-when-search, final surcharge + cap/floor) so the trace panel visibly shows every signal the deterministic formula weighed — agentic feel without changing a byte of the formula.

## What Changed

### 1. `backend/agent/nodes/pricing_agent.py`

- `PricingReasoning` schema gained `bullets: list[str] = Field(default_factory=list)` alongside the existing `summary: str`. Default-empty list preserves backward compat for any LLM emission that returns just `{"summary": "..."}`.
- New `_compute_volatility_flag(history_csv_path, current_price) -> Literal["low","normal","high"]`. Pure CSV reader, never raises.
- New `_build_bullets(...)` — deterministic bullet builder used as both fallback narration and the LLM's seed.
- New `_join_bullets(...)` helper — single source of truth for `- bullet\n- bullet` markdown shape.
- `_deterministic_narration` rewritten to delegate to `_build_bullets` + `_join_bullets`.
- `_narrate_with_llm` rewritten to: (a) build seed bullets, (b) hand them to Gemini in an augmented JSON payload (rate / surcharge / fuel_data / route_data / shipping_type / volatility_flag / search_context_summary / seed_bullets), (c) prefer the LLM's bullets when they're 3-5 items, (d) fall back to the seed otherwise.
- `pricing_agent_node` wires `volatility_flag` and `search_context` into the narration call site. Trace `status='ok'`, the gap-4 missing-input guard, and the OBS-03 auto-eval block are byte-for-byte unchanged.

### 2. `backend/agent/prompts/pricing_agent.py`

- `SYSTEM_PROMPT` rewritten with a multi-step rule set teaching Gemini to emit `{summary, bullets}` from the augmented payload.
- Bullet rules enforce: traffic only for bounce, news only when `search_context_summary` non-null, last bullet must mention cap/floor when `surcharge.capped`.
- Anti-hallucination preserved (use only the numbers in the payload).
- Includes a one-shot JSON example for a bounce shipment with high volatility and no news.

### 3. `backend/tests/test_pricing_agent.py`

- 5 pre-existing tests untouched (verified via diff).
- 4 new tests added + `_bullet_count` helper:
  1. `test_emits_bullet_reasoning` — happy path; LLM bullets preserved verbatim, ≥3 bullet lines, rate tier + volatility word + total all present.
  2. `test_bullets_drop_traffic_for_retail_standard` — shipping_type swap drops the traffic bullet; exactly 3 bullets remain.
  3. `test_bullets_include_search_context_when_present` — dual variant: 5 bullets when summary present, 4 when `search_context=None`.
  4. `test_bullet_shaped_deterministic_fallback` — D-11 fallback yields ≥3 bullets (not a single sentence), `status='ok'` preserved.

## Bullet Shapes (live examples)

**3 bullets — `retail_standard`, no search context:**
```
- Base rate 120.00 THB (11-25kg tier, zone central-1, retail_standard).
- Diesel at 31.00 THB/L vs baseline 29.94 (+3.54% delta, volatility normal over last 7 days).
- Final surcharge 1.77% = 2.12 THB; total 122.12 THB.
```

**4 bullets — `bounce`, no search context:**
```
- Base rate 120.00 THB (11-25kg tier, zone central-1, bounce).
- Diesel at 31.00 THB/L vs baseline 29.94 (+3.54% delta, volatility normal over last 7 days).
- Bangkok Metro traffic severity 2/5 adds a per-step bump on top of the fuel delta.
- Final surcharge 7.54% = 9.05 THB; total 129.05 THB.
```

**5 bullets — `bounce`, with search context summary:**
```
- Base rate 120.00 THB (11-25kg tier, zone central-1, bounce).
- Diesel at 31.00 THB/L vs baseline 29.94 (+3.54% delta, volatility low over last 7 days).
- Bangkok Metro traffic severity 2/5 adds a per-step bump on top of the fuel delta.
- Market context: Brent up 3% on OPEC cuts.
- Final surcharge 7.54% = 9.05 THB; total 129.05 THB.
```

## Volatility Threshold Rationale

Algorithm — read last 7 distinct calendar days from `data/raw/eppo_diesel_prices.csv`, drop today's row when its price equals `current_price` (avoids double-count), compute `mean_abs_delta = mean(|p[i] - p[i-1]|)` and `recent_delta = abs(current_price - first_window_price)`:

| Predicate | Flag |
| --- | --- |
| `recent_delta > 0.5 * mean_abs_delta` AND `mean_abs_delta > 0` | `"high"` |
| `recent_delta < 0.2 * mean_abs_delta` | `"low"` |
| otherwise | `"normal"` |
| <2 rows OR `mean_abs_delta == 0` | `"normal"` (safe default) |

Why these constants: the EPPO CSV swings between roughly 39.95–40.80 THB/L in the recent window (mean_abs_delta ≈ 0.18). A 0.5x threshold catches movements ≥ ~0.09 THB/L (a meaningful daily change at this price level), and a 0.2x threshold flags weeks where movement was barely above floating-point noise. Live smoke for `current_price=39.95` against the bundled CSV returns `"high"` — recent_delta (0.85) is well above 0.5 × mean_abs_delta (0.09 ≈ thus 0.18 × 0.5), which matches the human read of the data (price dropped sharply from 40.80 to 39.95 in the last 24h).

## Verification

| Gate | Command | Result |
| --- | --- | --- |
| Task 1 verify | `pytest backend/tests/test_pricing_agent.py -x -q` | 5 → 5 passed (existing) |
| Task 2 verify | `python -c "from backend.agent.prompts.pricing_agent import SYSTEM_PROMPT; assert all of bullets/summary/volatility_flag/search_context"` | passed |
| Task 3 verify (pricing) | `pytest backend/tests/test_pricing_agent.py -v -q` | 9 passed |
| Task 3 verify (full suite) | `pytest backend/tests -x -q` | 260 passed |
| Phase verify 1 (locked files unchanged) | `git diff --stat` over calculate_surcharge.py / models.py / state.py / calculate_surcharge_tool.py / graph.py | empty (zero changes) |
| Phase verify 4 (OBS-03 auto-eval) | `pytest -k "auto_eval or formula_accuracy or post_formula" -q` | 6 passed |
| Phase verify 5 (no new ext-API imports) | AST scan of pricing_agent.py for googlemaps/tavily/httpx/requests | clean (only `csv` + `pathlib` added as new stdlib imports) |

**Formula tests stay green.** All `calculate_surcharge` direct tests, the `formula_accuracy` auto-eval test, and the `post_formula_accuracy_score` observability test pass without modification — the formula contract is byte-for-byte unchanged (D-01 honoured).

**Test count delta:** test_pricing_agent.py went from 5 → 9 (4 new tests). Full backend suite: 248 baseline (per STATE 260509-eum) → 260 now; the +12 includes the 4 new pricing tests + 8 tests added since the 260509-eum baseline by intervening quick tasks (260509-utd guardrail work, etc., outside the scope of this plan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] LLM-bullet payloads in two test fixtures referenced wrong totals**

- **Found during:** Task 3 first test run (`test_emits_bullet_reasoning` failed with `assert '129.05' in '...124.80...'`).
- **Issue:** The plan's example LLM payload (`'{"bullets": ["Final surcharge 4.00% = 4.80 THB; total 124.80 THB."]}'`) used illustrative numbers, but the `calculate_surcharge` formula given the test state (`base_rate=120, current=31.0, traffic=2, bounce`) actually produces `pct=0.0754, amount=9.05, total=129.05`. The LLM-as-narrator contract requires the payload to mirror the formula's actual output, not the plan's illustrative shorthand.
- **Fix:** Updated both `test_emits_bullet_reasoning` (bounce: 7.54% / 9.05 / 129.05) and `test_bullets_drop_traffic_for_retail_standard` (retail: 1.77% / 2.12 / 122.12) to use the formula's actual computed values. Added an inline comment in each test explaining the source of the numbers so future readers see the LLM-as-narrator invariant.
- **Files modified:** `backend/tests/test_pricing_agent.py`
- **Commit:** `0a6b878` (folded into the Task 3 commit)

No other deviations. Plan executed exactly as written for Tasks 1 and 2.

## Authentication Gates

None. Plan was fully autonomous.

## Self-Check: PASSED

- ✅ `backend/agent/nodes/pricing_agent.py` modified — confirmed via `git log -p`.
- ✅ `backend/agent/prompts/pricing_agent.py` modified — confirmed via `git log -p`.
- ✅ `backend/tests/test_pricing_agent.py` modified — confirmed via `git log -p`.
- ✅ Commit `bbaf95e` (Task 1) exists in `git log --oneline -5`.
- ✅ Commit `119ac56` (Task 2) exists in `git log --oneline -5`.
- ✅ Commit `0a6b878` (Task 3) exists in `git log --oneline -5`.
- ✅ All 9 pricing tests pass (5 pre-existing + 4 new).
- ✅ Full backend suite 260/260 green.
- ✅ Locked files (`calculate_surcharge.py`, `models.py`, `state.py`, `calculate_surcharge_tool.py`, `graph.py`) unchanged in this plan's commits.
- ✅ No new external-API imports added.
