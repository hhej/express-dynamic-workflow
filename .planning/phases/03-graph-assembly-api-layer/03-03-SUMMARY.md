---
phase: 03-graph-assembly-api-layer
plan: 03
subsystem: graph-assembly
tags: [langgraph, retry-policy, checkpointer, state-graph, d-22, d-23, d-24, d-12, orch-08, orch-10]

# Dependency graph
requires:
  - phase: 03-graph-assembly-api-layer
    plan: 01
    provides: AgentState v2 (origin/destination/user_intent/missing_fields/clarification_reason/errors), in_memory_checkpointer fixture
  - phase: 03-graph-assembly-api-layer
    plan: 02
    provides: planner_node (D-12 cache override), fuel_agent_node (D-13 fetched_at), route_agent_node (D-13 fetched_at), pricing_agent_node (D-09 ValueError contract), response_node (D-10 final_payload)
provides:
  - build_graph(checkpointer) factory compiling 5-node StateGraph with D-03 planner-loop topology
  - phase3_retry_on(exc) D-23 retry filter (httpx.HTTPError, httpx.TimeoutException, asyncio.TimeoutError, ResourceExhausted, GMapsHTTPError; nothing else)
  - D-22 RetryPolicy(max_attempts=2, backoff_factor=2.0, initial_interval=1.0, jitter=True) on every node
  - D-24 _wrap_error_sink that re-raises retryable exceptions until max_attempts is hit, then converts to state.errors append + next_step='respond'
  - AgentState.final_payload field (Optional[dict]) so response_node output survives StateGraph(AgentState) merge
  - planner_node short-circuit on state.errors -> next_step='respond' (prevents planner-loop on persistent failure)
  - 7 ainvoke-based integration tests proving ORCH-08 + ORCH-10 + D-12 cache reuse end-to-end
affects: [03-04-api-chat, 03-05-api-conversations]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RetryPolicy + error-sink wrapper interplay: wrapper must re-raise retryable exceptions for LangGraph to apply RetryPolicy; only convert to error sink AFTER max_attempts is reached"
    - "Per-state attempt counter keyed on id(state): Pregel reuses the same state dict across retries of one task, so id() is a stable per-attempt-set key"
    - "Planner errors short-circuit (D-24 + D-03 reconciliation): planner checks state.errors first and routes to respond before consuming a Gemini call -- preserves planner-loop topology while honoring error sink"
    - "FakeMessagesListChatModel test pattern: a SHARED instance must be returned by get_chat_model factory so cycling through scripted responses works across multiple node invocations (lambda-per-call resets to response[0])"
    - "AgentState.final_payload: response-node output must be a TypedDict field for StateGraph(AgentState) to persist it; otherwise LangGraph drops keys absent from the schema"

key-files:
  created:
    - backend/agent/graph.py
  modified:
    - backend/agent/__init__.py
    - backend/agent/state.py
    - backend/agent/nodes/planner.py
    - backend/tests/test_graph.py

key-decisions:
  - "_wrap_error_sink uses per-state attempt counter (id(state)) to re-raise transient errors until max_attempts is reached -- without this RetryPolicy never sees the exception and tests of D-22 retry behavior fail"
  - "Pricing Agent node intentionally NOT wrapped in error sink -- D-09 mandates ValueError from lookup_rate must bubble uncaught; the wrapper would re-raise ValueError anyway, but skipping the wrap removes a stack frame and makes test failure clearer"
  - "Planner short-circuits on state.errors BEFORE the loop-budget guard and BEFORE any Gemini call -- ensures error sink output survives one round-trip back through planner without being overwritten by a fresh LLM emission"
  - "AgentState.final_payload added as TypedDict field rather than reusing surcharge_result -- keeps the SSE handler signal (Plan 03-04 will detect via astream_events) decoupled from the pricing tool output and lets the response_node return the same key for partial/clarify paths"

requirements-completed: [ORCH-08, ORCH-10]

# Metrics
duration: 7min
completed: 2026-04-25
---

# Phase 3 Plan 03: Graph Assembly Summary

**Wired the 5 nodes (planner, fuel_agent, route_agent, pricing_agent, response) into a LangGraph StateGraph with D-22 RetryPolicy, D-23 custom retry filter, D-24 error-sink wrappers, and AsyncSqliteSaver checkpointer integration. Backend test suite reports 95 passed / 8 skipped (7 new graph integration tests across ORCH-08 retry topology + ORCH-10 checkpointer + D-12 cache reuse end-to-end).**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-25T03:54:21Z
- **Completed:** 2026-04-25T04:02:15Z
- **Tasks:** 2
- **Files modified:** 5 (1 created + 4 edited)

## Accomplishments

