# Data Sources

Provenance, refresh cadence, and assumptions for every external data
source the Express Dynamic Surcharge Orchestrator consumes. Bangkok
Metro is the single supported region (`central-1` / `central-2` /
`central-3` zones).

## EPPO Diesel B7 Historical Prices

- **Source:** Thailand Department of Energy Business — Energy Policy
  and Planning Office (EPPO).
  URL: https://www.eppo.go.th/index.php/en/petroleum-statistics/petroleum-data
- **Refresh cadence:** daily (manual or cron-driven) via
  `data/scripts/fetch_fuel_prices.py`.
- **Storage:** `data/raw/eppo_diesel_prices.csv`.
- **Schema:** `date, diesel_b7_price, source` (date YYYY-MM-DD,
  price in THB/L, source tag).
- **Fallback chain (Phase 2 TOOL-01):** live API → cached CSV →
  hardcoded baseline (29.94 THB/L from `BASELINE_DIESEL_PRICE` env).
  Each step is logged in the agent's reasoning_trace as the `source`
  field on the FuelData payload.
- **Baseline:** 29.94 THB/L (configurable via `BASELINE_DIESEL_PRICE`
  env). Treated as the surcharge zero-point — when current price
  equals baseline, surcharge_pct = 0.

## Simulated Express Rate Table

- **Generator:** `data/scripts/generate_rate_table.py`.
- **Schema (Phase 9 / v1.1 — 999.9 D-05/D-07):** `shipping_type,
  origin_zone, dest_zone, weight_min_kg, weight_max_kg, base_rate_thb`.
  `origin_zone` was added BEFORE the existing zone column (renamed to
  `dest_zone`). The pre-v1.1 schema (`shipping_type, zone,
  weight_min_kg, weight_max_kg, base_rate_thb`) is replaced by
  `if_exists="replace"` re-seed semantics.
- **Lookup key:** `lookup_rate(shipping_type, origin_zone, dest_zone,
  weight_kg)`. `origin_zone` is derived at the pricing-agent layer
  from the chosen `origin_hub_id` via
  `origin_zone_for(hub_id)` (`backend/agent/tools/hubs.py`).
- **Assumptions (Phase 9 / v1.1 — 999.9 D-06 verbatim):**
  - `ORIGIN_DEST_MULTIPLIER` 3×3 symmetric matrix replaces the
    legacy single-zone multiplier dict:

    | M | central-1 | central-2 | central-3 |
    |---|-----------|-----------|-----------|
    | **central-1** | 1.00 | 1.25 | 1.70 |
    | **central-2** | 1.25 | 1.00 | 1.45 |
    | **central-3** | 1.70 | 1.45 | 1.00 |

    Symmetric: `M[origin][dest] == M[dest][origin]`. Diagonal = 1.00
    preserves v1.0 central-1 → central-1 base rates byte-for-byte
    (e.g., `bounce 0-5kg = 55 THB`, `retail_standard 0-5kg = 50 THB`,
    `retail_fast 0-5kg = 65 THB`). Off-diagonal scales with zone
    distance: one-zone-apart = 1.25, two-zones-apart = 1.70.
  - Shipping multipliers (applied to the surcharge percentage,
    NOT base rate): `bounce = 1.0` (most fuel-sensitive),
    `retail_standard = 0.5`, `retail_fast = 0.8`.
  - Base rate range produced: 50 – 765 THB.
  - Total rows: **135** (3 origin × 3 dest × 3 ship × 5 weight tiers).
- **HITL threshold (Phase 5 D-04):** `HITL_TOTAL_THB_THRESHOLD = 500`
  (default). The threshold was calibrated against the original 45-row
  distribution to gate ~9% of representative demo queries (RESEARCH
  §HITL Threshold Calibration); the 135-row matrix preserves
  intra-zone rates, so cross-zone shipments simply fire HITL more
  often (desirable). Override via env to demo more/fewer gate
  triggers.
- **Why simulated:** real Express tariff sheets are confidential.
  The simulation captures the structural assumptions (zone +
  shipping-type multipliers + weight tiers) sufficient for an
  end-to-end agent demo with transparent, reproducible numbers.

## HQ/Branch Hub Network (Phase 9 / v1.1)

Source: `data/raw/hubs.json` (also mirrored to `frontend/data/hubs.json` for static-import on the UI).

The Express network consists of 1 HQ + 9 branches across Bangkok Metro:

