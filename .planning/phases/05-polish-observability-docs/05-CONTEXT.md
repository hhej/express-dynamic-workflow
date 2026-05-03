# Phase 5: Polish, Observability & Docs - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Layer four advanced agent patterns onto the working Phase 4 pipeline (parallel exec, HITL, web search, Langfuse), wire the Phase 4 feedback stub to a real backend, and produce submission-ready docs.

End state: a fresh-thread surcharge query streams a trace whose timestamps visibly prove `fuel_agent` and `route_agent` ran in parallel; high-value surcharge queries pause at a real LangGraph `interrupt()` and resume on user Approve/Deny via a sixth SSE event type; planner emits `next_step="search_context"` only when the user asks about market/news/trends, routing to a new Search Agent that pulls Tavily results into reasoning context (not into the formula); every LLM and tool call appears in Langfuse Cloud with a synchronous formula-accuracy auto-eval Score and any user thumbs vote attached as a `user_feedback` Score; `README.md` (per DOC-01 verbatim), `docs/architecture.md` (Mermaid + ASCII), `docs/data-sources.md` (new), screenshots, and `docs/demo.mp4` are complete; `v1.0` is tagged on the `main` merge commit.

**In scope (this phase):** ORCH-07 (parallel Fuel + Route via Send API), ORCH-09 (HITL approval gate), TOOL-05 (search_fuel_news / Tavily), API-05 (POST /api/feedback wire to Langfuse Score), OBS-01 (Langfuse callback handler), OBS-02 (user feedback as Langfuse score), OBS-03 (formula accuracy auto-eval), DOC-01 (README), DOC-02 (architecture.md finalised), DOC-04 (data-sources documentation).

**Out of scope (v2 / backlog):** any new capability beyond the requirements above — multi-region expansion, what-if scenarios (V2-01), rate-table versioning (V2-03), batch calc (V2-04), scheduled reports (V2-05), past-turn trace inspection, theme toggle, internationalization, conversation deletion/archive.

</domain>

<decisions>
## Implementation Decisions

### Parallel agents (ORCH-07)
- **D-01:** Send API fan-out fires ONLY when both `fuel_data` AND `route_data` are missing-or-stale on the current turn. Phase 3 D-12 cache-aware skipping takes precedence — follow-ups with fresh cache run sequentially-skip exactly as today. Trace timestamps on the fresh-thread first turn must visibly overlap; that overlap is the demo evidence for ROADMAP §Phase 5 success criterion 1.
- **D-02:** Parallel branches inherit the existing `operator.add` reducers on `reasoning_trace` and `errors` (Phase 2 Pitfall 1, Phase 3 D-05). `fuel_data` and `route_data` stay scalar dict fields with the default last-write-wins behavior; this is safe because the two branches write disjoint state keys. The plan MUST include an integration test that fans out and asserts the merged state has BOTH `fuel_data` and `route_data` populated. No new reducers introduced.
- **D-03:** Phase 3 D-22/D-23 `RetryPolicy` and `phase3_retry_on` allow-list apply unchanged to both parallel branches. Phase 3 D-24 `_wrap_error_sink` applies unchanged — one branch failing routes that branch's error to `state.errors` while the other branch succeeds; planner sees a partial state on the next loop and clarifies or proceeds.

