# Phase 3: Graph Assembly & API Layer - Research

**Researched:** 2026-04-25
**Domain:** LangGraph StateGraph assembly + FastAPI async + SSE streaming + AsyncSqliteSaver checkpointer
**Confidence:** HIGH (stack and APIs verified in-repo against installed packages; ambiguous items flagged)

## Summary

Phase 3 assembles a full LangGraph StateGraph wiring a Planner, the Phase 2 Fuel + Route agents, a new Pricing agent, and a Response node, then exposes it through a FastAPI async app with SSE chat streaming, conversation listing/replay, and a historical fuel-prices endpoint. The existing Phase 2 D-11/D-12 narration pattern and `FakeMessagesListChatModel` test seam carry straight over to the three new nodes; the Planner additionally extracts structured inputs (origin, destination, shipping_type, weight_kg) so Route/Pricing nodes remain pre-extraction consumers.

The hard questions here are runtime, not logic: the `AsyncSqliteSaver` lifecycle under FastAPI lifespan, the retry-exhaustion fallback (LangGraph's `RetryPolicy` **does not have a "go to X on exhaustion" hook** — it raises), the streaming contract (`astream_events("v2")` is locked in D-17 and emits lifecycle events that need filtering), and the planner loop budget (LangGraph's default `recursion_limit=25` is already more permissive than our D-04 `PLANNER_MAX_ITERATIONS=6`, but the guard must be enforced inside the Planner, not by the graph).

Two environment-level findings matter for the planner: (1) the `.venv` is Python **3.9.6** (CLAUDE.md says 3.11+ but the real env is 3.9), so pinned dependency versions must be 3.9-compatible; and (2) `fastapi==0.128.8` (latest installable) does NOT yet ship `EventSourceResponse` — we use `sse-starlette==3.3.0` or raw `StreamingResponse` with manual SSE framing. Both are installable on 3.9.

**Primary recommendation:** Build the graph in `backend/agent/graph.py` as a module-level factory (`build_graph(checkpointer)` → `CompiledStateGraph`) compiled inside a FastAPI lifespan against an async-context-managed `AsyncSqliteSaver`. Each node implements the Phase 2 D-11/D-12 narration pattern and wraps its body in a try/except that converts retryable-exhaustion and fatal-input failures into an `errors[]` append plus `next_step="respond"` (since `RetryPolicy` cannot redirect on exhaustion). Stream via `astream_events(version="v2")` filtered on `event == "on_chain_end"` and `name` matching node names, emit `meta → trace* → answer → done` events through `StreamingResponse` with manual SSE framing.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Planner design (ORCH-01):**
- **D-01:** Single Gemini structured-output call. Planner returns a Pydantic schema `PlannerOutput { user_intent, shipping_type?, weight_kg?, origin?, destination?, missing_fields: list[str], next_step, clarification_reason? }`. Same Gemini path as Phase 2 Fuel/Route nodes (raw `model.invoke()` + `json.loads()`) so `FakeMessagesListChatModel` keeps working in tests.
- **D-02:** D-11 fallback applies. On parse failure: retry once with stricter prompt; on second failure, emit deterministic `next_step="clarify"` + `clarification_reason="planner_parse_failed"`. Never raise out of the Planner.
- **D-03:** Planner-loop routing pattern. Graph topology: `START → Planner → conditional_edge(next_step) → {fuel_agent | route_agent | pricing_agent | response} → Planner` (loop until `next_step="respond"`). Cache-aware skipping (D-12) is implemented inside the Planner, not in the edges.
- **D-04:** Max-loop guard. Planner must terminate within 6 iterations per request (1 init + up to 4 specialist calls + 1 respond). Hitting the cap forces `next_step="respond"` with a partial-result message.
- **D-05:** Flat AgentState additions. Add to `backend/agent/state.py` `AgentState`: `origin: Optional[str]`, `destination: Optional[str]`, `user_intent: Optional[str]`, `missing_fields: List[str]`, `clarification_reason: Optional[str]`, `errors: Annotated[List[dict], operator.add]`.
- **D-06:** Clarify-path message generation. Planner sets `next_step="clarify"` + `clarification_reason`. Response Node renders the user-facing message via Gemini with the same D-11 fallback pattern.
- **D-07:** Intent vocabulary (locked). `user_intent` enum: `surcharge_query`, `followup_query`, `clarification`, `out_of_scope`.

**Pricing Agent (ORCH-04):**
- **D-08:** Pricing Agent mirrors the Phase 2 Fuel/Route node pattern: invoke `lookup_rate` then `calculate_surcharge_tool`, narrate result via Gemini with D-11 deterministic fallback, emit a single D-12-shape `reasoning_trace` entry (`agent="pricing_agent"`). `tool` field = compound value `"lookup_rate+calculate_surcharge"`.
- **D-09:** `lookup_rate` ValueError → Planner clarify path. The Pricing Agent does NOT catch `ValueError` from `lookup_rate`.

**Response Node (ORCH-05):**
- **D-10:** Response payload shape: `{ markdown: str, surcharge_result: SurchargeResult.model_dump() | None, capped: bool, status: "ok" | "clarify" | "partial" }`.
- **D-11:** Markdown structure (locked): one-paragraph reasoning summary + 4-row breakdown table (`Base rate`, `Surcharge %`, `Surcharge amount`, `Total`) + italicised footer. When `capped=true`, prepend `> ⚠ Cap/floor applied — review recommended`.

**Conversation memory (ORCH-10):**
- **D-12:** Planner inspects state freshness, decides reuse. Checks `state.fuel_data["fetched_at"]` vs `FUEL_DATA_TTL_SECONDS` (3600); for route, `state.route_data["origin"] == new_origin` and `state.route_data["destination"] == new_destination`.
- **D-13:** `fetched_at` is added to `FuelData` and `RouteData` dump dicts as ISO-8601 UTC string. Pydantic models stay unchanged; timestamp is added at the agent-node serialisation layer (fuel_agent_node and route_agent_node updates `model_dump()` output).
- **D-14:** New config constants in `backend/config.py`: `FUEL_DATA_TTL_SECONDS=3600`, `PLANNER_MAX_ITERATIONS=6`.
- **D-15:** AsyncSqliteSaver checkpointer via `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver` + `aiosqlite` against `data/checkpoints.db`.
- **D-16:** Graph compiled once at FastAPI startup (lifespan event). Single `compiled_graph` stored on `app.state`.

**API contract (API-01..04):**
- **D-17:** SSE event granularity: live trace events + final answer. Use `compiled_graph.astream_events(..., version="v2")` filtered to `"on_chain_end"` per node completion.
- **D-18:** Typed JSON envelope. `data: {"type":"trace"|"answer"|"error"|"done","payload":{...}}\n\n`. `trace.payload` = D-12 trace entry verbatim.
- **D-19:** Thread ID flow. Client may supply `thread_id`; if missing/unknown, server generates UUIDv4 and emits it in the first SSE event as `meta` type `{"type":"meta","payload":{"thread_id": "..."}}`.
- **D-20:** API-04 fuel-prices source: `GET /api/fuel-prices?days=30` reads directly from `data/raw/eppo_diesel_prices.csv` (not SQLite).
- **D-21:** API-02/03 conversation listing/replay. `GET /api/conversations` queries the AsyncSqliteSaver's checkpoint table; `GET /api/conversations/:id` calls `checkpointer.aget(config={"configurable":{"thread_id":id}})`.

**Retry topology (ORCH-08):**
- **D-22:** LangGraph node-level `RetryPolicy(max_attempts=2, backoff_factor=2.0, initial_interval=1.0)` applied to all agent nodes.
- **D-23:** Retryable scope: `httpx.HTTPError`, `httpx.TimeoutException`, `asyncio.TimeoutError`, `google.api_core.exceptions.ResourceExhausted`, `googlemaps.exceptions.HTTPError`. Explicitly NOT retried: `ValueError`, `pydantic.ValidationError`, generic `Exception`.
- **D-24:** Retry-exhausted fallback edge: every node appends to `state.errors[]` and forces `next_step="respond"`. Response Node detects `state.errors` and renders partial-result message with `status: "partial"`.

**Testing strategy (cross-cutting):**
- **D-25:** Graph-level integration tests use `FakeMessagesListChatModel` for ALL Gemini calls. Tools mocked via `pytest-httpx` and `mocker.patch.object`. AsyncSqliteSaver tests use a temp `:memory:` DB.
- **D-26:** API tests use FastAPI's `TestClient` with `httpx.AsyncClient` for SSE assertion: parse `data: ...` lines, assert event sequence.

### Claude's Discretion

- Exact module split for the Planner (single `backend/agent/nodes/planner.py` vs a `planner/` package).
- Format of the Planner system prompt (must produce structured output parseable to `PlannerOutput`).
- Internal layout of FastAPI app (single `backend/api/main.py` with included routers vs split per-endpoint files).
- pandas vs csv-stdlib for `GET /api/fuel-prices` parsing.
- Exact Pydantic field names for `PlannerOutput` (within the schema in D-01).
- Whether Response Node uses Gemini for prose summary or a deterministic Jinja-style template (both acceptable — D-11 markdown structure is locked).

