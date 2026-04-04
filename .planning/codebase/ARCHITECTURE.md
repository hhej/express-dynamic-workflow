# Architecture

**Analysis Date:** 2026-04-04

## Pattern Overview

**Overall:** Multi-Agent Orchestration with LangGraph

This is an **agentic AI system** where the core product is intelligent decision-making (surcharge recommendations), not a traditional request-response API. The system uses LangGraph to orchestrate multiple specialist agents that work together to collect data, reason over it, and produce transparent recommendations.

**Key Characteristics:**
- **Multi-agent pattern**: One planner agent routes to four specialist agents (Fuel, Route, Pricing, Response)
- **Stateful graph execution**: LangGraph manages conditional routing based on user intent and cached state
- **Tool-driven reasoning**: Each agent calls external tools (APIs, databases) and incorporates results into reasoning
- **Memory-aware**: Caches tool results (fuel prices, routes) to optimize follow-up questions without re-fetching
- **Observability first**: All traces logged to Langfuse for evaluation, debugging, and user feedback integration

## Layers

**Orchestration Layer (Agent Graph):**
- Purpose: Coordinate multi-agent workflow, manage state transitions, decide which agents to invoke
- Location: `backend/agent/` (planned nodes and graph definition)
- Contains: Planner node, conditional routing logic, agent state management
- Depends on: Tool definitions, LangGraph framework
- Used by: API endpoints that receive user messages

**Specialist Agent Layer:**
- Purpose: Execute focused tasks — fetch fuel data, calculate routes, look up rates, compute surcharges
- Location: `backend/agent/nodes/` (individual agent implementations)
- Contains: Fuel Agent, Route Agent, Pricing Agent node implementations
- Depends on: Tool layer, external APIs, SQLite databases
- Used by: Orchestration layer (routed conditionally by planner)

**Tool Layer:**
- Purpose: Provide concrete implementations for external data access (APIs, databases, calculations)
- Location: `backend/agent/tools/` (tool definitions and wrappers)
- Contains: fetch_fuel_price, calculate_route, lookup_rate, calculate_surcharge, search_fuel_news
- Depends on: External services (EPPO, Google Maps, Tavily), SQLite databases
- Used by: Specialist agents during execution

**Prompt Layer:**
- Purpose: Store system prompts and instructions for agents
- Location: `backend/agent/prompts/` (prompt templates per agent)
- Contains: System prompts for Planner, Fuel Agent, Route Agent, Pricing Agent
- Depends on: Agent implementation
- Used by: Each agent to define behavior and output format

**API Layer:**
- Purpose: Expose agent functionality via REST endpoints, handle session management
- Location: `backend/api/` (endpoint definitions)
- Contains: POST /api/chat (streaming), GET /api/conversations, POST /api/feedback, GET /api/fuel-prices
- Depends on: Orchestration layer, conversation memory database
- Used by: Frontend, external consumers

**Data Layer:**
- Purpose: Persistent storage of rate tables, fuel prices, and conversation checkpoints
- Location: `data/raw/` (CSV source data), `data/` (SQLite databases)
- Contains: express.db (rate tables), checkpoints.db (LangGraph session memory), eppo_diesel_prices.csv (historical fuel)
- Depends on: None
- Used by: Tool layer for data lookups, LangGraph for conversation memory

## Data Flow

**Query Flow (Synchronous + Streaming):**

1. **User sends message** → `POST /api/chat` with thread_id and message
2. **API creates/retrieves conversation** → Loads LangGraph checkpointer state for thread_id
3. **Graph execution starts** → Planner node receives user message + conversation history
4. **Planner routes** → Analyzes intent, checks memory, outputs next_step (fetch_fuel, fetch_route, calculate_price, etc.)
5. **Conditional edge routes** → LangGraph edges direct to appropriate specialist node
6. **Specialist agent executes** → Calls tools (APIs, database queries), receives results
7. **Results streamed back** → Each intermediate result sent via SSE to frontend
8. **Graph completes** → Final response formatted by Response node
9. **State persisted** → Checkpointer saves updated state (fuel_data, route_data, surcharge_result) to checkpoints.db
10. **Response + trace** → Entire execution trace (all tool calls, reasoning) sent to frontend + Langfuse

**State Management:**

AgentState is maintained across turns and contains:
- `messages`: Full conversation history (enables follow-up context)
- `fuel_data`: Current diesel price + baseline + delta_pct (cached, TTL 1 hour)
- `route_data`: Distance, traffic, zone (cached until origin/destination changes)
- `shipping_type`: Determined from user message
- `weight_kg`: Shipment weight (from user message)
- `surcharge_result`: Computed surcharge with breakdown
- `reasoning_trace`: Agent steps for transparency panel
- `next_step`: Conditional routing target

**Follow-up Question Optimization:**

