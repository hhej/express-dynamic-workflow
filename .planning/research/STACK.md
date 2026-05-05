# Technology Stack

**Project:** Express Dynamic Surcharge Orchestrator
**Researched:** 2026-04-04
**Confidence note:** Versions are based on training data (cutoff May 2025). All version numbers are marked with confidence levels. Run `pip index versions <package>` and `npm view <package> version` to verify before pinning.

## Recommended Stack

### Agent Framework (Python Backend)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `langgraph` | >=0.3.x | Multi-agent orchestration graph | Only framework that gives you stateful graphs with conditional routing, Send API for parallel agents, and built-in checkpointing. CrewAI/AutoGen are higher-level abstractions that hide the graph structure you need to show for grading. | MEDIUM |
| `langchain-core` | >=0.3.x | Base abstractions (messages, tools, callbacks) | Required by LangGraph. Provides BaseMessage, ToolMessage, structured output, and callback infrastructure for Langfuse. | MEDIUM |
| `langchain-google-genai` | >=2.0.x | Gemini 2.0 Flash integration via LangChain | The official LangChain integration for Google Generative AI. Provides `ChatGoogleGenerativeAI` with structured output (`with_structured_output`), tool calling, and streaming support. Use this, NOT the raw `google-generativeai` SDK -- LangGraph needs LangChain-compatible chat models. | MEDIUM |
| `langgraph-checkpoint-sqlite` | >=2.0.x | SQLite-backed conversation memory | Official LangGraph checkpointer for SQLite. Stores full agent state per thread_id. Zero-config, file-based -- matches the SQLite-everywhere strategy. Note: the async variant `AsyncSqliteSaver` requires `aiosqlite`. | MEDIUM |

**CRITICAL COMPATIBILITY NOTE:** LangGraph, langchain-core, and langchain-google-genai must be version-aligned. The LangChain ecosystem pins compatible version ranges. Always install them together and let pip resolve:

```bash
pip install langgraph langchain-google-genai langgraph-checkpoint-sqlite
```

Do NOT pin langchain-core separately -- let it be pulled as a dependency.

### LLM Provider

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Google Gemini 2.0 Flash | model: `gemini-2.0-flash` | LLM reasoning for all agents | Free tier (15 RPM), supports tool calling and structured output. Sufficient for a demo with 3-agent orchestration. The model string may have evolved -- verify at https://ai.google.dev/gemini-api/docs/models | MEDIUM |

**Configuration:**
```python
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,  # Deterministic for surcharge calculations
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)
```

**Gotcha:** Gemini free tier has 15 RPM. A single surcharge query invokes the Planner + 2-3 sub-agents = 3-4 LLM calls. At 15 RPM, you can handle ~4 concurrent users max. For demo this is fine, but add a rate limiter to avoid 429 errors.

### Backend Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `fastapi` | >=0.115.x | REST API + SSE streaming | Async-native, auto-generates OpenAPI docs, first-class SSE support via `StreamingResponse`. Perfect for the `/api/chat` SSE endpoint. | MEDIUM |
| `uvicorn` | >=0.32.x | ASGI server | Standard FastAPI production server. Use `uvicorn[standard]` for uvloop + httptools. | MEDIUM |
| `pydantic` | >=2.9.x | Data validation, structured output schemas | FastAPI's native validation layer. Also used for LangGraph agent state and structured tool outputs. Pydantic v2 is required by modern FastAPI. | MEDIUM |
| `python-dotenv` | >=1.0.0 | Environment variable loading | Load `.env` file. Simple, stable, no version risk. | HIGH |
| `sse-starlette` | >=2.0.0 | Server-Sent Events for FastAPI | Cleaner SSE implementation than raw StreamingResponse. Handles connection lifecycle, heartbeats, and reconnection headers. | MEDIUM |
| `httpx` | >=0.27.x | Async HTTP client for EPPO/PTT API calls | Async-native, replaces requests for use in async FastAPI handlers. Use for fuel price fetching and any external API calls. | MEDIUM |

### Frontend

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `next` | 15.x | React meta-framework | App Router, React 19 support, API routes as BFF if needed. Use `create-next-app@latest` with App Router. | MEDIUM |
| `react` | 19.x | UI components | Bundled with Next.js 15. Provides hooks, Suspense, and the new `use` hook for data fetching. | MEDIUM |
| `tailwindcss` | 4.x | Utility-first CSS | Tailwind v4 ships with Next.js 15 by default via `create-next-app`. Simplified config vs v3. If compatibility issues arise, pin to 3.4.x which is battle-tested. | LOW |
| `recharts` | 2.x | Dashboard charts | Declarative React charting. Use for fuel price trends and surcharge history. Simple API, good React integration. v2 is stable and well-documented. | MEDIUM |
| `typescript` | 5.x | Type safety | Included with Next.js scaffold. Non-negotiable for any production-quality frontend. | HIGH |

