---
phase: 03-graph-assembly-api-layer
verified: 2026-04-25T11:35:00Z
status: passed
score: 5/5 success_criteria verified
human_verification:
  - test: "Live SSE end-to-end with real Gemini + EPPO + Google Maps"
    expected: "POST /api/chat with a natural-language surcharge query streams meta -> trace+ -> answer -> done; the answer markdown contains a populated 4-row breakdown table; reasoning_trace shows planner + fuel_agent + route_agent + pricing_agent + response steps"
    why_human: "Tests use FakeMessagesListChatModel + monkey-patched tool seams; live external services are intentionally never hit in CI per the project's free-tier constraint, so a one-time human curl confirms the shape against real Gemini/EPPO/Maps responses"
  - test: "Browser-side EventSource consumption"
    expected: "A browser fetch with Accept: text/event-stream (or EventSource client) parses each `data: {json}\\n\\n` line correctly, including type=meta on first chunk and type=done on close"
    why_human: "Programmatic verification confirmed via TestClient and curl; only a real browser confirms no proxy/buffer interaction breaks the SSE framing per Pitfall 5 in the field"
---

# Phase 3: Graph Assembly & API Layer Verification Report

**Phase Goal:** The full LangGraph StateGraph runs end-to-end -- planner routes to agents, agents produce a surcharge result, and FastAPI serves it via SSE streaming
**Verified:** 2026-04-25T11:35:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| #   | Truth                                                                                                                                                  | Status     | Evidence                                                                                                                                                                                                                                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | A natural language query like "What is the surcharge for a 15kg Bounce shipment from Bangkok to Nonthaburi?" produces a correct surcharge breakdown via the graph | VERIFIED | `test_full_surcharge_query_integration` (test_graph.py) drives planner -> fuel -> route -> pricing -> response and asserts final_payload.markdown contains all 4 D-11 row labels (Base rate, Surcharge %, Surcharge amount, Total). `test_happy_path_sse_sequence` (test_api_chat.py) drives the same path through FastAPI TestClient and asserts the answer SSE event carries status="ok" + surcharge_result. |
| 2   | Planner node correctly routes to Fuel + Route agents for surcharge queries and skips them for follow-up/clarification queries                          | VERIFIED | `_route_from_planner` in `backend/agent/graph.py:131-146` maps next_step values to nodes. Planner D-12 cache override in `backend/agent/nodes/planner.py:184-198` skips fetch_fuel/fetch_route when state has fresh data. `test_followup_reuses_cached_fuel` and `test_followup_only_runs_pricing` assert call counters stay at 1 across follow-ups. |
| 3   | Conversation memory works: a follow-up question in the same thread reuses previously fetched fuel/route data without re-calling tools                | VERIFIED | `test_checkpointer_persists_across_invocations` (round-trip via AsyncSqliteSaver), `test_followup_reuses_cached_fuel` (fuel_calls counter stays at 1 on turn 2), `test_followup_only_runs_pricing` (both fuel and route reused). End-to-end via `graph.aget_state(config)` after two ainvoke calls on same thread_id. |
| 4   | POST /api/chat returns an SSE stream with agent trace events and final response readable by a browser fetch call                                       | VERIFIED | `backend/api/routes/chat.py:32-80` returns `StreamingResponse(media_type="text/event-stream")` with manual `data: {json}\n\n` framing via `format_sse()`. Headers `Cache-Control: no-cache` + `X-Accel-Buffering: no`. Live curl confirms `/health -> {"status":"ok","graph_ready":true}`. `test_happy_path_sse_sequence` asserts meta -> trace+ -> answer -> done sequence. |
| 5   | GET /api/fuel-prices returns historical fuel price data as JSON                                                                                        | VERIFIED | `backend/api/routes/fuel_prices.py:34-78` reads `data/raw/eppo_diesel_prices.csv` and returns `List[FuelPricePoint]` with date+price+unit+source. Live curl `?days=30 -> 9 rows`, `?days=365 -> 185 rows`. Validation rejects days=0 and days=400 with HTTP 422. Tests `test_returns_last_30_days` + `test_clamps_to_available` pass. |

