---
phase: 03-graph-assembly-api-layer
plan: 04
subsystem: api-chat
tags: [fastapi, sse, lifespan, async-sqlite-saver, astream-events, api-01, d-17, d-18, d-19]

# Dependency graph
requires:
  - phase: 03-graph-assembly-api-layer
    plan: 03
    provides: build_graph(checkpointer) factory, AgentState.final_payload, D-22/D-23/D-24 retry topology, _route_from_planner
  - phase: 03-graph-assembly-api-layer
    plan: 02
    provides: response_node final_payload (D-10), reasoning_trace entries per node (D-12)
  - phase: 03-graph-assembly-api-layer
    plan: 01
    provides: AgentState v2 fields, FUEL_DATA_TTL_SECONDS, in_memory_checkpointer fixture
provides:
  - FastAPI app at backend/api/main.py with lifespan that opens AsyncSqliteSaver, calls setup() (Pitfall 9), compiles graph via build_graph(checkpointer), exposes app.state.graph and app.state.checkpointer
  - GET /health readiness endpoint returning {status, graph_ready}
  - POST /api/chat SSE handler at backend/api/routes/chat.py emitting D-18 envelope sequence (meta -> trace+ -> answer -> done; error before done on uncaught exception)
  - D-19 thread_id flow: client may omit thread_id; server generates UUIDv4 and emits as first SSE event
  - Pitfall 5 prevention: raw StreamingResponse + manual SSE framing (no EventSourceResponse, not available in FastAPI 0.128.8); Cache-Control: no-cache + X-Accel-Buffering: no headers
  - backend/api/sse.py: format_sse(event_type, payload) -> bytes helper
  - backend/api/models.py: ChatRequest (D-19), SSEEvent informational schema, ConversationSummary (Plan 03-05 stub), FuelPricePoint (Plan 03-05 stub)
  - 3 passing integration tests via FastAPI TestClient (happy path / UUIDv4 generation / error path)
affects: [03-05-api-conversations, frontend-chat-component]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lifespan-managed AsyncSqliteSaver: aiosqlite.connect(CHECKPOINT_PATH) -> AsyncSqliteSaver(conn) -> await checkpointer.setup() -> app.state.graph = build_graph(checkpointer); guarantees Pitfall 9 idempotent table creation runs once before any request and ties connection cleanup to app shutdown"
    - "Manual SSE framing via raw StreamingResponse + format_sse() bytes helper -- EventSourceResponse not available in FastAPI 0.128.8 (Pitfall 5), so we hand-write `data: {json}\\n\\n` lines with explicit Cache-Control + X-Accel-Buffering headers"
    - "astream_events('v2') filter on (on_chain_end, name in {planner, fuel_agent, route_agent, pricing_agent, response}) yields per-node partial state outputs; chat handler streams every reasoning_trace entry the node returned and emits an `answer` event when name=='response' AND output contains final_payload"
    - "Test isolation pattern for env-driven config: monkeypatch.setenv + importlib.reload(backend.config) + importlib.reload(backend.api.main) BEFORE TestClient enters lifespan; CRITICAL cleanup: monkeypatch.delenv + importlib.reload again on yield-cleanup (pytest's monkeypatch teardown runs AFTER the fixture's own cleanup, so without the explicit delenv + reload the polluted CHECKPOINT_PATH leaks into later tests like test_checkpoint_path_default)"
    - "Error-path test pragma: an uncaught RuntimeError from lookup_rate (which is NOT wrapped per D-09) MAY surface as either an explicit `error` SSE event OR a `partial`-status `answer` event depending on whether the exception bubbles past the graph or is caught by the D-24 error sink on a wrapped node; the test accepts EITHER outcome since both signal failure correctly per D-23/D-24"

key-files:
  created:
    - backend/api/__init__.py
    - backend/api/main.py
    - backend/api/models.py
    - backend/api/sse.py
    - backend/api/routes/__init__.py
    - backend/api/routes/chat.py
  modified:
    - backend/tests/test_api_chat.py
    - .gitignore

key-decisions:
  - "Lifespan stores both checkpointer and graph on app.state -- Plan 03-05 will need direct access to the checkpointer (graph.aget_state alone insufficient for listing all threads); exposing the saver lets the conversations endpoint enumerate via aput-side queries without re-opening another aiosqlite connection"
  - "Chat handler filters astream_events on on_chain_end + node-name allow-list rather than parsing every event -- Pattern 4 in RESEARCH; on_chain_start/on_chain_stream emissions are noisy and would duplicate or fragment trace entries"
  - "format_sse() bytes helper centralised so future endpoints (Plan 03-05 fuel-prices) can reuse the framing without re-deriving the `data: {json}\\n\\n` shape"
  - "Error test asserts EITHER `error` event OR `partial`-status `answer` -- the actual outcome depends on which graph node raises (wrapped vs unwrapped) and the test should not couple to the internal D-24 routing topology that may evolve in Phase 5"
  - "Test fixture explicitly delenv()s CHECKPOINT_PATH on cleanup before reloading config -- Rule 1 fix during Task 2 verification; without this, importlib.reload in cleanup re-reads the still-set monkeypatched env var and the polluted module-level constant leaks into later tests"

