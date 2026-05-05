---
phase: 05-polish-observability-docs
plan: 10
subsystem: agent
tags: [planner, response_node, search_agent, langgraph, observability, gap-closure]

# Dependency graph
requires:
  - phase: 05-04
    provides: search_agent_node + search_context state field + D-09 cache-aware override bypass at planner.py line 263
  - phase: 05-08
    provides: gap-1 followup_query inheritance branch + SYSTEM_PROMPT inheritance paragraph (must be preserved)
provides:
  - "Planner early-return guard: short-circuits to next_step='respond' when state.search_context populated AND user_intent in {news_query, out_of_scope}, BEFORE Gemini call"
  - "PlannerOutput.user_intent Literal extended with 'news_query' value"
  - "SYSTEM_PROMPT documents news_query as dedicated user_intent for fuel/market questions, distinct from out_of_scope"
  - "Response node 'search_only' status branch: renders 'Here's the latest market context.' prose when search_context populated and no surcharge_result"
  - "Status precedence updated: errors > search_only > clarify > ok > clarify(fallback)"
  - "Minimal trace entry on planner short-circuit so observability shows 'planner ran twice, second was a short-circuit'"
affects: [observability-demo, langfuse-traces, parallel-demo, news-query-flow, UAT-test-6]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Idempotent guard pattern: pre-LLM short-circuit when downstream node has already produced the requested output"
    - "Status precedence chain extension: insert new status BEFORE existing fallback to preserve old behaviour"

key-files:
  created: []
  modified:
    - "backend/agent/nodes/planner.py — gap-3 early-return guard between D-24 errors short-circuit and D-04 budget guard; PlannerOutput Literal extended with news_query"
    - "backend/agent/prompts/planner.py — news_query intent documented in user_intent values block AND JSON schema example; Plan 05-08 followup_query inheritance paragraph preserved"
    - "backend/agent/nodes/response_node.py — new status='search_only' branch with deterministic news prose; status precedence chain extended; D-11 Market context blockquote prefix preserved"
    - "backend/tests/test_planner.py — 3 new unit tests (early-return for out_of_scope, early-return for news_query, no short-circuit for surcharge_query)"
    - "backend/tests/test_response_node.py — 2 new unit tests (search-only flow, defensive against budget-exhausted regression)"
    - "backend/tests/test_graph.py — 1 new integration test (UAT test 6 reproducer; planner_count==2, search_agent_count==1, no clarify prose)"

key-decisions:
  - "Early-return guard accepts BOTH 'news_query' AND 'out_of_scope' for backward compatibility — today's LLM still emits out_of_scope before being retrained on the updated SYSTEM_PROMPT; the prompt update encourages news_query for future invocations"
  - "Guard placement: between D-24 errors short-circuit (line 159) and D-04 budget guard (line 196) — fires BEFORE budget can exhaust on the second planner re-entry"
  - "Minimal trace entry emitted by the early-return so planner_count==2 in the integration test (one normal step + one short-circuit step) — informative for Langfuse demos showing 'planner ran twice, second was a short-circuit'"
  - "search_only status precedence sits BEFORE clarify so the news prose wins even if a future regression sets clarification_reason='planner_loop_budget_exhausted' (defensive against re-introduction of the loop bug)"
  - "Errors still take precedence over search_only (status='partial' > status='search_only') so a Tavily failure path that left search_context as a graceful-warn dict AND populated state.errors still renders the partial-error prose, not news prose"
  - "Plan 05-04 D-09 cache-aware override bypass at line 263 (`if next_step != 'search_context':`) preserved — gap-3's early-return at the TOP of planner_node and the existing D-09 bypass later in the function are independent and both required"
  - "Plan 05-08 gap-1 followup_query inheritance branch and SYSTEM_PROMPT paragraph preserved unchanged — gap-3 only ADDS to planner.py and prompts/planner.py, never overwrites prior content"

patterns-established:
  - "Pre-LLM short-circuit guard: when state already encodes the answer to a downstream node's question, return BEFORE calling the LLM (Langfuse cost saving + observable trace entry)"
  - "Status branch insertion: new status values insert into the precedence chain BEFORE the catch-all 'clarify' fallback to preserve all prior contracts"

requirements-completed:
  - TOOL-05
  - ORCH-01

# Metrics
duration: ~15min
completed: 2026-05-03
---