| hub_id | Display name | Address (Google-geocodable) | Zone |
|--------|--------------|------------------------------|------|
| `hq-lat-krabang` | Express HQ — Lat Krabang Industrial Estate, Bangkok | Lat Krabang Industrial Estate, Bangkok | central-1 |
| `branch-bang-na` | Express Branch — Bang Na, Bangkok | Bang Na, Bangkok | central-1 |
| `branch-nonthaburi` | Express Branch — Mueang Nonthaburi | Mueang Nonthaburi, Nonthaburi | central-1 |
| `branch-pathum-thani` | Express Branch — Mueang Pathum Thani | Mueang Pathum Thani, Pathum Thani | central-1 |
| `branch-samut-prakan` | Express Branch — Mueang Samut Prakan | Mueang Samut Prakan, Samut Prakan | central-1 |
| `branch-ayutthaya` | Express Branch — Phra Nakhon Si Ayutthaya | Phra Nakhon Si Ayutthaya, Ayutthaya | central-2 |
| `branch-nakhon-pathom` | Express Branch — Mueang Nakhon Pathom | Mueang Nakhon Pathom, Nakhon Pathom | central-2 |
| `branch-samut-sakhon` | Express Branch — Mueang Samut Sakhon | Mueang Samut Sakhon, Samut Sakhon | central-2 |
| `branch-ratchaburi` | Express Branch — Mueang Ratchaburi | Mueang Ratchaburi, Ratchaburi | central-3 |
| `branch-lop-buri` | Express Branch — Mueang Lop Buri | Mueang Lop Buri, Lop Buri | central-3 |

**Distribution:** central-1 = 5 hubs, central-2 = 3 hubs, central-3 = 2 hubs. Mirrors real Bangkok logistics density; Lat Krabang HQ is the canonical e-commerce / logistics cluster.

**Origin zone derivation:** at lookup time, `pricing_agent_node` resolves `origin_hub_id` -> `origin_zone` via the `origin_zone_for(hub_id)` helper in `backend/agent/tools/hubs.py`. The zone is then passed to `lookup_rate(shipping_type, origin_zone, dest_zone, weight_kg)`.

**Single-leg routing (D-04):** every chat turn makes ONE Google Maps Directions call from the chosen hub to the destination. The internal HQ→branch transfer is operational cost, NOT customer-facing pricing — matches Kerry / Flash / Thailand Post quoting behaviour. The route TTL cache key is the `(origin_hub_id, destination)` tuple.

**Origin capture:** hybrid dropdown + prose. The `HubPicker` component sets a per-tab default (sessionStorage key `express_origin_hub_id`, default `hq-lat-krabang`); inline prose like "ship from Bang Na to Nonthaburi" is extracted by the planner via a 10-hub shortlist injected into its SYSTEM_PROMPT and validated against the `_HUB_INDEX` allowlist. Invalid LLM emissions silently fall back to the dropdown's value; absence on both layers defaults to `hq-lat-krabang` at the API boundary (`_fresh_stream` in `backend/api/routes/chat.py`).

**Refreshing:** the SQLite `hubs` table is rebuilt on every run of `python data/scripts/seed_database.py` via `if_exists="replace"` semantics — the script is idempotent, re-running produces the same 10-row table.

## Google Maps Directions API

- **Endpoint:** `directions/json` via the official `googlemaps` Python
  SDK.
- **Request shape:** `directions(origin, destination, mode='driving',
  departure_time='now')` — the `departure_time='now'` opt-in returns
  `duration_in_traffic` alongside `duration`, used to compute traffic
  severity (1–5).
- **Cache:** 15-minute TTL via `backend/agent/tools/_cache.py::TTLCache`,
  keyed on `(origin_normalised, destination_normalised)`.
- **Bangkok Metro provinces covered:** Bangkok, Nonthaburi, Pathum Thani, Samut Prakan, Ayutthaya, Ang Thong, Saraburi, Nakhon Pathom, Samut Sakhon, Lop Buri, Sing Buri, Chai Nat, Suphan Buri, Kanchanaburi, Ratchaburi.
- **Province -> zone mapping (verbatim from `data/raw/zone_definitions.json`):**
  - `central-1` (Bangkok Metro core): Bangkok, Nonthaburi, Pathum Thani, Samut Prakan
  - `central-2` (Greater Central): Ayutthaya, Ang Thong, Saraburi, Nakhon Pathom, Samut Sakhon
  - `central-3` (Extended Central): Lop Buri, Sing Buri, Chai Nat, Suphan Buri, Kanchanaburi, Ratchaburi
- **Out-of-scope provinces (raise ValueError "No Bangkok Metro zone for ..." -> graceful status='partial' clarify response):**
  Any Thai province NOT in the lists above (e.g. Chiang Mai, Phuket, Khon Kaen,
  Songkhla). Per backlog 999.2, the original Central Region scope was reduced
  to Bangkok Metro to keep rate-table coverage tight.
  Multi-region expansion is V2-02 (deferred).
