---
phase: 05-polish-observability-docs
plan: 03
subsystem: orchestration
tags: [langgraph, parallel, fan-out, send-api, conditional-edges, orch-07]

requires:
  - phase: 04-app-composition-trace-mvp
    provides: Phase 4 backend pipeline (planner, fuel, route, pricing, response) with operator.add reducers on reasoning_trace + errors and Phase 3 D-22/D-23/D-24 retry topology
  - phase: 05-polish-observability-docs
    provides: Phase 5 Plan 01 — AgentState v3 fields (approval_decision, search_context); no direct dependency on Plan 02 — orthogonal Wave 2 sibling
provides:
  - "fanout_fuel_route" sentinel set by planner_node when both fuel + route caches stale and all 4 extraction fields present
  - Graph router (_route_from_planner) returns ["fuel_agent", "route_agent"] for that sentinel — schedules same-superstep parallel execution
  - 4 integration tests in test_parallel_fanout.py asserting D-01 fan-out, trace overlap (<1.0s), D-12 cache-skip precedence, D-03/D-24 error sink resilience
  - 5 new planner unit tests covering fan-out promotion conditions
affects: [05-04-search-agent, 05-05-hitl-gate, 05-06-feedback-frontend, 05-07-docs]

tech-stack:
  added: []
  patterns:
    - "List-returning conditional edge: returning list[str] from _route_from_planner schedules every named node in the same Pregel superstep — the 1-line ORCH-07 win"
    - "operator.add reducers (Phase 2 Pitfall 1, Phase 3 D-05) carry parallel writes safely without per-branch state slicing"
    - "Cache-precedence-first promotion: fan-out only fires when BOTH fuel and route are stale; D-12 cache-skip cascade still wins on follow-up turns"

key-files:
  created:
    - backend/tests/test_parallel_fanout.py
  modified:
    - backend/agent/graph.py
    - backend/agent/nodes/planner.py
    - backend/tests/test_planner.py
    - backend/tests/test_graph.py

key-decisions:
  - "List-returning conditional edge over Send API — reading the same state keys means dynamic per-branch state slicing buys nothing; list return is the smaller, safer change"
  - "Sentinel-based promotion (fanout_fuel_route) keeps PlannerOutput.next_step Literal unchanged — Phase 5 router-only escape hatch"
  - "Pre-conditions on promotion (4 extraction fields + both caches stale) preserve Phase 3 D-12 cache-skip precedence; cache-fresh follow-ups continue running sequentially"
  - "No new reducers introduced — D-02 invariant honored; reasoning_trace and errors operator.add already handle concurrent appends"

patterns-established:
  - "Phase 5 routing extensions go through _route_from_planner sentinels (matched explicitly before the str.get fallback) — keeps PlannerOutput schema additive-only"
  - "Test scripts that assumed sequential 4-step turn 1 (fetch_fuel, fetch_route, calculate_price, respond) drop one planner response under Phase 5 — fan-out collapses 2 LLM hops into 1"

requirements-completed:
  - ORCH-07

duration: 7min
completed: 2026-05-02
---

# Phase 5 Plan 03: Parallel Fan-out (ORCH-07) Summary

**LangGraph list-returning conditional edge schedules fuel_agent and route_agent in the same Pregel superstep on a fresh thread; trace timestamp delta measured at ~165 microseconds — visible parallelism with zero new reducers.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-02T17:25:45Z
- **Completed:** 2026-05-02T17:32:09Z
- **Tasks:** 2
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `_route_from_planner` in `backend/agent/graph.py` recognizes the new `fanout_fuel_route` sentinel and returns `["fuel_agent", "route_agent"]`. LangGraph's list-returning conditional edge schedules both nodes in the same superstep — the ORCH-07 win in 1 line of routing code.
- `planner_node` adds a Phase 5 D-01 promotion block before the existing D-12 cache-skip cascade: when the LLM emits `fetch_fuel`/`fetch_route`, BOTH fuel and route caches are stale, AND all 4 extraction fields are present, `next_step` is promoted to `fanout_fuel_route`. Sequential cache-skip paths preserved for all other states.
- 4 new integration tests in `backend/tests/test_parallel_fanout.py` covering fresh-thread fan-out, trace timestamp overlap (<1.0s contract), cache-skip precedence on follow-ups, and one-branch-fails resilience via D-24 error sink.
- 5 new planner unit tests covering promotion trigger and counter-cases.
- Trace timestamp delta on the parallel turn measured at **0.000165 seconds** — about 165 microseconds, well within the <1.0s ROADMAP success criterion. Demo evidence is real, not aspirational.
- Full backend test suite green: 132 tests passing (previously 117 — 15 new, including 4 fan-out integration + 5 planner + 6 from Plan 02 wiring landing alongside).

