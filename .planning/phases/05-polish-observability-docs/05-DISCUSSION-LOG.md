# Phase 5: Polish, Observability & Docs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 05-polish-observability-docs
**Areas discussed:** Parallel agents + HITL gate, Tavily search, Langfuse observability, Docs & v1.0 submission

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Parallel agents + HITL gate | ORCH-07 (Send API fan-out for Fuel+Route) + ORCH-09 (high-value approval gate) | ✓ |
| Tavily search (TOOL-05) | search_fuel_news tool + planner integration | ✓ |
| Langfuse observability (OBS-01..03 + API-05) | Callback handler scope, formula auto-eval, feedback wire | ✓ |
| Docs & v1.0 submission (DOC-01/02/04) | README scope, architecture.md style, data-sources doc, demo artifacts, v1.0 tag | ✓ |

**User's choice:** All four areas selected.

---

## Parallel agents + HITL gate

### Q: When should Send API fan-out actually fire (parallel Fuel + Route)?

| Option | Description | Selected |
|--------|-------------|----------|
| Both missing/stale + same turn | Cache-aware skipping (D-12) takes precedence; parallel fires only when both fuel and route data are missing/stale on the current turn | ✓ |
| Always fan out when either is needed | If either fuel OR route is needed, fan out both — wastes a no-op branch but the trace always shows parallelism on data-fetch turns | |
| Fan out unconditionally on every surcharge_query | Both branches always fire; ignores cache; contradicts Phase 3 D-12 | |

**User's choice:** Both missing/stale + same turn (Recommended).
**Notes:** Preserves Phase 3 D-12 cache-aware skipping for follow-ups; parallel demos on fresh-thread first turn only. Realistic and matches conversation-memory rubric.

### Q: What threshold triggers the human-in-the-loop approval gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Total THB above configurable cap | Single env constant `HITL_TOTAL_THB_THRESHOLD`; surcharge_result.total > threshold → gate fires | ✓ |
| Surcharge percent above cap | Trigger when surcharge_pct > X% — most queries hit cap=15% so gate would fire constantly | |
| Multi-factor (THB + weight + capped) | Compound rule on multiple dimensions — richer demo, more code paths | |
| Bounce-only above THB threshold | Gate only on Bounce shipments; adds a shipping-type branch | |

**User's choice:** Total THB above configurable cap (Recommended).
**Notes:** Single env scalar `HITL_TOTAL_THB_THRESHOLD`; default left as Claude's Discretion (calibrate against rate distribution; ballpark 500–700 THB given Phase 1 rate range 50–698 THB).

### Q: How does the user actually approve / deny in the UI?

| Option | Description | Selected |
|--------|-------------|----------|
| LangGraph `interrupt()` + new SSE event | Native interrupt() between Pricing and Response; sixth SSE event type `approval_required`; resume via `Command(resume=...)` | ✓ |
| State flag + Response Node renders gate prompt | Add `state.requires_approval=true`; user replies "approve"/"deny" in next turn | |
| Auto-approve after N seconds | Cosmetic gate that auto-resumes — weak grading signal | |

**User's choice:** LangGraph `interrupt()` + new SSE event (Recommended).
**Notes:** Showcases LangGraph's checkpointer + HITL primitive — strongest signal for the 35% Agent Architecture rubric.

### Q: Are there state collisions beyond reasoning_trace + errors that the Send fan-out has to handle?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — audit fuel_data, route_data, fetched_at writes | Scalars are safe by construction (disjoint key writes); document invariant in plan; add integration test that asserts merged state has BOTH | ✓ |
| Yes — add reducers to fuel_data/route_data too | Defensive custom reducers that pick the non-None side | |
| No — reasoning_trace + errors are the only shared writes | Trust Phase 3 D-05 setup as-is; rely only on existing tests | |

**User's choice:** Yes — audit fuel_data, route_data, fetched_at writes (Recommended).
**Notes:** No new reducers. Plan must include integration test verifying merged state contains both fuel_data and route_data after fan-out.

---

## Tavily search (TOOL-05)

### Q: When should Planner emit `next_step="search_context"` (i.e., when does Tavily fire)?

| Option | Description | Selected |
|--------|-------------|----------|
| Intent-driven — user asks about news/trends | Planner emits search_context only when user_intent classifier detects news/market questions; conserves quota and demo-able with one explicit prompt | ✓ |
| Auto-augment when fuel delta is large | Run Fuel Agent first; if delta_pct > 5%, emit search_context for context | |
| Always run on first turn of every thread | Treat search as standard reasoning context — burns quota fast | |
| Optional follow-up only | User must explicitly ask "tell me why" as a follow-up turn | |

