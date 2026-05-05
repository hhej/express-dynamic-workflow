# Architecture Patterns

**Domain:** Multi-agent LangGraph orchestrator for logistics surcharge calculation
**Researched:** 2026-04-04
**Overall Confidence:** MEDIUM (based on training data through early 2025; web verification unavailable)

---

## Recommended Architecture

### Pattern: Supervisor with Parallel Fan-Out

The system follows a **supervisor (planner) pattern** where a central orchestrator node decides which specialist agents to invoke, routes to them via conditional edges, and a response node synthesizes the final output. This is the canonical LangGraph multi-agent pattern for deterministic workflows where the planner has full visibility into state.

**Why supervisor over network/hierarchical:**
- The workflow is predictable: planner decides, specialists execute, response synthesizes. No agent-to-agent negotiation needed.
- Supervisor keeps the graph debuggable and traceable -- critical for the reasoning trace requirement.
- Hierarchical patterns (sub-graphs calling sub-graphs) add complexity without benefit here since we have only 3 specialists.

```
                    START
                      |
                      v
               +-----------+
               |  Planner  |  (LLM: intent detection, state inspection)
               +-----+-----+
                     |
          conditional_edges(next_step)
          /          |           \            \
         v           v            v            v
   +---------+  +---------+  +---------+  +---------+
   |  Fuel   |  |  Route  |  | Pricing |  |Response |
   |  Agent  |  |  Agent  |  |  Agent  |  |  Node   |
   +---------+  +---------+  +---------+  +---------+
         \           |            |            |
          \          |           /             |
           v         v          v              |
        +------------------+                   |
        | Pricing Agent    |<---(if both done) |
        +--------+---------+                   |
                 |                             |
                 v                             |
           +-----------+                       |
           | HITL Gate |  (interrupt_before)    |
           +-----+-----+                       |
                 |                             |
                 v                             v
           +-----------+                 +-----------+
           | Response  |                 | Response  |
           |   Node    |                 |   Node    |
           +-----+-----+                 +-----+-----+
                 |                             |
                 v                             v
                END                           END
```

### Key Insight: Two Distinct Flow Paths

The graph supports two primary flow paths that share the same nodes but traverse different edges:

1. **Surcharge calculation flow:** Planner -> Fuel+Route (parallel) -> Pricing -> HITL Gate -> Response
2. **Information/clarification flow:** Planner -> Response (direct, no agents needed) or Planner -> Fuel (search mode) -> Response

The `next_step` field in state drives which path is taken via conditional edges.

---

## Component Boundaries

| Component | Responsibility | Inputs | Outputs | Communicates With |
|-----------|---------------|--------|---------|-------------------|
| **FastAPI Server** | HTTP layer, SSE streaming, session management | HTTP requests | SSE events, JSON responses | LangGraph engine, SQLite, Langfuse |
| **LangGraph Engine** | Graph compilation, execution, state management | Compiled graph + AgentState | Updated AgentState | All agent nodes, checkpointer |
| **Planner Node** | Intent detection, routing decision, state inspection | `messages`, current state fields | `next_step` routing decision | LLM (Gemini), state channels |
| **Fuel Agent Node** | Fuel price fetching with fallback chain | `fuel_type`, `region` from state | `fuel_data` dict in state | EPPO/PTT API, CSV fallback, Tavily |
| **Route Agent Node** | Distance/traffic calculation with caching | `origin`, `destination` from messages | `route_data` dict in state | Google Maps API, route cache |
| **Pricing Agent Node** | Rate lookup + surcharge formula execution | `fuel_data`, `route_data`, `shipping_type`, `weight_kg` | `surcharge_result` dict in state | SQLite rate table |
| **HITL Gate Node** | Approval checkpoint for high-value shipments | `surcharge_result` | Approval/rejection flag | Checkpointer (interrupt_before) |
| **Response Node** | Final answer synthesis with reasoning trace | Full state | Formatted response message | LLM (Gemini) |
| **SQLite Checkpointer** | Conversation persistence and HITL resumption | State snapshots | Restored state | LangGraph engine |
| **Langfuse Callback** | Tracing all LLM/tool calls | Callback events | Traces in Langfuse | Every LLM and tool invocation |

### Boundary Rules

