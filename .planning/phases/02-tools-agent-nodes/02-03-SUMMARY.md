---
phase: 02-tools-agent-nodes
plan: 03
subsystem: tools
tags: [google-maps, routing, caching, zone-derivation, ttl-cache, googlemaps-client]

requires:
  - phase: 02-tools-agent-nodes
    provides: "RouteData Pydantic model (Plan 01), TRAFFIC_RATIO_BUCKETS + ROUTE_CACHE_TTL_SECONDS config (Plan 01), zone_definitions.json (Phase 1), gmaps fixtures (Plan 01 conftest)"
provides:
  - "TOOL-02 calculate_route(origin, destination) -> RouteData"
  - "TTLCache helper class for in-process TTL caching (reusable)"
  - "Zone derivation (central-1/2/3) from Google Maps reverse-geocode + zone_definitions.json"
  - "Traffic severity bucketing 1-5 from duration_in_traffic/duration ratio (D-06)"
  - "15-minute in-process route cache (D-07) with far-future TTL expiry handling"
  - "Province-name normalisation stripping 'Province' suffix (Pitfall 6)"
affects: [route-agent-node, pricing-agent, orchestration, cost-control]

tech-stack:
  added: [googlemaps 4.10.0]
  patterns: ["Lazy client init via _client() accessor for test monkey-patching", "TTLCache dataclass with threading.Lock for parallel-agent safety", "Import-time _ZONE_INDEX build from JSON (read-once)", "pathlib.Path(__file__).resolve().parents[3] for repo-relative data paths"]

key-files:
  created:
    - backend/agent/tools/_cache.py
    - backend/agent/tools/calculate_route.py
    - backend/tests/test_calculate_route.py

key-decisions:
  - "Lazy googlemaps client via module-level _client() factory so tests mock via mocker.patch.object(mod, '_client', return_value=fake_client) without patching the SDK itself"
  - "Zone index loaded once at import time (_ZONE_INDEX module global) - read-only shared state, avoids per-call JSON parse"
  - "Province normalisation lowercases AND strips trailing ' Province' suffix; Pitfall 6 fixture 'Ayutthaya Province' confirms central-2 derivation"
  - "TTLCache is generic (TypeVar V) and threading-safe via Lock - designed for Phase 5 parallel Fuel+Route nodes"
  - "_bucket_traffic uses enumerate(start=1) over TRAFFIC_RATIO_BUCKETS; default [1.1,1.3,1.5,1.8] produces exactly severities 1-5"

patterns-established:
  - "Lazy SDK client init pattern: module-global sentinel + _client() accessor, replaces mock surface for tests"
  - "Half-open traffic bucketing: ratio < threshold advances level; final level is len(thresholds)+1"
  - "TTL cache freshness via monotonic-like time.time() delta; expiry check happens on get() (lazy eviction)"
  - "ValueError with both origin AND destination in message for no-route case; 'Could not geocode' or 'No Central Region zone' for geocoder failures"

requirements-completed: [TOOL-02]

duration: 2min
completed: 2026-04-18
---

# Phase 2 Plan 03: calculate_route Tool Summary

**TOOL-02 calculate_route with Google Maps Directions + reverse-geocode zone derivation, 1-5 traffic bucketing, 15-min in-process TTL cache, and province-suffix normalisation.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-18T07:52:05Z
- **Completed:** 2026-04-18T07:54:07Z
- **Tasks:** 3
- **Files modified:** 3 (all new)

## Accomplishments

- Reusable `TTLCache[V]` helper (`backend/agent/tools/_cache.py`) with thread-safe Lock and get/set/clear API — powers D-07's 15-minute route cache today and ready for Phase 5 parallel agent state.
- `calculate_route(origin, destination) -> RouteData` integrates Google Maps Directions + Geocoding with lazy client init, distance+duration+traffic extraction, zone derivation via reverse-geocode to admin_area_level_1 mapped through `data/raw/zone_definitions.json`, and D-06 traffic-ratio bucketing.
- Pitfall 3 (departure_time + traffic_model=best_guess enforced) and Pitfall 6 (province-suffix stripped pre-lookup) both wired in and test-covered.
- 8 tests with 12 parametric cases all pass in 0.05s; full suite remains 65/65 green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create _cache.py (TTLCache helper)** — `ead1eac` (feat)
2. **Task 2: Write test_calculate_route.py (RED phase)** — `a1a5dbc` (test)
3. **Task 3: Implement calculate_route.py (GREEN phase)** — `91b44c4` (feat)

