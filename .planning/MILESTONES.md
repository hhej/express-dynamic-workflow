# Milestones

## v1.1 Real-World Routing & Demo Hardening (Shipped: 2026-05-12)

**Phases completed:** 3 phases (9, 10, 11), 12 plans, ~26 tasks
**Timeline:** 2026-05-09 → 2026-05-12 (4 days; 102 commits)
**Code delta:** 69 source files changed, +7241/-348 LOC (backend + frontend + data)
**Requirements:** 22/22 v1.1 requirements satisfied (10 active phase-mapped + 12 retroactive)
**Audit:** passed (re-audit 2026-05-12T18:00:00Z); 23/23 cross-phase wires PASS; 6/6 E2E flows operational

**Key accomplishments:**

- 10-hub seed dataset (1 HQ + 9 branches) + 135-row origin × destination rate matrix + symmetric ORIGIN_DEST_MULTIPLIER + 4-arg `lookup_rate` signature; v1.0 central-1 rates preserved byte-for-byte (Phase 9 / 999.9-01)
- AgentState/RouteData/ChatRequest extended additively with `origin_hub_id`; `calculate_route` signature changed to `(hub_id, destination)`; planner extracts/validates/inherits hub_id; pricing_agent resolves hub_id → origin_zone via `origin_zone_for`; API boundary defaults to HQ (Phase 9 / 999.9-02)
- HubPicker dropdown with glass-morphism styling above ChatInput; ChatApp lifts `originHubId` state with sessionStorage persistence + post-hydration seeding; `useChatStream` forwards `origin_hub_id` in POST /api/chat body; full frontend suite green (145 tests, +20 net new) (Phase 9 / 999.9-03)
- Unified refusal copy on planner bypass paths — additive `GuardCategory` Literal extension (`planner_off_topic`, `planner_parse_failed`); planner D-04 (out_of_scope) + D-05 (parse_failed) emit `state.guard_decision` and route to response refusal branch; `REFUSAL_COPY` + `status='refused'` for adversarial_pack cases 2 + 4 (Phase 10 / 999.10)
- Live SSE hang on legit baseline diesel-price query CLOSED via pre-LLM destination-less short-circuit in `planner_node` (commit `e550256`); hypotheses (c) cold-start and (a) SSE termination cleanly RULED OUT; 5/5 fresh-uvicorn runs PASS_UNDER_30S at ~7.6–7.9 s — W6 demo gate cleared (Phase 11 / 999.11)
- FastAPI lifespan cold-start fuel-price refresh with timezone-aware (Asia/Bangkok) staleness predicate + D-03 log-and-continue (retroactive: Quick 260509-eum / DATA-06)
- Pricing Agent visible reasoning bullets (3–5 per turn) + 7-day fuel-volatility flag (low/normal/high) via pure CSV reader (retroactive: Quick 260509-uwb / PRICE-01, PRICE-02)
- Two-layer adversarial guardrails: SECURITY_PREAMBLE on all agent prompts, `guard_input` rules-first regex classifier + Gemini LLM fallback flag, `guard_output` SurchargeResult invariant validator, per-turn `tool_call_count` cap (=6) via `Annotated[int, operator.add]` reducer, locked REFUSAL_COPY, 15-attack `adversarial_pack.txt` (retroactive: Quick 260509-utd / GUARD-01..06)
- Dark cosmic glass-morphism UI theme applied across 23 view components (Tailwind v4 `@theme` tokens + `glass-surface`/`glass-panel`/`brand-gradient` utilities + static gradient mesh body) (retroactive: Quick 260509-e0p / THEME-01)
- EPPO fuel-price scraper rewrite after EPPO site URL + Excel structure restructure (retroactive: Debug 999.6 / DATA-07)
- 90-day daily fuel-price history backfilled via Bangchak historical scraper (retroactive: Debug 999.7 / DATA-08)
- Resume flow no longer appends duplicate assistant message on conversation reload (retroactive: Debug 999.5 / FIX-01)

---

## v1.0 MVP (Shipped: 2026-05-05)

**Phases completed:** 8 phases, 36 plans, 87 tasks

**Key accomplishments:**