### Deferred Ideas (OUT OF SCOPE)

- Parallel Fuel + Route via LangGraph Send API (ORCH-07) — Phase 5.
- Human-in-the-loop approval gate (ORCH-09) — Phase 5.
- Tavily web search / `search_fuel_news` tool (TOOL-05) — Phase 5. Planner's `next_step="search_context"` route stays unimplemented in Phase 3.
- `POST /api/feedback` (API-05) — Phase 5.
- Langfuse callback handler (OBS-01..03) — Phase 5.
- Token-level streaming over SSE — out of scope; trace-level granularity is the differentiator.
- Conversation deletion / archive endpoints — out of scope for v1.
- Adaptive replan-on-error — deferred.

## Project Constraints (from CLAUDE.md)

Extracted actionable directives (planner MUST verify compliance):

| Directive | Source | Phase 3 impact |
|-----------|--------|----------------|
| Python 3.11+ specified | CLAUDE.md "Runtime" | **ACTUAL venv is 3.9.6** — all pinned deps must be 3.9-compatible (see Environment Availability). Do not require 3.10+ syntax. |
| `from __future__ import annotations` | CONVENTIONS | New files must include this (existing pattern in Phase 1/2). |
| Secrets: Never commit `.env` | CLAUDE.md | New env keys (`FUEL_DATA_TTL_SECONDS`, `PLANNER_MAX_ITERATIONS`) added to `.env.example` only. |
| PEP 8, line length 88, Black | CONVENTIONS | All new Python files. |
| Google-style docstrings | CONVENTIONS | Planner, Pricing, Response nodes + new API modules must document Args/Returns/Raises. |
| Type hints on all public function signatures | CONVENTIONS | Mandatory. |
| TypedDict for state, Pydantic for IO models | CONVENTIONS | AgentState extensions stay TypedDict (D-05); `PlannerOutput` is Pydantic (D-01). |
| `snake_case.py` module files | CONVENTIONS | `planner.py`, `pricing_agent.py`, `response_node.py`, `graph.py`, etc. |
| Custom exceptions in `exceptions.py` at package level | CONVENTIONS | If Phase 3 introduces any, park them in `backend/agent/exceptions.py` (not needed per current plan — ValueError + existing exception types suffice). |
| Use specific exception types (not bare `except:`) | CONVENTIONS | D-23 retry filter + D-24 try/except wrappers comply. |
| Resource-based API endpoints | CONVENTIONS | `/api/chat`, `/api/conversations`, `/api/conversations/:id`, `/api/fuel-prices` — matches D-17..D-21. |
| Pydantic `BaseModel` for all FastAPI request/response bodies | CONVENTIONS | New models go in `backend/api/models.py` or `backend/api/schemas.py`. |
| Include context in error messages with relevant data | CONVENTIONS | Error payloads in SSE `error` events must include `retryable` flag + node context. |
| GSD workflow enforcement: start work through GSD command | CLAUDE.md | Already active (research phase). |
| No Docker/k8s deploy | CLAUDE.md "Out of Scope" | FastAPI runs via Uvicorn locally only. |
| Budget: free-tier APIs only (Gemini Flash, Google Maps, EPPO) | CLAUDE.md | No new paid services in Phase 3. |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **ORCH-01** | Planner detects user intent and routes to specialists via conditional edges | StateGraph conditional edges pattern (see Architecture Patterns §Planner loop); D-01/D-03 Pydantic structured-output + `FakeMessagesListChatModel` test seam inherited from Phase 2 (`backend/agent/nodes/fuel_agent.py::_narrate_with_llm`) |
| **ORCH-04** | Pricing Agent wraps `lookup_rate` + `calculate_surcharge` tools | Tools already exist (`backend/agent/tools/lookup_rate.py`, `calculate_surcharge_tool.py`); mirror the fuel_agent_node/route_agent_node structure |
| **ORCH-05** | Response node formats final answer with breakdown table + reasoning | D-10/D-11 locked payload shape; Gemini narration or deterministic template (Claude's discretion) |
| **ORCH-08** | Agentic retry loop with exponential backoff (max 2 retries per tool) + graceful fallback | LangGraph `RetryPolicy` (verified: `langgraph.types.RetryPolicy`; Added in v0.2.24); D-22 params; custom `retry_on` callable needed (default filter retries bare `Exception` — contrary to D-23). See Pitfall 3. |
| **ORCH-10** | Conversation memory via LangGraph SQLite checkpointer | `AsyncSqliteSaver` from `langgraph-checkpoint-sqlite==2.0.11`; D-12 cache-reuse decision lives in Planner, not in graph edges |
| **API-01** | POST `/api/chat` returns SSE stream of traces + response | `astream_events("v2")` filtered on `on_chain_end`; D-17/D-18 typed JSON envelope; `StreamingResponse(media_type="text/event-stream")` (EventSourceResponse not available on pinned FastAPI 0.128.8 — see Pitfall 5) |
| **API-02** | GET `/api/conversations` lists past threads | Query AsyncSqliteSaver's `checkpoints` table directly (columns: `thread_id, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata`) |
| **API-03** | GET `/api/conversations/:id` returns thread history | `checkpointer.aget(config={"configurable":{"thread_id":id}})` returns the latest state |
| **API-04** | GET `/api/fuel-prices?days=N` returns historical data for charts | Read `data/raw/eppo_diesel_prices.csv` (186 lines, ~6 months daily); pandas or csv stdlib (D-20) |

## Standard Stack

### Core (NEW in Phase 3)

| Library | Pinned Version | Purpose | Why Standard |
|---------|---------------|---------|--------------|
| `fastapi` | `0.128.8` | Async web framework serving SSE + REST | Project tech stack mandate; idiomatic async + Pydantic integration |
| `uvicorn[standard]` | `0.36.1` | ASGI server (dev + prod on free tier) | FastAPI default; `[standard]` bundles `httptools`, `uvloop`, `websockets`, `watchfiles` |
| `langgraph-checkpoint-sqlite` | `==2.0.11` | `AsyncSqliteSaver` for conversation state persistence | Official LangChain checkpointer; 2.0.11 is last release with Py3.9-compatible wheel (3.0+ requires Py3.10+ — see Pitfall 1) |
| `aiosqlite` | `==0.22.1` | Async SQLite driver used by `AsyncSqliteSaver` | Required dep; pure Python, no extra build |
| `python-multipart` | `0.0.20` | FastAPI form parsing (only if future endpoints need form data) | Optional; include if `/api/feedback` arrives in Phase 5 |

### Supporting (already installed, reused)

| Library | Installed Version | Purpose | When to Use |
|---------|------------------|---------|-------------|
| `langgraph` | `0.6.11` | `StateGraph`, `START`, `END`, `RetryPolicy`, `add_messages` | Graph assembly (all nodes) |
| `langchain-core` | `0.3.84` | `BaseMessage`, `HumanMessage`, `AIMessage`, `SystemMessage` | Planner prompt assembly, future message-history handling |
| `langchain-google-genai` | `2.1.12` | `ChatGoogleGenerativeAI` via `get_chat_model()` | Planner + Pricing + Response narration |
| `pydantic` | `2.12.5` | `BaseModel` for `PlannerOutput`, API request/response schemas | D-01, API-01/02/03/04 |
| `pandas` | `2.3.3` | CSV reading for `/api/fuel-prices` (alternative) | D-20 — use stdlib `csv` or `pandas`; pandas already pinned |
| `httpx` | `0.28.1` | `TestClient` + async testing + retryable exception class | D-23, D-26 |
| `pytest-httpx` | `0.35.0` | HTTP mocking in API tests (if API calls external services) | Reused test seam |
| `pytest-mock` | `3.15.1` | `mocker.patch.object` for tool/LLM injection | Reused test seam |
| `pytest` | `8.4.2` | Test runner | — |

### Alternative: `sse-starlette`

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `StreamingResponse` with manual SSE framing | `sse-starlette==3.3.0` (`EventSourceResponse`) | Handles keep-alive pings, `X-Accel-Buffering`, `Cache-Control` automatically. Extra dep. Either works; raw `StreamingResponse` is lighter and the streaming layer is already simple. **Recommendation: raw StreamingResponse** — demo context, no proxy layer. |

**Installation:**

```bash
pip install \
  fastapi==0.128.8 \
  "uvicorn[standard]==0.36.1" \
  langgraph-checkpoint-sqlite==2.0.11 \
  aiosqlite==0.22.1
```

Append these five lines to `requirements.txt` (Phase 2 additions section).

**Version verification (executed 2026-04-25):**

| Package | Latest on PyPI | Pinned for Phase 3 | Verification |
|---------|----------------|-------------------|--------------|
| `fastapi` | `0.128.8` | `0.128.8` | `pip index versions fastapi` (latest installable with Python 3.9) |
| `uvicorn` | `0.39.0` | `0.36.1` | Latest verified compatible with fastapi 0.128.8; `uvicorn[standard]` pins pulls httptools + uvloop |
| `langgraph-checkpoint-sqlite` | `3.0.3` (requires Py3.10+) | `2.0.11` | **Py 3.9 compat mandate — 3.0+ blocks install on current venv.** Confirmed by `pip download langgraph-checkpoint-sqlite` which picks 2.0.11 for the 3.9 interpreter. Download + manual import verified at `/tmp/lgchk-test-install/langgraph/checkpoint/sqlite/aio.py`. |
| `aiosqlite` | `0.22.1` | `0.22.1` | Universal wheel, no Py version issue |
| `sse-starlette` | `3.3.0` | (optional; not pinned) | PyPI Requires-Python says >=3.10 but pip's `download` picks 3.3.0 on Py3.9 — the wheel itself is tagged `py3-none-any`. Pass. |

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── agent/
│   ├── graph.py                    # NEW: build_graph(checkpointer) factory, StateGraph assembly (D-15..D-22 topology)
│   ├── state.py                    # EXTEND: add D-05 fields (origin, destination, user_intent, missing_fields, clarification_reason, errors)
│   ├── llm.py                      # UNCHANGED: get_chat_model() factory
│   ├── prompts/
│   │   ├── planner.py              # NEW: Planner SYSTEM_PROMPT (D-01 schema + routing instructions)
│   │   ├── pricing_agent.py        # NEW: Pricing SYSTEM_PROMPT (narration)
│   │   └── response_node.py        # NEW: Response SYSTEM_PROMPT (markdown structure narration, only if Gemini path chosen)
│   ├── nodes/
│   │   ├── planner.py              # NEW: planner_node() — reads state, emits next_step + extracted fields
│   │   ├── pricing_agent.py        # NEW: pricing_agent_node() — lookup_rate + calculate_surcharge_tool + narrate
│   │   ├── response_node.py        # NEW: response_node() — renders D-10 payload
│   │   ├── fuel_agent.py           # EXTEND: add fetched_at (D-13) in model_dump override
│   │   └── route_agent.py          # EXTEND: add fetched_at (D-13) in model_dump override
│   ├── tools/                      # UNCHANGED (lookup_rate, calculate_surcharge_tool, fetch_fuel_price, calculate_route, _cache, models)
│   └── exceptions.py               # NEW (optional, only if D-24 wrapper benefits from named exception type)
├── api/
│   ├── __init__.py                 # NEW
│   ├── main.py                     # NEW: FastAPI app, lifespan, router registration
│   ├── models.py                   # NEW: ChatRequest, MessageResponse, ConversationSummary, FuelPricePoint, etc.
│   ├── sse.py                      # NEW (optional): helper to format SSE events (data: json\n\n)
│   └── routes/
│       ├── __init__.py
│       ├── chat.py                 # NEW: POST /api/chat (SSE)
│       ├── conversations.py        # NEW: GET /api/conversations, GET /api/conversations/:id
│       └── fuel_prices.py          # NEW: GET /api/fuel-prices
├── config.py                       # EXTEND: add FUEL_DATA_TTL_SECONDS, PLANNER_MAX_ITERATIONS
└── tests/
    ├── conftest.py                 # EXTEND: add in-memory checkpointer fixture
    ├── test_planner.py             # NEW
    ├── test_pricing_agent.py       # NEW
    ├── test_response_node.py       # NEW
    ├── test_graph.py               # NEW (integration: full planner-loop scenarios)
    ├── test_api_chat.py            # NEW
    ├── test_api_conversations.py   # NEW
    └── test_api_fuel_prices.py     # NEW
```

### Pattern 1: Node body with error-sink wrapper (D-22 + D-24)

**What:** Every agent node wraps its business logic in try/except to convert both retry-exhaustion (after LangGraph's RetryPolicy raises) and non-retryable failures into state.errors + forced `next_step="respond"`.

**When to use:** All four new nodes (Planner has its own D-02 internal retry; apply to Pricing, Response explicitly; Fuel/Route get it via the same D-24 pattern if they raise after exhaustion).

**Why not rely on RetryPolicy alone:** LangGraph's `RetryPolicy` has no "on-exhaustion goto X" hook. When max_attempts is hit, the node raises and the graph aborts unless the exception is caught outside the graph (at the API layer) — which would lose D-12 trace context and break live SSE trace streaming.

**Example:**

```python
# Source: adapted from Phase 2 fuel_agent_node + the LangChain forum pattern
#   https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574
from datetime import datetime, timezone

def pricing_agent_node(state: dict) -> dict:
    try:
        rate = lookup_rate(
            shipping_type=state["shipping_type"],
            zone=state["route_data"]["zone"],
            weight_kg=state["weight_kg"],
        )
        surcharge_input = SurchargeInput(
            base_rate=rate.base_rate,
            current_diesel_price=state["fuel_data"]["price"],
            shipping_type=state["shipping_type"],
            traffic_severity=state["route_data"]["traffic_severity"],
        )
        surcharge = calculate_surcharge_tool.invoke(
            surcharge_input.model_dump()
        )
        reasoning = _narrate_with_llm(rate, surcharge, state)  # D-11 fallback inside
        prior = len(state.get("reasoning_trace") or [])
        return {
            "surcharge_result": surcharge.model_dump(),
            "reasoning_trace": [{
                "step": prior + 1,
                "agent": "pricing_agent",
                "tool": "lookup_rate+calculate_surcharge",  # D-08 compound value
                "tool_input": surcharge_input.model_dump(),
                "tool_output": surcharge.model_dump(),
                "reasoning": reasoning,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": "ok",
            }],
        }
    except ValueError as exc:
        # D-09: bubble to Planner (do NOT catch here)
        raise
    except Exception as exc:
        # D-24 retry-exhausted sink (reached only after RetryPolicy gave up)
        return {
            "errors": [{
                "node": "pricing_agent",
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }],
            "next_step": "respond",
        }
```

Note: For `ValueError` specifically (D-09), the Pricing Agent must let it raise so Planner (or the graph driver) can classify it as clarify-path. The above re-raises explicitly.

### Pattern 2: Custom `retry_on` callable for D-23 compliance

**What:** LangGraph's default `retry_on` callable (`langgraph.types.default_retry_on`) excludes `ValueError`, `TypeError`, etc. — good — but **retries the generic `Exception` fallthrough** (returns `True`). D-23 says "NOT retried: ... generic `Exception`." So we must supply our own `retry_on`.

**When to use:** Every `RetryPolicy(...)` in `graph.py`.

**Example:**

```python
# Source: backend/.venv/lib/python3.9/site-packages/langgraph/types.py::default_retry_on (inspected 2026-04-25)
import asyncio
from typing import Sequence, Type
import httpx
from google.api_core.exceptions import ResourceExhausted
from googlemaps.exceptions import HTTPError as GMapsHTTPError

_RETRYABLE: Sequence[Type[BaseException]] = (
    httpx.HTTPError,
    httpx.TimeoutException,
    asyncio.TimeoutError,
    ResourceExhausted,
    GMapsHTTPError,
)

def phase3_retry_on(exc: BaseException) -> bool:
    """D-23 compliant: ONLY the enumerated transient-network exceptions retry."""
    return isinstance(exc, _RETRYABLE)

# Usage in graph.py:
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy
from backend.agent.state import AgentState

def build_graph(checkpointer):
    retry = RetryPolicy(
        max_attempts=2,
        backoff_factor=2.0,
        initial_interval=1.0,
        jitter=True,
        retry_on=phase3_retry_on,
    )
    g = StateGraph(AgentState)
    g.add_node("planner", planner_node, retry_policy=retry)
    g.add_node("fuel_agent", fuel_agent_node, retry_policy=retry)
    g.add_node("route_agent", route_agent_node, retry_policy=retry)
    g.add_node("pricing_agent", pricing_agent_node, retry_policy=retry)
    g.add_node("response", response_node, retry_policy=retry)

    g.set_entry_point("planner")
    g.add_conditional_edges(
        "planner",
        lambda s: s["next_step"],
        {
            "fetch_fuel": "fuel_agent",
            "fetch_route": "route_agent",
            "calculate_price": "pricing_agent",
            "clarify": "response",
            "respond": "response",
            "search_context": "response",  # Phase-5 stub: route to Response with a "not-yet-supported" message
        },
    )
    # D-03 loop: specialists return to Planner
    for node in ("fuel_agent", "route_agent", "pricing_agent"):
        g.add_edge(node, "planner")
    g.add_edge("response", END)

    return g.compile(checkpointer=checkpointer)
```

### Pattern 3: FastAPI lifespan with AsyncSqliteSaver (D-15 + D-16)

**What:** Open the aiosqlite connection in a lifespan context manager, wrap it with `AsyncSqliteSaver(conn)`, build + compile the graph once, store on `app.state`.

**When to use:** `backend/api/main.py` only.

**Example:**

```python
# Sources:
# - https://fastapi.tiangolo.com/advanced/events/
# - https://reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver
# - Installed AsyncSqliteSaver signature (inspected): AsyncSqliteSaver(conn: aiosqlite.Connection, *, serde=None)
from contextlib import asynccontextmanager
from pathlib import Path
import aiosqlite
from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from backend.agent.graph import build_graph
from backend.config import CHECKPOINT_PATH

@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(CHECKPOINT_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(CHECKPOINT_PATH)
    try:
        checkpointer = AsyncSqliteSaver(conn)
        await checkpointer.setup()  # creates tables if absent
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer)
        yield
    finally:
        await conn.close()

app = FastAPI(title="Express Dynamic Surcharge Orchestrator", lifespan=lifespan)
# ... include routers ...
```

**Note:** `from_conn_string()` is an async context manager. Using it inside a lifespan requires nested `async with` which is cleaner via `AsyncExitStack`. The direct `aiosqlite.connect` → `AsyncSqliteSaver(conn)` path shown above is simpler and matches the signature `(conn: aiosqlite.Connection, *, serde=None)` verified by `inspect.signature(AsyncSqliteSaver)`.

### Pattern 4: SSE streaming via `astream_events("v2")` (D-17 + D-18)

**What:** Filter `astream_events` output to lifecycle events that correspond to node completion, map each to a D-18 SSE envelope, yield through `StreamingResponse`.

**When to use:** `backend/api/routes/chat.py` POST `/api/chat`.

**Example:**

```python
# Sources:
# - https://docs.langchain.com/oss/python/langgraph/streaming (astream_events v2 shape)
# - https://dev.to/kasi_viswanath/streaming-ai-agent-with-fastapi-langgraph-2025-26-guide-1nkn
import json
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

NODE_NAMES = {"planner", "fuel_agent", "route_agent", "pricing_agent", "response"}

def _sse(event_type: str, payload: dict) -> bytes:
    """D-18 envelope. Always JSON-encode the full body as one 'data:' line."""
    body = {"type": event_type, "payload": payload}
    return f"data: {json.dumps(body, ensure_ascii=False)}\n\n".encode("utf-8")

@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    graph = request.app.state.graph
    thread_id = req.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    async def stream():
        # D-19 meta first
        yield _sse("meta", {"thread_id": thread_id})
        try:
            initial_state = {"messages": [{"role": "user", "content": req.message}]}
            async for event in graph.astream_events(
                initial_state, config=config, version="v2"
            ):
                ev = event["event"]
                name = event.get("name", "")
                if ev == "on_chain_end" and name in NODE_NAMES:
                    output = event["data"].get("output") or {}
                    # Specialists emit partial state with 'reasoning_trace' list — stream the trace
                    trace_entries = output.get("reasoning_trace") or []
                    for entry in trace_entries:
                        yield _sse("trace", entry)
                    # Response node emits final answer payload (D-10)
                    if name == "response" and "final_payload" in output:
                        yield _sse("answer", output["final_payload"])
        except Exception as exc:
            yield _sse("error", {"message": str(exc), "retryable": False})
        finally:
            yield _sse("done", {})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx / Vercel passthrough
            "Connection": "keep-alive",
        },
    )
