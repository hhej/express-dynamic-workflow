# Codebase Structure

**Analysis Date:** 2026-04-04

## Directory Layout

```
express-dynamic-workflow/
├── backend/                    # FastAPI backend + LangGraph agent orchestration
│   ├── agent/                  # LangGraph multi-agent system
│   │   ├── nodes/              # Individual agent implementations (Planner, Fuel, Route, Pricing, Response)
│   │   ├── tools/              # Tool definitions (fetch_fuel_price, calculate_route, etc.)
│   │   └── prompts/            # System prompts for each agent
│   ├── api/                    # REST API endpoints (chat, conversations, feedback, fuel-prices)
│   └── evaluation/             # Evaluation and scoring scripts
├── frontend/                   # Next.js 15 React 19 UI (chat, trace panel, charts, feedback)
├── data/                       # Data pipeline and persistence layer
│   ├── raw/                    # Source CSV files (eppo_diesel_prices, express_rate_table)
│   └── scripts/                # Data ingestion scripts (fetch_fuel_prices, generate_rate_table, seed_database)
├── docs/                       # Project documentation
│   └── architecture.md         # System architecture details
├── .planning/                  # GSD codebase mapping output
│   └── codebase/               # Analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
├── .claude/                    # Claude-specific context (memory, project metadata)
├── README.md                   # Project overview and setup instructions
├── .env.example                # Environment variable template
└── .gitignore                  # Git ignore rules
```

## Directory Purposes

**`backend/`:**
- Purpose: Python FastAPI backend serving the LangGraph agent and REST API
- Contains: Agent orchestration code, tool implementations, API endpoints, database queries
- Key files: main.py (entry point), agent graph definition, API route handlers
- Primary tech: Python 3.11+, FastAPI, LangGraph, SQLite

**`backend/agent/`:**
- Purpose: LangGraph multi-agent system that orchestrates surcharge calculation reasoning
- Contains: Agent nodes (Planner, Fuel, Route, Pricing, Response), tool definitions, prompt templates
- Key files: Planner node (routes to specialists based on intent), tool wrappers (fetch_fuel_price, etc.), system prompts
- Pattern: Each agent is a function node in LangGraph graph; tools are Runnable objects passed to agents

**`backend/agent/nodes/`:**
- Purpose: Individual agent implementations as LangGraph nodes
- Contains: planner.py, fuel_agent.py, route_agent.py, pricing_agent.py, response_node.py
- Pattern: Each node is a function that receives AgentState, calls tools conditionally, returns updated state
- Usage: LangGraph graph invokes these nodes based on conditional edges

**`backend/agent/tools/`:**
- Purpose: Tool definitions and wrappers for external API calls and database queries
- Contains: fetch_fuel_price.py, calculate_route.py, lookup_rate.py, calculate_surcharge.py, search_fuel_news.py
- Pattern: Each tool is a Runnable with input schema, docstring (for LLM instruction), and error handling
- Usage: Agents call tools via tool_node in LangGraph; results incorporated into AgentState

**`backend/agent/prompts/`:**
- Purpose: System prompts and instructions for each agent
- Contains: planner_prompt.txt, fuel_agent_prompt.txt, route_agent_prompt.txt, pricing_agent_prompt.txt
- Pattern: Prompts instruct agent what role to play, which tools to call, how to format output
- Usage: Each agent loads its prompt as system message when initialized

**`backend/api/`:**
- Purpose: REST API endpoints that expose agent functionality to frontend
- Contains: chat.py (SSE streaming), conversations.py (list/get), feedback.py, fuel_prices.py
- Key endpoints:
  - POST /api/chat: Send message, receive SSE stream of traces
  - GET /api/conversations: List all conversation threads
  - GET /api/conversations/:id: Resume past conversation
  - POST /api/feedback: Submit user feedback (thumbs up/down + reason)
  - GET /api/fuel-prices?days=30: Get historical fuel data for chart
- Pattern: Each endpoint creates or loads LangGraph checkpointer state, invokes graph, streams/returns results

**`backend/evaluation/`:**
- Purpose: Evaluation and quality assurance utilities
- Contains: Formula accuracy checker (verify surcharge calculation), tool output validator
- Usage: Can be run manually to audit agent outputs or integrated into CI/CD