**User's choice:** Intent-driven — user asks about news/trends (Recommended).
**Notes:** Demo prompt: "What's driving diesel prices this week?". Conserves Tavily 1000/mo free quota and Gemini RPM.

### Q: Where does the search live in the graph?

| Option | Description | Selected |
|--------|-------------|----------|
| New dedicated Search Agent node | New `backend/agent/nodes/search_agent.py` mirroring Fuel/Route pattern; routes via existing `search_context` next_step | ✓ |
| Fold into Fuel Agent | Add search_fuel_news as second tool inside Fuel Agent — couples search to fuel-only context | |
| Pre-Planner enrichment middleware | Run search before Planner — diverges from D-03 loop topology | |

**User's choice:** New dedicated Search Agent node (Recommended).
**Notes:** Mirrors Fuel/Route narration pattern — easy to test, isolated quota concerns.

### Q: How does search output influence the agent's output?

| Option | Description | Selected |
|--------|-------------|----------|
| Reasoning context only — prose + trace, not surcharge math | Tavily lands in state.search_context; narration prepended to markdown answer; calc stays deterministic | ✓ |
| Influence baseline diesel price | Use search to detect spike news → adjust BASELINE_DIESEL_PRICE for the calc | |
| Trace-only, no user-facing surface | Tavily output appears only in reasoning_trace JSON; final answer unchanged | |

**User's choice:** Reasoning context only — prose + trace, not surcharge math (Recommended).
**Notes:** Surcharge formula stays deterministic and unit-testable. Search is reasoning context only.

### Q: Quota and fallback strategy for Tavily?

| Option | Description | Selected |
|--------|-------------|----------|
| TTL cache + graceful skip on failure | Reuse Phase 2 _cache.py TTLCache; on error: trace status='warn', skip search_context, planner continues | ✓ |
| No cache, hard-fail on rate limit | Always live-search; rate-limit becomes user-visible error | |
| Cache + retry only (no skip path) | Cache + Phase 3 retry policy, but exhausted retries surface to user | |

**User's choice:** TTL cache + graceful skip on failure (Recommended).
**Notes:** SEARCH_CACHE_TTL_SECONDS=1800 default. Search failure NEVER blocks the surcharge response.

---

## Langfuse observability (OBS-01..03 + API-05)

### Q: Langfuse deployment: cloud free tier or self-hosted Docker?

| Option | Description | Selected |
|--------|-------------|----------|
| Cloud free tier | cloud.langfuse.com; three new env vars; graceful no-op when keys missing; preserves local-reproducibility | ✓ |
| Self-hosted Docker | Full data control but adds infra + Docker dependency | |
| Conditional — cloud or in-memory shim | Cloud when keys present, JSON-file shim otherwise; adds maintenance burden | |

**User's choice:** Cloud free tier (Recommended).
**Notes:** Aligns with PROJECT.md "free-tier APIs only". Three env vars: LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY.

### Q: What gets traced in Langfuse?

| Option | Description | Selected |
|--------|-------------|----------|
| Single CallbackHandler covers every LLM + tool call | langfuse.langchain.CallbackHandler at graph.compile() boundary; one trace per chat turn named `chat_turn_{thread_id}_{turn_idx}` | ✓ |
| Manual span instrumentation only on agent nodes | Wrap each node body with langfuse.start_span() — boilerplate in 5+ files | |
| LLM calls only — skip tool spans | Trace only Gemini calls; loses tool-invocation visibility | |

**User's choice:** Single CallbackHandler covers every LLM + tool call (Recommended).
**Notes:** Trace name convention is load-bearing for D-16 feedback wire to resolve trace_id deterministically.

### Q: OBS-03 formula accuracy auto-eval mechanic?

| Option | Description | Selected |
|--------|-------------|----------|
| Synchronous independent recompute on every query | Run Phase 1 pure function as oracle; attach Score to live trace; microsecond cost | ✓ |
| Async batch eval (cron over recent traces) | Daily script samples last N traces and posts scores | |
| CI / test-suite only (no production eval) | Eval only fires in pytest — doesn't satisfy OBS-03 | |

**User's choice:** Synchronous independent recompute on every query (Recommended).
**Notes:** Reuse `backend/agent/tools/calculate_surcharge.py` (Phase 1 pure function), NOT the @tool wrapper. Score is fire-and-forget; never blocks user response.

