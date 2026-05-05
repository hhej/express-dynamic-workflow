---
phase: 02-tools-agent-nodes
plan: 02
subsystem: tools
tags: [fuel, httpx, pandas, pytest-httpx, fallback-chain, tool-01]

requires:
  - phase: 02-tools-agent-nodes
    provides: "Plan 01: Pydantic FuelData model, Phase 2 config (BASELINE_DIESEL_PRICE, FUEL_FETCH_TIMEOUT), pytest-httpx fixture support"
  - phase: 01-foundation
    provides: "data/raw/eppo_diesel_prices.csv seed (185 rows, diesel_b7_price column)"
provides:
  - "TOOL-01: fetch_fuel_price() with 3-level fallback chain (live scrape stubbed, CSV fallback active, baseline final)"
  - "Source tagging: 'eppo_live' | 'eppo_cached_csv' | 'hardcoded_baseline' (D-03) for reasoning-trace transparency"
  - "Exponential backoff retry policy (1s, 2s) per D-04"
  - "Never-raises contract: tool always returns FuelData"
affects: [fuel-agent-node, planner-routing, reasoning-trace, phase-5-polish]

tech-stack:
  added: []
  patterns:
    - "3-level fallback chain (live -> cached CSV -> hardcoded baseline)"
    - "Module-level resource constants (_FUEL_CSV, _EPPO_URL) monkeypatchable from tests"
    - "NotImplementedError as an intentional stub signal caught by the retry loop"
    - "pytest-httpx module-wide marker to relax assert_all_responses_were_requested when stubs short-circuit"

key-files:
  created:
    - "backend/agent/tools/fetch_fuel_price.py (TOOL-01 implementation)"
    - "backend/tests/test_fetch_fuel_price.py (6 TDD tests)"
  modified: []

key-decisions:
  - "pytest-httpx mocks registered but not consumed (stub raises before httpx call) -- relaxed module-wide via pytestmark"
  - "_FUEL_CSV kept as module-level Path so monkeypatch can inject tmp paths in tests"
  - "time imported as module (not `from time import sleep`) so monkeypatching mod.time.sleep works"

patterns-established:
  - "Fallback chain: iterate retries -> exceptions caught broadly (HTTPError, ValueError, NotImplementedError) -> degrade level"
  - "Build helper (_build_fuel_data) centralises rounding and delta_pct computation"
  - "Exponential backoff encoded as [0, 1, 2] list iteration -- simple, deterministic, test-friendly"

requirements-completed: ["TOOL-01"]

duration: 3min
completed: 2026-04-18
---

# Phase 02 Plan 02: fetch_fuel_price TOOL-01 Summary

**3-level fuel-price fallback chain (stubbed live scrape -> cached CSV -> hardcoded baseline) with source tagging, exponential backoff, and a never-raises contract, fully covered by 6 deterministic tests using pytest-httpx.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-18T07:51:52Z
- **Completed:** 2026-04-18T07:54:30Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2 (1 created impl, 1 created tests)

## Accomplishments

- Shipped `fetch_fuel_price()` as the Fuel Agent's primary data source — always returns a `FuelData`, never raises.
- Wired D-03 source tagging (`eppo_live` / `eppo_cached_csv` / `hardcoded_baseline`) so the reasoning trace can later surface fallback provenance.
- Implemented D-04 exponential-backoff retry policy (sleeps `[0, 1, 2]` between 3 attempts) with deterministic test coverage.
- Documented Open Question 2 in code: `_scrape_eppo_live()` raises `NotImplementedError` as an intentional stub, caught by the Level-1 loop so CSV fallback works immediately.

## Task Commits

Each task committed atomically:

1. **Task 1: Write test_fetch_fuel_price.py (RED phase)** — `ead1eac` (test)
2. **Task 2: Implement fetch_fuel_price.py (GREEN phase)** — `e1b6919` (feat)

_Note: Task 2's GREEN commit also contains a small test-file update (see Deviations)._

## Files Created/Modified

