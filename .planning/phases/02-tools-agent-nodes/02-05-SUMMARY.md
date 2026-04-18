---
phase: 02-tools-agent-nodes
plan: 05
subsystem: agent-nodes
tags: [langgraph, gemini, langchain, pydantic, tdd]

# Dependency graph
requires:
  - phase: 02-tools-agent-nodes
    provides: fetch_fuel_price (Plan 02), calculate_route (Plan 03), AgentState + FuelData/RouteData models, GEMINI_MODEL config
provides:
  - fuel_agent_node (ORCH-02) with Gemini-narrated fuel analysis + D-11 deterministic fallback
  - route_agent_node (ORCH-03) with Gemini-narrated route analysis + D-10 origin/destination contract + D-11 fallback
  - get_chat_model() factory in backend/agent/llm.py (test-swappable seam for Gemini model)
  - SYSTEM_PROMPT strings for fuel and route agents
  - D-12 reasoning_trace schema producer (8-key entry format) established in working code
affects: [phase-03-graph-planner, phase-04-api-ui, phase-05-extensions]

# Tech tracking
tech-stack:
  added: [langchain_google_genai.ChatGoogleGenerativeAI (via factory), langchain_core.fake_chat_models (tests)]
  patterns:
    - "get_chat_model factory as single test-swappable seam for Gemini"
    - "Raw model.invoke() + JSON parse for narration (FakeMessagesListChatModel compatible; avoids with_structured_output)"
    - "Try/except wrapping of full Gemini path with deterministic narration fallback (D-11)"
    - "D-12 eight-key reasoning_trace schema (step, agent, tool, tool_input, tool_output, reasoning, timestamp, status)"
    - "Partial state return from node (operator.add reducer in AgentState appends trace list)"

key-files:
  created:
    - backend/agent/llm.py
    - backend/agent/prompts/fuel_agent.py
    - backend/agent/prompts/route_agent.py
    - backend/agent/nodes/fuel_agent.py
    - backend/agent/nodes/route_agent.py
    - backend/tests/test_fuel_agent.py
    - backend/tests/test_route_agent.py
  modified: []

key-decisions:
  - "Replaced model.with_structured_output(...) with raw .invoke() + json.loads + Pydantic validation; FakeMessagesListChatModel does not implement with_structured_output and every test fell through to the deterministic fallback (Rule 1 bug fix)"
  - "Wrapped entire Gemini call path in try/except catching (Exception, ValidationError) so any failure (auth, network, unparseable JSON) yields deterministic narration with status='ok' per D-11"
  - "route_agent_node raises ValueError when origin/destination missing from state — surfaces D-10 Planner-contract violations eagerly rather than silently no-op"
  - "Added ```-fence stripping in _parse_structured so Gemini responses wrapped in ```json...``` still parse (defensive; prompt already requests raw JSON)"
  - "Fuel SYSTEM_PROMPT omits search_fuel_news (TOOL-05 deferred to Phase 5 per Open Question 3) — prevents hallucinated tool calls"

patterns-established:
  - "Agent node shape: fetch → narrate → append D-12 trace entry → return partial state"
  - "Narration seam: module-level get_chat_model imported from backend.agent.llm; tests monkeypatch the attribute on the node module, not the factory module"
  - "Deterministic fallback narration stays textually rich (numbers, direction, zone/traffic label) so traces remain useful when LLM fails"

requirements-completed: [ORCH-02, ORCH-03]

# Metrics
duration: 5min
completed: 2026-04-18
---

# Phase 02 Plan 05: Fuel & Route Agent Nodes Summary

**Gemini-narrated fuel_agent_node (ORCH-02) and route_agent_node (ORCH-03) with D-11 deterministic fallback, D-12 trace schema, and a test-swappable get_chat_model factory.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-18T07:57:12Z
- **Completed:** 2026-04-18T08:01:41Z
- **Tasks:** 3
- **Files created:** 7
- **Files modified:** 0

## Accomplishments

