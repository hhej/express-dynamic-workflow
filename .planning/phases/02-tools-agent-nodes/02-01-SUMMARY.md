---
phase: 02-tools-agent-nodes
plan: 01
subsystem: infra
tags: [langgraph, pytest, httpx, pytest-httpx, googlemaps, langchain-google-genai, gemini, conftest, fixtures]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: AgentState TypedDict, FuelData/RouteData/RateResult/SurchargeInput/SurchargeResult Pydantic models, backend/config.py pattern, data/express.db seeded rate_table, Phase 1 pytest suite (35 green)
provides:
  - Phase 2 Python dependencies installed and pinned (langgraph 0.6.11, langchain-google-genai 2.1.12, googlemaps 4.10.0, httpx 0.28.1, pytest-httpx 0.35.0, pytest-mock 3.15.1, langchain-core 0.3.84)
  - Six new config constants in backend/config.py (GOOGLE_MAPS_API_KEY, GOOGLE_API_KEY, GEMINI_MODEL, FUEL_FETCH_TIMEOUT, ROUTE_CACHE_TTL_SECONDS, TRAFFIC_RATIO_BUCKETS)
  - AgentState.reasoning_trace typed as Annotated[List[dict], operator.add] so parallel Send nodes append rather than overwrite (Pitfall 1 fix)
  - FuelData.source docstring documents the five valid values (eppo, ptt, eppo_live, eppo_cached_csv, hardcoded_baseline) per D-03
  - pyproject.toml with [tool.pytest.ini_options] enabling bare `pytest` invocation and silencing Python 3.9 EOL deprecation warnings from google/pydantic
  - backend/tests/conftest.py with 7 shared fixtures (sample_agent_state, eppo_html_fixture, gmaps_directions_fixture, gmaps_geocode_bangkok/ayutthaya/lopburi_fixture, seeded_sqlite_path)
  - Five canonical fixture files under backend/tests/fixtures/ (EPPO HTML sample + 1 directions JSON + 3 geocode JSONs including 'Ayutthaya Province' form to exercise Pitfall 6)
affects: [02-02-fuel-agent, 02-03-route-agent, 02-04-pricing-agent, 02-05-orchestrator, 05-langgraph-graph]

# Tech tracking
tech-stack:
  added: [langgraph==0.6.11, langchain-core==0.3.84, langchain-google-genai==2.1.12, googlemaps==4.10.0, httpx==0.28.1, pytest-httpx==0.35.0, pytest-mock==3.15.1]
  patterns: [Annotated-reducer for LangGraph state fields, shared conftest.py fixtures for parallel test plans, captured-fixture JSON files for external-API mocking, env-loaded config with list-parsing (TRAFFIC_RATIO_BUCKETS), pyproject.toml pytest configuration]

key-files:
  created: [pyproject.toml, backend/tests/conftest.py, backend/tests/fixtures/eppo_sample.html, backend/tests/fixtures/gmaps_directions.json, backend/tests/fixtures/gmaps_geocode_bangkok.json, backend/tests/fixtures/gmaps_geocode_ayutthaya.json, backend/tests/fixtures/gmaps_geocode_lopburi.json]
  modified: [requirements.txt, backend/config.py, .env.example, backend/agent/state.py, backend/agent/tools/models.py]

key-decisions:
  - "pytest-httpx chosen over `responses` for HTTP mocking (C-01): unified httpx-native mocking for both fuel-tool and any future HTTP call"
  - "TRAFFIC_RATIO_BUCKETS parsed from comma-separated env string with defaults 1.1/1.3/1.5/1.8 (D-06) -- keeps thresholds tunable without code edits"
  - "ROUTE_CACHE_TTL_SECONDS default 900s (15 min) per D-07 -- balances Google Maps quota against data freshness"
  - "FuelData.source kept as `str` (no Enum) per D-03 -- open value-set accommodates future data sources without schema migration"
  - "AgentState.reasoning_trace uses operator.add reducer (Pitfall 1) so Phase 5 parallel Send nodes append traces cleanly"
  - "seeded_sqlite_path fixture copies the real data/express.db instead of re-seeding in-memory -- tests run against the exact Phase 1 rate_table as shipped"
  - "pyproject.toml filterwarnings ignores google.* and pydantic.* DeprecationWarnings -- they are Python 3.9 EOL notices from transitive deps, not our code"

patterns-established:
  - "LangGraph-reducer-on-TypedDict: use Annotated[T, reducer_fn] from typing_extensions for any state field multiple nodes write to (critical for parallel Send)"
  - "Shared conftest.py lives at backend/tests/conftest.py and exposes named fixtures consumed by every downstream test module in Phase 2"
  - "Fixture JSON/HTML files live at backend/tests/fixtures/ and capture canonical upstream-API shapes -- tests load via conftest helpers rather than inline-literal strings"
  - "Config list-values parsed from comma-separated env strings with sensible defaults (see TRAFFIC_RATIO_BUCKETS) -- preserve env-driven configuration while supporting structured data"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-18
