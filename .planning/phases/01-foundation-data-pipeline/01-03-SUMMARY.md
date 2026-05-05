---
phase: 01-foundation-data-pipeline
plan: 03
subsystem: calculation
tags: [surcharge, tdd, pydantic, business-logic, pricing]

# Dependency graph
requires:
  - phase: 01-02
    provides: "SurchargeResult Pydantic model, config constants (BASELINE_DIESEL_PRICE, SURCHARGE_CAP, SURCHARGE_FLOOR, SHIPPING_MULTIPLIERS)"
provides:
  - "calculate_surcharge() pure function for surcharge computation"
  - "13 hand-calculated test cases validating the formula"
affects: [agent-tools, pricing-agent, api-endpoints]

# Tech tracking
tech-stack:
  added: []
  patterns: ["TDD with hand-calculated test values", "Pure function with Pydantic return type", "Config-driven constants (no hardcoded values)"]

key-files:
  created:
    - backend/agent/tools/calculate_surcharge.py
  modified:
    - backend/tests/test_surcharge.py

key-decisions:
  - "Rounding: 4 decimal places for pct, 2 for amounts -- matches spec"
  - "Exact cap boundary (== 0.15) treated as NOT capped -- only exceeding triggers cap"

patterns-established:
  - "TDD: RED commit (failing tests) -> GREEN commit (implementation) -> verify all pass"
  - "Pure functions: no side effects, config imported from backend.config"
  - "Input validation with descriptive ValueError messages"

requirements-completed: [CALC-01, CALC-02, CALC-03, CALC-04]

# Metrics
duration: 2min
completed: 2026-04-08
---

# Phase 01 Plan 03: Surcharge Calculation Summary

**Pure surcharge function with TDD: fuel delta * shipping multiplier + bounce traffic adjustment, capped at 15%/-5%**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-08T13:50:58Z
- **Completed:** 2026-04-08T13:53:13Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Implemented surcharge formula as pure function matching D-10/D-11/D-12 specification
- 13 hand-calculated test cases all passing, covering baseline, above/below baseline, cap/floor, boundary, and error cases
- Traffic adjustment correctly limited to bounce shipments only (CALC-03)
- Cap/floor clamping verified at exact boundaries (CALC-04)

## Task Commits

Each task was committed atomically:

1. **TDD RED: Failing tests** - `afa0aed` (test) - 13 hand-calculated test cases
2. **TDD GREEN: Implementation** - `dc3bec3` (feat) - calculate_surcharge function

## Files Created/Modified
- `backend/agent/tools/calculate_surcharge.py` - Pure surcharge calculation function with input validation
- `backend/tests/test_surcharge.py` - 13 test cases with hand-calculated expected values per D-12

## Decisions Made
- Exact cap boundary (surcharge_pct == 0.15 exactly) treated as not capped -- only values exceeding the cap trigger clamping
- Zero base_rate treated as invalid (same as negative) since surcharge on zero rate is meaningless

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Surcharge calculation ready to be wrapped as LangGraph tool in Phase 2
- All 35 tests passing (22 model + 13 surcharge) -- full test suite green
- Function importable from `backend.agent.tools.calculate_surcharge`

## Self-Check: PASSED

- [x] backend/agent/tools/calculate_surcharge.py exists
- [x] backend/tests/test_surcharge.py exists
- [x] 01-03-SUMMARY.md exists
- [x] Commit afa0aed (RED) found
- [x] Commit dc3bec3 (GREEN) found

---
*Phase: 01-foundation-data-pipeline*
*Completed: 2026-04-08*
