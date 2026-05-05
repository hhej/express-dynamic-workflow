# Phase 2: Tools & Agent Nodes - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Build four tools that work independently with tests, and wrap Fuel + Route agents as LangGraph-compatible nodes:

1. `fetch_fuel_price` — EPPO diesel price with multi-level fallback
2. `calculate_route` — Google Maps Directions with zone mapping and traffic severity
3. `lookup_rate` — SQLite query by shipping_type + zone + weight_kg
4. `calculate_surcharge` tool wrapper — LangGraph tool around the existing pure function

Plus the Fuel Agent (ORCH-02) and Route Agent (ORCH-03) nodes, invokable individually with a sample AgentState.

**Out of scope (Phase 3):** Pricing Agent node, Planner node, full graph assembly, conditional routing, FastAPI endpoints, checkpointer wiring, agentic retry loop (ORCH-08), conversation memory.

</domain>

<decisions>
## Implementation Decisions

### Fuel fetch fallback chain (TOOL-01)
- **D-01:** Three-level chain: live EPPO scrape → latest row in `data/raw/eppo_diesel_prices.csv` → `BASELINE_DIESEL_PRICE` constant. No PTT secondary scrape — reality is that EPPO has no public API, so "API → scrape" collapses to scrape-only as the live path.
- **D-02:** HTTP client is `httpx` (async-native, FastAPI/LangGraph-compatible) with `BeautifulSoup4` for HTML parsing.
- **D-03:** Expand `FuelData.source` enum beyond Phase 1's `eppo`/`ptt` values. New values used by the tool: `eppo_live`, `eppo_cached_csv`, `hardcoded_baseline`. Reasoning trace renders the exact level hit.
- **D-04:** Live-fetch retry policy inside the tool: 2 retries with exponential backoff (1s, then 2s) before falling to CSV. Aligned with ORCH-08 direction without depending on the Phase 3 agentic wrapper.

### Route tool & zone mapping (TOOL-02, ORCH-03)
- **D-05:** Zone derivation: reverse-geocode the **destination** via Google Maps Geocoding API, extract `administrative_area_level_1` (province), match against `data/raw/zone_definitions.json` to produce `central-1`/`central-2`/`central-3`. Deterministic, testable, respects TOOL-06 (structured output).
- **D-06:** Traffic severity (1-5) derived from **ratio** `duration_in_traffic / duration`, bucketed: `<1.1=1`, `1.1-1.3=2`, `1.3-1.5=3`, `1.5-1.8=4`, `>1.8=5`. Thresholds live in `backend/config.py` so tuning does not require code changes.
- **D-07:** 15-minute route cache is in-process: a `(origin, destination)` → `(RouteData, timestamp)` dict behind a TTL wrapper. Resets on server restart — acceptable for dev + demo. No SQLite persistence.
- **D-08:** Dev hits Google Maps live; tests use pre-recorded JSON fixtures (no live API calls in CI).

### Agent node reasoning style (ORCH-02, ORCH-03)
- **D-09:** LLM-wrapped tool calls in Fuel Agent and Route Agent nodes. Each node: Gemini receives state + system prompt, decides to call its tool with extracted args, Gemini summarises the tool result into a `reasoning_trace` entry, node updates state. This is the agentic-pattern surface area that grading rewards most.
- **D-10:** Nodes read **pre-extracted** fields from `AgentState` (`shipping_type`, `weight_kg`, origin/destination placeholders). The Planner node (Phase 3) is responsible for extracting these from raw user messages. Phase 2 tests pass state directly — no message parsing in Fuel/Route nodes.
- **D-11:** Gemini structured-output fallback: if the Gemini response doesn't parse into the expected Pydantic model, retry once with a stricter prompt; if the second attempt still fails, skip LLM narration and emit a canned deterministic `reasoning_trace` entry from the tool result. Tests this early (addresses the "Gemini reliability unknown" blocker in STATE.md).
- **D-12:** `reasoning_trace` entry schema is a rich structured record: `{step, agent, tool, tool_input, tool_output, reasoning, timestamp, status}`. Maps directly to Langfuse span format (Phase 5) and to the UI-02 trace panel (Phase 4). All nodes emit this shape.

