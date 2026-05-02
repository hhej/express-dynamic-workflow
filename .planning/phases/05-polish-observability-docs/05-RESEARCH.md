# Phase 5: Polish, Observability & Docs - Research

**Researched:** 2026-05-02
**Domain:** Multi-agent orchestration polish — LangGraph parallel + HITL, Langfuse observability, Tavily web search, MADT7204 submission docs
**Confidence:** HIGH (verified primary sources for all four hard problems)

## Summary

Phase 5 layers four advanced agent patterns onto the working Phase 4 system: (1) parallel Fuel + Route execution via LangGraph's conditional fan-out, (2) a native `interrupt()`-based human-in-the-loop gate between Pricing and Response, (3) a Tavily-backed Search Agent gated by intent classification, and (4) a Langfuse `CallbackHandler` that captures every LLM/tool call plus a fire-and-forget formula-accuracy auto-eval Score and a synchronous user-feedback Score. Documentation deliverables (README per DOC-01, architecture.md Mermaid update, data-sources.md, demo.mp4) close the phase and ship as the v1.0 tagged submission.

The hard problems are well-specified by CONTEXT.md decisions D-01 through D-21 — research confirmed every one of those decisions is achievable with the **current** library APIs as of 2026-05 (langgraph 1.1.10, langfuse 4.5.1, tavily-python 0.7.24). The only operational risk is the deterministic Langfuse trace-id pattern: the LangChain CallbackHandler in v3+ requires either pre-seeding `trace_context={"trace_id": ...}` or using `langfuse.create_trace_id(seed=...)` to recover the same id later — both are available and load-bearing for D-16's feedback wire.

**Primary recommendation:** Land work in this order — (1) Wave 0: deps + state fields + config constants + observability stub + .env.example; (2) Langfuse callback wiring (independent, demo-able first); (3) Parallel fan-out from Planner via Send API; (4) Search Agent + Tavily tool; (5) HITL `interrupt()` gate + sixth SSE event + frontend ApprovalCard; (6) Feedback wire + frontend POST swap; (7) Docs + screenshots + demo.mp4 + v1.0 tag.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Parallel agents (ORCH-07)
- **D-01:** Send API fan-out fires ONLY when both `fuel_data` AND `route_data` are missing-or-stale on the current turn. Phase 3 D-12 cache-aware skipping takes precedence — follow-ups with fresh cache run sequentially-skip exactly as today. Trace timestamps on the fresh-thread first turn must visibly overlap; that overlap is the demo evidence for ROADMAP §Phase 5 success criterion 1.
- **D-02:** Parallel branches inherit the existing `operator.add` reducers on `reasoning_trace` and `errors` (Phase 2 Pitfall 1, Phase 3 D-05). `fuel_data` and `route_data` stay scalar dict fields with the default last-write-wins behavior; this is safe because the two branches write disjoint state keys. The plan MUST include an integration test that fans out and asserts the merged state has BOTH `fuel_data` and `route_data` populated. No new reducers introduced.
- **D-03:** Phase 3 D-22/D-23 `RetryPolicy` and `phase3_retry_on` allow-list apply unchanged to both parallel branches. Phase 3 D-24 `_wrap_error_sink` applies unchanged — one branch failing routes that branch's error to `state.errors` while the other branch succeeds; planner sees a partial state on the next loop and clarifies or proceeds.

#### HITL approval gate (ORCH-09)
- **D-04:** Trigger condition is a single env-driven scalar threshold: `surcharge_result.total > HITL_TOTAL_THB_THRESHOLD`. Configurable in `backend/config.py` and `.env.example`. Default value is **Claude's Discretion** — calibrate after inspecting `data/express.db` rate distribution; given Phase 1 rate range 50–698 THB and the 15% cap, ballpark 500–700 THB total to gate ~5–10% of demo queries.
- **D-05:** Gate placement: between `pricing_agent` and `response_node`, implemented via LangGraph's native `interrupt()` primitive (NOT a state flag).
- **D-06:** Gate UX is a new sixth SSE event type. Backend emits `data: {"type":"approval_required","payload":{"surcharge_result": {...}, "thread_id": "..."}}\n\n` immediately before suspending. Frontend renders inline Approve / Deny buttons. Resume via `POST /api/chat` with `{thread_id, approve: true|false}` which calls `graph.ainvoke(Command(resume=...), config)`. Adds `approval_required` as a sixth event alongside Phase 3 D-18's `meta|trace|answer|error|done`.
- **D-07:** New `AgentState` field `approval_decision: Optional[Literal["approve","deny"]]`. On `approve` → graph proceeds to `response_node` with `surcharge_result` intact. On `deny` → `response_node` renders a "User declined the recommended surcharge — review and adjust" prose with `status="partial"`; no surcharge breakdown table.
- **D-08:** Trace step. The gate emits one D-12-shape trace entry (`agent="hitl_gate"`, `tool="interrupt"`). After resume, a second trace entry records `decision: "approve"|"deny"`. Phase 4 D-08's "trace panel = current-turn only" is preserved — the resume request emits its own fresh trace stream.

#### Tavily search (TOOL-05)
- **D-09:** Planner emits `next_step="search_context"` ONLY when its `user_intent` classifier identifies a news/market/trend question. Standard `surcharge_query` and `followup_query` paths NEVER trigger search by default.
- **D-10:** New dedicated Search Agent node at `backend/agent/nodes/search_agent.py`, mirroring the Phase 2 Fuel/Route narration pattern. Phase 5 re-routes `search_context` from response stub to `search_agent` and adds `search_agent → planner` per Phase 3 D-03 loop.
- **D-11:** Search effect = reasoning context only, never a formula input. Tavily output lands in `AgentState.search_context: Optional[Dict]` shaped `{query, summary, sources: [{title, url, snippet, published_at}], fetched_at}`. Search Agent narrates a 1–2 sentence "market context" line; `response_node` prepends it ABOVE the prose summary in the markdown answer when present.
- **D-12:** Tavily client wraps `backend/agent/tools/_cache.py::TTLCache` keyed on the normalized query string, default 30 min (`SEARCH_CACHE_TTL_SECONDS=1800`). On Tavily API error or rate-limit: trace entry `status="warn"`, `search_context` stays `None`, planner continues. Search failure NEVER blocks the surcharge response.