**Score:** 5/5 success criteria verified

### Required Artifacts

| Artifact                                                  | Expected                                                                       | Status     | Details                                                                                                                                                              |
| --------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/agent/graph.py`                                  | `build_graph` factory + `phase3_retry_on` filter; 5-node StateGraph compiled   | VERIFIED   | 202 lines, both symbols exported; live import smoke test passes; routes 5 add_node calls + 6 add_edge/conditional_edges; `compile(checkpointer=checkpointer)` present |
| `backend/agent/__init__.py`                               | Package-level export of `build_graph`                                          | VERIFIED   | Imports `build_graph` from `backend.agent.graph` and lists in `__all__`; `from backend.agent import build_graph` returns the same callable                          |
| `backend/agent/state.py`                                  | AgentState v3 with 15 fields including final_payload + errors with operator.add | VERIFIED   | Exposes all 15 fields confirmed via runtime inspection: messages, fuel_data, route_data, shipping_type, weight_kg, surcharge_result, reasoning_trace, next_step, origin, destination, user_intent, missing_fields, clarification_reason, errors, final_payload. errors uses `Annotated[List[dict], operator.add]` |
| `backend/agent/nodes/planner.py`                          | planner_node + PlannerOutput Pydantic schema + D-04 + D-12 + D-02 + D-24 short-circuit | VERIFIED | 231 lines, all 4 features present (state.errors short-circuit at L135, D-04 budget guard at L139, D-02 retry/clarify fallback at L155-179, D-12 cache override at L183-198) |
| `backend/agent/nodes/pricing_agent.py`                    | pricing_agent_node calling lookup_rate + calculate_surcharge_tool with D-08/D-09/D-11 | VERIFIED | 167 lines; lookup_rate at L127 (no try/except — D-09 honored); compound trace tool="lookup_rate+calculate_surcharge" at L153; deterministic narration fallback at L44-54 |
| `backend/agent/nodes/response_node.py`                    | response_node returning final_payload with D-10 shape + D-11 markdown          | VERIFIED   | 223 lines; final_payload returns markdown + surcharge_result + capped + status; 4-row table at L60-67; `_CAP_CALLOUT = "> ⚠ Cap/floor applied — review recommended"` at L42; status precedence at L168-175 |
| `backend/agent/nodes/fuel_agent.py`                       | D-13 fetched_at injection on fuel_data                                          | VERIFIED   | `fuel_dump["fetched_at"] = datetime.now(timezone.utc).isoformat()...` at L132                                                                                       |
| `backend/agent/nodes/route_agent.py`                      | D-13 fetched_at injection on route_data                                         | VERIFIED   | `route_dump["fetched_at"] = datetime.now(timezone.utc).isoformat()...` at L139                                                                                      |
| `backend/agent/prompts/planner.py`                        | SYSTEM_PROMPT for Planner with PlannerOutput schema                            | VERIFIED   | 2080 bytes; SYSTEM_PROMPT importable                                                                                                                                |
| `backend/agent/prompts/pricing_agent.py`                  | SYSTEM_PROMPT for Pricing narration                                            | VERIFIED   | 695 bytes; SYSTEM_PROMPT importable                                                                                                                                 |
| `backend/agent/prompts/response_node.py`                  | SYSTEM_PROMPT placeholder for future polish                                     | VERIFIED   | 960 bytes; SYSTEM_PROMPT importable (v1 uses deterministic prose; prompt locked for vocabulary parity)                                                              |
| `backend/api/main.py`                                     | FastAPI app with lifespan-managed AsyncSqliteSaver + 3 routers + /health       | VERIFIED   | 59 lines; lifespan opens AsyncSqliteSaver -> setup() -> compiles graph -> stores both on app.state; 3 include_router calls; /health endpoint returns graph_ready=true (live confirmed) |
| `backend/api/models.py`                                   | ChatRequest, SSEEvent, ConversationSummary, FuelPricePoint Pydantic models     | VERIFIED   | 51 lines; ChatRequest has min_length=1 on message; FuelPricePoint has date+price+unit+source                                                                        |
| `backend/api/sse.py`                                      | format_sse(event_type, payload) -> bytes helper                                 | VERIFIED   | 28 lines; D-18 envelope `data: {"type":..., "payload":...}\n\n` framing                                                                                            |
| `backend/api/routes/chat.py`                              | POST /api/chat SSE streaming handler                                            | VERIFIED   | 81 lines; uses graph.astream_events("v2"); filters on_chain_end + 5-node allow-list; emits meta/trace/answer/error/done; UUIDv4 fallback at L36; Cache-Control + X-Accel-Buffering headers at L75-79 |
| `backend/api/routes/conversations.py`                     | GET /api/conversations + GET /api/conversations/{thread_id}                     | VERIFIED   | 121 lines; SQL `FROM checkpoints GROUP BY thread_id ORDER BY MAX(checkpoint_id) DESC` at L46-55; `graph.aget_state(cfg)` at L63 + L105; 404 when no messages at L108-111 |
| `backend/api/routes/fuel_prices.py`                       | GET /api/fuel-prices?days=N reading EPPO CSV                                    | VERIFIED   | 79 lines; `Query(30, ge=1, le=365)` validation; `csv.DictReader` reads `data/raw/eppo_diesel_prices.csv`; sorted ascending; HTTP 503 when CSV missing at L51-55      |
| `backend/config.py`                                       | FUEL_DATA_TTL_SECONDS + PLANNER_MAX_ITERATIONS                                  | VERIFIED   | L55-62; both env-driven int constants present; defaults 3600 and 6                                                                                                  |
| `backend/tests/conftest.py`                               | in_memory_checkpointer fixture                                                  | VERIFIED   | Fixture present; AsyncSqliteSaver against `:memory:` aiosqlite connection                                                                                          |

### Key Link Verification

| From                                                       | To                                                       | Via                                                                                              | Status | Details                                                                                                                                              |
| ---------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/agent/graph.py`                                   | `langgraph.types.RetryPolicy`                            | `RetryPolicy(retry_on=phase3_retry_on, max_attempts=2, ...)`                                     | WIRED  | L161-167 instantiates with all 5 D-22 args; passed to all 5 add_node calls via `retry_policy=retry`                                                  |
| `backend/agent/graph.py`                                   | `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`       | `g.compile(checkpointer=checkpointer)`                                                            | WIRED  | L198 compiles with checkpointer; main.py L32-35 wires AsyncSqliteSaver(conn) and passes via build_graph(checkpointer)                                |
| `backend/agent/graph.py`                                   | All 5 node modules                                       | `g.add_node` calls                                                                                | WIRED  | L175-179: planner, fuel_agent, route_agent, pricing_agent, response. 4 wrapped in `_wrap_error_sink`; pricing intentionally unwrapped per D-09       |
| `backend/agent/nodes/planner.py`                           | `backend/config.py`                                      | `from backend.config import FUEL_DATA_TTL_SECONDS, PLANNER_MAX_ITERATIONS`                       | WIRED  | L31; both used in `_fuel_fresh()` (L78) and `_loop_budget_exhausted()` (L99)                                                                         |
| `backend/agent/nodes/pricing_agent.py`                     | `lookup_rate` + `calculate_surcharge_tool`               | `lookup_rate(...)` at L127 + `calculate_surcharge_tool.invoke(...)` at L136                       | WIRED  | Tool seams imported at L23-26; invoked sequentially; one compound trace entry emitted with tool='lookup_rate+calculate_surcharge'                    |
| `backend/api/main.py`                                      | `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`       | lifespan: `aiosqlite.connect(CHECKPOINT_PATH)` + `AsyncSqliteSaver(conn)` + `await checkpointer.setup()` | WIRED  | L29-35; both checkpointer and graph stashed on app.state; lifespan wired into FastAPI(lifespan=lifespan) at L42-46                                  |
| `backend/api/main.py`                                      | `backend.agent.build_graph`                              | `app.state.graph = build_graph(checkpointer)`                                                     | WIRED  | L35; build_graph imported at L17                                                                                                                     |
| `backend/api/routes/chat.py`                               | `compiled_graph.astream_events`                          | v2 streaming with on_chain_end filter                                                             | WIRED  | L48-49 calls `graph.astream_events(initial_state, config=config, version="v2")`; filter on `event.get("event") == "on_chain_end"` + 5-node allow-list at L51-53 |
| `backend/api/routes/conversations.py`                      | `graph.aget_state(config)`                               | Compiled-graph snapshot retrieval (Pitfall 6 — avoid CheckpointTuple)                             | WIRED  | L63 (list endpoint preview) + L105 (get-by-id endpoint)                                                                                              |
| `backend/api/routes/conversations.py`                      | AsyncSqliteSaver checkpoints table                       | SQL: `SELECT thread_id, MAX(checkpoint_id) FROM checkpoints`                                      | WIRED  | L46-55 via `app.state.checkpointer.conn.execute(...)`                                                                                                |
| `backend/api/routes/fuel_prices.py`                        | `data/raw/eppo_diesel_prices.csv`                        | `csv.DictReader` reads file relative to repo root                                                  | WIRED  | L26-31 resolves path via `Path(__file__).resolve().parents[3]`; L59-75 reads + filters + sorts                                                       |

