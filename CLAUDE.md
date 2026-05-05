<!-- GSD:project-start source:PROJECT.md -->
## Project

**Express Dynamic Surcharge Orchestrator**

An Agentic AI product that dynamically calculates fuel surcharges for Express logistics operations in Thailand's Bangkok Metro. The agent reasons over live fuel prices, route data, and internal rate tables to produce surcharge recommendations — it is the core decision-making product, not a feature on a dashboard. Built as a MADT7204 course project demonstrating multi-agent AI architecture with real-world logistics impact.

**Core Value:** The agent must transparently reason through fuel price, route, and shipping data to produce an accurate, explainable surcharge recommendation — visible reasoning is what makes this agentic, not just automated.

### Constraints

- **Budget**: Free-tier APIs only — Gemini Flash, Google Maps ($200/mo credit), EPPO public data
- **LLM**: Gemini 2.0 Flash only — no paid model APIs
- **Timeline**: 6 weeks total; W5 is code freeze + docs, W6 is final demo
- **Repo structure**: Must follow brief-mandated layout (agent/, app/, data/, docs/, notebooks/)
- **Secrets**: Never commit .env — .env.example required, violations affect grade
- **Git practice**: Descriptive commit messages, feature branches, IT Lead holds majority of commits — graded at 20%
- **Data**: At least one real dataset must be queried by agent (EPPO fuel prices satisfy this)
- **Submission**: Tag final commit as v1.0, submit repo URL
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11+ - Backend, LangGraph agent orchestration, data pipeline
- TypeScript/JavaScript - Frontend UI components and API client
- SQL - SQLite database queries for rate tables and conversation state
- Bash - Data pipeline scripts and environment setup
## Runtime
- Python 3.11+ (specified in setup instructions)
- Node.js 18+ (specified in setup instructions)
- Python: `pip` with virtual environment (`.venv`)
- Node.js: `npm`
## Frameworks
- LangGraph (agent framework) - Multi-agent graph orchestration for Planner, Fuel, Route, and Pricing agents
- FastAPI (backend web framework) - REST API + SSE streaming for agent responses
- Next.js 15 (frontend framework) - React-based UI with chat interface, trace viewer, and feedback collection
- React 19 (UI library) - Component framework for frontend
- Uvicorn (ASGI server) - HTTP server for FastAPI backend (specified: port 8000)
- SQLite - Rate table storage (`data/express.db`), conversation checkpoints (`data/checkpoints.db`)
- Tailwind CSS - Frontend styling and component framework
- Langfuse (tracing/evaluation) - LLM call tracking, tool invocation logging, user feedback scoring
## Key Dependencies
- `langgraph` - Multi-agent graph framework with conditional routing and state management
- `fastapi` - Async web framework for REST + SSE endpoints
- `uvicorn` - ASGI server for production serving
- `google-generativeai` (Gemini SDK) - LLM provider for agent reasoning
- `google-maps-services` - Google Maps Directions API client for route calculation
- `tavily-python` - Web search API client for fuel market news
- `langfuse` - Observability/tracing integration for agent monitoring
- `sqlite3` (Python stdlib) - Database client for rate tables and checkpoints
- `pandas` - Data pipeline for CSV processing (referenced in `data/scripts/`)
- Checkpointer for LangGraph - SQLite-backed (`data/checkpoints.db`) for session memory persistence
## Configuration
- `.env` file (required, use `.env.example` template in `/Users/pollot/Desktop/express-dynamic-workflow/.env.example`)
- Loaded via environment variables for:
- Backend: FastAPI automatic API documentation generation (Swagger/OpenAPI)
- Frontend: Next.js build system with TypeScript compilation
## Platform Requirements
- Python 3.11+ with pip and venv support
- Node.js 18+ with npm
- Git for version control
- API keys from: Google AI Studio (Gemini), Google Maps Platform, Tavily, Langfuse
- Deployment target: Not specified in documentation
- Backend can run on any Python ASGI-compatible server (Uvicorn specified for dev)
- Frontend requires Node.js for build, but outputs static assets
- Both components require internet connectivity for external API calls
- SQLite databases must be accessible (local file-based)
## Data Sources & External APIs
- EPPO (Thailand Department of Energy Business) - Public data source or scraping
- PTT Price Board - Alternative live API/web scraping source
- Google Maps Directions API - Distance, duration, and traffic data for Thailand's Bangkok Metro
- Tavily Search API - Web search for fuel market news and trend analysis
- Google AI Studio (Gemini 2.0 Flash) - Free tier with 15 RPM limit noted as constraint
## Database Schema
- Created from CSV seed via `data/scripts/seed_database.py`
- Contains: Shipping types (bounce, retail_standard, retail_fast), zones (central-1, central-2, central-3), weight tiers, base rates in THB
- LangGraph SQLite checkpointer
- Stores: Conversation thread state, message history, agent state (fuel_data, route_data, surcharge_result, reasoning_trace)
- Generated via `data/scripts/generate_rate_table.py` with documented assumptions
- 3 shipping types × 3 zones × multiple weight tiers
- Downloaded via `data/scripts/fetch_fuel_prices.py`
- Source: EPPO or PTT
- Updated frequency: Daily (per documentation)
## Environment Variables Required
## Performance & Constraints
- Gemini free tier: 15 requests per minute (noted as sufficient for demo, not production)
- Route calculations cached for 15 minutes to reduce Google Maps API calls
- Fuel data cached in agent state with 1-hour TTL
- Conversation memory reduces redundant tool calls across follow-up questions
- Agent latency target: < 10 seconds per query (tracked via Langfuse)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Project Status
## Language-Specific Conventions
### Python Backend
- `backend/agent/` — LangGraph orchestrator and multi-agent nodes
- `backend/agent/nodes/` — Individual agent implementations (Planner, Fuel Agent, Route Agent, Pricing Agent)
- `backend/agent/tools/` — Tool definitions (fetch_fuel_price, calculate_route, lookup_rate, calculate_surcharge, search_fuel_news)
- `backend/agent/prompts/` — Prompt templates for LLM calls
- `backend/api/` — FastAPI application, endpoints, request/response models
- `backend/evaluation/` — Evaluation and testing utilities
### TypeScript/JavaScript Frontend
- `frontend/app/` — Next.js 15 app directory (pages, layouts)
- `frontend/components/` — React components
- `frontend/hooks/` — Custom React hooks
- `frontend/lib/` — Utilities and helpers
- `frontend/api/` — Client-side API calls/services
## Naming Patterns
### Python Files and Functions
- Module files: `snake_case.py` (e.g., `fetch_fuel_prices.py`, `agent_state.py`)
- Test files: `test_<module>.py` (co-located with source or in `tests/` directory)
- Functions and methods: `snake_case()` (e.g., `fetch_fuel_price()`, `calculate_surcharge()`)
- Private functions: Prefix with `_` (e.g., `_validate_input()`)
- Class methods following Python conventions (lowercase)
- Classes: `PascalCase` (e.g., `AgentState`, `FuelAgent`, `PricingAgent`)
- Dataclass/TypedDict: `PascalCase` (e.g., `FuelData`, `RouteData`, `SurchargeResult`)
- Variables: `snake_case` (e.g., `fuel_data`, `base_rate`, `traffic_severity`)
- Constants: `UPPER_CASE` (e.g., `BASELINE_DIESEL_PRICE`, `MAX_SURCHARGE_CAP`)
- Agent/node names in state: lowercase with underscores (e.g., `fetch_fuel`, `fetch_route`, `calculate_price`)
### TypeScript/JavaScript Files and Components
- Component files: `PascalCase.tsx` (e.g., `ChatInterface.tsx`, `SurchargeChart.tsx`)
- Hook files: `use<HookName>.ts` (e.g., `useFetchConversation.ts`)
- Utility files: `camelCase.ts` (e.g., `apiClient.ts`, `formatters.ts`)
- Type definition files: `types.ts` or `<domain>.types.ts` (e.g., `api.types.ts`, `agent.types.ts`)
- Functions: `camelCase()` (e.g., `formatSurcharge()`, `parseAgentResponse()`)
- React hooks: `use<PascalCase>()` (e.g., `useChat()`, `useFeedback()`)
- Variables: `camelCase` (e.g., `currentFuelPrice`, `surchargeAmount`, `isLoading`)
- React state: `camelCase` for state and setter names (e.g., `const [isLoading, setIsLoading]`)
- Types/Interfaces: `PascalCase` (e.g., `AgentMessage`, `SurchargeResponse`, `ChatState`)
- Type files: `*.types.ts` or interfaces inline near usage
## Code Style
### Python
- Follow **PEP 8** standard
- Line length: 88 characters (Black formatter default)
- Use `black` for automatic formatting if available
- Use `ruff` for linting (modern, fast replacement for flake8/pylint)
- Use specific exception types (not bare `except:`)
- Define custom exceptions in a `exceptions.py` file at the package level
- Include context in error messages with relevant data (e.g., "Failed to fetch fuel price for region: central")
- Use type hints for all function signatures
- Use `TypedDict` for dictionary-based state structures (e.g., `AgentState`)
- Use `Optional[]` or `|` (Python 3.10+) for optional values
### TypeScript/JavaScript
- Use **Prettier** with consistent settings (`.prettierrc`)
- Line length: 80-100 characters (project standard to be defined)
- Configure ESLint with `@next/next` and React plugin
- Use try/catch with proper error typing
- Log errors to console in development, to observability in production
- Provide user-friendly error messages
## Import Path Aliases
### Python Backend
- No aliases required; use relative imports for same-package modules
- Use absolute imports for different packages: `from backend.agent.nodes import ...`
### TypeScript Frontend
- Configure `jsconfig.json` or `tsconfig.json` with path aliases:
- Use `@/` prefix for absolute imports within the app
## Comments and Documentation
### Python
- Complex algorithm logic (especially surcharge calculation with traffic adjustments)
- Non-obvious LangGraph routing decisions
- Fallback mechanisms and error recovery paths
- Assumptions about data formats or external API contracts
- Use Google-style docstrings for all public functions/classes
- Include Args, Returns, Raises sections
### TypeScript/JavaScript
- Use JSDoc for public functions and component prop types
- Describe purpose, params, and return type
## Agent and Node Conventions
### LangGraph Agent Nodes
- Each node implementation in `backend/agent/nodes/<node_name>.py`
- Exports a single callable or function matching the node's name
- Uses type hints with `AgentState` from `backend/agent/state.py`
- Node names: `<agent_name>_node` (e.g., `fuel_agent_node`, `pricing_agent_node`)
- Next step routing values: lowercase with underscores (e.g., `fetch_fuel`, `fetch_route`, `calculate_price`, `respond`)
### Tool Definitions
## State Management Conventions
### AgentState (LangGraph)
- Use `TypedDict` for clarity and type safety
- Include comment describing each field
- Keys are `snake_case`
### Frontend Component State
## API Design Conventions
### FastAPI Endpoints
- Use Pydantic `BaseModel` for all request/response bodies
- Define in `backend/api/models.py` or `backend/api/schemas.py`
- Use descriptive field names with type hints
- Resource-based (e.g., `/api/chat`, `/api/conversations`, `/api/feedback`)
- Use HTTP methods correctly (POST for mutations, GET for queries)
### Frontend API Client
## Constants and Configuration
### Python
### TypeScript
## Logging Conventions
### Python
- Tool invocations (start and result)
- Cache hits/misses
- Fallback mechanisms
- Errors with full context
### TypeScript/React
## File Organization Summary
- Agent logic: `backend/agent/nodes/*.py`
- Tools: `backend/agent/tools/*.py`
- Prompts: `backend/agent/prompts/*.py`
- API endpoints: `backend/api/routes/*.py`
- Models: `backend/api/models.py`
- State: `backend/agent/state.py`
- Config: `backend/config.py`
- Tests: `backend/tests/test_*.py`
- Pages: `frontend/app/*.tsx`
- Components: `frontend/components/*.tsx`
- Hooks: `frontend/hooks/use*.ts`
- API: `frontend/lib/api.ts`
- Types: `frontend/types/*.ts`
- Utils: `frontend/lib/*.ts`
- Tests: `frontend/__tests__/`, `frontend/components/*.test.tsx`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- **Multi-agent pattern**: One planner agent routes to four specialist agents (Fuel, Route, Pricing, Response)
- **Stateful graph execution**: LangGraph manages conditional routing based on user intent and cached state
- **Tool-driven reasoning**: Each agent calls external tools (APIs, databases) and incorporates results into reasoning
- **Memory-aware**: Caches tool results (fuel prices, routes) to optimize follow-up questions without re-fetching
- **Observability first**: All traces logged to Langfuse for evaluation, debugging, and user feedback integration
## Layers
- Purpose: Coordinate multi-agent workflow, manage state transitions, decide which agents to invoke
- Location: `backend/agent/` (planned nodes and graph definition)
- Contains: Planner node, conditional routing logic, agent state management
- Depends on: Tool definitions, LangGraph framework
- Used by: API endpoints that receive user messages
- Purpose: Execute focused tasks — fetch fuel data, calculate routes, look up rates, compute surcharges
- Location: `backend/agent/nodes/` (individual agent implementations)
- Contains: Fuel Agent, Route Agent, Pricing Agent node implementations
- Depends on: Tool layer, external APIs, SQLite databases
- Used by: Orchestration layer (routed conditionally by planner)
- Purpose: Provide concrete implementations for external data access (APIs, databases, calculations)
- Location: `backend/agent/tools/` (tool definitions and wrappers)
- Contains: fetch_fuel_price, calculate_route, lookup_rate, calculate_surcharge, search_fuel_news
- Depends on: External services (EPPO, Google Maps, Tavily), SQLite databases
- Used by: Specialist agents during execution
- Purpose: Store system prompts and instructions for agents
- Location: `backend/agent/prompts/` (prompt templates per agent)
- Contains: System prompts for Planner, Fuel Agent, Route Agent, Pricing Agent
- Depends on: Agent implementation
- Used by: Each agent to define behavior and output format
- Purpose: Expose agent functionality via REST endpoints, handle session management
- Location: `backend/api/` (endpoint definitions)
- Contains: POST /api/chat (streaming), GET /api/conversations, POST /api/feedback, GET /api/fuel-prices
- Depends on: Orchestration layer, conversation memory database
- Used by: Frontend, external consumers
- Purpose: Persistent storage of rate tables, fuel prices, and conversation checkpoints
- Location: `data/raw/` (CSV source data), `data/` (SQLite databases)
- Contains: express.db (rate tables), checkpoints.db (LangGraph session memory), eppo_diesel_prices.csv (historical fuel)
- Depends on: None
- Used by: Tool layer for data lookups, LangGraph for conversation memory
## Data Flow
- `messages`: Full conversation history (enables follow-up context)
- `fuel_data`: Current diesel price + baseline + delta_pct (cached, TTL 1 hour)
- `route_data`: Distance, traffic, zone (cached until origin/destination changes)
- `shipping_type`: Determined from user message
- `weight_kg`: Shipment weight (from user message)
- `surcharge_result`: Computed surcharge with breakdown
- `reasoning_trace`: Agent steps for transparency panel
- `next_step`: Conditional routing target
## Key Abstractions
- Purpose: Encapsulate domain logic (fuel analysis, routing, pricing) in LLM-backed agents
- Examples: Fuel Agent (`backend/agent/nodes/fuel_agent.py`), Route Agent, Pricing Agent
- Pattern: Each agent receives state, may call tools, outputs reasoning + results, returns updated state
- Purpose: Abstract external services and databases behind a common interface
- Examples: `fetch_fuel_price` (EPPO/PTT API), `calculate_route` (Google Maps), `lookup_rate` (SQLite)
- Pattern: Tool receives structured input, calls external service, catches/handles errors, returns structured output
- Purpose: Direct agent execution based on planner's decision and current state
- Examples: Skip Fuel Agent if fuel_data cached and fresh; route to Pricing Agent only when all inputs available
- Pattern: Planner outputs `next_step`, LangGraph edges check `next_step` field, route accordingly
- Purpose: Persist conversation state across API calls, enable conversation resumption
- Examples: Retrieving old thread_id to continue past conversation
- Pattern: Thread ID maps to row in checkpoints.db, row contains pickled AgentState
## Entry Points
- Location: `backend/api/` (chat endpoint)
- Triggers: POST request with `{thread_id: str, message: str}`
- Responsibilities: Extract message, load checkpointer state, invoke graph, stream results, persist state, send to Langfuse
- Location: `data/scripts/fetch_fuel_prices.py`, `generate_rate_table.py`, `seed_database.py`
- Triggers: Manual execution (cron job or manual run)
- Responsibilities: Fetch EPPO data, generate rate table assumptions, seed SQLite databases
- Location: `frontend/` (Next.js app)
- Triggers: User types message + clicks send
- Responsibilities: Call /api/chat, parse SSE stream, update conversation UI, display trace panel, submit feedback
## Error Handling
- If fuel API unavailable: Fall back to latest row in `data/raw/eppo_diesel_prices.csv`
- If Google Maps fails: Use cached route data with warning in reasoning trace
- If lookup_rate fails: Return generic rate with explanation to user
- All fallbacks logged in reasoning_trace for transparency
- Retry 1 time after 2 second delay
- If still fails: Return partial result with explanation ("Could not complete analysis, here's what I found...")
- Planner routes to `clarify` path via Response node
- Node asks user for missing information with example queries
- Does not block conversation, suggests how to phrase request
- calculate_surcharge tool automatically applies min/max caps (15% max, -5% min)
- Sets `capped: true` flag in result
- Agent's reasoning trace explains why cap was hit and recommends review
- Retry SQLite operations up to 2 times
- If persistent: Return error in reasoning_trace, suggest contact support
## Cross-Cutting Concerns
- Approach: Structured logging via LangGraph's built-in logging + Langfuse callback handler
- Every agent step, tool call, and decision is logged to Langfuse automatically
- Backend console logs warnings/errors with context
- Approach: Input validation at API layer (message structure, thread_id format)
- Type validation in AgentState (TypedDict with annotations)
- Tool outputs validated against expected schema before state update
- Surcharge calculation validates weight > 0, shipping_type in [bounce, retail_standard, retail_fast]
- Approach: Not enforced in MVP (demo system with public API)
- Thread IDs are opaque UUIDs (cannot enumerate conversations without thread_id)
- In production: Add API key validation or OAuth at API gateway
- Approach: Implicit via Gemini free tier (15 RPM limit)
- Langfuse observability can detect when rate limit hit
- Fallback behavior: Return previous result + explanation if limit exceeded
- Approach: Full trace via Langfuse callback handler
- Every LLM call, tool call, and state transition captured automatically
- User feedback from thumbs up/down integrated into Langfuse scoring
- Frontend renders reasoning_trace array as expandable trace panel
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