**Frontend architecture:**
```
app/
  layout.tsx          # Root layout with providers
  page.tsx            # Chat interface (main product)
  dashboard/
    page.tsx          # Recharts dashboard for trends
  components/
    ChatMessage.tsx   # Message bubble with reasoning trace
    ReasoningTrace.tsx # Expandable agent step viewer
    FeedbackButtons.tsx # Thumbs up/down
    SurchargeTable.tsx  # Breakdown table
```

### Database

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| SQLite 3 | stdlib | Rate tables + checkpoints | Zero-config, file-based, built into Python stdlib. Two separate DB files: `express.db` (rate tables) and `checkpoints.db` (LangGraph state). Perfect for local reproducibility -- graders run `python seed_database.py` and it just works. | HIGH |
| `aiosqlite` | >=0.20.0 | Async SQLite for LangGraph checkpointer | Required by `langgraph-checkpoint-sqlite` for async operations in FastAPI's async handlers. | MEDIUM |

### Observability

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `langfuse` | >=2.50.x | LLM tracing + evaluation scoring | Official Python SDK. Integrates with LangChain/LangGraph via callback handler. Tracks LLM calls, tool invocations, latency, and user feedback scores. Free tier is generous for course projects. | MEDIUM |

**Integration pattern:**
```python
from langfuse.callback import CallbackHandler

langfuse_handler = CallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)

# Pass to LangGraph invocation
result = await graph.ainvoke(
    {"messages": [HumanMessage(content=query)]},
    config={"callbacks": [langfuse_handler]},
)
```

**Gotcha:** Langfuse v2 vs v3 had breaking API changes in the callback handler. Verify the import path matches your installed version. The `langfuse.callback.CallbackHandler` import is v2 style; v3 may use `langfuse.langchain.CallbackHandler`.

### External API Clients

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `googlemaps` | >=4.10.0 | Google Maps Directions API | Official Python client. Handles auth, retries, and response parsing. Use `googlemaps.Client(key=...)` then `client.directions(origin, destination)`. | MEDIUM |
| `tavily-python` | >=0.5.x | Web search for fuel news | Official Tavily SDK. Simple `TavilyClient(api_key=...).search(query)`. Integrates with LangChain tools via `TavilySearchResults`. | MEDIUM |

**Tavily as LangChain tool (recommended for LangGraph integration):**
```python
from langchain_community.tools.tavily_search import TavilySearchResults

search_tool = TavilySearchResults(max_results=3)
```

This makes it a proper LangGraph tool that can be bound to agents, rather than a raw API call.

### Data Pipeline

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `pandas` | >=2.2.x | CSV processing for data pipeline | Read EPPO CSV, transform, load into SQLite. Overkill for simple ETL but the team likely knows it from coursework. | MEDIUM |
| `beautifulsoup4` | >=4.12.x | EPPO/PTT web scraping fallback | If EPPO has no clean API, scrape the price table from their website. Use with `httpx` for async fetching. | MEDIUM |

### Dev Dependencies

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `pytest` | >=8.x | Python testing | Test surcharge calculations, tool outputs, agent routing. | HIGH |
| `pytest-asyncio` | >=0.24.x | Async test support | FastAPI and LangGraph are async -- tests need async fixtures. | MEDIUM |
| `ruff` | >=0.8.x | Python linter + formatter | Replaces black + flake8 + isort in a single tool. Fast, opinionated. | MEDIUM |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Agent Framework | LangGraph | CrewAI | CrewAI is higher-level, hides graph structure. LangGraph exposes conditional routing and state management -- exactly what grading rewards. |
| Agent Framework | LangGraph | AutoGen | AutoGen focuses on multi-agent chat, not graph orchestration. Harder to show structured agent architecture. |
| LLM | Gemini 2.0 Flash | GPT-4o-mini | Not free tier. Budget constraint eliminates OpenAI. |
| LLM | Gemini 2.0 Flash | Claude Haiku | Not free tier. Same budget constraint. |
| Backend | FastAPI | Flask | Flask is sync by default. FastAPI's async + SSE + auto-docs are materially better for this use case. |
| Backend | FastAPI | Django | Overkill. No ORM needed (SQLite is simple), no admin panel needed. |
| Frontend | Next.js 15 | Streamlit | Streamlit is fine for prototypes but does not demonstrate frontend engineering skill. Next.js shows proper separation of concerns. |
| Frontend | Next.js 15 | Gradio | Same as Streamlit -- too prototype-y for a graded project. |
| Database | SQLite | PostgreSQL | PostgreSQL requires installation/config. SQLite is zero-config, file-based, and portable. Grading requires easy local setup. |
| Charts | Recharts | Chart.js | Recharts is React-native (declarative components). Chart.js requires imperative canvas manipulation. Recharts fits better in a React app. |
| HTTP Client | httpx | requests | `requests` is synchronous. `httpx` is async-native, critical for FastAPI async handlers. |
| Observability | Langfuse | LangSmith | Langfuse is open-source and has a free cloud tier. LangSmith has limited free usage and is LangChain-specific. |