## Task Commits

1. **Task 1 (RED): planner fan-out tests** — `af68208` (test)
2. **Task 1 (GREEN): planner fan-out promotion** — `272fd8d` (feat)
3. **Task 2 (RED): integration tests** — `502e1dc` (test)
4. **Task 2 (GREEN): graph router list return** — `46f8618` (feat)

_TDD: 2 tasks × (RED, GREEN) — no REFACTOR commits required; both implementations were minimal._

## Files Created/Modified
- `backend/agent/graph.py` (modified) — `_route_from_planner` returns `["fuel_agent", "route_agent"]` when `state.next_step == "fanout_fuel_route"`; signature changed to return `Union[str, List[str]]`. No edge map changes (target nodes already mapped).
- `backend/agent/nodes/planner.py` (modified) — Phase 5 D-01 promotion block inserted before D-12 cache-skip cascade. Sentinel `fanout_fuel_route` set when LLM emits fetch_fuel/fetch_route + both caches stale + all 4 fields present. Trace `tool_output` automatically reflects the post-override `next_step` (999.3 fix invariant preserved).
- `backend/tests/test_parallel_fanout.py` (created, 414 lines) — 4 integration tests with shared `_stateful_factory` + `_planner_response` helpers mirroring `test_graph.py` conventions.
- `backend/tests/test_planner.py` (modified) — 5 new fan-out tests appended; 4 pre-existing tests adapted to Phase 5 contract (`fetch_fuel` → `fanout_fuel_route` on fresh-thread complete-input states).
- `backend/tests/test_graph.py` (modified) — `test_followup_param_switch_routes_through_pricing` turn-1 planner script reduced from 4 → 3 responses; under Phase 5 the first `fetch_fuel` emission promotes to `fanout_fuel_route`, collapsing 2 sequential planner re-entries into 1.

## Decisions Made

**1. List-returning conditional edge over Send API.** The dynamic Send API requires fabricating per-branch state slices; both fuel_agent and route_agent read the SAME state keys (`origin`, `destination`, `messages`), so state slicing adds no value. The list return is the minimal change that achieves same-superstep scheduling — recommended in 05-RESEARCH §Pattern 1.

**2. Sentinel-based promotion (`fanout_fuel_route`) instead of new Literal value.** Keeps `PlannerOutput.next_step` Literal stable (the LLM continues to emit `fetch_fuel` / `fetch_route`); the router promotes based on cache state. Avoids retraining Gemini's prompt for a routing-only concept the LLM doesn't need to understand.

**3. Pre-conditions enforce D-12 cache-skip precedence.** Promotion fires only when BOTH `_fuel_fresh(state) is False` AND `_route_matches(state, ...) is False` AND all four extraction fields present. Cache-warm follow-ups continue running through the sequential cache-skip cascade (Phase 3 D-12). Verified by `test_cache_hit_skips_fanout` which asserts `fuel_calls == 1` and `route_calls == 1` after turn 2.

**4. No new reducers introduced (D-02 invariant).** `operator.add` on `reasoning_trace` and `errors` (Phase 2 Pitfall 1, Phase 3 D-05) handles concurrent appends from the parallel branches. `fuel_data` and `route_data` are scalar dict keys written by disjoint branches — last-write-wins is correct because no branch touches the other's key.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] 4 pre-existing planner tests adapted to Phase 5 contract**
- **Found during:** Task 1 (after GREEN implementation)
- **Issue:** `test_routes_to_fetch_fuel_on_fresh_query`, `test_loop_budget_resets_after_response_entry`, `test_followup_merges_prior_state_promotes_clarify_to_fetch`, `test_trace_tool_output_reflects_merged_inherited_fields` all asserted `next_step == "fetch_fuel"` for state shapes that, under Phase 5 D-01, now correctly promote to `fanout_fuel_route` (no caches + 4 fields present).
- **Fix:** Updated each assertion to expect `fanout_fuel_route`. Comments in each test explain the Phase 5 promotion path.
- **Files modified:** `backend/tests/test_planner.py`
- **Verification:** All 15 planner tests pass.
- **Committed in:** `272fd8d` (Task 1 GREEN commit)

