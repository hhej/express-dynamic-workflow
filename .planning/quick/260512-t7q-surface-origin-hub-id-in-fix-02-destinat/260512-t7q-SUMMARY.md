---
phase: quick-260512-t7q
plan: "01"
status: complete
subsystem: backend/agent/planner
tags:
  - observability
  - trace
  - FIX-02
  - planner
  - v1.1-audit
requirements-completed:
  - OBS-FIX-02-HUBID
  - FIX-02-OBSERVABILITY
dependency-graph:
  requires:
    - FIX-02 destination-less short-circuit (Phase 999.11 Plan 03)
    - origin_hub_id state field (Phase 9 hub selection)
  provides:
    - Structured tool_input on FIX-02 short-circuit reasoning_trace entry
    - origin_hub_id surfaced to SSE consumers / Langfuse spans / frontend trace panel
  affects:
    - backend/agent/nodes/planner.py (1 logical line — short-circuit return dict)
    - backend/tests/test_planner.py (1 new regression test added)
tech-stack:
  added: []
  patterns:
    - Structured trace shape: tool_input as dict instead of opaque sentinel string
key-files:
  modified:
    - backend/agent/nodes/planner.py
    - backend/tests/test_planner.py
  created: []
decisions:
  - "tool_input keys named `trigger` (sentinel string preserved for grep-ability) and `origin_hub_id` (load-bearing observability surface) — matches structured trace convention used elsewhere in planner.py"
  - "Used state.get('origin_hub_id') (not direct key access) — tolerates legacy states where the field is absent; returns None safely"
  - "Test placement: immediately AFTER the D-10 pin test, BEFORE the Phase 11 / FIX-02 defense-in-depth divider — keeps related-test locality"
metrics:
  duration-minutes: ~6
  completed: 2026-05-12
  test-count-before: 358
  test-count-after: 359
  test-delta: +1
  files-modified: 2
  lines-added: 112
  lines-deleted: 1
commits:
  - 527fe62 feat(quick-260512-t7q) surface origin_hub_id in FIX-02 short-circuit trace (observability)
---

# Quick Task 260512-t7q: Surface origin_hub_id in FIX-02 short-circuit trace Summary

**One-liner:** Upgrade the FIX-02 destination-less short-circuit's `reasoning_trace[0].tool_input` from a bare sentinel string to a structured dict containing `trigger` + `origin_hub_id`, closing the v1.1 milestone audit's sole cross-phase observability gap (Phase 9 × Phase 11).

## Accomplishments

