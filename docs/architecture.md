# Architecture Document

## Express Dynamic Surcharge Orchestrator

### Overview

This system is an **Agentic AI product** that dynamically calculates fuel surcharges for Express logistics operations in Thailand's Bangkok Metro. The agent reasons over live fuel prices, route data, and internal rate tables to produce surcharge recommendations — it is the core decision-making product, not a feature on a dashboard.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SYSTEM OVERVIEW                              │
│                                                                     │
│  ┌──────────┐    SSE / REST    ┌───────────────────────────────┐   │
│  │ Next.js  │◄────────────────►│  FastAPI Backend              │   │
│  │ Frontend │                  │                               │   │
│  │          │                  │  ┌─────────────────────────┐  │   │
│  │ - Chat   │                  │  │  LangGraph Orchestrator │  │   │
│  │ - Trace  │                  │  │                         │  │   │
│  │ - Charts │                  │  │  Planner ──► Fuel Agent │  │   │
│  │ - Feedback│                 │  │          ──► Route Agent│  │   │
│  └──────────┘                  │  │          ──► Price Agent│  │   │
│                                │  └────────┬────────────────┘  │   │
│                                │           │                   │   │
│                                │  ┌────────▼────────┐          │   │
│                                │  │  SQLite Memory  │          │   │
│                                │  │  (Checkpointer) │          │   │
│                                │  └─────────────────┘          │   │
│                                └───────────┬───────────────────┘   │
│                                            │                       │
│          ┌─────────────────────────────────┼────────────────┐      │
│          │         EXTERNAL SERVICES       │                │      │
│          │                                 │                │      │
│          │  ┌──────────┐  ┌────────────┐   ▼                │      │
│          │  │ EPPO /   │  │ Google     │  ┌─────────────┐  │      │
│          │  │ PTT API  │  │ Maps API   │  │  Langfuse   │  │      │
│          │  └──────────┘  └────────────┘  │  (Tracing)  │  │      │
│          │                                └─────────────┘  │      │
│          │  ┌──────────┐  ┌────────────┐                   │      │
│          │  │ Tavily   │  │ Rate DB    │                   │      │
│          │  │ Search   │  │ (SQLite)   │                   │      │
│          │  └──────────┘  └────────────┘                   │      │
│          └─────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Agent Architecture

### Framework: LangGraph

We use **LangGraph** to build a stateful, multi-agent graph. The orchestrator (planner) decides which specialist agents to invoke based on user intent, and the graph manages state transitions and conditional routing.

### Agent Graph Flow

```
START
  │
  ▼
[Planner Node]
  │  Understands user intent
  │  Checks memory for cached data
  │  Decides which agents to invoke
  │
  ├── "fetch_fuel" ────► [Fuel Agent Node]
  │                        Calls: fetch_fuel_price tool
  │                        Returns: price, baseline, delta%, trend
  │
  ├── "fetch_route" ───► [Route Agent Node]
  │                        Calls: calculate_route tool
  │                        Returns: distance_km, traffic_severity, zone
  │
  ├── "calculate_price" ► [Pricing Agent Node]
  │                        Calls: lookup_rate + calculate_surcharge tools
  │                        Returns: base_rate, surcharge_pct, total, breakdown
  │
  ├── "search_context" ─► [Fuel Agent Node]
  │                        Calls: search_fuel_news tool
  │                        Returns: news/context about fuel trends
  │
  └── "clarify" ────────► [Response Node]
  │                        Asks user for missing information
  │
  ▼
[Response Node]
  │  Formats final answer with reasoning trace
  │  Includes surcharge breakdown table
  │  Adds business recommendations when relevant
  ▼
END
```

### Agent State

```python
class AgentState(TypedDict):
    messages: list[BaseMessage]           # Full conversation history
    fuel_data: dict | None                # Current fuel price + baseline + delta
    route_data: dict | None               # Origin, destination, distance, traffic, zone
    shipping_type: str | None             # "bounce" | "retail_standard" | "retail_fast"
    weight_kg: float | None               # Shipment weight
    surcharge_result: dict | None         # Base rate, surcharge %, amount, total
    reasoning_trace: list[dict]           # Agent steps for transparency panel
    next_step: str                        # Conditional edge routing
```

