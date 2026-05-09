---
phase: quick-260509-eum
plan: 01
subsystem: backend-startup
tags: [backend, lifespan, fuel-data, observability]
requirements:
  - QUICK-260509-EUM-01  # cold-start refresh trigger (D-01 staleness predicate)
  - QUICK-260509-EUM-02  # background, non-blocking lifespan integration (D-02)
  - QUICK-260509-EUM-03  # log-and-continue failure semantic (D-03)
dependency_graph:
  requires:
    - data/scripts/fetch_fuel_prices.py (existing _scrape_eppo, _load_seed_csv, OUTPUT_PATH)
    - backend/api/main.py lifespan (Phase 3 AsyncSqliteSaver wiring)
    - Python 3.11+ stdlib zoneinfo (already in project pin)
  provides:
    - is_csv_stale(csv_path, today) -- timezone-aware staleness predicate
    - refresh_csv(today) -- skip-if-fresh / scrape-and-write / log-and-continue
    - EXPRESS_SKIP_COLDSTART_REFRESH config flag
    - app.state.coldstart_refresh_task lifespan task handle
  affects:
    - data/raw/eppo_diesel_prices.csv (auto-refreshed on cold start when stale)
    - GET /api/fuel-prices (now serves fresh data without manual fetcher run)
tech-stack:
  added: []  # zoneinfo is stdlib; no new pip deps
  patterns:
    - Background task scheduling via asyncio.create_task held on app.state for GC safety
    - asyncio.to_thread shunt for blocking requests.get inside async lifespan
    - Module-level _today_bangkok seam for testable timezone-aware clock
    - Cross-package import via sys.path-prepended REPO_ROOT (deliberate reuse of CLI script)
key-files:
  created:
    - backend/tests/test_coldstart_fuel_refresh.py (12 tests; 0.6s runtime; offline)
  modified:
    - data/scripts/fetch_fuel_prices.py (+is_csv_stale, +refresh_csv, +_today_bangkok, +BANGKOK_TZ; main/_scrape_eppo/_load_seed_csv unchanged)
    - backend/api/main.py (+_coldstart_fuel_refresh helper, +lifespan scheduling, +sys.path-prepended import of refresh_csv)
    - backend/config.py (+EXPRESS_SKIP_COLDSTART_REFRESH bool flag)
    - .planning/STATE.md (+260509-eum row in Quick Tasks Completed; last_updated bumped)
decisions:
  - D-01 honored: staleness predicate is Asia/Bangkok timezone-aware via _today_bangkok seam; strict max(date) < today (boundary equality NOT stale; future dates NOT stale -- clock skew safe)
  - D-02 honored: refresh runs as background asyncio.create_task scheduled BEFORE lifespan yields; held on app.state.coldstart_refresh_task for GC safety; synchronous requests.get shunted via asyncio.to_thread so event loop is never blocked
  - D-03 honored: refresh_csv catches all _scrape_eppo exceptions internally and logs WARNING + returns False without overwriting CSV; _coldstart_fuel_refresh adds outer try/except as belt-and-braces against asyncio scheduling errors
  - EXPRESS_SKIP_COLDSTART_REFRESH=1 confirmed effective end-to-end (no thread spawned, no network attempt, /health 200, app.state.coldstart_refresh_task is None)
  - CLI seed-fallback semantic deliberately NOT moved into refresh_csv -- it belongs to main() (the "give me a CSV no matter what" entry); cold-start contract is "refresh if you can, otherwise leave the existing CSV alone"
metrics:
  start: "2026-05-09T03:47:57Z"
  end: "2026-05-09T03:55:30Z"
  duration_minutes: 7.5
  tasks_completed: 3
  files_created: 1
  files_modified: 4
  tests_added: 12
  total_tests_passing: 248
---

# Quick Task 260509-eum: Backend Cold-Start Fuel-Price Refresh Summary

Auto-refresh `data/raw/eppo_diesel_prices.csv` when stale on FastAPI startup, in the background, with log-and-continue failure semantics — eliminates the "stale dashboard" demo failure mode without requiring a manual `python data/scripts/fetch_fuel_prices.py` run before every demo. Reuses the existing fetcher (`_scrape_eppo`); zero scrape-logic duplication.

## What Was Built

**Three coordinated changes layered atop the existing fetcher and lifespan:**

