---
phase: 03-graph-assembly-api-layer
plan: 02
subsystem: agent-nodes
tags: [langgraph, planner, pricing, response, gemini, d-13-timestamps, tdd]

# Dependency graph
requires:
  - phase: 03-graph-assembly-api-layer
    plan: 01
    provides: AgentState v2 (origin/destination/user_intent/missing_fields/clarification_reason/errors), FUEL_DATA_TTL_SECONDS, PLANNER_MAX_ITERATIONS, in_memory_checkpointer fixture
  - phase: 02-tools-and-agent-nodes
    provides: lookup_rate (D-09 ValueError contract), calculate_surcharge_tool, fuel_agent_node + route_agent_node (D-11 narration pattern), get_chat_model factory
provides:
  - planner_node (D-01 PlannerOutput schema + D-02 retry/clarify fallback + D-04 loop budget guard + D-12 cache-aware fetch_fuel/fetch_route override)
  - pricing_agent_node (D-08 compound trace tool='lookup_rate+calculate_surcharge', D-09 ValueError propagation, D-11 deterministic fallback)
  - response_node (D-10 final_payload shape, D-11 locked markdown structure with 4-row table + cap callout, deterministic prose with no Gemini call in v1)
  - D-13 fetched_at injection on fuel_data and route_data dumps (ORCH-10 prerequisite for Plan 03-03 graph routing)
affects: [03-03-graph, 03-04-api-chat, 03-05-api-conversations]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Planner cache-override pattern: parsed.next_step --> _fuel_fresh / _route_matches override --> final next_step (D-12)"
    - "Compound trace tool name (D-08): 'lookup_rate+calculate_surcharge' for the pricing step that fans two tools through one node invocation"
    - "Deterministic Response prose (RESEARCH OQ 3/5): final hop renders prose+table from Python f-strings, no Gemini call, fully testable"
    - "fetched_at as state-level annotation (not Pydantic field): added AFTER model_dump() so the original tool-output Pydantic model stays clean"

key-files:
  created:
    - backend/agent/prompts/planner.py
    - backend/agent/prompts/pricing_agent.py
    - backend/agent/prompts/response_node.py
    - backend/agent/nodes/planner.py
    - backend/agent/nodes/pricing_agent.py
    - backend/agent/nodes/response_node.py
  modified:
    - backend/agent/nodes/fuel_agent.py
    - backend/agent/nodes/route_agent.py
    - backend/tests/test_planner.py
    - backend/tests/test_pricing_agent.py
    - backend/tests/test_response_node.py
    - backend/tests/test_fuel_agent.py
    - backend/tests/test_route_agent.py

key-decisions:
  - "Response Node renders prose deterministically (Python f-string) -- no Gemini call in v1 per RESEARCH Open Questions 3 & 5; final hop stays fully deterministic for tests and saves Gemini quota for Planner+Fuel+Route+Pricing"
  - "PlannerOutput.next_step still includes 'search_context' Literal value despite v1 not emitting it -- prompt instructs the model NOT to emit search_context, but keeping it in the schema means a stray emission validates instead of triggering parse_failed (D-02 path), reducing false-positive clarify cycles when Phase 5 enables search"
  - "fetched_at attached to fuel_data/route_data AFTER model_dump() (state-level annotation, not Pydantic field) -- preserves clean tool-output schema so trace_entry tool_output reflects exactly what the tool returned (RESEARCH §fetched_at injection note)"

requirements-completed: [ORCH-01, ORCH-04, ORCH-05]

# Metrics
duration: 6min
completed: 2026-04-25
---

# Phase 3 Plan 02: Agent Nodes (Planner, Pricing, Response) Summary

**Built three new LangGraph nodes (Planner D-01/D-02/D-04/D-12, Pricing Agent D-08/D-09/D-11, Response Node D-10/D-11) plus D-13 fetched_at injection on existing Fuel/Route nodes — backend test suite now reports 88 passed / 15 skipped (12 new active tests across Wave 2: 5 planner + 3 pricing + 4 response).**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-25T03:44:32Z
- **Completed:** 2026-04-25T03:50:19Z
- **Tasks:** 2
- **Files modified:** 13 (6 created + 7 edited)

## Accomplishments