# Phase 05 Plan 10: gap-3 News Query Loop + Misleading Clarify Prose Fix Summary

**Planner short-circuits to respond when search_agent already populated search_context (preventing 5x LLM re-routing loop) AND response_node renders deterministic news prose instead of misleading 'I need a bit more information' clarify text**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-03T11:30:00Z (approx)
- **Completed:** 2026-05-03T11:45:00Z (approx)
- **Tasks:** 2
- **Files modified:** 6 (3 source + 3 tests)

## Accomplishments

- **Loop closure:** News queries (e.g. "Why are diesel prices rising this week?") now invoke the planner exactly TWICE (initial routing + early-return short-circuit) and the search_agent exactly ONCE — previously this was 5 + 5 with D-04 budget exhaustion (UAT test 6 reproducer).
- **User-facing prose fix:** Response no longer mis-renders "I need a bit more information to calculate your surcharge. (planner_loop_budget_exhausted)" for clearly news-shaped queries. Now renders "Here's the latest market context." with the Market context blockquote prefix preserved.
- **Intent vocabulary extension:** `news_query` is a recognized PlannerOutput.user_intent value distinct from `out_of_scope`. SYSTEM_PROMPT documents the distinction so future LLM responses use the more specific intent (the early-return guard accepts both for backward compatibility).
- **Observability trace clarity:** Minimal trace entry on the planner short-circuit ("search_context populated; routing to respond") makes the second planner step visible in Langfuse without inflating the loop count.
- **6 new tests added** (3 unit in test_planner + 1 integration in test_graph + 2 unit in test_response_node), all passing.
- **184/184 backend tests green** (was 178 before; +6 new, 0 regressions).

## Task Commits

Each task was committed atomically following TDD red/green pattern:

1. **Task 1 RED: failing tests for planner early-return guard** - `2c17561` (test)
2. **Task 1 GREEN: planner early-return guard + news_query intent** - `be6335e` (feat)
3. **Task 2 RED: failing tests for response_node search-only flow** - `9c56db9` (test)
4. **Task 2 GREEN: response_node search-only flow prose** - `e692256` (feat)

## Files Created/Modified