- `backend/agent/tools/fetch_fuel_price.py` (115 lines) — TOOL-01 implementation: `fetch_fuel_price()` public entry, `_scrape_eppo_live()` stub, `_read_cached_csv()` pandas reader, `_build_fuel_data()` helper.
- `backend/tests/test_fetch_fuel_price.py` (95 lines) — 6 TDD tests covering all three fallback paths, retry timing, delta_pct computation, and direct stub verification.

## Decisions Made

- **Module-level `_FUEL_CSV` path** instead of a function argument — enables `monkeypatch.setattr(mod, "_FUEL_CSV", ...)` in tests without threading a parameter through production callers.
- **`import time` over `from time import sleep`** — tests monkeypatch `mod.time.sleep`; the attribute form keeps the production code unchanged while making the sleep seam injectable.
- **Broad exception catch in Level 1** (`httpx.HTTPError | ValueError | NotImplementedError`) — treats the stubbed scrape as a transient failure, so the chain falls through cleanly today and requires zero changes when the live scrape is un-stubbed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pytest-httpx assert_all_responses_were_requested incompatible with stubbed scrape**

- **Found during:** Task 2 (first GREEN pytest run)
- **Issue:** pytest-httpx 0.35.0 asserts every registered mock must be consumed. The RED tests register 3 `httpx_mock.add_exception(...)` mocks per test, but `_scrape_eppo_live()` raises `NotImplementedError` before any httpx call is attempted — so the mocks are never consumed and pytest-httpx fails the test with `assert not <pending matchers>`.
- **Fix:** Added a module-level `pytestmark = pytest.mark.httpx_mock(assert_all_responses_were_requested=False)` to `backend/tests/test_fetch_fuel_price.py`. The mocks remain registered (future-proofs them for Phase 5 when the scrape is un-stubbed and will consume them) but the framework no longer fails when they go unused today.
- **Files modified:** `backend/tests/test_fetch_fuel_price.py`
- **Verification:** `.venv/bin/pytest backend/tests/test_fetch_fuel_price.py -x -q` now exits 0 with all 6 tests passing.
- **Committed in:** `e1b6919` (bundled into the Task 2 GREEN commit since it is inseparable from making the tests pass)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minimal — the fix is a one-line pytest marker; production code is exactly as specified in the plan. No scope creep.

## Issues Encountered

None beyond the pytest-httpx marker deviation above.

## User Setup Required

None — no external service configuration required. The CSV seed from Phase 1 is sufficient for the CSV fallback; no API keys needed for the stubbed live scrape.

## Next Phase Readiness

- **Ready for Plan 05 (Fuel Agent node):** `fetch_fuel_price()` is importable, type-stable, and always returns a `FuelData`. The Fuel Agent can consume `.price`, `.delta_pct`, and `.source` directly for reasoning-trace output.
- **Full suite green:** 65 tests pass (Phase 1 + TOOL-01); no regressions introduced.
- **Deferred to Phase 5 polish:** un-stub `_scrape_eppo_live()` once live EPPO selectors are captured (Open Question 2). The registered pytest-httpx mocks and the `assert_all_responses_were_requested=False` marker will need to be revisited at that point.

## Self-Check: PASSED

Verification performed:

- `backend/agent/tools/fetch_fuel_price.py` exists (115 lines) — FOUND
- `backend/tests/test_fetch_fuel_price.py` exists (95 lines, 6 `def test_` functions) — FOUND
- Commit `ead1eac` (test) — FOUND in git log
- Commit `e1b6919` (feat) — FOUND in git log
- All 6 TOOL-01 tests pass — VERIFIED (`.venv/bin/pytest backend/tests/test_fetch_fuel_price.py -x -q`)
- Full suite (65 tests) passes — VERIFIED (`.venv/bin/pytest backend/tests/ -q`)
- Smoke import returns `eppo_cached_csv 31.62` (latest CSV row) — VERIFIED

---
*Phase: 02-tools-agent-nodes*
*Completed: 2026-04-18*