requirements-completed: [API-01]

# Metrics
duration: 4min
completed: 2026-04-25
---

# Phase 3 Plan 04: FastAPI Chat SSE Endpoint Summary

**Stood up the FastAPI app with a lifespan-managed AsyncSqliteSaver checkpointer, compiled the graph at startup, and exposed POST /api/chat as a manually-framed SSE stream emitting D-18 envelopes (meta -> trace+ -> answer -> done) with D-19 thread_id flow. Backend test suite reports 98 passed / 5 skipped (3 new chat integration tests; +3 vs Plan 03-03 baseline; zero regressions after fixing the test-fixture env-var pollution).**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-25T04:06:59Z
- **Completed:** 2026-04-25T04:11:44Z
- **Tasks:** 2
- **Files modified:** 8 (6 created + 2 edited)

## Accomplishments

- `backend/api/main.py` boots the FastAPI app under `lifespan(app)`. The lifespan opens `aiosqlite.connect(CHECKPOINT_PATH)`, wraps it in `AsyncSqliteSaver(conn)`, calls `await checkpointer.setup()` (Pitfall 9 — idempotent table creation), exposes the saver and `build_graph(checkpointer)` on `app.state`, and tears the connection down on shutdown.
- `app.title = "Express Dynamic Surcharge Orchestrator"`, `version = "0.3.0"`, and `app.routes` includes `/api/chat` and `/health`.
- `GET /health` returns `{"status": "ok", "graph_ready": True}` once the lifespan has compiled the graph (verified via live `curl` smoke against `uvicorn`).
- `POST /api/chat` accepts `{message: str, thread_id: str | None}` (Pydantic `ChatRequest`) and returns `text/event-stream` with the D-18 envelope sequence:
  - First event: `{"type": "meta", "payload": {"thread_id": <str>}}` — server generates UUIDv4 (`uuid.uuid4()`) when client omits it (D-19).
  - One `{"type": "trace", "payload": <D-12 entry>}` event per `reasoning_trace` entry yielded by any of the five agent nodes (`planner`, `fuel_agent`, `route_agent`, `pricing_agent`, `response`).
  - One `{"type": "answer", "payload": <D-10 final_payload>}` when the `response` node emits `final_payload`.
  - On uncaught exception: `{"type": "error", "payload": {"message": str, "retryable": False}}` followed by `done`.
  - Stream ALWAYS closes with `{"type": "done", "payload": {}}`.
- Response headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive` (Pitfall 5 — prevent proxy buffering for SSE).
- `backend/api/sse.py` exposes `format_sse(event_type, payload) -> bytes` returning UTF-8 `data: {json}\n\n` framing; reused by both happy-path and error-path emissions in the chat handler.
- `backend/api/models.py` declares `ChatRequest` (Pydantic, `message` required `min_length=1`, `thread_id` optional), `SSEEvent` (informational D-18 shape), and the `ConversationSummary` + `FuelPricePoint` placeholders Plan 03-05 will populate.
- 3 passing integration tests in `backend/tests/test_api_chat.py` via FastAPI `TestClient`:
  1. `test_happy_path_sse_sequence` — full mocked stack (4 LLM seams + 3 tool seams) drives planner-loop through fuel + route + pricing + response; asserts first event is `meta` with the supplied `thread_id`, last event is `done`, an `answer` event is present with `status="ok"` + `markdown` + `surcharge_result`, and at least 4 `trace` events appeared. Verifies `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers.
  2. `test_server_generates_thread_id` — client omits `thread_id`; first SSE event MUST be a `meta` carrying a 36-char UUIDv4 with 4 hyphens.
  3. `test_error_sse_sequence` — replaces `pricing_mod.lookup_rate` with a `RuntimeError`-raising stub; asserts the stream still closes with `done` and contains either an `error` event OR a `partial`-status `answer` event (per D-23/D-24, both are valid failure-mode signals).
- Backend test suite: **98 passed, 5 skipped** (was 95 + 8 — net +3 chat tests; zero regressions in Phase 1/2 or earlier Phase 3 tests).
- Live smoke test: `uvicorn backend.api.main:app --port 8765` boots cleanly; `curl /health` returns `{"status":"ok","graph_ready":true}`; `curl /openapi.json` lists `/api/chat` and `/health` paths.