- `build_graph(checkpointer)` factory in `backend/agent/graph.py` (~190 lines) compiles a 5-node StateGraph with D-03 planner-loop topology: `START -> planner`; planner conditional edges to `fuel_agent | route_agent | pricing_agent | response`; specialists return to planner; `response -> END`. `recursion_limit=12` (D-04 belt-and-braces under business cap N=6).
- `phase3_retry_on(exc)` callable in `backend/agent/graph.py` enforces the D-23 allow-list. Returns `True` only for `httpx.HTTPError`, `httpx.TimeoutException`, `asyncio.TimeoutError`, `google.api_core.exceptions.ResourceExhausted`, `googlemaps.exceptions.HTTPError`. Returns `False` for `ValueError`, `pydantic.ValidationError`, `RuntimeError`, generic `Exception`. Test 1 verifies the matrix.
- `RetryPolicy(max_attempts=2, backoff_factor=2.0, initial_interval=1.0, jitter=True, retry_on=phase3_retry_on)` applied on all five nodes (D-22).
- `_wrap_error_sink(node_name, node_fn)` wraps `planner`, `fuel_agent`, `route_agent`, `response`. The wrapper re-raises retryable exceptions on the first attempt so LangGraph's Pregel runtime can apply `RetryPolicy`; on the second attempt (max_attempts reached) it converts the exception to a `state.errors` append + `next_step="respond"`. `pricing_agent_node` is intentionally NOT wrapped per D-09 (`ValueError` from `lookup_rate` must bubble uncaught).
- `pricing_agent_node` ValueError contract preserved end-to-end: the unwrapped pricing node lets ValueError propagate; the planner's clarify path picks it up on the next loop iteration.
- `planner_node` short-circuit on `state.errors`: when the error sink writes errors[] and routes back to planner per D-03 topology, the planner immediately returns `next_step="respond"` without consuming a Gemini call. This reconciles D-03 (loop topology) with D-24 (error sink force-respond).
- `AgentState.final_payload: Optional[dict]` field added so `response_node`'s D-10 payload survives `StateGraph(AgentState)` reduction (LangGraph drops keys absent from the schema).
- `backend/agent/__init__.py` exports `build_graph` for import as `from backend.agent import build_graph`.
- 7 ainvoke-based integration tests in `backend/tests/test_graph.py`:
  1. `test_value_error_skips_retry` — phase3_retry_on returns False on ValueError/RuntimeError, True on httpx classes.
  2. `test_retry_policy_retries_httpx_error` — flaky fetch (HTTPError once, then success); asserts call_counter == 2 (1 retry).
  3. `test_retry_exhaustion_routes_to_response_partial` — persistent HTTPError; asserts state.errors[0] populated AND final_payload.status == "partial".
  4. `test_checkpointer_persists_across_invocations` — AsyncSqliteSaver round-trip on thread_id=t1; aget_state retrieves fuel/route data.
  5. `test_followup_reuses_cached_fuel` — turn 1 populates cache; turn 2 (same thread_id) only emits calculate_price; fuel_calls counter stays at 1 (D-12 verified end-to-end).
  6. `test_full_surcharge_query_integration` — full happy path; final_payload.markdown contains all 4 D-11 row labels.
  7. `test_followup_only_runs_pricing` — both fuel AND route caches reused on follow-up; both counters stay at 1.
- Full backend test suite: **95 passed, 8 skipped** (was 88 + 15 — net +7 from converted graph placeholders, zero regressions).

## Task Commits

1. **Task 1: build_graph factory + phase3_retry_on filter** — `f4e80e6` (feat)
2. **Task 2: 7 graph integration tests + retry-topology fixes** — `716505e` (test)

**Plan metadata commit:** _appended after this SUMMARY is written_ (docs commit covering SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md)

## Files Created/Modified

### Created
- `backend/agent/graph.py` — `build_graph()` factory + `phase3_retry_on()` filter + `_wrap_error_sink()` helper + `_route_from_planner()` conditional edge selector

### Modified
- `backend/agent/__init__.py` — Replaced empty file with `from backend.agent.graph import build_graph` export
- `backend/agent/state.py` — Appended `final_payload: Optional[dict]` field to AgentState (Rule 1 deviation; needed for response_node output to survive merge)
- `backend/agent/nodes/planner.py` — Added `if state.get("errors"): return {"next_step": "respond"}` guard at top of `planner_node` BEFORE the D-04 loop-budget guard (Rule 3 deviation; prevents planner-loop on persistent error)
- `backend/tests/test_graph.py` — Removed `pytestmark = pytest.mark.skip` and replaced 7 placeholder stubs with full integration tests; added `_stateful_factory` helper

## Decisions Made

