# Phase 3: Graph Assembly & API Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 03-graph-assembly-api-layer
**Areas discussed:** Planner design, Output & SSE contract, Memory & cache invalidation, Retry loop topology

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Planner design (ORCH-01) | LLM extraction approach, AgentState extensions, clarify-path triggers | ✓ |
| Output & SSE contract (ORCH-05 + API-01) | Response shape, event granularity, thread_id flow | ✓ |
| Memory & cache invalidation (ORCH-10) | Checkpointer, cache reuse policy, TTL tracking | ✓ |
| Retry loop topology (ORCH-08) | Graph-level retry vs node-level, fallback edges | ✓ |

**User's choice:** All four areas selected.

---

## Planner design (ORCH-01)

### Q1: How should the Planner extract intent + fields from user messages?

| Option | Description | Selected |
|--------|-------------|----------|
| Single structured-output call | One Gemini call returns Pydantic schema {intent, shipping_type?, weight_kg?, origin?, destination?, missing_fields[], next_step}. Mirrors Phase 2 D-09 pattern; D-11 fallback applies. | ✓ |
| LLM tool-calling | Gemini decides which agent to invoke via function-calling. More agentic, but harder to test and reliability variable on free tier. | |
| Hybrid regex + LLM | Regex pre-extracts obvious fields, LLM fills gaps + classifies intent. Cheaper but two paths to maintain. | |

**User's choice:** Single structured-output call (Recommended).

### Q2: What routing pattern should the graph use?

| Option | Description | Selected |
|--------|-------------|----------|
| Planner-loop | Planner runs first → routes to specialist → control returns to Planner → next next_step. Loops until next_step='respond'. Supports cache-aware skipping. | ✓ |
| Fixed pipeline | Planner fans out to fuel → route → price → respond every time. Simpler but can't skip cached steps. | |
| Up-front plan | Planner outputs full agent sequence, executor walks it. Explicit but rigid. | |

**User's choice:** Planner-loop (Recommended).

### Q3: Where should the new fields (origin, destination, intent) live on AgentState?

| Option | Description | Selected |
|--------|-------------|----------|
| Flat additions to TypedDict | Add origin, destination, user_intent, missing_fields directly on AgentState. Matches existing Phase 2 pattern. | ✓ |
| Nested 'extracted' dict | state['extracted'] = {origin, destination, intent, ...}. Groups planner output but breaks D-10 contract from Phase 2. | |
| Separate PlannerOutput model | Pydantic PlannerOutput stored on state.planner_output. Most type-safe but requires every consumer to know about the model. | |

**User's choice:** Flat additions to TypedDict (Recommended).

### Q4: How should the clarify path produce its message to the user?

| Option | Description | Selected |
|--------|-------------|----------|
| Planner sets reason, Response Node renders | Planner sets next_step='clarify' + state.clarification_reason. Response Node renders the user-facing message. Single output path. | ✓ |
| Planner writes message directly | Planner composes the clarification text itself, Response Node passes through. Two places generate user-facing text. | |
| Static template per missing-field | Lookup table per missing field. Deterministic, zero LLM cost, but loses conversational tone. | |

**User's choice:** Planner sets reason, Response Node renders (Recommended).

---

## Output & SSE contract (ORCH-05 + API-01)

### Q1: What level of granularity should /api/chat stream over SSE?

| Option | Description | Selected |
|--------|-------------|----------|
| Live trace events + final answer | Each new reasoning_trace entry emits an SSE event as soon as the node finishes; final 'answer' event closes the stream. Maximises 'visible reasoning' grading value. | ✓ |
| Token-level streaming + trace events | Stream Gemini's response tokens as they arrive PLUS trace events. Best UX but adds complexity and tightens Gemini free-tier coupling. | |
| Final answer + full trace blob | Single SSE event at the end with {answer, reasoning_trace}. Simplest but loses the 'watching the agent think' demo moment. | |

