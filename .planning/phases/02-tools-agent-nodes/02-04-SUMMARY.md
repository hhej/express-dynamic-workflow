---
phase: 02-tools-agent-nodes
plan: 04
subsystem: tools
tags: [sqlite, langchain, langgraph, pydantic, rate-table, surcharge]

# Dependency graph
requires:
  - phase: 02-01
    provides: Pydantic models (RateResult, SurchargeInput, SurchargeResult), conftest seeded_sqlite_path fixture
  - phase: 01-foundation
    provides: calculate_surcharge pure function, data/express.db seeded rate_table (45 rows)
provides:
  - TOOL-03 lookup_rate SQLite query with half-open weight-tier matching
  - TOOL-04 calculate_surcharge_tool LangChain @tool wrapper
affects: [pricing-agent, phase-03-graph, phase-03-agents]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Module-level _DB_PATH for test monkeypatch override of DB connection
    - Half-open [min, max) interval SQL matching with `? < weight_max_kg` (sentinel-safe)
    - LangChain `@tool(name, args_schema=...)` wrapping a pure function via delegation

key-files:
  created:
    - backend/agent/tools/lookup_rate.py
    - backend/agent/tools/calculate_surcharge_tool.py
    - backend/tests/test_lookup_rate.py
    - backend/tests/test_calculate_surcharge_tool.py
  modified: []

key-decisions:
  - "Use parameterized SQL with `? < weight_max_kg` so sentinel 999 is automatically excluded — no special-case branching"
  - "Format rate_tier as '50+kg' when weight_max >= 999, else '<min>-<max>kg' — mirrors rate-card display convention"
  - "Wrapper delegates to Phase 1 pure function unchanged (import alias `_calc`) — preserves test coverage, avoids duplicating formula logic"
  - "Tests accept both SurchargeResult model and model_dump dict return from @tool.invoke — robust to minor LangChain version shifts"

patterns-established:
  - "Module-level _DB_PATH pattern: production reads from config; tests monkeypatch to seeded_sqlite_path tmp copy"
  - "LangChain @tool-over-pure-function: pure function owns logic + tests; @tool wrapper adds LLM surface with zero logic duplication"

requirements-completed: [TOOL-03, TOOL-04]

# Metrics
duration: 4min
completed: 2026-04-18
---

# Phase 02 Plan 04: Rate Lookup & Surcharge Tool Wrapper Summary

**TOOL-03 SQLite rate lookup with half-open weight tiers plus TOOL-04 LangChain @tool wrapper over the Phase 1 surcharge function**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-18T07:52:10Z
- **Completed:** 2026-04-18T07:54:00Z
- **Tasks:** 2 (both TDD — RED then GREEN)
- **Files created:** 4
- **Files modified:** 0

## Accomplishments

- `lookup_rate(shipping_type, zone, weight_kg)` queries `rate_table` with half-open tier matching; sentinel `weight_max_kg=999` excluded by strict inequality (no NULL handling needed, per C-02)
- `calculate_surcharge_tool` exposes the Phase 1 pure surcharge function via LangChain `@tool` with `args_schema=SurchargeInput` — ready for Gemini function-calling in Phase 3
- 8 + 4 = 12 new tests, all passing; full suite 65/65 green (no regression across Phase 1 and Plans 02/03)
- Rate-tier formatting matches rate-card display (`"0-5kg"` for bounded, `"50+kg"` for top tier)

## Task Commits

Each task followed strict TDD (test → implementation):

1. **Task 1 RED: failing tests for lookup_rate** — `526dfcc` (test)
2. **Task 1 GREEN: implement lookup_rate** — `5887cdc` (feat)
3. **Task 2 RED: failing tests for calculate_surcharge_tool** — `d9d3ba7` (test)
4. **Task 2 GREEN: implement wrapper** — `1dcad27` (feat)

All commits used `--no-verify` as parallel-executor policy (orchestrator validates hooks once at end).

## Files Created/Modified

- `backend/agent/tools/lookup_rate.py` — TOOL-03 implementation; 76 lines; `lookup_rate(shipping_type, zone, weight_kg) -> RateResult`
- `backend/agent/tools/calculate_surcharge_tool.py` — TOOL-04 implementation; 44 lines; `@tool` wrapper delegating to Phase 1 `calculate_surcharge`
- `backend/tests/test_lookup_rate.py` — 8 tests; happy path, D-13 half-open boundary at 5.0 kg, 4.99 kg lower tier, unknown type/zone ValueError, sentinel 999 ValueError, zero/negative weight ValueError, `"50+kg"` format
- `backend/tests/test_calculate_surcharge_tool.py` — 4 tests; `.name`/`.args_schema` contract, parity with pure function (retail_standard + bounce cases), ValueError propagation

## Decisions Made

- **Sentinel-safe SQL:** Used `weight_min_kg <= ? AND ? < weight_max_kg` so weight=999 returns no row naturally (999 < 999 is false). Avoided `IS NULL` branch entirely because C-02 confirmed rates store 999 as sentinel.
- **Rate-tier string format:** Chose `"<wmin>+kg"` when `wmax >= 999`, else `"<wmin>-<wmax>kg"`. Human-readable for reasoning traces without exposing the sentinel.
- **Zero-logic wrapper:** `calculate_surcharge_tool` delegates to `_calc` (imported alias) rather than re-implementing validation/formula. Pure function keeps its 13 existing tests; wrapper's 4 tests cover only the LangChain surface contract.
- **Flexible return-shape assertions:** Tests accept both `SurchargeResult` model and `model_dump` dict from `.invoke` — `@tool` behaviour differs subtly across LangChain minor versions; structural equality is the real contract.

## Deviations from Plan

None — plan executed exactly as written. Every test name, SQL predicate, and wrapper field matches the plan specification verbatim.

## Issues Encountered

None. TDD cycle was clean: RED commit confirmed import errors, GREEN commit made all assertions pass on first run, full suite regressed zero tests.

## User Setup Required

None — no external services, no new env vars, no dashboards. `DATABASE_PATH` already defined in Phase 1 config and `.env.example`.

## Next Phase Readiness

- Pricing Agent (Phase 3) can now `bind_tools([lookup_rate, calculate_surcharge_tool])` on a Gemini ChatGoogleGenerativeAI instance
- Two of four Phase 2 tool requirements closed (TOOL-03, TOOL-04); TOOL-01 / TOOL-02 remain in parallel plans 02/03
- No blockers introduced for downstream graph assembly

## Self-Check

Performed after writing SUMMARY.md:

- `backend/agent/tools/lookup_rate.py` — FOUND
- `backend/agent/tools/calculate_surcharge_tool.py` — FOUND
- `backend/tests/test_lookup_rate.py` — FOUND
- `backend/tests/test_calculate_surcharge_tool.py` — FOUND
- Commit `526dfcc` (test RED lookup_rate) — FOUND
- Commit `5887cdc` (feat GREEN lookup_rate) — FOUND
- Commit `d9d3ba7` (test RED wrapper) — FOUND
- Commit `1dcad27` (feat GREEN wrapper) — FOUND
- Full test suite 65/65 passing — VERIFIED
- Smoke test `lookup_rate('bounce', 'central-1', 10) -> 130.0 10-20kg` — VERIFIED
- Smoke test `calculate_surcharge_tool.name == 'calculate_surcharge'` — VERIFIED

## Self-Check: PASSED

---
*Phase: 02-tools-agent-nodes*
*Completed: 2026-04-18*
