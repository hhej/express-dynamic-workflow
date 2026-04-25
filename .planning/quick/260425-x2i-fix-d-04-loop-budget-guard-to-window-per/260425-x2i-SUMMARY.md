---
phase: quick-260425-x2i
plan: 01
subsystem: agent
tags: [planner, loop-budget, langgraph, regression-fix, 999.4]

# Dependency graph
requires:
  - phase: quick-260425-vyj
    provides: 999.1 state-merge fix (made the cross-turn D-04 short-circuit visible by enabling cached follow-ups)
provides:
  - Per-turn windowed _loop_budget_exhausted guard in planner.py
  - test_loop_budget_resets_after_response_entry unit coverage for the windowing semantics
  - test_followup_param_switch_routes_through_pricing now passes against default PLANNER_MAX_ITERATIONS=6
  - ROADMAP backlog 999.4 entry documenting the bug + fix
affects: [phase-04-frontend, phase-05-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Reverse-scan-for-marker windowing pattern over cumulative LangGraph state lists
    - "Operator.add reducer + per-turn windowed reads: trace stays cumulative for UI panel; guards window per-turn"

key-files:
  created: []
  modified:
    - backend/agent/nodes/planner.py
    - backend/tests/test_planner.py
    - backend/tests/test_graph.py
    - .planning/ROADMAP.md

key-decisions:
  - "Window the count, not the trace: reasoning_trace stays cumulative (operator.add unchanged) — only the guard's interpretation changes. Phase 2 trace UI panel + Phase 4 frontend keep working without a state-shape change."
  - "Define 'current turn' as entries since the most recent agent='response' entry: matches the natural completion marker emitted by the response node; no new state field needed."
  - "Count only agent='planner' tagged entries, not all entries in the window: matches D-04's documented intent of capping planner *iterations within one user request*; specialist nodes (fuel_agent, route_agent, pricing_agent) were never the iteration risk."

patterns-established:
  - "Pattern: cumulative-list windowing — when LangGraph reducers (operator.add) cause state lists to grow across turns, guards/reads scan backward for a turn-completion marker and operate on the suffix slice"
  - "Pattern: monkeypatch-removed-as-proof — when fixing a guard that previously needed a test workaround, remove the workaround and let the test pass against the default value as the strongest end-to-end signal"

requirements-completed: [BUG-999.4]

# Metrics
duration: 2min
completed: 2026-04-25
---

# Quick Task 260425-x2i: D-04 Loop Budget Windowed Per Turn Summary

**Per-turn windowing of D-04 loop budget guard so cross-turn cumulative reasoning_trace no longer short-circuits turn 2 of a same-thread conversation; E2E test passes against default PLANNER_MAX_ITERATIONS=6 (no monkeypatch).**

## Performance

- **Duration:** ~2 min 22 sec
- **Started:** 2026-04-25T16:52:47Z
- **Completed:** 2026-04-25T16:55:09Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- `_loop_budget_exhausted` in `backend/agent/nodes/planner.py` rewritten to count only `agent == "planner"` entries since the most recent `agent == "response"` entry (or whole trace if no response yet). Restores D-04's documented intent of capping planner *iterations within one user request*.
- `test_loop_budget_exhaustion_forces_respond` updated: dummy entries changed from `agent="x"` to `agent="planner"` so the test still proves the guard fires when 5 planner-tagged entries exist with no intervening response.
- New `test_loop_budget_resets_after_response_entry` proves a 6-entry trace ending in `agent='response'` does NOT trip the guard; the LLM IS invoked and the post-LLM 999.1 merge promotes `clarify` -> `fetch_fuel`.
- E2E test `test_followup_param_switch_routes_through_pricing` no longer needs the `PLANNER_MAX_ITERATIONS=100` monkeypatch — passes against the default budget of 6, which is the strongest end-to-end signal the D-04 fix actually closes the cross-turn short-circuit gap.
- ROADMAP.md backlog gained a `### 999.4:` entry matching the established 999.1/999.2/999.3 entry style.
- Backend test suite climbed from **108 passed** to **109 passed** with zero failures.

## Task Commits

Each task was committed atomically:

1. **Task 1: Window D-04 loop-budget guard per turn + update existing test + add new windowing test** — `3ee9fa2` (fix)
2. **Task 2: Remove PLANNER_MAX_ITERATIONS=100 monkeypatch from E2E test** — `3282cd9` (test)
3. **Task 3: Append 999.4 Resolved entry to ROADMAP.md Backlog** — final metadata commit

**Plan metadata:** to be added by final commit (this SUMMARY + ROADMAP + STATE wrap-up).

## Files Created/Modified

- `backend/agent/nodes/planner.py` — `_loop_budget_exhausted` rewritten to per-turn windowed count; module docstring D-04 bullet updated; new 999.4 fix bullet appended.
- `backend/tests/test_planner.py` — `test_loop_budget_exhaustion_forces_respond` updated (dummy `agent="planner"`); new `test_loop_budget_resets_after_response_entry` added immediately after.
- `backend/tests/test_graph.py` — `test_followup_param_switch_routes_through_pricing` lost its `monkeypatch.setattr(planner_mod, "PLANNER_MAX_ITERATIONS", 100)` line; replacement comment block explains the windowing fix.
- `.planning/ROADMAP.md` — `### 999.4:` Backlog subsection appended after 999.3 with Status / Origin / Fix matching the 999.1/999.2/999.3 entry shape.

## Decisions Made

- **Window the count, not the trace.** The Phase 2 design intentionally chose `operator.add` for the `reasoning_trace` reducer so the cumulative trace persists across turns for the UI panel (Phase 4 trace rendering). Changing the reducer to overwrite would break the cumulative trace UX. The fix targets only the guard's interpretation: cumulative trace storage stays the same; the guard now reads a per-turn slice.
- **Use `agent == "response"` as the turn-completion marker.** The response node emits exactly one trace entry per turn with `agent='response'`, so a reverse scan for the most recent such entry naturally bounds the current turn without requiring a new state field, a turn counter, or tampering with how nodes write their trace entries.
- **Count only `agent == "planner"` entries inside the window.** The original D-04 docstring describes the budget as "planner iterations" — specialist nodes (fuel_agent, route_agent, pricing_agent) were never the iteration risk. Counting only planner entries makes the guard tighter (only 5 actual planner runs, not 5 mixed entries) while still firing on the runaway-loop pathology D-04 was designed to catch.

## Deviations from Plan

None — plan executed exactly as written. Test count came in at 10 planner tests (plan said "9") because the plan miscounted the existing tests (5 original D-01/D-02/D-04/D-12 + 4 999.1/999.3 regression tests + 1 new = 10, not 9); this is a planning math error, not a code deviation. All test outcomes match plan expectations: existing D-04 test still proves the guard fires; new windowing test proves the per-turn reset behaviour; full backend suite climbed to 109 passed (108 + 1).

## Issues Encountered

None. The implementation matched the plan's interface block 1:1, all three tasks landed first try, and both the targeted E2E test and the full backend suite passed without re-runs.

## User Setup Required

None — no external service configuration required.

## Verification Results

```
backend/tests/test_planner.py ..........                                 [100%]
======================== 10 passed, 4 warnings in 0.72s ========================

backend/tests/test_graph.py::test_followup_param_switch_routes_through_pricing PASSED
======================== 1 passed, 4 warnings in 0.66s =========================

backend/tests/ ...
======================== 109 passed, 4 warnings in 3.21s ========================
```

`grep -cE "^### 999\.(1|2|3|4):" .planning/ROADMAP.md` → **4**

## Manual Verification (Out of Scope but Noted)

User will run a manual live smoke test post-merge: boot uvicorn, send turn 1 ("Calculate surcharge for 50kg retail_standard from Bangkok to Pathum Thani") + turn 2 ("What if I switched it to a Bounce shipment instead?") with the same `thread_id`, and confirm turn 2 produces a fresh Bounce surcharge with a new planner trace step rather than re-rendering turn 1's cached `surcharge_result`. The E2E test passing against the default PLANNER_MAX_ITERATIONS=6 already exercises this exact graph path with the same reproducer-shape LLM responses, so the manual smoke is expected to confirm without surprises.

## Next Phase Readiness

- Planner cross-turn correctness restored on top of the 999.1 state-merge fix; same-thread follow-ups now route through the planner LLM and the post-LLM merge/promotion + D-12 cache cascade as designed.
- Phase 4 frontend work can proceed against a trustworthy `reasoning_trace` that grows cumulatively (UI panel design) without needing to know about the per-turn guard implementation detail.
- No new blockers introduced. PLANNER_MAX_ITERATIONS default stays 6; no config or env-var changes required.

## Self-Check: PASSED

- `backend/agent/nodes/planner.py` — FOUND (modified `_loop_budget_exhausted`)
- `backend/tests/test_planner.py` — FOUND (10 tests pass, includes new windowing test)
- `backend/tests/test_graph.py` — FOUND (monkeypatch removed; E2E passes)
- `.planning/ROADMAP.md` — FOUND (999.4 entry appended; grep reports 4 entries)
- Commit `3ee9fa2` (Task 1) — FOUND
- Commit `3282cd9` (Task 2) — FOUND
- Backend suite: 109 passed, 0 failed — verified

---
*Quick task: 260425-x2i-fix-d-04-loop-budget-guard-to-window-per*
*Completed: 2026-04-25*