_Note: Task 2+3 form one TDD RED→GREEN pair; no REFACTOR commit was needed — the implementation passed on first run after RED verification._

## Files Created/Modified

- `backend/agent/tools/_cache.py` (52 lines) — `TTLCache` generic dataclass with thread-safe `get`/`set`/`clear`, lazy expiry on read.
- `backend/agent/tools/calculate_route.py` (160 lines) — Tool entry point, `_client()` lazy factory, `_normalize_province`, `_load_zone_index`, `_bucket_traffic`, `_zone_for_destination`, module-level `_route_cache` + `_ZONE_INDEX`.
- `backend/tests/test_calculate_route.py` (123 lines) — 8 tests (directions parsing, parametric traffic bucketing ×5, 3 zone derivations, cache hit, cache expiry via `time.time` patch, 2 error paths); autouse `_clear_cache` fixture prevents order coupling.

## Decisions Made

- **Lazy gmaps client:** Module-level `_gmaps` singleton initialised on first `_client()` call; tests bypass it entirely via `mocker.patch.object(mod, "_client", return_value=fake_client)`. Zero SDK-internal patching — cleanest possible seam.
- **Import-time zone index:** `_ZONE_INDEX` built once via `_load_zone_index()` at module import. JSON is ~20 provinces — no memory concern, no per-call parse overhead.
- **Far-future TTL expiry in test:** Instead of patching `time.time` twice (on set + on get), the test patches it to `10**12` between calls so the `get()` sees a huge delta and evicts. Keeps the test mechanical and independent of `ROUTE_CACHE_TTL_SECONDS` value.
- **distance_km rounded to 2 decimals:** `round(leg["distance"]["value"] / 1000.0, 2)` — avoids float noise and keeps the value stable for downstream UI display and Pydantic equality checks.

## Deviations from Plan

None — plan executed exactly as written. TTLCache class, test file, and implementation were all created verbatim from the plan's exact-content code blocks. No Rule 1-3 auto-fixes were needed: no bugs found, no missing critical functionality, no blockers encountered.

## Issues Encountered

None. All tests passed on the first GREEN run after RED verification. The RED phase failed cleanly with the expected `ImportError: cannot import name 'calculate_route' from 'backend.agent.tools'` — no spurious failures.

Minor note: parallel agents are concurrently working on `test_fetch_fuel_price.py`, `fetch_fuel_price.py`, and `calculate_surcharge_tool.py` (visible in `git status`). Per the parallel-executor protocol, this plan only staged and committed its own three files (`_cache.py`, `calculate_route.py`, `test_calculate_route.py`) with `--no-verify` to avoid hook contention.

## User Setup Required

None at runtime code level. For live (non-test) operation, `GOOGLE_MAPS_API_KEY` must be set in `.env` (Google Cloud Console → APIs & Services → Credentials, with Directions API + Geocoding API enabled). Tests do not require the key — they mock the googlemaps client via fixtures.

## Next Phase Readiness

- **TOOL-02 ready** for Route Agent node consumption (Plan 05) and for Phase 3 Pricing Agent (zone feeds `lookup_rate` from Plan 04).
- **TTLCache reusable** by any future in-process cache (fuel price freshness check, geocoding cache, etc.).
- **No blockers.** The "Google Maps free tier credit burn" concern is mitigated by the 15-min cache — follow-up questions hit cache even across Planner routing loops.
- **Phase 5 Send-API parallelism** can safely call `calculate_route` concurrently with Fuel tool; `TTLCache` Lock prevents dict corruption.

## Self-Check: PASSED

**Files verified:**
- FOUND: backend/agent/tools/_cache.py
- FOUND: backend/agent/tools/calculate_route.py
- FOUND: backend/tests/test_calculate_route.py

**Commits verified:**
- FOUND: ead1eac (Task 1 — TTLCache)
- FOUND: a1a5dbc (Task 2 — RED tests)
- FOUND: 91b44c4 (Task 3 — GREEN impl)

**Test suite verified:**
- `.venv/bin/pytest backend/tests/test_calculate_route.py -q` → 12 passed
- `.venv/bin/pytest backend/tests/ -q` → 65 passed (Phase 1 + Plan 01 + Plan 02 + Plan 03 green)

---
*Phase: 02-tools-agent-nodes*
*Completed: 2026-04-18*