- **Closed v1.1 audit cross-phase observability gap (OBS-FIX-02-HUBID):** The cold-start E2E acceptance criterion ("SSE stream emits `answer` within 30s with `origin_hub_id="hq-lat-krabang"` in trace") is now fully met. Previously, functional state was correct (LangGraph's last-write-wins preserves `origin_hub_id` on partial dict returns), but the trace entry's `tool_input` was an opaque sentinel string — SSE consumers reading the cold-start baseline-diesel response had no way to see which hub the user selected.
- **Atomic, minimal diff:** Exactly one logical line in `planner.py` changed; surrounding return-dict fields (`next_step`, `user_intent`, `step`, `agent`, `tool`, `tool_output`, `reasoning`, `timestamp`, `status`) are byte-identical. Zero collateral risk to any other planner path (`_set_guard_refusal`, cache-aware override, LLM invoke path all untouched).
- **TDD discipline:** New test was written first, confirmed RED (`AssertionError: ... got str: 'fuel_data_present_no_destination'`), then planner.py edit made it GREEN. The D-10 pin test for the FIX-02 fix itself (test_planner_does_not_loop_on_destination_less_baseline_query) remained green throughout — no regression on the underlying fix.
- **Defense-in-depth structure preserved:** The `# Phase 11 / FIX-02 defense-in-depth` divider in test_planner.py appears exactly once after the edit (grep-confirmed), maintaining the file's organizational landmarks.

## Files Modified

| File                                  | Change                                                                                                                                                   |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/agent/nodes/planner.py`      | Line 316: `"tool_input": "fuel_data_present_no_destination"` → 4-line dict literal `{"trigger": "...", "origin_hub_id": state.get("origin_hub_id")}` |
| `backend/tests/test_planner.py`       | Added `test_planner_short_circuit_trace_surfaces_origin_hub_id` (~108 lines) immediately before the Phase 11 / FIX-02 defense-in-depth divider          |

## Task Commits

| Task | Description                                                                                | Commit  |
| ---- | ------------------------------------------------------------------------------------------ | ------- |
| 1    | Upgrade FIX-02 short-circuit tool_input to structured dict + add regression test (TDD)     | 527fe62 |

## Acceptance Criteria

- [x] **Sentinel string moved inside dict:** `grep -n "fuel_data_present_no_destination" backend/agent/nodes/planner.py` shows the string as the value of a `"trigger":` key (no longer as a bare `tool_input` string value).
- [x] **New regression test added and passing:** `test_planner_short_circuit_trace_surfaces_origin_hub_id` exists in `backend/tests/test_planner.py` and passes — asserts `tool_input` is a `dict`, with `trigger == "fuel_data_present_no_destination"` and `origin_hub_id == "hq-lat-krabang"`.
- [x] **D-10 pin remains green:** `test_planner_does_not_loop_on_destination_less_baseline_query` still passes (its assertions on `next_step`, `mock_factory.call_count`, and trace-entry `agent`/`status` are independent of `tool_input` inner shape).
- [x] **Section divider integrity:** The `# Phase 11 / FIX-02 defense-in-depth` divider appears exactly once in test_planner.py (grep count = 1).
- [x] **Test count delta 358 → 359:** Full backend test suite output confirmed:

```
........................................................................ [ 80%]
.......................................................................  [100%]
359 passed in 10.49s
```

- [x] **Focused verify (D-10 + new test):**

```
collected 38 items / 36 deselected / 2 selected
tests/test_planner.py ..                                                 [100%]
======================= 2 passed, 36 deselected in 0.53s =======================
```

- [x] **Scope (no spurious file changes):** `git status --short` shows only `backend/agent/nodes/planner.py` and `backend/tests/test_planner.py` modified by this commit. Other status entries (`data/raw/eppo_diesel_prices.csv`, untracked `.planning/...` artifacts) were pre-existing and unrelated.
- [x] **Atomic commit message exact:** `feat(quick-260512-t7q): surface origin_hub_id in FIX-02 short-circuit trace (observability)` — verified via `git log --oneline -1`.
- [x] **Minimal diff confirmed:** `git diff` showed exactly 1 deletion (the old bare-string line) and 4 insertions (the dict literal) in planner.py — no other field touched.

## Deviations from Plan

**None — plan executed exactly as written.**

The plan was unusually precise (line number, exact old_string and new_string, exact test placement anchor, exact assertion targets, exact expected diff stats). No deviation rules (1-4) triggered:
- No bugs encountered (Rule 1 N/A)
- No missing critical functionality discovered (Rule 2 N/A)
- No blockers encountered (Rule 3 N/A)
- No architectural decisions needed (Rule 4 N/A)

## Forward-Looking Notes

- **v1.1 milestone audit gap closed:** `.planning/milestones/v1.1-MILESTONE-AUDIT.md` flagged this as the sole cross-phase observability gap (Phase 9 hub-selection × Phase 11 FIX-02 short-circuit). With this commit, the cold-start baseline-diesel E2E flow now emits `origin_hub_id` on the trace's first short-circuit entry, satisfying the audit's acceptance criterion verbatim. Future audits should treat this gap as **closed**.
- **No follow-on work required:** SSE consumers (frontend trace panel, Langfuse span ingestion) already render `tool_input` as JSON without assuming string/dict type — no client-side changes needed. Defense-in-depth tests for SSE event-stream structure (`test_api_chat.py:197` checking `event:` types of `meta`/`trace`/`answer`/`done`) are unaffected because they read event envelope structure, not inner `tool_input` shape.
- **Pattern reusable for future short-circuits:** Any future planner short-circuit emission should follow the same structured-dict shape (`{"trigger": "...", "origin_hub_id": ..., "<other_relevant_state>": ...}`) for trace consistency. The bare-string sentinel was a Phase 999.11 expedient that's now retired.
- **No frontend changes required:** Diff scope is backend-only.

## Self-Check: PASSED

Verified post-commit:

- `git log --oneline -1` → `527fe62 feat(quick-260512-t7q): surface origin_hub_id in FIX-02 short-circuit trace (observability)` ✓
- `backend/agent/nodes/planner.py` modified line 316-319 (structured dict literal) ✓
- `backend/tests/test_planner.py` contains `test_planner_short_circuit_trace_surfaces_origin_hub_id` ✓
- `grep -c "Phase 11 / FIX-02 defense-in-depth — tool_call_count reducer invariant" backend/tests/test_planner.py` = 1 ✓
- `cd backend && pytest tests/` → `359 passed in 10.49s` ✓
- `cd backend && pytest tests/test_planner.py -k "destination_less or short_circuit_trace" -v` → 2 passed ✓