1. **Nodes never call other nodes directly.** All routing goes through conditional edges. This is enforced by LangGraph's graph structure.
2. **Tools are owned by nodes.** Each tool function is bound to a specific agent node. The Fuel Agent owns `fetch_fuel_price` and `search_fuel_news`. The Route Agent owns `calculate_route`. The Pricing Agent owns `lookup_rate` and `calculate_surcharge`.
3. **State is the shared bus.** Agents communicate exclusively through `AgentState` typed dict channels. No direct function calls between agents.
4. **The FastAPI layer never touches agent internals.** It invokes `graph.astream()` and forwards SSE events. It does not inspect or modify agent state mid-execution.

---

## Data Flow

### Primary Surcharge Calculation Flow

```
User message (HTTP POST /api/chat)
    |
    v
FastAPI endpoint
    |-- Creates/resumes thread_id
    |-- Invokes graph.astream({"messages": [user_msg]}, config={"configurable": {"thread_id": tid}})
    |
    v
[Planner Node]
    |-- LLM inspects messages + state
    |-- Determines: fuel_data missing? route_data missing? both?
    |-- Sets next_step = "fetch_parallel" or "fetch_fuel" or "calculate_price" etc.
    |-- Appends to reasoning_trace
    |
    v (conditional edge: next_step == "fetch_parallel")
[Send API: Fan-out to Fuel + Route in parallel]
    |
    +-- [Fuel Agent] -----> calls fetch_fuel_price tool
    |                        EPPO API -> PTT scrape -> CSV -> hardcoded
    |                        Writes fuel_data to state
    |                        Appends to reasoning_trace
    |
    +-- [Route Agent] ----> calls calculate_route tool
    |                        Google Maps API (15-min cache)
    |                        Writes route_data to state
    |                        Appends to reasoning_trace
    |
    v (fan-in: both complete)
[Pricing Agent]
    |-- Reads fuel_data, route_data, shipping_type, weight_kg from state
    |-- Calls lookup_rate tool (SQLite query)
    |-- Calls calculate_surcharge (pure computation)
    |-- Writes surcharge_result to state
    |-- Appends to reasoning_trace
    |
    v (conditional: high-value shipment?)
[HITL Gate] -- interrupt_before
    |-- Checkpointer saves state
    |-- Execution pauses, SSE sends "awaiting_approval" event
    |-- User approves/rejects via UI
    |-- graph.astream(None, config) resumes from checkpoint
    |
    v
[Response Node]
    |-- LLM synthesizes answer from surcharge_result + reasoning_trace
    |-- Formats breakdown table, recommendations
    |-- Appends final message to state
    |
    v
SSE stream back to frontend
    |-- Each node emits events as it executes
    |-- Frontend renders reasoning trace in real-time
    |-- Final response displayed in chat
```

### Follow-Up Query Flow (Memory Reuse)

```
User: "What about Retail Fast?"
    |
    v
[Planner Node]
    |-- Inspects state: fuel_data present (< 1hr old)? YES
    |-- Inspects state: route_data present? YES
    |-- Only shipping_type changed
    |-- Sets next_step = "calculate_price" (skips Fuel + Route)
    |
    v
[Pricing Agent] -- reuses cached fuel_data and route_data
    |
    v
[Response Node]
```

This is a key architectural advantage of LangGraph's stateful checkpointing: follow-up queries avoid redundant API calls by inspecting persisted state.

### SSE Event Stream Structure

Each node should emit structured SSE events for the frontend reasoning trace:

```
event: agent_step
data: {"node": "planner", "action": "routing", "detail": "Fuel and route data needed", "next": "fetch_parallel"}

event: tool_call
data: {"node": "fuel_agent", "tool": "fetch_fuel_price", "input": {"fuel_type": "diesel_b7"}, "status": "calling"}

event: tool_result
data: {"node": "fuel_agent", "tool": "fetch_fuel_price", "output": {"price": 31.44, "source": "eppo"}, "status": "success"}

event: agent_step
data: {"node": "pricing_agent", "action": "calculating", "detail": "Applying bounce multiplier 1.0x"}

event: response
data: {"content": "The surcharge for your Bounce shipment...", "surcharge_result": {...}}
```

---

## LangGraph-Specific Implementation Patterns

### 1. StateGraph Construction

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

# Define the graph
builder = StateGraph(AgentState)

# Add nodes
builder.add_node("planner", planner_node)
builder.add_node("fuel_agent", fuel_agent_node)
builder.add_node("route_agent", route_agent_node)
builder.add_node("pricing_agent", pricing_agent_node)
builder.add_node("hitl_gate", hitl_gate_node)
builder.add_node("response", response_node)

