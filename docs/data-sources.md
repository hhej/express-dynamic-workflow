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
- **Schema:** `shipping_type, zone, weight_min_kg, weight_max_kg,
  base_rate_thb`.
- **Assumptions (verbatim):**
  - Zone multipliers: `central-1 = 1.0`, `central-2 = 1.25`,
    `central-3 = 1.55`. Approximate the cost stack-up from Bangkok
    outward — central-1 is intra-Bangkok (no zone toll), central-2
    adjacent provinces, central-3 the outer Bangkok Metro ring.
  - Shipping multipliers (applied to the surcharge percentage,
    NOT base rate): `bounce = 1.0` (most fuel-sensitive),
    `retail_standard = 0.5`, `retail_fast = 0.8`.
  - Base rate range produced: 50 – 698 THB.
  - Total rows: 45 (3 ship types × 3 zones × 5 weight tiers).
- **HITL threshold (Phase 5 D-04):** `HITL_TOTAL_THB_THRESHOLD = 500`
  (default). Calibrated empirically against the 45-row distribution
  to gate ~9% of representative demo queries (RESEARCH §HITL
  Threshold Calibration). Override via env to demo more/fewer
  gate triggers.
- **Why simulated:** real Express tariff sheets are confidential.
  The simulation captures the structural assumptions (zone +
  shipping-type multipliers + weight tiers) sufficient for an
  end-to-end agent demo with transparent, reproducible numbers.

## Google Maps Directions API

- **Endpoint:** `directions/json` via the official `googlemaps` Python
  SDK.
- **Request shape:** `directions(origin, destination, mode='driving',
  departure_time='now')` — the `departure_time='now'` opt-in returns
  `duration_in_traffic` alongside `duration`, used to compute traffic
  severity (1–5).
- **Cache:** 15-minute TTL via `backend/agent/tools/_cache.py::TTLCache`,
  keyed on `(origin_normalised, destination_normalised)`.
- **Bangkok Metro provinces covered:** Bangkok, Nonthaburi, Pathum Thani,
  Samut Prakan, Nakhon Pathom, Samut Sakhon, Ayutthaya.
- **Province → zone mapping (verbatim):**
  - `central-1`: Bangkok
  - `central-2`: Nonthaburi, Pathum Thani, Samut Prakan, Nakhon Pathom,
    Samut Sakhon, Ayutthaya
  - `central-3`: Reserved for outer Bangkok Metro ring (e.g., outer
    Ayutthaya districts, far Pathum Thani) — currently sparse.
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