- `fuel_agent_node` calls `fetch_fuel_price()`, narrates via Gemini, writes `fuel_data` + a single reasoning_trace entry (4 tests passing)
- `route_agent_node` calls `calculate_route(origin, destination)`, raises ValueError on missing planner-extracted fields (D-10), narrates via Gemini, writes `route_data` + trace entry (5 tests passing)
- `backend/agent/llm.get_chat_model` factory provides the only module importing `ChatGoogleGenerativeAI`; tests never touch it (grep verified)
- D-11 deterministic fallback narration is proven by tests that inject broken LLMs — trace `status` remains `"ok"` and reasoning still includes price/baseline for fuel or distance/zone for route
- D-12 trace schema (8 keys) formalized in working code; step counter uses `len(state["reasoning_trace"]) + 1` so parallel appends produce monotonically increasing step values when sequenced by the Planner
- Full Phase 2 test suite: **74 passing** (prior 65 + 4 fuel + 5 route), no regressions

## Task Commits

1. **Task 1: Gemini model factory + prompt modules** — `8b846ee` (feat)
2. **Task 2 RED: failing fuel_agent tests** — `85478be` (test)
3. **Task 2 GREEN: fuel_agent_node implementation** — `1062974` (feat)
4. **Task 3 RED: failing route_agent tests** — `4a581ff` (test)
5. **Task 3 GREEN: route_agent_node implementation** — `0b0e6b0` (feat)

_TDD cycle: Tasks 2 and 3 each have RED (failing test) and GREEN (passing implementation) commits per tdd="true" plan directive._

## Files Created/Modified

- `backend/agent/llm.py` — `get_chat_model()` factory returning ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0, max_retries=0)
- `backend/agent/prompts/fuel_agent.py` — SYSTEM_PROMPT describing FuelReasoning JSON schema (summary + trend); explicitly does not mention search_fuel_news
- `backend/agent/prompts/route_agent.py` — SYSTEM_PROMPT describing RouteReasoning JSON schema (summary + traffic_label)
- `backend/agent/nodes/fuel_agent.py` — `fuel_agent_node(state)` + FuelReasoning pydantic model + `_deterministic_narration` + `_parse_structured` (strips ``` fences)
- `backend/agent/nodes/route_agent.py` — `route_agent_node(state)` + RouteReasoning pydantic model + traffic-label deterministic narration + origin/destination ValueError guard
- `backend/tests/test_fuel_agent.py` — 4 tests (state+trace, D-12 schema, D-11 fallback, LLM trend propagation)
- `backend/tests/test_route_agent.py` — 5 tests (state+trace, zone, D-12 schema, missing-inputs ValueError, D-11 fallback)

## Decisions Made

- **Raw `.invoke()` + json.loads instead of `.with_structured_output()`** — plan prescribed `with_structured_output(FuelReasoning)` but `FakeMessagesListChatModel` does not implement that helper, so every test fell through to the deterministic fallback and lost LLM-produced trend strings. Switched to plain chat invocation; prompt already mandates JSON return format, `_parse_structured` strips Markdown fences defensively and validates with Pydantic. This is a Rule 1 bug fix (the planned approach was unusable with the test harness).
- **Broad `except (Exception, ValidationError)` around Gemini path** — satisfies D-11 without a separate retry layer; retries can land in Phase 3's agentic loop (ORCH-08). Status stays `"ok"` because we always return narration (LLM or fallback).
- **`route_agent_node` raises ValueError on missing origin/destination** rather than silently proceeding with empty strings or returning `status="error"`. Surfaces Phase 3 Planner contract violations eagerly.
- **Prompt excludes search_fuel_news** — Open Question 3 decision; advertising an unimplemented tool would cause Gemini to hallucinate tool calls that the node doesn't route.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced `with_structured_output()` with raw `.invoke()` + JSON parsing**

- **Found during:** Task 2 (GREEN phase, first pytest run)
- **Issue:** Plan's `model.with_structured_output(FuelReasoning, method="json_schema")` path works on real `ChatGoogleGenerativeAI` but `FakeMessagesListChatModel` used throughout tests does not implement `with_structured_output` — every test case fell through to the deterministic fallback, so `test_reasoning_includes_trend_from_llm_when_successful` failed because the LLM-supplied `above_baseline` never reached the trace entry.
- **Fix:** Replaced structured-output path with `model.invoke([SystemMessage, HumanMessage])` + `getattr(response, 'content')` + `_parse_structured` (strips optional ```json fences, `json.loads`, `FuelReasoning.model_validate`). Broad try/except still catches any Pydantic/JSON/runtime failure and falls to deterministic narration per D-11. Applied identical pattern to route_agent_node.
- **Files modified:** backend/agent/nodes/fuel_agent.py, backend/agent/nodes/route_agent.py, backend/tests/test_fuel_agent.py (broken-LLM stub raises in `.invoke` now), backend/tests/test_route_agent.py (same)
- **Verification:** All 9 new tests + 65 prior tests pass (74 total). `grep -R ChatGoogleGenerativeAI backend/tests/` returns 0 matches — tests never touch the live Gemini SDK path.
- **Committed in:** `1062974` (fuel), `0b0e6b0` (route)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** The fix was required for the plan's own test harness to pass. Core intent (Gemini narration + D-11 fallback + D-12 trace schema) preserved verbatim; only the LangChain call surface changed. No scope creep; identical pattern applied to both nodes for consistency.

