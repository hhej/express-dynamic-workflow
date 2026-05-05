# Feature Landscape

**Domain:** Agentic AI Logistics Surcharge Orchestrator (MADT7204 Course Project)
**Researched:** 2026-04-04
**Confidence:** MEDIUM (based on training data knowledge of LangGraph, logistics systems, and agentic AI patterns; WebSearch unavailable for verification)

---

## Table Stakes

Features that must exist or the project fails to demonstrate "agentic AI" and loses marks on the 35% Agent Architecture criterion. These are non-negotiable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Multi-agent orchestration** | Core of the 35% grading criterion. Planner + 3 specialist agents (Fuel, Route, Pricing) via LangGraph graph. Without this, it is a script, not an agent. | High | LangGraph StateGraph with conditional edges. This IS the product. |
| **Live fuel price fetch** | 20% grading on Data Integration. Must query real EPPO/PTT data, not hardcoded values. | Medium | Tool: `fetch_fuel_price`. Real external API call is what makes this "data integration." |
| **Surcharge calculation with formula** | The core business logic. Without a transparent, auditable formula, there is no product value. | Low | Pure math: `fuel_delta_pct * multiplier[shipping_type]` with caps/floors. Already well-specified. |
| **3 shipping types with distinct multipliers** | Demonstrates the agent handles conditional business logic, not just one path. | Low | Bounce (1.0x), Retail Standard (0.5x), Retail Fast (0.8x). Trivial once schema is set. |
| **Route distance/zone calculation** | Second real data source. Demonstrates multi-source data integration. | Medium | Google Maps API with zone mapping. 15-min cache to manage API budget. |
| **Rate table lookup from SQLite** | Third data source. Shows structured data integration alongside APIs. | Low | Simple SQL query by shipping_type + zone + weight_tier. |
| **Chat-based natural language interface** | The "agentic" part means users interact via conversation, not forms. A form-based UI is not an agent. | Medium | SSE streaming from FastAPI to Next.js. User types "What's the surcharge for 50kg Bounce from Bangkok to Ayutthaya?" |
| **Reasoning trace visibility** | What separates "agentic" from "automated." Graders must SEE the agent's decision chain. | Medium | Each agent step logged to `reasoning_trace` in state, rendered in UI panel. Critical for the 35% criterion. |
| **Structured output (Pydantic models)** | Deterministic, testable agent responses. Shows engineering rigor over "vibes." | Low | Pydantic BaseModel for each tool's input/output. LangGraph supports this natively. |
| **Data pipeline scripts** | Graded under Data Integration (20%). Must have reproducible data ingestion. | Low | `fetch_fuel_prices.py`, `generate_rate_table.py`, `seed_database.py`. Run once to populate. |
| **Conversation memory (checkpointer)** | Explicit bonus mark category. Follow-up queries ("now try Retail Fast") must work without re-asking everything. | Medium | LangGraph SqliteSaver. Thread-based state persistence. |
| **Error handling with graceful degradation** | Agent must not crash on API failure. Shows production-readiness thinking. | Medium | Retry + fallback chain. If EPPO fails, try cached CSV. Always explain what happened. |

---

## Differentiators

