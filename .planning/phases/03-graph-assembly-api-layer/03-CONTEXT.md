# Phase 3: Graph Assembly & API Layer - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the existing agent components (Phase 2 Fuel + Route nodes, Phase 2 tools, Phase 1 state/models) into a complete LangGraph StateGraph with a Planner, Pricing Agent, and Response node; persist conversation state via a SQLite checkpointer; and expose the graph via a FastAPI service with chat (SSE), conversation history, and historical fuel-prices endpoints.

End state: a natural-language query like *"What is the surcharge for a 15kg Bounce shipment from Bangkok to Nonthaburi?"* hits `POST /api/chat`, streams reasoning_trace events live, and closes with a final markdown + structured surcharge breakdown. Follow-up questions in the same `thread_id` reuse cached fuel/route data without re-calling tools.

**In scope (this phase):** ORCH-01 (Planner), ORCH-04 (Pricing Agent), ORCH-05 (Response), ORCH-08 (graph-level retry loop), ORCH-10 (conversation memory), API-01 (chat SSE), API-02 (list conversations), API-03 (get conversation), API-04 (historical fuel-prices).

**Out of scope (Phase 5):** ORCH-07 (parallel Fuel + Route via Send API), ORCH-09 (HITL approval), TOOL-05 (Tavily search), API-05 (feedback), OBS-01..03 (Langfuse).

</domain>

<decisions>
## Implementation Decisions

### Planner design (ORCH-01)
- **D-01:** Single Gemini structured-output call. Planner returns a Pydantic schema `PlannerOutput { user_intent, shipping_type?, weight_kg?, origin?, destination?, missing_fields: list[str], next_step, clarification_reason? }`. Same Gemini path as Phase 2 Fuel/Route nodes (raw `model.invoke()` + `json.loads()`) so `FakeMessagesListChatModel` keeps working in tests.
- **D-02:** D-11 fallback applies. On parse failure: retry once with stricter prompt; on second failure, emit deterministic `next_step="clarify"` + `clarification_reason="planner_parse_failed"`. Never raise out of the Planner.
- **D-03:** Planner-loop routing pattern. Graph topology: `START → Planner → conditional_edge(next_step) → {fuel_agent | route_agent | pricing_agent | response} → Planner` (loop until `next_step="respond"`). Cache-aware skipping (D-12) is implemented inside the Planner, not in the edges.
- **D-04:** Max-loop guard. Planner must terminate within 6 iterations per request (1 init + up to 4 specialist calls + 1 respond). Hitting the cap forces `next_step="respond"` with a partial-result message. Prevents infinite ping-pong on degenerate planner outputs.
- **D-05:** Flat AgentState additions. Add to `backend/agent/state.py` `AgentState`: `origin: Optional[str]`, `destination: Optional[str]`, `user_intent: Optional[str]`, `missing_fields: List[str]`, `clarification_reason: Optional[str]`, `errors: Annotated[List[dict], operator.add]` (errors uses `add` reducer so retry-exhausted nodes can append). Do NOT introduce a nested `extracted` dict — D-10 from Phase 2 reads `state.get("origin")` directly.
- **D-06:** Clarify-path message generation. Planner sets `next_step="clarify"` + `clarification_reason` (e.g., `"missing_weight"`). Response Node renders the user-facing message via Gemini with the same D-11 fallback pattern. Single output path: all final user-facing text comes from the Response Node.
- **D-07:** Intent vocabulary (locked). `user_intent` enum: `surcharge_query` (compute new surcharge), `followup_query` (refine using cached data), `clarification` (missing inputs), `out_of_scope` (not a logistics question). Maps 1-to-1 to the routing table in `docs/architecture.md`.

### Pricing Agent (ORCH-04)
- **D-08:** Pricing Agent mirrors the Phase 2 Fuel/Route node pattern: invoke `lookup_rate` then `calculate_surcharge_tool`, narrate result via Gemini with D-11 deterministic fallback, emit a single D-12-shape `reasoning_trace` entry (`agent="pricing_agent"`). The trace's `tool` field uses the compound value `"lookup_rate+calculate_surcharge"` to record both invocations in one entry — keeps step counter linear.
- **D-09:** `lookup_rate` ValueError → Planner clarify path. The Pricing Agent does NOT catch `ValueError` from `lookup_rate` (D-14 from Phase 2). It bubbles to the graph-level retry policy; if the policy classifies `ValueError` as non-transient (D-22), the failure routes to Response Node with `clarification_reason="invalid_inputs"`.