- Rate table generator, EPPO fuel scraper with fallback, and SQLite seeder producing express.db with 45 rates, 185 fuel prices, and 3 zone definitions
- Pydantic models for 5 tool I/O contracts, AgentState TypedDict with 8 fields, and env-loaded surcharge config with 22 passing tests
- Phase 2 Wave 0 test & runtime scaffolding: 7 new pinned deps installed, six config constants added, AgentState.reasoning_trace migrated to operator.add reducer, FuelData source docs expanded per D-03, shared conftest with 7 fixtures plus 5 canonical fixture files landed, pyproject.toml pytest config added; Phase 1's 35-test suite still green.
- 3-level fuel-price fallback chain (stubbed live scrape -> cached CSV -> hardcoded baseline) with source tagging, exponential backoff, and a never-raises contract, fully covered by 6 deterministic tests using pytest-httpx.
- TOOL-02 calculate_route with Google Maps Directions + reverse-geocode zone derivation, 1-5 traffic bucketing, 15-min in-process TTL cache, and province-suffix normalisation.
- TOOL-03 SQLite rate lookup with half-open weight tiers plus TOOL-04 LangChain @tool wrapper over the Phase 1 surcharge function
- Gemini-narrated fuel_agent_node (ORCH-02) and route_agent_node (ORCH-03) with D-11 deterministic fallback, D-12 trace schema, and a test-swappable get_chat_model factory.
- Phase 3 dep stack installed, AgentState extended with 6 D-05 fields (origin, destination, user_intent, missing_fields, clarification_reason, errors), and 27 placeholder tests scaffolded across 7 new files so the Phase 3 test map is grep-verifiable on day one.
- Built three new LangGraph nodes (Planner D-01/D-02/D-04/D-12, Pricing Agent D-08/D-09/D-11, Response Node D-10/D-11) plus D-13 fetched_at injection on existing Fuel/Route nodes — backend test suite now reports 88 passed / 15 skipped (12 new active tests across Wave 2: 5 planner + 3 pricing + 4 response).
- Wired the 5 nodes (planner, fuel_agent, route_agent, pricing_agent, response) into a LangGraph StateGraph with D-22 RetryPolicy, D-23 custom retry filter, D-24 error-sink wrappers, and AsyncSqliteSaver checkpointer integration. Backend test suite reports 95 passed / 8 skipped (7 new graph integration tests across ORCH-08 retry topology + ORCH-10 checkpointer + D-12 cache reuse end-to-end).
- Stood up the FastAPI app with a lifespan-managed AsyncSqliteSaver checkpointer, compiled the graph at startup, and exposed POST /api/chat as a manually-framed SSE stream emitting D-18 envelopes (meta -> trace+ -> answer -> done) with D-19 thread_id flow. Backend test suite reports 98 passed / 5 skipped (3 new chat integration tests; +3 vs Plan 03-03 baseline; zero regressions after fixing the test-fixture env-var pollution).
- Closed Phase 3's API layer with the three remaining read-only endpoints: GET /api/conversations (SQL enumeration of checkpointed threads), GET /api/conversations/{thread_id} (graph.aget_state replay), and GET /api/fuel-prices?days=N (direct CSV read of EPPO historical data per D-20). Backend test suite reports 103 passed / 0 skipped (5 placeholders activated; +5 vs Plan 03-04 baseline; zero regressions across Phase 1, 2, or earlier Phase 3 tests).
- Next.js 15 + React 19 + Tailwind v4 scaffold with overrides.react-is, hand-mirrored snake_case TS contracts mirroring backend models + SSE envelope, and Vitest + Playwright + MSW test infra with canonical SSE fixtures (happy/capped/clarify/partial)
- Generic SSE parser, typed api client + ApiError, three React hooks (useChatStream / useConversations / useFuelPrices) that hide fetch + AbortController + localStorage from UI components — UI-01 and UI-06 data-layer satisfied
- 15 pure-renderer components (3 shared + 7 chat + 3 trace + 2 sidebar) covering the chat surface, reasoning trace, and conversation sidebar — UI-01/02/03/05/06 satisfied at the component level via TDD with 42 passing tests.
- Recharts dashboard with 7d/30d/90d fuel-price line chart and client-derived surcharge-history bar chart — both wrapped in a local ChartErrorBoundary, both with Pitfall 4 (animation flicker) and Pitfall 8 (N+1 fetches) explicitly mitigated.
- Three-column desktop shell (ConversationSidebar | ChatColumn | TracePanel) wired through a single state-lifting `<ChatApp />` root with Chat | Dashboard tab toggle, resume + new-conversation flows, Playwright smoke against the live backend, and a human-verified live SSE streaming UX — closes Phase 4 at 92/22 tests green and zero "Central Region" leakage.
- Phase 5 contracts locked: Python 3.11 venv + langfuse/tavily deps + AgentState v3 + observability.py with deterministic trace IDs
- Per-turn Langfuse CallbackHandler + deterministic trace_id seed wired into POST /api/chat; pricing_agent_node fires fire-and-forget formula accuracy auto-eval after surcharge_result is built
- LangGraph list-returning conditional edge schedules fuel_agent and route_agent in the same Pregel superstep on a fresh thread; trace timestamp delta measured at ~165 microseconds — visible parallelism with zero new reducers.
- TOOL-05 search agent: Tavily-backed news search with TTL cache, graceful-warn node, planner news-intent routing, and Market-context markdown prefix
- ORCH-09 HITL gate via langgraph.types.interrupt() + Command(resume) — pricing → hitl_gate → response topology, sixth SSE event approval_required, response_node deny short-circuit, Pitfall 1+2 mitigations enforced
- API-05 / OBS-02 — POST /api/feedback resolves trace_id deterministically from message_id and forwards to Langfuse user_feedback Score; frontend ApprovalCard + SearchContextLine + FeedbackButtons swap + useChatStream.approve() complete the HITL + search-context + feedback wires.
- DOC-01 README rewritten with 9 sections + Mermaid agent topology, DOC-02 architecture.md extended with Mermaid + Phase 5 topology + Observability + Parallel Execution sections, DOC-04 data-sources.md created from scratch with EPPO + simulated rate-table assumptions + Google Maps + Tavily + Langfuse + internal constants. demo.mp4 + 5 screenshots + v1.0 tag pending human action.
- Defensive null-out branch in planner_node that prevents the LLM from corrupting cached follow-up state when it hallucinates truthy values for fields the user did not explicitly mention.
- Selective ValueError catch in route_agent_node converts out-of-Metro destinations to a status='partial' clarify response naming route_agent + the supported zone set, plus docs corrected to match data/raw/zone_definitions.json verbatim.
- Planner short-circuits to respond when search_agent already populated search_context (preventing 5x LLM re-routing loop) AND response_node renders deterministic news prose instead of misleading 'I need a bit more information' clarify text
- Extended TraceStep AGENT_LABEL to cover all 7 AgentName keys (added hitl_gate -> 'Approval gate' and search_agent -> 'Search agent') and added a Vitest exhaustive loop that catches future AgentName drift at runtime — closes audit Issue 1 TS2739 compile blocker on TraceStep.tsx.
- Wires the HITL approval prop chain ChatApp -> ChatColumn -> MessageList -> ApprovalCard, locks ChatInput while awaiting_approval with contextual placeholder, and adds an inline red error surface for failed approve/deny POSTs
- Adds the canonical ChatApp integration test (D-15.3) that exercises BOTH approve and deny SSE flows end-to-end through the production ChatApp tree using MSW — drift-prevention layer that catches any future regression of audit Issue 2 (the cross-phase chat.approve / chat.approvalPayload prop chain breakage that produced the original audit gap).
- Backend stamps the canonical `message_id = '{thread_id}-{turn_idx}'` on every SSE answer payload AND on the LAST assistant per turn returned by GET /api/conversations/:id, closing audit Issue 3 root cause (cross-phase contract drift between FE id construction and BE feedback regex).
- Frontend now reads the BE-stamped `message_id` on both live-append and resume paths, with the TypeScript type system enforcing message_id presence on every answer payload — closes the FE half of audit Issue 3 and adds round-trip Vitest+MSW tests as the lasting drift-prevention layer.
- Documentation + HUMAN-only live smoke for the Langfuse user_feedback Score wire — 6-step verification checklist appended to `docs/data-sources.md`, screenshot filename reserved in `.gitkeep`, real-backend live verification PERFORMED with Score row confirmed in Langfuse Cloud (PNG artifact deferred).
- `response_node` now always emits `search_context` in `final_payload` (happy + deny paths), `FinalStatus` declares `'search_only'`, and `MessageList` dispatches it explicitly to `MarkdownAnswer` — closes audit Issue 6 backend half + frontend type/dispatch half.
- Audit Issue 4 closed: useConversations promoted from 3 independent useState instances to a single React Context provider, so post-`done` `conversations.refresh()` propagates from ChatApp to ConversationSidebar and SurchargeHistoryChart without a page reload — UI-06 restored to fully satisfied.

---
