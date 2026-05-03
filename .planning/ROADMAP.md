# Roadmap: Express Dynamic Surcharge Orchestrator

## Overview

This roadmap delivers an agentic AI surcharge calculator in five phases, moving from data foundation through individual tools, graph orchestration, frontend, and finally polish/observability. Each phase produces a working, testable artifact. The structure follows the natural dependency chain: tools need data, the graph needs tools, the UI needs the API, and observability wraps the whole system.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation & Data Pipeline** - State schema, Pydantic models, SQLite database, seed scripts, surcharge formula constants
- [ ] **Phase 2: Tools & Agent Nodes** - Build and test each tool independently, wrap in LangGraph agent nodes
- [ ] **Phase 3: Graph Assembly & API Layer** - Wire nodes into StateGraph with conditional routing, checkpointer, FastAPI endpoints
- [x] **Phase 4: Frontend & Reasoning Trace** - Chat UI, reasoning trace panel, dashboard, SSE streaming display (completed 2026-04-26)
- [ ] **Phase 5: Polish, Observability & Docs** - Parallel agents, HITL gate, Langfuse tracing, Tavily search, documentation

## Phase Details

### Phase 1: Foundation & Data Pipeline
**Goal**: A seeded SQLite database with rate tables, zone definitions, and fuel price history -- plus the Pydantic models and state schema that every downstream component depends on
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, CALC-01, CALC-02, CALC-03, CALC-04, TOOL-06, ORCH-06, DOC-03
**Success Criteria** (what must be TRUE):
  1. Running `python seed_database.py` produces a populated `data/express.db` with rate table rows for all 3 shipping types, 3 zones, and multiple weight tiers
  2. Running `python fetch_fuel_prices.py` downloads EPPO diesel price history into `data/raw/` as CSV
  3. Surcharge formula implemented as a pure Python function with configurable baseline, shipping-type multipliers, traffic adjustment, and cap/floor -- passing unit tests for known inputs
  4. AgentState TypedDict and all Pydantic input/output models are defined and importable with no errors
  5. `.env.example` exists with all required API key placeholders documented
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Data pipeline: requirements.txt, data generation scripts, seed CSVs, SQLite seeding, zone definitions
- [x] 01-02-PLAN.md — Type foundations: Pydantic models, AgentState TypedDict, config module, validation tests
- [x] 01-03-PLAN.md — Surcharge formula: TDD implementation of pure calculate_surcharge function with hand-calculated tests

### Phase 2: Tools & Agent Nodes
**Goal**: Each tool (fuel fetch, route calc, rate lookup, surcharge calc) works independently with tests, and is wrapped in a LangGraph-compatible agent node
**Depends on**: Phase 1
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, ORCH-02, ORCH-03
**Success Criteria** (what must be TRUE):
  1. fetch_fuel_price tool returns current diesel price, exercising the multi-level fallback chain (API -> cached CSV -> last-known) and returning a structured Pydantic response
  2. calculate_route tool returns distance, duration, traffic severity, and zone for a given origin/destination pair (tested with mocked Google Maps responses)
  3. lookup_rate tool queries SQLite and returns the correct rate for a given shipping_type + zone + weight combination
  4. Fuel Agent and Route Agent nodes can be invoked individually with a sample AgentState and produce correct state updates
**Plans**: 5 plans

Plans:
- [x] 02-01-PLAN.md — Wave 0 foundation: deps, config, AgentState reducer fix, conftest + fixtures
- [x] 02-02-PLAN.md — TOOL-01: fetch_fuel_price 3-level fallback chain + tests
- [x] 02-03-PLAN.md — TOOL-02: calculate_route with zone mapping, traffic bucketing, TTL cache + tests
- [x] 02-04-PLAN.md — TOOL-03 + TOOL-04: lookup_rate SQLite query and calculate_surcharge @tool wrapper + tests
- [x] 02-05-PLAN.md — ORCH-02 + ORCH-03: Fuel Agent and Route Agent nodes with Gemini narration (D-11 fallback) + tests

### Phase 3: Graph Assembly & API Layer
**Goal**: The full LangGraph StateGraph runs end-to-end -- planner routes to agents, agents produce a surcharge result, and FastAPI serves it via SSE streaming
**Depends on**: Phase 2
**Requirements**: ORCH-01, ORCH-04, ORCH-05, ORCH-08, ORCH-10, API-01, API-02, API-03, API-04
**Success Criteria** (what must be TRUE):
  1. A natural language query like "What is the surcharge for a 15kg Bounce shipment from Bangkok to Nonthaburi?" produces a correct surcharge breakdown via the graph
  2. Planner node correctly routes to Fuel + Route agents for surcharge queries and skips them for follow-up/clarification queries
  3. Conversation memory works: a follow-up question in the same thread reuses previously fetched fuel/route data without re-calling tools
  4. POST /api/chat returns an SSE stream with agent trace events and final response readable by a browser fetch call
  5. GET /api/fuel-prices returns historical fuel price data as JSON
**Plans**: 5 plans