#### Langfuse observability (OBS-01..03)
- **D-13:** Deployment is Langfuse Cloud free tier (`https://cloud.langfuse.com`). Three new env vars in `.env.example`: `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`. The agent MUST run identically without keys (graceful no-op).
- **D-14:** Trace coverage = single `langfuse.langchain.CallbackHandler` registered at the `graph.compile()` boundary inside `backend/agent/graph.py` (or at the chat-handler invocation — exact insertion point is planner's call). One Langfuse trace per chat turn, named `chat_turn_{thread_id}_{turn_idx}` so the feedback wire (D-16) can resolve `trace_id` deterministically.
- **D-15:** OBS-03 formula-accuracy auto-eval. After `pricing_agent` completes, run `calculate_surcharge` (Phase 1 pure function imported directly from `backend/agent/tools/calculate_surcharge.py`, NOT via the `@tool` wrapper) with the same inputs. Compare against the agent's `surcharge_result` within float tolerance (1e-6). Attach a Score: `name="formula_accuracy"`, `value=1.0` on match else `0.0` with a `reason` string. Score posting MUST be fire-and-forget.
- **D-16:** API-05 feedback wire. New `backend/api/routes/feedback.py` exposes `POST /api/feedback` accepting `{thread_id, message_id, score, reason?}` matching Phase 4 D-17 localStorage payload shape verbatim. Resolves the matching Langfuse trace via the deterministic name from D-14; calls `langfuse.create_score(trace_id=..., name="user_feedback", value=1|-1, comment=reason)`. Returns 200 immediately — synchronous.

#### Documentation & v1.0 submission (DOC-01/02/04)
- **D-17:** README scope per DOC-01 verbatim: project overview → team → problem statement → agent design (with Mermaid diagram + brief prose) → data sources (link to `docs/data-sources.md`) → setup instructions → AI tools used → limitations → license. README copy uses "Bangkok Metro" everywhere.
- **D-18:** `docs/architecture.md` diagram style = Mermaid + keep current ASCII as fallback. Add Mermaid `flowchart` for the graph topology including Phase 5 parallel branches and HITL gate, `sequenceDiagram` for the SSE event flow including the new `approval_required` event, and a `flowchart` showing the Langfuse callback boundary. Conditional Routing table, AgentState schema, Memory Management, and Error Handling sections must be updated.
- **D-19:** Data source documentation lives in `docs/data-sources.md` (new file). Sections: EPPO source URL + scrape/download mechanics + refresh cadence; `generate_rate_table.py` simulation assumptions; Google Maps Directions API usage + 15-min cache; Tavily search query template + 30-min cache.
- **D-20:** Demo artifact = static screenshots embedded in README + a 1–2 minute screen recording at `docs/demo.mp4`. Recording shows fresh-thread surcharge query end-to-end including parallel trace timestamps and HITL approval.
- **D-21:** v1.0 git tag protocol. After all DOC-* are merged on `develop`: merge `develop → main`, tag `v1.0` on the merge commit (annotated tag with submission deliverables checklist).

### Claude's Discretion
- Exact `HITL_TOTAL_THB_THRESHOLD` default value — calibrate to gate ~5–10% of demo queries.
- Module split for the Search Agent (single file vs. package).
- Tavily SDK choice — official `tavily-python` vs raw httpx.
- Mermaid diagram fidelity — must show parallel branches, HITL gate, search agent, Langfuse callback boundary; level of detail beyond that is open.
- Demo recording tool (QuickTime, Loom, OBS).
- Plan ordering across the four sub-domains.
- Inline UI affordance for the HITL prompt (dedicated `ApprovalCard.tsx` vs. inline buttons inside `MessageList.tsx`).
- Whether `response_node` deny path includes the original surcharge_result as a "Show declined recommendation" debug affordance.
- Exact prompt-engineering for the Tavily query construction.

### Deferred Ideas (OUT OF SCOPE)
- Multi-region beyond Bangkok Metro (V2-02)
- What-if scenario queries (V2-01)
- Rate table versioning for historical surcharge accuracy (V2-03)
- Batch surcharge calculation (V2-04)
- Email / scheduled surcharge reports (V2-05)
- Past-turn trace inspection (Phase 4 D-08 deferred)
- Backend `/api/surcharge-history` endpoint
- Theme toggle (light / dark)
- Internationalization (Thai locale)
- Conversation deletion / archive
- HITL approval timeout / auto-escalation
- Tavily prompt-engineering tuning beyond a basic query template
- Self-hosted Langfuse migration
- Background-task or batch-flush feedback wire
- Trace-only Tavily output (no user-facing surface)
- Influencing baseline diesel price from Tavily news
- Auto-augment search on every surcharge query
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORCH-07 | Fuel Agent and Route Agent execute in parallel via LangGraph Send API | "LangGraph Parallel Execution" section — `add_conditional_edges` returning `["fuel_agent","route_agent"]` triggers same-superstep parallel scheduling; `operator.add` reducer on `reasoning_trace`/`errors` already supports concurrent appends (state.py L35, L61) |
| ORCH-09 | Human-in-the-loop approval gate for high-value shipments | "LangGraph HITL via interrupt()" section — `langgraph.types.interrupt()` pauses execution, AsyncSqliteSaver (already wired in main.py L33) snapshots state, resume via `Command(resume=...)` through second `POST /api/chat` |
| TOOL-05 | search_fuel_news tool searches fuel trends via Tavily API | "Tavily Search Tool" section — `tavily-python` 0.7.24 client.search() with topic="news", wrapped in TTLCache (already exists at `backend/agent/tools/_cache.py`), graceful warn on failure |
| API-05 | POST /api/feedback forwards to Langfuse Score | "Langfuse Integration" section — deterministic trace_id via `langfuse.create_trace_id(seed=f"chat_turn_{thread_id}_{turn_idx}")` enables backend feedback handler to score same trace |
| OBS-01 | Langfuse callback handler traces all LLM/tool/agent steps | "Langfuse Integration" section — single `langfuse.langchain.CallbackHandler` attached at chat handler invocation, captures every Gemini call + every `@tool` invocation automatically |
| OBS-02 | User feedback scores forwarded to Langfuse Score API | "Langfuse Integration" section — `langfuse.create_score(trace_id=..., name="user_feedback", value=1\|-1, comment=reason)` |
| OBS-03 | Formula accuracy auto-eval: independent calc vs agent output | "Langfuse Integration" section — re-run `calculate_surcharge()` (the Phase 1 pure function, not the @tool wrapper) post-pricing, post Score `formula_accuracy` 1.0/0.0 fire-and-forget |
| DOC-01 | README covers project overview, team, problem, agent design, data sources, setup, AI tools, limitations | "Documentation Deliverables" section — section template enumerated; Mermaid `flowchart` block embedded for agent design |
| DOC-02 | docs/architecture.md finalized with accurate agent design diagrams | "Documentation Deliverables" section — Mermaid `flowchart` + `sequenceDiagram` patterns ready; existing ASCII art kept as fallback |
| DOC-04 | Data source documentation with URLs, assumptions for simulated data | "Documentation Deliverables" section — section template enumerated for EPPO, generate_rate_table.py assumptions, Google Maps usage, Tavily query template |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

These directives are AUTHORITATIVE — research recommendations conform to them:

- **Free-tier APIs only** — Gemini 2.0 Flash (15 RPM), Google Maps free credit, EPPO public data, Tavily free tier (1000 searches/month), Langfuse Cloud free tier. NO paid model APIs.
- **Python 3.11+** declared, but project venv currently runs **3.9.6** (verified via `.venv/bin/python --version`). Codebase uses `from __future__ import annotations` exactly to support 3.9 compat. Phase 5 MUST preserve this — no Python 3.10+ syntax (e.g., `match` statements, `X | Y` runtime type expressions outside annotations) in new code. **Open question for planner:** decide whether to bump to 3.11 OR continue 3.9-compat. Current pattern says: stay 3.9-compat.
- **Bangkok Metro** phrasing in ALL user-facing copy (README, architecture.md, data-sources.md, demo captions, HITL approval prompt copy, search-context summary). Internal `central-1/2/3` zone IDs are NOT user-facing.
- **Secrets discipline:** `.env` never committed; `.env.example` already lists Phase 5 keys (`TAVILY_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`).
- **Git practice graded at 20%** — descriptive commit messages, feature branches, IT Lead majority commit count. Phase 5 commits must follow `<type>(<scope>): <subject>` convention used in recent commits (`docs(05): capture phase context`).
- **Submission target:** `v1.0` annotated tag on the `main` merge commit per D-21 — the artifact for grading.
- **GSD Workflow Enforcement** — file edits must flow through `/gsd:execute-phase`; no out-of-band edits.
- **Coding conventions:** PEP 8, 88-col, Black, Google-style docstrings, TypedDict + Pydantic; PascalCase.tsx components, useX.ts hooks, camelCase.ts utilities, `*.types.ts`.
- **Snake_case across the wire** — Phase 4 hand-mirrored backend snake_case verbatim into `frontend/types/{api,agent}.types.ts`. Phase 5 additions (`approval_required` event payload, `search_context`, feedback POST body) MUST stay snake_case end-to-end.
- **Pure functions raise `ValueError`; Phase 3 D-23 retry allow-list deliberately excludes ValueError.** Phase 5 MUST NOT add ValueError to the retry allow-list when extending `phase3_retry_on` for Tavily errors.

## Standard Stack

### Core (new additions — Phase 5)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `langfuse` | 4.5.1 (PyPI 2026-04, requires-python `<4.0,>=3.10`) | LLM observability — traces every LLM + tool call from a single CallbackHandler attachment | Officially supported LangChain integration (`langfuse.langchain.CallbackHandler`); free Cloud tier; Python SDK v3+ supports deterministic trace IDs via `create_trace_id(seed=...)` which load-bearing for D-16 feedback wire |
| `tavily-python` | 0.7.24 (PyPI 2026, requires-python >=3.8) | Web search API client — fuel news / market trends | Official Tavily SDK; matches PROJECT.md tech-stack reference; supports `topic="news"` for fuel-specific queries with `published_date`; Pydantic-shaped response (`{query, answer?, results: [{title, url, content, score, published_date}]}`) |

**Python compat note (HIGH confidence):** `langfuse 4.5.1` requires Python `>=3.10`. Project venv is **3.9.6**. **PLANNER MUST DECIDE:** either (a) pin `langfuse < 3.0` (last v2 line — supports 3.9), (b) bump project to 3.10/3.11 (CLAUDE.md already declares 3.11+), or (c) check if a langfuse 3.x LTS line still supports 3.9. Recommend (b): bump to 3.11 — CLAUDE.md says it should already be 3.11+; the 3.9 venv is a Phase 1 lock-in artifact. This unblocks the modern Langfuse v3+ trace_id API which D-16 needs. **Wave 0 task: bump runtime to 3.11 + reinstall venv before adding langfuse.**

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `langgraph` | 1.1.10 (current PyPI; project pinned 0.6.11) | Graph runtime; `interrupt()`, Send API, `Command` all in this version | Already installed at 0.6.11 — verify Send API + `interrupt()` exist on that version (they do; the API is stable since 0.2). NO need to bump for Phase 5 unless test runs surface a v0.6→v1.x divergence |
| `langgraph-checkpoint-sqlite` | 2.0.11 (project pinned) | `AsyncSqliteSaver` — required for `interrupt()` resume across requests | Already wired in `backend/api/main.py` L31–37 |
| `langchain-google-genai` | 2.1.12 (project pinned) | Gemini Flash chat | No change |
| `aiosqlite` | 0.20.0 (project pinned — DO NOT bump) | `AsyncSqliteSaver` connection | Phase 3 lock-in: 0.22.x removed `Connection.is_alive()` that langgraph-checkpoint-sqlite 2.0.11 requires |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `tavily-python` | Raw `httpx` against Tavily REST API | SDK is ~50 lines of httpx wrapping; no heavy transitive deps (httpx already a project dep). SDK gives typed exceptions and matches PROJECT.md reference. **Recommend tavily-python** — D-12 retry allow-list extension cleaner with a named exception class than catch-all httpx errors |
| `langfuse.langchain.CallbackHandler` | Manual `@observe` decorators on each node | CallbackHandler captures the FULL graph (every node + every `@tool` + every Gemini call) automatically without code changes per node. `@observe` requires touching 6 node files and the tool wrappers. **Recommend CallbackHandler** — D-14 already specifies single attachment point |
| Custom feedback queue (background task / RQ / Celery) | Synchronous `langfuse.create_score()` inside `POST /api/feedback` | Synchronous chosen by D-16; backlog explicitly rejected batch-flush. `create_score()` SDK is non-blocking (the SDK batches behind the scenes via OpenTelemetry); a 200 returns in <100ms typical. Stay synchronous |
| Native LangGraph `add_node(..., interrupt_before=True)` static breakpoint | Runtime `interrupt()` inside a guard node | Static `interrupt_before` would pause EVERY pricing→response transition; we only want to gate on `surcharge_result.total > THRESHOLD`. **Recommend runtime `interrupt()`** inside a tiny `hitl_gate_node` placed between pricing and response — guard logic is one `if`, conditional edge handles bypass for low-value queries |

**Installation:**

```bash
# After 3.11 venv bump (see Python compat note above)
.venv/bin/pip install "langfuse==4.5.1" "tavily-python==0.7.24"
```

**Version verification (run at install time):**

```bash
.venv/bin/pip show langfuse tavily-python | grep -E "^(Name|Version)"
# Expected:
#   Name: langfuse        Version: 4.5.1
#   Name: tavily-python   Version: 0.7.24
```

## Architecture Patterns

### Recommended File Touchpoints (Phase 5 EXTENDS, does not rewrite)

```
backend/
├── agent/
│   ├── graph.py                     # EXTEND: parallel fan-out, interrupt(), search_agent edges, Langfuse handler
│   ├── state.py                     # EXTEND: add approval_decision, search_context fields
│   ├── observability.py             # NEW: Langfuse client init + auto-eval helper (D-15) + trace_id seed
│   ├── nodes/
│   │   ├── planner.py               # EXTEND: detect news/trend intent → next_step="search_context"; emit Send fan-out when both fuel+route stale
│   │   ├── hitl_gate.py             # NEW (small): emits trace entry + calls interrupt() when total > threshold
│   │   ├── search_agent.py          # NEW: mirrors fuel_agent — narration + D-11 fallback + 1 trace entry
│   │   └── response_node.py         # EXTEND: read search_context (prepend), read approval_decision (deny path)
│   └── tools/
│       └── search_fuel_news.py      # NEW: Tavily wrapper + TTLCache
├── api/
│   ├── main.py                      # EXTEND: include feedback router; CORS already covers POST
│   ├── models.py                    # EXTEND: ApprovalRequest, FeedbackRequest Pydantic
│   ├── sse.py                       # EXTEND: EventType Literal adds "approval_required"
│   └── routes/
│       ├── chat.py                  # EXTEND: detect __interrupt__, emit approval_required event; accept optional approve in body for resume; bind Langfuse trace_id seed per turn
│       └── feedback.py              # NEW: POST /api/feedback → langfuse.create_score
├── config.py                        # EXTEND: HITL_TOTAL_THB_THRESHOLD, SEARCH_CACHE_TTL_SECONDS, LANGFUSE_*, TAVILY_API_KEY
└── tests/
    ├── test_parallel_fanout.py      # NEW: assert both fuel_data and route_data populated after fan-out
    ├── test_hitl_gate.py            # NEW: threshold trigger + Command(resume) approve/deny paths
    ├── test_search_agent.py         # NEW: mock Tavily client; assert search_context populated; failure path keeps None
    ├── test_observability.py        # NEW: Langfuse no-op mode (keys missing); CallbackHandler attached; auto-eval Score posted
    └── test_api_feedback.py         # NEW: POST /api/feedback resolves trace_id and posts Score

frontend/
├── components/chat/
│   ├── ApprovalCard.tsx             # NEW: Approve / Deny inline UI (or extend MessageList.tsx — discretion)
│   └── FeedbackButtons.tsx          # EXTEND: localStorage stub → api.postFeedback() call
├── hooks/
│   └── useChatStream.ts             # EXTEND: handle approval_required event; expose approve(threadId, decision)
├── lib/
│   └── api.ts                       # EXTEND: postFeedback()
└── types/agent.types.ts             # EXTEND: SSEEvent union adds "approval_required"

docs/
├── architecture.md                  # OVERWRITE: Mermaid + ASCII fallback per D-18
├── data-sources.md                  # NEW: DOC-04
└── demo.mp4                         # NEW: D-20 screen recording

README.md                            # OVERWRITE: full DOC-01 layout
.env.example                         # EXTEND: HITL_TOTAL_THB_THRESHOLD, SEARCH_CACHE_TTL_SECONDS (already has the rest)
```

### Pattern 1: Parallel Fan-out via Conditional Edge → List

**What:** A planner node returns multiple destination node names from a conditional-edge function — LangGraph schedules all returned nodes in the SAME superstep. With `operator.add` on shared list keys, parallel writes merge cleanly; scalar keys (`fuel_data`, `route_data`) are disjoint between branches so last-write-wins is safe.

**When to use:** D-01 fresh-thread fan-out where we need BOTH fuel and route, and they have NO ordering dependency.

**Example (matches our existing graph.py L131–146 routing function):**

```python
# backend/agent/graph.py — EXTEND _route_from_planner
from langgraph.graph import StateGraph, START, END

def _route_from_planner(state: dict) -> str | list[str]:
    """Conditional-edge selector. Returns:
       - str for sequential routing (existing behaviour)
       - list[str] for fan-out (Phase 5 — Send API equivalent for static targets)
    """
    ns = state.get("next_step", "respond")
    # D-01: parallel fan-out trigger — both fuel+route stale on this turn.
    if ns in ("fetch_fuel", "fetch_route"):
        fuel_stale = not _fuel_fresh(state)
        route_stale = not _route_matches(state, state.get("origin"), state.get("destination"))
        if fuel_stale and route_stale:
            return ["fuel_agent", "route_agent"]   # parallel superstep
    return {
        "fetch_fuel": "fuel_agent",
        "fetch_route": "route_agent",
        "calculate_price": "pricing_agent",
        "clarify": "response",
        "respond": "response",
        "search_context": "search_agent",     # D-10: re-route from response stub
    }.get(ns, "response")
```

**Why a list-returning conditional edge instead of `Send()`:** Send is for dynamic state per branch (e.g., per-item map-reduce). Both fuel and route here read the SAME state (origin/destination/messages), so a static list of node names is simpler, achieves identical concurrent scheduling, and avoids fabricating per-branch state slices. Same superstep, same trace overlap. Verified per LangChain docs ("[Send] targets are executed in parallel" — same applies to list-returning conditional edges).

**Trace overlap demo (D-01 success criterion):** Each node calls `datetime.now(timezone.utc).isoformat()` BEFORE its tool call (in the trace_entry it returns). Because both nodes start in the same superstep, the trace `timestamp` for `fuel_agent` and `route_agent` will be ≤ ~50ms apart — visibly overlapping when the demo prints them.

### Pattern 2: HITL via `interrupt()` + Resume with `Command`

**What:** A node in the graph calls `interrupt(payload)` to pause. The runtime persists the entire state via the checkpointer. The caller observes `__interrupt__` in the next stream chunk (or via `aget_state`), shows the user the payload, and resumes by invoking the graph again with `Command(resume=user_decision)`. The same `interrupt()` call returns `user_decision` to the node body when execution resumes.

**When to use:** D-04/D-05/D-06/D-07 — pause between `pricing_agent` and `response_node` when `surcharge_result.total > HITL_TOTAL_THB_THRESHOLD`.

**Example:**

```python
# backend/agent/nodes/hitl_gate.py — NEW
from __future__ import annotations
from datetime import datetime, timezone
from langgraph.types import interrupt

from backend.config import HITL_TOTAL_THB_THRESHOLD


def hitl_gate_node(state: dict) -> dict:
    """D-05 gate. Either pass-through (low-value) or interrupt() (high-value)."""
    sr = state.get("surcharge_result") or {}
    total = float(sr.get("total") or 0.0)

    if total <= HITL_TOTAL_THB_THRESHOLD:
        # Pass-through — no trace entry pollution for low-value path.
        return {"approval_decision": "approve"}

    # D-08 pre-pause trace entry (one).
    prior_steps = len(state.get("reasoning_trace") or [])
    pre_trace = {
        "step": prior_steps + 1,
        "agent": "hitl_gate",
        "tool": "interrupt",
        "tool_input": {"threshold": HITL_TOTAL_THB_THRESHOLD, "total": total},
        "tool_output": {"decision_pending": True},
        "reasoning": f"Total {total:.2f} > {HITL_TOTAL_THB_THRESHOLD} THB threshold; awaiting user approval.",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "warn",  # signals pause, not error
    }
    # interrupt() returns the resume value when graph is resumed via Command(resume=...).
    decision = interrupt({
        "type": "approval_required",
        "surcharge_result": sr,
        "threshold": HITL_TOTAL_THB_THRESHOLD,
    })
    # decision is whatever the caller passed: True/False or "approve"/"deny".
    approval = "approve" if decision in (True, "approve") else "deny"

    # D-08 post-resume trace entry.
    post_trace = {
        "step": prior_steps + 2,
        "agent": "hitl_gate",
        "tool": "interrupt",
        "tool_input": {},
        "tool_output": {"decision": approval},
        "reasoning": f"User decision: {approval}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "ok",
    }
    return {
        "approval_decision": approval,
        "reasoning_trace": [pre_trace, post_trace],
    }
```

```python
# backend/agent/graph.py — wire into topology
g.add_node("hitl_gate", hitl_gate_node)  # NOT wrapped in error sink (interrupt is by-design pause, not error)
g.add_edge("pricing_agent", "hitl_gate")
g.add_conditional_edges(
    "hitl_gate",
    lambda s: "response" if s.get("approval_decision") in ("approve", "deny") else "response",
    {"response": "response"},
)
# Pricing → planner edge from Phase 3 D-03 is REPLACED with pricing → hitl_gate → response
```

**Resume from chat handler:**

```python
# backend/api/routes/chat.py — EXTEND
from langgraph.types import Command

@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    graph = request.app.state.graph
    thread_id = req.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # D-06 resume path
    if req.approve is not None and req.thread_id:
        async def resume_stream():
            yield format_sse("meta", {"thread_id": thread_id})
            async for event in graph.astream_events(
                Command(resume=req.approve), config=config, version="v2"
            ):
                # ... same trace/answer/done filtering as fresh path
                ...
            yield format_sse("done", {})
        return StreamingResponse(resume_stream(), media_type="text/event-stream")

    # Fresh path — same as today, plus detection of __interrupt__ in stream.
    # ...
```

**Detecting interrupt in the stream:** With `astream_events(version="v2")`, the run emits an event with `event.get("event") == "on_chain_end"` and the chunk data contains `__interrupt__` when a node has called `interrupt()`. Alternatively (more reliable), call `await graph.aget_state(config)` after the stream finishes and check `state.next` (will be non-empty list if interrupted) or `state.values.get("__interrupt__")`. **Recommendation:** rely on `aget_state` after the stream loop terminates — robust to LangGraph internal eventing changes.

```python
# After astream_events loop, in the fresh-path stream():
snapshot = await graph.aget_state(config)
if snapshot.next:  # graph is paused
    # interrupt() payload is in snapshot.tasks[0].interrupts[0].value
    interrupt_payload = snapshot.tasks[0].interrupts[0].value if snapshot.tasks else {}
    yield format_sse("approval_required", {
        "thread_id": thread_id,
        "surcharge_result": interrupt_payload.get("surcharge_result"),
        "threshold": interrupt_payload.get("threshold"),
    })
    # Do NOT yield "done" — frontend treats approval_required as terminal-pending.
    return
```

**Why NOT static `interrupt_before`:** D-04 specifies a runtime threshold check. `interrupt_before="response"` would pause every single response transition, including low-value queries that should never gate. Runtime `interrupt()` inside `hitl_gate_node` lets us bypass with a `return {"approval_decision":"approve"}` for low-value totals — zero user-visible UI impact on the common case.

### Pattern 3: Langfuse CallbackHandler with Deterministic Trace IDs

**What:** Attach `langfuse.langchain.CallbackHandler` once at graph invocation; pass `langfuse_session_id` via `config["metadata"]`; pre-seed a deterministic `trace_id` so `POST /api/feedback` can score the SAME trace later without searching.

**When to use:** D-13/D-14/D-15/D-16 — wrap every chat turn invocation.

**Example:**

```python
# backend/agent/observability.py — NEW
from __future__ import annotations
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return all(os.environ.get(k) for k in (
        "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"
    ))


def get_langfuse_client():
    """Returns initialized Langfuse client, or None when keys missing (D-13 graceful no-op)."""
    if not _enabled():
        return None
    try:
        from langfuse import get_client
        return get_client()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse init failed: %s", exc)
        return None


def get_callback_handler(trace_id: Optional[str] = None):
    """Returns a Langfuse CallbackHandler, or a no-op stub when keys missing.

    Args:
        trace_id: deterministic trace id (D-14 seed). If provided, the handler
            uses trace_context to ensure the resulting trace has this exact id,
            so D-16 feedback wire can score it without a name lookup.
    """
    if not _enabled():
        return None
    try:
        from langfuse.langchain import CallbackHandler
        if trace_id:
            return CallbackHandler(trace_context={"trace_id": trace_id})
        return CallbackHandler()
    except Exception as exc:  # noqa: BLE001
        logger.warning("CallbackHandler init failed: %s", exc)
        return None


def seed_trace_id(thread_id: str, turn_idx: int) -> str:
    """Deterministic 32-hex trace_id seeded by D-14 name pattern."""
    client = get_langfuse_client()
    if client is None:
        # Stable hash for tests / no-op mode.
        import hashlib
        return hashlib.md5(f"chat_turn_{thread_id}_{turn_idx}".encode()).hexdigest()
    return client.create_trace_id(seed=f"chat_turn_{thread_id}_{turn_idx}")


def post_formula_accuracy_score(
    trace_id: str,
    base_rate: float,
    current_diesel_price: float,
    shipping_type: str,
    traffic_severity: int,
    agent_result: dict,
) -> None:
    """D-15 fire-and-forget auto-eval.

    Re-runs the Phase 1 pure function (NOT the @tool wrapper — that goes
    through the agent path, defeating eval independence) and posts a Score.
    Any failure is logged and swallowed; eval failure MUST NOT impact users.
    """
    client = get_langfuse_client()
    if client is None:
        return
    try:
        from backend.agent.tools.calculate_surcharge import calculate_surcharge
        oracle = calculate_surcharge(
            base_rate=base_rate,
            current_diesel_price=current_diesel_price,
            shipping_type=shipping_type,
            traffic_severity=traffic_severity,
        )
        agent_total = float(agent_result.get("total") or 0.0)
        match = abs(oracle.total - agent_total) < 1e-6
        client.create_score(
            trace_id=trace_id,
            name="formula_accuracy",
            value=1.0 if match else 0.0,
            comment=None if match else f"oracle={oracle.total} agent={agent_total}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("formula_accuracy auto-eval failed (non-fatal): %s", exc)
```

```python
# backend/api/routes/chat.py — wire callback per turn
from backend.agent.observability import get_callback_handler, seed_trace_id

# Inside chat():
turn_idx = await _count_turns(graph, config)  # helper — len(messages)//2 from snapshot
trace_id = seed_trace_id(thread_id, turn_idx)
handler = get_callback_handler(trace_id=trace_id)
config_with_callbacks = {
    **config,
    "callbacks": [handler] if handler else [],
    "metadata": {
        "langfuse_session_id": thread_id,         # session = whole conversation
        "langfuse_user_id": "demo",               # MADT7204 demo — single user
        "langfuse_tags": ["express-surcharge", f"turn-{turn_idx}"],
    },
}
async for event in graph.astream_events(initial_state, config=config_with_callbacks, version="v2"):
    ...
```

```python
# backend/api/routes/feedback.py — NEW
from fastapi import APIRouter, HTTPException
from backend.api.models import FeedbackRequest
from backend.agent.observability import get_langfuse_client, seed_trace_id

router = APIRouter()


@router.post("/api/feedback")
async def feedback(req: FeedbackRequest):
    client = get_langfuse_client()
    if client is None:
        # D-13 graceful no-op — return 200 anyway so frontend doesn't error.
        return {"status": "ok", "delivered": False, "reason": "langfuse_disabled"}
    # The frontend supplies thread_id + message_id (which encodes turn_idx).
    # turn_idx encoding is whatever the FE adopts; recommend message_id = f"{thread_id}-{turn_idx}".
    turn_idx = _extract_turn_idx(req.message_id)  # parser helper
    trace_id = seed_trace_id(req.thread_id, turn_idx)
    score_value = 1 if req.score == "up" else -1
    try:
        client.create_score(
            trace_id=trace_id,
            name="user_feedback",
            value=score_value,
            data_type="NUMERIC",
            comment=req.reason,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc))
    return {"status": "ok", "delivered": True, "trace_id": trace_id}
```

**Why deterministic trace_id (load-bearing):** D-14 names the trace `chat_turn_{thread_id}_{turn_idx}` so D-16 can resolve it. The Langfuse SDK exposes `langfuse.create_trace_id(seed=...)` (HIGH confidence — verified via discussion #2658 and #3592). Using the seed pattern, both the `CallbackHandler(trace_context={"trace_id": ...})` and the later `create_score(trace_id=...)` see the same id without an extra DB lookup. **Rename in either place breaks the wire** — keep `seed_trace_id()` as the single source of truth.

### Pattern 4: Tavily Search Agent (Mirrors fuel_agent / route_agent)

**What:** A LangGraph node that calls `client.search(query, topic="news", max_results=5)`, narrates the results via Gemini with D-11 deterministic fallback, populates `state.search_context`, and emits one D-12 trace entry.

**When to use:** D-09/D-10/D-11/D-12 — when planner emits `next_step="search_context"`.

**Example:**

```python
# backend/agent/tools/search_fuel_news.py — NEW
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List

from pydantic import BaseModel, Field

from backend.agent.tools._cache import TTLCache
from backend.config import SEARCH_CACHE_TTL_SECONDS

__all__ = ["search_fuel_news", "SearchInput", "SearchResult", "SearchSource"]

logger = logging.getLogger(__name__)
_CACHE: TTLCache = TTLCache(ttl_seconds=SEARCH_CACHE_TTL_SECONDS)


class SearchInput(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=10)


class SearchSource(BaseModel):
    title: str
    url: str
    snippet: str
    published_at: Optional[str] = None  # ISO-8601 from Tavily 'published_date'


class SearchResult(BaseModel):
    query: str
    summary: Optional[str] = None
    sources: List[SearchSource] = Field(default_factory=list)
    fetched_at: str  # D-13 ISO-8601 UTC 'Z'


def _tavily_client():
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY missing")
    from tavily import TavilyClient
    return TavilyClient(api_key)


def search_fuel_news(query: str, max_results: int = 5) -> SearchResult:
    """Tavily-backed fuel news search with TTLCache + graceful failure."""
    cache_key = (query.strip().lower(), max_results)
    cached: Optional[SearchResult] = _CACHE.get(cache_key)
    if cached is not None:
        return cached

    client = _tavily_client()
    raw = client.search(
        query=query,
        topic="news",
        max_results=max_results,
        include_answer="basic",       # 1-line LLM-generated answer
        search_depth="basic",
    )
    sources = [
        SearchSource(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=(r.get("content") or "")[:240],
            published_at=r.get("published_date"),
        )
        for r in (raw.get("results") or [])
    ]
    result = SearchResult(
        query=query,
        summary=raw.get("answer"),
        sources=sources,
        fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    _CACHE.set(cache_key, result)
    return result
```

```python
# backend/agent/nodes/search_agent.py — NEW (mirrors fuel_agent.py)
from __future__ import annotations
import json, logging
from datetime import datetime, timezone
import httpx
from pydantic import ValidationError

from backend.agent.llm import get_chat_model
from backend.agent.tools.search_fuel_news import search_fuel_news, SearchResult

logger = logging.getLogger(__name__)


def _last_user_message(state: dict) -> str:
    msgs = state.get("messages") or []
    for m in reversed(msgs):
        if m.get("role") == "user":
            return m.get("content", "")
    return ""


def search_agent_node(state: dict) -> dict:
    """TOOL-05: search → narrate → populate search_context + emit one trace entry.

    On any Tavily failure, returns search_context=None and a warn-status
    trace entry so the planner continues without blocking the surcharge response.
    """
    query = _last_user_message(state) or "Thailand diesel fuel price news"
    prior = len(state.get("reasoning_trace") or [])
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    try:
        result: SearchResult = search_fuel_news(query=query, max_results=5)
    except (httpx.HTTPError, RuntimeError, Exception) as exc:  # graceful warn
        logger.warning("search_fuel_news failed: %s", exc)
        return {
            "search_context": None,
            "reasoning_trace": [{
                "step": prior + 1,
                "agent": "search_agent",
                "tool": "search_fuel_news",
                "tool_input": {"query": query},
                "tool_output": {"error": str(exc)},
                "reasoning": "Search failed; continuing without market context.",
                "timestamp": timestamp,
                "status": "warn",
            }],
        }

    # Use Tavily's own answer when present; else deterministic 1-liner from top result.
    summary = result.summary or (
        result.sources[0].snippet[:160] if result.sources else "No recent news found."
    )

    return {
        "search_context": result.model_dump(),
        "reasoning_trace": [{
            "step": prior + 1,
            "agent": "search_agent",
            "tool": "search_fuel_news",
            "tool_input": {"query": query, "max_results": 5},
            "tool_output": {"sources": len(result.sources), "summary_present": bool(result.summary)},
            "reasoning": summary,
            "timestamp": timestamp,
            "status": "ok",
        }],
    }
```

**Wiring:**

```python
# backend/agent/graph.py — add to topology
g.add_node("search_agent", _wrap_error_sink("search_agent", search_agent_node), retry_policy=retry)
g.add_edge("search_agent", "planner")  # D-03 loop closure
# _route_from_planner already maps next_step="search_context" → "search_agent" (Pattern 1 above)
```

**Retry allow-list extension (D-12):**

```python
# backend/agent/graph.py — extend the existing tuple
_RETRYABLE_EXCEPTIONS: Sequence[Type[BaseException]] = (
    httpx.HTTPError,                    # already covers TavilyClient (uses httpx under the hood)
    httpx.TimeoutException,
    asyncio.TimeoutError,
    ResourceExhausted,
    GMapsHTTPError,
    # Tavily SDK does not raise distinct subclasses for 429/5xx — they bubble as httpx.HTTPError already covered.
)
# CRITICAL: Do NOT add ValueError or BaseException — Phase 3 D-23 invariant.
```

### Anti-Patterns to Avoid

- **Static `interrupt_before="response"`:** would gate every query, not just high-value. Use runtime `interrupt()` inside a guard node.
- **Calling `@tool`-wrapped `calculate_surcharge_tool` for the auto-eval oracle (D-15):** routes through the agent path, defeats independence. Import the pure function `from backend.agent.tools.calculate_surcharge import calculate_surcharge` directly.
- **Naming the Langfuse trace inconsistently between handler init and feedback wire:** breaks D-16 silently (feedback POSTs score against a non-existent trace, no error visible to user). Centralize the `seed_trace_id()` helper.
- **Passing the user's exact words as the Tavily query without sanitization:** Tavily charges per query; cache miss rate goes up if "What's diesel doing today?" vs "diesel today?" hash to different keys. **Normalize:** lowercase + strip whitespace + collapse internal spaces — already done in `_tavily_client()` cache key above.
- **Adding `Exception` or `ValueError` to `phase3_retry_on` allow-list:** Phase 3 D-23 deliberately excludes ValueError; widening here breaks pricing-agent ValueError bubbling (D-09).
- **Sync `langfuse.create_score()` blocking the FastAPI handler:** the SDK is non-blocking under the hood (OpenTelemetry batched export), but a network blip could still surface latency. Recommend wrapping the `create_score` call in `asyncio.wait_for(loop.run_in_executor(None, ...), timeout=2.0)` to bound user-facing latency. (This is a stylistic refinement; not strictly required by D-16 which says "synchronous, returns 200 immediately".)
- **Missing `from __future__ import annotations`:** project convention; required because venv currently runs Python 3.9 and uses `X | Y` annotation syntax in type hints.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pause-and-resume across HTTP requests | Custom state-flag + DB poll loop | `langgraph.types.interrupt()` + `Command(resume=...)` | LangGraph's runtime + AsyncSqliteSaver already snapshot the EXACT execution point (which node, which line in the node body, which intermediate values). A state-flag approach loses the resume-at-line invariant and forces re-running the pricing computation |
| LLM trace capture | Manual `print()` of every Gemini call + tool call to a file | `langfuse.langchain.CallbackHandler` | Captures every chain start/end, tool start/end, LLM token usage, latency — at the framework level. Single attach point. Custom logging would touch every node + every tool |
| Trace-id correlation between agent and feedback POST | Database table mapping `(thread_id, message_id) → trace_id` | `langfuse.create_trace_id(seed=...)` deterministic helper | Free, no new table, no race conditions. Available in Langfuse v3+ SDK (verified) |
| Web search for fuel news | Custom RSS scrape + ranking | Tavily `topic="news"` with `include_answer="basic"` | Returns ranked news with `published_date`; built-in 1-line answer summary (saves a Gemini call); free tier covers demo (1000 searches/month >> demo footprint of ~10) |
| Fan-out scheduling | Spawn `asyncio.gather()` from a node | LangGraph conditional-edge returning a list of node names | Reducer + checkpointer integration is automatic; tool retry policy + error-sink wraps both branches; observability handler captures both as siblings of the planner trace |
| Mermaid diagram drawing | Custom SVG / PNG embed | Mermaid fenced code block in `.md` | GitHub renders Mermaid natively (HIGH confidence — Mermaid parsing in GitHub since 2022). Graders see live diagram |

**Key insight:** Phase 5 is mostly *integration* of well-established framework primitives. The high-leverage discipline is naming/contract consistency: the deterministic trace-id seed, the sixth SSE event type, the `approval_decision` state field, and the `search_context` shape all need to match between backend producer and frontend consumer. Get the shapes right in Wave 0, the implementation falls out.

## Common Pitfalls

### Pitfall 1: `interrupt()` resume loses dynamic config (callbacks, metadata)
**What goes wrong:** When resuming via `Command(resume=value)`, you must pass the SAME config dict (with `configurable.thread_id`, `callbacks`, `metadata`) you originally invoked with. Otherwise Langfuse spans on the resume turn won't link to the original session, and the checkpointer won't find the thread.
**Why it happens:** The chat handler's two paths (fresh + resume) are easy to write divergently — fresh path builds full config, resume path forgets to add Langfuse callback.
**How to avoid:** Build a `_make_config(thread_id, turn_idx, trace_id)` helper used by BOTH the fresh-stream path and the `Command(resume=...)` path. Test: assert that two consecutive POST /api/chat calls with the same `thread_id` yield Langfuse traces that share `langfuse_session_id`.
**Warning signs:** Langfuse "session" view shows the resume turn as orphaned; trace count for a single user conversation > expected.

### Pitfall 2: SSE event ordering — `approval_required` must NOT be followed by `done`
**What goes wrong:** The standard SSE `finally:` block in `chat.py` (L69–70) emits `done` unconditionally. If we yield `approval_required` and then fall through to `done`, the frontend sees the stream as fully complete and may NOT render the Approve/Deny buttons (or worse, removes them after a moment).
**Why it happens:** Backend re-uses the existing `try/finally` envelope without a control-flow exit before `done`.
**How to avoid:** When the post-stream `aget_state()` shows `next` non-empty (interrupted), `return` from the generator BEFORE the `finally:` clause is reached. Recommend a `pending_approval = False` local flag in the generator; in `finally:`, only `yield format_sse("done", {})` when `not pending_approval`.
**Warning signs:** Frontend log shows `done` event arriving immediately after `approval_required`; Approve buttons flash and disappear.

### Pitfall 3: Tavily query cache key drift
**What goes wrong:** Two semantically identical queries ("What's diesel doing today?" and "what is diesel doing today") cache as separate entries — quota burns faster, cache hit rate drops to ~0%.
**Why it happens:** The TTLCache key is the raw query string.
**How to avoid:** Normalize before caching — lowercase, strip leading/trailing whitespace, collapse multi-space to single. (Above pattern code does this.) Optionally hash to a stable digest.
**Warning signs:** Tavily "queries this month" climbing faster than expected during demo prep; same news result re-fetched on every demo click.

### Pitfall 4: Parallel branch each emits a `step: prior + 1` trace entry
**What goes wrong:** Both `fuel_agent_node` and `route_agent_node` compute `step` from `len(reasoning_trace) + 1` BEFORE the reducer fires. They both produce step `N+1`, and after merge the trace shows two entries with the same step number.
**Why it happens:** The two parallel nodes read the SAME pre-superstep state (the planner's output); neither sees the other's append.
**How to avoid:** Either (a) drop step-monotonicity assumption — UI sorts by `timestamp` anyway (Phase 4 D-09 implies this); (b) accept duplicate step numbers as visual proof of parallelism (this is actually GOOD — graders see "both fuel_agent and route_agent are step 2" in the trace panel and read it as concurrent execution); or (c) compute step by index AFTER merge in the response_node (defer renumbering). **Recommend (b)** — duplicate step numbers reinforce the parallel demo. Document in the Phase 5 plan + architecture.md that step is monotonic per node and may collide across parallel branches.
**Warning signs:** Test asserting `step` is strictly monotonic fails after fan-out is wired.

### Pitfall 5: Langfuse callback handler crashes when keys missing in tests
**What goes wrong:** Tests don't set Langfuse env vars; importing `langfuse.langchain.CallbackHandler` directly without keys triggers an init error when constructed.
**Why it happens:** SDK does basic auth-key validation at construction time.
**How to avoid:** D-13 graceful no-op pattern — wrap `get_callback_handler()` in `if not _enabled(): return None` before instantiation; downstream code treats `None` as "no callback". The pattern code in `observability.py` above does this.
**Warning signs:** CI fails with "MissingAPIKeyError" or "AuthenticationError" from Langfuse.

### Pitfall 6: Pricing → HITL gate breaks Phase 3 D-03 planner-loop topology
**What goes wrong:** Phase 3 D-03 says specialists return to planner. Inserting `hitl_gate` between pricing and response means pricing → hitl_gate → response is now sequential without re-entering planner. If the planner's later iterations needed to re-route (e.g., another query in a multi-turn conversation), this might break.
**Why it happens:** The new edge bypasses the loop.
**How to avoid:** This is INTENTIONAL — D-05 says gate placement is between pricing and response, NOT between pricing and planner. The planner-loop is still entered for the NEXT user turn (fresh `astream_events` call). Within ONE turn, the loop topology is: planner → fetch_fuel/route → planner → calculate_price → planner → respond (per Phase 3 D-03). Phase 5 changes the last hop to: → calculate_price → hitl_gate → respond, bypassing planner on the final hop. This is correct because the planner's job is intent classification, and after pricing succeeds there is nothing left to classify.
**Warning signs:** Test `test_graph.py` integration assertion that `planner` runs N times per turn — count may decrease by 1 after Phase 5. Update test.

### Pitfall 7: Frontend feedback POST race with `approval_required`
**What goes wrong:** User clicks thumbs-up while `approval_required` is pending — the message has no final answer to score yet, but the backend handler tries to score a trace_id whose underlying turn isn't complete in Langfuse.
**Why it happens:** Phase 4 `FeedbackButtons` is gated on `threadId !== null`, NOT on `finalPayload !== null`.
**How to avoid:** Update `MessageList.tsx` (Phase 4 owner) to gate `FeedbackButtons` rendering on `finalPayload?.status !== undefined` AND `status === 'streaming'/'idle'/'done'` (NOT during `approval_required` pause). Also: backend should accept the score and let Langfuse silently no-op if trace not yet flushed (which is fine; SDK is async).
**Warning signs:** 502 from POST /api/feedback on rapid demo clicks during approval pause.

## Code Examples

### Common Operation 1: Detect interrupt in chat handler

```python
# backend/api/routes/chat.py — fresh-path stream() generator
async def stream():
    yield format_sse("meta", {"thread_id": thread_id})
    pending_approval = False
    try:
        initial_state = {"messages": [{"role": "user", "content": req.message}]}
        async for event in graph.astream_events(initial_state, config=cfg, version="v2"):
            ev_type = event.get("event")
            name = event.get("name", "")
            if ev_type == "on_chain_end" and name in _NODE_NAMES:
                output = (event.get("data") or {}).get("output") or {}
                for entry in (output.get("reasoning_trace") or []):
                    yield format_sse("trace", entry)
                if name == "response" and "final_payload" in output:
                    yield format_sse("answer", output["final_payload"])
        # After stream ends: check if interrupted.
        snapshot = await graph.aget_state(cfg)
        if snapshot.next:
            pending_approval = True
            iv = snapshot.tasks[0].interrupts[0].value if snapshot.tasks else {}
            yield format_sse("approval_required", {
                "thread_id": thread_id,
                "surcharge_result": iv.get("surcharge_result"),
                "threshold": iv.get("threshold"),
            })
            return  # Pitfall 2: do NOT yield done.
    except Exception as exc:  # noqa: BLE001
        yield format_sse("error", {"message": str(exc), "retryable": False})
    finally:
        if not pending_approval:
            yield format_sse("done", {})
```

### Common Operation 2: Parallel fan-out integration test

```python
# backend/tests/test_parallel_fanout.py — NEW
import asyncio
import pytest
from backend.agent.graph import build_graph

@pytest.mark.asyncio
async def test_fresh_thread_fans_out_fuel_and_route(in_memory_checkpointer, mock_gemini, mock_tools):
    """D-01 / D-02 — both fuel_data and route_data must populate after one planner turn."""
    graph = build_graph(in_memory_checkpointer)
    config = {"configurable": {"thread_id": "test-fanout"}}
    initial = {"messages": [{
        "role": "user",
        "content": "Surcharge for 15kg bounce from Bangkok to Nonthaburi"
    }]}
    final_state = await graph.ainvoke(initial, config=config)
    assert final_state.get("fuel_data") is not None, "fuel_data missing — fan-out branch dropped"
    assert final_state.get("route_data") is not None, "route_data missing — fan-out branch dropped"
    # Trace overlap evidence (D-01 success criterion):
    fuel_trace = next(t for t in final_state["reasoning_trace"] if t["agent"] == "fuel_agent")
    route_trace = next(t for t in final_state["reasoning_trace"] if t["agent"] == "route_agent")
    from datetime import datetime
    fuel_ts = datetime.fromisoformat(fuel_trace["timestamp"].replace("Z", "+00:00"))
    route_ts = datetime.fromisoformat(route_trace["timestamp"].replace("Z", "+00:00"))
    delta_s = abs((fuel_ts - route_ts).total_seconds())
    assert delta_s < 1.0, f"Trace timestamps {delta_s}s apart — likely sequential, not parallel"
```

### Common Operation 3: HITL gate threshold + resume

```python
# backend/tests/test_hitl_gate.py — NEW
import pytest
from langgraph.types import Command

@pytest.mark.asyncio
async def test_low_value_total_bypasses_gate(in_memory_checkpointer, mock_pricing_low):
    graph = build_graph(in_memory_checkpointer)
    config = {"configurable": {"thread_id": "low"}}
    final = await graph.ainvoke({"messages": [{"role": "user", "content": "..."}]}, config=config)
    assert final["approval_decision"] == "approve"  # auto-approved
    assert final.get("final_payload") is not None    # response rendered

@pytest.mark.asyncio
async def test_high_value_total_pauses_for_approval(in_memory_checkpointer, mock_pricing_high):
    graph = build_graph(in_memory_checkpointer)
    config = {"configurable": {"thread_id": "high"}}
    # First call interrupts.
    await graph.ainvoke({"messages": [{"role": "user", "content": "..."}]}, config=config)
    snapshot = await graph.aget_state(config)
    assert snapshot.next != ()  # paused
    iv = snapshot.tasks[0].interrupts[0].value
    assert iv["surcharge_result"]["total"] > 500  # threshold default
    # Resume with approve.
    final = await graph.ainvoke(Command(resume=True), config=config)
    assert final["approval_decision"] == "approve"
    assert final["final_payload"]["status"] == "ok"
```

### Common Operation 4: Mermaid graph topology block for architecture.md

````markdown
```mermaid
flowchart TD
    START([START]) --> P[Planner Node]
    P -->|next_step=fetch_fuel/fetch_route<br/>both stale| FAN{Fan-out<br/>parallel superstep}
    FAN --> F[Fuel Agent]
    FAN --> R[Route Agent]
    P -->|next_step=fetch_fuel<br/>route cached| F
    P -->|next_step=fetch_route<br/>fuel cached| R
    P -->|next_step=search_context| S[Search Agent]
    P -->|next_step=calculate_price| PR[Pricing Agent]
    P -->|next_step=clarify/respond| RESP[Response Node]
    F --> P
    R --> P
    S --> P
    PR --> H{HITL Gate<br/>total > threshold?}
    H -->|low value| RESP
    H -->|high value| INT([interrupt — await user])
    INT -->|Command resume=approve/deny| RESP
    RESP --> END([END])
```
````

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `langfuse.callback.CallbackHandler` (v2 path) | `langfuse.langchain.CallbackHandler` (v3+ path) | Langfuse 3.0 (mid-2025) | All Phase 5 imports MUST use the new path |
| `CallbackHandler(session_id="...", trace_id="...")` constructor args | Pass `session_id` via `config["metadata"]["langfuse_session_id"]`, pass `trace_id` via `CallbackHandler(trace_context={"trace_id": ...})` | Langfuse 3.0 | Forces config-time wiring (which fits our chat-handler integration well) |
| Static `interrupt_before=["node_name"]` at graph compile | Runtime `interrupt(payload)` call inside a node body, resume with `Command(resume=...)` | LangGraph 0.2+ (preferred since LangChain 2024 blog post) | Allows conditional interrupt — exactly what D-04 needs for threshold-gated pause |
| `langfuse.score(trace_id=..., name=..., value=...)` (v2) | `langfuse.create_score(trace_id=..., name=..., value=..., data_type="NUMERIC")` (v3+) | Langfuse 3.0 | Method renamed; data_type now explicit |

**Deprecated/outdated:**
- `from langfuse.callback import CallbackHandler` — replaced by `from langfuse.langchain import CallbackHandler`
- LangGraph `MemorySaver` for HITL — replaced by `AsyncSqliteSaver` for production-grade resume across processes (already used by us)
- Manual SSE framing via `EventSourceResponse` — not relevant; our existing `format_sse()` helper is correct for fastapi 0.128.8 (Phase 3 Pitfall 5)

## Open Questions

1. **Python 3.9 vs 3.11 venv compatibility for langfuse 4.x**
   - What we know: PyPI metadata says `langfuse 4.5.1` requires `>=3.10`. Project venv is 3.9.6. CLAUDE.md declares 3.11+ but Phase 1 `from __future__ import annotations` was added precisely for 3.9 compat.
   - What's unclear: whether bumping to 3.11 breaks anything else in the project (probably not — `from __future__` is forward-compatible).
   - Recommendation: planner adds a Wave 0 task to `python3.11 -m venv .venv && pip install -r requirements.txt && pytest` and confirm 100% existing test suite passes. If any failure: pin `langfuse<3.0` and use the v2 trace-id pattern (less elegant — no `create_trace_id(seed=...)`; would need name-based trace lookup via search API).

2. **Langfuse v3+ trace_id parameter shape: hex32 string vs UUID**
   - What we know: discussion #2658 example shows `str(uuid.uuid4()).replace("-", "")` (32-hex). `create_trace_id(seed=...)` returns the canonical format.
   - What's unclear: whether arbitrary user-supplied strings work or only hex32.
   - Recommendation: use `client.create_trace_id(seed=...)` exclusively — never construct trace_ids by hand. The wrapper guarantees format conformance.

3. **Tavily SDK exception class for retry allow-list**
   - What we know: SDK uses httpx under the hood; httpx errors already in our `_RETRYABLE_EXCEPTIONS` tuple. Tavily docs do NOT enumerate distinct exception classes.
   - What's unclear: whether the SDK wraps httpx errors in its own `tavily.exceptions.UsageLimitExceededError` etc.
   - Recommendation: do NOT add new types to retry allow-list. Existing `httpx.HTTPError` covers the common cases (429, 5xx). Quota-exceeded (`UsageLimitExceeded`) should NOT retry — it'll never succeed within the cooldown window. Catch it in `search_agent_node`'s explicit `try/except` and convert to a `warn` trace entry directly.

4. **Frontend `message_id` shape for feedback POST**
   - What we know: Phase 4 D-17 localStorage uses `{thread_id, message_id, score, reason?}`. Phase 4 left `message_id` informally as "an opaque per-message id".
   - What's unclear: whether `message_id` already encodes `turn_idx` (so backend can compute `seed_trace_id(thread_id, turn_idx)`).
   - Recommendation: in Phase 5 plan Wave 0, lock `message_id = f"{thread_id}-{turn_idx}"` shape; document in architecture.md API section. Backend `_extract_turn_idx(message_id)` is then trivial.

5. **HITL approval prompt copy — exact wording**
   - What we know: D-06 says "approval_required" payload includes `surcharge_result`. Backlog 999.2 mandates "Bangkok Metro" phrasing.
   - What's unclear: exact button labels and prompt text.
   - Recommendation: planner picks; suggested copy: heading "**High-value shipment — review required**", body "This Bangkok Metro shipment estimates THB {total} (above the {threshold} review threshold). Approve to finalize, deny to mark for manual review.", buttons "Approve" / "Deny".

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ runtime | langfuse 4.x SDK | Partial | venv has 3.9.6 (system has 3.11/3.13 likely available via brew) | Pin `langfuse<3.0` if 3.11 bump blocked — but loses `create_trace_id(seed=...)` |
| Node.js 18+ | Next.js 15 frontend | ✓ | v25.9.0 | — |
| npm | frontend deps | ✓ | 11.12.1 | — |
| `aiosqlite` 0.20.0 | AsyncSqliteSaver (HITL resume) | ✓ | already installed (Phase 3 lock) | — |
| `langgraph` (Send + interrupt support) | Parallel + HITL | ✓ | 0.6.11 installed (1.1.10 latest) | If 0.6.11 lacks `interrupt()`, bump to 1.x — verify in Wave 0 |
| `data/express.db` (rate table for HITL threshold calibration) | Threshold default selection | ✓ | seeded; 45 rows, base_rate range 50–698 THB | — |
| Internet connectivity (Gemini, Google Maps, Tavily, Langfuse Cloud) | All external calls | ✓ assumed dev env | — | Cached responses for fuel/route; Tavily failure → search_context=None; Langfuse missing keys → no-op handler |
| ffmpeg / QuickTime / Loom | demo.mp4 recording | not probed | — | Manual screen recording; any tool that exports .mp4 |

**Missing dependencies with no fallback:** None — Python 3.11 install is a Wave 0 task, not a hard blocker.

**Missing dependencies with fallback:** None critical.

## HITL Threshold Calibration (Claude's Discretion D-04)

Verified empirically against `data/express.db` (45 rate-table rows):

```
Threshold  | Approx % of demo queries gated (assuming modest +5% surcharge)
-----------+----------------------------------------------------------------
300 THB    | ~29%   (too noisy — gate fires on basic shipments)
400 THB    | ~18%
500 THB    | ~9%    ← RECOMMENDED — hits CONTEXT.md target of 5–10%
600 THB    | ~4%
700 THB    | ~2%    (too rare — may not fire during demo)
```

**Recommendation:** `HITL_TOTAL_THB_THRESHOLD = 500` default. Demo prompts in README should include at least one query that hits the gate (e.g., a 200kg+ retail_fast shipment to central-3). Document in data-sources.md the calibration logic so graders see the empirical basis.

## Documentation Deliverables (DOC-01 / DOC-02 / DOC-04)

### README.md outline (DOC-01 verbatim)

```
# Express Dynamic Surcharge Orchestrator

[Brief tagline + rubric-aligned summary]

## Project Overview
[1 paragraph; "Bangkok Metro" phrasing]

## Team
[Members + roles, IT Lead = pollot]

## Problem Statement
[Express logistics fuel-volatility cost; manual recompute pain; agentic value]

## Agent Design
[Mermaid flowchart embed (Pattern 4 above) + 3 paragraphs:
 - LangGraph multi-agent orchestration
 - Cache-aware planner + parallel fuel/route
 - HITL gate + Search Agent
]

## Data Sources
See [docs/data-sources.md](docs/data-sources.md) for full provenance.
- EPPO diesel B7 historical prices (real)
- Simulated rate table (transparent assumptions)
- Google Maps Directions API
- Tavily news search

## Setup Instructions
1. Python 3.11+ venv: `python3.11 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`, fill in API keys
4. Seed DB: `python data/scripts/seed_database.py`
5. Backend: `uvicorn backend.api.main:app --port 8000`
6. Frontend: `cd frontend && npm install && npm run dev`
7. Tests: `pytest backend/tests/ && cd frontend && npm test`

## AI Tools Used
[Per AI/Vibe-Coding 15% rubric:]
- Claude Agent SDK + Claude Code (architecture, tool design, code generation)
- Cursor (inline edits)
- GitHub Copilot (typing acceleration)
[+ rationale: each used for what / why]

## Limitations
- Bangkok Metro only (V2-02 deferred)
- Gemini Flash 15 RPM (demo-grade, not prod throughput)
- Tavily 1k searches/month (free tier)
- Simulated rate table (real Express tariffs are confidential)

## License
MIT (or specified course license)

## Demo
[Embedded screenshot links + ![demo](docs/demo.mp4) reference]
```

### docs/architecture.md update plan (DOC-02 / D-18)

Replace the existing ASCII-only sections with hybrid Mermaid + ASCII layout:

1. **System Overview:** keep ASCII (it's good for terminal-readable fallback), add Mermaid `flowchart` showing same components.
2. **Agent Graph Flow:** REPLACE current ASCII with Mermaid flowchart from Pattern 4 above (parallel + HITL + search shown explicitly).
3. **Conditional Routing table:** add row for `search_context → search_agent` (was → response stub); add note about parallel fan-out trigger.
4. **AgentState schema:** add `approval_decision`, `search_context` fields with descriptions.
5. **API Endpoints table:** add `POST /api/feedback` + new `approve` body field on `POST /api/chat`.
6. **SSE Event Types:** expand from 5 to 6 — add `approval_required`.
7. **Memory Management section:** add note that AsyncSqliteSaver is REQUIRED for HITL resume (was: nice-to-have for follow-ups).
8. **Error Handling section:** add Tavily failure path (warn trace, search_context=None); add HITL deny path (status="partial"); add Langfuse no-op when keys missing.
9. **NEW section: Observability Architecture** — Mermaid `flowchart` showing Langfuse callback boundary, where the auto-eval runs, how feedback flows from FE button → backend POST → Langfuse Score.
10. **NEW section: Parallel Execution** — explain when fan-out fires (D-01 conditions), trace overlap evidence, reducer safety.

### docs/data-sources.md outline (DOC-04 / D-19)

```
# Data Sources

## EPPO Diesel B7 Historical Prices
- Source: https://www.eppo.go.th/index.php/en/petroleum-statistics/petroleum-data
- Refresh cadence: daily via `data/scripts/fetch_fuel_prices.py`
- Storage: `data/raw/eppo_diesel_prices.csv`
- Schema: `date,diesel_b7_price,source`
- Fallback chain: API → scrape → cached CSV → last-known
- Baseline: 29.94 THB/L (configurable via `BASELINE_DIESEL_PRICE`)

## Simulated Express Rate Table
- Generator: `data/scripts/generate_rate_table.py`
- Schema: `shipping_type, zone, weight_min_kg, weight_max_kg, base_rate_thb`
- Assumptions:
  - Zone multipliers: central-1 = 1.0, central-2 = 1.25, central-3 = 1.55
  - Shipping multipliers: bounce = 1.0, retail_standard = 0.5x, retail_fast = 0.8x
  - Base rate range produced: 50–698 THB
  - 45 rows total (3 ship types × 3 zones × 5 weight tiers)
- HITL threshold (500 THB) calibrated against this distribution to gate ~9% of demo queries

## Google Maps Directions API
- Endpoint: `directions/json`
- Cache: 15-minute TTL via `backend/agent/tools/_cache.py::TTLCache`
- Bangkok Metro provinces covered: Bangkok, Nonthaburi, Pathum Thani, Samut Prakan,
  Nakhon Pathom, Samut Sakhon, Ayutthaya
- Province → zone mapping table

## Tavily News Search
- Endpoint: `client.search(query=..., topic="news", max_results=5)`
- Cache: 30-minute TTL keyed on normalized query string
- Triggered ONLY by news/market intent (planner classification)
- Free tier: 1000 searches/month — demo footprint estimate ~10/run
- Failure handling: warn trace, search_context=None, surcharge response continues

## SQLite databases
- `data/express.db`: rate_table + zones + fuel_prices snapshot
- `data/checkpoints.db`: LangGraph AsyncSqliteSaver — conversation memory + HITL pause snapshots
```

## Validation Architecture

> Phase 5 has nyquist_validation enabled (config.workflow.nyquist_validation defaulted to true).

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest 8.4.2 + pytest-asyncio 0.24.0 + pytest-mock 3.15.1 + pytest-httpx 0.35.0 |
| Backend config | `backend/tests/conftest.py` (existing fixtures: `sample_agent_state`, `seeded_sqlite_path`, `in_memory_checkpointer`, `eppo_html_fixture`); `pyproject.toml` / `pytest.ini` for asyncio mode |
| Frontend framework | Vitest 4 + jsdom + MSW 2 + @testing-library/react + Playwright (e2e) |
| Frontend config | `frontend/vitest.config.ts`, `frontend/__tests__/setup.ts`, `frontend/playwright.config.ts` |
| Quick run command (backend) | `.venv/bin/pytest backend/tests/test_<module>.py -x -q` |
| Quick run command (frontend) | `cd frontend && npm test -- <pattern>` |
| Full backend suite | `.venv/bin/pytest backend/tests/` |
| Full frontend suite | `cd frontend && npm test && npm run test:e2e` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORCH-07 | Fan-out: both fuel_data and route_data populated after fresh-thread first turn | integration | `pytest backend/tests/test_parallel_fanout.py::test_fresh_thread_fans_out_fuel_and_route -x` | ❌ Wave 0 |
| ORCH-07 | Trace timestamps for fuel_agent and route_agent within 1s of each other (overlap evidence) | integration | `pytest backend/tests/test_parallel_fanout.py::test_trace_timestamps_overlap -x` | ❌ Wave 0 |
| ORCH-07 | Cache-warm follow-up turn skips fan-out (sequential per Phase 3 D-12) | integration | `pytest backend/tests/test_parallel_fanout.py::test_cache_hit_skips_fanout -x` | ❌ Wave 0 |
| ORCH-09 | Low-value total (<= threshold) bypasses gate, sets approval_decision="approve" | unit | `pytest backend/tests/test_hitl_gate.py::test_low_value_total_bypasses_gate -x` | ❌ Wave 0 |
| ORCH-09 | High-value total (> threshold) calls interrupt(); aget_state().next non-empty after first invoke | integration | `pytest backend/tests/test_hitl_gate.py::test_high_value_total_pauses_for_approval -x` | ❌ Wave 0 |
| ORCH-09 | Resume with Command(resume=True) → final_payload status="ok" | integration | `pytest backend/tests/test_hitl_gate.py::test_resume_approve_renders_full_response -x` | ❌ Wave 0 |
| ORCH-09 | Resume with Command(resume=False) → final_payload status="partial", deny prose | integration | `pytest backend/tests/test_hitl_gate.py::test_resume_deny_renders_partial_response -x` | ❌ Wave 0 |
| TOOL-05 | search_fuel_news returns SearchResult with sources; cache hit on second call | unit | `pytest backend/tests/test_search_fuel_news.py -x` | ❌ Wave 0 |
| TOOL-05 | Search Agent populates state.search_context; trace status="ok" | unit | `pytest backend/tests/test_search_agent.py::test_search_agent_populates_context -x` | ❌ Wave 0 |
| TOOL-05 | Tavily failure → search_context=None, trace status="warn", planner continues | unit | `pytest backend/tests/test_search_agent.py::test_search_failure_graceful_warn -x` | ❌ Wave 0 |
| TOOL-05 | Planner emits next_step="search_context" only when user_intent indicates news/trend | unit | `pytest backend/tests/test_planner.py::test_news_intent_routes_to_search -x` | ❌ Wave 0 |
| API-05 | POST /api/feedback resolves seed_trace_id(thread_id, turn_idx); calls langfuse.create_score | integration | `pytest backend/tests/test_api_feedback.py::test_feedback_posts_score -x` | ❌ Wave 0 |
| API-05 | POST /api/feedback returns 200 with delivered=False when Langfuse keys missing (no-op) | integration | `pytest backend/tests/test_api_feedback.py::test_feedback_no_op_without_keys -x` | ❌ Wave 0 |
| OBS-01 | get_callback_handler returns None when keys missing; CallbackHandler instance when present | unit | `pytest backend/tests/test_observability.py::test_callback_handler_no_op_mode -x` | ❌ Wave 0 |
| OBS-01 | seed_trace_id is deterministic for same (thread_id, turn_idx) across calls | unit | `pytest backend/tests/test_observability.py::test_seed_trace_id_deterministic -x` | ❌ Wave 0 |
| OBS-02 | (Covered by API-05 tests above — feedback flow IS the OBS-02 wire) | — | (see API-05) | (see API-05) |
| OBS-03 | post_formula_accuracy_score posts value=1.0 on match; 0.0 on divergence | unit | `pytest backend/tests/test_observability.py::test_formula_accuracy_match -x` | ❌ Wave 0 |
| OBS-03 | post_formula_accuracy_score is fire-and-forget — exception in calculate_surcharge does NOT raise | unit | `pytest backend/tests/test_observability.py::test_formula_accuracy_swallows_errors -x` | ❌ Wave 0 |
| DOC-01 | README.md exists at repo root with required sections (overview, team, agent design, setup, AI tools, limitations) | manual + smoke | `grep -q "## Setup Instructions" README.md && grep -q "## AI Tools" README.md` | manual review |
| DOC-02 | docs/architecture.md contains Mermaid flowchart with parallel + HITL + search nodes | manual + smoke | `grep -q "mermaid" docs/architecture.md && grep -q "hitl_gate" docs/architecture.md` | manual review |
| DOC-04 | docs/data-sources.md exists with EPPO + rate-table + Google Maps + Tavily sections | manual + smoke | `test -f docs/data-sources.md && grep -q "EPPO" docs/data-sources.md && grep -q "Tavily" docs/data-sources.md` | ❌ Wave 0 |
| End-to-end (manual) | Live Bangkok→Pathum Thani 200kg retail_fast triggers HITL gate; Approve renders surcharge; Langfuse trace appears | e2e (manual) | Live demo with Langfuse dashboard open | manual checkpoint per Phase 4 D-21 pattern |
| End-to-end (Playwright) | "What's driving diesel prices?" prompt populates search_context, prepended summary renders above answer | e2e | `cd frontend && npm run test:e2e -- search-news.spec.ts` | ❌ Wave 0 |
| End-to-end (Playwright) | High-value query shows ApprovalCard; click Approve → final answer renders | e2e | `cd frontend && npm run test:e2e -- hitl-gate.spec.ts` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/test_<module-touched>.py -x -q` (typically <5s); `cd frontend && npm test -- <pattern>` for FE files
- **Per wave merge:** `pytest backend/tests/` (full backend) + `cd frontend && npm test` (full FE unit) — must be all green
- **Phase gate:** Full suite green + Playwright e2e green + manual checkpoint (HITL approval flow + Langfuse dashboard view) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_parallel_fanout.py` — covers ORCH-07
- [ ] `backend/tests/test_hitl_gate.py` — covers ORCH-09
- [ ] `backend/tests/test_search_fuel_news.py` — covers TOOL-05 (tool unit)
- [ ] `backend/tests/test_search_agent.py` — covers TOOL-05 (node unit)
- [ ] `backend/tests/test_api_feedback.py` — covers API-05 / OBS-02
- [ ] `backend/tests/test_observability.py` — covers OBS-01 / OBS-03
- [ ] `backend/tests/conftest.py` extension — fixtures `mock_langfuse`, `mock_tavily_client`, `mock_pricing_low`, `mock_pricing_high`
- [ ] `frontend/__tests__/components/ApprovalCard.test.tsx` — covers ORCH-09 UI
- [ ] `frontend/__tests__/hooks/useChatStream-approval.test.ts` — covers approval_required event handling
- [ ] `frontend/playwright/specs/hitl-gate.spec.ts` + `search-news.spec.ts` — e2e
- [ ] `docs/data-sources.md` (new file)
- [ ] `docs/demo.mp4` (artifact)
- [ ] Framework install: `python3.11 -m venv .venv && pip install langfuse==4.5.1 tavily-python==0.7.24` (Wave 0 if Python bump confirmed) — see Open Question 1

*Existing test infrastructure (conftest fixtures, in_memory_checkpointer, FakeMessagesListChatModel seam, MSW handlers) covers all extension points; Phase 5 adds new files only.*

## Sources

### Primary (HIGH confidence)
- LangChain official docs — Human-in-the-loop primitives: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- LangChain official docs — Use the graph API (Send + parallel): https://docs.langchain.com/oss/python/langgraph/use-graph-api
- Langfuse official integration guide — LangChain CallbackHandler: https://langfuse.com/integrations/frameworks/langchain
- Langfuse v3 sessions docs: https://langfuse.com/docs/observability/features/sessions
- Langfuse v3 trace IDs docs: https://langfuse.com/docs/observability/features/trace-ids-and-distributed-tracing
- Langfuse Python v2→v3 migration: https://langfuse.com/docs/observability/sdk/upgrade-path/python-v2-to-v3
- Tavily Python SDK reference: https://docs.tavily.com/sdk/python/reference
- PyPI — version verification (`langfuse 4.5.1`, `tavily-python 0.7.24`, `langgraph 1.1.10`): direct `pip` JSON metadata lookups, 2026-05-02
- Project source files (verified): `backend/agent/graph.py`, `backend/agent/state.py`, `backend/agent/nodes/planner.py`, `backend/agent/nodes/fuel_agent.py`, `backend/agent/nodes/pricing_agent.py`, `backend/agent/nodes/response_node.py`, `backend/api/main.py`, `backend/api/routes/chat.py`, `backend/api/sse.py`, `backend/api/models.py`, `backend/agent/tools/_cache.py`, `backend/config.py`, `frontend/hooks/useChatStream.ts`, `frontend/lib/api.ts`, `frontend/components/chat/FeedbackButtons.tsx`, `frontend/types/agent.types.ts`, `data/express.db` (45-row rate distribution)
- Phase context: `.planning/phases/05-polish-observability-docs/05-CONTEXT.md`
- Phase 3/4 contracts: `.planning/STATE.md` Phase 03/04 decision log

### Secondary (MEDIUM confidence)
- LangChain Forum — Best practices for parallel nodes (fanouts): https://forum.langchain.com/t/best-practices-for-parallel-nodes-fanouts/1900
- Langfuse GitHub Discussion #8125 (session_id pattern): https://github.com/orgs/langfuse/discussions/8125
- Langfuse GitHub Discussion #2658 (custom trace_id): https://github.com/orgs/langfuse/discussions/2658
- Langfuse GitHub Discussion #3592 (CallbackHandler trace_context): https://github.com/orgs/langfuse/discussions/3592
- Medium — Parallel Nodes in LangGraph (Giuseppe Murro): https://medium.com/@gmurro/parallel-nodes-in-langgraph-managing-concurrent-branches-with-the-deferred-execution-d7e94d03ef78
- LangChain blog — Making it easier to build human-in-the-loop agents with interrupt: https://www.langchain.com/blog/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt

### Tertiary (LOW confidence — needs validation at install time)
- DEV Community / Substack tutorials on Send API patterns — confirmed against official docs above
- Tavily exception class names (UsageLimitExceededError etc.) — Open Question 3; do NOT add to retry allow-list speculatively

## Metadata

**Confidence breakdown:**
- Standard stack (libraries + versions): HIGH — all three new packages verified against PyPI on 2026-05-02; Python compat caveat called out as Open Question 1
- Architecture patterns (parallel, HITL, Langfuse, Tavily): HIGH — each pattern verified against official docs + at least one supporting source; code sketches anchored to actual repo files
- Pitfalls: HIGH for callback handler / SSE ordering / trace-id correlation (cross-verified); MEDIUM for parallel step-collision (inferred from LangGraph reducer behaviour, not seen in production reports)
- HITL threshold (500 THB default): HIGH — empirically calibrated against `data/express.db`
- Documentation deliverables: HIGH — outlines anchored to DOC-01/02/04 verbatim per CONTEXT.md
- Validation architecture: HIGH — test mapping derived from existing conftest fixtures + Phase 4 patterns

**Research date:** 2026-05-02
**Valid until:** 2026-06-02 (30 days — stable libraries; Tavily SDK and Langfuse SDK both rev frequently — re-verify versions if Phase 5 implementation slips past June)