---

# Phase 02 Plan 01: Wave 0 Foundation Summary

**Phase 2 Wave 0 test & runtime scaffolding: 7 new pinned deps installed, six config constants added, AgentState.reasoning_trace migrated to operator.add reducer, FuelData source docs expanded per D-03, shared conftest with 7 fixtures plus 5 canonical fixture files landed, pyproject.toml pytest config added; Phase 1's 35-test suite still green.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-18T07:44:08Z
- **Completed:** 2026-04-18T07:48:38Z
- **Tasks:** 3
- **Files modified:** 12 (3 modified + 8 created; pyproject.toml + 6 test assets + 1 modified requirements.txt + 1 modified config.py + 1 modified .env.example + 1 modified state.py + 1 modified models.py -- pyproject.toml counted as created)

## Accomplishments

- Installed and pinned 7 Phase 2 Python dependencies into `.venv` (langgraph 0.6.11, langchain-core 0.3.84, langchain-google-genai 2.1.12, googlemaps 4.10.0, httpx 0.28.1, pytest-httpx 0.35.0, pytest-mock 3.15.1) and documented the four new env vars in `.env.example`.
- Fixed the Phase 2 Pitfall 1 in `backend/agent/state.py`: `reasoning_trace` now uses `Annotated[List[dict], operator.add]` so parallel Fuel/Route Send nodes in Phase 5 append traces without clobbering each other's writes.
- Built the shared test scaffolding Plans 02-05 will parallelise over: `backend/tests/conftest.py` with 7 reusable fixtures, plus 5 canonical fixture files under `backend/tests/fixtures/` (including the 'Ayutthaya Province' geocode form that exercises Pitfall 6 province-suffix normalisation).
- Added `pyproject.toml` with `[tool.pytest.ini_options]` so `pytest` runs without arguments and suppresses unavoidable Python 3.9 EOL deprecation warnings from google/pydantic transitive deps.
- Phase 1 regression clean: `.venv/bin/pytest backend/tests/ -q` still reports **35 passed** after the reducer-type change and conftest load.

## Task Commits

Each task was committed atomically:

1. **Task 1: Install Phase 2 dependencies, extend config, update .env.example** - `5c961fe` (chore)
2. **Task 2: Fix AgentState reducer + expand FuelData.source docs + add pyproject.toml** - `ac48832` (feat)
3. **Task 3: Create conftest.py + fixture files for Phase 2 tests** - `3cf1e92` (test)

**Plan metadata:** (to be recorded after final commit)

## Files Created/Modified

### Modified
- `requirements.txt` - Appended 7 Phase 2 deps after existing Phase 1 pins (no deletions)
- `backend/config.py` - Added six Phase 2 constants (GOOGLE_MAPS_API_KEY, GOOGLE_API_KEY, GEMINI_MODEL, FUEL_FETCH_TIMEOUT, ROUTE_CACHE_TTL_SECONDS, TRAFFIC_RATIO_BUCKETS) with env-driven defaults
- `.env.example` - Appended four new env var entries (GEMINI_MODEL, FUEL_FETCH_TIMEOUT, ROUTE_CACHE_TTL_SECONDS, TRAFFIC_RATIO_BUCKETS); API-key entries unchanged
- `backend/agent/state.py` - `reasoning_trace` now `Annotated[List[dict], operator.add]`; added `import operator` and `from typing_extensions import Annotated`; field docstring explains Pitfall 1 fix
- `backend/agent/tools/models.py` - `FuelData` class docstring + `source` Field description now list all five allowed values (eppo, ptt, eppo_live, eppo_cached_csv, hardcoded_baseline); type remains `str`, no Enum per D-03

### Created
- `pyproject.toml` - `[tool.pytest.ini_options]` with testpaths, addopts, filterwarnings (ignores google/pydantic DeprecationWarnings from Python 3.9 EOL)
- `backend/tests/conftest.py` - 7 pytest fixtures (sample_agent_state, eppo_html_fixture, gmaps_directions_fixture, gmaps_geocode_bangkok_fixture, gmaps_geocode_ayutthaya_fixture, gmaps_geocode_lopburi_fixture, seeded_sqlite_path)
- `backend/tests/fixtures/eppo_sample.html` - Minimal well-formed EPPO price-page HTML with Diesel B7 row
- `backend/tests/fixtures/gmaps_directions.json` - Canonical `googlemaps.directions()` response (15.2 km, 1800s normal, 2400s with traffic -> ratio 1.333 -> severity 3)
- `backend/tests/fixtures/gmaps_geocode_bangkok.json` - Bangkok reverse-geocode (central-1 example)
- `backend/tests/fixtures/gmaps_geocode_ayutthaya.json` - Ayutthaya reverse-geocode using 'Ayutthaya Province' form to drive Pitfall 6 normalisation (central-2 example)
- `backend/tests/fixtures/gmaps_geocode_lopburi.json` - Lop Buri reverse-geocode (central-3 example)