- `backend/agent/nodes/planner.py` - Added gap-3 early-return guard between D-24 errors short-circuit (line 159) and D-04 budget guard (line 196); extended PlannerOutput.user_intent Literal with 'news_query'.
- `backend/agent/prompts/planner.py` - Documented news_query in user_intent values block AND JSON schema example; preserved Plan 05-08 followup_query inheritance paragraph and all prior content.
- `backend/agent/nodes/response_node.py` - Added status='search_only' branch in status precedence chain (BEFORE clarify) and markdown-build chain (deterministic 'Here's the latest market context.' prose with footer); updated module docstring status precedence comment.
- `backend/tests/test_planner.py` - Added 3 unit tests: `test_planner_early_returns_when_search_context_populated`, `test_planner_early_returns_for_news_query_intent_too`, `test_planner_does_not_short_circuit_for_surcharge_query_with_search_context`.
- `backend/tests/test_response_node.py` - Added 2 unit tests: `test_response_renders_news_prose_for_search_only_flow`, `test_response_renders_news_prose_even_when_loop_budget_exhausted`.
- `backend/tests/test_graph.py` - Added 1 integration test: `test_news_query_no_loop_renders_market_context` (UAT test 6 reproducer; asserts planner_count==2, search_agent_count==1, no clarify prose, Market context blockquote present).

## Decisions Made

- **Guard placement:** between D-24 errors short-circuit and D-04 budget guard ensures early-return fires BEFORE budget can exhaust on the second planner re-entry after search_agent.
- **Minimal trace entry:** the early-return appends ONE trace entry (not zero) so observability shows "planner ran twice, second was a short-circuit" — informative for the Langfuse demo AND consumed by `planner_count == 2` assertion in the integration test.
- **Backward-compatible intent acceptance:** the guard accepts BOTH `news_query` AND `out_of_scope` because today's LLM still emits `out_of_scope` for fuel/market questions; the SYSTEM_PROMPT update encourages `news_query` going forward, but live tests must keep passing during the transition.
- **search_only above clarify:** status='search_only' branch fires BEFORE clarify in BOTH the precedence block AND the markdown-build block — defensive against re-introduction of the loop bug (if a regression sets `clarification_reason='planner_loop_budget_exhausted'` AND search_context is populated, news prose still wins).
- **errors above search_only:** errors take precedence so a Tavily failure path with `state.errors` populated still renders the partial-error prose, not news prose.

## Confirmation: Plan 05-04 D-09 Cache-Aware Override Bypass Preserved

The existing `if next_step != "search_context":` guard at planner.py line 263 (added by Plan 05-04 to prevent demoting news queries to fetch_fuel) is unchanged. This is verified by acceptance grep `grep -c 'next_step != "search_context"' backend/agent/nodes/planner.py` returning 1. Both bypasses coexist: the gap-3 early-return at the TOP of planner_node fires AFTER search_agent has run on the second iteration, while the D-09 bypass fires on the FIRST iteration when the LLM emits `next_step="search_context"`.

## Confirmation: Plan 05-08 Gap-1 SYSTEM_PROMPT Paragraph Preserved

The "Follow-up query inheritance (D-05/999.1):" paragraph added by Plan 05-08 to instruct the LLM to emit null for unmentioned fields on followup_query turns is preserved verbatim. Acceptance grep returns 1 match.

## Confirmation: planner_count==2 / search_agent_count==1 on UAT Test 6

Integration test `test_news_query_no_loop_renders_market_context` confirms via `sum(1 for e in trace if e.get("agent") == "planner")` and `sum(1 for e in trace if e.get("agent") == "search_agent")`:
- planner_count == 2 (initial routing → search_context, then early-return short-circuit → respond)
- search_agent_count == 1 (single Tavily-mocked invocation populating search_context)
- final_payload.markdown contains "Diesel prices up 3% on supply concerns this week" (Market context blockquote summary)
- final_payload.markdown does NOT contain "I need a bit more information to calculate your surcharge"
- final_payload.status != "clarify"

## Deviations from Plan

None — plan executed exactly as written. RED/GREEN TDD pattern was followed for both tasks. All acceptance criteria pass.

## Issues Encountered

None. The integration test correctly transitioned from RED (Task 1 GREEN partially passed but the response prose was still wrong) to fully GREEN after Task 2's response_node fix, exactly as the plan anticipated.

## Self-Check: PASSED

Verified the following claims via Read+Grep:
- `backend/agent/nodes/planner.py` contains gap-3 fix marker (1 occurrence), `state.get("search_context") is not None` (1 occurrence), `{"news_query", "out_of_scope"}` set literal (1 occurrence), short-circuit reasoning text (1 occurrence), news_query Literal value (2 occurrences in module).
- `backend/agent/prompts/planner.py` contains news_query (2 occurrences: user_intent values block + JSON schema), Follow-up query inheritance preserved (1 occurrence).
- `backend/agent/nodes/response_node.py` contains gap-3 fix marker (2 occurrences), search_only (3 occurrences: status precedence + markdown branch + docstring), 'Here's the latest market context' literal (2 occurrences: comment + actual string).
- All 6 new tests grep with count 1 each in their respective files.
- Plan 05-04 D-09 bypass `next_step != "search_context"` preserved (1 occurrence).
- Plan 05-08 gap-1 inheritance paragraph preserved.
- 184/184 backend tests pass (`pytest backend/tests/` exits 0).
- All 4 commit hashes exist in git log: `2c17561`, `be6335e`, `9c56db9`, `e692256`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- gap-3 closure completes the gap-closure trio (gap-1 / gap-2 / gap-3) for UAT test 3, 4, and 6 surfaced during demo prep.
- Phase 5 ROADMAP success criterion #1 (parallel and observability demos quality) restored: news queries no longer waste 4 redundant Gemini calls AND no longer mis-render the clarify prose.
- TOOL-05 acceptance: search agent flow now ends in a sensible response (not a loop-exhausted clarify).
- ORCH-01 (planner correctness) restored on the news-query path.
- Plan 05-10 ready to be picked up by `/gsd:execute-phase 05 --gaps-only` via `gap_closure: true` frontmatter (already executed).
- Phase 5 is the final phase before milestone v1.0 — recommend full UAT re-run on the news-query path to confirm the fix lands end-to-end against live Tavily and Gemini before tagging.

---
*Phase: 05-polish-observability-docs*
*Completed: 2026-05-03*