- **Free-tier quota:** $200/month Google Maps credit (sufficient for
  demo + dev).

## Tavily News Search

- **Endpoint:** `client.search(query, topic='news',
  max_results=5, include_answer='basic', search_depth='basic')` via
  the official `tavily-python` SDK.
- **Cache:** 30-minute TTL via the same `TTLCache` class. Cache key
  is the normalised query string (`lowercase + strip + collapse
  whitespace`) to mitigate cache-key drift on semantically identical
  queries (RESEARCH §Pitfall 3).
- **Trigger semantics (D-09):** Planner emits
  `next_step="search_context"` ONLY when its user_intent classifier
  identifies a news/market/trend question (e.g. "why is fuel up",
  "diesel news this week"). Standard `surcharge_query` and
  `followup_query` paths NEVER trigger search by default — quota
  conservation.
- **Free-tier quota:** 1000 searches/month. Demo footprint estimate
  ~10 searches/run.
- **Failure handling (D-12):** any Tavily error (network, quota,
  auth) raises `RuntimeError` from `search_fuel_news` → caught by
  `search_agent_node` → emits a `warn`-status trace entry,
  `state.search_context` stays None, planner continues. Search
  failure NEVER blocks the surcharge response.
- **Snippet ceiling:** raw Tavily content per source clipped to 240
  characters before being persisted to `state.search_context.sources`
  (Pitfall 2 — Langfuse trace bloat mitigation).

## SQLite Databases

- **`data/express.db`** — `rate_table` + `zones` (seeded by
  `data/scripts/seed_database.py` from `data/raw/express_rate_table.csv`).
  Static reference data; not modified by the running agent.
- **`data/checkpoints.db`** — LangGraph `AsyncSqliteSaver`
  conversation memory. One thread per `thread_id`. Stores the full
  state snapshot per superstep — required for HITL resume across
  HTTP requests (Phase 5).

## Langfuse Cloud (Observability)

- **Host:** https://cloud.langfuse.com (free tier).
- **Captured events:** every Gemini structured-output call,
  every `@tool` invocation, every node entry/exit. Single
  `langfuse.langchain.CallbackHandler` attached at the chat handler
  boundary captures the full graph automatically.
- **Trace naming:** `chat_turn_{thread_id}_{turn_idx}` —
  deterministic seed via `langfuse.create_trace_id(seed=...)` so
  `POST /api/feedback` resolves the same trace ID without a name
  lookup. Falls back to `md5(f"chat_turn_{thread_id}_{turn_idx}")`
  when the langfuse client is unavailable, guaranteeing a stable
  32-hex trace ID even in tests / no-key environments.
- **Scores:**
  - `formula_accuracy` (1.0 / 0.0) — fire-and-forget auto-eval
    after pricing_agent. Re-runs the deterministic Phase 1 pure
    function with the same inputs and posts 1.0 on match,
    0.0 on divergence. Eval failure NEVER blocks the user response.
  - `user_feedback` (+1 / -1) — thumbs vote forwarded by
    `POST /api/feedback`.
- **Graceful no-op:** when any of `LANGFUSE_PUBLIC_KEY`,
  `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` is missing, the callback
  handler is None and all Score helpers return without calling the
  API. `POST /api/feedback` returns 200 with `delivered=false`
  (NOT a user-facing error) so the FE silent-error contract stays
  clean. The agent runs identically without Langfuse — local
  reproducibility preserved per CLAUDE.md.

## Internal Constants (config.py)

| Constant | Default | Meaning |
|----------|---------|---------|
| BASELINE_DIESEL_PRICE | 29.94 THB/L | Surcharge zero-point |
| SURCHARGE_CAP | 0.15 | Maximum surcharge percentage (15%) |
| SURCHARGE_FLOOR | -0.05 | Minimum surcharge percentage (-5%) |
| FUEL_DATA_TTL_SECONDS | 3600 | Phase 3 D-12 cache freshness window |
| ROUTE_CACHE_TTL_SECONDS | 900 | Google Maps cache TTL |
| SEARCH_CACHE_TTL_SECONDS | 1800 | Tavily cache TTL (Phase 5) |
| HITL_TOTAL_THB_THRESHOLD | 500.0 | HITL gate trigger (Phase 5) |
| PLANNER_MAX_ITERATIONS | 6 | Planner loop budget per turn |
| TRAFFIC_RATIO_BUCKETS | 1.1,1.3,1.5,1.8 | Severity thresholds (Phase 2) |

All constants are overridable via environment variables of the same
name. Defaults live in `backend/config.py`; see `.env.example` for
the full list of supported overrides.

## Live Verification (Langfuse Feedback)