### HITL approval gate (ORCH-09)
- **D-04:** Trigger condition is a single env-driven scalar threshold: `surcharge_result.total > HITL_TOTAL_THB_THRESHOLD`. Configurable in `backend/config.py` and `.env.example`. Default value is **Claude's Discretion** — calibrate after inspecting `data/express.db` rate distribution; given Phase 1 rate range 50–698 THB and the 15% cap, ballpark 500–700 THB total to gate ~5–10% of demo queries (enough to demo, not enough to spam approval prompts).
- **D-05:** Gate placement: between `pricing_agent` and `response_node`, implemented via LangGraph's native `interrupt()` primitive (NOT a state flag). The `interrupt()` primitive showcases LangGraph's checkpointer + HITL pattern — strong signal for the 35% Agent Architecture rubric.
- **D-06:** Gate UX is a new sixth SSE event type. Backend emits `data: {"type":"approval_required","payload":{"surcharge_result": {...}, "thread_id": "..."}}\n\n` immediately before suspending. Frontend renders inline Approve / Deny buttons in the assistant turn. Resume via `POST /api/chat` with `{thread_id, approve: true|false}` (existing endpoint, new optional `approve` body field) which calls `graph.ainvoke(Command(resume=...), config)`. Adds `approval_required` as a sixth event alongside Phase 3 D-18's `meta|trace|answer|error|done`.
- **D-07:** Approval state. New `AgentState` field `approval_decision: Optional[Literal["approve","deny"]]`. On `approve` → graph proceeds to `response_node` with `surcharge_result` intact. On `deny` → `response_node` renders a "User declined the recommended surcharge — review and adjust" prose with `status="partial"` (Phase 3 D-12 status vocabulary); no surcharge breakdown table in the markdown.
- **D-08:** Trace step. The gate emits one D-12-shape trace entry (`agent="hitl_gate"`, `tool="interrupt"`, `tool_output={threshold, total, decision_pending: true}`). After resume, a second trace entry records `decision: "approve"|"deny"` so the audit trail is complete. Phase 4 D-08's "trace panel = current-turn only" is preserved — the resume request emits its own fresh trace stream that carries the approval decision.