```

**Important:** `event["data"]["output"]` for `on_chain_end` on a LangGraph node is the **partial state dict returned by the node**, not the cumulative state. Phase 2's `fuel_agent_node` returns `{"fuel_data": ..., "reasoning_trace": [entry]}` — so `output["reasoning_trace"]` contains exactly the ONE new entry. This matches D-18's "trace.payload = D-12 trace entry verbatim" contract cleanly.

**For the Response Node to emit an `answer` event via `on_chain_end`,** the node must return its D-10 payload under a recognisable state key (suggested: `final_payload`) so the stream filter can pick it up. The alternative is post-processing the final state after `astream_events` exhausts, but that splits the SSE emission logic across two paths.

### Pattern 5: Conversation listing via checkpoint SQL query (D-21)

**What:** The AsyncSqliteSaver's `checkpoints` table schema is `(thread_id, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)` with auxiliary `writes` table. Directly query `thread_id` + `MAX(checkpoint_id)` to enumerate conversations, then use `checkpointer.aget()` for individual retrieval.

**Example:**

```python
# Source: https://deepwiki.com/langchain-ai/langgraph/4.2-checkpoint-implementations
#         (schema confirmed by running the wheel-installed aio.py source locally)
@router.get("/api/conversations")
async def list_conversations(request: Request, limit: int = 50):
    checkpointer = request.app.state.checkpointer
    async with checkpointer.conn.execute(
        """
        SELECT thread_id, MAX(checkpoint_id) AS latest
        FROM checkpoints
        GROUP BY thread_id
        ORDER BY latest DESC
        LIMIT ?
        """,
        (limit,),
    ) as cur:
        rows = await cur.fetchall()
    summaries = []
    for thread_id, latest in rows:
        state = await checkpointer.aget({"configurable": {"thread_id": thread_id}})
        messages = state.get("channel_values", {}).get("messages", []) if state else []
        preview = messages[0].get("content", "")[:100] if messages else ""
        summaries.append({
            "thread_id": thread_id,
            "last_updated": latest,  # checkpoint_id is a timestamp-ordered ULID
            "first_message_preview": preview,
        })
    return summaries
