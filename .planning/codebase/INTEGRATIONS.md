# External Integrations

**Analysis Date:** 2026-04-04

## APIs & External Services

**LLM Provider:**
- Google Gemini 2.0 Flash - Agent reasoning and response generation
  - SDK/Client: `google-generativeai` Python package
  - Auth: `GOOGLE_API_KEY` environment variable from Google AI Studio
  - Rate limit: 15 requests per minute (free tier)
  - Constraint: Not suitable for production without upgrade

**Mapping & Route Calculation:**
- Google Maps Directions API - Distance, duration, traffic severity, zone mapping
  - SDK/Client: `google-maps-services` Python package
  - Auth: `GOOGLE_MAPS_API_KEY` environment variable from Google Cloud
  - Caching: Route results cached for 15 minutes in agent state
  - Usage: Invoked by Route Agent node via `calculate_route` tool
  - Fallback: None documented; API failure triggers retry + graceful degradation warning

**Web Search & Market Context:**
- Tavily Search API - Fuel price news, market trends, context for agent reasoning
  - SDK/Client: `tavily-python` Python package
  - Auth: `TAVILY_API_KEY` environment variable
  - Usage: Invoked by Fuel Agent node via `search_fuel_news` tool
  - Purpose: Provides transparency in agent reasoning (agent can cite why prices are moving)
  - Triggered by: User queries about trends or market context