## Task Commits

1. **Task 1: FastAPI app shell + lifespan + chat models + SSE helper** — `3496479` (feat)
2. **Task 2: POST /api/chat SSE handler + 3 integration tests** — `fb942b7` (feat)

**Plan metadata commit:** _appended after this SUMMARY is written_ (docs commit covering SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md)

## Files Created/Modified

### Created
- `backend/api/__init__.py` — package marker docstring (was empty)
- `backend/api/routes/__init__.py` — routes-package marker
- `backend/api/main.py` — FastAPI app with lifespan-managed AsyncSqliteSaver + chat router include + /health endpoint
- `backend/api/models.py` — `ChatRequest`, `SSEEvent`, `ConversationSummary`, `FuelPricePoint` Pydantic models
- `backend/api/sse.py` — `format_sse(event_type, payload) -> bytes` helper
- `backend/api/routes/chat.py` — `POST /api/chat` SSE streaming handler with `astream_events("v2")` filter

### Modified
- `backend/tests/test_api_chat.py` — Replaced 3 placeholder stubs with full integration tests; removed `pytestmark = pytest.mark.skip`; added `app_with_mocks` fixture with explicit env-var cleanup
- `.gitignore` — Added `data/checkpoints.db-shm` and `data/checkpoints.db-wal` SQLite WAL/SHM sidecars (created at runtime by AsyncSqliteSaver during the uvicorn smoke test)

## Decisions Made

- **Lifespan stores BOTH checkpointer and graph on app.state** — Plan 03-05's `GET /api/conversations` will need direct access to the saver to enumerate persisted threads; just exposing the compiled graph is insufficient because `graph.aget_state(config)` only retrieves a single thread's snapshot. Exposing both lets the conversations endpoint reuse the lifespan's open connection rather than opening a second aiosqlite handle.
- **Chat handler filters `astream_events` on `on_chain_end` + node-name allow-list** — RESEARCH Pattern 4 recommended this approach over parsing every event class. `on_chain_start` would emit before the node runs (no useful payload yet) and `on_chain_stream` would fragment a single trace entry across multiple chunks. Filtering to `on_chain_end` keeps one SSE trace event per node-completion as the contract intends.
- **`format_sse()` bytes helper centralised** — Plan 03-05's `GET /api/fuel-prices` may also stream; centralising the `data: {json}\n\n` framing means there's one place to fix if D-18 evolves and one place to test for byte-level correctness.
- **Error test accepts EITHER `error` event OR `partial`-status `answer`** — A `RuntimeError` from the un-wrapped pricing node bubbles past the graph's outer `astream_events`; the chat handler's try/except converts it to an SSE `error` event. But on a wrapped node (planner / fuel / route / response) the same exception would be converted by `_wrap_error_sink` into `state.errors[]` + `next_step="respond"`, which routes through Response Node to a `partial`-status `answer`. Both are valid D-23/D-24 outcomes; coupling the test to one specific routing path would be brittle as Phase 5 may extend the wrapping.
- **Test fixture explicitly delenv()s CHECKPOINT_PATH on cleanup before reloading config** — Rule 1 deviation discovered during Task 2 verification (see Deviations below). Without the explicit `monkeypatch.delenv` + second `importlib.reload`, the polluted module-level constant leaked into later tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test-fixture env-var pollution leaked tmp-path into `test_checkpoint_path_default`**
- **Found during:** Task 2 (full backend suite run after `pytest test_api_chat.py` passed in isolation)
- **Issue:** The plan-specified `app_with_mocks` fixture used `monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "checkpoints.db"))` + `importlib.reload(backend.config)` + `importlib.reload(backend.api.main)`. While `monkeypatch.setenv` correctly restored the env var on test teardown, the in-memory `backend.config.CHECKPOINT_PATH` constant was reloaded against the polluted env DURING the test and was NEVER reloaded back. So `test_checkpoint_path_default` (which asserts `config.CHECKPOINT_PATH == "data/checkpoints.db"`) saw the tmp-path string and failed.
- **Fix:** Restructured the fixture to use `yield` semantics with an explicit cleanup block after yield: `monkeypatch.delenv("CHECKPOINT_PATH", raising=False)` followed by `importlib.reload(backend.config)` + `importlib.reload(backend.api.main)`. Pytest's monkeypatch teardown runs AFTER fixture cleanup, so without the explicit delenv the second reload would re-read the still-set env var.
- **Files modified:** `backend/tests/test_api_chat.py`
- **Verification:** `pytest backend/tests/test_api_chat.py backend/tests/test_models.py -v` -> 25 passed; full suite -> 98 passed / 5 skipped; zero regressions.
- **Committed in:** `fb942b7` (Task 2 commit)