### Behavioral Spot-Checks

| Behavior                                                                          | Command                                                                  | Result                                                                                | Status |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- | ------ |
| Backend test suite passes with no regressions                                    | `python -m pytest backend/tests/ -q`                                     | `103 passed, 4 warnings in 4.36s`                                                     | PASS   |
| Live FastAPI app boots cleanly                                                   | `uvicorn backend.api.main:app --port 8765` then `curl /health`           | `{"status":"ok","graph_ready":true}`                                                  | PASS   |
| OpenAPI lists all 5 expected paths                                               | `curl /openapi.json` then parse paths                                    | `['/api/chat', '/api/conversations', '/api/conversations/{thread_id}', '/api/fuel-prices', '/health']` | PASS   |
| GET /api/fuel-prices?days=30 returns rows                                        | `curl /api/fuel-prices?days=30`                                          | 9 rows, first 2026-03-26 @ 31.54 THB/L, source=eppo                                   | PASS   |
| GET /api/fuel-prices?days=365 returns full CSV span                              | `curl /api/fuel-prices?days=365`                                         | 185 rows, first 2025-10-01 @ 29.94 THB/L                                              | PASS   |
| GET /api/fuel-prices validates days bounds (1<=N<=365)                           | `curl /api/fuel-prices?days=0` and `?days=400`                            | Both return HTTP 422                                                                  | PASS   |
| GET /api/conversations returns empty list when no checkpoints                    | `curl /api/conversations`                                                | `count=0` (clean tmp DB)                                                              | PASS   |
| GET /api/conversations/{unknown_id} returns 404                                  | `curl /api/conversations/no-such-thread-xyz`                             | `404`                                                                                 | PASS   |
| `phase3_retry_on` matrix matches D-23                                            | runtime check on httpx/asyncio/Resource/Maps + ValueError/Exception     | True for all 5 retryable, False for ValueError + generic Exception                   | PASS   |
| `from backend.agent import build_graph` works                                    | `python -c "from backend.agent import build_graph; ..."`                | Same callable as `from backend.agent.graph import build_graph`                       | PASS   |
| `AgentState` exposes all 15 fields including `final_payload` + `errors`          | runtime inspect of `AgentState.__annotations__`                          | All 15 keys present in declared order                                                | PASS   |