Manual smoke test for the user-feedback wire. Run once during W5 code
freeze (or whenever the feedback contract changes) to confirm a real
thumbs-up click against the production frontend lands a `user_feedback`
Score row in Langfuse Cloud on the correct trace.

The frontend → backend → Langfuse path is fully exercised by the
automated tests (Phase 7 Plan 07-01 + 07-02), but only a live click
against a backend running with real `LANGFUSE_*` keys can prove the
Score row actually appears in the Langfuse dashboard. This is the
final defense against the audit's recurring bug class (cross-phase
contract drift that automated tests miss in isolation).

### Prerequisites

- Backend `.env` populated with valid `LANGFUSE_PUBLIC_KEY`,
  `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` (e.g.
  `https://cloud.langfuse.com`). Without these, the backend
  gracefully no-ops the Score POST (Phase 5 D-13) and the smoke
  cannot succeed.
- Browser access to https://cloud.langfuse.com (Langfuse Cloud
  dashboard) signed in to the same project the keys above belong to.

### Steps

1. Ensure backend `.env` has `LANGFUSE_*` keys, then **restart
   uvicorn** (a running server holds the old `_make_config` and
   `_drain_events` closures in memory; the new contract from Phase 7
   only takes effect on a fresh import — this is documented in
   quick task `260503-rs8`).
   ```bash
   # Kill any running uvicorn process, then:
   cd backend && uvicorn api.main:app --reload --port 8000
   ```

2. Start the frontend dev server.
   ```bash
   cd frontend && npm run dev
   ```

3. Open http://localhost:3000 in the browser. Send one surcharge
   query, e.g. `Surcharge for 15kg Bounce Bangkok to Nonthaburi`.
   Wait for the agent's full response (markdown answer + breakdown
   table).

4. Click the thumbs-up button (`👍`) below the assistant response.
   The button is `aria-label="Helpful"`. The frontend POSTs
   `{thread_id, message_id, score: 'up'}` to `/api/feedback`; the
   backend calls `client.create_score(name="user_feedback", ...)`
   on the same Langfuse trace the chat handler attached its
   CallbackHandler to (Phase 5 D-14).

5. Open https://cloud.langfuse.com → **Observations**. Filter by
   trace name `express-surcharge-agent` (the constant set by
   quick task `260503-rs8` / `260503-s2h` so all agent traces share
   one identity for dashboard filtering). The most recent trace
   corresponds to the query you just sent.

6. Confirm a `user_feedback` Score row exists on the matching
   `chat_turn_{thread_id}_{turn_idx}` trace with `value=1`. The
   trace_id is deterministic — derived from
   `md5("chat_turn_{thread_id}_{turn_idx}")` (Phase 5 D-14) — so
   the Score row attaches to the EXACT trace the agent run
   produced, not a name-lookup. Capture a screenshot showing the
   Score row and save it to `docs/screenshots/langfuse-feedback-score.png`
   (filename reserved in `docs/screenshots/.gitkeep`).

### Resume-path verification (optional)

Phase 7 also fixed the resume-path feedback wire (broken pre-Phase-7
via `replay-${i}` ids). To verify:

1. Reload http://localhost:3000 (the previous thread is in the sidebar).
2. Click the prior conversation entry to resume it.
3. Click thumbs-up on a replayed assistant message.
4. Confirm a SECOND `user_feedback` Score row appears in Langfuse
   on the same trace as step 6 above (the resume-path POST uses the
   BE-supplied `message_id` from `GET /api/conversations/:id`,
   which encodes the same `(thread_id, turn_idx)` pair).

### Troubleshooting

- **Click returns HTTP 400**: Backend regex `^(.+)-(\d+)$` rejected
  the `message_id`. Inspect the request body in the browser
  DevTools Network tab; the `message_id` should be
  `{thread_id}-{turn_idx}` shape (e.g. UUIDv4 + dash + integer).
  Pre-Phase-7 ids of the form `a-1714706402381` would 400 here —
  that is the audit's bug class. If you see this in production,
  Phase 7 frontend changes did not deploy.
- **Click returns HTTP 200 but no Score in Langfuse**: Backend
  gracefully no-opped (LANGFUSE_* keys missing or
  `langchain==0.3.28` not pinned — the silent import failure was
  the root cause of the original `260503-rs8` quick fix). Check
  the backend log for `feedback: langfuse disabled, skipping
  score`. Re-pin `langchain` and restart uvicorn.
- **Score appears on the wrong trace**: The `seed_trace_id` helper
  is deterministic; trace mismatch means the `(thread_id,
  turn_idx)` pair in the feedback POST does not match the pair the
  chat handler used. Verify the Phase 7 D-01 stamping at
  `backend/api/routes/chat.py::_drain_events`.