### Response Node (ORCH-05)
- **D-10:** Response payload shape: `{ markdown: str, surcharge_result: SurchargeResult.model_dump() | None, capped: bool, status: "ok" | "clarify" | "partial" }`. Frontend renders `markdown` directly; `surcharge_result` is the structured object Phase 4 dashboard charts can consume without re-parsing markdown.
- **D-11:** Markdown structure (locked): a one-paragraph reasoning prose summary, followed by a 4-row breakdown table (`Base rate`, `Surcharge %`, `Surcharge amount`, `Total`), followed by an italicised "Reasoning trace available below" footer. When `capped=true`, prepend a callout line: `> ⚠ Cap/floor applied — review recommended`.

### Conversation memory (ORCH-10)
- **D-12:** Planner inspects state freshness, decides reuse. On each turn, Planner checks `state.fuel_data["fetched_at"]` against `FUEL_DATA_TTL_SECONDS` (3600). For route, Planner checks `state.route_data["origin"] == new_origin` and `state.route_data["destination"] == new_destination`. Stale or origin/dest-changed → Planner emits `next_step="fetch_fuel"` / `"fetch_route"`. Fresh and matching → skip directly to next missing data or `calculate_price`.
- **D-13:** `fetched_at` is added to `FuelData` and `RouteData` dump dicts as ISO-8601 UTC string. The Pydantic models stay unchanged in Phase 3 — the timestamp is added at the agent-node serialisation layer (fuel_agent_node and route_agent_node updates `model_dump()` output). Avoids Phase 2 model churn.
- **D-14:** New config constants in `backend/config.py`: `FUEL_DATA_TTL_SECONDS=3600`, `PLANNER_MAX_ITERATIONS=6`. The existing 15-min in-process route cache (Phase 2 D-07) stays as-is — it's a tool-level cache; D-12 is the agent-level reuse decision.
- **D-15:** AsyncSqliteSaver checkpointer. Use `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver` initialised with `aiosqlite` against `data/checkpoints.db`. FastAPI is async; sync SqliteSaver would block the event loop on every `update_state`/`get_state` call. Add `aiosqlite` to `requirements.txt`.
- **D-16:** Graph compiled once at FastAPI startup (lifespan event). Single `compiled_graph = graph.compile(checkpointer=checkpointer)` stored on `app.state`. All chat requests reuse it; per-thread isolation is provided by `thread_id` in the config dict, not by graph topology. Per-request compile would be wasteful and break the checkpointer's async context.

### API contract (API-01..04)
- **D-17:** SSE event granularity: live trace events + final answer. Use `compiled_graph.astream_events(..., version="v2")` to emit one SSE event per node completion (`"on_chain_end"` filter). Trace events fire as soon as each agent's node returns — visible reasoning is the explicit grading rubric (35% Agent Architecture).
- **D-18:** Typed JSON envelope. Each SSE event body: `data: {"type":"trace"|"answer"|"error"|"done","payload":{...}}\n\n`. `trace.payload` = D-12 trace entry verbatim. `answer.payload` = D-10 Response payload. `error.payload` = `{"message": str, "retryable": bool}`. `done` event closes the stream with empty payload.
- **D-19:** Thread ID flow. Client may supply `thread_id` in POST body; if missing or unknown to the checkpointer, server generates a UUIDv4 and emits it in the FIRST SSE event as a `meta` event: `{"type":"meta","payload":{"thread_id": "..."}}`. Frontend persists thread_id in localStorage for resume. (`meta` is a fifth event type — added implicitly.)
- **D-20:** API-04 fuel-prices source. `GET /api/fuel-prices?days=30` reads directly from `data/raw/eppo_diesel_prices.csv` (not SQLite). Phase 1 only seeded `rate_table`; adding a new `fuel_prices` SQLite table for read-only chart data would require a Phase-1 schema retroactive change. CSV read with pandas is < 50 ms for 6 months of daily prices. Endpoint returns `[{date, price, unit, source}]` JSON array.
- **D-21:** API-02/03 conversation listing/replay. `GET /api/conversations` queries the AsyncSqliteSaver's checkpoint table (`SELECT thread_id, MAX(checkpoint_ts) FROM checkpoints GROUP BY thread_id ORDER BY 2 DESC LIMIT 50`) returning `[{thread_id, last_updated, first_message_preview}]`. `GET /api/conversations/:id` calls `checkpointer.aget(config={"configurable":{"thread_id":id}})` and returns the message history + final surcharge_result (if any).