### Requirements Coverage

| Requirement | Source Plan(s)         | Description                                                                                                                                                          | Status     | Evidence                                                                                                                                                                |
| ----------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ORCH-01     | 03-02                  | Planner agent detects user intent and routes to appropriate specialist agent(s) via conditional edges                                                                | SATISFIED  | `planner_node` extracts user_intent + emits next_step from locked vocabulary (PlannerOutput.next_step Literal); `_route_from_planner` maps to fuel/route/pricing/response nodes; 5 planner tests pass |
| ORCH-04     | 03-02                  | Pricing Agent node wraps lookup_rate and calculate_surcharge tools                                                                                                   | SATISFIED  | `pricing_agent_node` calls lookup_rate (L127) + calculate_surcharge_tool (L136); compound trace tool='lookup_rate+calculate_surcharge'; 3 pricing tests pass            |
| ORCH-05     | 03-02                  | Response node formats final answer with surcharge breakdown table and reasoning                                                                                      | SATISFIED  | `response_node` renders D-11 markdown with 4-row table + D-10 final_payload {markdown, surcharge_result, capped, status}; cap callout when capped=True; 4 response tests pass |
| ORCH-08     | 03-01, 03-03           | Agentic retry loop with exponential backoff (max 2 retries per tool) and graceful fallback with explanation                                                          | SATISFIED  | `RetryPolicy(max_attempts=2, backoff_factor=2.0, initial_interval=1.0, jitter=True)` applied to all 5 nodes; `phase3_retry_on` D-23 allow-list; `_wrap_error_sink` D-24 fallback to state.errors + next_step='respond'; 3 retry tests pass (filter unit, retry succeeds, retry exhausts -> partial) |
| ORCH-10     | 03-01, 03-02, 03-03    | Conversation memory via LangGraph SQLite checkpointer — follow-up queries reuse cached fuel/route data                                                              | SATISFIED  | AsyncSqliteSaver wired in main.py lifespan; `build_graph(checkpointer)` compiles with checkpointer; D-12 cache override in planner skips fetch_fuel/fetch_route on follow-ups; 3 cache-reuse tests pass (round-trip, fuel reused, both reused) |
| API-01      | 03-04                  | POST /api/chat endpoint accepts user message and returns SSE stream of agent traces + response                                                                       | SATISFIED  | `backend/api/routes/chat.py` POST /api/chat; StreamingResponse text/event-stream; D-18 envelope (meta/trace+/answer/error/done); 3 SSE tests pass (happy path / UUIDv4 / error path); live curl confirms |
| API-02      | 03-05                  | GET /api/conversations lists all past conversation threads                                                                                                            | SATISFIED  | `backend/api/routes/conversations.py` GET /api/conversations; SQL on checkpoints table grouped by thread_id; ordered DESC; default limit=50; `test_lists_conversations_desc` passes; live curl returns []  |
| API-03      | 03-05                  | GET /api/conversations/:id returns full conversation history for a thread                                                                                            | SATISFIED  | GET /api/conversations/{thread_id} returns messages + surcharge_result + reasoning_trace + fuel_data + route_data + errors; HTTP 404 on unknown thread (verified live); `test_returns_thread_state` + `test_404_unknown_thread` pass |
| API-04      | 03-05                  | GET /api/fuel-prices?days=30 returns historical fuel price data for charts                                                                                            | SATISFIED  | `backend/api/routes/fuel_prices.py` GET /api/fuel-prices?days=N; FastAPI Query(ge=1, le=365); reads EPPO CSV; sorted ascending; `test_returns_last_30_days` + `test_clamps_to_available` pass; live curl confirms 9/185 rows + HTTP 422 on out-of-range |