- **`_wrap_error_sink` per-state attempt counter** — The plan specified a simple try/except wrapper, but that pattern catches exceptions BEFORE LangGraph's Pregel runtime can apply RetryPolicy, so D-22 retries never happen. The fix re-raises retryable exceptions on the first attempt and only converts to the error-sink path on attempt 2 (matching `max_attempts=2`). Per-attempt-set state is keyed on `id(state)` because Pregel reuses the same state dict across retries of one task. Cited in module docstring: https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574
- **Pricing Agent NOT wrapped in error sink** — D-09 mandates `ValueError` from `lookup_rate` must bubble uncaught. Wrapping pricing would still re-raise ValueError correctly, but skipping the wrap removes a stack frame and makes test failure clearer. The pricing node has `retry_policy=retry` applied directly without the wrapper.
- **Planner short-circuits on state.errors** — Without this, after fuel_agent's error sink routes back to planner per D-03 topology, the planner emits a fresh LLM-driven `next_step` (e.g., `fetch_fuel` again) and the graph loops until `recursion_limit=12`. The short-circuit honors D-03 (specialists -> planner -> next decision) AND D-24 (errors trigger respond) by making the planner's "next decision" be "respond" when errors are present.
- **`AgentState.final_payload` as TypedDict field** — The plan implicitly assumed `final_payload` would survive the StateGraph merge, but LangGraph drops keys absent from `AgentState`. Adding the field is a one-line addition that keeps Plan 03-04's SSE astream_events handler decoupled from the pricing tool output.
- **`_stateful_factory` test helper** — `lambda **_: _scripted_llm(...)` re-instantiates a fresh `FakeMessagesListChatModel` on every `get_chat_model` call, replaying only `responses[0]`. Planner-loop scripting requires a shared instance that cycles through the response list across multiple invocations. The helper is local to test_graph.py (not added to conftest.py since the planner/fuel/route tests work with the simpler pattern — they only invoke each node once).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_wrap_error_sink` short-circuited RetryPolicy**
- **Found during:** Task 2 (test_retry_policy_retries_httpx_error first run)
- **Issue:** The plan-specified wrapper caught ALL non-ValueError Exceptions and converted them to error-sink returns. This prevented LangGraph's Pregel runtime from ever seeing retryable exceptions, so `RetryPolicy.retry_on=phase3_retry_on` never engaged. Test 2 expected `call_counter == 2` (1 original + 1 retry) but got 1.
- **Fix:** Rewrote `_wrap_error_sink` to track per-state attempt count (keyed on `id(state)`) and re-raise retryable exceptions until `max_attempts=2` is reached. Only on the final attempt does the wrapper fall through to the error-sink path. Documented the pattern in the wrapper docstring with a citation to the LangChain forum thread on retry-exhaustion control flow.
- **Files modified:** `backend/agent/graph.py`
- **Verification:** Tests 2 (retry succeeds) and 3 (retry exhausts) both pass.
- **Committed in:** `716505e` (Task 2 commit)

**2. [Rule 3 - Blocking] Planner-loop on persistent error sink output**
- **Found during:** Task 2 (test_retry_exhaustion_routes_to_response_partial first run after deviation 1 fix)
- **Issue:** After fuel_agent's error sink wrote `next_step="respond"` + `errors[]`, control returned to the planner per D-03 topology. The planner then emitted `fetch_fuel` again (fresh LLM call), looping until `GraphRecursionError: recursion_limit=12`. The error sink output was effectively overwritten by every subsequent planner call.
- **Fix:** Added `if state.get("errors"): return {"next_step": "respond"}` short-circuit at the top of `planner_node`, before the D-04 loop-budget guard and before any Gemini call. This honors D-03 (loop topology preserved) AND D-24 (errors trigger respond) without requiring conditional edges from each specialist.
- **Files modified:** `backend/agent/nodes/planner.py`
- **Verification:** Test 3 now reaches Response Node and `final_payload.status == "partial"` succeeds.
- **Committed in:** `716505e` (Task 2 commit)

**3. [Rule 1 - Bug] `AgentState` missing `final_payload` field**
- **Found during:** Task 2 (test_retry_exhaustion_routes_to_response_partial after deviations 1 + 2)
- **Issue:** `response_node` returns `{"final_payload": ...}` but `AgentState` (TypedDict) had no such field. `StateGraph(AgentState)` enforces the schema and silently drops keys absent from it, so `result["final_payload"]` was always `None`. Plan 03-04's SSE handler will need this key to detect the final response chunk via `astream_events`.
- **Fix:** Appended `final_payload: Optional[dict]` to `AgentState` with a docstring citing D-10 (response payload shape) and the Plan 03-04 SSE detection use case. Updated `_empty_state` test helper to include `"final_payload": None`.
- **Files modified:** `backend/agent/state.py`, `backend/tests/test_graph.py`
- **Verification:** All 7 graph tests pass; full backend suite still 95 passed / 8 skipped (no regressions in the 14 active node tests that construct AgentState dicts manually — they don't reference final_payload, so adding an Optional field is backward-compat).
- **Committed in:** `716505e` (Task 2 commit)

**4. [Rule 3 - Blocking] Test scripting required shared `FakeMessagesListChatModel`**
- **Found during:** Task 2 (test_retry_policy_retries_httpx_error first run)
- **Issue:** Planner-loop tests require the planner LLM to play back DIFFERENT responses across multiple invocations within one ainvoke. The plan-specified `lambda **_: _scripted_llm(*responses)` instantiates a fresh `FakeMessagesListChatModel` on every `get_chat_model` call, which always replays `responses[0]` because each instance starts at index 0. The planner only ever saw the first response.
- **Fix:** Added `_stateful_factory(*responses_json)` helper local to `test_graph.py` that creates ONE shared `FakeMessagesListChatModel` and returns the same instance on every factory call. The shared instance cycles through its response list across invocations, enabling planner-loop scripting (e.g., `[fetch_fuel, fetch_route, calculate_price, respond]` for the 4-step happy path).
- **Files modified:** `backend/tests/test_graph.py`
- **Verification:** Tests 2-7 all script multi-turn planner output correctly.
- **Committed in:** `716505e` (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (2 Rule 1 bugs + 2 Rule 3 blocking issues)
**Impact on plan:** Zero scope change — the deliverable matches plan intent (working build_graph with D-22/D-23/D-24 + 7 passing integration tests). All four issues surfaced as the first ainvoke ran end-to-end and were essential for the retry topology to actually function. RESEARCH should be updated with the per-state attempt-counter pattern when Phase 3 is summarized at phase-transition.

## Issues Encountered

- None beyond the 4 deviations above. All surfaced during integration testing and were resolved inline within Task 2.

## User Setup Required

None — all tests use `FakeMessagesListChatModel` and `mocker.patch.object` for tools; no live Gemini, EPPO, or Google Maps quota consumed. The `in_memory_checkpointer` fixture from Plan 03-01 provides isolated AsyncSqliteSaver instances backed by `:memory:` SQLite.

## Next Phase Readiness

- **Plan 03-04 (chat SSE)** can immediately wire the FastAPI `POST /api/chat` endpoint. The graph is ainvocable with `config={"configurable": {"thread_id": ...}}` and `astream_events` will surface every node's output. The SSE handler can detect the terminal chunk by filtering on the presence of `final_payload` in the event payload.
- **Plan 03-05 (conversations)** can use `graph.aget_state(config)` to retrieve any thread_id's snapshot for the `GET /api/conversations` endpoint. The AgentState schema is final after this plan (final_payload added).
- **D-12 cache reuse is proven end-to-end**: Test 5 + Test 7 both demonstrate that follow-up turns on the same thread_id skip fetch_fuel (and fetch_route when origin/destination match), saving Google Maps and EPPO quota.
- **D-22 + D-23 + D-24 retry topology is proven end-to-end**: Test 2 (retry succeeds), Test 3 (retry exhausts -> partial), Test 1 (filter unit) cover the matrix.
- **AgentState v3 finalised** for Phase 3: 15 fields total (`messages`, `fuel_data`, `route_data`, `shipping_type`, `weight_kg`, `surcharge_result`, `reasoning_trace`, `next_step`, `origin`, `destination`, `user_intent`, `missing_fields`, `clarification_reason`, `errors`, `final_payload`).

## Self-Check: PASSED

All claims verified:
- Created files exist:
  - `backend/agent/graph.py` FOUND
- Modified files updated: 4/4 (`__init__.py`, `state.py`, `planner.py`, `test_graph.py`)
- Commits in history: `f4e80e6` (Task 1), `716505e` (Task 2) — both verified via `git log --oneline -3`
- Test suite: 95 passed, 8 skipped (verified post-Task-2; +7 active tests vs Plan 03-02 baseline of 88)
- Imports succeed: `build_graph`, `phase3_retry_on` both importable from `backend.agent.graph`
- Acceptance grep checks: all 14 grep-based checks across both tasks return expected counts (build_graph=1, phase3_retry_on=1, RetryPolicy=5, max_attempts=2 appears 2x, backoff_factor=2.0=1, initial_interval=1.0=1, retry_on=phase3_retry_on=1, recursion_limit.*12=2, pytestmark skip removed=0, 7 test names matched, in_memory_checkpointer=8, @pytest.mark.asyncio=6)
- Build smoke test: `from backend.agent import build_graph; build_graph()` exits 0
- Retry filter unit smoke: `phase3_retry_on(httpx.HTTPError("x")) is True; phase3_retry_on(ValueError("x")) is False` exits 0

---
*Phase: 03-graph-assembly-api-layer*
*Completed: 2026-04-25*
