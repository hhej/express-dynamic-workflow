# Technology Stack

**Analysis Date:** 2026-04-04

## Languages

**Primary:**
- Python 3.11+ - Backend, LangGraph agent orchestration, data pipeline
- TypeScript/JavaScript - Frontend UI components and API client
- SQL - SQLite database queries for rate tables and conversation state

**Auxiliary:**
- Bash - Data pipeline scripts and environment setup

## Runtime

**Environment:**
- Python 3.11+ (specified in setup instructions)
- Node.js 18+ (specified in setup instructions)

**Package Manager:**
- Python: `pip` with virtual environment (`.venv`)
  - Lockfile: Not detected (requirements.txt referenced but not present in repo)
- Node.js: `npm`
  - Lockfile: Not detected (frontend directory is scaffold-only)

## Frameworks

**Core:**
- LangGraph (agent framework) - Multi-agent graph orchestration for Planner, Fuel, Route, and Pricing agents
- FastAPI (backend web framework) - REST API + SSE streaming for agent responses
- Next.js 15 (frontend framework) - React-based UI with chat interface, trace viewer, and feedback collection
- React 19 (UI library) - Component framework for frontend

**Agent Components:**
- Uvicorn (ASGI server) - HTTP server for FastAPI backend (specified: port 8000)

**Data & Persistence:**
- SQLite - Rate table storage (`data/express.db`), conversation checkpoints (`data/checkpoints.db`)

**Styling & UI:**
- Tailwind CSS - Frontend styling and component framework

**Observability:**
- Langfuse (tracing/evaluation) - LLM call tracking, tool invocation logging, user feedback scoring

## Key Dependencies

**Critical (Backend):**
- `langgraph` - Multi-agent graph framework with conditional routing and state management
- `fastapi` - Async web framework for REST + SSE endpoints
- `uvicorn` - ASGI server for production serving
- `google-generativeai` (Gemini SDK) - LLM provider for agent reasoning
- `google-maps-services` - Google Maps Directions API client for route calculation
- `tavily-python` - Web search API client for fuel market news
- `langfuse` - Observability/tracing integration for agent monitoring

**Data & Storage:**
- `sqlite3` (Python stdlib) - Database client for rate tables and checkpoints
- `pandas` - Data pipeline for CSV processing (referenced in `data/scripts/`)

**Infrastructure:**
- Checkpointer for LangGraph - SQLite-backed (`data/checkpoints.db`) for session memory persistence

## Configuration

**Environment:**
- `.env` file (required, use `.env.example` template in `/Users/pollot/Desktop/express-dynamic-workflow/.env.example`)
- Loaded via environment variables for:
  - API credentials (GOOGLE_API_KEY, GOOGLE_MAPS_API_KEY, TAVILY_API_KEY)
  - Observability keys (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)
  - App settings (BACKEND_PORT=8000, FRONTEND_PORT=3000)
  - Surcharge configuration (BASELINE_DIESEL_PRICE, SURCHARGE_CAP, SURCHARGE_FLOOR)
  - Database paths (DATABASE_PATH, CHECKPOINT_PATH)

**Build:**
- Backend: FastAPI automatic API documentation generation (Swagger/OpenAPI)
- Frontend: Next.js build system with TypeScript compilation

## Platform Requirements

**Development:**
- Python 3.11+ with pip and venv support
- Node.js 18+ with npm
- Git for version control
- API keys from: Google AI Studio (Gemini), Google Maps Platform, Tavily, Langfuse

**Production:**
- Deployment target: Not specified in documentation
- Backend can run on any Python ASGI-compatible server (Uvicorn specified for dev)
- Frontend requires Node.js for build, but outputs static assets
- Both components require internet connectivity for external API calls
- SQLite databases must be accessible (local file-based)

## Data Sources & External APIs

**Fuel Prices:**
- EPPO (Thailand Department of Energy Business) - Public data source or scraping
- PTT Price Board - Alternative live API/web scraping source

**Geographic/Route Data:**
- Google Maps Directions API - Distance, duration, and traffic data for Thailand Central Region

**Search/Market Context:**
- Tavily Search API - Web search for fuel market news and trend analysis

**LLM Provider:**
- Google AI Studio (Gemini 2.0 Flash) - Free tier with 15 RPM limit noted as constraint

## Database Schema

**Rate Database (`data/express.db`):**
- Created from CSV seed via `data/scripts/seed_database.py`
- Contains: Shipping types (bounce, retail_standard, retail_fast), zones (central-1, central-2, central-3), weight tiers, base rates in THB

**Checkpoint Database (`data/checkpoints.db`):**
- LangGraph SQLite checkpointer
- Stores: Conversation thread state, message history, agent state (fuel_data, route_data, surcharge_result, reasoning_trace)

**Rate Table CSV Source (`data/raw/express_rate_table.csv`):**
- Generated via `data/scripts/generate_rate_table.py` with documented assumptions
- 3 shipping types × 3 zones × multiple weight tiers

**Fuel Price CSV (`data/raw/eppo_diesel_prices.csv`):**
- Downloaded via `data/scripts/fetch_fuel_prices.py`
- Source: EPPO or PTT
- Updated frequency: Daily (per documentation)

## Environment Variables Required

See `.env.example` in `/Users/pollot/Desktop/express-dynamic-workflow/.env.example`:

```
GOOGLE_API_KEY              # Gemini LLM API key
GOOGLE_MAPS_API_KEY         # Google Maps Directions API key
TAVILY_API_KEY              # Tavily Search API key
LANGFUSE_PUBLIC_KEY         # Langfuse observability public key
LANGFUSE_SECRET_KEY         # Langfuse observability secret key
LANGFUSE_HOST               # Langfuse endpoint (default: https://cloud.langfuse.com)
BACKEND_PORT                # FastAPI server port (default: 8000)
FRONTEND_PORT               # Next.js dev server port (default: 3000)
DATABASE_PATH               # SQLite rate table path (default: data/express.db)
CHECKPOINT_PATH             # LangGraph checkpoint DB path (default: data/checkpoints.db)
BASELINE_DIESEL_PRICE       # Baseline fuel price for surcharge calculations (default: 29.94 THB/L)
SURCHARGE_CAP               # Maximum surcharge percentage (default: 0.15 = 15%)
SURCHARGE_FLOOR             # Minimum surcharge percentage (default: -0.05 = -5% discount)
```

## Performance & Constraints

**LLM Rate Limits:**
- Gemini free tier: 15 requests per minute (noted as sufficient for demo, not production)

**API Caching:**
- Route calculations cached for 15 minutes to reduce Google Maps API calls
- Fuel data cached in agent state with 1-hour TTL
- Conversation memory reduces redundant tool calls across follow-up questions

**Response Time Targets:**
- Agent latency target: < 10 seconds per query (tracked via Langfuse)

---

*Stack analysis: 2026-04-04*