**2. [Rule 1 — Bug] `test_followup_param_switch_routes_through_pricing` turn-1 script collapsed**
- **Found during:** Task 2 (full-suite regression check)
- **Issue:** Test scripted 4 planner LLM responses for turn 1 (`fetch_fuel`, `fetch_route`, `calculate_price`, `respond`). Under Phase 5 the first `fetch_fuel` is promoted to `fanout_fuel_route` and the cache-skip cascade collapses the next two responses into one effective `calculate_price` outcome. The leftover script entry caused pricing to run twice in turn 1 (`lookup_calls == 2`, expected 1).
- **Fix:** Removed the redundant `fetch_route` response from turn-1 script; turn 1 now needs 3 responses (`fetch_fuel` → fanout, `calculate_price`, `respond`). Comment in test explains the Phase 5 collapsing.
- **Files modified:** `backend/tests/test_graph.py`
- **Verification:** Test passes; `lookup_calls == 1` after turn 1 and `== 2` after turn 2 (rate re-looked-up because shipping_type changed).
- **Committed in:** `46f8618` (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — pre-existing tests adapted to reflect the Phase 5 contract change ORCH-07 introduced).
**Impact on plan:** Both adaptations were strictly necessary — the underlying behavior is correct under Phase 5; only the test assertions encoded the pre-Phase-5 sequential flow. No scope creep, no new functionality.

## Issues Encountered
None — RED-then-GREEN cycle uncovered the test deviations cleanly. Trace overlap measurement confirmed the parallel scheduling actually works at the Pregel layer, not just on paper.

## Step-Collision Note (RESEARCH §Pitfall 4)

Both `fuel_agent_node` and `route_agent_node` compute their `step` value as `len(state.get("reasoning_trace") or []) + 1` independently. When they run in the same superstep they BOTH read the same prior length and BOTH emit `step=N+1` — duplicate step numbers in the merged trace. This is intended: the UI sorts the trace panel by `timestamp`, not `step`, so duplicates render correctly in chronological order. Documented for downstream agents (the trace panel in 04-04 already uses timestamp-sort).

## Trace Overlap Evidence (ROADMAP §Phase 5 success criterion 1)

Captured during a manual ainvoke run with mocked tools and FakeMessagesListChatModel:

```
fuel_agent ts:  2026-05-02T17:31:29.323211Z
route_agent ts: 2026-05-02T17:31:29.323376Z
delta_s: 0.000165
```

165 microseconds between the two agent timestamps on the parallel turn — well within the 1-second contract and visibly parallel under any timestamp-sorted UI view.

## Next Phase Readiness
- Wave 3 plans (05-04 search agent, 05-05 HITL gate) can land on top of this without further routing changes — they extend the conditional-edge map with new sentinels, not the fan-out shape.
- The Phase 5 Langfuse callback (Plan 02, Wave 2 sibling) automatically captures the parallel branches because it registers at the `graph.compile()` boundary; one Langfuse trace per chat turn now contains overlapping spans for fuel_agent and route_agent — visible in the dashboard for graders.

## Self-Check: PASSED

- `backend/agent/graph.py` exists with `["fuel_agent", "route_agent"]` list return — verified
- `backend/agent/nodes/planner.py` contains `fanout_fuel_route` sentinel set — verified
- `backend/tests/test_parallel_fanout.py` exists with 4 named tests — verified
- Commits `af68208`, `272fd8d`, `502e1dc`, `46f8618` all present in git log — verified
- Full backend suite (`pytest backend/tests/ -q`) exits 0 — verified

---
*Phase: 05-polish-observability-docs*
*Completed: 2026-05-02*