```

The `aget()` return value is the **CheckpointTuple**, not the AgentState directly — state lives under `.checkpoint["channel_values"]` or `.values` depending on API surface. The planner should verify this in the installed 2.0.11 source when writing the route.

### Anti-Patterns to Avoid

- **Compiling the graph per request:** breaks the AsyncSqliteSaver async context, adds ~200ms overhead per chat. D-16 mandates single compile at startup.
- **Using `@app.on_event("startup")`:** deprecated in favour of lifespan. Use lifespan only.
- **Relying on LangGraph default `retry_on`:** retries generic `Exception` (contrary to D-23). Always pass a custom callable.
- **Catching ValueError inside Pricing Agent:** violates D-09. Let it bubble; Planner's clarify path handles it on the next loop.
- **Treating `astream_events` `on_chain_end` output as full state:** it is the partial state returned by the node. If the Planner or Response needs cumulative state for stream decisions, use `astream` with `stream_mode="values"` instead — but that conflicts with D-17's lock.
- **Using `pydantic.Field(..., default_factory=list)` for the new `errors` reducer field:** TypedDict + `operator.add` reducer lives on `state.py`, not a Pydantic model. See Phase 2 D-05 for the pattern; Phase 3 reuses it for `errors`.
- **Sending one SSE event per token:** out of scope; only node-completion granularity per D-17.
- **Forgetting `X-Accel-Buffering: no`:** nginx and similar proxies buffer 8KB by default, breaking live trace streaming. Even on localhost this surfaces during `curl` testing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Conversation state persistence | Custom SQLite checkpoint manager | `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver` | Handles versioning, parent-child checkpoint chains, pending writes, and the `channel_values` merge — recreating this is a 500-line project. |
| Node retry + backoff | `while retries < 2: try: ...` loops | `langgraph.types.RetryPolicy` with custom `retry_on` | Built-in exponential + jitter; integrates with LangGraph tracing. |
| SSE framing | Manual byte concatenation with escape handling | JSON.dumps + format string `f"data: {body}\n\n"` (or `sse-starlette.EventSourceResponse`) | JSON escapes all special chars; the SSE protocol needs only `data:` prefix + double-newline separator. Do not invent binary framing. |
| UUID generation for thread_id | Custom random string | `uuid.uuid4()` | Stdlib; guaranteed unique, opaque (D-19). |
| Graph topology validation | Ad-hoc edge cycle checks | LangGraph's built-in validation at `.compile()` time + `recursion_limit` (default 25) | LangGraph raises `GraphRecursionError` if the planner loop doesn't terminate. D-04's 6-iteration guard is a BUSINESS-level cap inside the Planner; LangGraph's 25-step cap is the SAFETY net. |
| CSV parsing for `/api/fuel-prices` | Manual `open()` + `split(",")` | `csv.DictReader` (stdlib) or `pandas.read_csv` (already installed) | Handles quoted fields, trailing newlines, UTF-8 BOM. For 186 rows either is instant (< 5ms). |
| FastAPI request body parsing | Manual JSON parse in handler | Pydantic `BaseModel` as the type hint on the route arg | Automatic 422 on validation error; free OpenAPI docs. |

**Key insight:** The plumbing in this phase is where custom solutions accrete unnecessarily. Every line of retry/backoff/SSE framing written by hand is a line that drifts from upstream best practice. Delegate to the libraries; spend budget on the Planner prompt design and the D-12 cache-reuse logic instead.

## Common Pitfalls

### Pitfall 1: `langgraph-checkpoint-sqlite` version skew on Python 3.9

**What goes wrong:** `pip install langgraph-checkpoint-sqlite` without a version pin will select 3.0.3 (latest) on a system where 3.0+ is available, then fail to import because 3.0.3 requires Py3.10+ and the current `.venv` is 3.9.6.

**Why it happens:** PyPI's Requires-Python metadata only **discourages** pip; doesn't always block resolution in older pip. The project's `.venv` predates Phase 1's CLAUDE.md "3.11+" statement.

**How to avoid:** Pin to `langgraph-checkpoint-sqlite==2.0.11` in `requirements.txt`. Verified installable on 3.9 by `pip download`.

**Warning signs:** `ImportError: No module named 'langgraph.checkpoint.sqlite.aio'` at graph compile time; or `SyntaxError` on `match` statements in 3.0+ source files.

### Pitfall 2: `RetryPolicy` raises on exhaustion — no built-in fallback edge

**What goes wrong:** Node's `httpx.HTTPError` retry succeeds twice, fails third time. `RetryPolicy` raises out of the node. The graph run aborts. The SSE stream emits an `error` event but never the `answer` payload — contrary to D-24 which wants a `partial` status payload.

**Why it happens:** LangGraph's `RetryPolicy` has no "go-to on exhaustion" hook — explicitly confirmed in the LangChain forum discussion and by reading the 0.6.11 source.

**How to avoid:** Wrap each node body in try/except (see Pattern 1). Catch `Exception` (after letting `ValueError` through per D-09) and write to `state.errors` + set `next_step="respond"`. The try/except IS the fallback edge.

**Warning signs:** Graph raises `ExceptionGroup` or a bare `httpx.HTTPError` to the FastAPI handler; SSE stream closes without an `answer` or `done` event.

### Pitfall 3: Default `retry_on` contradicts D-23

**What goes wrong:** Planner writes `RetryPolicy(max_attempts=2, ...)` without `retry_on`, expecting defaults to be sane. A `RuntimeError` from a bad Gemini narration triggers two unnecessary retries — burning free-tier budget (15 RPM) — before the D-11 fallback would have caught it on first attempt.

**Why it happens:** `default_retry_on` excludes `ValueError`/`TypeError`/... but has a final `return True` for all other `Exception` subclasses. Read the source before relying on defaults.

**How to avoid:** Always pass a project-specific `retry_on=phase3_retry_on` (Pattern 2). Keep the allowlist narrow: only the five classes in D-23.

**Warning signs:** Test latency creeps up (retries on mocked failures); Gemini free-tier quota exhausted unexpectedly during demo.

### Pitfall 4: Planner loop doesn't terminate (D-04 breached)

**What goes wrong:** Planner keeps emitting `next_step="fetch_fuel"` because D-12's freshness check has a bug (e.g., comparing epoch seconds to ISO strings). Graph hits LangGraph's default `recursion_limit=25` and raises `GraphRecursionError`.

**Why it happens:** Two independent caps (business cap D-04=6 vs LangGraph safety cap=25) and the easier one is invisible. Also: `fetched_at` typo between writer (`route_agent_node`) and reader (Planner).

**How to avoid:**
1. Planner explicitly counts loop iterations: maintain `state["_planner_loop_count"]` (transient) or infer from `len(reasoning_trace)`. After 6 iterations, force `next_step="respond"`.
2. Write an integration test (D-25) that simulates a Planner that always returns `fetch_fuel` and asserts the graph emits a `respond` within 6 iterations — not 25.
3. Set graph recursion_limit explicitly via `.with_config({"recursion_limit": 12})` at compile time as a defensive belt (still above the business limit, well below LangGraph default).

**Warning signs:** `GraphRecursionError` in tests; chat stream hangs for 60+ seconds before emitting error event; Gemini quota exhausted mid-demo.

### Pitfall 5: `EventSourceResponse` not available in pinned FastAPI

**What goes wrong:** Planner reads newer FastAPI docs that recommend `EventSourceResponse`, writes a handler with `response_class=EventSourceResponse`, installs `fastapi==0.128.8`, and gets `ImportError: cannot import name 'EventSourceResponse' from 'fastapi.sse'`.

**Why it happens:** `EventSourceResponse` was added in FastAPI **0.135.0** (released after the 0.128.8 mid-April 2026 snapshot). Latest installable version still doesn't have it.

**How to avoid:** Use raw `StreamingResponse(..., media_type="text/event-stream")` with manual `data: ... \n\n` framing. Add the `Cache-Control: no-cache` + `X-Accel-Buffering: no` headers manually (Pattern 4). If desired, pull in `sse-starlette==3.3.0` for automatic keep-alive — both work on Py 3.9.

**Warning signs:** Import errors on FastAPI app startup; proxy (nginx, Vercel) buffers the stream and the frontend sees all events in one burst at the end.

### Pitfall 6: `aget()` on AsyncSqliteSaver returns CheckpointTuple, not state

**What goes wrong:** `GET /api/conversations/:id` calls `await checkpointer.aget(config)` and tries to index the result as `state["messages"]` — fails because the object is a `CheckpointTuple` with nested structure.

**Why it happens:** LangGraph's checkpoint API exposes checkpoint metadata around the state; raw state lives at `.checkpoint["channel_values"]` or `.values` depending on the method called. Planner often assumes a flat return shape.

**How to avoid:**
- Call `aget_tuple(config)` and read `tuple.checkpoint["channel_values"]["messages"]` — or
- Call `aget(config)` which returns the checkpoint dict (not a Tuple) — verify in 2.0.11 source when writing the route.
- Consider using `compiled_graph.aget_state(config)` instead, which returns a `StateSnapshot` with a `.values` dict exposing AgentState directly.

**Warning signs:** `TypeError: 'CheckpointTuple' object is not subscriptable`; `AttributeError: 'CheckpointTuple' object has no attribute 'messages'`.

### Pitfall 7: Planner's `origin`/`destination` case and normalization must match Phase 2

**What goes wrong:** Planner extracts `"origin": "bangkok"` from user message, Route Agent calls `calculate_route("bangkok", ...)`, Google Maps geocode returns a result whose province name Phase 2 normalises to `central-1` — but cache keys are case-sensitive, so "Bangkok" (title case) and "bangkok" (lower case) miss each other.

**Why it happens:** The Phase 2 route cache keys on the exact input strings (`TTLCache` is key-sensitive). If the Planner sometimes title-cases and sometimes lowercases, the D-12 cache-reuse check breaks.

**How to avoid:** Planner normalises origin/destination to the exact string form it will pass to Route Agent (suggest: title-case city names) before writing to state. Document this normalization rule in the Planner prompt; add a test (D-25).

**Warning signs:** Follow-up question ("What about Retail Fast?") triggers a fresh `calculate_route` call even though same route — breaks the cache-reuse demo value prop.

### Pitfall 8: Message format drift between LangGraph add_messages and the existing `messages: List[dict]`

**What goes wrong:** Current AgentState has `messages: List[dict]` (Phase 1 D-11). Some LangGraph tutorials use `messages: Annotated[list, add_messages]` with `BaseMessage` subclasses. If the Planner passes raw dicts to Gemini's `ChatGoogleGenerativeAI.invoke()` expecting BaseMessage objects, parsing fails.

**Why it happens:** Phase 1 chose `List[dict]` for simplicity (ORCH-06). Phase 3 adds conversation flow, which is where the `add_messages` reducer starts helping.

**How to avoid:**
- Stay with `List[dict]` in AgentState (non-breaking with Phase 1/2 tests).
- Planner converts dicts to `HumanMessage`/`AIMessage` at call-site only (same as Phase 2 fuel_agent does with `SystemMessage(content=...)` + `HumanMessage(content=...)`).
- Do NOT switch the whole field to `Annotated[list, add_messages]` in Phase 3 — that is a state-schema migration that risks breaking existing tests.

**Warning signs:** `pydantic.ValidationError: messages[0] is not a BaseMessage`; Gemini call receives wrong payload shape.

### Pitfall 9: AsyncSqliteSaver.setup() not called before first request

**What goes wrong:** Fresh `data/checkpoints.db` file exists, but the `checkpoints` and `writes` tables aren't created. First `POST /api/chat` fails with `sqlite3.OperationalError: no such table: checkpoints`.

**Why it happens:** `AsyncSqliteSaver(conn)` is lazy; the first `aput`/`aget` creates tables. But if the first op is `astream_events` with a NEW thread_id, some paths race the table creation.

**How to avoid:** Call `await checkpointer.setup()` inside the lifespan after instantiation (Pattern 3). This method is idempotent and explicit.

**Warning signs:** First-request-after-fresh-deploy failure with `no such table`; tests pass (in-memory recreates tables) but dev fails.

## Runtime State Inventory

Phase 3 is not a rename/refactor phase — this section is informational only. The small persistence touchpoints are documented so the planner can sequence them correctly.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | **`data/checkpoints.db`** — auto-created by `AsyncSqliteSaver.setup()`. Stores conversation state per thread. No pre-existing data to migrate (Phase 2 did not write to it). | Ensure `data/` directory exists at startup; `.gitignore` already excludes `*.db` files. |
| Live service config | None. Free-tier API keys (Gemini, Google Maps) are already in `.env` from Phase 2. | None. |
| OS-registered state | None — no cron, launchd, or systemd units touched by this phase. | None. |
| Secrets / env vars | **New env vars** (D-14): `FUEL_DATA_TTL_SECONDS=3600`, `PLANNER_MAX_ITERATIONS=6`. Also implicit: `GOOGLE_API_KEY` (already defined Phase 2), `GOOGLE_MAPS_API_KEY` (already), `CHECKPOINT_PATH` (already defaulted to `data/checkpoints.db`). | Add the two new keys to `.env.example` with defaults. |
| Build artifacts / installed packages | **New deps**: `fastapi`, `uvicorn[standard]`, `langgraph-checkpoint-sqlite==2.0.11`, `aiosqlite==0.22.1`. Venv cache will need refresh after `requirements.txt` update. | Run `pip install -r requirements.txt` after the first task updates the file; document in plan-01's setup task. |

## Common Pitfalls (cont'd — already covered above in Common Pitfalls section)

## Code Examples

### Planner node skeleton (D-01 + D-02 + D-12 + D-04)

```python
# Source: pattern derived from backend/agent/nodes/fuel_agent.py (Phase 2) +
#         D-01..D-12 decisions. Uses raw invoke + json.loads to preserve the
#         FakeMessagesListChatModel test seam.
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from backend.agent.llm import get_chat_model
from backend.agent.prompts.planner import SYSTEM_PROMPT
from backend.config import FUEL_DATA_TTL_SECONDS, PLANNER_MAX_ITERATIONS

