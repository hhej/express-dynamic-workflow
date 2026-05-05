---
phase: quick-260503-rs8
plan: 01
subsystem: observability
tags: [langfuse, langchain, langgraph, tracing, callbacks, dependencies]

# Dependency graph
requires:
  - phase: 05
    provides: Langfuse observability scaffolding (Plan 05-01) and per-turn CallbackHandler wiring (Plan 05-02)
provides:
  - Live Langfuse tracing actually fires in production (top-level langchain dep was missing → silent no-op)
  - Stable, filterable trace name on every /api/chat trace (langfuse_trace_name="express-surcharge-agent")
affects: [phase-05-polish-observability-docs, demo-week-6]

# Tech tracking
tech-stack:
  added: ["langchain==0.3.28 (top-level package, required by langfuse.langchain CallbackHandler import)"]
  patterns: ["constant trace_name in metadata for one-name dashboard filter (NOT per-question dynamic name)"]

key-files:
  created: []
  modified:
    - requirements.txt (1 line added)
    - backend/api/routes/chat.py (1 dict entry + 2 docstring lines)
    - backend/tests/test_observability_wiring.py (1 assertion added)

key-decisions:
  - "Pin langchain==0.3.28 (not later) — verified compatible with langchain-core==0.3.84 + langfuse==4.5.1 via live install where 25 traces reached Langfuse Cloud"
  - "langfuse_trace_name is a STRING CONSTANT 'express-surcharge-agent', not derived from message/intent — single stable name to filter the dashboard by"
  - "Extend single existing test (test_chat_attaches_callback_when_enabled) over adding a new test — locks contract with minimum surface change"
  - "observability.py byte-identical — the dep pin alone fixes the silent-import-failure root cause; no source change in the helper"

patterns-established:
  - "Three atomic edits in one commit when they are co-required (dep pin makes import succeed, trace_name names the now-firing traces, test locks the contract)"
  - "When the gold-standard 186-test suite is green but production observability is dead, suspect a graceful-no-op fallback hiding an import failure"

requirements-completed: [OBS-FIX-LANGCHAIN-PIN, OBS-FIX-TRACE-NAME]

# Metrics
duration: 2min
completed: 2026-05-03
---

# Quick Task 260503-rs8: Pin langchain dep + set Langfuse trace name Summary

**Pinned langchain==0.3.28 so `langfuse.langchain.CallbackHandler` import actually succeeds in production, AND added constant `langfuse_trace_name="express-surcharge-agent"` so every Langfuse trace filters under one stable name in the dashboard.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-03T13:02:46Z
- **Completed:** 2026-05-03T13:04:12Z
- **Tasks:** 1 (single-task quick fix per plan; three co-required edits in one commit)
- **Files modified:** 3

## Accomplishments

- **Live Langfuse tracing now fires.** Root cause was the `from langfuse.langchain import CallbackHandler` line in `backend/agent/observability.py:50` — it requires the top-level `langchain` package, but `requirements.txt` only pinned `langchain-core==0.3.84`. Because `get_callback_handler()` returns None on import failure (graceful no-op pattern by design — D-13), the 186-test suite passed while OBS-01/02/03 were effectively dead in production. Live install of `langchain==0.3.28` confirmed compatibility and 25 traces successfully landed in Langfuse Cloud.
- **Stable trace name on every /api/chat trace.** `_make_config` metadata dict gains exactly one new key — `langfuse_trace_name: "express-surcharge-agent"` — so the Langfuse dashboard has one stable name to filter all agent traces by. Constant string, NOT derived from message/intent (out-of-scope guard honored).
- **Test contract locked.** `test_chat_attaches_callback_when_enabled` extended with one new assertion covering the new key, in-place rather than as a new test.

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin langchain dep, add langfuse_trace_name, extend test** — `529075f` (fix)

## Files Created/Modified

- `requirements.txt` — Added `langchain==0.3.28` between `langchain-core==0.3.84` (line 11) and `langchain-google-genai==2.1.12` (line 13), keeping the lang* pins grouped.
- `backend/api/routes/chat.py` — `_make_config` metadata dict now has 5 keys (was 4); new key `"langfuse_trace_name": "express-surcharge-agent"` added directly under `langfuse_session_id`. Docstring Returns section gained one matching bullet under `metadata.langfuse_session_id`.
- `backend/tests/test_observability_wiring.py` — `test_chat_attaches_callback_when_enabled` extended with `assert cfg["metadata"]["langfuse_trace_name"] == "express-surcharge-agent"` (line 38).