- `planner_node` extracts shipping_type, weight_kg, origin, destination, user_intent from a user message and emits `next_step` from the locked vocabulary (`fetch_fuel | fetch_route | calculate_price | clarify | respond`); uses `Literal[...]` validation on `next_step` so invalid emissions trigger the D-02 retry path instead of leaking through.
- D-12 cache override implemented: when the LLM emits `next_step="fetch_fuel"` and `state.fuel_data.fetched_at` is younger than `FUEL_DATA_TTL_SECONDS`, the node skips ahead to `fetch_route` (or `calculate_price` if the route is also cached and inputs are present); symmetric override for `fetch_route` when `state.route_data` matches the parsed origin/destination.
- D-04 loop budget guard runs BEFORE any Gemini call: when `len(state.reasoning_trace) >= PLANNER_MAX_ITERATIONS - 1` (default 5), the planner returns `next_step="respond"` with `clarification_reason="planner_loop_budget_exhausted"` — verified by asserting `mock_factory.call_count == 0` in the dedicated test.
- D-02 fallback returns `next_step="clarify"` with `clarification_reason="planner_parse_failed"` after two consecutive Gemini parse failures; mirrors the Phase 2 fuel/route deterministic-fallback pattern but routes to clarify (not respond) since the user's intent is still unknown.
- `pricing_agent_node` fans two tools through one node invocation: `lookup_rate(...)` then `calculate_surcharge_tool.invoke(...)`. The single emitted trace entry uses the compound tool name `"lookup_rate+calculate_surcharge"` (D-08) and `tool_input = SurchargeInput.model_dump()`.
- D-09 contract honoured: `ValueError` from `lookup_rate` (no rate, invalid weight) propagates uncaught — the Pricing Agent does NOT wrap or swallow it. Verified via `pytest.raises(ValueError)` test.
- D-11 deterministic narration falls back when Gemini fails: `f"Base rate {rate.base_rate:.2f} THB; surcharge {pct:.2%} = {amt:.2f} THB; total {total:.2f} THB[ (capped)]"`. Trace status remains `"ok"` even on Gemini failure because narration is always produced.
- `response_node` renders D-10 payload `{markdown, surcharge_result, capped, status}` under the `final_payload` key — the chat SSE handler in Plan 03-04 will detect this via `astream_events`.
- D-11 locked markdown structure: prose paragraph + 4-row table (`| Base rate |`, `| Surcharge % |`, `| Surcharge amount |`, `| Total |`) + italic footer (`*Reasoning trace available below.*`).
- Cap callout: when `surcharge_result.capped == True`, the markdown is prepended with `> ⚠ Cap/floor applied — review recommended\n\n`.
- Status precedence: `errors` non-empty → `partial`; else `clarification_reason && !surcharge_result` → `clarify`; else `surcharge_result` → `ok`; fallback → `clarify`.
- D-13 fetched_at injection on `fuel_agent_node` and `route_agent_node`: after `model_dump()`, the dict is decorated with `fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")`. The trace entry's `tool_output` retains the un-annotated dump (fetched_at is a state-level annotation, not a tool return).
- Test suite: 88 passed, 15 skipped — 12 new active tests across Wave 2 (5 planner + 3 pricing + 4 response) plus 2 fetched_at tests removed from skip list. No regressions in any Phase 1 or Phase 2 tests.

## Task Commits

1. **Task 1: Planner node + prompt + 5 tests (ORCH-01)** — `01cefe2` (feat)
2. **Task 2: Pricing Agent + Response Node + D-13 fetched_at injection** — `0de1f9c` (feat)

**Plan metadata commit:** _appended after this SUMMARY is written_ (docs commit covering SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md)

## Files Created/Modified

### Created

- `backend/agent/prompts/planner.py` — SYSTEM_PROMPT for Planner (D-01 schema + next_step vocabulary + D-07 user_intent enum)
- `backend/agent/prompts/pricing_agent.py` — SYSTEM_PROMPT for Pricing narration (one-sentence summary, JSON `{summary}`)
- `backend/agent/prompts/response_node.py` — SYSTEM_PROMPT placeholder for future Gemini polish (v1 uses deterministic prose; prompt locked for vocabulary parity with fuel/route)
- `backend/agent/nodes/planner.py` — `planner_node`, `PlannerOutput` Pydantic schema, helpers `_fuel_fresh`, `_route_matches`, `_loop_budget_exhausted`, `_parse_structured`
- `backend/agent/nodes/pricing_agent.py` — `pricing_agent_node`, `PricingReasoning` schema, `_deterministic_narration`, `_narrate_with_llm`
- `backend/agent/nodes/response_node.py` — `response_node`, `_render_table`, `_render_prose_ok`, `_render_prose_clarify`, `_render_prose_partial`

### Modified

- `backend/agent/nodes/fuel_agent.py` — D-13 fetched_at stamp on returned fuel_data dict (post `model_dump()`)
- `backend/agent/nodes/route_agent.py` — D-13 fetched_at stamp on returned route_data dict
- `backend/tests/test_planner.py` — Replaced 5 placeholders with real tests (`pytestmark = pytest.mark.skip` removed)
- `backend/tests/test_pricing_agent.py` — Replaced 3 placeholders with real tests
- `backend/tests/test_response_node.py` — Replaced 4 placeholders with real tests
- `backend/tests/test_fuel_agent.py` — Removed `@pytest.mark.skip` from `test_fetched_at_added_to_dump`, implemented assertion
- `backend/tests/test_route_agent.py` — Same as above for route

## Decisions Made