Plans:
- [x] 03-01-PLAN.md — Wave 0 foundation: deps, AgentState extension, config constants, .env.example, test scaffolds, in_memory_checkpointer fixture
- [x] 03-02-PLAN.md — Planner + Pricing + Response nodes (ORCH-01/04/05) + D-13 fetched_at injection in fuel/route nodes
- [x] 03-03-PLAN.md — Graph assembly: build_graph + RetryPolicy + AsyncSqliteSaver topology (ORCH-08/10) + 7 integration tests
- [x] 03-04-PLAN.md — FastAPI app shell + POST /api/chat SSE handler (API-01) with meta/trace/answer/error/done envelope
- [x] 03-05-PLAN.md — GET /api/conversations + /api/conversations/:id + /api/fuel-prices (API-02, API-03, API-04)

### Phase 4: Frontend & Reasoning Trace
**Goal**: Users interact with the surcharge agent through a chat interface that streams responses and displays every reasoning step transparently
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06
**Success Criteria** (what must be TRUE):
  1. User can type a surcharge query and see the response stream in real-time via SSE (not a loading spinner then full response)
  2. Reasoning trace panel shows each agent step, tool call, and decision for the current query -- visible alongside the chat response
  3. Surcharge breakdown table appears in chat showing base rate, surcharge percentage, surcharge amount, and total
  4. Dashboard page displays fuel price trend chart and surcharge history using Recharts
  5. User can browse and resume past conversations via a sidebar
**Plans**: 5 plans
**UI hint**: yes

Plans:
- [x] 04-01-PLAN.md — Wave 0 foundation: Next.js scaffold, TS types mirroring backend, Vitest+MSW+Playwright infra
- [x] 04-02-PLAN.md — Data layer: SSE parser, api client, formatters, useChatStream/useConversations/useFuelPrices hooks
- [x] 04-03-PLAN.md — Chat + trace + sidebar UI: MarkdownAnswer, MessageList, FeedbackButtons, TracePanel, ConversationSidebar (UI-01/02/03/05/06)
- [x] 04-04-PLAN.md — Dashboard: FuelPriceChart + SurchargeHistoryChart with Recharts × React 19 mitigations (UI-04)
- [x] 04-05-PLAN.md — Composition: ChatColumn tab toggle + ChatApp shell + Playwright e2e + human verification checkpoint

### Phase 5: Polish, Observability & Docs
**Goal**: The system demonstrates advanced agent patterns (parallel execution, HITL, web search) with full observability and submission-ready documentation
**Depends on**: Phase 4
**Requirements**: ORCH-07, ORCH-09, TOOL-05, API-05, OBS-01, OBS-02, OBS-03, DOC-01, DOC-02, DOC-04
**Success Criteria** (what must be TRUE):
  1. Fuel and Route agents execute in parallel (observable via trace timestamps showing overlapping execution)
  2. High-value shipment queries trigger a human-in-the-loop approval gate before finalizing the surcharge
  3. Langfuse dashboard shows traced LLM calls, tool invocations, and user feedback scores for completed queries
  4. User feedback (thumbs up/down) on a response is visible in Langfuse as a score entry
  5. README.md, architecture.md, and data source docs are complete and accurate for submission
**Plans**: 7 plans

Plans:
- [x] 05-01-PLAN.md — Wave 0 foundation: Python 3.11 bump, deps (langfuse, tavily-python), AgentState v3 (approval_decision, search_context), config constants, observability.py + Pydantic models + conftest fixtures
- [x] 05-02-PLAN.md — Langfuse callback wiring in chat handler + formula accuracy auto-eval after pricing_agent (OBS-01, OBS-03)
- [x] 05-03-PLAN.md — Parallel fan-out: planner emits fanout_fuel_route sentinel; graph router returns list[str] for same-superstep parallel scheduling (ORCH-07)
- [x] 05-04-PLAN.md — Tavily search agent: search_fuel_news tool + search_agent_node + planner news intent + graph wiring + response_node Market context line (TOOL-05)
- [x] 05-05-PLAN.md — HITL approval gate: hitl_gate_node + interrupt() + sixth SSE event approval_required + Command(resume) in chat handler + deny path in response_node (ORCH-09)
- [x] 05-06-PLAN.md — Backend POST /api/feedback + frontend wires (postFeedback, useChatStream approve, ApprovalCard, SearchContextLine, FeedbackButtons swap, MessageList branch) (API-05, OBS-02)
- [ ] 05-07-PLAN.md — Documentation: README.md (DOC-01), docs/architecture.md update (DOC-02), docs/data-sources.md (DOC-04), screenshots, demo.mp4, v1.0 tag (D-21)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Data Pipeline | 0/3 | Planning complete | - |
| 2. Tools & Agent Nodes | 0/3 | Not started | - |
| 3. Graph Assembly & API Layer | 0/3 | Not started | - |
| 4. Frontend & Reasoning Trace | 5/5 | Complete   | 2026-04-26 |
| 5. Polish, Observability & Docs | 6/7 | Wave 5 complete | - |