## Issues Encountered

- First GREEN run for fuel_agent revealed that `FakeMessagesListChatModel.with_structured_output` is unimplemented. Fixed via the deviation above. This was anticipated by STATE.md's "Gemini structured output reliability unknown" blocker — we now have a concrete answer: the production Gemini SDK supports structured output, but the test fakes don't, so the node uses prompt-enforced JSON + manual parsing for portability.

## User Setup Required

None at test time — `GOOGLE_API_KEY` is only required when running live Gemini calls (Phase 3+ graph invocation). Plan frontmatter documents this under `user_setup.service: gemini` for future reference.

## Next Phase Readiness

- **ORCH-02 and ORCH-03 complete** — Phase 2 closes with all 4 tool requirements (TOOL-01..TOOL-04) and 2 agent-node requirements (ORCH-02, ORCH-03) satisfied. The `get_chat_model` seam is ready for the Planner node in Phase 3 to reuse.
- **D-11/D-12 pattern proven end-to-end** — Phase 3 Planner can adopt the same `try_llm_then_deterministic_fallback` shape, and the 8-key trace entry schema is now a frozen contract.
- **D-10 placeholder fields** — `route_agent_node` reads `state.get("origin")` / `state.get("destination")`. Phase 3 Planner must either (a) add these to AgentState TypedDict or (b) populate them on the state dict before routing to route_agent. The ValueError guard documents this contract.
- **Blocker resolved:** STATE.md "Gemini structured output reliability unknown" — we now know `with_structured_output` is production-only; tests use raw `.invoke()` + JSON parse.

## Self-Check

Files on disk:
- FOUND: backend/agent/llm.py
- FOUND: backend/agent/prompts/fuel_agent.py
- FOUND: backend/agent/prompts/route_agent.py
- FOUND: backend/agent/nodes/fuel_agent.py
- FOUND: backend/agent/nodes/route_agent.py
- FOUND: backend/tests/test_fuel_agent.py
- FOUND: backend/tests/test_route_agent.py

Commits on branch:
- FOUND: 8b846ee (feat(02-05): add Gemini model factory and agent prompts)
- FOUND: 85478be (test(02-05): add failing tests for fuel_agent_node)
- FOUND: 1062974 (feat(02-05): implement fuel_agent_node)
- FOUND: 4a581ff (test(02-05): add failing tests for route_agent_node)
- FOUND: 0b0e6b0 (feat(02-05): implement route_agent_node)

Test suite: 74 passed, 0 failed.

## Self-Check: PASSED

---
*Phase: 02-tools-agent-nodes*
*Completed: 2026-04-18*