1. **`data/scripts/fetch_fuel_prices.py`** — Two new exports next to the existing CLI:
   - `is_csv_stale(csv_path, today)` — strict `max(date) < today` predicate; returns True on missing/empty/corrupt CSV (forces refresh attempt) and on stale data; returns False on boundary equality and future dates (clock-skew safe). Uses `_today_bangkok()` (Asia/Bangkok via stdlib zoneinfo) when `today` is None.
   - `refresh_csv(today)` — skip-if-fresh / scrape-and-write / log-and-continue wrapper around `_scrape_eppo`. NEVER falls back to seed; on any failure leaves the existing CSV byte-for-byte unchanged so the dashboard renders last-known data (D-03).
   - Existing `main()`, `_scrape_eppo`, `_load_seed_csv`, `OUTPUT_PATH`, `SEED_PATH` symbols are PRESERVED — the 8 tests in `test_fuel_prices.py` still pass and `python data/scripts/fetch_fuel_prices.py` continues to print "Fetched N rows from EPPO" or "Using seed CSV fallback (N rows)" with exit code 0.

2. **`backend/config.py`** — `EXPRESS_SKIP_COLDSTART_REFRESH: bool` env flag (truthy values `"1"`, `"true"`, `"yes"`, `"on"`, case-insensitive; default False). Tests and CI use this to opt out of the network attempt.

3. **`backend/api/main.py`** — Cross-package import of `refresh_csv` (aliased `refresh_fuel_csv`) via sys.path-prepended REPO_ROOT; private async helper `_coldstart_fuel_refresh` shells the synchronous refresh through `asyncio.to_thread` (D-02 — `requests.get` cannot block the event loop); lifespan schedules via `asyncio.create_task` BEFORE `yield`, holds the task on `app.state.coldstart_refresh_task` to prevent GC mid-flight (per asyncio docs), then yields immediately so the API begins accepting traffic. When `EXPRESS_SKIP_COLDSTART_REFRESH` is set the task slot is None and an info log is emitted — no thread is spawned.

## Tests Added (12 in one new file)

`backend/tests/test_coldstart_fuel_refresh.py` — runs in 0.6s, offline:

**`TestIsCsvStale` (6 tests):** stale-when-older / fresh-when-equal (boundary) / fresh-when-future (clock skew) / stale-when-missing / stale-when-empty-or-corrupt / Bangkok-tz seam exercised when `today=None`.

**`TestRefreshCsv` (3 tests):** skip-and-return-False-when-fresh (`_scrape_eppo` MUST NOT be called) / write-and-return-True-when-stale-and-scrape-succeeds (file content asserted) / return-False-and-leave-csv-untouched-when-scrape-raises (byte-level read-before/read-after assertion + WARNING log assertion).

**Lifespan integration (3 tests):** schedules-as-background-task-by-default (`/health` 200 INSIDE the lifespan, then loop driven via subsequent client.get until `task.done()`, asserts `task.exception() is None` and stub called exactly once) / skips-when-env-flag-set (no task slot, stub never called) / swallows-refresh-exception (outer net captures the raise, WARNING logged, no exception propagates).

## Manual Smoke (Task 3)

```
$ .venv/bin/python -c "from datetime import date; ..."
is_stale (real CSV, today=2026-05-09): True
is_stale (real CSV, today=2026-04-03): False

$ .venv/bin/python data/scripts/fetch_fuel_prices.py
EPPO scrape failed: 404 Client Error: Component not found. ...
Using seed CSV fallback (185 rows)
exit=0

$ EXPRESS_SKIP_COLDSTART_REFRESH=1 .venv/bin/python -c "..."
health: 200 {'status': 'ok', 'graph_ready': True}
coldstart_refresh_task: None
```

Full suite: **248/248 backend tests green** both with and without `EXPRESS_SKIP_COLDSTART_REFRESH=1` (default-on path is ~5s slower because background scrape attempts run, but log-and-continue means none of them break a test).

## Acceptance Gates