### Retry topology (ORCH-08)
- **D-22:** LangGraph node-level `RetryPolicy(max_attempts=2, backoff_factor=2.0, initial_interval=1.0)` applied to all agent nodes (`planner`, `fuel_agent`, `route_agent`, `pricing_agent`, `response`). Total worst-case latency ~3 s per failing node — under the 10 s target from architecture.md.
- **D-23:** Retryable exception scope: `httpx.HTTPError`, `httpx.TimeoutException`, `asyncio.TimeoutError`, `google.api_core.exceptions.ResourceExhausted` (Gemini 15-RPM), `googlemaps.exceptions.HTTPError`. Explicitly NOT retried: `ValueError` (D-14: clarify-path trigger), `pydantic.ValidationError` (planner D-02 has its own retry), generic `Exception` (would mask bugs).
- **D-24:** Retry-exhausted fallback edge: every node has an error sink that appends to `state.errors[]` (`{node, exception_type, message, timestamp}`) and forces `next_step="respond"`. Response Node detects `state.errors` and renders a partial-result message: e.g., *"Could not fetch live fuel price (network failure after 2 retries). Using last cached value."* — `status: "partial"` in the payload. Phase 2 in-tool retries (D-04 fuel) stay — they handle network flakes BELOW this graph-level retry.

### Testing strategy (cross-cutting)
- **D-25:** Graph-level integration tests use `FakeMessagesListChatModel` for ALL Gemini calls (Planner, Pricing, Response, plus reused Fuel/Route from Phase 2). Tools mocked via the same `pytest-httpx` (TOOL-01) and `mocker.patch.object` (TOOL-02 D-08) seams Phase 2 established. AsyncSqliteSaver tests use a temp `:memory:` DB via `aiosqlite.connect(":memory:")` — no checkpoint pollution between tests.
- **D-26:** API tests use FastAPI's `TestClient` with `httpx.AsyncClient` for SSE assertion: parse `data: ...` lines, assert event sequence `[meta, trace*, answer, done]` for happy path; `[meta, trace*, error, done]` for failure path.

### Claude's Discretion
- Exact module split for the Planner (single `backend/agent/nodes/planner.py` vs a `planner/` package with `extractor.py` + `router.py`) — as long as it follows the `backend/agent/nodes/<name>.py` + `backend/tests/test_<name>.py` convention.
- Format of the Planner system prompt (still must produce structured output parseable to `PlannerOutput`).
- Internal layout of FastAPI app (single `backend/api/main.py` with included routers vs split per-endpoint files).
- pandas vs csv-stdlib for `GET /api/fuel-prices` parsing.
- Exact Pydantic field names for `PlannerOutput` (within the schema in D-01).
- Whether Response Node uses Gemini for prose summary or a deterministic Jinja-style template (both are acceptable — D-11 markdown structure is locked, the prose itself is not).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & agent design
- `docs/architecture.md` — Agent Graph Flow (Planner → specialists routing table), AgentState schema, Conditional Routing table (next_step values), API Endpoints table, Memory Management section (checkpointer + cache TTLs), Error Handling section (retry/fallback strategy)
- `docs/architecture.md` §Conditional Routing — locks the next_step vocabulary: `fetch_fuel`, `fetch_route`, `calculate_price`, `search_context`, `clarify`, `respond`
- `docs/architecture.md` §Memory Management — confirms 1-hour fuel TTL and 15-min route cache (Phase 3 enforces fuel TTL via D-12/D-14)
- `docs/architecture.md` §Error Handling — confirms "Up to 2 retries with exponential backoff" + "Return partial result with explanation" (codified in D-22 / D-24)