logger = logging.getLogger(__name__)


class PlannerOutput(BaseModel):
    user_intent: Literal[
        "surcharge_query", "followup_query", "clarification", "out_of_scope"
    ]
    shipping_type: Optional[str] = None
    weight_kg: Optional[float] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    next_step: Literal[
        "fetch_fuel", "fetch_route", "calculate_price",
        "clarify", "respond", "search_context"
    ]
    clarification_reason: Optional[str] = None


def _fuel_fresh(state: dict) -> bool:
    fd = state.get("fuel_data")
    if not fd or "fetched_at" not in fd:
        return False
    fetched = datetime.fromisoformat(fd["fetched_at"].replace("Z", "+00:00"))
    age_s = (datetime.now(timezone.utc) - fetched).total_seconds()
    return age_s < FUEL_DATA_TTL_SECONDS


def _route_matches(state: dict, origin: Optional[str], destination: Optional[str]) -> bool:
    rd = state.get("route_data")
    if not rd or not origin or not destination:
        return False
    return rd.get("origin") == origin and rd.get("destination") == destination


def _loop_budget_exhausted(state: dict) -> bool:
    # Rough proxy: reasoning_trace length ≈ specialist invocations
    # D-04 guard: plan for planner + ≤4 specialists + respond = ≤6
    return len(state.get("reasoning_trace") or []) >= PLANNER_MAX_ITERATIONS - 1