Features that earn bonus marks, impress graders, and demonstrate depth beyond minimum requirements. These are what separate an A from a B+.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Parallel agent execution (LangGraph Send API)** | Fuel + Route agents are independent, so running them in parallel shows sophisticated graph design. Explicit bonus mark territory (multi-agent pattern). | Medium | Use `Send()` to fan out, then join at Pricing Agent. Saves wall-clock time and demonstrates LangGraph mastery. |
| **Agentic retry loop with backoff** | Explicit bonus mark category. Agent autonomously retries failed tools, not the user. Shows the agent has agency over its own failure recovery. | Medium | Exponential backoff (1s, 2s, 4s). Max 2 retries per tool. Falls back gracefully with explanation. |
| **Human-in-the-loop approval gate** | Shows agent safety patterns. For high-value shipments (e.g., >500kg Bounce), pause and ask for human approval before finalizing surcharge. | Medium | LangGraph interrupt mechanism. Demonstrates responsible AI design. |
| **Tavily web search for fuel news context** | RAG-adjacent feature (bonus mark category). Agent can cite WHY diesel is up, not just THAT it is up. Adds reasoning depth. | Low | Tavily API call, results injected into agent context for trend analysis. |
| **Langfuse observability + evaluation** | Production-grade tracing. Graders can see every LLM call, token count, latency. Shows AI engineering maturity. | Medium | Langfuse callback handler on LangGraph. Auto-traces everything. Evaluation scores from user feedback. |
| **User feedback loop (thumbs up/down)** | Closes the feedback loop. Shows the system can learn/improve, not just output. Feeds into Langfuse scores. | Low | UI button -> POST /api/feedback -> Langfuse Score API. Simple but demonstrates evaluation thinking. |
| **Dashboard with surcharge trends (Recharts)** | Visual storytelling for management audience. Shows surcharge history across routes/types/time. Grading includes "management transparency." | Medium | GET /api/fuel-prices endpoint + Recharts line/bar charts. Time-series fuel prices + surcharge trends. |
| **Multi-level fuel fallback chain** | API -> scrape -> cached CSV -> last-known-good. Shows resilience engineering. More impressive than a single API call. | Medium | 4-level fallback with source attribution in reasoning trace ("Used cached data from 2 hours ago because EPPO API returned 503"). |
| **What-if scenario queries** | "What if diesel goes up 2 baht?" without re-fetching. Uses conversation memory to modify parameters. Shows the agent reasons, not just fetches. | Low | Planner detects hypothetical intent, overrides `fuel_data.price` in state, re-runs Pricing Agent only. |
| **Conversation history sidebar** | Shows memory persistence across sessions. Graders can see past queries, resume threads. | Low | GET /api/conversations + simple list UI. Thread management. |

---

## Anti-Features

Features to deliberately NOT build. These waste time, add complexity without grading value, or violate project constraints.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Admin CRUD for rate tables** | Explicitly out of scope in PROJECT.md. Zero grading value. Rate tables are seeded via scripts. Building a rate table editor is a CRUD trap that steals time from agent work. | Seed via `generate_rate_table.py` + `seed_database.py`. Document the schema. |
| **User authentication / OAuth** | Explicitly out of scope. Not relevant to agent architecture grading. Adds significant complexity for zero marks. | Skip entirely. No login, no users, no sessions beyond conversation threads. |
| **Multi-region support** | Scope creep. Central Region is sufficient to demonstrate the architecture. Adding regions multiplies test cases without adding architectural depth. | Hardcode Central Region zones. Document that the architecture supports extension. |
| **Production deployment (Docker/K8s)** | Grading requires local reproducibility, not production infra. Docker adds setup friction for graders. | `pip install` + `npm install` + clear README. Maybe a single `docker-compose.yml` if trivial, but not required. |
| **Real-time webhook notifications** | Overkill for a demo. SSE streaming already shows real-time capability. Webhooks require a subscriber system. | SSE for chat streaming is sufficient. |
| **Mobile native app** | Web-first is specified. A mobile app is months of work for no grading value. | Responsive Tailwind CSS design. Works on mobile browsers if needed. |
| **Fine-tuning or custom model training** | Gemini Flash free tier does not support fine-tuning. Prompt engineering is the correct approach for this scope. | Well-crafted system prompts for each agent role. Few-shot examples in prompts if needed. |
| **Complex RAG with vector store** | Overkill for structured data (rate tables, fuel prices). Vector search adds complexity without value when your data is tabular. Tavily search already covers the "RAG-adjacent" bonus mark. | SQLite for structured lookup. Tavily for unstructured web context. This combination is more appropriate than embedding fuel price CSVs. |
| **Autonomous agent loops without bounds** | Unbounded agent loops are dangerous and waste API credits. The agent should be goal-directed with clear termination. | Max iteration count on the graph (e.g., 10 steps). Clear termination conditions. Human-in-the-loop as safety valve. |
| **Elaborate visualization / Grafana dashboards** | Overengineering the monitoring layer. Langfuse is already the observability answer. Adding Grafana, Prometheus, etc. is infra work, not agent work. | Langfuse for tracing. Simple Recharts dashboard for business metrics. |

---

## Feature Dependencies

```
Data Pipeline Scripts
  |
  v
SQLite Database (rate tables populated)
  |
  v
Rate Table Lookup Tool ----+
                           |
Fuel Price Tool -----------+---> Surcharge Calculator Tool
  |                        |
  v                        |
Fuel Fallback Chain        |
                           |
Route Calculator Tool -----+
  |
  v
Zone Mapping Logic

Surcharge Calculator Tool
  |
  v
Planner Agent (orchestrates all above)
  |
  +---> Reasoning Trace ---------> Trace Panel UI
  |
  +---> Chat Response ------------> Chat UI (SSE)
  |
  +---> Langfuse Callbacks -------> Observability
  |
  +---> Conversation Memory ------> History Sidebar

Human-in-the-loop Gate (depends on: Planner + Surcharge Calculator)
Tavily Search (independent, invoked by Planner on "search_context" routing)
Dashboard Charts (depends on: /api/fuel-prices endpoint + historical data)
User Feedback (depends on: Chat UI + Langfuse integration)
```