**Line counts:** 1 addition to requirements.txt + 3 additions to chat.py (1 dict entry + 2 docstring lines) + 1 addition to test = **5 net insertions, 0 deletions** (matches `git commit` output: `3 files changed, 5 insertions(+)`).

## Decisions Made

- **Pin 0.3.28 specifically (not latest)** — that exact version was verified compatible with the existing `langchain-core==0.3.84` and `langfuse==4.5.1` pins via a live install where 25 traces reached Langfuse Cloud. Bumping to a different version risks a SemVer-locked import-graph regression.
- **Constant trace name, not derived** — user decision documented in plan: one stable name to filter the dashboard by. Per-question dynamic naming (e.g. interpolating intent or message) was explicitly out-of-scope.
- **Extend single existing test, not add a new one** — the enabled-path test is sufficient since `_make_config` builds metadata identically regardless of key presence (only the callbacks list branches). Test count stays at 186.
- **Do not touch observability.py** — the import-time failure is fixed by the requirements.txt pin alone. The helper's graceful no-op design is correct (preserves CLAUDE.md local-reproducibility constraint when `LANGFUSE_*` keys are missing). Verified `git diff --stat backend/agent/observability.py` is empty.

## Deviations from Plan

None — plan executed exactly as written. Three atomic edits, one commit, 186/186 tests green.

## Issues Encountered

None.

## Verification Results

| Check | Expected | Actual |
|---|---|---|
| `grep -n "^langchain==0.3.28$" requirements.txt` | 1 match between langchain-core and langchain-google-genai | line 12, sandwiched between line 11 and line 13 ✓ |
| `grep -n "langfuse_trace_name" backend/api/routes/chat.py` | ≥2 matches (dict + docstring) | 2 matches: line 81 (docstring) + line 97 (dict) ✓ |
| `grep -n "express-surcharge-agent" backend/api/routes/chat.py` | dict-value match | 2 matches (docstring + dict value) ✓ |
| `grep -n "langfuse_trace_name" backend/tests/test_observability_wiring.py` | 1 match inside enabled test | line 38, inside `test_chat_attaches_callback_when_enabled` ✓ |
| `pytest backend/tests/ -q` | 186 passed | **186 passed in 6.31s** ✓ |
| `git diff --stat backend/agent/observability.py` | empty (untouched) | empty ✓ |
| `_make_config(...)["metadata"]["langfuse_trace_name"]` | "express-surcharge-agent" | covered by new assertion in test ✓ |

## Operator / Deploy Note

**A running uvicorn process holds the OLD `_make_config` in memory and must be restarted before the new `langfuse_trace_name` metadata key takes effect on live `/api/chat` requests.** This is a deploy-side action, NOT a plan task. Pytest exercises a fresh import each run so the test suite covers the new key without needing a server restart.

The executor was instructed via context note that a uvicorn server may be running on port 8000 from earlier verification work. The executor did NOT restart it — that is a deployment-time concern documented here for the user.

To pick up the change on a live server:

```bash
# from /Users/pollot/Desktop/express-dynamic-workflow
.venv/bin/pip install -r requirements.txt   # only if the venv lacks langchain==0.3.28
# then restart uvicorn (kill the existing process and re-run):
.venv/bin/uvicorn backend.api.main:app --reload
```

Once restarted, every `/api/chat` request will emit a Langfuse trace named `express-surcharge-agent`, filterable as a single name in the Langfuse Cloud dashboard.

## Root-Cause One-Liner

Langfuse traces were silently no-op'd because `from langfuse.langchain import CallbackHandler` requires top-level `langchain`, which wasn't pinned. Now pinned at 0.3.28; live install verified 25 traces reaching Langfuse Cloud.

## Self-Check: PASSED

- requirements.txt modified (line 12 contains `langchain==0.3.28`) ✓
- backend/api/routes/chat.py modified (lines 81, 97 contain `langfuse_trace_name`) ✓
- backend/tests/test_observability_wiring.py modified (line 38 contains assertion) ✓
- Commit `529075f` exists in git log ✓
- Test suite green: 186 passed in 6.31s ✓
- No files outside the three planned were modified ✓
- observability.py byte-identical (empty `git diff --stat`) ✓

---
*Quick task: 260503-rs8*
*Completed: 2026-05-03*