### Tavily search (TOOL-05)
- **D-09:** Trigger semantics. Planner emits `next_step="search_context"` ONLY when its `user_intent` classifier identifies a news/market/trend question (e.g. "why is fuel up", "diesel news", "market trends"). Standard `surcharge_query` and `followup_query` paths NEVER trigger search by default. Conserves Tavily free-tier quota (1000 searches/month) and Gemini RPM. Demo prompt to include in README/example prompts: *"What's driving diesel prices this week?"*.
- **D-10:** New dedicated Search Agent node at `backend/agent/nodes/search_agent.py`, mirroring the Phase 2 Fuel/Route narration pattern: LLM-narrate Tavily results with the D-11 deterministic fallback, emit ONE D-12-shape trace entry (`agent="search_agent"`, `tool="search_fuel_news"`). Phase 3 D-01 already keeps `"search_context"` in `PlannerOutput.next_step`; today it routes to `response` as a stub — Phase 5 re-routes it to `search_agent` and adds `search_agent → planner` per Phase 3 D-03 loop.
- **D-11:** Search effect = reasoning context only, never a formula input. Tavily output lands in a new `AgentState` field `search_context: Optional[Dict]` shaped `{query, summary, sources: [{title, url, snippet, published_at}], fetched_at}`. Search Agent narrates a 1–2 sentence "market context" line; `response_node` prepends it ABOVE the prose summary in the markdown answer when present. The surcharge formula stays untouched — `calculate_surcharge` remains the deterministic, unit-testable Phase 1 pure function.
- **D-12:** Quota and failure handling. Tavily client wraps `backend/agent/tools/_cache.py::TTLCache` (Phase 2 D-07) keyed on the normalized query string, default 30 min (`SEARCH_CACHE_TTL_SECONDS=1800`). On Tavily API error or rate-limit: trace entry `status="warn"`, `search_context` stays `None`, planner continues. **Search failure NEVER blocks the surcharge response.** Aligns with Phase 3 D-22/D-23 retry topology (Tavily-specific retryable exceptions added to `phase3_retry_on`'s allow-list) and Phase 3 D-24 graceful fallback discipline.

### Langfuse observability (OBS-01..03)
- **D-13:** Deployment is Langfuse Cloud free tier (`https://cloud.langfuse.com`). Three new env vars in `.env.example`: `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`. The agent MUST run identically without keys (graceful no-op) so PROJECT.md's local-reproducibility constraint is preserved. Implementation: `backend/agent/observability.py` initialises the Langfuse client only when all three keys are present; otherwise the callback handler is a no-op stub.
- **D-14:** Trace coverage = single `langfuse.langchain.CallbackHandler` registered at the `graph.compile()` boundary inside `backend/agent/graph.py` (or at the chat-handler invocation — exact insertion point is planner's call). Captures every Gemini structured-output call (Planner, Fuel, Route, Pricing, Response, Search) AND every `@tool` invocation (`fetch_fuel_price`, `calculate_route`, `lookup_rate`, `calculate_surcharge`, `search_fuel_news`). One Langfuse trace per chat turn, named `chat_turn_{thread_id}_{turn_idx}` so the feedback wire (D-16) can resolve `trace_id` deterministically.
- **D-15:** OBS-03 formula-accuracy auto-eval mechanic. After `pricing_agent` completes, run `calculate_surcharge` (Phase 1 pure function imported directly from `backend/agent/tools/calculate_surcharge.py`, NOT via the `@tool` wrapper) with the same inputs. Compare against the agent's `surcharge_result` within float tolerance (1e-6). Attach a Score to the live Langfuse trace: `name="formula_accuracy"`, `value=1.0` on match else `0.0` with a `reason` string capturing the divergence. Microsecond cost, 100% coverage, demonstrable in Langfuse dashboard during demo. Score posting MUST be fire-and-forget — auto-eval failure cannot block or fail the user response.
- **D-16:** API-05 feedback wire. New `backend/api/routes/feedback.py` exposes `POST /api/feedback` accepting `{thread_id, message_id, score, reason?}` matching Phase 4 D-17 localStorage payload shape verbatim. Resolves the matching Langfuse trace via the deterministic name from D-14; calls `langfuse.score(trace_id=..., name="user_feedback", value=1|-1, comment=reason)`. Returns 200 immediately — synchronous (low traffic, simple error surface, no queue). Phase 4 `frontend/components/chat/FeedbackButtons.tsx` swaps its localStorage handler to `api.postFeedback` with no other UI changes (Phase 4 D-17 anticipated this).

### Documentation & v1.0 submission (DOC-01/02/04)
- **D-17:** README scope per DOC-01 verbatim: project overview → team → problem statement → agent design (with Mermaid diagram + brief prose) → data sources (link to `docs/data-sources.md`) → setup instructions (env vars, Python install, npm install, run backend, run frontend, run tests) → AI tools used (Cursor / Claude Code / Claude Agent SDK / etc, with rationale per AI/Vibe-Coding 15% rubric) → limitations → license. Maps 1:1 to DOC-01's enumerated contents. README copy uses "Bangkok Metro" everywhere (backlog 999.2).
- **D-18:** `docs/architecture.md` diagram style = Mermaid + keep current ASCII as fallback. Add Mermaid `flowchart` for the graph topology including Phase 5 parallel branches and HITL gate, `sequenceDiagram` for the SSE event flow including the new `approval_required` event, and a `flowchart` showing the Langfuse callback boundary. Mermaid renders natively on GitHub for graders; ASCII stays for terminal-readable fallback during live demo. The Conditional Routing table, AgentState schema, Memory Management, and Error Handling sections must be updated to reflect Phase 5 changes (parallel, HITL, search agent, Langfuse callback).
- **D-19:** Data source documentation lives in `docs/data-sources.md` (new file per DOC-04). Sections: EPPO source URL + scrape/download mechanics + refresh cadence; `generate_rate_table.py` simulation assumptions (zone multipliers 1.0/1.25/1.55, weight tiers, baseline 29.94 THB/L); Google Maps Directions API usage + 15-min cache; Tavily search query template + 30-min cache. README links to it from the data-sources section.
- **D-20:** Demo artifact = static screenshots embedded in README + a 1–2 minute screen recording. Screenshots: chat with surcharge breakdown table, trace panel mid-stream, dashboard fuel chart + surcharge history chart, HITL approval prompt, Langfuse trace view. Recording at `docs/demo.mp4` shows one fresh-thread surcharge query end-to-end including the parallel trace timestamps and a HITL approval. README references both. Recording targets W5 code freeze; W6 final demo can replay it as a fallback if the live demo hits a free-tier rate limit.
- **D-21:** v1.0 git tag protocol. After all DOC-* are merged on `develop`: merge `develop → main`, tag `v1.0` on the merge commit (annotated tag with submission deliverables checklist in the message), push the tag. Only the IT Lead pushes the tag. Tag annotation message format: `v1.0 — MADT7204 final submission. Includes: README per DOC-01, architecture.md, data-sources.md, demo.mp4. Backend tests: <count> passing. Frontend e2e: passing.`

### Claude's Discretion
- Exact `HITL_TOTAL_THB_THRESHOLD` default value — calibrate after inspecting `data/express.db` rate distribution; aim for 5–10% of representative demo queries triggering the gate. Ballpark 500–700 THB total given Phase 1 rate range 50–698 THB and the 15% cap.
- Module split for the Search Agent (single file vs. package with separate `tavily_client.py`) — follow existing `backend/agent/nodes/<name>.py` + `backend/agent/tools/<name>.py` convention.
- Tavily SDK choice — official `tavily-python` matches PROJECT.md tech-stack reference; raw httpx is acceptable if the SDK pulls in heavy transitive deps.
- Mermaid diagram fidelity — must show parallel branches, HITL gate, search agent, Langfuse callback boundary; level of detail beyond that is open.
- Demo recording tool (QuickTime, Loom, OBS, etc.) — open as long as the artifact lands at `docs/demo.mp4` (or `.gif`) at 1080p+.
- Plan ordering across the four sub-domains (parallel → HITL → search → Langfuse → docs vs. Langfuse-first vs. docs-last) — planner picks based on dependency analysis. Suggestion: Langfuse callback wiring is independent and demo-able first; docs land last because they describe completed code.
- Inline UI affordance for the HITL prompt (dedicated `ApprovalCard.tsx` vs. inline buttons inside `MessageList.tsx`) — both fit Phase 4 D-12 status-card pattern.
- Whether `response_node` deny path includes the original surcharge_result as a "Show declined recommendation" debug affordance.
- Exact prompt-engineering for the Tavily query construction (LLM-generated query vs. fixed template + user message).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & API contract
- `docs/architecture.md` — Agent Graph Flow, Conditional Routing table (`next_step` vocab including `search_context`), API Endpoints table, Memory Management section, Error Handling section. **Phase 5 D-18 updates this file** with Mermaid + Phase 5 changes (parallel branches, HITL gate, search agent, Langfuse callback).

### Phase inputs from earlier phases
- `.planning/phases/03-graph-assembly-api-layer/03-CONTEXT.md` — Phase 3 locked decisions, especially:
  - **D-01** `PlannerOutput` schema — `next_step` already includes `search_context` — drives D-09/D-10 above
  - **D-03** Planner-loop topology — `search_agent` slots in via this loop; HITL `interrupt()` slots between `pricing_agent` and `response`
  - **D-04** `PLANNER_MAX_ITERATIONS=6` — Phase 5 must verify the cap still holds when `search_context` is added on a search-bearing turn
  - **D-05** AgentState v2 fields (`origin`, `destination`, `errors` with `operator.add`) — Phase 5 adds `approval_decision` (D-07), `search_context` (D-11)
  - **D-12** Cache-aware planner reuse on follow-ups — drives D-01 (parallel only when both stale)
  - **D-13** `fetched_at` ISO-8601 UTC `Z` annotation pattern — Phase 5 reuses for `search_context.fetched_at`
  - **D-15** AsyncSqliteSaver checkpointer — REQUIRED for HITL `interrupt()` resume across requests
  - **D-17** SSE event granularity (one event per node completion via `astream_events`) — drives D-06 (`approval_required` event) and D-14 (Langfuse callback at this boundary)
  - **D-18** Typed SSE envelope `{type, payload}` — drives D-06 sixth event type
  - **D-19** thread_id flow + first `meta` event — drives D-06 resume contract `{thread_id, approve}`
  - **D-22 / D-23** RetryPolicy + `retry_on` allow-list — drives D-03 (parallel reuses these) and D-12 (Tavily errors added to allow-list)
  - **D-24** error-sink + `state.errors` — drives D-03 (parallel branch failure handling)
- `.planning/phases/04-frontend-reasoning-trace/04-CONTEXT.md` — Phase 4 decisions, especially:
  - **D-08** Trace panel = current-turn only — preserved by Phase 5 D-08 (resume turn = own trace stream)
  - **D-13** UI does NOT separately render `surcharge_result` JSON — preserved
  - **D-17** Feedback localStorage payload `{thread_id, message_id, score, reason?}` — drives D-16 wire shape
  - **D-18** UI-05 traceability stays Phase 4; Phase 5 owns the wire — drives D-16

### Implementation source files (Phase 5 extends, does not rewrite)
- `backend/agent/graph.py` — Phase 3 `_wrap_error_sink`, `phase3_retry_on`, `RetryPolicy`. Phase 5 extends with: conditional Send fan-out from Planner (D-01), `interrupt()` between `pricing_agent` and `response` (D-05), `search_agent` node + edges (D-10), Langfuse `CallbackHandler` registration (D-14).
- `backend/agent/state.py` — `AgentState` TypedDict. Phase 5 adds: `approval_decision: Optional[Literal["approve","deny"]]` (D-07), `search_context: Optional[Dict]` (D-11).
- `backend/agent/nodes/planner.py` — Phase 5 extends `user_intent` classification to detect news/trend questions (D-09); emits parallel Send pair when both fuel and route are stale (D-01).
- `backend/agent/nodes/response_node.py` — Phase 5 reads `search_context` (prepend market-context line per D-11); reads `approval_decision` (D-07: `deny` renders `status="partial"` + decline prose).
- `backend/api/routes/chat.py` — Phase 5 adds: sixth SSE event type `approval_required` (D-06); accepts optional `approve: bool` in body for resume; binds Langfuse trace name `chat_turn_{thread_id}_{turn_idx}` per D-14.
- `backend/api/main.py` — Phase 5 includes new feedback router; verify CORSMiddleware (Phase 4 in-band fix, commit `750cf5d`) covers `POST /api/feedback`.
- `backend/api/models.py` — Phase 5 adds `FeedbackRequest`, `ApprovalRequest` Pydantic models.
- `backend/api/sse.py` — SSE framing helper; reuse for `approval_required` event.
- `backend/agent/tools/_cache.py` — `TTLCache`; Phase 5 reuses for Tavily query cache (D-12).
- `backend/agent/tools/calculate_surcharge.py` — Phase 1 pure function; **D-15 reuses as the auto-eval oracle (do not import via `@tool` wrapper)**.
- `backend/agent/llm.py` — `get_chat_model()` factory + `FakeMessagesListChatModel` test seam (Phase 2 D-15) — Phase 5 Search Agent tests reuse.
- `backend/config.py` — Phase 5 adds: `HITL_TOTAL_THB_THRESHOLD`, `SEARCH_CACHE_TTL_SECONDS`, `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `TAVILY_API_KEY`.
- `frontend/components/chat/FeedbackButtons.tsx` — Phase 4 stub; Phase 5 swaps localStorage handler to `api.postFeedback` (D-16).
- `frontend/lib/api.ts` — Phase 5 adds `postFeedback({thread_id, message_id, score, reason?})`; extends SSE event union with `approval_required`.
- `frontend/hooks/useChatStream.ts` — Phase 5 handles `approval_required`; exposes `approve(threadId, decision)` callback that calls `POST /api/chat` with the resume body.

### Requirements & project framing
- `.planning/REQUIREMENTS.md` — Phase 5 scope: ORCH-07, ORCH-09, TOOL-05, API-05, OBS-01, OBS-02, OBS-03, DOC-01, DOC-02, DOC-04
- `.planning/PROJECT.md` — Tech stack lock (Gemini 15 RPM, free-tier APIs only, local reproducibility); grading rubric weights (Agent Architecture 35%, Data Integration 20%, Documentation/Git Practice 20%, AI/Vibe-Coding 15%, Team Tech Leadership 10%); v1.0 tag at submission
- `.planning/ROADMAP.md` §Phase 5 — five success criteria (parallel observable, HITL gate, Langfuse traces, feedback in Langfuse, docs complete)

### Coding conventions
- `.planning/codebase/CONVENTIONS.md` §Python — PEP 8, Black, Google-style docstrings, `from __future__ import annotations`, TypedDict + Pydantic patterns; §TypeScript — PascalCase.tsx components, useX.ts hooks, camelCase.ts utilities, `*.types.ts`
- `.planning/codebase/STRUCTURE.md` — `backend/agent/nodes/` (Search Agent), `backend/agent/tools/` (search_fuel_news), `backend/api/routes/` (feedback endpoint), `frontend/components/chat/` (HITL approval inline UI), `docs/` (data-sources.md, demo.mp4 land here)
- `.planning/codebase/STACK.md` — Tailwind, Recharts, Node 18+, npm, locked LLM provider

### Backlog
- `.planning/ROADMAP.md` §Backlog 999.2 — "Bangkok Metro" phrasing in ALL Phase 5 user-facing copy AND new Phase 5 docs (README, architecture.md, data-sources.md, demo captions). NEVER "Central Region". Internal `central-1/2/3` zone IDs are not user-facing — they appear only in trace step `tool_input/tool_output` JSON.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/agent/graph.py` — Phase 3 `_wrap_error_sink`, `phase3_retry_on`, `RetryPolicy(max_attempts=2, backoff_factor=2.0)` are unchanged contracts; Phase 5 EXTENDS without rewriting (parallel Send fan-out, HITL `interrupt()`, search agent edge, Langfuse callback registration).
- `backend/agent/state.py` — `operator.add` reducer pattern proven (Phase 2 Pitfall 1, Phase 3 D-05). Phase 5 reuses for any new list field. New scalar fields (`approval_decision`, `search_context`) default to last-write-wins, which is safe given they are written from a single node each.
- `backend/agent/tools/_cache.py::TTLCache` — Phase 2 thread-safe; Phase 5 wraps the Tavily client in this same TTLCache (D-12).
- `backend/agent/llm.py::get_chat_model()` + `FakeMessagesListChatModel` test seam — Phase 5 Search Agent + HITL gate tests reuse the seam exactly as Fuel/Route/Pricing did.
- `backend/agent/nodes/fuel_agent.py` / `route_agent.py` — narration pattern reference (LLM-narrate + D-11 fallback + single D-12 trace entry). Search Agent copies this shape.
- `backend/api/routes/chat.py` — SSE handler pattern; Phase 5 extends with sixth event type and optional `approve` body field. No rewrite.
- `backend/api/sse.py::format_sse()` — manual SSE framing helper (Phase 3 Plan 03-04 Pitfall 5); reuse for `approval_required` events.
- `backend/agent/tools/calculate_surcharge.py` — Phase 1 pure function; D-15 reuses as auto-eval oracle (do NOT import via the `@tool` wrapper — that goes through the agent path, defeating independence).
- `frontend/components/chat/FeedbackButtons.tsx` — Phase 4 stub UI is ready; only the click handler swaps in Phase 5.
- `frontend/components/chat/MarkdownAnswer.tsx` — Phase 5 prepends `search_context.summary` line above the prose when present (one-line addition; the existing react-markdown + remark-gfm path handles whatever prose tone Search Agent emits).
- `frontend/components/trace/TracePanel.tsx` + `TraceStep.tsx` — Phase 5 trace entries (`agent="search_agent"`, `agent="hitl_gate"`) automatically render via the existing TraceStep component; no UI change needed (Phase 4 D-07 was designed to be agent-agnostic).
- `frontend/hooks/useChatStream.ts` — already a `useReducer` over SSE events; Phase 5 adds an `APPROVAL_REQUIRED` action and an `approve()` callback without changing the existing event-routing shape.

### Established Patterns
- LangGraph node = read state → optionally call tool → narrate via Gemini with D-11 fallback → emit ONE D-12-shape trace entry → return partial state dict (LangGraph reducer merges). Search Agent and the HITL gate's synthetic trace entry follow this.
- Phase 3 D-22 RetryPolicy applied uniformly to every node — Search Agent gets the same; the HITL gate is `interrupt()`-driven (not retried).
- TTLCache pattern — Phase 2 D-07 (route 15 min) + Phase 5 D-12 (search 30 min); env-driven TTL constants.
- ISO-8601 UTC `Z` `fetched_at` (Phase 3 D-13) — Phase 5 D-11 `search_context.fetched_at` follows.
- Env-driven config constants in `backend/config.py` — Phase 5 adds the six listed in the canonical refs section.
- "Bangkok Metro" phrasing convention (resolved backlog 999.2) — applies to README, architecture.md, data-sources.md, demo captions, and any user-facing FE copy added in Phase 5 (HITL approval prompt, search-context summary).
- `from __future__ import annotations` in all new Python files.
- Pure functions raise `ValueError` on invalid input; Phase 3 D-23 explicitly skips ValueError from retries — Phase 5 must NOT add ValueError to the retry allow-list when extending `phase3_retry_on` for Tavily errors.

### Integration Points
- `backend/agent/nodes/search_agent.py` (new) — TOOL-05 narration node; mirrors fuel_agent / route_agent
- `backend/agent/tools/search_fuel_news.py` (new) — Tavily API wrapper + TTLCache + Pydantic IO models
- `backend/agent/tools/models.py` — add `SearchInput`, `SearchResult`, `SearchSource` Pydantic models
- `backend/agent/state.py` — add `approval_decision`, `search_context` fields
- `backend/agent/graph.py` — extend with: conditional Send fan-out from Planner (D-01), `interrupt()` after `pricing_agent` (D-05), `search_agent` node + edges (D-10), Langfuse `CallbackHandler` at compile (D-14)
- `backend/agent/nodes/planner.py` — extend `user_intent` classification to detect news/trend questions; emit Send pair when both fuel + route are stale; conditional `next_step="search_context"` per D-09
- `backend/agent/nodes/response_node.py` — read `search_context` (prepend market-context line per D-11), read `approval_decision` (D-07: `deny` renders `status="partial"` + decline prose)
- `backend/agent/observability.py` (new) — Langfuse client init, graceful no-op when keys missing, auto-eval helper for D-15
- `backend/api/routes/chat.py` — sixth SSE event type `approval_required` (D-06); accept optional `approve: bool` in body for resume; bind Langfuse trace name `chat_turn_{thread_id}_{turn_idx}` per D-14
- `backend/api/routes/feedback.py` (new) — POST /api/feedback handler per D-16
- `backend/api/main.py` — include feedback router; CORSMiddleware already covers POST verbs (Phase 4 in-band fix)
- `backend/api/models.py` — add `FeedbackRequest`, `ApprovalRequest` Pydantic models
- `backend/config.py` — add HITL_TOTAL_THB_THRESHOLD, SEARCH_CACHE_TTL_SECONDS, LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, TAVILY_API_KEY constants
- `requirements.txt` — add `langfuse`, `tavily-python` (or use raw httpx if SDK transitive deps are heavy)
- `backend/tests/test_search_agent.py`, `test_hitl_gate.py`, `test_parallel_fanout.py`, `test_observability.py`, `test_api_feedback.py` (new)
- `frontend/lib/api.ts` — add `postFeedback()`; extend SSE event type union with `approval_required`
- `frontend/hooks/useChatStream.ts` — handle `approval_required`; expose `approve(threadId, decision)` callback that calls `POST /api/chat` with the resume body
- `frontend/components/chat/MessageList.tsx` (or new `frontend/components/chat/ApprovalCard.tsx`) — render Approve / Deny inline UI when `approval_required` event seen; route click to `useChatStream.approve()`
- `frontend/components/chat/FeedbackButtons.tsx` — swap localStorage handler to `api.postFeedback`
- `frontend/components/chat/MarkdownAnswer.tsx` — render `search_context.summary` above prose when present
- `.env.example` — add `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `TAVILY_API_KEY`, `HITL_TOTAL_THB_THRESHOLD`, `SEARCH_CACHE_TTL_SECONDS`
- `README.md` — full rewrite per DOC-01 verbatim (D-17)
- `docs/architecture.md` — Mermaid + ASCII update for Phase 5 (D-18)
- `docs/data-sources.md` (new) — DOC-04 data source documentation (D-19)
- `docs/demo.mp4` (new) — D-20 demo recording artifact

</code_context>

<specifics>
## Specific Ideas

- "Visible reasoning is what makes this agentic" (PROJECT.md Core Value) drives both the parallel-trace-timestamps demo (D-01) and the visible gate-pause in the trace (D-08). Both are explicit grading-rubric levers for the 35% Agent Architecture score.
- Cache-reuse demo is preserved — a follow-up like *"What about Retail Fast?"* on the same `thread_id` still skips Fuel + Route per Phase 3 D-12. Parallel only fires on turn 1 of fresh threads. The README example prompts should include both a fresh-thread surcharge query (to demo parallel) AND a follow-up (to demo cache reuse), exactly as Phase 4 D-09 already structured the empty-state prompts.
- The HITL gate adds a SIXTH SSE event type (`approval_required`) beyond the five enumerated in Phase 3 D-18 (`meta|trace|answer|error|done`). Document this explicitly in any API schema artifact and in `docs/architecture.md` so the Phase 4 frontend doesn't get a surprise event class.
- Auto-eval oracle (D-15) reuses the EXACT Phase 1 pure function (`backend/agent/tools/calculate_surcharge.py`), NOT the `@tool` wrapper. The `@tool` wrapper goes through the agent invocation path; using it as the oracle would defeat the independence the eval is meant to demonstrate.
- Bangkok Metro phrasing (resolved backlog 999.2) applies to README, architecture.md, data-sources.md, demo recording captions, the HITL approval prompt copy, and the search-context summary copy — NEVER "Central Region". Internal `central-1/2/3` IDs are fine in code, trace JSON, and rate-table SQL.
- v1.0 tag is THE submission deliverable. Tag the merge commit on `main`, not on `develop`. Annotation message includes the deliverable checklist (README, architecture.md, data-sources.md, demo.mp4, backend test count, frontend e2e status).
- Langfuse trace name `chat_turn_{thread_id}_{turn_idx}` is the load-bearing convention that lets D-16 feedback wire resolve `trace_id` deterministically without an extra DB lookup. Both D-14 and D-16 must keep this format in lockstep — a rename in either place breaks feedback scoring.
- Tavily added to `phase3_retry_on` allow-list (D-12) MUST be done by adding the specific Tavily exception class (e.g., `tavily.exceptions.HTTPError` or `httpx.HTTPError` if the SDK uses raw httpx) — NOT by adding `Exception` or `BaseException`, which would break Phase 3 D-23's deliberate ValueError exclusion.

</specifics>

<deferred>
## Deferred Ideas

- Multi-region beyond Bangkok Metro (V2-02) — v2 (PROJECT.md Out of Scope)
- What-if scenario queries (V2-01) — v2
- Rate table versioning for historical surcharge accuracy (V2-03) — v2
- Batch surcharge calculation for multiple routes (V2-04) — v2
- Email / scheduled surcharge reports (V2-05) — v2
- Past-turn trace inspection (Phase 4 D-08 deferred) — Phase 5 does NOT pick this up. Langfuse traces (D-14) cover much of the audit need externally; if a downstream user wants per-turn trace replay in the FE, it's a v2 backend D-21 extension.
- Backend `/api/surcharge-history` endpoint (Phase 4 D-15.2 derives client-side) — Phase 5 does NOT tackle this. No signal yet that the client-side derivation is painful in dev.
- Theme toggle (light / dark) — future
- Internationalization (Thai locale) — future
- Conversation deletion / archive — out of scope for v1
- HITL approval timeout / auto-escalation — explicitly rejected during discussion (auto-approve was a weak grading signal). v2 if a real workflow ever needs SLA-bound approvals.
- Tavily prompt-engineering tuning beyond a basic query template — future iteration
- Self-hosted Langfuse migration — deferred unless cloud free tier proves insufficient
- Background-task or batch-flush feedback wire — explicitly rejected during discussion (Phase 4 D-17 array shape stays as a localStorage append, but the wire is synchronous one-vote-at-a-time)
- Trace-only Tavily output (no user-facing surface) — explicitly rejected during discussion (would hide the demo value)
- Influencing baseline diesel price from Tavily news — explicitly rejected during discussion (would couple LLM judgment to the deterministic formula)
- Auto-augment search on every surcharge query — explicitly rejected during discussion (Tavily quota + Gemini RPM exhaustion risk)

### Reviewed Todos (not folded)
None — `gsd-tools todo match-phase 5` returned 0 matches.

</deferred>

---

*Phase: 05-polish-observability-docs*
*Context gathered: 2026-05-02*