def planner_node(state: dict) -> dict:
    if _loop_budget_exhausted(state):
        return {
            "next_step": "respond",
            "clarification_reason": "planner_loop_budget_exhausted",
        }

    messages = state.get("messages") or []
    last_user = next(
        (m for m in reversed(messages) if m.get("role") == "user"), None
    )
    if not last_user:
        return {"next_step": "clarify", "clarification_reason": "no_user_message"}

    # Gemini call with D-02 one-retry fallback
    parsed: Optional[PlannerOutput] = None
    for attempt in (1, 2):
        try:
            model = get_chat_model()
            response = model.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=last_user["content"]),
            ])
            content = getattr(response, "content", response)
            if not isinstance(content, str):
                content = str(content)
            # Strip markdown fences (same as fuel_agent Phase 2)
            text = content.strip()
            if text.startswith("```"):
                lines = text.splitlines()[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            parsed = PlannerOutput.model_validate(json.loads(text))
            break
        except (Exception, ValidationError) as exc:
            logger.warning("planner parse attempt %d failed: %s", attempt, exc)
            if attempt == 2:
                return {
                    "next_step": "clarify",
                    "clarification_reason": "planner_parse_failed",
                }

    # D-12 cache-aware override
    next_step = parsed.next_step
    if next_step == "fetch_fuel" and _fuel_fresh(state):
        # Reuse cached fuel — advance to next logical step
        if _route_matches(state, parsed.origin, parsed.destination):
            next_step = "calculate_price"
        else:
            next_step = "fetch_route"
    elif next_step == "fetch_route" and _route_matches(state, parsed.origin, parsed.destination):
        next_step = "calculate_price" if _fuel_fresh(state) else "fetch_fuel"

    prior = len(state.get("reasoning_trace") or [])
    return {
        "user_intent": parsed.user_intent,
        "shipping_type": parsed.shipping_type or state.get("shipping_type"),
        "weight_kg": parsed.weight_kg if parsed.weight_kg is not None else state.get("weight_kg"),
        "origin": parsed.origin or state.get("origin"),
        "destination": parsed.destination or state.get("destination"),
        "missing_fields": parsed.missing_fields,
        "clarification_reason": parsed.clarification_reason,
        "next_step": next_step,
        "reasoning_trace": [{
            "step": prior + 1,
            "agent": "planner",
            "tool": None,
            "tool_input": {},
            "tool_output": parsed.model_dump(),
            "reasoning": f"Intent={parsed.user_intent}; routing to {next_step}",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "ok",
        }],
    }
```

### `fetched_at` injection on Fuel/Route agents (D-13)

Modify `backend/agent/nodes/fuel_agent.py` line 127-130 (similarly `route_agent.py` line 134-137):

```python
# Replace:
return {"fuel_data": fuel_data.model_dump(), "reasoning_trace": [trace_entry]}

# With (D-13 addition):
fuel_dump = fuel_data.model_dump()
fuel_dump["fetched_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
return {"fuel_data": fuel_dump, "reasoning_trace": [trace_entry]}
```

**Note:** This is a non-breaking addition — Pydantic `FuelData.model_validate()` on the dict would fail (extra field), but Phase 2 code never round-trips through the Pydantic model after model_dump. The timestamp is consumed only by the Planner's `_fuel_fresh()`.

### SSE response handler (D-17/D-18 full flow)

See Pattern 4 above.

### Conversation list endpoint (D-21)

See Pattern 5 above.

### `GET /api/fuel-prices` endpoint (D-20)

```python
# Source: stdlib csv + D-20 spec
import csv
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
_CSV = Path("data/raw/eppo_diesel_prices.csv")

@router.get("/api/fuel-prices")
async def fuel_prices(days: int = Query(30, ge=1, le=365)):
    if not _CSV.exists():
        raise HTTPException(status_code=503, detail="Fuel price CSV not seeded")
    cutoff = datetime.utcnow().date() - timedelta(days=days)
    rows = []
    with _CSV.open() as f:
        for row in csv.DictReader(f):
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
            if d >= cutoff:
                rows.append({
                    "date": row["date"],
                    "price": float(row["diesel_b7_price"]),
                    "unit": "THB/L",
                    "source": row["source"],
                })
    return rows
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` / `@app.on_event("shutdown")` | `@asynccontextmanager lifespan` | FastAPI 0.93 (2023), strongly recommended since 0.107 | Phase 3 uses lifespan only; eventhandlers are deprecated. |
| Sync `SqliteSaver` in async code | `AsyncSqliteSaver` with `aiosqlite` | LangGraph 0.2.x; required since `langgraph` moved to async-first | Blocks event loop otherwise. D-15 mandate. |
| `astream` with `stream_mode="values"` giving full state dumps per step | `astream_events("v2")` with lifecycle events (`on_chain_start`, `on_chain_end`, `on_chat_model_stream`) | LangGraph 0.2 introduced v2 schema | More granular, but forces filtering. D-17 locks v2. |
| Raw `StreamingResponse` with manual SSE framing | `EventSourceResponse` (FastAPI ≥0.135) | 2026-03 | Not yet available on installable 0.128.8 — use StreamingResponse for now (Pitfall 5). |
| `graph.compile()` without `recursion_limit` | Explicit `.with_config({"recursion_limit": N})` | Always supported; now common as a safety net paired with business-level loop caps | Phase 3 adds explicit N=12 as belt-and-braces under D-04's N=6. |

**Deprecated / outdated:**
- `from langgraph.checkpoint.aiosqlite import AiosqliteSaver` (pre-0.2.0 name) → now `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`.
- Pydantic v1 `Optional[str]` implicit `None` default → in v2, Pydantic 2 requires explicit `= None` for truly optional (Pydantic WebSearch confirms).

## Open Questions

1. **AsyncSqliteSaver `.aget()` return shape in 2.0.11**
   - What we know: newer LangChain reference docs say `CheckpointTuple` with nested state at `.checkpoint["channel_values"]`. Older tutorials show a flat dict.
   - What's unclear: which shape the pinned 2.0.11 returns.
   - Recommendation: First task that touches `/api/conversations/:id` should `print(type(result))` against a fresh `:memory:` checkpointer in a quick local script and document the shape in a `# Source:` comment above the handler. Test with the D-26 `TestClient` asserting the JSON shape.

2. **Planner's normalisation of origin/destination**
   - What we know: Phase 2 Route Agent's cache is case-sensitive (in-process TTLCache keyed on raw strings).
   - What's unclear: whether Planner should title-case, lower-case, or preserve user input.
   - Recommendation: Planner prompt instructs "normalise to Title Case for Thai city/province names". Document in the system prompt and cover in a D-25 test.

3. **Response Node prose: Gemini vs. template**
   - What we know: D-11 markdown STRUCTURE is locked; the prose summary is Claude's discretion.
   - What's unclear: whether adding another Gemini call per request is worth the 1-2s latency (against the 10s target).
   - Recommendation: Use a **deterministic Jinja-style template** (Python f-string) for the prose in Phase 3 for predictable latency + clean tests. Revisit in Phase 5 after Langfuse shows the spare budget. Document as open question in the phase wrap-up.

4. **Conversation listing scalability**
   - What we know: D-21 caps the list at 50 threads. The SQL `MAX(checkpoint_id)` over all rows is O(n).
   - What's unclear: whether this is fast enough with 1000+ conversations (course demo almost certainly fewer than 50).
   - Recommendation: Ship as-is. Phase 5+ can add an index on `thread_id` if profiling shows bottleneck. Out of scope for Phase 3.

5. **Clarify-path without Gemini call**
   - What we know: D-06 says "Response Node renders the user-facing message via Gemini with the same D-11 fallback pattern."
   - What's unclear: whether the deterministic fallback for clarify-path should produce a generic "please provide X, Y, Z" message or a templated missing-field list.
   - Recommendation: If the prose is deterministic templated (per Open Question 3), the clarify-path message becomes a trivial f-string using `state["missing_fields"]`. No Gemini call needed in the clarify branch; simpler + faster + more reliable.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python runtime | All of Phase 3 | ✓ | **3.9.6** (.venv) — **note: CLAUDE.md says 3.11+ but actual venv is 3.9** | Constrain all new deps to Py3.9-compatible versions. |
| Node.js | (not needed this phase) | ✓ | v25.9.0 | — |
| `sqlite3` CLI | manual DB inspection (optional) | ✓ | 3.43.2 | — |
| `pip` | installing new deps | ✓ | 21.2.4 (old; `pip install --upgrade pip` recommended but not required) | — |
| `fastapi` package | ALL API endpoints | ✗ (not installed) | — | Install `fastapi==0.128.8` — verified Py3.9-compatible |
| `uvicorn[standard]` | Uvicorn dev server | ✗ | — | Install `uvicorn[standard]==0.36.1` |
| `langgraph-checkpoint-sqlite` | `AsyncSqliteSaver` | ✗ | — | Install `langgraph-checkpoint-sqlite==2.0.11` (3.0+ requires Py3.10+ — **BLOCKER** if used) |
| `aiosqlite` | `AsyncSqliteSaver` connection | ✗ | — | Install `aiosqlite==0.22.1` |
| `langgraph` | graph assembly | ✓ | 0.6.11 | — |
| `langchain-core` | message types | ✓ | 0.3.84 | — |
| `langchain-google-genai` | Gemini in Planner/Pricing/Response | ✓ | 2.1.12 | — |
| `pydantic` | `PlannerOutput`, API models | ✓ | 2.12.5 | — |
| `pandas` | optional CSV parsing in `/api/fuel-prices` | ✓ | 2.3.3 | stdlib `csv` is equivalent and lighter |
| `httpx` | test client + retryable exception type | ✓ | 0.28.1 | — |
| `pytest-httpx` | HTTP mocking in tests | ✓ | 0.35.0 | — |
| `pytest-mock` | `mocker.patch.object` in tests | ✓ | 3.15.1 | — |
| `pytest` | test runner | ✓ | 8.4.2 | — |
| Google API key (Gemini) | Planner / Pricing / Response narration | Runtime-only | (in `.env`) | Test path uses `FakeMessagesListChatModel` — no live calls (D-25) |
| Google Maps API key | Route Agent (reused) | Runtime-only | (in `.env`) | Test path mocks via `mocker.patch.object` on googlemaps client (Phase 2 seam) |
| EPPO CSV data | Fuel Agent + `/api/fuel-prices` | ✓ | `data/raw/eppo_diesel_prices.csv` (186 rows, 2025-10-01 → 2026-04-03) | — |
| Checkpoint DB | `AsyncSqliteSaver` | Auto-created on first `.setup()` | `data/checkpoints.db` (not yet present) | — |

**Missing dependencies with no fallback:** None — all blockers have pinned workarounds.

**Missing dependencies with fallback:** None critical; pandas (optional for `/api/fuel-prices`) is already installed but stdlib `csv` is the recommended choice given 186-row file size.

**Environment risk notes:**
- `.venv` is Python 3.9 — do NOT update deps blindly to latest-major. Lock every new dep to a known-working 3.9 version.
- `pip` is 21.2.4 (released Dec 2022). Older pip sometimes ignores Requires-Python on universal wheels — which is actually fortunate here (lets us install `langgraph-checkpoint-sqlite==2.0.11`), but planner should `pip install --upgrade pip` once if any dep resolution surprises emerge.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest==8.4.2` + `pytest-mock==3.15.1` + `pytest-httpx==0.35.0` |
| Config file | `backend/tests/conftest.py` (fixtures); no `pytest.ini` yet — runs via default discovery rooted at `backend/tests/` |
| Quick run command | `.venv/bin/python -m pytest backend/tests/test_<module>.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest backend/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORCH-01 | Planner detects intent `surcharge_query` and routes to `fetch_fuel` when fuel_data absent | unit | `.venv/bin/python -m pytest backend/tests/test_planner.py::test_routes_to_fetch_fuel_on_fresh_query -x` | ❌ Wave 0 |
| ORCH-01 | Planner skips fetch when fuel_data is fresh (D-12 cache reuse) | unit | `.venv/bin/python -m pytest backend/tests/test_planner.py::test_skips_fetch_when_fuel_fresh -x` | ❌ Wave 0 |
| ORCH-01 | Planner emits `clarify` when missing_fields non-empty | unit | `.venv/bin/python -m pytest backend/tests/test_planner.py::test_emits_clarify_on_missing_fields -x` | ❌ Wave 0 |
| ORCH-01 | Planner hits D-04 loop budget and forces `respond` | unit | `.venv/bin/python -m pytest backend/tests/test_planner.py::test_loop_budget_exhaustion_forces_respond -x` | ❌ Wave 0 |
| ORCH-01 | Planner D-02 fallback: parse failure yields `clarify` with `planner_parse_failed` | unit | `.venv/bin/python -m pytest backend/tests/test_planner.py::test_parse_failure_falls_back_to_clarify -x` | ❌ Wave 0 |
| ORCH-04 | Pricing Agent invokes `lookup_rate` + `calculate_surcharge_tool` and emits compound trace | unit | `.venv/bin/python -m pytest backend/tests/test_pricing_agent.py::test_computes_surcharge_and_emits_trace -x` | ❌ Wave 0 |
| ORCH-04 | Pricing Agent bubbles ValueError from lookup_rate (D-09) | unit | `.venv/bin/python -m pytest backend/tests/test_pricing_agent.py::test_bubbles_value_error_from_lookup_rate -x` | ❌ Wave 0 |
| ORCH-04 | Pricing Agent D-11 fallback narration on Gemini failure | unit | `.venv/bin/python -m pytest backend/tests/test_pricing_agent.py::test_gemini_failure_deterministic_fallback -x` | ❌ Wave 0 |
| ORCH-05 | Response Node renders D-10 payload with locked D-11 markdown structure | unit | `.venv/bin/python -m pytest backend/tests/test_response_node.py::test_renders_locked_markdown_structure -x` | ❌ Wave 0 |
| ORCH-05 | Response Node detects `state.errors` and emits `status: "partial"` | unit | `.venv/bin/python -m pytest backend/tests/test_response_node.py::test_partial_status_on_errors -x` | ❌ Wave 0 |
| ORCH-05 | Response Node detects `state.clarification_reason` and emits `status: "clarify"` | unit | `.venv/bin/python -m pytest backend/tests/test_response_node.py::test_clarify_status -x` | ❌ Wave 0 |
| ORCH-05 | Response Node prepends cap callout when `capped=true` | unit | `.venv/bin/python -m pytest backend/tests/test_response_node.py::test_cap_callout_prepended -x` | ❌ Wave 0 |
| ORCH-08 | RetryPolicy applied to all nodes with custom `retry_on` (D-23 compliance) | unit | `.venv/bin/python -m pytest backend/tests/test_graph.py::test_retry_policy_retries_httpx_error -x` | ❌ Wave 0 |
| ORCH-08 | Retry exhaustion triggers D-24 error-sink path → `respond` with partial result | integration | `.venv/bin/python -m pytest backend/tests/test_graph.py::test_retry_exhaustion_routes_to_response_partial -x` | ❌ Wave 0 |
| ORCH-08 | `ValueError` does NOT trigger retries (D-23) | unit | `.venv/bin/python -m pytest backend/tests/test_graph.py::test_value_error_skips_retry -x` | ❌ Wave 0 |
| ORCH-10 | AsyncSqliteSaver persists state across two invocations on same thread_id | integration | `.venv/bin/python -m pytest backend/tests/test_graph.py::test_checkpointer_persists_across_invocations -x` | ❌ Wave 0 |
| ORCH-10 | Follow-up on same thread reuses cached fuel_data (no re-fetch) | integration | `.venv/bin/python -m pytest backend/tests/test_graph.py::test_followup_reuses_cached_fuel -x` | ❌ Wave 0 |
| ORCH-10 | fetched_at is appended to fuel_data / route_data model_dump outputs (D-13) | unit | `.venv/bin/python -m pytest backend/tests/test_fuel_agent.py::test_fetched_at_added_to_dump -x` | ❌ Wave 0 (extends existing test file) |
| API-01 | POST `/api/chat` returns SSE stream with `meta → trace* → answer → done` sequence | integration | `.venv/bin/python -m pytest backend/tests/test_api_chat.py::test_happy_path_sse_sequence -x` | ❌ Wave 0 |
| API-01 | POST `/api/chat` emits `error` event on exception, then `done` | integration | `.venv/bin/python -m pytest backend/tests/test_api_chat.py::test_error_sse_sequence -x` | ❌ Wave 0 |
| API-01 | `meta` event contains server-generated `thread_id` when client omits it | integration | `.venv/bin/python -m pytest backend/tests/test_api_chat.py::test_server_generates_thread_id -x` | ❌ Wave 0 |
| API-02 | GET `/api/conversations` lists threads ordered by latest checkpoint_id desc | integration | `.venv/bin/python -m pytest backend/tests/test_api_conversations.py::test_lists_conversations_desc -x` | ❌ Wave 0 |
| API-03 | GET `/api/conversations/:id` returns message history for that thread | integration | `.venv/bin/python -m pytest backend/tests/test_api_conversations.py::test_returns_thread_state -x` | ❌ Wave 0 |
| API-03 | GET `/api/conversations/:unknown` returns 404 | integration | `.venv/bin/python -m pytest backend/tests/test_api_conversations.py::test_404_unknown_thread -x` | ❌ Wave 0 |
| API-04 | GET `/api/fuel-prices?days=30` returns last 30 days of EPPO CSV data | integration | `.venv/bin/python -m pytest backend/tests/test_api_fuel_prices.py::test_returns_last_30_days -x` | ❌ Wave 0 |
| API-04 | GET `/api/fuel-prices?days=365` clamps to available rows | integration | `.venv/bin/python -m pytest backend/tests/test_api_fuel_prices.py::test_clamps_to_available -x` | ❌ Wave 0 |
| Cross | Full happy-path query "Surcharge for 15kg Bounce Bangkok→Nonthaburi" end-to-end | integration | `.venv/bin/python -m pytest backend/tests/test_graph.py::test_full_surcharge_query_integration -x` | ❌ Wave 0 |
| Cross | Follow-up "What about Retail Fast?" reuses fuel + route, only Pricing runs | integration | `.venv/bin/python -m pytest backend/tests/test_graph.py::test_followup_only_runs_pricing -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest backend/tests/test_<module>.py -x` for the module being modified.
- **Per wave merge:** `.venv/bin/python -m pytest backend/tests/ -q` (full backend suite; currently ~30 tests from Phase 1+2, Phase 3 adds ~28).
- **Phase gate:** Full suite green + `uvicorn backend.api.main:app` boots successfully + manual SSE test via `curl -N http://localhost:8000/api/chat -d '{"message":"...","thread_id":null}' -H "Content-Type: application/json"` before `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] `backend/tests/test_planner.py` — covers ORCH-01 (Planner behavior + D-12 cache + D-04 loop cap + D-02 fallback)
- [ ] `backend/tests/test_pricing_agent.py` — covers ORCH-04 (narration + D-09 ValueError bubble + D-11 fallback)
- [ ] `backend/tests/test_response_node.py` — covers ORCH-05 (D-10 payload, D-11 markdown, status=ok/clarify/partial)
- [ ] `backend/tests/test_graph.py` — covers ORCH-08 (retry topology), ORCH-10 (checkpointer persistence), cross-cutting integration tests
- [ ] `backend/tests/test_api_chat.py` — covers API-01 (SSE sequence, thread_id flow)
- [ ] `backend/tests/test_api_conversations.py` — covers API-02 + API-03
- [ ] `backend/tests/test_api_fuel_prices.py` — covers API-04
- [ ] Extend `backend/tests/conftest.py` — add `in_memory_checkpointer` fixture using `aiosqlite.connect(":memory:")` + `AsyncSqliteSaver(conn).setup()`
- [ ] Extend `backend/tests/test_fuel_agent.py` — add one test asserting `fetched_at` present in returned `fuel_data` (D-13)
- [ ] Extend `backend/tests/test_route_agent.py` — add one test asserting `fetched_at` present in returned `route_data` (D-13)
- [ ] Framework install: **none required** — pytest + pytest-mock + pytest-httpx already installed and working from Phase 2.

## Sources

### Primary (HIGH confidence)

- **Installed `langgraph==0.6.11`** — verified `RetryPolicy` signature `(initial_interval=0.5, backoff_factor=2.0, max_interval=128.0, max_attempts=3, jitter=True, retry_on=default_retry_on)` via `inspect.signature(RetryPolicy)`; verified `default_retry_on` source (returns True for generic Exception fallthrough).
- **Downloaded `langgraph-checkpoint-sqlite==2.0.11` wheel** — verified `AsyncSqliteSaver(conn: aiosqlite.Connection, *, serde=None)` signature + methods (`aget`, `alist`, `aput`, `setup`, `list`, `get`).
- **`pip download` picks 2.0.11 on Python 3.9.6** (reproducible) — confirms dep pin is installable.
- `backend/agent/nodes/fuel_agent.py` (Phase 2 reference implementation, lines 1-131) — template for D-11 fallback + D-12 trace.
- `backend/agent/nodes/route_agent.py` (Phase 2 reference, lines 1-138) — same pattern + D-10 Planner contract.
- `backend/agent/tools/lookup_rate.py` + `calculate_surcharge_tool.py` (Phase 2) — D-14 ValueError contract.
- `backend/agent/state.py` (Phase 2) — existing TypedDict pattern for D-05 extension.
- `docs/architecture.md` — Conditional Routing table, API Endpoints, Error Handling.
- `.planning/phases/02-tools-agent-nodes/` — all Phase 2 locked decisions (D-04, D-07, D-09, D-10, D-11, D-12, D-14, D-15, D-16).
- **FastAPI Lifespan Events** — https://fastapi.tiangolo.com/advanced/events/
- **LangGraph Streaming** — https://docs.langchain.com/oss/python/langgraph/streaming
- **LangGraph Persistence** — https://docs.langchain.com/oss/python/langgraph/persistence
- **LangGraph GRAPH_RECURSION_LIMIT** — https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT
- **LangGraph RetryPolicy reference** — https://reference.langchain.com/python/langgraph/types/RetryPolicy
- **AsyncSqliteSaver reference** — https://reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver

### Secondary (MEDIUM confidence)

- **langgraph-checkpoint-sqlite PyPI** — https://pypi.org/project/langgraph-checkpoint-sqlite/ (confirmed `Requires-Python >=3.10` is for 3.x; 2.0.11 is py3-universal and installable on 3.9)
- **sse-starlette PyPI** — https://pypi.org/project/sse-starlette/ (confirms installable as wheel on 3.9 despite Requires-Python >=3.10 metadata)
- **LangChain forum: control flow after retries exhausted** — https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574 (community consensus: manual try/except is the idiomatic fallback)
- **Streaming AI Agent with FastAPI & LangGraph (2025-26)** — https://dev.to/kasi_viswanath/streaming-ai-agent-with-fastapi-langgraph-2025-26-guide-1nkn (current streaming pattern for FastAPI + LangGraph)
- **LangGraph Streaming 101: 5 Modes** — https://dev.to/sreeni5018/langgraph-streaming-101-5-modes-to-build-responsive-ai-applications-4p3f (compares stream_mode="updates" vs astream_events)
- **LangGraph add_conditional_edges (Issue #987)** — https://github.com/langchain-ai/langgraph/issues/987 (clarifies path_map behavior)
- **FastAPI Server-Sent Events tutorial** — https://fastapi.tiangolo.com/tutorial/server-sent-events/ (documents EventSourceResponse — note: only available FastAPI 0.135+)
- **LangGraph Error Handling Guide (dev.to)** — https://dev.to/aiengineering/a-beginners-guide-to-handling-errors-in-langgraph-with-retry-policies-h22
- **Pydantic v2 Models concepts** — https://docs.pydantic.dev/latest/concepts/models/ (confirms explicit `= None` default pattern for Optional)

### Tertiary (LOW confidence — flagged for validation)

- Specific AsyncSqliteSaver `.aget()` return shape for 2.0.11 — documented as Open Question 1 pending first-task source inspection.
- `EventSourceResponse` deprecation/replacement timeline (WebFetch returned FastAPI 0.135+ pattern, but 0.128.8 is latest installable as of 2026-04-25) — not a blocker; planner uses raw `StreamingResponse`.
- `checkpoints` table schema in `langgraph-checkpoint-sqlite==2.0.11` specifically (vs. newer versions) — verified by DeepWiki; planner should confirm column names via `PRAGMA table_info(checkpoints);` in the first conversation-listing task.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — versions verified by `pip index`, `pip download`, and manual `inspect.signature` / `import` against pinned wheels.
- Architecture patterns: **HIGH** — patterns derived from existing Phase 2 code + locked CONTEXT decisions + cross-checked with official LangGraph + FastAPI docs.
- Pitfalls: **HIGH** for 1-5 and 8-9 (reproducible or checked against installed source); **MEDIUM** for 6 (AsyncSqliteSaver return shape) and 7 (string-case convention, a convention question rather than a bug).
- Runtime state: **HIGH** — no data migration; only a new checkpoint DB auto-created by setup.
- Validation architecture: **HIGH** — existing test infra proven in Phase 2; Phase 3 adds new test files but no framework changes.

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (30 days — stack is stable; re-verify `langgraph-checkpoint-sqlite` version if reopened after that window).