**User's choice:** Live trace events + final answer (Recommended).

### Q2: What shape should each SSE event take?

| Option | Description | Selected |
|--------|-------------|----------|
| Typed JSON envelope | data: {"type":..., "payload":{...}}. Frontend dispatches by type. | ✓ |
| SSE 'event:' field per type | Use SSE protocol's named-event mechanism. Native to spec but requires per-type listeners on frontend. | |
| Plain JSON lines | Each event is a raw JSON object; client infers type from keys. Smallest, but loose contract. | |

**User's choice:** Typed JSON envelope (Recommended).

### Q3: How does thread_id flow between client and server?

| Option | Description | Selected |
|--------|-------------|----------|
| Client-supplied UUID, server creates on first use | Client sends thread_id in POST body; if missing, server generates UUID and returns in first SSE event. | ✓ |
| Server-issued only | Server always generates thread_id and returns via response header. Simpler but harder to test. | |
| Client-required | Client must supply thread_id. Cleanest contract but frontend must know to generate. | |

**User's choice:** Client-supplied UUID, server creates on first use (Recommended).

### Q4: What should the Response Node final answer contain?

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown + structured surcharge_result | Response payload: {markdown, surcharge_result, capped}. Frontend renders markdown; structured object available for charts. | ✓ |
| Pure markdown | Just a markdown string. Simplest but Phase 4 dashboard can't pull surcharge values without re-parsing. | |
| Structured-only | Only structured fields. Frontend builds the table. Most flexible but Response Node loses control of presentation. | |

**User's choice:** Markdown + structured surcharge_result (Recommended).

---

## Memory & cache invalidation (ORCH-10)

### Q1: Which LangGraph checkpointer should we use?

| Option | Description | Selected |
|--------|-------------|----------|
| AsyncSqliteSaver | FastAPI handlers are async; matches the runtime. Avoids sync-in-async deadlocks under load. | ✓ |
| SqliteSaver (sync) | Standard sync checkpointer wrapped via run_in_threadpool. Every chat request blocks a thread on every checkpoint write. | |
| MemorySaver | In-memory only. Loses all conversations on restart. Wrong for ORCH-10 + GET /api/conversations. | |

**User's choice:** AsyncSqliteSaver (Recommended).

### Q2: Should the compiled graph be a singleton or per-request?

| Option | Description | Selected |
|--------|-------------|----------|
| Singleton compiled at app startup | FastAPI lifespan event compiles the StateGraph once. Standard LangGraph pattern. | ✓ |
| Per-request compile | Compile inside the chat handler each time. Wasteful re-binding. | |
| Per-thread cached compile | Cache compiled graphs by thread_id. Unnecessary — thread_id only affects checkpointer state. | |

**User's choice:** Singleton compiled at app startup (Recommended).

### Q3: Who decides whether to reuse cached fuel_data / route_data on follow-up turns?

| Option | Description | Selected |
|--------|-------------|----------|
| Planner inspects state freshness | Planner reads state.fuel_data + fetched_at vs TTL. Emits next_step accordingly. | ✓ |
| Conditional edges short-circuit | Edges from START check state directly. Decouples from Planner but spreads cache logic. | |
| Specialist agents self-skip | Fuel/Route nodes check freshness inside themselves; return early if cached. | |

**User's choice:** Planner inspects state freshness (Recommended).

### Q4: How are TTL/invalidation rules tracked?

| Option | Description | Selected |
|--------|-------------|----------|
| Timestamps on state objects | Add fetched_at: ISO-8601 string to fuel_data and route_data. Planner compares against datetime.now() with TTL constants in config. | ✓ |
| Step-counter staleness | Each AgentState has a turn counter; fuel_data stale after N turns. Approximate, no clock dependency. | |
| Re-fetch every turn | Don't cache across turns at all. Defeats the purpose of ORCH-10. | |