# Entry point
builder.set_entry_point("planner")

# Conditional edges from planner
builder.add_conditional_edges(
    "planner",
    route_planner_output,  # function that reads next_step
    {
        "fetch_fuel": "fuel_agent",
        "fetch_route": "route_agent",
        "fetch_parallel": "fan_out",  # handled by Send
        "calculate_price": "pricing_agent",
        "search_context": "fuel_agent",
        "clarify": "response",
        "respond": "response",
    }
)

# After specialist agents, route back or forward
builder.add_edge("fuel_agent", "check_ready")
builder.add_edge("route_agent", "check_ready")
builder.add_conditional_edges(
    "check_ready",
    check_if_ready_for_pricing,
    {
        "ready": "pricing_agent",
        "waiting": END,  # other parallel agent still running
    }
)
builder.add_edge("pricing_agent", "hitl_gate")
builder.add_edge("hitl_gate", "response")
builder.add_edge("response", END)

# Compile with checkpointer
memory = SqliteSaver.from_conn_string("data/checkpoints.db")
graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["hitl_gate"],  # HITL pattern
)
```

**Confidence: MEDIUM** -- The above follows documented LangGraph StateGraph patterns. Exact API surface for `SqliteSaver` and `interrupt_before` should be verified against current LangGraph version.

### 2. Send API for Parallel Execution

The `Send` API allows fan-out to multiple node instances in parallel. For the Fuel + Route parallel pattern:

```python
from langgraph.constants import Send

def route_planner_output(state: AgentState):
    next_step = state["next_step"]
    if next_step == "fetch_parallel":
        # Fan-out: send to both fuel and route agents simultaneously
        return [
            Send("fuel_agent", state),
            Send("route_agent", state),
        ]
    return next_step
```

**Critical detail:** When using `Send`, both nodes receive a copy of the current state. Their outputs are merged back into the parent state via **reducers** on the state channels. This means `fuel_data` and `route_data` must use `operator.add` or custom reducers, OR (simpler for this case) each agent writes to its own dedicated state key, avoiding merge conflicts.

**Confidence: MEDIUM** -- Send API existed in LangGraph v0.1+ but the exact semantics of state merging after fan-in may have evolved. Verify with current docs.

### 3. State Channel Design with Reducers

```python
from typing import Annotated
from operator import add
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

class AgentState(TypedDict):
    # Messages use built-in add_messages reducer (appends, handles dedup)
    messages: Annotated[list[BaseMessage], add_messages]

    # Agent data fields: use "last writer wins" (default, no reducer needed)
    fuel_data: dict | None
    route_data: dict | None
    shipping_type: str | None
    weight_kg: float | None
    surcharge_result: dict | None

    # Reasoning trace: use list append reducer for parallel safety
    reasoning_trace: Annotated[list[dict], add]

    # Routing: last writer wins
    next_step: str
```

**Key insight:** The `messages` field MUST use `add_messages` reducer. Without it, parallel agents would overwrite each other's messages. The `reasoning_trace` list should also use `add` (or `operator.add`) so parallel agents can both append trace entries without conflict.

Fields like `fuel_data` and `route_data` are fine with default "last writer wins" since only one agent writes to each.

### 4. Human-in-the-Loop via interrupt_before

```python
# At compile time:
graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["hitl_gate"],
)

# At runtime (FastAPI endpoint):
async def chat_endpoint(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}

    async for event in graph.astream({"messages": [request.message]}, config):
        if event.get("__interrupt__"):
            # Graph paused before hitl_gate
            # Send SSE event asking for approval
            yield sse_event("approval_required", event["state"]["surcharge_result"])
            return

        yield sse_event("agent_step", event)

