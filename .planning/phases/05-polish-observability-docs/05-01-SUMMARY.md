---
phase: 05-polish-observability-docs
plan: 01
subsystem: infra
tags: [langfuse, tavily, python311, observability, pydantic, foundation]

requires:
  - phase: 04-app-composition-trace-mvp
    provides: AgentState v2, FastAPI chat handler, frontend trace panel — all foundations Phase 5 extends without rewriting
provides:
  - Python 3.11+ runtime pinned and venv migrated
  - langfuse 4.5.1 + tavily-python 0.7.24 in requirements.txt
  - AgentState extended with approval_decision (D-07) and search_context (D-11) fields
  - backend/config.py exposing HITL_TOTAL_THB_THRESHOLD, SEARCH_CACHE_TTL_SECONDS, LANGFUSE_*, TAVILY_API_KEY
  - .env.example listing all six new env placeholders
  - backend/agent/observability.py with get_langfuse_client / get_callback_handler / seed_trace_id / post_formula_accuracy_score (graceful no-op when keys missing)
  - SearchInput / SearchSource / SearchResult Pydantic models in backend/agent/tools/models.py for Tavily plan
  - Shared test fixtures (mock_langfuse, mock_tavily_client, mock_pricing_low/high) in conftest.py
  - test_observability.py + test_state_phase5.py scaffolds (Phase 5 ready-to-fail stubs)
affects: [05-02-langfuse-wiring, 05-03-parallel-fanout, 05-04-search-agent, 05-05-hitl-gate, 05-06-feedback-frontend, 05-07-docs]

tech-stack:
  added: [langfuse==4.5.1, tavily-python==0.7.24]
  patterns:
    - "Graceful-no-op observability: missing keys return None, agent runs identically without Langfuse"
    - "Deterministic trace_id seed (chat_turn_{thread_id}_{turn_idx}) via seed_trace_id() — load-bearing for D-14/D-16 score attachment without name lookup"
    - "Fire-and-forget auto-eval: post_formula_accuracy_score swallows failures so eval never affects user response"

key-files:
  created:
    - backend/agent/observability.py
    - backend/tests/test_observability.py
    - backend/tests/test_state_phase5.py
  modified:
    - requirements.txt
    - .env.example
    - backend/config.py
    - backend/agent/state.py
    - backend/agent/tools/models.py
    - backend/tests/conftest.py

key-decisions:
  - "Python 3.11 baseline (was 3.10) — required by langfuse 4.x SDK"
  - "AgentState additive-only: approval_decision + search_context appended, no rename of existing fields"
  - "observability.py uses graceful-no-op pattern (logger.warning + return None) so local dev without Langfuse keys is identical"
  - "seed_trace_id falls back to md5(...) when client missing — guarantees the same key in tests as in production"

patterns-established:
  - "Phase 5 imports observability via `from backend.agent.observability import ...` — single chokepoint for Langfuse"
  - "Pydantic models in tools/models.py centralized so search/HITL plans share the schema"

requirements-completed:
  - OBS-01
  - OBS-03

duration: ~22 min
completed: 2026-05-03
---

# Phase 5 Plan 01: Foundation Summary

**Phase 5 contracts locked: Python 3.11 venv + langfuse/tavily deps + AgentState v3 + observability.py with deterministic trace IDs**

## Performance

- **Duration:** ~22 min
- **Tasks:** 4
- **Files modified:** 9

## Accomplishments
- Python 3.11.15 venv with langfuse 4.5.1 + tavily-python 0.7.24 installed and pinned
- AgentState extended with `approval_decision` (D-07) and `search_context` (D-11) — additive only
- backend/agent/observability.py created with graceful no-op semantics — agent runs identically without Langfuse keys
- Deterministic trace_id pattern (`chat_turn_{thread_id}_{turn_idx}`) implemented as `seed_trace_id()` — load-bearing for downstream feedback attachment without name lookup
- Six new env placeholders added to `.env.example` and corresponding constants in `backend/config.py`
- Shared test fixtures (`mock_langfuse`, `mock_tavily_client`, `mock_pricing_low`, `mock_pricing_high`) added to conftest for downstream plans
- Test scaffolds (`test_observability.py`, `test_state_phase5.py`) added — 8 tests, all passing
- Full backend suite passes (117 tests, no regressions)

## Task Commits

1. **Task 1: bump Python + deps** — `62f306f` (chore)
2. **Task 2: extend AgentState** — `3dc6c5a` (feat)
3. **Task 3: config + .env.example** — `3ee34ff` (feat)
4. **Task 4: observability.py + Pydantic models + fixtures** — `90218c6` (feat)

## Files Created/Modified
- `requirements.txt` — pinned langfuse==4.5.1 and tavily-python==0.7.24
- `.env.example` — six new env placeholders for Phase 5
- `backend/config.py` — HITL_TOTAL_THB_THRESHOLD (500.0), SEARCH_CACHE_TTL_SECONDS (1800), Langfuse/Tavily key constants
- `backend/agent/state.py` — added approval_decision + search_context to AgentState
- `backend/agent/observability.py` — Langfuse helpers with graceful no-op
- `backend/agent/tools/models.py` — SearchInput, SearchSource, SearchResult Pydantic models
- `backend/tests/conftest.py` — shared Phase 5 fixtures
- `backend/tests/test_observability.py` — 5 unit tests for observability helpers
- `backend/tests/test_state_phase5.py` — 3 tests for state extension

## Decisions Made
- Python 3.11.15 venv; langfuse 4.5.1 (latest stable, requires 3.11+) and tavily-python 0.7.24
- AgentState additive only — no rename of existing fields, preserves Phase 4 contracts
- observability helpers return None when keys missing (graceful no-op) instead of raising — preserves local-dev parity
- `seed_trace_id` md5 fallback guarantees test/prod parity even without a Langfuse client

## Deviations from Plan

None — plan executed as written.

## Issues Encountered

- Wrap-up phase (SUMMARY.md + STATE/ROADMAP updates) was completed by orchestrator after the executor agent's stream timed out post-Task 4 commit. Spot-checks confirmed all 4 task commits present, all expected files on disk, and test suite passing — work was complete; only the documentation handoff was finished by orchestrator.

## Next Phase Readiness
- Wave 2 plans (05-02 Langfuse wiring + 05-03 parallel fan-out) can now import from `backend.agent.observability` and reference the new AgentState fields
- All downstream Phase 5 plans (02–06) have ready-to-fail test stubs and shared fixtures
- HITL threshold (500.0 THB) and search cache TTL (1800s) configurable via env

---
*Phase: 05-polish-observability-docs*
*Completed: 2026-05-03*