**2. [Rule 3 - Blocking] SQLite WAL/SHM sidecar files untracked after live smoke test**
- **Found during:** Post-Task-2 manual smoke test (`uvicorn backend.api.main:app` + `curl /health`)
- **Issue:** AsyncSqliteSaver opens `data/checkpoints.db` with WAL journal mode by default, creating `data/checkpoints.db-shm` and `data/checkpoints.db-wal` sidecar files alongside the main DB. The existing `.gitignore` excluded `data/checkpoints.db` but not the sidecars, so `git status` showed two new untracked files after the smoke test.
- **Fix:** Appended `data/checkpoints.db-shm` and `data/checkpoints.db-wal` to the `# SQLite databases (generated at runtime)` block in `.gitignore`. Rationale: WAL/SHM are runtime artefacts, never meaningful to commit, and grow/shrink as transactions checkpoint.
- **Files modified:** `.gitignore`
- **Verification:** `git status --short` post-smoke shows only intended changes; sidecar files now ignored.
- **Committed in:** `fb942b7` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug + 1 Rule 3 blocking issue)
**Impact on plan:** Zero scope change. Both fixes were essential for clean test isolation and clean repo state. No retest of the 95 prior tests was needed beyond confirming no regressions; both fixes were entirely additive (new fixture cleanup logic + new gitignore patterns).

## Issues Encountered

- None beyond the 2 deviations above. Both surfaced during the verification phase of Task 2 and were resolved inline.

## User Setup Required

None — all tests use `FakeMessagesListChatModel` and direct attribute monkeypatching for tools; no live Gemini, EPPO, or Google Maps quota consumed. The lifespan creates the checkpoint DB automatically; no manual seeding required for the chat endpoint to function.

## Next Phase Readiness

- **Plan 03-05 (conversations + fuel-prices)** can immediately attach two new routers to `app.include_router(...)`. The lifespan already exposes `app.state.checkpointer`, so `GET /api/conversations` can iterate persisted threads via `await app.state.checkpointer.alist(config={"configurable": {}}, limit=50)`. `GET /api/fuel-prices` reads `data/raw/eppo_diesel_prices.csv` directly with no graph involvement.
- **Frontend chat component** can `POST /api/chat` with `fetch(..., { headers: {Accept: "text/event-stream"} })` and parse `data: {json}\n\n` lines. The first `meta` event yields `thread_id` for persistence in localStorage; subsequent `trace` events drive the reasoning panel; the `answer` event renders the final markdown; `done` closes the stream cleanly.
- **D-18 envelope is locked** — every type/payload pair across the four phases that touch the chat endpoint (Plan 03-05 fuel-prices stream if added; Phase 4 frontend; Phase 5 enhancement waves) must conform.
- **D-19 thread_id flow is locked** — server generates UUIDv4 when client omits; same `thread_id` reuses checkpointed state across requests (verified end-to-end in Plan 03-03 Test 5/7 and reachable through this plan's TestClient flow).
- **Pitfall 5 + Pitfall 9 both prevented** — manual SSE framing avoids the `EventSourceResponse` import that doesn't exist in FastAPI 0.128.8; lifespan calls `setup()` before any request runs.

## Self-Check: PASSED

All claims verified:
- Created files exist:
  - `backend/api/__init__.py` FOUND
  - `backend/api/main.py` FOUND
  - `backend/api/models.py` FOUND
  - `backend/api/sse.py` FOUND
  - `backend/api/routes/__init__.py` FOUND
  - `backend/api/routes/chat.py` FOUND
- Modified files updated: 2/2 (`backend/tests/test_api_chat.py`, `.gitignore`)
- Commits in history: `3496479` (Task 1), `fb942b7` (Task 2) — both verified via `git log --oneline -3`
- Test suite: 98 passed, 5 skipped (verified post-Task-2; +3 active tests vs Plan 03-03 baseline of 95)
- Imports succeed: `from backend.api.main import app` -> `app.title == "Express Dynamic Surcharge Orchestrator"`
- Acceptance grep checks: all 10 grep-based checks pass (class ChatRequest=1, class SSEEvent=1, def format_sse=1, lifespan=3, AsyncSqliteSaver=5, checkpointer.setup()=1, app.state.graph=1, from backend.api.routes.chat import router=1, @router.post /api/chat=1, version=v2=1, X-Accel-Buffering=1, Cache-Control=1, uuid.uuid4=1, format_sse usages>=5, pytestmark skip removed=0, 3 test names matched=3)
- Live smoke: uvicorn boots, /health returns `{"status":"ok","graph_ready":true}`, /openapi.json lists `/api/chat` + `/health`

---
*Phase: 03-graph-assembly-api-layer*
*Completed: 2026-04-25*