# When user approves:
async def approve_endpoint(request: ApproveRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    # Resume from checkpoint -- pass None as input to continue
    async for event in graph.astream(None, config):
        yield sse_event("agent_step", event)
```

**Confidence: MEDIUM** -- The `interrupt_before` pattern is well-documented. The exact event shape from `astream` when interrupted should be verified.

### 5. Checkpointer for Conversation Memory

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Use async version for FastAPI
async with AsyncSqliteSaver.from_conn_string("data/checkpoints.db") as memory:
    graph = builder.compile(checkpointer=memory)
```

Each conversation gets a unique `thread_id`. The checkpointer automatically saves state after each node execution. When the user sends a follow-up message, `graph.astream(new_input, config)` loads the latest checkpoint for that thread and resumes from it.

**Confidence: MEDIUM** -- `AsyncSqliteSaver` may have been renamed or restructured. The `aio` submodule path should be verified.

### 6. Structured Output with Pydantic

```python
from pydantic import BaseModel, Field

class FuelData(BaseModel):
    price: float = Field(description="Current diesel price in THB/L")
    date: str = Field(description="Price date in YYYY-MM-DD")
    source: str = Field(description="Data source: eppo, ptt, csv, or hardcoded")
    baseline: float = Field(description="Baseline diesel price in THB/L")
    delta_pct: float = Field(description="Percentage change from baseline")

class RouteData(BaseModel):
    origin: str
    destination: str
    distance_km: float
    duration_min: int
    traffic_severity: int = Field(ge=1, le=5)
    zone: str = Field(pattern=r"^central-[123]$")

class SurchargeResult(BaseModel):
    base_rate: float
    surcharge_pct: float
    surcharge_amount: float
    total: float
    capped: bool
    breakdown: dict
```

Use these models in tool return types for deterministic, testable outputs. The LLM does not generate these -- the tools compute and return them as structured data that gets written to state.

---

## Patterns to Follow

### Pattern 1: Tool-Computed, Not LLM-Generated

**What:** All numerical outputs (prices, distances, surcharges) come from tool functions, not LLM generation. The LLM decides WHICH tools to call and synthesizes the narrative response, but never generates numbers.

**Why:** Eliminates hallucinated calculations. Makes outputs deterministic and testable. The surcharge formula is a pure function -- it should never pass through an LLM.

**Implementation:** Tools return Pydantic models. Agent nodes call tools and write structured results to state. The Response node reads these structured results to format the final message.

### Pattern 2: State-Driven Routing (Not Message Parsing)

**What:** The Planner inspects typed state fields (`fuel_data is None`, `route_data is None`) to decide routing, rather than parsing previous message content.

**Why:** Reliable, testable routing. No risk of the LLM misinterpreting its own prior messages. State fields have clear types and staleness checks.

**Implementation:**
```python
def planner_node(state: AgentState) -> dict:
    # Check what data we already have
    has_fuel = state.get("fuel_data") and is_fresh(state["fuel_data"], max_age_hours=1)
    has_route = state.get("route_data")
    has_shipping = state.get("shipping_type")

    if not has_fuel and not has_route:
        return {"next_step": "fetch_parallel"}
    elif not has_fuel:
        return {"next_step": "fetch_fuel"}
    elif not has_route:
        return {"next_step": "fetch_route"}
    elif has_fuel and has_route and has_shipping:
        return {"next_step": "calculate_price"}
    else:
        return {"next_step": "clarify"}
```

### Pattern 3: Fallback Chain as Tool Implementation Detail

**What:** The multi-level fuel fallback (API -> scrape -> CSV -> hardcoded) is implemented entirely within the `fetch_fuel_price` tool, not as separate graph nodes.

**Why:** Keeps the graph simple. Fallback is a tool concern, not an orchestration concern. The agent graph doesn't need to know or care which source succeeded -- it gets a `FuelData` model either way.

### Pattern 4: Streaming Reasoning Trace via Callbacks

**What:** Use LangGraph's `astream_events` (v2) or callback-based streaming to emit reasoning trace events in real-time over SSE.

**Why:** The reasoning trace is a core grading criterion. Users must see each agent step as it happens, not just the final result.

**Implementation:** Prefer `astream_events` over `astream` for granular streaming:
```python
async for event in graph.astream_events(input, config, version="v2"):
    kind = event["event"]
    if kind == "on_chain_start":
        yield sse_event("agent_start", {"node": event["name"]})
    elif kind == "on_tool_start":
        yield sse_event("tool_call", {"tool": event["name"], "input": event["data"]})
    elif kind == "on_tool_end":
        yield sse_event("tool_result", {"tool": event["name"], "output": event["data"]})
    elif kind == "on_chain_end":
        yield sse_event("agent_end", {"node": event["name"], "output": event["data"]})
```

**Confidence: MEDIUM** -- `astream_events` v2 was available in LangGraph/LangChain by late 2024. Verify exact event schema.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: LLM as Calculator

**What:** Passing numerical data through the LLM to compute surcharges.
**Why bad:** LLMs hallucinate arithmetic. Non-deterministic. Untestable. You will get different surcharges for the same inputs.
**Instead:** Pure Python functions for all calculations. LLM only handles intent detection and natural language synthesis.

### Anti-Pattern 2: Monolithic Agent Node

**What:** One giant node that fetches fuel, calculates route, looks up rates, and computes surcharge.
**Why bad:** Cannot parallelize. Cannot test individual capabilities. Cannot reuse cached data selectively. Defeats the purpose of the multi-agent architecture (which is literally being graded).
**Instead:** One node per concern. Each node owns its tools and writes to its own state keys.

### Anti-Pattern 3: Message-Based Inter-Agent Communication

**What:** Agents communicating by writing messages that other agents parse.
**Why bad:** Fragile. LLM might misinterpret another agent's message. Adds latency (each message requires an LLM call to parse).
**Instead:** Write structured data to typed state fields. Agents read state, not messages.

### Anti-Pattern 4: Eager API Calls

**What:** Calling EPPO/Google Maps on every single user message regardless of state.
**Why bad:** Hits rate limits. Wastes free-tier quota. Adds unnecessary latency.
**Instead:** Planner checks state staleness before routing. Fuel data cached 1hr. Route data cached until origin/destination changes.

### Anti-Pattern 5: Untyped State

**What:** Using `dict[str, Any]` for agent state instead of TypedDict with Pydantic models.
**Why bad:** No IDE support, no validation, bugs surface at runtime instead of import time.
**Instead:** TypedDict for state schema, Pydantic models for tool return types.

---

## File/Module Structure Recommendation

```
agent/
  state.py              # AgentState TypedDict + Pydantic models
  graph.py              # StateGraph construction + compilation
  nodes/
    planner.py          # Planner node (intent detection + routing)
    fuel_agent.py       # Fuel Agent node
    route_agent.py      # Route Agent node
    pricing_agent.py    # Pricing Agent node
    response.py         # Response synthesis node
    hitl_gate.py        # Human-in-the-loop gate node
  tools/
    fuel_price.py       # fetch_fuel_price (with fallback chain)
    route_calculator.py # calculate_route (with caching)
    rate_lookup.py      # lookup_rate (SQLite query)
    surcharge.py        # calculate_surcharge (pure function)
    fuel_search.py      # search_fuel_news (Tavily)
  prompts/
    planner.py          # Planner system prompt
    response.py         # Response synthesis prompt
app/
  api/
    chat.py             # POST /api/chat (SSE streaming)
    conversations.py    # GET /api/conversations
    fuel_prices.py      # GET /api/fuel-prices
    feedback.py         # POST /api/feedback
  evaluation/
    callbacks.py        # Langfuse callback handler
    auto_eval.py        # Formula accuracy checker
  config.py             # Environment variables + constants
  main.py               # FastAPI app + Uvicorn entry point
  database.py           # SQLite connection + helpers
```

This structure maps 1:1 to the component boundaries defined above. Each file has a single responsibility and a clear dependency direction (tools -> nodes -> graph -> api).

---

## Scalability Considerations

| Concern | Course Demo (5 users) | Production (100+ users) |
|---------|----------------------|------------------------|
| Concurrency | Single Uvicorn worker fine | Add workers, switch to PostgreSQL checkpointer |
| SQLite locks | No issue with low concurrency | Would need PostgreSQL or WAL mode |
| API rate limits | Google Maps free tier sufficient | Need paid tier or aggressive caching |
| LLM throughput | Gemini free tier: 15 RPM | Need paid tier or request queuing |
| State size | Full conversation in memory fine | Need state pruning / summarization |

**For this project:** Scalability is explicitly out of scope. SQLite + single worker + free tier is the correct choice for demo and grading.

---

## Sources

- LangGraph documentation (concepts: multi-agent, human-in-the-loop, persistence, streaming) -- training data through early 2025
- LangGraph examples repository (multi-agent supervisor pattern) -- training data
- Project architecture doc (`docs/architecture.md`) -- local file
- Project spec (`PROJECT.md`) -- local file

**Confidence note:** All LangGraph-specific API details (Send, interrupt_before, astream_events, SqliteSaver) are based on training data. The patterns are architecturally sound but exact import paths and method signatures should be verified against the installed LangGraph version before implementation. Run `pip install langgraph && python -c "import langgraph; print(langgraph.__version__)"` to confirm.
