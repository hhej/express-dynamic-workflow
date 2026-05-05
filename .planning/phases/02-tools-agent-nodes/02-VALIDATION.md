---
phase: 2
slug: tools-agent-nodes
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-18
updated: 2026-04-18
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 (existing Phase 1 infra) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) — created in Plan 01 Task 2 |
| **Quick run command** | `.venv/bin/pytest backend/tests/test_<module>.py -x -q` |
| **Full suite command** | `.venv/bin/pytest backend/tests/ -q` |
| **Estimated runtime** | ~10 seconds full suite (~70 tests expected after phase complete) |

---

## Sampling Rate

- **After every task commit:** Run the task's quick command (e.g., `.venv/bin/pytest backend/tests/test_fetch_fuel_price.py -x -q`)
- **After every plan wave:** Run `.venv/bin/pytest backend/tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green (Phase 1 35 tests + Phase 2 additions)
- **Max feedback latency:** 10 seconds (full suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | Phase 2 foundation (deps + config + env) | smoke | `.venv/bin/python -c "from backend.config import GEMINI_MODEL, FUEL_FETCH_TIMEOUT, ROUTE_CACHE_TTL_SECONDS, TRAFFIC_RATIO_BUCKETS"` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | AgentState reducer fix + FuelData docs + pyproject | regression | `.venv/bin/pytest backend/tests/ -q` | ✅ Phase 1 | ⬜ pending |
| 02-01-03 | 01 | 0 | conftest + fixtures | smoke | `.venv/bin/pytest backend/tests/ -q --collect-only` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | TOOL-01 (tests RED) | unit | `.venv/bin/pytest backend/tests/test_fetch_fuel_price.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | TOOL-01 (implementation GREEN) | unit | `.venv/bin/pytest backend/tests/test_fetch_fuel_price.py -x -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 1 | TOOL-02 TTLCache helper | smoke | `.venv/bin/python -c "from backend.agent.tools._cache import TTLCache; TTLCache(10)"` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 1 | TOOL-02 (tests RED) | unit | `.venv/bin/pytest backend/tests/test_calculate_route.py -x -q` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03 | 1 | TOOL-02 (implementation GREEN) | unit | `.venv/bin/pytest backend/tests/test_calculate_route.py -x -q` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 1 | TOOL-03 | unit | `.venv/bin/pytest backend/tests/test_lookup_rate.py -x -q` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 1 | TOOL-04 | unit | `.venv/bin/pytest backend/tests/test_calculate_surcharge_tool.py -x -q` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 2 | llm factory + prompts | smoke | `.venv/bin/python -c "from backend.agent.llm import get_chat_model; from backend.agent.prompts.fuel_agent import SYSTEM_PROMPT; from backend.agent.prompts.route_agent import SYSTEM_PROMPT"` | ❌ W0 | ⬜ pending |
| 02-05-02 | 05 | 2 | ORCH-02 (Fuel Agent node) | unit | `.venv/bin/pytest backend/tests/test_fuel_agent.py -x -q` | ❌ W0 | ⬜ pending |
| 02-05-03 | 05 | 2 | ORCH-03 (Route Agent node) | unit | `.venv/bin/pytest backend/tests/test_route_agent.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Requirement coverage:**
- TOOL-01 -> Plan 02 Task 2
- TOOL-02 -> Plan 03 Task 3
- TOOL-03 -> Plan 04 Task 1
- TOOL-04 -> Plan 04 Task 2
- ORCH-02 -> Plan 05 Task 2
- ORCH-03 -> Plan 05 Task 3

Every Phase 2 requirement has at least one automated command.

---

## Wave 0 Requirements

Wave 0 (Plan 01) must be complete before Wave 1 plans (02, 03, 04) execute. Wave 2 (Plan 05) depends on Plans 02 and 03.

- [ ] `pytest-httpx==0.35.0` installed via `requirements.txt` (Plan 01 Task 1)
- [ ] `pytest-mock==3.15.1` installed (Plan 01 Task 1)
- [ ] `langgraph`, `langchain-core`, `langchain-google-genai`, `googlemaps`, `httpx` installed (Plan 01 Task 1)
- [ ] `backend/agent/state.py` uses `Annotated[List[dict], operator.add]` for `reasoning_trace` (Plan 01 Task 2) — Pitfall 1 fix
- [ ] `backend/agent/tools/models.py` FuelData docstring enumerates `eppo_live`, `eppo_cached_csv`, `hardcoded_baseline` (Plan 01 Task 2) — D-03
- [ ] `backend/config.py` exposes `GEMINI_MODEL`, `FUEL_FETCH_TIMEOUT`, `ROUTE_CACHE_TTL_SECONDS`, `TRAFFIC_RATIO_BUCKETS`, `GOOGLE_MAPS_API_KEY`, `GOOGLE_API_KEY` (Plan 01 Task 1)
- [ ] `.env.example` documents the four new env vars (Plan 01 Task 1)
- [ ] `pyproject.toml` at repo root with `[tool.pytest.ini_options]` (Plan 01 Task 2)
- [ ] `backend/tests/conftest.py` with 7 fixtures: `sample_agent_state`, `eppo_html_fixture`, `gmaps_directions_fixture`, `gmaps_geocode_bangkok_fixture`, `gmaps_geocode_ayutthaya_fixture`, `gmaps_geocode_lopburi_fixture`, `seeded_sqlite_path` (Plan 01 Task 3)
- [ ] Fixture files under `backend/tests/fixtures/`: `eppo_sample.html`, `gmaps_directions.json`, `gmaps_geocode_bangkok.json`, `gmaps_geocode_ayutthaya.json`, `gmaps_geocode_lopburi.json` (Plan 01 Task 3)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Google Maps integration sanity check | TOOL-02 | Requires real `GOOGLE_MAPS_API_KEY` and internet; we don't want CI burning API credit | (Optional, dev-only) Set `GOOGLE_MAPS_API_KEY` in `.env`, run `.venv/bin/python -c "from backend.agent.tools.calculate_route import calculate_route; print(calculate_route('Bangkok', 'Nonthaburi'))"`. Expect a RouteData with distance ~15km and zone=central-1. |
| Live Gemini integration sanity check | ORCH-02 / ORCH-03 | Free-tier 15 RPM; CI mustn't consume quota | (Optional, dev-only) Set `GOOGLE_API_KEY` in `.env`, run `fuel_agent_node(sample_state)` manually and inspect the trace entry's reasoning string is coherent natural language. |
| Live EPPO scrape selector discovery | TOOL-01 (Level 1) | Stubbed with `NotImplementedError` per Open Question 2; selectors need human-captured HTML first | Deferred to Phase 5 polish. Until then the fallback chain (CSV -> baseline) serves all fuel queries. |

All three manual verifications are optional and do NOT block `/gsd:verify-work`. The 3-level fallback chain and FakeMessagesListChatModel ensure all automated tests pass without live services.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task has its own pytest command)
- [x] Wave 0 covers all MISSING references (conftest, fixtures, reducer fix, config, deps)
- [x] No watch-mode flags (all commands use `-x -q` or `-q`, single-shot)
- [x] Feedback latency < 10s (full suite estimated at ~10s with 70 tests)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-18
