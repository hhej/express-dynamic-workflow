# Requirements: Express Dynamic Surcharge Orchestrator

**Defined:** 2025-04-04
**Core Value:** The agent must transparently reason through fuel price, route, and shipping data to produce an accurate, explainable surcharge recommendation.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Data Pipeline

- [x] **DATA-01**: Data pipeline seeds SQLite database with rate table (3 shipping types, 3 zones, multiple weight tiers)
- [x] **DATA-02**: fetch_fuel_prices.py fetches historical diesel prices from EPPO and stores in data/raw/
- [x] **DATA-03**: generate_rate_table.py creates simulated Express rate table with documented assumptions
- [x] **DATA-04**: seed_database.py loads CSVs into SQLite (data/express.db)
- [x] **DATA-05**: Zone definitions configured for Central Region (central-1, central-2, central-3) with province mappings

### Agent Tools

- [x] **TOOL-01**: fetch_fuel_price tool retrieves live diesel price from EPPO/PTT with multi-level fallback (API -> scrape -> cached CSV -> last-known)
- [x] **TOOL-02**: calculate_route tool computes distance, duration, traffic severity, and zone via Google Maps API with 15-min caching
- [x] **TOOL-03**: lookup_rate tool queries SQLite rate table by shipping_type, zone, and weight_kg
- [x] **TOOL-04**: calculate_surcharge tool applies formula: fuel_delta_pct * multiplier[shipping_type] with traffic adjustment and cap/floor
- [x] **TOOL-05**: search_fuel_news tool searches fuel trends via Tavily API for reasoning context
- [x] **TOOL-06**: All tools use structured Pydantic input/output models for deterministic, testable responses

### Agent Orchestration

- [x] **ORCH-01**: Planner agent detects user intent and routes to appropriate specialist agent(s) via conditional edges
- [x] **ORCH-02**: Fuel Agent node wraps fetch_fuel_price and search_fuel_news tools
- [x] **ORCH-03**: Route Agent node wraps calculate_route tool with zone mapping
- [x] **ORCH-04**: Pricing Agent node wraps lookup_rate and calculate_surcharge tools
- [x] **ORCH-05**: Response node formats final answer with surcharge breakdown table and reasoning
- [x] **ORCH-06**: Agent state schema (AgentState TypedDict) manages messages, fuel_data, route_data, shipping_type, weight_kg, surcharge_result, reasoning_trace, next_step
- [x] **ORCH-07**: Fuel Agent and Route Agent execute in parallel via LangGraph Send API
- [x] **ORCH-08**: Agentic retry loop with exponential backoff (max 2 retries per tool) and graceful fallback with explanation
- [x] **ORCH-09**: Human-in-the-loop approval gate for high-value shipments before finalizing surcharge
- [x] **ORCH-10**: Conversation memory via LangGraph SQLite checkpointer — follow-up queries reuse cached fuel/route data

### Surcharge Logic

- [x] **CALC-01**: Three shipping types with distinct multipliers: Bounce (1.0x), Retail Standard (0.5x), Retail Fast (0.8x)
- [x] **CALC-02**: Surcharge formula uses configurable baseline diesel price (default 29.94 THB/L)
- [x] **CALC-03**: Traffic adjustment applied for Bounce shipments only (2% per severity level, 1-5 scale)
- [x] **CALC-04**: Surcharge cap at 15% maximum, floor at -5% minimum (configurable via env)

### Backend API

- [x] **API-01**: POST /api/chat endpoint accepts user message and returns SSE stream of agent traces + response
- [x] **API-02**: GET /api/conversations lists all past conversation threads
- [x] **API-03**: GET /api/conversations/:id returns full conversation history for a thread
- [x] **API-04**: GET /api/fuel-prices?days=30 returns historical fuel price data for charts
- [x] **API-05**: POST /api/feedback accepts user feedback (score + reason) and forwards to Langfuse

### Frontend

