---
name: Quick Task 260509-eum Context
description: Locked decisions for backend cold-start fuel-price refresh
type: quick-task-context
---

# Quick Task 260509-eum: Backend Cold-Start Fuel-Price Refresh - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Task Boundary

Add a cold-start hook to the FastAPI backend (`backend/api/main.py` lifespan) that auto-refreshes `data/raw/eppo_diesel_prices.csv` when it is stale. The existing CLI script `data/scripts/fetch_fuel_prices.py` (and its `_scrape_eppo` / `_load_seed_csv` helpers) is the reuse target — DO NOT duplicate the scrape logic. Manual `python data/scripts/fetch_fuel_prices.py` invocation must continue to work unchanged.

**Out of scope:**
- Cron / launchd / GitHub Actions scheduling.
- Changing the fuel-prices API endpoint contract.
- Front-end changes (the chart is already wired; refreshing the CSV is enough).
- Touching the rate table or checkpoint databases.

</domain>

<decisions>
## Implementation Decisions

### Staleness threshold (D-01)
- Trigger refresh when the **latest `date` row in the CSV is older than today** (i.e. `max(date) < today`, in the project's timezone — Asia/Bangkok).
- Concretely: at most one refresh per calendar day; reboots within the same day after a successful fetch are no-ops.
- The "today" comparison must be timezone-aware (or use a stable UTC date fallback) — never naive `date.today()` if the host is offline UTC vs. Bangkok (+07).

### Startup behavior (D-02)
- Refresh runs as a **background asyncio task** (e.g. `asyncio.create_task(...)` inside the lifespan).
- The lifespan must NOT `await` the refresh — the API begins accepting traffic immediately.
- Implementation must wrap the synchronous `_scrape_eppo` (which uses blocking `requests`) in `asyncio.to_thread(...)` so the event loop is never blocked.

### Failure behavior (D-03)
- On any exception during the refresh: **log a warning and continue**. Existing CSV stays untouched; the dashboard renders last-known data. No retry, no alerting, no startup failure.
- Reuse the script's existing try/except contract — `main()` already catches and logs; the cold-start path should match that semantic.

### Claude's Discretion
- Exact module location for the cold-start helper (likely a new `backend/api/startup_tasks.py` or inline in `main.py.lifespan` — pick whichever keeps `main.py` readable).
- Function naming (e.g. `refresh_fuel_prices_if_stale()` or similar) — must be self-documenting.
- Whether to expose a feature flag / env var to disable cold-start refresh in tests (e.g. `EXPRESS_SKIP_COLDSTART_REFRESH=1`) — recommended so the test suite isn't slowed by network attempts. Default behavior in production: enabled.
- Whether to refactor `fetch_fuel_prices.py:main` into a reusable function (e.g. `refresh_csv() -> bool`) or just import its private helpers (`_scrape_eppo`, `_load_seed_csv`). Mild refactor preferred to keep one source of truth, as long as the CLI usage `python data/scripts/fetch_fuel_prices.py` still works.
- Logging format / log level (info on success, warning on failure) — follow existing `backend/api/main.py` `logger.info(...)` style.
- Test approach (unit test the staleness predicate + mock the network call; do not hit EPPO in CI).

</decisions>

<specifics>
## Specific Ideas

- Backend stack: FastAPI + asynccontextmanager `lifespan` already exists at [backend/api/main.py:28-41](backend/api/main.py#L28-L41) — that's the integration point.
- Existing fetcher: [data/scripts/fetch_fuel_prices.py](data/scripts/fetch_fuel_prices.py) — `_scrape_eppo()`, `_load_seed_csv()`, `main()`. The script already has the EPPO-fail → seed-fallback contract; cold-start should preserve it.
- CSV path: `data/raw/eppo_diesel_prices.csv`, defined as `OUTPUT_PATH` in the script. The cold-start helper should not hardcode the path — import it from the script module.
- Today's date: 2026-05-09. Latest CSV row is 2026-04-03 — so first cold-start with this change will trigger a real fetch attempt (which will likely fall through to the seed CSV no-op unless EPPO is reachable). That's expected behavior given D-03.

</specifics>

<canonical_refs>
## Canonical References

No external specs. Decisions above are the contract.

</canonical_refs>
