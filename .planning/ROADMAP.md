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
- [ ] **Phase 4: Frontend & Reasoning Trace** - Chat UI, reasoning trace panel, dashboard, SSE streaming display
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
- [ ] 03-01-PLAN.md — Wave 0 foundation: deps, AgentState extension, config constants, .env.example, test scaffolds, in_memory_checkpointer fixture
- [ ] 03-02-PLAN.md — Planner + Pricing + Response nodes (ORCH-01/04/05) + D-13 fetched_at injection in fuel/route nodes
- [ ] 03-03-PLAN.md — Graph assembly: build_graph + RetryPolicy + AsyncSqliteSaver topology (ORCH-08/10) + 7 integration tests
- [ ] 03-04-PLAN.md — FastAPI app shell + POST /api/chat SSE handler (API-01) with meta/trace/answer/error/done envelope
- [ ] 03-05-PLAN.md — GET /api/conversations + /api/conversations/:id + /api/fuel-prices (API-02, API-03, API-04)

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
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD

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
**Plans**: 5 plans

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Data Pipeline | 0/3 | Planning complete | - |
| 2. Tools & Agent Nodes | 0/3 | Not started | - |
| 3. Graph Assembly & API Layer | 0/3 | Not started | - |
| 4. Frontend & Reasoning Trace | 0/3 | Not started | - |
| 5. Polish, Observability & Docs | 0/3 | Not started | - |