### Q: POST /api/feedback (API-05) implementation shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Synchronous + Langfuse score on the trace | Resolve trace_id via deterministic name; call langfuse.score(); return 200 immediately | ✓ |
| Background task via FastAPI BackgroundTasks | Endpoint returns 200 immediately, score posts in background | |
| Batch flush on next chat request | Frontend keeps batching; flushes on next /api/chat — confuses contract | |

**User's choice:** Synchronous + Langfuse score on the trace (Recommended).
**Notes:** Frontend swaps `FeedbackButtons.tsx` localStorage handler to `api.postFeedback` (Phase 4 D-17 anticipated this).

---

## Docs & v1.0 submission (DOC-01/02/04)

### Q: README.md scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Full per DOC-01 brief | Project overview → team → problem statement → agent design → data sources → setup → AI tools used → limitations → license | ✓ |
| Setup-only README, design lives in docs/ | Lean README; design content elsewhere | |
| Full README + duplicate design in docs/architecture.md | Comprehensive everywhere; duplicate maintenance burden | |

**User's choice:** Full per DOC-01 brief (Recommended).
**Notes:** Maps 1:1 to DOC-01 enumeration. AI Tools Used section maximises AI/Vibe-Coding 15% rubric coverage.

### Q: architecture.md diagram style?

| Option | Description | Selected |
|--------|-------------|----------|
| Mermaid + keep current ASCII as fallback | Add Mermaid graphs below existing ASCII; GitHub renders Mermaid natively; ASCII stays for terminal | ✓ |
| Mermaid only — strip ASCII | Cleaner file but loses terminal readability during live demo | |
| Keep ASCII only — update content for Phase 5 | Minimal-effort path; loses visual polish | |

**User's choice:** Mermaid + keep current ASCII as fallback (Recommended).
**Notes:** Mermaid `flowchart` for graph topology, `sequenceDiagram` for SSE event flow. Both representations stay in lockstep.

### Q: Where does DOC-04 (data source documentation) live?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate docs/data-sources.md | Dedicated file covering EPPO, simulation assumptions, Google Maps, Tavily | ✓ |
| Section inside README.md | Folds DOC-04 into README — inflates README | |
| Distributed across data/ subdirectories as READMEs | Closest to source but harder for graders to find canonical doc | |

**User's choice:** Separate docs/data-sources.md (Recommended).
**Notes:** README links to it. Easier to extend if v2 adds sources.

### Q: Demo artifact strategy for W5/W6 submission?

| Option | Description | Selected |
|--------|-------------|----------|
| Screenshots in README + recorded MP4 of agent run | Static screenshots embedded; 1-2 min .mp4 of live query end-to-end | ✓ |
| Screenshots only | Faster to produce; loses live-reasoning-trace impact | |
| GIF only (no screenshots) | Compact, autoplays on GitHub; lower-resolution detail | |
| Live demo only — no recorded artifact | Risks demo-day failure with no fallback | |

**User's choice:** Screenshots in README + recorded MP4 of agent run (Recommended).
**Notes:** Recording at `docs/demo.mp4` shows fresh-thread query with parallel trace timestamps + HITL approval. Submission-ready, demo-day-ready, durable beyond demo day.

---

## Claude's Discretion

Areas where the user accepted that Claude has flexibility:
- Exact `HITL_TOTAL_THB_THRESHOLD` default value (calibrate against rate-table distribution)
- Module split for the Search Agent (single file vs. package)
- Tavily SDK choice (official `tavily-python` vs. raw httpx)
- Mermaid diagram fidelity beyond the required structural elements
- Demo recording tool (QuickTime, Loom, OBS)
- Plan ordering across the four sub-domains
- Inline UI affordance for the HITL prompt (dedicated component vs. inline)
- Whether `response_node` deny path includes the original surcharge_result as a debug affordance
- Exact prompt-engineering for Tavily query construction

## Deferred Ideas

Surfaced during option presentation and explicitly rejected (these become the deferred decisions):
- Auto-approve HITL after N seconds (weak grading signal)
- Auto-augment Tavily search on every surcharge query (quota waste)
- Trace-only Tavily output with no user-facing surface (hides demo value)
- Tavily influencing baseline diesel price (couples LLM to deterministic formula)
- Background-task / batch-flush feedback wire (over-engineered for course demo)
- Self-hosted Langfuse (cloud free tier sufficient)

Plus standing v2 deferrals from prior phases (multi-region, what-if, rate-table versioning, batch calc, scheduled reports, past-turn trace inspection, theme toggle, i18n, conversation deletion).
