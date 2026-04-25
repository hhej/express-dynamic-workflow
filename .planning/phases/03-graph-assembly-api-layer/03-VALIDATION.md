---
phase: 3
slug: graph-assembly-api-layer
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-25
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 + pytest-mock 3.15.1 + pytest-httpx 0.35.0 + pytest-asyncio 0.24.0 (added in Plan 03-01) |
| **Config file** | `backend/tests/conftest.py` (fixtures); pytest-asyncio mode `auto` set in pytest.ini (created Plan 03-01) |
| **Quick run command** | `.venv/bin/python -m pytest backend/tests/test_<module>.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest backend/tests/ -q` |
| **Estimated runtime** | ~12-18 seconds (Phase 2 baseline ~6s; Phase 3 adds async tests + checkpoint setup) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest backend/tests/test_<module>.py -x -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest backend/tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 18 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | (deps install) | runtime | `.venv/bin/python -c "import fastapi, uvicorn, aiosqlite; from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver"` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | ORCH-06 (extension) | unit | `.venv/bin/python -m pytest backend/tests/ -q` (no regressions) | ✅ existing | ⬜ pending |
| 03-01-03 | 01 | 1 | (test scaffolds) | collection | `.venv/bin/python -m pytest backend/tests/ --collect-only -q` (≥27 new placeholder tests collected) | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | ORCH-01 | unit | `.venv/bin/python -m pytest backend/tests/test_planner.py -x -v` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | ORCH-04, ORCH-05, ORCH-10 (D-13) | unit | `.venv/bin/python -m pytest backend/tests/test_pricing_agent.py backend/tests/test_response_node.py backend/tests/test_fuel_agent.py backend/tests/test_route_agent.py -x` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 3 | ORCH-08 | unit | `.venv/bin/python -c "from backend.agent.graph import phase3_retry_on; import httpx; assert phase3_retry_on(httpx.HTTPError('x')); assert not phase3_retry_on(ValueError('x'))"` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 3 | ORCH-08, ORCH-10 | integration | `.venv/bin/python -m pytest backend/tests/test_graph.py -x -v` | ❌ W0 | ⬜ pending |
| 03-04-01 | 04 | 4 | API-01 (shell) | runtime | `.venv/bin/python -c "from backend.api.main import app; from backend.api.sse import format_sse; assert format_sse('meta', {}).startswith(b'data: ')"` | ❌ W0 | ⬜ pending |
| 03-04-02 | 04 | 4 | API-01 | integration | `.venv/bin/python -m pytest backend/tests/test_api_chat.py -x -v` | ❌ W0 | ⬜ pending |
| 03-05-01 | 05 | 4 | API-02, API-03 | integration | `.venv/bin/python -m pytest backend/tests/test_api_conversations.py -x -v` | ❌ W0 | ⬜ pending |
| 03-05-02 | 05 | 4 | API-04 | integration | `.venv/bin/python -m pytest backend/tests/test_api_fuel_prices.py -x -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Plan 03-01 lands all of these:

- [ ] `backend/tests/test_planner.py` — 5 stubs for ORCH-01 (filled in Plan 03-02)
- [ ] `backend/tests/test_pricing_agent.py` — 3 stubs for ORCH-04 (filled in Plan 03-02)
- [ ] `backend/tests/test_response_node.py` — 4 stubs for ORCH-05 (filled in Plan 03-02)
- [ ] `backend/tests/test_graph.py` — 7 stubs for ORCH-08, ORCH-10, cross-cutting (filled in Plan 03-03)
- [ ] `backend/tests/test_api_chat.py` — 3 stubs for API-01 (filled in Plan 03-04)
- [ ] `backend/tests/test_api_conversations.py` — 3 stubs for API-02 + API-03 (filled in Plan 03-05)
- [ ] `backend/tests/test_api_fuel_prices.py` — 2 stubs for API-04 (filled in Plan 03-05)
- [ ] `backend/tests/conftest.py` — `in_memory_checkpointer` fixture using `aiosqlite.connect(":memory:")` + `AsyncSqliteSaver(conn).setup()`
- [ ] `backend/tests/test_fuel_agent.py` — extend with `test_fetched_at_added_to_dump` placeholder (skipped; filled in Plan 03-02)
- [ ] `backend/tests/test_route_agent.py` — extend with `test_fetched_at_added_to_dump` placeholder (skipped; filled in Plan 03-02)
- [ ] Framework install: `pytest-asyncio==0.24.0` (added to requirements.txt in Plan 03-01)
- [ ] `pytest.ini` (or pyproject [tool.pytest.ini_options]) with `asyncio_mode = "auto"`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live SSE stream end-to-end on real Gemini + Google Maps | API-01 | Free-tier API quota — automated tests use FakeMessagesListChatModel + mocked tools per D-25 | After Plan 03-04 lands, run `.venv/bin/uvicorn backend.api.main:app --port 8000` then `curl -N -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message":"Surcharge for 15kg Bounce shipment from Bangkok to Nonthaburi"}'`. Verify the stream emits `data: {"type":"meta",...}` first, then multiple `trace` events, then one `answer`, then `done`. |
| Uvicorn boot with real CHECKPOINT_PATH (creates data/checkpoints.db) | ORCH-10 | Pitfall 9 surfaces only on first request after fresh deploy; in-memory tests recreate tables every run | After Plan 03-04, run uvicorn once; verify `data/checkpoints.db` is created; `sqlite3 data/checkpoints.db ".schema"` shows checkpoints + writes tables. |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (Plan 03-01 creates every test file)
- [x] No watch-mode flags
- [x] Feedback latency < 18s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready (will flip to wave_0_complete: true after Plan 03-01 ships)