**User's choice:** Timestamps on state objects (Recommended).

---

## Retry loop topology (ORCH-08)

### Q1: What does ORCH-08 mean in Phase 3, given Phase 2 already has in-tool retries?

| Option | Description | Selected |
|--------|-------------|----------|
| LangGraph node-level RetryPolicy + graceful-fallback edges | Wrap each agent node with RetryPolicy(max_attempts=2, backoff=2.0). On final failure, error edge routes to Response Node with partial-result message. | ✓ |
| Agentic adaptive retry (Planner re-routes) | On node failure, set state.last_error; Planner sees it and decides recovery. Most agentic, highest grading value, significant prompt complexity. | |
| Strip in-tool retry, do everything graph-level | Move all retry logic out of tools into the graph. Cleaner but breaks Phase 2 D-04 contract. | |

**User's choice:** LangGraph node-level RetryPolicy + graceful-fallback edges (Recommended).

### Q2: Where does a node go after retries are exhausted?

| Option | Description | Selected |
|--------|-------------|----------|
| Always to Response Node with partial state | Failed node sets state.errors[] entry; routing falls through to Response Node with 'Could not complete X' message. | ✓ |
| Route to Planner for adaptive recovery | Failed node bumps next_step='replan'; Planner decides recovery. More flexible, more LLM cost. | |
| Hard-fail the request (HTTP error) | Surface exception out of graph; FastAPI returns 5xx. Loses 'graceful fallback with explanation'. | |

**User's choice:** Always to Response Node with partial state (Recommended).

### Q3: Which exceptions should trigger graph-level retry?

| Option | Description | Selected |
|--------|-------------|----------|
| Transient only — network/timeout/quota | RetryPolicy retries httpx.HTTPError, asyncio.TimeoutError, google.api_core.exceptions.ResourceExhausted. Skip ValueError (clarify-path). Skip generic Exception. | ✓ |
| Everything except ValueError | Retry any Exception that isn't ValueError. Broader safety net but masks bugs and burns Gemini quota. | |
| Only Gemini quota errors | Retry only on 15-RPM rate-limit errors. Doesn't help with Google Maps / EPPO failures. | |

**User's choice:** Transient only — network/timeout/quota (Recommended).

### Q4: What backoff schedule for the graph-level retry?

| Option | Description | Selected |
|--------|-------------|----------|
| Exponential: 1s, 2s, then fail | max_attempts=2 retries (3 total tries), backoff_factor=2.0, initial_interval=1s. Worst-case ~3s. Aligns with ORCH-08 wording. | ✓ |
| Linear: 2s, 2s, then fail | Fixed 2s between retries. Predictable but slower and doesn't match 'exponential' wording. | |
| Aggressive: 0.5s, 1s, 2s, then fail | 3 retries with shorter floor. Maximises recovery but 4 LLM calls in worst case is risky on 15-RPM. | |

**User's choice:** Exponential: 1s, 2s, then fail (Recommended).

---

## Claude's Discretion

Areas where Claude has flexibility during planning/implementation:
- Exact module split for the Planner (single file vs `planner/` package).
- Format of the Planner system prompt (still must produce structured output parseable to PlannerOutput).
- Internal layout of FastAPI app (single main.py with included routers vs split per-endpoint files).
- pandas vs csv-stdlib for `GET /api/fuel-prices` parsing.
- Exact Pydantic field names for `PlannerOutput`.
- Whether Response Node uses Gemini for prose summary or a deterministic template.

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section:
- ORCH-07 (parallel Fuel+Route via Send API) — Phase 5
- ORCH-09 (HITL approval gate) — Phase 5
- TOOL-05 (Tavily search) — Phase 5
- API-05 (feedback) + Langfuse OBS-01..03 — Phase 5
- Token-level streaming — out of scope (low marginal value)
- Conversation deletion/archive — out of scope for v1
- Adaptive replan-on-error — deferred to Phase 5+