## Backlog

Out-of-band items surfaced during execution (not part of the planned 5-phase milestone).

### 999.2: Scope-naming mismatch — "Central Region" vs Bangkok Metro

**Status**: Resolved 2026-04-25 via quick task `260425-vc6-rename-product-scope-from-central-region` (option b: rename docs to match code).

**Origin**: Live smoke testing on 2026-04-25 surfaced that the rate table and zone classifier only cover Bangkok metro provinces (Nonthaburi, Pathum Thani, Samut Prakan, Nakhon Pathom, Samut Sakhon, Ayutthaya), despite user-facing docs and runtime error messages calling the scope "Central Region".

**Options considered**:
- (a) Expand zones to cover the full Thai Central Region (north to Lop Buri, west to Kanchanaburi, etc.) — deferred as a v2.0 possibility; would require new zone definitions, rate table rows, and Google Maps coverage testing.
- (b) Rename the product scope language from "Central Region" to "Bangkok Metro" across user-facing docs, narration docstrings, and runtime error messages — chosen, smaller blast radius, no rate-table/zone churn.

**Decision**: Option (b). Internal zone identifiers `central-1/2/3` were intentionally NOT renamed to avoid churn in rate tables, fixtures, and lookup_rate logic. Option (a) remains open as a future expansion possibility for v2.0.

### 999.1: Planner state merge on follow-up turns

**Status**: Resolved 2026-04-25 via quick task `260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo` (option b: post-process recompute).

**Origin**: Live smoke testing on 2026-04-25 (prompt C) surfaced that on the same thread, "Calculate surcharge for 50kg retail_standard from Bangkok to Pathum Thani" followed by "What if I switched it to a Bounce shipment instead?" returned a clarification asking for weight/origin/destination instead of routing through fetch_route/fetch_fuel/calculate_price using the prior thread's values. Root cause: planner_node invoked the LLM with only the latest user message; the LLM returned null for unmentioned fields, populated missing_fields, and emitted next_step=clarify. The post-LLM `parsed.X or state.get("X")` merge filled extraction fields after the fact, but next_step and missing_fields were already decided.

**Options considered**:
- (a) Inject prior state into the LLM prompt context so the LLM sees state.shipping_type / weight_kg / origin / destination — heavier, requires SYSTEM_PROMPT changes plus a token-cost increase on every planner call, and trusts the LLM to do the right thing.
- (b) After the existing `parsed.X or state.get("X")` merge produces final values, recompute missing_fields and next_step from the merged values. If the LLM said clarify but the merge has all fields, promote next_step to fetch_fuel and let the existing D-12 cache-aware override cascade further (fetch_route / calculate_price) — chosen, smaller blast radius, no prompt change, no token cost increase, deterministic.

**Decision**: Option (b). The D-12 cache-aware override block was also updated to reference merged_origin/merged_destination (not parsed.origin/parsed.destination) so route-cache hits work on follow-ups where origin/destination were inherited from prior state. Option (a) remains open for future consideration if user_intent classification becomes unreliable on follow-ups.

### 999.3: Planner trace tool_output narration mismatch

**Status**: Resolved 2026-04-25 via quick task `260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo` (folded into the same patch as 999.1).

**Origin**: Live smoke testing on 2026-04-25 surfaced that the trace panel's planner step displayed `tool_output.next_step` values that did not match the actually-routed step. Root cause: planner_node emitted `parsed.model_dump()` as `tool_output`, capturing the raw LLM emission BEFORE the D-12 cache-aware override mutated the local `next_step` variable. The `reasoning` text was correct (already used post-override next_step); only `tool_output` was stale. Pure narration bug — no impact on graph routing — but undermined the agent's transparency promise.

**Options considered**:
- (a) Drop `tool_output` from planner trace entries entirely — would lose trace-panel detail.
- (b) Construct `tool_output` as an explicit dict from the post-override next_step and merged extraction fields — chosen, preserves trace fidelity and matches what the function actually returns to the graph.

**Decision**: Option (b). The trace tool_output dict now contains the same values that planner_node returns to the graph, eliminating any narration/routing skew.

### 999.4: D-04 loop budget windowed per turn (cross-turn short-circuit bug)

**Status**: Resolved 2026-04-25 via quick task `260425-x2i-fix-d-04-loop-budget-guard-to-window-per`.

**Origin**: Live smoke retest 2026-04-25 of 999.1 fix exposed that turn 2 of a same-thread conversation never reached the planner — the cumulative reasoning_trace from turn 1 (operator.add reducer) tripped D-04's `len(trace) >= MAX-1` guard before turn 2's planner could run. Result: response node re-rendered turn 1's cached surcharge_result instead of recomputing for the new user message. Symptom matched the original 999.1 surface bug, but the root cause was the budget guard, not the merge logic.

**Fix**: `_loop_budget_exhausted` now counts only `agent == "planner"` entries in the current turn (entries since the most recent `agent == "response"` entry). Matches D-04's documented intent of capping planner *iterations within one user request*.