### Conditional Routing

The Planner node outputs a `next_step` field that LangGraph uses for conditional edges:

| next_step | Target Node | When |
|-----------|------------|------|
| `fetch_fuel` | Fuel Agent | No fuel data in state, or data > 1 hour old |
| `fetch_route` | Route Agent | New origin/destination pair |
| `calculate_price` | Pricing Agent | Fuel + route data available, ready to compute |
| `search_context` | Fuel Agent (search mode) | User asks about trends or news |
| `clarify` | Response Node | Missing required info (shipping type, route, etc.) |
| `respond` | Response Node | All data collected, ready to answer |

---

## Tools

### 1. Fuel Price Tool (`fetch_fuel_price`)

- **Source**: EPPO (Department of Energy Business, Thailand) or PTT
- **Input**: `fuel_type` (diesel_b7, gasohol_95, etc.), `region` (central)
- **Output**: `{price: float, date: str, unit: "THB/L", source: str}`
- **Fallback**: If API fails, reads latest row from `data/raw/eppo_diesel_prices.csv`

### 2. Route Calculator Tool (`calculate_route`)

- **Source**: Google Maps Directions API
- **Input**: `origin` (e.g., "Bangkok"), `destination` (e.g., "Nonthaburi")
- **Output**: `{distance_km: float, duration_min: int, traffic_severity: int (1-5), zone: str}`
- **Zone mapping**: Based on origin-destination pair → central-1, central-2, or central-3
- **Cache**: Results cached for 15 minutes to reduce API calls

### 3. Rate Table Lookup Tool (`lookup_rate`)

- **Source**: Local SQLite database (`data/express.db`)
- **Input**: `shipping_type`, `zone`, `weight_kg`
- **Output**: `{base_rate: float, currency: "THB", rate_tier: str}`
- **Data**: Express rate table with 3 shipping types, 3 zones, multiple weight tiers

### 4. Surcharge Calculator Tool (`calculate_surcharge`)

- **Source**: Pure calculation (no external API)
- **Input**: `base_rate`, `fuel_delta_pct`, `shipping_type`, `traffic_severity`
- **Output**: `{surcharge_pct: float, surcharge_amount: float, total: float, capped: bool}`
- **Logic**: See Surcharge Logic section below

### 5. Web Search Tool (`search_fuel_news`)

- **Source**: Tavily Search API
- **Input**: `query` (e.g., "Thailand diesel price forecast")
- **Output**: `{results: [{title, snippet, url}]}`
- **Purpose**: Provides context for reasoning transparency — the agent can cite why prices are moving

---

## Surcharge Calculation Logic

```
baseline_diesel = 29.94 THB/L (configurable via env)
current_diesel = <from fuel_price tool>
fuel_delta_pct = (current - baseline) / baseline

Shipping Type Multipliers:
  bounce:           1.0  (fully exposed to fuel cost)
  retail_fast:      0.8  (high exposure, dedicated routes)
  retail_standard:  0.5  (partially absorbed, batched shipments)

surcharge_pct = fuel_delta_pct * multiplier[shipping_type]

Traffic Adjustment (Bounce only):
  surcharge_pct += traffic_severity * 0.02  (2% per severity level, 1-5 scale)

Caps:
  Maximum: 15% (configurable via env)
  Minimum: -5% (discount when fuel drops)
```

---

## Memory Management

### Session Memory (LangGraph Checkpointer)

- **Backend**: SQLite file (`data/checkpoints.db`)
- **Key**: `thread_id` (UUID assigned per conversation)
- **What it stores**: Full message history + agent state per conversation thread
- **Enables**:
  - Follow-up questions reuse cached fuel/route data
  - "What about Retail Fast?" works without re-fetching
  - "What if diesel goes up 2 baht?" uses existing context

### Tool Result Cache (in AgentState)

- `fuel_data` persists across conversation turns (TTL: 1 hour)
- `route_data` persists across turns (invalidated when origin/destination changes)
- Planner checks state before re-invoking tools to save API calls

### Conversation Management

- `GET /api/conversations` — list all past conversations
- `GET /api/conversations/:id` — resume a conversation
- Frontend shows conversation sidebar for history

---

## Observability & Evaluation (Langfuse)

### Integration