**Note on ORCH-06:** Plan 03-01 frontmatter lists ORCH-06 in `requirements-completed`, but ORCH-06 (AgentState TypedDict) was already shipped in Phase 1; Plan 03-01 only extended the schema. ROADMAP assigns ORCH-06 to Phase 1, so it is correctly NOT one of the Phase 3 requirement IDs.

**Orphaned Requirements:** None. ROADMAP Phase 3 lists exactly [ORCH-01, ORCH-04, ORCH-05, ORCH-08, ORCH-10, API-01, API-02, API-03, API-04] = 9 IDs. All 9 are claimed by at least one plan's `requirements:` frontmatter and all 9 verified above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | -    | -       | -        | -      |

Grep across `backend/agent/` and `backend/api/` for `TODO|FIXME|XXX|HACK|PLACEHOLDER|placeholder|coming soon|not yet implemented` returned zero matches. The Wave 0 placeholder skip markers in `backend/tests/` were all removed during Plans 03-02 through 03-05 (verified: `grep "pytestmark = pytest.mark.skip" backend/tests/` returns no matches).

The only deliberate "fallback" patterns are:
- `pricing_agent._deterministic_narration` — D-11 contract; intentional fallback when Gemini parse fails (test asserts both paths)
- `response_node._render_prose_*` — Deterministic prose by design per RESEARCH OQ 3 & 5; SYSTEM_PROMPT in `prompts/response_node.py` is locked for future Gemini polish but not invoked in v1 (documented decision in 03-02-SUMMARY)
- `_wrap_error_sink` — D-24 retry-exhaustion sink; produces a "partial"-status response with a populated errors[] when transient exceptions exhaust max_attempts