### lookup_rate tool (TOOL-03)
- **D-13:** Weight tier lookup uses **half-open intervals** `[weight_min_kg, weight_max_kg)`. SQL: `WHERE weight_min_kg <= :w AND (weight_max_kg IS NULL OR :w < weight_max_kg)`. The top tier (`50+`) stores `weight_max_kg = NULL`. 5.0 kg falls in the `5-10` tier, not `0-5`.
- **D-14:** On lookup miss (unknown zone, weight above top tier, unknown shipping_type), the tool raises `ValueError` with descriptive context. Consistent with `calculate_surcharge`'s D-11 pattern from Phase 1. The Phase 3 Planner/Pricing nodes catch and route to the clarify path — Phase 2 tests verify the exception.

### Testing strategy (cross-cutting)
- **D-15:** External HTTP mocked via the `responses` library (for `requests` / `httpx`-adapter mode). One-time capture of real EPPO HTML + Google Maps JSON committed as fixtures. Tests run offline and deterministically.
- **D-16:** Agent-node tests mock the LLM via `langchain` `FakeListChatModel` / `FakeMessagesListChatModel` — scripted Gemini responses, zero quota consumption. Tools mocked via `responses`. Addresses the Gemini 15-RPM limit without sacrificing node-level coverage.

### Claude's Discretion
- Exact module layout for the new tools (file names, test file names) as long as it follows the `backend/agent/tools/<name>.py` + `backend/tests/test_<name>.py` convention from Phase 1.
- Config keys and defaults for traffic-ratio thresholds (within the bucketing rule in D-06).
- Choice of `requests`-adapter vs native `httpx.MockTransport` inside the `responses` setup.
- Internal structure of the TTL wrapper (D-07) — class, context manager, or decorator.
- Format of Gemini system prompts for Fuel and Route agents (still must produce structured output parseable to Pydantic).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & agent design
- `docs/architecture.md` — Tool specs (Fuel Price, Route Calculator, Rate Table Lookup, Surcharge Calculator), agent graph flow, AgentState schema, conditional routing table, error handling strategy
- `docs/architecture.md` §Memory Management — 15-min route cache TTL, 1-hour fuel_data TTL (Phase 3 enforces, but Phase 2 tools produce data shaped for it)

### Phase inputs from Phase 1
- `backend/agent/tools/models.py` — Pydantic models: `FuelData`, `RouteData`, `RateResult`, `SurchargeInput`, `SurchargeResult` — Phase 2 tools MUST use these unchanged (D-03 only expands the `FuelData.source` value set)
- `backend/agent/tools/calculate_surcharge.py` — Pure surcharge function; Phase 2 task is to wrap it as a LangGraph tool without altering logic
- `backend/agent/state.py` — `AgentState` TypedDict; Fuel/Route nodes read/write these fields
- `backend/config.py` — `BASELINE_DIESEL_PRICE`, `SURCHARGE_CAP`, `SURCHARGE_FLOOR`, `SHIPPING_MULTIPLIERS`, `DATABASE_PATH` — Phase 2 adds traffic-ratio bucket thresholds here (D-06)
- `data/raw/zone_definitions.json` — Canonical zone → province list consumed by D-05
- `data/express.db` — Rate table schema; `lookup_rate` queries this
- `data/raw/eppo_diesel_prices.csv` — CSV fallback for fuel tool (D-01)
- `.planning/phases/01-foundation-data-pipeline/01-CONTEXT.md` — Phase 1 locked decisions (rate table design, fuel sourcing, formula constants, validation style)

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 2 scope: TOOL-01, TOOL-02, TOOL-03, TOOL-04, ORCH-02, ORCH-03
- `.planning/PROJECT.md` — Tech stack constraints (Gemini Flash free tier, SQLite, $200 Maps credit), grading weight on agent architecture (35%)

### Environment
- `.env.example` — API key placeholders: `GOOGLE_MAPS_API_KEY`, `GEMINI_API_KEY`, etc. — Phase 2 tools read these.