Every LangGraph invocation passes a Langfuse callback handler that automatically traces:

- **LLM calls**: model, tokens, latency, prompt/completion
- **Tool calls**: tool name, input, output, duration
- **Agent steps**: which agent ran, what it decided, why
- **User feedback**: thumbs up/down from the UI, mapped to Langfuse scores

### Evaluation Strategy

| Type | Method | Frequency |
|------|--------|-----------|
| Formula Accuracy | Auto-eval: independent calculation vs agent output | Every query |
| Tool Success | Check tool outputs for errors/empty results | Every query |
| Response Quality | User thumbs up/down via UI | User-triggered |
| Latency | Langfuse auto-tracking (target: < 10s) | Every query |
| Reasoning Coherence | Manual review via Langfuse dashboard | Weekly |

### User Feedback Flow

1. User sees surcharge recommendation in chat
2. Clicks thumbs up/down on the response
3. If thumbs down: selects reason (wrong price, wrong route, etc.)
4. Feedback sent to `POST /api/feedback` → forwarded to Langfuse Score API
5. Scores visible in Langfuse dashboard for analysis

---

## Data Pipeline

### Ingestion

| Script | Source | Output | Frequency |
|--------|--------|--------|-----------|
| `fetch_fuel_prices.py` | EPPO website/API | `data/raw/eppo_diesel_prices.csv` | Daily |
| `generate_rate_table.py` | Simulated (assumptions documented) | `data/raw/express_rate_table.csv` | Once |
| `seed_database.py` | CSVs above | `data/express.db` (SQLite) | After CSV update |

### Runtime Data Flow

1. **Live fuel price** → fetched by Fuel Agent via `fetch_fuel_price` tool
   - Falls back to latest CSV row if API is unavailable
2. **Rate table** → queried from SQLite by `lookup_rate` tool
3. **Route data** → fetched live from Google Maps by `calculate_route` tool
   - Cached for 15 minutes

### Zone Definitions

| Zone | Coverage | Example Areas |
|------|----------|--------------|
| central-1 | Bangkok inner + adjacent provinces | Bangrak, Sathorn, Nonthaburi Muang, Pak Kret |
| central-2 | Bangkok outer + near provinces | Pathum Thani, Samut Prakan, Bang Phli |
| central-3 | Extended central region | Nakhon Pathom, Samut Sakhon, Ayutthaya |

---

## Error Handling

### Tool Failure
- **Retry**: Up to 2 retries with exponential backoff
- **Fallback**: Use cached/CSV data with warning in reasoning trace
- **Graceful**: Explain to user what failed and what data was used instead

### LLM Failure
- **Retry**: 1 retry after 2 seconds
- **Fallback**: Return partial result with explanation

### Invalid User Input
- Agent asks for clarification via the `clarify` routing path
- Suggests example queries to guide the user

### Surcharge Out of Bounds
- Cap/floor applied automatically
- Agent flags when cap is hit and recommends cap review

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/chat` | Send message, receive SSE stream of traces + response |
| GET | `/api/conversations` | List all past conversations |
| GET | `/api/conversations/:id` | Get conversation history |
| GET | `/api/fuel-prices?days=30` | Get historical fuel price data for chart |
| POST | `/api/feedback` | Submit user feedback (score + reason) |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | LangGraph |
| LLM | Google Gemini 2.0 Flash (free tier) |
| Backend | FastAPI + Uvicorn |
| Frontend | Next.js 15 + React 19 + Tailwind CSS |
| Database | SQLite (rate tables + conversation checkpoints) |
| Observability | Langfuse (tracing + evaluation) |
| Fuel Data | EPPO / PTT |
| Routing | Google Maps Directions API |
| Search | Tavily Search API |
| Charts | Recharts |

---

## Shipping Types

| Type | Customer | Pricing Model | Fuel Sensitivity | Use Case |
|------|----------|--------------|-----------------|----------|
| Bounce | B2B | Weight + distance | High (1.0x multiplier) | Bulk shipments, 50-1000kg |
| Retail Standard | B2C | Zone-based flat rate | Medium (0.5x multiplier) | Consumer parcels, 3-5 day delivery |
| Retail Fast | B2C | Premium flat rate | High (0.8x multiplier) | Same/next-day delivery |