## Decisions Made

- **pytest-httpx over `responses`:** Phase 2 Correction C-01. httpx-native mocking keeps fuel-tool tests aligned with the production HTTP client.
- **AgentState reducer via `operator.add`:** Phase 2 Pitfall 1. Without it, Phase 5 parallel Send nodes would each overwrite `reasoning_trace` with only their own single entry, silently losing the transparency trail the project's Core Value depends on.
- **`seeded_sqlite_path` copies the real `data/express.db`:** Avoids re-seeding in tests (risk of test/prod drift) while still giving each test an isolated mutable copy via `tmp_path`.
- **pyproject.toml filter for google.* / pydantic.* DeprecationWarnings:** Environmental noise from Python 3.9 EOL notices and Pydantic v2 deprecations in transitive deps — not our code. Filtering keeps the test output actionable without hiding real warnings.

## Deviations from Plan

None - plan executed exactly as written. All three tasks completed per the specified actions and acceptance criteria.

**Note on verify-script compatibility:** The plan's Task-2 one-liner verify used `hints['reasoning_trace'] == Annotated[list[dict], operator.add] or 'operator.add' in repr(hints['reasoning_trace'])`. On Python 3.9.6 (this repo's current interpreter), `list[dict]` is not equal to `typing.List[dict]`, and `repr(operator.add)` renders as `<built-in function add>` rather than the literal string `operator.add`, so that exact assertion reports AssertionError even though the reducer is correctly installed. This is a script-expression artifact; the equivalent structural check (`operator.add in typing.get_args(hint)`) passes, and LangGraph's own reducer introspection reads the metadata via `get_args`, so runtime behaviour is correct. No code change needed; noted here so downstream tasks don't re-investigate.

**Total deviations:** 0 auto-fixes
**Impact on plan:** No scope creep; plan was complete and accurate.

## Issues Encountered

- **pip warning during install:** Pip version 21.2.4 recommended upgrade to 26.0.1, and `googlemaps==4.10.0` used legacy `setup.py install` instead of a wheel (package-side issue). Install succeeded regardless; noted but not acted on — tightening venv pip is out of scope for this plan.
- **Python 3.9 EOL warnings from google.* and pydantic.*:** Solved by `pyproject.toml` filterwarnings (part of Task 2).

## User Setup Required

None - no external service configuration required. The Phase 2 env vars (`GEMINI_MODEL`, `FUEL_FETCH_TIMEOUT`, `ROUTE_CACHE_TTL_SECONDS`, `TRAFFIC_RATIO_BUCKETS`) all have sensible defaults in `backend/config.py`. `GOOGLE_MAPS_API_KEY` and `GOOGLE_API_KEY` remain set via `.env` by the developer (no change to Phase 1 setup).

## Next Phase Readiness

- **Plans 02-02, 02-03, 02-04, 02-05 unblocked:** All prerequisite fixtures, deps, and reducer fix are in place. Plans can run in parallel waves as planned.
- **TOOL-01 (Fuel Agent, Plan 02-02):** `eppo_html_fixture`, `pytest-httpx`, `httpx`, `FUEL_FETCH_TIMEOUT`, and FuelData source docstring all ready.
- **TOOL-02 (Route Agent, Plan 02-03):** `gmaps_directions_fixture`, `gmaps_geocode_*_fixture`, `googlemaps` lib, `ROUTE_CACHE_TTL_SECONDS`, `TRAFFIC_RATIO_BUCKETS` all ready.
- **TOOL-03 (Pricing Agent, Plan 02-04):** `seeded_sqlite_path` fixture ready for rate-table lookup tests.
- **ORCH-02/ORCH-03 (Plan 02-05):** `sample_agent_state` fixture + `operator.add` reducer ready for node & graph tests.
- **No blockers** - Phase 1 regression clean, all deps importable.

## Self-Check: PASSED

- requirements.txt updated with 7 Phase 2 pins: FOUND
- backend/config.py GEMINI_MODEL/FUEL_FETCH_TIMEOUT/ROUTE_CACHE_TTL_SECONDS/TRAFFIC_RATIO_BUCKETS: FOUND
- .env.example GEMINI_MODEL=gemini-2.0-flash: FOUND
- backend/agent/state.py Annotated[List[dict], operator.add]: FOUND
- backend/agent/tools/models.py eppo_live/eppo_cached_csv/hardcoded_baseline: FOUND
- pyproject.toml with testpaths: FOUND
- backend/tests/conftest.py with 7 fixtures: FOUND
- 5 fixture files in backend/tests/fixtures/: FOUND
- Phase 1 regression 35/35 green: PASSED
- Task 1 commit 5c961fe: FOUND
- Task 2 commit ac48832: FOUND
- Task 3 commit 3cf1e92: FOUND

---
*Phase: 02-tools-agent-nodes*
*Completed: 2026-04-18*