- [x] **UI-01**: Chat interface for natural language surcharge queries with SSE streaming display
- [x] **UI-02**: Reasoning trace panel showing agent steps, tool calls, and decisions for each query
- [x] **UI-03**: Surcharge breakdown table in chat responses (base rate, surcharge %, amount, total)
- [x] **UI-04**: Dashboard with fuel price trends and surcharge history charts (Recharts)
- [x] **UI-05**: User feedback buttons (thumbs up/down) on agent responses with reason selector on thumbs down
- [x] **UI-06**: Conversation history sidebar for resuming past threads

### Observability

- [x] **OBS-01**: Langfuse callback handler traces all LLM calls, tool calls, and agent steps
- [x] **OBS-02**: User feedback scores forwarded to Langfuse Score API for evaluation tracking
- [x] **OBS-03**: Formula accuracy auto-eval: independent calculation vs agent output on every query

### Documentation

- [x] **DOC-01**: README.md covers project overview, team, problem statement, agent design, data sources, setup instructions, AI tools used, limitations
- [x] **DOC-02**: docs/architecture.md finalized with accurate agent design diagrams
- [x] **DOC-03**: .env.example with all required API key placeholders
- [x] **DOC-04**: Data source documentation with URLs, assumptions for simulated data

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Extended Features

- **V2-01**: What-if scenario queries ("What if diesel goes up 2 baht?") using conversation memory
- **V2-02**: Multi-region support beyond Central Region
- **V2-03**: Rate table versioning for historical surcharge accuracy
- **V2-04**: Batch surcharge calculation for multiple routes simultaneously
- **V2-05**: Email/scheduled surcharge reports for operations team

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Rate table admin CRUD | Zero grading value; rate data seeded via scripts |
| User authentication / OAuth | Not relevant to agent architecture grading |
| Mobile native app | Web-first; responsive design sufficient |
| Docker/Kubernetes deployment | Grading requires local reproducibility, not production infra |
| Fine-tuning / custom model training | Gemini Flash free tier; prompt engineering is correct approach |
| Complex RAG with vector store | Tabular data; SQLite + Tavily covers structured + unstructured |
| Real-time webhook notifications | SSE streaming sufficient for demo |
| Grafana/Prometheus monitoring | Langfuse covers observability needs |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| TOOL-01 | Phase 2 | Complete |
| TOOL-02 | Phase 2 | Complete |
| TOOL-03 | Phase 2 | Complete |
| TOOL-04 | Phase 2 | Complete |
| TOOL-05 | Phase 5 | Complete |
| TOOL-06 | Phase 1 | Complete |
| ORCH-01 | Phase 3 | Complete |
| ORCH-02 | Phase 2 | Complete |
| ORCH-03 | Phase 2 | Complete |
| ORCH-04 | Phase 3 | Complete |
| ORCH-05 | Phase 3 | Complete |
| ORCH-06 | Phase 1 | Complete |
| ORCH-07 | Phase 5 | Complete |
| ORCH-08 | Phase 3 | Active |
| ORCH-09 | Phase 6 | Complete |
| ORCH-10 | Phase 3 | Active |
| CALC-01 | Phase 1 | Complete |
| CALC-02 | Phase 1 | Complete |
| CALC-03 | Phase 1 | Complete |
| CALC-04 | Phase 1 | Complete |
| API-01 | Phase 3 | Complete |
| API-02 | Phase 3 | Complete |
| API-03 | Phase 3 | Complete |
| API-04 | Phase 3 | Complete |
| API-05 | Phase 7 | Complete |
| UI-01 | Phase 6 | Complete |
| UI-02 | Phase 4 | Complete |
| UI-03 | Phase 4 | Complete |
| UI-04 | Phase 4 | Complete |
| UI-05 | Phase 7 | Complete |
| UI-06 | Phase 4 | Complete |
| OBS-01 | Phase 5 | Complete |
| OBS-02 | Phase 7 | Complete |
| OBS-03 | Phase 5 | Complete |
| DOC-01 | Phase 5 | Complete |
| DOC-02 | Phase 5 | Complete |
| DOC-03 | Phase 1 | Complete |
| DOC-04 | Phase 5 | Complete |

**Coverage:**
- v1 requirements: 43 total
- Mapped to phases: 43
- Unmapped: 0

---
*Requirements defined: 2025-04-04*
*Last updated: 2026-04-04 after roadmap creation*