| # | Gate | Status |
|---|------|--------|
| 1 | Staleness predicate (D-01 boundary) | PASS — TestIsCsvStale 6/6 |
| 2 | Non-blocking lifespan (D-02) | PASS — `/health` returns 200 inside lifespan before background task completes |
| 3 | Failure tolerance (D-03 log-and-continue) | PASS — refresh_csv inner + _coldstart_fuel_refresh outer net both verified |
| 4 | CLI preservation | PASS — `python data/scripts/fetch_fuel_prices.py` exit 0, prints expected status |
| 5 | Skip flag effective end-to-end | PASS — Task 3 smoke step 3 + lifespan unit test |
| 6 | Reuse gate (no logic duplication) | PASS — `grep EPPO_URL\|_scrape_eppo BeautifulSoup backend/` returns only test-side monkeypatch refs and the pre-existing `_scrape_eppo_live` (different function in `backend/agent/tools/fetch_fuel_price.py`, untouched by this task) |
| 7 | No-network gate | PASS — all 12 new tests run offline; EXPRESS_SKIP_COLDSTART_REFRESH=1 disables lifespan scrape too |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Test fixture leaked CHECKPOINT_PATH and EXPRESS_SKIP_COLDSTART_REFRESH into later tests**
- **Found during:** Task 3 smoke step 4 (full backend suite under `EXPRESS_SKIP_COLDSTART_REFRESH=1`)
- **Issue:** Two leak vectors: (a) `app_with_stub_refresh` reloaded `backend.config` without first delenv'ing `EXPRESS_SKIP_COLDSTART_REFRESH`, so when CI runs the suite with the flag set, the "default-on" test reloaded into "default-off" branch and saw a None task slot (`assert task is not None` failed). (b) Both fixture and standalone test left CHECKPOINT_PATH monkeypatched in the cached config module, polluting `test_models.TestConfig.test_checkpoint_path_default` (it asserts `config.CHECKPOINT_PATH == "data/checkpoints.db"` literal).
- **Fix:** Defensive delenv inside the fixture before reload + assert post-reload that the flag is False. Mirrored `test_api_chat.py`'s teardown pattern: `monkeypatch.delenv("CHECKPOINT_PATH") + reload(_cfg) + reload(_main)` after yield (and in `try/finally` for the standalone skip test).
- **Files modified:** `backend/tests/test_coldstart_fuel_refresh.py`
- **Commit:** `5220292`

**2. [Rule 1 — Bug] First version of lifespan integration tests used `asyncio.run(asyncio.wait_for(task, timeout))` to wait for the background task, which raised `ValueError: The future belongs to a different loop`**
- **Found during:** Task 2 GREEN phase
- **Issue:** TestClient runs the lifespan (and thus our `asyncio.create_task`) on its own event loop. A fresh `asyncio.run` from the test creates a different loop and cannot await a task that lives on the TestClient loop.
- **Fix:** Replace `asyncio.run(_wait())` with a bounded loop of `client.get('/health')` calls — each subsequent request drives the TestClient loop forward, giving the scheduled task an opportunity to run. After exiting the `with TestClient(...)` block, assert `task.done()` and `task.exception() is None`.
- **Files modified:** `backend/tests/test_coldstart_fuel_refresh.py` (in-flight, never reached the first commit)

No architectural deviations. No Rule 4 escalations.

## Decisions Made (Beyond Plan)

- **CLI seed-fallback NOT moved into `refresh_csv`** — explicitly kept in `main()`. The cold-start contract per D-03 is "refresh if you can, otherwise leave the existing CSV alone"; the CLI's "give me a CSV no matter what" semantic is a different responsibility and conflating them would risk overwriting a fresh production CSV with the older seed on transient EPPO outages.
- **Outer `try/except` in `_coldstart_fuel_refresh` despite `refresh_csv` already swallowing internal errors** — belt-and-braces against `asyncio.to_thread` / scheduling-layer failures. Marked `# pragma: no cover` was considered but dropped because dropping the `pragma` keeps the failure-tolerance gate auditable in coverage reports.
- **`app.state.coldstart_refresh_task = None` in the skip branch** (not just absent) — gives tests a stable attribute to assert against (`assert app.state.coldstart_refresh_task is None`) and is more Pythonic than `getattr(...) is None` everywhere.

## Commits

| # | Task | SHA | Subject |
|---|------|-----|---------|
| 1 | Task 1 RED | `78ee806` | test(260509-eum): add failing tests for is_csv_stale + refresh_csv + lifespan |
| 2 | Task 1 GREEN | `9accbd4` | feat(260509-eum): add is_csv_stale + refresh_csv to fetch_fuel_prices |
| 3 | Task 2 GREEN | `5f2ae94` | feat(260509-eum): wire cold-start fuel CSV refresh into FastAPI lifespan |
| 4 | Task 3 fix | `5220292` | fix(260509-eum): prevent test fixture env-var leak into later tests |
| 5 | Task 3 docs | `9bf5471` | docs(260509-eum): complete backend cold-start fuel-refresh quick task |

## Self-Check: PASSED

All 6 listed files exist on disk; all 4 task commits (78ee806, 9accbd4, 5f2ae94, 5220292) present in `git log --all`. Final docs commit hash will be filled in by the metadata commit that lands this file + the STATE.md update.