**Observability & Tracing:**
- Langfuse - LLM call tracing, agent step logging, evaluation framework, user feedback scoring
  - SDK/Client: `langfuse` Python package integrated with LangGraph callback handlers
  - Auth: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` (default: https://cloud.langfuse.com)
  - Automatic Tracing:
    - LLM calls (model, tokens, latency, prompts)
    - Tool invocations (tool name, input, output, duration)
    - Agent steps (which agent ran, decisions, reasoning)
  - User Feedback Integration:
    - Endpoint: `POST /api/feedback` (backend route to Langfuse Score API)
    - Maps UI thumbs up/down to Langfuse scores
    - Feedback reasons tracked for analysis

## Data Storage

**Databases:**

**Primary Rate Table Database:**
- Type: SQLite (file-based)
- Location: `data/express.db` (path configurable via `DATABASE_PATH` env var)
- Client: Python `sqlite3` stdlib module
- Purpose: Stores Express shipping rates (3 types × 3 zones × weight tiers)
- Seeding: `data/scripts/seed_database.py` loads from `data/raw/express_rate_table.csv`
- Accessed by: `lookup_rate` tool in Pricing Agent node
- Schema: 
  - Tables: shipping_types, zones, rates (with weight_tier, base_rate_thb columns)
  - Relationships: shipping_type → zone → weight_tier → base_rate

**Conversation State Database (LangGraph Checkpointer):**
- Type: SQLite (file-based)
- Location: `data/checkpoints.db` (path configurable via `CHECKPOINT_PATH` env var)
- Client: LangGraph SQLite checkpointer (integrated with graph execution)
- Purpose: Persists conversation threads, message history, and agent state across sessions
- Key: Thread ID (UUID assigned per conversation)
- Stored State:
  - `messages`: Full conversation history (BaseMessage objects)
  - `fuel_data`: Current fuel price, baseline, delta % (cached, 1-hour TTL)
  - `route_data`: Origin, destination, distance, traffic, zone
  - `shipping_type`, `weight_kg`: Parsed from user query
  - `surcharge_result`: Base rate, surcharge %, amount, total, capped flag
  - `reasoning_trace`: List of agent steps for transparency
  - `next_step`: Current routing decision (conditional edge)
- Enable: Follow-up questions and context preservation without re-fetching

**File Storage:**
- Local filesystem only (no cloud storage)
- CSV data sources in `data/raw/`:
  - `eppo_diesel_prices.csv` - Historical fuel prices (downloaded daily)
  - `express_rate_table.csv` - Rate assumptions (generated once, manually updated)

**Caching:**
- In-memory during conversation (AgentState):
  - fuel_data persists across turns (TTL: 1 hour)
  - route_data persists across turns (invalidated if origin/destination changes)
- Route calculation cache: 15 minutes
- No distributed cache (single-process app)

## Authentication & Identity

**Auth Provider:**
- Custom: No user authentication system documented
- Single-user/public app (no user management)
- All authentication is API-key based for external services

**Authorization:**
- Not applicable (no user roles or permission system)

**Session Management:**
- Thread-based: Each conversation gets a unique thread_id (UUID)
- Persisted in LangGraph checkpointer (`data/checkpoints.db`)
- Frontend manages thread_id in conversation sidebar for history
- No login required; conversations accessed by thread ID

## Monitoring & Observability

**Error Tracking & Tracing:**
- Primary: Langfuse (cloud-based)
  - Traces every LLM call, tool invocation, agent step
  - Endpoint: https://cloud.langfuse.com (configurable)
  - Integration: Callback handlers passed to LangGraph execution
- Secondary: Application logs (not detailed in docs)

**Logging:**
- Approach: Not fully specified in documentation
- Reasoning trace: Custom `reasoning_trace` list in AgentState captures agent decisions
- Fallback handling: Warnings included in reasoning trace when tools fail or cached data is used

**Metrics & Monitoring:**
- Langfuse dashboard tracks:
  - Latency per query (target: < 10s)
  - Token usage per LLM call (cost tracking)
  - Tool success/failure rates
  - Reasoning coherence (manual review)

**Evaluation Framework:**
- Auto-evaluation: Formula accuracy (independent calculation vs agent output), every query
- Manual evaluation: User thumbs up/down from UI
- User feedback scores sent to Langfuse Score API via `POST /api/feedback`
- Feedback categories: wrong_price, wrong_route, wrong_surcharge_type, etc.

## CI/CD & Deployment

**Hosting:**
- Not specified in documentation
- Backend: FastAPI server (any Python ASGI-compatible host)
  - Dev server: `uvicorn main:app --reload --port 8000`
  - Requires: Python 3.11+, API keys, SQLite DB access
- Frontend: Next.js static build output
  - Dev server: `npm run dev` (port 3000)
  - Requires: Node.js 18+

**CI Pipeline:**
- Not detected (no GitHub Actions, Jenkins, or CI config files in repo)

**Deployment Notes:**
- Databases must be accessible at configured paths
- External API keys required in environment
- No containerization (Dockerfile/docker-compose) detected in scaffold

## Webhooks & Callbacks

**Incoming Webhooks:**
- Not documented; no webhook ingestion endpoints specified

**Outgoing Webhooks/Callbacks:**
- Langfuse callback handler integrated with LangGraph
  - Automatically sends traces, scores, evaluations to https://cloud.langfuse.com
- User feedback callback: `POST /api/feedback` → Langfuse Score API

## Data Flow Between Systems

**Query Processing Flow:**

1. **Frontend** (Next.js) sends user message to `POST /api/chat` with thread_id
2. **Backend** (FastAPI) receives request:
   - Loads conversation state from `data/checkpoints.db` using thread_id
   - Invokes LangGraph orchestrator with user message
3. **LangGraph Orchestrator**:
   - Planner node reasons about user intent
   - Conditionally invokes specialist agents based on `next_step`:
     - Fuel Agent → `fetch_fuel_price` tool (Google Gemini reasoning + fallback to CSV)
     - Route Agent → `calculate_route` tool (Google Maps API)
     - Pricing Agent → `lookup_rate` tool (SQLite), `calculate_surcharge` tool (pure calculation)
     - Search Agent → `search_fuel_news` tool (Tavily API)
   - Saves updated state to `data/checkpoints.db` checkpoint
4. **Callback Handler** (Langfuse):
   - Intercepts all LLM calls and tool invocations
   - Sends traces to https://cloud.langfuse.com in real-time
5. **Backend Response**:
   - Streams response via SSE to frontend as reasoning trace JSON + final answer
6. **Frontend Display**:
   - Shows chat message, trace panel (tools called, outputs), surcharge table
   - Collects user feedback (thumbs up/down)
7. **Feedback Loop**:
   - User clicks thumbs down → selects reason
   - Frontend sends `POST /api/feedback` with score + reason
   - Backend forwards to Langfuse Score API

## Data Requirements

**Environment Configuration:**

Required env vars (see `/Users/pollot/Desktop/express-dynamic-workflow/.env.example`):
- `GOOGLE_API_KEY` - Gemini LLM
- `GOOGLE_MAPS_API_KEY` - Route calculations
- `TAVILY_API_KEY` - Search/news context
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` - Observability
- `BACKEND_PORT`, `FRONTEND_PORT` - Server ports
- `DATABASE_PATH`, `CHECKPOINT_PATH` - SQLite files
- `BASELINE_DIESEL_PRICE`, `SURCHARGE_CAP`, `SURCHARGE_FLOOR` - Surcharge configuration

**Data Seeding:**
1. `data/scripts/fetch_fuel_prices.py` → downloads EPPO/PTT data → `data/raw/eppo_diesel_prices.csv`
2. `data/scripts/generate_rate_table.py` → generates assumptions → `data/raw/express_rate_table.csv`
3. `data/scripts/seed_database.py` → loads CSVs → `data/express.db` (SQLite)
4. `data/checkpoints.db` auto-created by LangGraph on first conversation

**Initial Setup:**
```bash
# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Seed databases
cd ../data/scripts
python fetch_fuel_prices.py
python generate_rate_table.py
python seed_database.py

# Frontend setup
cd ../../frontend
npm install
```

---

*Integration audit: 2026-04-04*
