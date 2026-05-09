---
phase: quick-260509-eum
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - data/scripts/fetch_fuel_prices.py
  - backend/api/main.py
  - backend/config.py
  - backend/tests/test_coldstart_fuel_refresh.py
autonomous: true
requirements:
  - QUICK-260509-EUM-01  # cold-start refresh trigger (D-01 staleness predicate)
  - QUICK-260509-EUM-02  # background, non-blocking lifespan integration (D-02)
  - QUICK-260509-EUM-03  # log-and-continue failure semantic (D-03)

must_haves:
  truths:
    - "On FastAPI startup, if data/raw/eppo_diesel_prices.csv max(date) < today (Asia/Bangkok), the existing _scrape_eppo logic is invoked in the background"
    - "The lifespan does NOT await the refresh — /health responds immediately while the refresh runs"
    - "Manual `python data/scripts/fetch_fuel_prices.py` continues to work unchanged"
    - "Any exception during the cold-start refresh is logged at WARNING and swallowed; the existing CSV is untouched"
    - "Setting EXPRESS_SKIP_COLDSTART_REFRESH=1 disables the cold-start path (used by tests / opt-out)"
    - "The staleness predicate is timezone-aware (Asia/Bangkok) and treats max(date) == today as fresh"
  artifacts:
    - path: "data/scripts/fetch_fuel_prices.py"
      provides: "is_csv_stale() predicate + refresh_csv() reusable function; CLI entry preserved"
      contains: "def is_csv_stale"
    - path: "backend/api/main.py"
      provides: "Cold-start hook scheduled via asyncio.create_task in lifespan"
      contains: "asyncio.create_task"
    - path: "backend/config.py"
      provides: "EXPRESS_SKIP_COLDSTART_REFRESH flag"
      contains: "EXPRESS_SKIP_COLDSTART_REFRESH"
    - path: "backend/tests/test_coldstart_fuel_refresh.py"
      provides: "Unit tests for staleness predicate + lifespan wiring smoke test (network mocked)"
      contains: "def test_is_csv_stale"
  key_links:
    - from: "backend/api/main.py:lifespan"
      to: "data/scripts/fetch_fuel_prices.refresh_csv"
      via: "asyncio.create_task(asyncio.to_thread(refresh_csv))"
      pattern: "asyncio\\.create_task"
    - from: "data/scripts/fetch_fuel_prices.refresh_csv"
      to: "_scrape_eppo + is_csv_stale"
      via: "early-return when fresh; reuse existing scrape on stale"
      pattern: "is_csv_stale"
---

<objective>
Add a backend cold-start hook that auto-refreshes `data/raw/eppo_diesel_prices.csv` when stale, so the dashboard always serves current fuel data without requiring a manual `python data/scripts/fetch_fuel_prices.py` run before every demo. Reuses the existing fetcher (`_scrape_eppo`, `_load_seed_csv`) — no scrape-logic duplication.

Purpose: Eliminate the "stale dashboard" failure mode in demos. The CSV is the single source of truth for `/api/fuel-prices`; staleness on cold start currently surfaces as silently-old chart data.

Output: A timezone-aware staleness predicate, a reusable `refresh_csv()` function, a non-blocking lifespan hook scheduled with `asyncio.create_task`, and unit tests that mock the network entirely.
</objective>

<execution_context>
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/workflows/execute-plan.md
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260509-eum-backend-cold-start-fuel-price-refresh-au/260509-eum-CONTEXT.md
@backend/api/main.py
@data/scripts/fetch_fuel_prices.py
@backend/config.py
@backend/api/routes/fuel_prices.py
@backend/tests/test_fuel_prices.py
@backend/tests/conftest.py

<interfaces>
<!-- Key contracts the executor needs. Extracted from current codebase. -->

From data/scripts/fetch_fuel_prices.py (existing, will be extended):
```python
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent
RAW_DIR = DATA_DIR / "raw"
OUTPUT_PATH = RAW_DIR / "eppo_diesel_prices.csv"   # canonical CSV path
SEED_PATH = RAW_DIR / "eppo_diesel_prices.csv"

def _scrape_eppo() -> pd.DataFrame: ...    # raises on any failure; returns date,diesel_b7_price,source
def _load_seed_csv() -> pd.DataFrame: ...  # never raises (assuming seed present)
def main() -> None: ...                    # CLI entry; try _scrape_eppo, on Exception fall back to seed
```