### Critical Path

The critical path to a working demo is:
1. Data pipeline (seed DB) -- unblocks everything
2. Tool implementations (fuel, route, rate lookup, surcharge calc) -- unblocks agents
3. LangGraph state + Planner agent -- unblocks orchestration
4. Specialist agent nodes wired into graph -- unblocks chat
5. FastAPI /api/chat endpoint with SSE -- unblocks frontend
6. Next.js chat UI with trace panel -- demo-ready

Everything else (dashboard, feedback, human-in-the-loop, Tavily, Langfuse) layers on top of this critical path.

---

## MVP Recommendation

### Phase 1: Build First (Core Agent -- Table Stakes)

Prioritize in this order:
1. **Data pipeline + SQLite seeding** -- fastest, unblocks all tools
2. **Tool implementations** (fuel fetch, route calc, rate lookup, surcharge calc) -- the agent's hands
3. **LangGraph orchestrator** (Planner + conditional routing + state schema) -- the agent's brain
4. **FastAPI /api/chat with SSE** -- the agent's voice
5. **Basic chat UI** with reasoning trace panel -- the agent's face

This gives you a working, demonstrable agent in the shortest time.

### Phase 2: Build Next (Differentiators -- Bonus Marks)

6. **Conversation memory** (SqliteSaver checkpointer) -- bonus mark: memory
7. **Parallel agent execution** (Send API) -- bonus mark: multi-agent sophistication
8. **Agentic retry loop** with fallback chain -- bonus mark: agentic loop
9. **Langfuse integration** -- shows engineering maturity
10. **Human-in-the-loop gate** -- shows responsible AI

### Phase 3: Polish (UI + Analytics)

11. **Dashboard with Recharts** -- management transparency angle
12. **Tavily search for fuel news** -- RAG-adjacent, easy win
13. **User feedback + Langfuse scores** -- closes evaluation loop
14. **Conversation history sidebar** -- nice-to-have, low effort
15. **What-if scenario support** -- impressive but depends on solid memory

### Defer Entirely

- Rate table admin UI
- Auth/login
- Multi-region
- Production deployment
- Vector store RAG

---

## Grading Alignment

| Grading Criterion | Weight | Features That Address It |
|-------------------|--------|--------------------------|
| Agent Architecture & Technical Execution | 35% | Multi-agent orchestration, conditional routing, parallel execution, structured outputs, reasoning trace, retry loop, human-in-the-loop |
| Data Integration | 20% | Live fuel API, Google Maps API, SQLite rate tables, data pipeline scripts, multi-level fallback |
| Technical Documentation & Git Practice | 20% | Architecture doc (exists), clear README, descriptive commits, feature branches |
| AI/Vibe-Coding Tool Leverage | 15% | Using Claude Code for development, documenting AI-assisted workflow |
| Team Technical Leadership | 10% | IT Lead owns codebase, reviews team contributions |

### Bonus Mark Features (all four targeted)

| Bonus Category | Feature | Status |
|----------------|---------|--------|
| Multi-agent | Planner + Fuel + Route + Pricing agents | Planned, table stakes |
| RAG | Tavily web search for fuel news context | Planned, differentiator |
| Memory | LangGraph SqliteSaver checkpointer | Planned, table stakes |
| Agentic retry loop | Exponential backoff + fallback chain | Planned, differentiator |

---

## Sources

- Project architecture document (`docs/architecture.md`) -- primary source for feature specifications
- Project brief (`PROJECT.md`) -- grading criteria, constraints, scope decisions
- LangGraph documentation (training data, MEDIUM confidence) -- Send API, conditional routing, SqliteSaver patterns
- Logistics industry knowledge (training data, MEDIUM confidence) -- fuel surcharge calculation patterns, shipping type differentiation
- Langfuse integration patterns (training data, MEDIUM confidence) -- callback handler approach, score API

**Note:** WebSearch was unavailable during this research session. Feature landscape is derived from project documents (HIGH confidence for project-specific features) and training data knowledge of agentic AI patterns and logistics systems (MEDIUM confidence for industry comparisons). No competitor analysis was possible.