## Installation

### Backend (Python)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Core agent stack
pip install langgraph langchain-google-genai langgraph-checkpoint-sqlite

# Backend framework
pip install "fastapi[standard]" sse-starlette

# External API clients
pip install googlemaps tavily-python

# Observability
pip install langfuse

# Data pipeline
pip install pandas beautifulsoup4 httpx aiosqlite

# Dev
pip install pytest pytest-asyncio ruff python-dotenv

# Freeze
pip freeze > requirements.txt
```

**IMPORTANT:** Install `langgraph`, `langchain-google-genai`, and `langgraph-checkpoint-sqlite` in a single pip command. This lets pip resolve compatible `langchain-core` versions. Installing them separately risks version conflicts.

### Frontend (Node.js)

```bash
cd app/
npx create-next-app@latest . --typescript --tailwind --app --eslint --src-dir --no-import-alias

# Charts
npm install recharts

# Utility (optional but recommended)
npm install clsx
```

### Environment Setup

```bash
cp .env.example .env
# Fill in: GOOGLE_API_KEY, GOOGLE_MAPS_API_KEY, TAVILY_API_KEY,
#          LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
```

## Version Pinning Strategy

For a 6-week course project, use **minimum version pins** (>=), not exact pins (==). This avoids dependency hell while still being reproducible via `requirements.txt` freeze output.

```
# requirements.txt approach:
# 1. Install with >= constraints
# 2. Run pip freeze > requirements.txt
# 3. Commit the frozen requirements.txt
# This gives you exact reproducibility without manual pin management.
```

For the frontend, `package-lock.json` handles this automatically via npm.

## Key Compatibility Warnings

1. **LangChain ecosystem version alignment:** All `langchain-*` packages must be from the same minor version family. Mixing `langchain-core==0.2.x` with `langchain-google-genai` built for `0.3.x` will cause import errors. Let pip resolve by installing together.

2. **Pydantic v2 is mandatory:** FastAPI >= 0.100 and LangChain >= 0.2 both require Pydantic v2. If you see `pydantic.v1` imports, something is wrong. All your models should use `from pydantic import BaseModel`.

3. **`google-generativeai` vs `langchain-google-genai`:** Do NOT use the raw `google-generativeai` SDK for LLM calls. LangGraph requires LangChain-compatible chat models (`ChatGoogleGenerativeAI`). The raw SDK would bypass tool calling, structured output, and callback infrastructure. Only use `google-generativeai` directly if you need Gemini features not yet in the LangChain wrapper.

4. **Async everywhere in FastAPI:** All endpoint handlers that call LangGraph must be `async def`. The LangGraph checkpointer and graph invocation are async. Mixing sync/async will cause event loop errors. Use `httpx` (not `requests`), `aiosqlite` (not `sqlite3` for async paths).

5. **Next.js App Router vs Pages Router:** Use App Router (default in Next.js 15). The project scaffold expects `app/` directory routing. Do NOT mix Pages Router patterns. Server Components are the default -- use `"use client"` directive only for interactive components (chat input, feedback buttons, charts).

6. **Tailwind v4 vs v3:** If `create-next-app` scaffolds Tailwind v4, the config file format changed from `tailwind.config.js` to CSS-based `@config` directives. If this causes friction, downgrade to Tailwind v3 (`npm install tailwindcss@3`) -- the visual output is identical, just different config format.

7. **SSE from FastAPI to Next.js:** The frontend must use `EventSource` API or `fetch` with `ReadableStream` to consume SSE. Do NOT use WebSockets -- SSE is simpler, unidirectional (server-to-client), and matches the architecture spec. The `EventSource` API handles reconnection automatically.

## Sources

- Package versions: Based on training data (cutoff May 2025). **VERIFY with `pip index versions <package>` and `npm view <package> version` before finalizing.**
- Architecture decisions: Derived from project's `docs/architecture.md` and `.planning/PROJECT.md`
- LangGraph patterns: Based on LangGraph documentation and examples available through early 2025
- Compatibility notes: Based on known breaking changes in the LangChain ecosystem through 2025