CSV row schema (from data/raw/eppo_diesel_prices.csv):
```
date,diesel_b7_price,source        # ISO YYYY-MM-DD, float, str
2026-04-03,31.62,eppo              # current latest row (today is 2026-05-09 -> stale)
```

From backend/api/main.py (existing lifespan — integration point):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(CHECKPOINT_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(CHECKPOINT_PATH)
    try:
        checkpointer = AsyncSqliteSaver(conn)
        await checkpointer.setup()
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer)
        logger.info("Graph compiled with AsyncSqliteSaver(%s)", CHECKPOINT_PATH)
        yield                                      # <-- cold-start hook fires BEFORE yield, non-awaited
    finally:
        await conn.close()
```

From backend/config.py (existing pattern for env-var reads):
```python
import os
from dotenv import load_dotenv
load_dotenv()
# Pattern: VAR: TYPE = TYPE(os.environ.get("VAR", "default"))
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extract reusable refresh_csv() + is_csv_stale() in fetch_fuel_prices.py</name>
  <files>data/scripts/fetch_fuel_prices.py, backend/tests/test_coldstart_fuel_refresh.py</files>
  <behavior>
    Test file `backend/tests/test_coldstart_fuel_refresh.py` (created in this task; extended in Task 3):

    Tests for `is_csv_stale(csv_path: Path, today: date | None = None) -> bool`:
      - test_is_csv_stale_returns_true_when_max_date_before_today: CSV with max(date)=2026-04-03, today=2026-05-09 -> True
      - test_is_csv_stale_returns_false_when_max_date_equals_today: CSV with max(date)=2026-05-09, today=2026-05-09 -> False (boundary; D-01 "older than today" means strict <)
      - test_is_csv_stale_returns_false_when_max_date_after_today: CSV with max(date)=2026-05-10, today=2026-05-09 -> False (clock skew safe)
      - test_is_csv_stale_returns_true_when_csv_missing: nonexistent path -> True (forces a refresh attempt; `_scrape_eppo`'s own try/except handles the rest per D-03)
      - test_is_csv_stale_returns_true_when_csv_empty_or_unparseable: file exists but no parseable date rows -> True
      - test_is_csv_stale_uses_bangkok_today_when_none_passed: monkeypatch the module's clock helper to return a fixed Bangkok date and assert the call path is exercised (proves NOT using naive date.today())

    Tests for `refresh_csv(today: date | None = None) -> bool`:
      - test_refresh_csv_returns_false_and_skips_scrape_when_fresh: stub `_scrape_eppo` to raise; if predicate says fresh, scrape must NOT be invoked -> returns False
      - test_refresh_csv_returns_true_and_writes_when_stale_and_scrape_succeeds: stub `_scrape_eppo` to return a synthetic 2-row DF; redirect OUTPUT_PATH to tmp_path; returns True; file contents match
      - test_refresh_csv_returns_false_when_scrape_raises: stub `_scrape_eppo` to raise; CSV must remain UNCHANGED (we read the bytes before/after); function returns False; no exception propagates (D-03 contract; refresh_csv is the wrapper main()'s old try/except now lives in)

    Existing tests in backend/tests/test_fuel_prices.py MUST still pass — `main()`, `_scrape_eppo`, `_load_seed_csv`, `OUTPUT_PATH`, `SEED_PATH` symbols all preserved.
  </behavior>
  <action>
    Refactor `data/scripts/fetch_fuel_prices.py` to add two new public functions WITHOUT removing or renaming any existing symbols (D-03 reuse contract; preserves the 8 tests in test_fuel_prices.py and the CLI entry point):

    1. Add `from datetime import date, datetime` and `from zoneinfo import ZoneInfo` (Python 3.11+ stdlib; project pins 3.11+ per CLAUDE.md).
    2. Add module constant `BANGKOK_TZ = ZoneInfo("Asia/Bangkok")`.
    3. Add private helper `_today_bangkok() -> date` that returns `datetime.now(BANGKOK_TZ).date()`. This is the seam tests monkeypatch.
    4. Add `def is_csv_stale(csv_path: Path = OUTPUT_PATH, today: date | None = None) -> bool`:
       - If `today is None`: `today = _today_bangkok()` (D-01 timezone-aware).
       - If `not csv_path.exists()`: return True.
       - Read CSV with pandas, parse `date` column with `pd.to_datetime(..., errors="coerce").dt.date`, drop NaT rows.
       - If empty after drop: return True.
       - Return `df["date"].max() < today` (strict `<` per D-01 boundary "older than today").
       - Wrap pandas read in try/except Exception → return True (corrupt CSV forces refresh attempt; the refresh itself has its own try/except per D-03).
    5. Add `def refresh_csv(today: date | None = None) -> bool`:
       - If `not is_csv_stale(OUTPUT_PATH, today)`: log info "Fuel CSV is fresh (max date >= today); skipping cold-start refresh"; return False.
       - Else: call `_scrape_eppo()` inside try/except Exception. On success: write to OUTPUT_PATH; log info "Cold-start fuel refresh: wrote N rows to <path>"; return True. On failure: log warning "Cold-start fuel refresh failed: %s; existing CSV untouched" with exc_info=True; return False (D-03 log-and-continue; CSV NOT overwritten with seed — current file is the last-known-good).
       - DO NOT call `_load_seed_csv()` here — the seed-fallback semantic belongs to the CLI `main()`, not the cold-start path. The cold-start contract is "refresh if you can, otherwise leave the existing CSV alone" (D-03).
    6. Leave `main()` and the `if __name__ == "__main__": main()` block UNCHANGED so `python data/scripts/fetch_fuel_prices.py` continues to work with its existing seed-fallback behaviour.

    Then create `backend/tests/test_coldstart_fuel_refresh.py` with the test cases enumerated in <behavior>. Load the script the same way `test_fuel_prices.py` does (importlib.util.spec_from_file_location pattern — copy the `_load_fetch_module()` helper) so we're testing the live module file. Mock `_scrape_eppo` via direct attr-set on the loaded module; mock the clock via `monkeypatch.setattr(module, "_today_bangkok", lambda: date(2026, 5, 9))`. NEVER hit the network — tests must pass with no internet.

    Why no zoneinfo fallback: project requires Python 3.11+ (CLAUDE.md "Python 3.11+"), and zoneinfo has been stdlib since 3.9. No `tzdata` pip dependency needed on macOS/Linux; if Windows support ever matters, `pip install tzdata` is documented elsewhere.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow &amp;&amp; .venv/bin/python -m pytest backend/tests/test_coldstart_fuel_refresh.py backend/tests/test_fuel_prices.py -x -v</automated>
  </verify>
  <done>
    - `is_csv_stale()` and `refresh_csv()` exported from `data/scripts/fetch_fuel_prices.py`
    - All new tests in `test_coldstart_fuel_refresh.py` pass
    - All 8 existing tests in `test_fuel_prices.py` still pass (no regression on `main()`, `_scrape_eppo`, `_load_seed_csv`, `OUTPUT_PATH`, `SEED_PATH`)
    - Manual smoke: `cd /Users/pollot/Desktop/express-dynamic-workflow && .venv/bin/python data/scripts/fetch_fuel_prices.py` runs without error and prints either "Fetched N rows from EPPO" or "Using seed CSV fallback (N rows)"
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire cold-start refresh into FastAPI lifespan (non-blocking, env-gated)</name>
  <files>backend/config.py, backend/api/main.py, backend/tests/test_coldstart_fuel_refresh.py</files>
  <behavior>
    Extend `backend/tests/test_coldstart_fuel_refresh.py` with lifespan integration tests:

    - test_lifespan_schedules_refresh_as_background_task_by_default:
      Use FastAPI TestClient context-manager to enter the lifespan with EXPRESS_SKIP_COLDSTART_REFRESH unset. Monkeypatch `data.scripts.fetch_fuel_prices.refresh_csv` (the symbol imported by main.py) with a recording stub that records its invocation. Assert: `/health` returns 200 inside the `with TestClient(app)` block (proves lifespan did NOT block on the refresh), and within a short bounded wait (e.g. wait_for(future, timeout=2.0)) the recording stub WAS called exactly once.

    - test_lifespan_skips_refresh_when_env_flag_set:
      Same setup but with monkeypatch.setenv("EXPRESS_SKIP_COLDSTART_REFRESH", "1") BEFORE importing/reloading config + main. The recording stub MUST NOT be called. /health still returns 200.

    - test_lifespan_swallows_refresh_exception:
      Set the recording stub to raise RuntimeError("simulated scrape blowup"). Lifespan must enter and exit cleanly; /health returns 200; an explicit assertion that the WARNING was logged (use caplog at WARNING level on logger 'backend.api.main' or wherever the cold-start helper lives) — D-03 log-and-continue.

    All three tests must complete in under 5 seconds total (no real network, no real scrape).
  </behavior>
  <action>
    1. Add to `backend/config.py` (append after the LANGFUSE block, follow the existing `os.environ.get(..., "default")` pattern):
       ```python
       # Quick 260509-eum: Cold-start fuel CSV refresh opt-out.
       # When set to a truthy value ("1","true","yes","on", case-insensitive),
       # the FastAPI lifespan skips the auto-refresh of
       # data/raw/eppo_diesel_prices.csv. Default behavior in production:
       # enabled (refresh runs in background on startup if CSV is stale).
       # Tests set this to "1" to avoid network attempts.
       EXPRESS_SKIP_COLDSTART_REFRESH: bool = os.environ.get(
           "EXPRESS_SKIP_COLDSTART_REFRESH", ""
       ).strip().lower() in {"1", "true", "yes", "on"}
       ```

    2. Modify `backend/api/main.py`:
       - Add imports near the top:
         ```python
         import asyncio
         import sys

         # Make data/scripts importable as a module. The script lives outside
         # the backend package, so we resolve REPO_ROOT and append it to
         # sys.path once at import time. This is a deliberate cross-package
         # reuse — the alternative (duplicating refresh_csv into backend/) is
         # ruled out by the quick-task constraint "DO NOT duplicate scrape
         # logic" and CONTEXT D-03 reuse contract.
         _REPO_ROOT = Path(__file__).resolve().parents[2]
         if str(_REPO_ROOT) not in sys.path:
             sys.path.insert(0, str(_REPO_ROOT))

         # Import after sys.path manipulation. Aliased so the symbol is
         # easy to monkeypatch in tests (`monkeypatch.setattr(
         # "backend.api.main.refresh_fuel_csv", stub)`).
         from data.scripts.fetch_fuel_prices import refresh_csv as refresh_fuel_csv  # noqa: E402
         ```
       - Add `EXPRESS_SKIP_COLDSTART_REFRESH` to the existing `from backend.config import ...` line.
       - Add a private async helper above `lifespan`:
         ```python
         async def _coldstart_fuel_refresh() -> None:
             """Run the blocking refresh_csv() in a worker thread.

             D-02: must not block the event loop -- asyncio.to_thread shunts
             the synchronous requests.get() call off the loop. D-03: any
             exception is logged and swallowed; the existing CSV is left
             untouched and the dashboard renders last-known data.
             """
             try:
                 refreshed = await asyncio.to_thread(refresh_fuel_csv)
                 if refreshed:
                     logger.info("Cold-start fuel CSV refresh: completed")
                 # When refreshed is False, refresh_csv has already logged
                 # the reason (fresh OR scrape failed) at the appropriate
                 # level; no extra log here.
             except Exception as exc:  # pragma: no cover -- defensive
                 # refresh_csv already swallows internal errors; this is the
                 # outer net for asyncio.to_thread / scheduling failures.
                 logger.warning(
                     "Cold-start fuel CSV refresh: scheduling error: %s",
                     exc,
                     exc_info=True,
                 )
         ```
       - Inside `lifespan`, AFTER `app.state.graph = build_graph(checkpointer)` and BEFORE `yield`, add:
         ```python
         if not EXPRESS_SKIP_COLDSTART_REFRESH:
             # D-02: schedule, do not await -- API begins accepting traffic immediately.
             # Hold a reference on app.state so GC cannot collect the task mid-flight
             # (asyncio docs: "Save a reference to the result of [create_task], to
             # avoid a task disappearing mid-execution.").
             app.state.coldstart_refresh_task = asyncio.create_task(
                 _coldstart_fuel_refresh()
             )
             logger.info("Cold-start fuel CSV refresh: scheduled in background")
         else:
             logger.info(
                 "Cold-start fuel CSV refresh: skipped "
                 "(EXPRESS_SKIP_COLDSTART_REFRESH set)"
             )
         ```

    3. Append the three lifespan integration tests from <behavior> to `backend/tests/test_coldstart_fuel_refresh.py`. Use this fixture pattern (copied from existing test_api_chat.py / test_api_fuel_prices.py conventions in the repo):
       ```python
       from fastapi.testclient import TestClient
       from importlib import reload

       @pytest.fixture
       def app_with_stub_refresh(monkeypatch):
           """Reload backend.api.main with refresh_fuel_csv replaced by a stub.
           Yields (app, recording_stub) so tests can assert call count.
           """
           import backend.config as _cfg
           reload(_cfg)
           import backend.api.main as _main
           reload(_main)
           calls = []
           def stub(*args, **kwargs):
               calls.append(("call", args, kwargs))
               return True
           monkeypatch.setattr(_main, "refresh_fuel_csv", stub)
           return _main.app, calls
       ```
       For the "raises" test, set the stub to `lambda: (_ for _ in ()).throw(RuntimeError("..."))`. Use `caplog.at_level(logging.WARNING, logger="backend.api.main")` to capture the warning. Wait briefly for the background task to complete — `await asyncio.sleep(0.1)` inside an async test, OR use `app.state.coldstart_refresh_task` directly: `asyncio.run(asyncio.wait_for(app.state.coldstart_refresh_task, timeout=2.0))` after exiting the TestClient context.

    Logging: All log lines from the cold-start path go through the existing module-level `logger = logging.getLogger(__name__)` in main.py — no new logger configuration needed (matches the established style in main.py per CONTEXT discretion).

    Why import via `from data.scripts.fetch_fuel_prices import refresh_csv as refresh_fuel_csv`: the script directory is not currently on PYTHONPATH (it's a CLI script, not a package). The sys.path append at module import time keeps the import explicit and tests can verify the symbol via `backend.api.main.refresh_fuel_csv`. Alternative considered and rejected: importlib.util.spec_from_file_location at lifespan startup time — adds runtime cost to every cold-start with no benefit.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow &amp;&amp; .venv/bin/python -m pytest backend/tests/test_coldstart_fuel_refresh.py backend/tests/test_fuel_prices.py backend/tests/test_api_fuel_prices.py -x -v</automated>
  </verify>
  <done>
    - `EXPRESS_SKIP_COLDSTART_REFRESH` exported from `backend/config.py`
    - `backend/api/main.py` imports `refresh_csv as refresh_fuel_csv`, schedules `_coldstart_fuel_refresh()` via `asyncio.create_task` inside `lifespan` (post-graph-build, pre-yield), gated on `EXPRESS_SKIP_COLDSTART_REFRESH`
    - `app.state.coldstart_refresh_task` holds the task reference (GC safety)
    - All three new lifespan integration tests pass; tests in `test_api_fuel_prices.py` (existing API contract) still pass
    - `backend/tests/test_coldstart_fuel_refresh.py` total runtime under 5 seconds
  </done>
</task>

<task type="auto">
  <name>Task 3: End-to-end smoke + manual CLI regression check + update STATE.md</name>
  <files>.planning/STATE.md</files>
  <action>
    Smoke verification (no new code; runs the integration end-to-end against the real CSV without hitting EPPO):

    1. Confirm the staleness predicate fires for the current real CSV (today=2026-05-09, latest row=2026-04-03):
       ```bash
       cd /Users/pollot/Desktop/express-dynamic-workflow
       .venv/bin/python -c "
       from datetime import date
       import sys, importlib.util
       spec = importlib.util.spec_from_file_location('f', 'data/scripts/fetch_fuel_prices.py')
       m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
       print('is_stale (real CSV, today=2026-05-09):', m.is_csv_stale(today=date(2026,5,9)))
       print('is_stale (real CSV, today=2026-04-03):', m.is_csv_stale(today=date(2026,4,3)))
       "
       ```
       Expected: True, then False.

    2. Confirm the CLI entry point still works (DOES hit EPPO if reachable; either branch is acceptable per the existing `main()` contract):
       ```bash
       cd /Users/pollot/Desktop/express-dynamic-workflow
       .venv/bin/python data/scripts/fetch_fuel_prices.py
       ```
       Expected: prints either "Fetched N rows from EPPO -> ..." OR "Using seed CSV fallback (N rows)". Exit code 0. Does NOT raise.

    3. Confirm cold-start hook scheduling without ever firing the scrape (env flag opt-out):
       ```bash
       cd /Users/pollot/Desktop/express-dynamic-workflow
       EXPRESS_SKIP_COLDSTART_REFRESH=1 .venv/bin/python -c "
       from fastapi.testclient import TestClient
       from backend.api.main import app
       with TestClient(app) as c:
           r = c.get('/health'); print('health:', r.status_code, r.json())
       "
       ```
       Expected: status 200, json `{"status":"ok","graph_ready":true}`, no network calls (logs include "Cold-start fuel CSV refresh: skipped").

    4. Run the FULL backend test suite to confirm zero regression on the existing 200+ tests:
       ```bash
       cd /Users/pollot/Desktop/express-dynamic-workflow
       .venv/bin/python -m pytest backend/tests/ -x -q
       ```
       Expected: every previously-passing test still passes; new test file adds the cases from Tasks 1+2 (~10 tests).

    5. Update `.planning/STATE.md` Quick Tasks Completed table — append a new row:
       ```
       | 260509-eum | Backend cold-start fuel-price refresh: lifespan schedules background asyncio task; reuses fetch_fuel_prices.refresh_csv with timezone-aware (Asia/Bangkok) staleness predicate; D-03 log-and-continue on any failure (QUICK-260509-EUM-01..03) | 2026-05-09 | <commit> | Verified | [260509-eum-backend-cold-start-fuel-price-refresh-au](./quick/260509-eum-backend-cold-start-fuel-price-refresh-au/) |
       ```
       (Replace `<commit>` with the actual commit short SHA after the user commits.)

    Update the `last_updated` and `last_activity` fields at the top of STATE.md to the current date.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow &amp;&amp; .venv/bin/python -m pytest backend/tests/ -x -q &amp;&amp; EXPRESS_SKIP_COLDSTART_REFRESH=1 .venv/bin/python -c "from fastapi.testclient import TestClient; from backend.api.main import app; c=TestClient(app); c.__enter__(); r=c.get('/health'); assert r.status_code==200 and r.json()['graph_ready'] is True; c.__exit__(None,None,None); print('OK')"</automated>
  </verify>
  <done>
    - All 5 smoke steps produce expected output
    - Full `pytest backend/tests/` passes with zero failures (no regressions)
    - `EXPRESS_SKIP_COLDSTART_REFRESH=1` flag confirmed effective end-to-end against the real lifespan
    - STATE.md updated with the new Quick Tasks Completed row + last_updated bumped to 2026-05-09
  </done>
</task>

</tasks>

<verification>
**Acceptance gates (every gate must hold to ship):**

1. **Staleness gate:** `is_csv_stale()` returns True iff `max(date) < today` in Asia/Bangkok; True on missing/empty/corrupt CSV; False on max(date) >= today. Verified by Task 1 unit tests.

2. **Non-blocking gate:** Inside the `with TestClient(app) as c:` block, `c.get("/health")` returns 200 BEFORE `refresh_fuel_csv` has been called or completed — the lifespan must yield without awaiting the refresh. Verified by Task 2 lifespan integration tests.

3. **Failure-tolerance gate:** When the refresh callable raises, the lifespan still enters and exits cleanly, /health returns 200, a WARNING log is emitted, and the existing CSV is untouched. Verified by Task 1 (`refresh_csv` swallow) + Task 2 (`_coldstart_fuel_refresh` outer net).

4. **CLI-preservation gate:** `python data/scripts/fetch_fuel_prices.py` continues to work with its existing seed-fallback behaviour (Task 3 smoke step 2). The 8 tests in `test_fuel_prices.py` continue to pass unchanged.

5. **Skip-flag gate:** `EXPRESS_SKIP_COLDSTART_REFRESH=1` causes the refresh to be skipped (no thread spawned, no scheduling log line). Verified by Task 2 + Task 3 smoke step 3.

6. **Reuse gate (no logic duplication):** `data/scripts/fetch_fuel_prices.py` remains the SOLE owner of `_scrape_eppo`. `backend/api/main.py` imports `refresh_csv` from it; nothing in the backend tree contains `requests.get(EPPO_URL...)` or `BeautifulSoup` parsing. Verified by `grep -r "EPPO_URL\|_scrape_eppo" backend/` returning ONLY `from data.scripts.fetch_fuel_prices import` lines.

7. **No-network gate:** Full test suite runs offline. CI never hits EPPO. Verified by all new tests using monkeypatched scrapers + the `EXPRESS_SKIP_COLDSTART_REFRESH=1` env when the lifespan is exercised.
</verification>

<success_criteria>
**Definition of done — all must be true:**

- [ ] `data/scripts/fetch_fuel_prices.py` exports `is_csv_stale()` and `refresh_csv()`; existing `main()`, `_scrape_eppo()`, `_load_seed_csv()`, `OUTPUT_PATH`, `SEED_PATH` symbols unchanged
- [ ] `python data/scripts/fetch_fuel_prices.py` continues to print "Fetched ... from EPPO" or "Using seed CSV fallback ..." with exit code 0
- [ ] `backend/config.py` exports `EXPRESS_SKIP_COLDSTART_REFRESH: bool`
- [ ] `backend/api/main.py` lifespan schedules `_coldstart_fuel_refresh()` via `asyncio.create_task(...)` (NOT `await`), gated on the env flag, with the task reference held on `app.state.coldstart_refresh_task`
- [ ] `_coldstart_fuel_refresh()` shells `refresh_fuel_csv` through `asyncio.to_thread(...)` so the synchronous `requests.get` cannot block the event loop
- [ ] `backend/tests/test_coldstart_fuel_refresh.py` has at least 9 tests (6 predicate + 3 wrapper from Task 1, 3 lifespan from Task 2) covering: stale=True, fresh=False, boundary equality, missing-CSV, corrupt-CSV, Bangkok-tz seam, scrape-skipped-when-fresh, scrape-success, scrape-failure-leaves-csv-intact, lifespan-schedules-by-default, lifespan-skips-on-flag, lifespan-swallows-exception
- [ ] `pytest backend/tests/` passes with zero failures end-to-end
- [ ] No new dependencies added to `requirements.txt` (zoneinfo is stdlib in Python 3.11+, which the project already pins)
- [ ] `.planning/STATE.md` Quick Tasks Completed table includes the 260509-eum row with status "Verified"
- [ ] All work committed to git on a single commit (or per-task commits) with descriptive message tying back to QUICK-260509-EUM-01..03
</success_criteria>

<output>
After completion, the orchestrator (or a SUMMARY-writing follow-up) should produce `.planning/quick/260509-eum-backend-cold-start-fuel-price-refresh-au/260509-eum-SUMMARY.md` documenting:
- Locked decisions honored (D-01 timezone-aware staleness, D-02 background asyncio + to_thread, D-03 log-and-continue)
- Files modified (4 listed in frontmatter)
- New tests added (count, file path)
- Manual CLI verified (Task 3 smoke step 2 output)
- Any deviations from the plan with rationale
- Commit SHA(s)
</output>