### Phase inputs from earlier phases
- `backend/agent/state.py` — `AgentState` TypedDict; Phase 3 adds D-05 fields (origin, destination, user_intent, missing_fields, clarification_reason, errors)
- `backend/agent/tools/models.py` — Pydantic IO models; Pricing Agent uses `RateResult` + `SurchargeInput`/`SurchargeResult` unchanged
- `backend/agent/tools/lookup_rate.py` — TOOL-03 already raises ValueError on miss (D-14 Phase 2) — Pricing Agent relies on this contract (D-09)
- `backend/agent/tools/calculate_surcharge_tool.py` — TOOL-04 LangGraph @tool wrapper, ready for Pricing Agent to invoke
- `backend/agent/nodes/fuel_agent.py` — ORCH-02 reference implementation; Planner/Pricing/Response nodes mirror its D-11/D-12 narration pattern
- `backend/agent/nodes/route_agent.py` — ORCH-03 reference; D-10 contract (reads pre-extracted origin/destination) is the contract Phase 3 Planner must satisfy
- `backend/agent/llm.py` — `get_chat_model()` factory; tests patch this to inject `FakeMessagesListChatModel` (D-25)
- `backend/config.py` — Add D-14 constants here (`FUEL_DATA_TTL_SECONDS`, `PLANNER_MAX_ITERATIONS`)
- `.planning/phases/01-foundation-data-pipeline/01-CONTEXT.md` — Phase 1 locked decisions (formula constants, AgentState origin)
- `.planning/phases/02-tools-agent-nodes/02-CONTEXT.md` — Phase 2 locked decisions: D-09 (LLM-wrapped nodes), D-10 (planner pre-extraction contract), D-11 (Gemini fallback), D-12 (reasoning_trace schema), D-14 (ValueError clarify-path), D-15/D-16 (testing seams)

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 3 scope: ORCH-01, ORCH-04, ORCH-05, ORCH-08, ORCH-10, API-01, API-02, API-03, API-04
- `.planning/PROJECT.md` — Tech stack constraints (Gemini Flash 15-RPM, SQLite, FastAPI async); grading weights (Agent Architecture 35%, Data Integration 20%, Documentation/Git 20%)

### Environment
- `.env.example` — Add new keys: `FUEL_DATA_TTL_SECONDS=3600`, `PLANNER_MAX_ITERATIONS=6` defaults

