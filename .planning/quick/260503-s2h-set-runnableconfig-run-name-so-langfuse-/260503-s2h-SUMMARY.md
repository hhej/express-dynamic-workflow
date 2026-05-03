---
phase: quick-260503-s2h
plan: 01
subsystem: observability
tags: [langfuse, langchain, runnableconfig, run_name, observability, fastapi, sse]

# Dependency graph
requires:
  - phase: quick-260503-rs8
    provides: "metadata.langfuse_trace_name='express-surcharge-agent' populates Langfuse 'Trace Name' column; this quick fix completes the pair by populating the 'Name' column."
provides:
  - "Top-level RunnableConfig.run_name='express-surcharge-agent' on every /api/chat turn so the LangChain root span name (Langfuse Observations 'Name' column) matches the trace name."
affects: [quick-260503-rs8, phase-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RunnableConfig top-level run_name as the canonical agent identity for LangChain root spans (sibling to metadata.langfuse_trace_name which targets the Langfuse Trace Name column)."

key-files:
  created: []
  modified:
    - backend/api/routes/chat.py
    - backend/tests/test_observability_wiring.py

key-decisions:
  - "run_name placed at TOP LEVEL of RunnableConfig dict (between callbacks and metadata), NOT inside metadata — matches LangChain RunnableConfig schema; langfuse-langchain CallbackHandler reads the top-level key for the root observation's name."
  - "Constant string 'express-surcharge-agent' (not derived from message/intent/turn_idx) — single stable name to filter under in Langfuse Observations, matches the constant used by metadata.langfuse_trace_name."
  - "Extended existing test_chat_attaches_callback_when_enabled with one in-place assertion rather than adding a new test — keeps test count flat at 186 per plan success criteria."

patterns-established:
  - "Two-Langfuse-column rule: metadata.langfuse_trace_name → 'Trace Name' column, top-level run_name → 'Name' column. Both should match for a single agent identity in dashboard filtering."

requirements-completed: [OBS-FIX-RUN-NAME]

# Metrics
duration: ~3min
completed: 2026-05-03
---

# Quick-task 260503-s2h: Set RunnableConfig.run_name for Langfuse Name Column

**Top-level `run_name="express-surcharge-agent"` added to `_make_config` so the Langfuse Observations "Name" column matches the "Trace Name" column from quick-task 260503-rs8.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-03T13:04:12Z (resume from STATE.md last_updated)
- **Completed:** 2026-05-03 (single TDD red→green cycle, no refactor)
- **Tasks:** 1 (TDD: 1 RED, 1 GREEN, 0 REFACTOR)
- **Files modified:** 2 (backend/api/routes/chat.py, backend/tests/test_observability_wiring.py)
- **Lines added:** 7 (1 dict entry + 5 docstring bullet lines + 1 test assertion)

## Accomplishments

- `_make_config` in `backend/api/routes/chat.py` now returns a RunnableConfig with `run_name="express-surcharge-agent"` as a TOP-LEVEL key (sibling to `configurable`/`callbacks`/`metadata`).
- Docstring `Returns:` section documents the new top-level key with a brief explanation of how it pairs with `metadata.langfuse_trace_name` (different Langfuse columns).
- `test_chat_attaches_callback_when_enabled` extended with one in-place assertion `cfg["run_name"] == "express-surcharge-agent"`. No new test function, no test count delta — still 186/186 passing.
- `test_chat_skips_callback_when_disabled` left untouched per plan (kept tight).

## Task Commits

This is a single-commit quick task (TDD red and green steps land together for surgical doc-text/test/dict edits where the green diff is a single line):

1. **Task 1: Add top-level run_name to RunnableConfig + docstring + test assertion** — `0606e43` (feat)

_TDD note: the plan called for a TDD task. Executor ran the failing test first (RED — `KeyError: 'run_name'` confirmed), then made the production-code edits (GREEN — 5/5 in target file, 186/186 full suite), then committed both in one atomic commit since the production change is a single key-value pair that cannot be meaningfully split from the assertion that proves it._

## Files Created/Modified

- `backend/api/routes/chat.py` — Added `"run_name": "express-surcharge-agent",` to the `_make_config` return dict at line 95 (sibling to `callbacks` and `metadata`); added a 5-line bullet to the function's `Returns:` docstring describing the new top-level key.
- `backend/tests/test_observability_wiring.py` — Appended one assertion line (line 39) to `test_chat_attaches_callback_when_enabled`, immediately after the existing `langfuse_trace_name` assertion.

## Decisions Made

- **Top-level placement (not inside metadata)** — `RunnableConfig.run_name` per LangChain schema is a top-level field. The langfuse-langchain `CallbackHandler` reads it from there to set the root observation's `name`, which is what populates the "Name" column on the Langfuse Observations dashboard. Putting it inside `metadata` would be silently ignored.
- **Constant value, not dynamic** — Same string as the `metadata.langfuse_trace_name` set in 260503-rs8. Two columns, same name, single filter in the dashboard. Per-question dynamic naming explicitly out-of-scope (would scatter traces across many names and break dashboard filtering).
- **In-place test extension, not new test function** — Plan success criteria explicitly required no test count delta. One additional assertion in the same test that already validates the rest of the metadata is the smallest correct change.

## Deviations from Plan

None — plan executed exactly as written. The three surgical edits landed in the order described:

1. Test assertion added (RED confirmed: `KeyError: 'run_name'`).
2. Production dict entry added (`"run_name": "express-surcharge-agent",`).
3. Docstring bullet added in the same edit block.

Single commit covers all three edits atomically, matching the plan's explicit `<success_criteria>` line "Single git commit covers all three edits atomically."

## Issues Encountered

None.

## Verification

```bash
cd /Users/pollot/Desktop/express-dynamic-workflow && source .venv/bin/activate && pytest backend/tests/ -x --tb=short
```

Result: **186 passed in 7.86s** — matches the post-260503-rs8 baseline exactly, no test count delta, all assertions in the extended test pass.

Static spot-checks (all passed):
- `grep -n '"run_name"' backend/api/routes/chat.py` → 1 hit (line 95, top-level dict entry).
- `grep -c 'run_name' backend/api/routes/chat.py` → 2 (1 in docstring, 1 in code).
- `grep -n 'run_name' backend/tests/test_observability_wiring.py` → 1 hit (line 39, assertion in `test_chat_attaches_callback_when_enabled`).

## Operator Note: Uvicorn Restart Required

The running uvicorn server (port 8000, started before this task) holds the OLD `_make_config` in memory. Live `/api/chat` traffic will continue to emit traces with the LangGraph-default root span name until the server is restarted. After restart, the next POST to `/api/chat` produces a Langfuse trace whose Observations dashboard "Name" column shows `express-surcharge-agent` (matching the existing "Trace Name" column).

Same operational caveat as quick-task 260503-rs8 — pytest exercises a fresh import per run so the test suite covers the change without a server restart, but live traffic does not.

Recommended restart command (per CLAUDE.md tech stack):
```bash
uvicorn backend.api.main:app --reload --port 8000
```

Previously-recorded traces retain their old root span name; only NEW traces post-restart pick up the new `run_name`.

## User Setup Required

None — no environment variables, no external service configuration. The change is purely in-process Python code; the Langfuse SDK already in use (langfuse 4.5.1 + langchain 0.3.28 pinned in 260503-rs8) consumes the `run_name` field automatically once the new `_make_config` is loaded.

## Next Phase Readiness

- Both Langfuse Observations columns ("Name" and "Trace Name") will display `express-surcharge-agent` after uvicorn restart, satisfying OBS-FIX-RUN-NAME and completing the pair started by OBS-FIX-TRACE-NAME (260503-rs8).
- Demo screenshots and dashboard filtering align under one consistent agent identity.
- No follow-up quick task expected — the OBS gap reported by the user (Name column showing "LangGraph") is fully closed by this change.

## Self-Check: PASSED

- File `backend/api/routes/chat.py`: FOUND (modified, contains `"run_name": "express-surcharge-agent",` at line 95 + docstring bullet at line 80).
- File `backend/tests/test_observability_wiring.py`: FOUND (modified, contains assertion at line 39).
- File `.planning/quick/260503-s2h-set-runnableconfig-run-name-so-langfuse-/260503-s2h-SUMMARY.md`: FOUND (this file).
- Commit `0606e43`: FOUND in git log on `feature/polish-observability-docs`.
- Test result: **186 passed** (no test count delta; matches success criteria).

---
*Quick-task: 260503-s2h*
*Completed: 2026-05-03*