**`frontend/`:**
- Purpose: Next.js React UI for chat, trace visualization, fuel price charts, feedback
- Contains: App page (chat interface), components (message list, trace panel, chart), API client hooks
- Key files: app/page.tsx (main page), components/ChatInterface.tsx, components/TracePanel.tsx, lib/api.ts
- Pattern: React components call `useEffect` + API client to fetch from backend, SSE hook to stream traces

**`data/`:**
- Purpose: Data pipeline and persistence
- Contains: Source CSVs, scripts to fetch/generate/seed data, SQLite database files (generated)
- Key files:
  - `data/raw/eppo_diesel_prices.csv`: Historical diesel prices (generated by fetch_fuel_prices.py)
  - `data/raw/express_rate_table.csv`: Shipping rate table (generated by generate_rate_table.py)
  - `data/express.db`: SQLite database with rate_table, fuel_prices tables (generated by seed_database.py)
  - `data/checkpoints.db`: LangGraph SQLite checkpointer for conversation memory (auto-created at runtime)

**`data/scripts/`:**
- Purpose: One-time and periodic data ingestion
- Contains: fetch_fuel_prices.py, generate_rate_table.py, seed_database.py
- Usage: Run in order: (1) fetch fuel data, (2) generate rate table, (3) seed databases
- Pattern: Each script reads source/API, processes, writes to CSV/SQLite with logging

**`docs/`:**
- Purpose: Project documentation (architecture details, API specs, etc.)
- Contains: architecture.md (comprehensive system design document)
- Usage: Reference during development, feature planning, and debugging

**`.planning/codebase/`:**
- Purpose: GSD (Good Software Development) codebase analysis documents
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md (as generated)
- Usage: Consumed by orchestrator for code generation, refactoring, and planning

## Key File Locations

**Entry Points:**

- `backend/main.py`: FastAPI app initialization, route registration, middleware setup, graph initialization
- `frontend/app/page.tsx`: Next.js root page, chat interface layout, SSE hook setup
- `backend/agent/graph.py`: LangGraph graph definition (nodes, edges, entry points)

**Configuration:**

- `.env.example`: Template for environment variables (GOOGLE_API_KEY, GOOGLE_MAPS_API_KEY, etc.)
- `.env`: Actual secrets and configuration (not committed, generated from .env.example)
- `pyproject.toml` or `requirements.txt`: Python dependencies (in backend/ directory)
- `package.json`: Node.js dependencies (in frontend/ directory)

**Core Logic:**

- `backend/agent/nodes/planner.py`: Main orchestrator logic (decides which agents to invoke)
- `backend/agent/tools/fetch_fuel_price.py`: Fuel data retrieval with fallback logic
- `backend/agent/tools/calculate_surcharge.py`: Surcharge calculation formula + capping logic
- `backend/api/chat.py`: SSE stream handler (coordinates graph execution, streams traces)

**Testing:**

- `backend/tests/test_tools.py`: Unit tests for tool implementations
- `backend/tests/test_agents.py`: Agent node tests (mocked tools)
- `backend/tests/test_api.py`: API endpoint tests
- `frontend/__tests__/`: React component tests (if using Jest/Vitest)

**Databases:**

- `data/express.db`: SQLite with tables: rate_table (shipping rates), fuel_prices (optional historical cache)
- `data/checkpoints.db`: LangGraph checkpointer (created at runtime, stores conversation state)

## Naming Conventions

**Files:**

- `*_agent.py`: Agent node implementation (e.g., fuel_agent.py, route_agent.py)
- `*_tool.py`: Tool definition (e.g., fetch_fuel_price_tool.py) or grouped in tools/__init__.py
- `*_prompt.txt`: System prompt for an agent
- `test_*.py`: Unit tests (pytest convention)
- `*.spec.tsx`: React component tests

**Directories:**

- `backend/agent/nodes/`: Plural for multiple nodes
- `backend/agent/tools/`: Plural for tool collection
- `data/raw/`: Raw source data (CSVs)
- `data/scripts/`: Data processing scripts

**Functions/Classes:**