These are not stubs — they are explicit operational fallbacks with full test coverage.

### Human Verification Required

#### 1. Live SSE end-to-end with real Gemini + EPPO + Google Maps

**Test:** Start the server (`source .venv/bin/activate && uvicorn backend.api.main:app --port 8000`) with valid `.env` (GOOGLE_API_KEY, GOOGLE_MAPS_API_KEY) and curl `-N -X POST -H 'Content-Type: application/json' -d '{"message":"What is the surcharge for a 15kg Bounce shipment from Bangkok to Nonthaburi?"}' http://localhost:8000/api/chat`
**Expected:** SSE stream emits one `data: {"type":"meta","payload":{"thread_id":"<UUID>"}}`, then several `data: {"type":"trace",...}` events (planner -> fuel_agent -> route_agent -> pricing_agent -> response), then one `data: {"type":"answer","payload":{"markdown":"...","status":"ok",...}}`, and closes with `data: {"type":"done",...}`. The answer markdown contains the 4-row table with non-zero values.
**Why human:** Tests use FakeMessagesListChatModel + monkey-patched tool seams; live external services are intentionally never hit in CI per the project's free-tier constraint. A one-time human curl confirms the shape against real Gemini/EPPO/Maps responses.

#### 2. Browser-side EventSource consumption

**Test:** Open a browser dev console and run a `fetch('http://localhost:8000/api/chat', {method:'POST', headers:{'Content-Type':'application/json','Accept':'text/event-stream'}, body:'{"message":"..."}'})` then read the response stream.
**Expected:** Each `data: {json}\n\n` line parses correctly, no proxy buffering breaks framing.
**Why human:** Programmatic verification confirmed via TestClient and curl; only a real browser confirms no proxy/buffer interaction breaks the SSE framing per Pitfall 5 in the field. (Phase 4 frontend will exercise this end-to-end; this verification only establishes the backend contract is correct on the wire.)

### Gaps Summary

**No gaps found.** All 5 ROADMAP Success Criteria are verified by a combination of:
1. **Code inspection** (artifacts exist with substantive content; no stubs or placeholders)
2. **Wiring inspection** (RetryPolicy applied to all 5 nodes, AsyncSqliteSaver wired through lifespan, conditional edges keyed on next_step, astream_events filter, csv.DictReader on EPPO source)
3. **Test execution** (103 backend tests pass, 0 skipped, 0 failed — including 7 graph integration tests proving end-to-end ainvoke + retry + cache reuse + 3 SSE tests + 3 conversation tests + 2 fuel-prices tests)
4. **Live API smoke** (uvicorn boots, /health returns graph_ready=true, OpenAPI lists all 5 paths, fuel-prices returns expected row counts and validates days bounds, conversations returns 404 on unknown threads)

The 9 Phase 3 requirement IDs (ORCH-01, ORCH-04, ORCH-05, ORCH-08, ORCH-10, API-01, API-02, API-03, API-04) are all SATISFIED with concrete code + test evidence.

The two human-verification items (live Gemini round-trip and browser EventSource) are explicitly out-of-scope for automated CI per the project's free-tier constraint; they should be ticked off as part of Phase 4 frontend integration when a real browser drives the stack.

---

*Verified: 2026-04-25T11:35:00Z*
*Verifier: Claude (gsd-verifier)*
