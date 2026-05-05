# Phase 5 — Deferred Items

Out-of-scope discoveries logged during plan execution. Each item names
the plan that should resolve it.

## Discovered during Plan 05-02 (Wave 2)

### test_api_chat.py — 2 transient failures fixed mid-wave by Plan 05-03

- **Tests:** `test_happy_path_sse_sequence`, `test_error_sse_sequence`
- **Symptom (during 05-02 Task 1):** SSE stream emitted only 2 trace events (planner + response `status="clarify"`); fuel/route/pricing nodes never ran.
- **Root cause:** Commit `272fd8d feat(05-03): planner fan-out promotion to 'fanout_fuel_route'` landed planner-side promotion logic without the matching graph wiring; planner emitted `next_step="fanout_fuel_route"` but `graph.py` had no edge for it.
- **Resolution:** Plan 05-03 sibling agent landed `46f8618 feat(05-03): graph router schedules parallel fan-out (GREEN)` mid-wave. After that commit both chat tests passed cleanly under 05-02 changes.
- **Status:** RESOLVED. No deferred work remaining.