User: "What's the fuel surcharge for a Bounce shipment, 200kg, Bangkok to Nonthaburi?"
→ Planner fetches fuel_data, route_data, calculates surcharge, saves state

User: "What about Retail Fast for the same route?"
→ Planner checks state, finds fuel_data and route_data still valid
→ Planner only invokes Pricing Agent with different shipping_type
→ Response: ~2 seconds vs 10+ seconds for full fetch

## Key Abstractions

**Agent as Reasoning Function:**
- Purpose: Encapsulate domain logic (fuel analysis, routing, pricing) in LLM-backed agents
- Examples: Fuel Agent (`backend/agent/nodes/fuel_agent.py`), Route Agent, Pricing Agent
- Pattern: Each agent receives state, may call tools, outputs reasoning + results, returns updated state

**Tool as Data Access Wrapper:**
- Purpose: Abstract external services and databases behind a common interface
- Examples: `fetch_fuel_price` (EPPO/PTT API), `calculate_route` (Google Maps), `lookup_rate` (SQLite)
- Pattern: Tool receives structured input, calls external service, catches/handles errors, returns structured output

**Conditional Routing in Graph:**
- Purpose: Direct agent execution based on planner's decision and current state
- Examples: Skip Fuel Agent if fuel_data cached and fresh; route to Pricing Agent only when all inputs available
- Pattern: Planner outputs `next_step`, LangGraph edges check `next_step` field, route accordingly

**Memory Checkpointer (LangGraph SQLite):**
- Purpose: Persist conversation state across API calls, enable conversation resumption
- Examples: Retrieving old thread_id to continue past conversation
- Pattern: Thread ID maps to row in checkpoints.db, row contains pickled AgentState

## Entry Points

**Chat API Endpoint:**
- Location: `backend/api/` (chat endpoint)
- Triggers: POST request with `{thread_id: str, message: str}`
- Responsibilities: Extract message, load checkpointer state, invoke graph, stream results, persist state, send to Langfuse

**Data Ingestion Scripts:**
- Location: `data/scripts/fetch_fuel_prices.py`, `generate_rate_table.py`, `seed_database.py`
- Triggers: Manual execution (cron job or manual run)
- Responsibilities: Fetch EPPO data, generate rate table assumptions, seed SQLite databases

**Frontend Chat Interface:**
- Location: `frontend/` (Next.js app)
- Triggers: User types message + clicks send
- Responsibilities: Call /api/chat, parse SSE stream, update conversation UI, display trace panel, submit feedback

## Error Handling

**Strategy:** Graceful degradation with transparency

**Patterns:**

**Tool Failure with Fallback:**
- If fuel API unavailable: Fall back to latest row in `data/raw/eppo_diesel_prices.csv`
- If Google Maps fails: Use cached route data with warning in reasoning trace
- If lookup_rate fails: Return generic rate with explanation to user
- All fallbacks logged in reasoning_trace for transparency

**LLM Generation Failure:**
- Retry 1 time after 2 second delay
- If still fails: Return partial result with explanation ("Could not complete analysis, here's what I found...")

**Invalid/Incomplete User Input:**
- Planner routes to `clarify` path via Response node
- Node asks user for missing information with example queries
- Does not block conversation, suggests how to phrase request

**Surcharge Out of Bounds:**
- calculate_surcharge tool automatically applies min/max caps (15% max, -5% min)
- Sets `capped: true` flag in result
- Agent's reasoning trace explains why cap was hit and recommends review

**Database Connection Failure:**
- Retry SQLite operations up to 2 times
- If persistent: Return error in reasoning_trace, suggest contact support

## Cross-Cutting Concerns

**Logging:**
- Approach: Structured logging via LangGraph's built-in logging + Langfuse callback handler
- Every agent step, tool call, and decision is logged to Langfuse automatically
- Backend console logs warnings/errors with context

**Validation:**
- Approach: Input validation at API layer (message structure, thread_id format)
- Type validation in AgentState (TypedDict with annotations)
- Tool outputs validated against expected schema before state update
- Surcharge calculation validates weight > 0, shipping_type in [bounce, retail_standard, retail_fast]

**Authentication:**
- Approach: Not enforced in MVP (demo system with public API)
- Thread IDs are opaque UUIDs (cannot enumerate conversations without thread_id)
- In production: Add API key validation or OAuth at API gateway

**Rate Limiting:**
- Approach: Implicit via Gemini free tier (15 RPM limit)
- Langfuse observability can detect when rate limit hit
- Fallback behavior: Return previous result + explanation if limit exceeded

**Observability:**
- Approach: Full trace via Langfuse callback handler
- Every LLM call, tool call, and state transition captured automatically
- User feedback from thumbs up/down integrated into Langfuse scoring
- Frontend renders reasoning_trace array as expandable trace panel