### Coding conventions
- `.planning/codebase/CONVENTIONS.md` — PEP 8, Black, Google-style docstrings, TypedDict/Pydantic patterns, test layout

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/agent/tools/calculate_surcharge.py` — Pure function, ready to be wrapped as a LangGraph `@tool`
- `backend/agent/tools/models.py` — Pydantic IO models cover all four tools; only `FuelData.source` needs a value-set expansion (D-03)
- `backend/agent/state.py` — `AgentState` ready for Fuel/Route agent reads/writes
- `backend/config.py` — Already has env-driven loading pattern; add traffic-ratio thresholds here
- `data/express.db` — Seeded rate table queryable directly by `lookup_rate`
- `data/raw/zone_definitions.json` — Drives D-05 zone mapping
- `data/raw/eppo_diesel_prices.csv` — Drives D-01 second-level fallback

### Established Patterns
- Pure functions raise `ValueError` on invalid input with descriptive messages (D-11 from Phase 1) — `lookup_rate` follows (D-14)
- `pathlib` relative to `__file__` for all data paths (STATE.md accumulated decision) — applies to CSV reads in fuel tool
- `from __future__ import annotations` for modern typing compat — continue
- Constants env-configurable via `backend/config.py` (D-09 Phase 1) — applies to new traffic-ratio thresholds
- Exact cap boundary treated as NOT capped (Phase 1 STATE.md decision) — informs lookup_rate tier boundary treatment (D-13 half-open)

### Integration Points
- `backend/agent/tools/fetch_fuel_price.py` (new) — imported by Fuel Agent node + eventually Planner (Phase 3)
- `backend/agent/tools/calculate_route.py` (new) — imported by Route Agent node + Planner
- `backend/agent/tools/lookup_rate.py` (new) — imported by Pricing Agent node (Phase 3)
- `backend/agent/tools/calculate_surcharge_tool.py` (new wrapper) or exposed via existing module — imported by Pricing Agent node (Phase 3)
- `backend/agent/nodes/fuel_agent.py` (new) — read/write `AgentState`, consume Fuel + `search_fuel_news` tools (search_fuel_news is TOOL-05, Phase 5 — stub the dependency)
- `backend/agent/nodes/route_agent.py` (new) — read/write `AgentState`, consume Route tool
- Graph wiring in `backend/agent/__init__.py` is Phase 3 — Phase 2 leaves it untouched
- Tests live under `backend/tests/` per Phase 1 pattern (`test_<tool>.py`, `test_<node>.py`)

</code_context>

<specifics>
## Specific Ideas

- "EPPO API response format undocumented" concern (STATE.md) is addressed by D-01 (scrape-only live path) + D-15 (`responses` library replay of one captured HTML sample).
- "Gemini structured output reliability unknown" concern (STATE.md) is addressed by D-11 (retry-then-deterministic fallback) and exercised early in Fuel/Route agent node tests (D-16).
- Traffic severity thresholds (D-06) should ship with sensible defaults but be overridable via env so the operations team can tune without a redeploy — matches the Phase 1 env-config philosophy.
- Reasoning-trace schema (D-12) is designed to map 1:1 onto Langfuse spans in Phase 5; Phase 2 nodes should already emit all fields even if Langfuse is not yet wired.

</specifics>

<deferred>
## Deferred Ideas

- `search_fuel_news` tool (TOOL-05) — Phase 5. Fuel Agent node (D-09) mentions it in system prompt but tool itself is not implemented here.
- Planner node / intent extraction — Phase 3. Fuel/Route agents rely on pre-extracted state (D-10).
- Agentic retry loop with exponential backoff + graceful fallback (ORCH-08) — Phase 3. Phase 2's in-tool retry (D-04) is a local stand-in, not the agentic wrapper.
- Human-in-the-loop approval gate (ORCH-09) — Phase 5.
- Parallel Fuel + Route execution via LangGraph Send API (ORCH-07) — Phase 5.
- Conversation memory via SQLite checkpointer (ORCH-10) — Phase 3.
- Pricing Agent node wrapping `lookup_rate` + `calculate_surcharge` (ORCH-04) — Phase 3.
- Langfuse callback integration (OBS-01) — Phase 5. Trace schema (D-12) is pre-aligned.

</deferred>

---

*Phase: 02-tools-agent-nodes*
*Context gathered: 2026-04-18*