### Coding conventions
- `.planning/codebase/CONVENTIONS.md` — PEP 8, Black, Google-style docstrings, TypedDict/Pydantic patterns, snake_case file names
- `.planning/codebase/STRUCTURE.md` — `backend/api/` layout for endpoint files, `backend/agent/nodes/` for new Planner/Pricing/Response

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/agent/llm.py` `get_chat_model()` — same factory used for Planner, Pricing, Response Gemini calls (test-swappable via `FakeMessagesListChatModel`)
- `backend/agent/nodes/fuel_agent.py` and `route_agent.py` — reference implementations for the D-09/D-11/D-12 narration pattern; Planner/Pricing/Response copy the structure
- `backend/agent/tools/lookup_rate.py` + `calculate_surcharge_tool.py` — drop-in tools for Pricing Agent
- `backend/agent/tools/_cache.py` `TTLCache` — already thread-safe (Phase 2 D-07); useful if Phase 3 needs any in-process caches beyond what AgentState provides
- `backend/agent/state.py` — already has `reasoning_trace: Annotated[List[dict], operator.add]` reducer (Phase 2 Pitfall 1); the new `errors` field reuses the same pattern (D-05)
- `backend/config.py` — env-driven constant pattern; D-14 constants drop straight in
- `data/raw/eppo_diesel_prices.csv` — direct source for `GET /api/fuel-prices` (D-20)
- `data/checkpoints.db` — auto-created path; AsyncSqliteSaver writes here (D-15)

### Established Patterns
- Agent nodes: read state, optionally call tool, narrate via `_narrate_with_llm` with D-11 fallback, emit ONE D-12 trace entry, return partial state dict (LangGraph reducer merges) — Phase 3 Planner/Pricing/Response follow this shape
- Pure functions raise `ValueError` on invalid input (Phase 1 D-11, Phase 2 D-14) — Phase 3 retries (D-22) explicitly skip ValueError
- Test seams: `mocker.patch.object` on the lazy client factory (calculate_route Phase 2 plan-03), `pytest-httpx` for HTTP mocks, `FakeMessagesListChatModel` for LLM — extend to Planner / Pricing / Response and to API tests (D-25, D-26)
- `from __future__ import annotations` for modern typing — keep
- ISO-8601 UTC timestamps with explicit `Z` suffix (Phase 2 fuel_agent line 121-123) — pattern for D-13 `fetched_at` formatting

### Integration Points
- `backend/agent/nodes/planner.py` (new) — entry node; reads state.messages, emits next_step + extracted fields
- `backend/agent/nodes/pricing_agent.py` (new) — invokes lookup_rate + calculate_surcharge_tool, narrates, emits trace
- `backend/agent/nodes/response_node.py` (new) — reads state.surcharge_result | state.errors | state.clarification_reason, emits final markdown payload (D-10/D-11)
- `backend/agent/graph.py` (new) — defines StateGraph, registers nodes with RetryPolicy (D-22), conditional edges keyed on `next_step`, compiles with AsyncSqliteSaver
- `backend/agent/__init__.py` — current empty; Phase 3 exports the compiled graph factory
- `backend/api/main.py` (new) — FastAPI app with lifespan event for graph compile (D-16)
- `backend/api/routes/chat.py` (new) — POST /api/chat handler with SSE streaming via astream_events (D-17/D-18)
- `backend/api/routes/conversations.py` (new) — GET /api/conversations + /:id (D-21)
- `backend/api/routes/fuel_prices.py` (new) — GET /api/fuel-prices?days=N (D-20)
- `backend/api/models.py` or `backend/api/schemas.py` (new) — Pydantic request/response models for the four endpoints
- `backend/tests/test_planner.py`, `test_pricing_agent.py`, `test_response_node.py`, `test_graph.py`, `test_api_chat.py`, `test_api_conversations.py`, `test_api_fuel_prices.py` (new)
- `requirements.txt` — add `fastapi`, `uvicorn[standard]`, `aiosqlite`, `langgraph-checkpoint-sqlite` (or whatever pkg the AsyncSqliteSaver lives in for our `langgraph==0.6.11` pin)

</code_context>

<specifics>
## Specific Ideas

- "Visible reasoning is what makes this agentic" (PROJECT.md Core Value) is the explicit grading lever for D-17 (live trace events). The Phase 4 frontend will render the trace panel from these events; ANY decision that hides or batches them weakens the grading argument.
- Planner-loop pattern (D-03) is what enables ORCH-10's signature feature: a follow-up like *"What about Retail Fast?"* keeps the same `thread_id`, Planner sees `state.fuel_data` is < 1 hour old (D-12), skips Fuel + Route, and routes straight to Pricing. This is the cache-reuse demo.
- D-11 markdown structure is locked but the prose summary is Claude's Discretion — this lets the Response Node Gemini call vary tone naturally while keeping the table format predictable for Phase 4 rendering.
- D-23's exclusion of `pydantic.ValidationError` from graph retries is deliberate: the Planner's D-02 already retries-once internally on its own validation failures. Double-retrying would burn 4 Gemini calls on a permanent prompt issue and starve the 15-RPM budget.
- The `meta` SSE event type (D-19) is a fifth type beyond the four enumerated in D-18. Document it explicitly in any API schema artefact so the Phase 4 frontend doesn't get a surprise event class.

</specifics>

<deferred>
## Deferred Ideas

- Parallel Fuel + Route execution via LangGraph Send API (ORCH-07) — Phase 5. The state reducer (`operator.add` on reasoning_trace + on the new `errors` field per D-05) is already shaped for this.
- Human-in-the-loop approval gate for high-value shipments (ORCH-09) — Phase 5. Will likely insert between Pricing Agent and Response Node as a conditional edge gated on `surcharge_result.total > THRESHOLD`.
- Tavily web search tool / search_fuel_news (TOOL-05) — Phase 5. Phase 3 Fuel Agent system prompt (Phase 2) explicitly does NOT advertise it; Planner's `next_step="search_context"` route stays unimplemented in Phase 3 (or routes to a stub Response message).
- POST /api/feedback endpoint (API-05) — Phase 5, alongside Langfuse Score API integration.
- Langfuse callback handler integration (OBS-01..03) — Phase 5. D-12 trace schema is pre-aligned with Langfuse spans.
- Token-level streaming over SSE (alt to D-17) — out of scope. Adds complexity for low marginal demo value; trace-level granularity is already the differentiator.
- Conversation deletion / archive endpoints — out of scope for v1; checkpointer rows accumulate indefinitely (acceptable for course demo).
- Adaptive replan-on-error (alt to D-24) — deferred. Current "always-to-Response on retry exhaustion" is a deliberate simplification; agentic recovery loops are a Phase 5+ enhancement.

</deferred>

---

*Phase: 03-graph-assembly-api-layer*
*Context gathered: 2026-04-25*