- `fetch_fuel_price()`: Tool function (verb_noun pattern)
- `FuelAgent`: Agent class (PascalCase)
- `agentState`: Type definition (camelCase)
- `BASELINE_DIESEL_PRICE`: Constants (SCREAMING_SNAKE_CASE)

**API Endpoints:**

- `/api/chat`: POST (user message)
- `/api/conversations`: GET (list), POST (create)
- `/api/conversations/:id`: GET (retrieve), DELETE (archive)
- `/api/feedback`: POST (submit score)
- `/api/fuel-prices`: GET (historical data)

## Where to Add New Code

**New Feature (e.g., add handling for "what if" scenarios):**
- Primary code: `backend/agent/nodes/planner.py` (add routing condition) + `backend/agent/prompts/planner_prompt.txt` (instruct planner)
- Tests: `backend/tests/test_agents.py` (mock scenario, verify output)
- API: `backend/api/chat.py` (likely no change, handles message routing)
- Frontend: `frontend/components/ChatInterface.tsx` (render "what if" button or prompt suggestion)

**New Agent Specialist (e.g., add Competitor Pricing Agent):**
- Implementation: Create `backend/agent/nodes/competitor_pricing_agent.py`
- Tools: Create `backend/agent/tools/fetch_competitor_price.py`
- Prompt: Create `backend/agent/prompts/competitor_pricing_prompt.txt`
- Graph: Update `backend/agent/graph.py` (add node, register edge from planner)
- State: Update AgentState TypedDict to include `competitor_pricing_data: dict | None`

**New Tool (e.g., add traffic incident lookup):**
- Implementation: Create `backend/agent/tools/fetch_traffic_incidents.py`
- Tool registration: Import and add to graph's tool_node
- Agent usage: Route Agent calls tool conditionally based on traffic_severity threshold
- Fallback: Implement cached/fallback behavior if external API fails

**Utilities/Helpers:**
- Shared helpers: `backend/utils/` (create if doesn't exist) for helper functions
- Example: `backend/utils/thai_geography.py` (zone mapping helpers), `backend/utils/currency.py` (THB formatting)
- Import pattern: `from backend.utils.thai_geography import zone_from_coordinates`

**Data Pipeline:**
- New fuel source: Create `data/scripts/fetch_[source]_fuel_prices.py`, output to `data/raw/`
- New rate source: Create `data/scripts/generate_[source]_rate_table.py`
- Seeding: Update `data/scripts/seed_database.py` to import new CSV if applicable

**Frontend Component:**
- New UI: Create `frontend/components/[FeatureName].tsx`
- Hooks: Add to `frontend/hooks/` if reusable (e.g., useFuelChart, useConversationHistory)
- Types: Add to `frontend/types/` (e.g., ConversationMessage, ToolTrace)
- Styles: Tailwind CSS inline (no separate CSS file)

## Special Directories

**`data/raw/`:**
- Purpose: Source CSV files (not code, not databases)
- Generated: Yes (by data/scripts/ Python scripts)
- Committed: Yes (important for reproducibility and fallback)
- Files: eppo_diesel_prices.csv, express_rate_table.csv

**`data/scripts/`:**
- Purpose: One-time and periodic data ingestion/seeding
- Generated: No (source files)
- Committed: Yes (needed to refresh data)
- Usage: Run manually or via cron: python data/scripts/fetch_fuel_prices.py && python data/scripts/seed_database.py

**`.planning/codebase/`:**
- Purpose: GSD analysis output (not part of runtime)
- Generated: Yes (by GSD orchestrator)
- Committed: Yes (reference for future development)
- Files: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md

**`backend/tests/`:**
- Purpose: Unit and integration tests (if created)
- Generated: No (developer-written)
- Committed: Yes
- Pattern: pytest for Python, Jest/Vitest for React

**`frontend/__tests__/`:**
- Purpose: React component and integration tests (if created)
- Generated: No (developer-written)
- Committed: Yes
- Pattern: Jest with @testing-library/react

**`backend/logs/` (if created):**
- Purpose: Runtime logs and debug output
- Generated: Yes (at runtime)
- Committed: No (add to .gitignore)

**`data/checkpoints.db` (auto-created):**
- Purpose: LangGraph SQLite checkpointer for conversation memory
- Generated: Yes (first time agent runs)
- Committed: No (conversation-specific, lost on reset is acceptable)