- **Response Node uses deterministic prose, not Gemini** — Per RESEARCH Open Questions 3 & 5: the final hop renders the prose paragraph from Python f-strings (current diesel vs baseline + route distance/zone + shipping_type + optional cap note + italic footer). This keeps the response phase fully deterministic for tests, saves a 5th Gemini call per request (free-tier 15 RPM constraint), and the markdown table is always deterministic anyway. SYSTEM_PROMPT is preserved for the future enhancement where Gemini may polish the prose.
- **`PlannerOutput.next_step` Literal includes `'search_context'`** — Even though v1 instructs the LLM never to emit it (Phase 5 deferred), keeping `search_context` in the Literal means a stray emission validates cleanly instead of triggering `planner_parse_failed` (D-02 path). Phase 5 will then enable the `search_context` route without re-touching this schema.
- **`fetched_at` is a state-level annotation, not a Pydantic field** — Decorating the dict AFTER `model_dump()` keeps the `FuelData` / `RouteData` Pydantic models clean (no extra-field churn) and ensures the trace entry's `tool_output` reflects exactly what the tool returned. The `_fuel_fresh()` helper consumes `fetched_at` directly off the dict — Pydantic round-tripping is never needed for this field.
- **Pricing Agent `traffic_severity` sourced from `state.route_data.traffic_severity`** — The `SurchargeInput.traffic_severity` arg defaults to 1, but the Pricing Agent reads the real value from the route lookup. This makes the tool input fully reproducible from the state alone (no implicit defaults leaking into the trace).
- **`response_node` accepts `surcharge_result` from `state` but does NOT validate it as `SurchargeResult`** — The dict shape is contractually guaranteed by `pricing_agent_node` (Pydantic-dumped). Re-validating in the Response node would add cost and risk false negatives if Phase 5 extends the schema.

## Deviations from Plan

None — plan executed exactly as written. The plan's two tasks completed with TDD (RED test → GREEN implementation → refactor pass) and the deterministic Response Node design was already specified in the plan's `<action>` block (Step B). No Rule 1/2/3 auto-fixes were needed; lookup_rate, calculate_surcharge_tool, FakeMessagesListChatModel, and the AgentState v2 fields all worked as advertised by Plan 03-01.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration. All tests use `FakeMessagesListChatModel` and `mocker.patch.object`; live Gemini quota is never consumed.

## Next Phase Readiness

- **Plan 03-03 (graph assembly)** can immediately wire all five nodes (`planner_node`, `fuel_agent_node`, `route_agent_node`, `pricing_agent_node`, `response_node`) into a `StateGraph`. The conditional edge from `planner_node` reads `state.next_step` and routes to one of `fetch_fuel | fetch_route | calculate_price | clarify | respond` — the locked vocabulary matches.
- **D-12 cache reuse is testable end-to-end now**: Plan 03-03's graph integration test can populate `fuel_data.fetched_at` in the initial state and assert `fuel_agent_node` is NOT entered.
- **D-13 prerequisite satisfied**: any state-level routing that depends on `fuel_data.fetched_at` (planner cache override, future TTL-based purge logic) has the field populated.
- **Plans 03-04 (chat SSE)** can use the `final_payload` key as the SSE filter signal — `response_node` always returns this key when the graph terminates.
- **Plan 03-05 (conversations)**: no new requirements from this plan; conversation list logic only needs the AgentState v2 fields already in place from Plan 03-01.

## Self-Check: PASSED

All claims verified:
- Created files exist:
  - `backend/agent/prompts/planner.py` FOUND
  - `backend/agent/prompts/pricing_agent.py` FOUND
  - `backend/agent/prompts/response_node.py` FOUND
  - `backend/agent/nodes/planner.py` FOUND
  - `backend/agent/nodes/pricing_agent.py` FOUND
  - `backend/agent/nodes/response_node.py` FOUND
- Modified files updated: 7/7 (fuel_agent.py, route_agent.py, test_planner.py, test_pricing_agent.py, test_response_node.py, test_fuel_agent.py, test_route_agent.py)
- Commits in history: `01cefe2` (Task 1), `0de1f9c` (Task 2) — both verified via `git log --oneline -3`
- Test suite: 88 passed, 15 skipped (verified post-Task-2; +14 active tests vs Plan 03-01 baseline of 74)
- Imports succeed: `planner_node`, `PlannerOutput`, `pricing_agent_node`, `response_node` all importable
- Acceptance grep checks: all 11 grep-based checks across both tasks return the expected counts (PlannerOutput=1, FUEL_DATA_TTL_SECONDS=4, PLANNER_MAX_ITERATIONS=5, fetched_at in fuel/route nodes >=1 each, all 4 markdown row labels matched, cap callout matched, compound tool name matched)
- No Gemini SDK leak in tests: `grep -R ChatGoogleGenerativeAI backend/tests/` returns nothing
- Wave 2 plan-specific test count: `pytest test_planner.py test_pricing_agent.py test_response_node.py -q` reports 12 passed (5 + 3 + 4)

---
*Phase: 03-graph-assembly-api-layer*
*Completed: 2026-04-25*
