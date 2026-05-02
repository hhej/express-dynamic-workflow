---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 5 UI-SPEC approved
last_updated: "2026-05-02T16:58:37.775Z"
last_activity: 2026-05-02 -- Phase 05 execution started
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 25
  completed_plans: 18
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-04)

**Core value:** The agent must transparently reason through fuel price, route, and shipping data to produce an accurate, explainable surcharge recommendation.
**Current focus:** Phase 05 — polish-observability-docs

## Current Position

Phase: 05 (polish-observability-docs) — EXECUTING
Plan: 1 of 7 complete; starting Wave 2 (Plans 02 + 03)
Status: Executing Phase 05
Last activity: 2026-05-03 -- Plan 05-01 complete

Progress: [█░░░░░░░░░] 14%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: n/a
- Trend: n/a

*Updated after each plan completion*
| Phase 01 P01 | 4min | 2 tasks | 7 files |
| Phase 01 P02 | 4min | 2 tasks | 6 files |
| Phase 01 P03 | 2min | 2 tasks | 2 files |
| Phase 02 P01 | 5min | 3 tasks | 12 files |
| Phase 02 P04 | 4min | 2 tasks | 4 files |
| Phase 02 P03 | 2min | 3 tasks | 3 files |
| Phase 02 P02 | 3min | 2 tasks | 2 files |
| Phase 02 P05 | 5min | 3 tasks | 7 files |
| Phase 03 P01 | 8min | 3 tasks | 14 files |
| Phase 03 P02 | 6min | 2 tasks | 13 files |
| Phase 03 P03 | 7min | 2 tasks | 5 files |
| Phase 03 P04 | 4min | 2 tasks | 8 files |
| Phase 03 P05 | 3min | 2 tasks | 5 files |
| Phase 04 P01 | 7min | 3 tasks | 21 files |
| Phase 04 P02 | 8min | 2 tasks | 13 files |
| Phase 04 P03 | 6min | 3 tasks | 25 files |
| Phase 04 P04 | 5min | 2 tasks | 9 files |
| Phase 04 P05 | 13min | 4 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 5 phases derived from requirement dependencies -- data first, tools second, graph third, UI fourth, polish last
- [Roadmap]: TOOL-06 (Pydantic models) and ORCH-06 (state schema) placed in Phase 1 as shared foundation
- [Roadmap]: TOOL-05 (Tavily), ORCH-07 (parallel), ORCH-09 (HITL) deferred to Phase 5 as differentiators that build on a working base
- [Phase 01]: Used pathlib relative to __file__ for all script paths to avoid cwd issues
- [Phase 01]: Zone multipliers 1.0/1.25/1.55 producing rate range 50-698 THB
- [Phase 01]: Used from __future__ import annotations for Python 3.9 compat with modern type hint syntax
- [Phase 01]: Exact cap boundary (== 0.15) treated as NOT capped -- only exceeding triggers cap
- [Phase 02]: pytest-httpx chosen over responses lib (C-01) — httpx-native mocking for fuel tool tests
- [Phase 02]: AgentState.reasoning_trace uses operator.add reducer (Pitfall 1) — parallel Send nodes append instead of overwrite
- [Phase 02]: FuelData.source kept as str (no Enum) per D-03 — open value-set for future sources
- [Phase 02]: TRAFFIC_RATIO_BUCKETS parsed from comma-separated env (defaults 1.1/1.3/1.5/1.8) per D-06
- [Phase 02]: ROUTE_CACHE_TTL_SECONDS default 900s per D-07 — balances Google Maps quota vs freshness
- [Phase 02]: seeded_sqlite_path fixture copies real data/express.db — avoids test/prod seed drift
- [Phase 02]: [Phase 02]: Sentinel-safe SQL — '? < weight_max_kg' excludes 999 sentinel naturally; no NULL/special-case needed (C-02, D-13)
- [Phase 02]: [Phase 02]: @tool wrapper delegates to Phase 1 pure function (import alias _calc) — zero logic duplication, preserves existing 13 tests
- [Phase 02]: [Phase 02]: rate_tier format '<min>+kg' for top tier, '<min>-<max>kg' otherwise — human-readable, hides sentinel 999 from reasoning traces
- [Phase 02]: Plan 03 TOOL-02: lazy googlemaps client factory _client() enables clean mocker.patch.object seam — zero SDK-internal patching
- [Phase 02]: Plan 03 TOOL-02: _ZONE_INDEX built once at import time — read-once optimisation for hot path (Pitfall 8)
- [Phase 02]: Plan 03 TOOL-02: province normalisation strips ' Province' suffix + lowercases — Pitfall 6 verified via 'Ayutthaya Province' fixture → central-2
- [Phase 02]: fetch_fuel_price tool: 3-level fallback with NotImplementedError stub caught by Level-1 retry loop, CSV fallback active, baseline always reachable
- [Phase 02]: pytest-httpx assert_all_responses_were_requested disabled module-wide in TOOL-01 tests -- stub raises before httpx call, mocks activate in Phase 5 when scrape un-stubbed
- [Phase 02]: Plan 05: Raw model.invoke() + json.loads for agent narration instead of with_structured_output -- FakeMessagesListChatModel does not implement the structured helper; Rule 1 bug fix applied to both fuel and route nodes
- [Phase 02]: Plan 05: route_agent_node raises ValueError when origin/destination missing from state (D-10) -- surfaces Phase 3 Planner pre-extraction contract violations eagerly
- [Phase 02]: Plan 05: Fuel SYSTEM_PROMPT excludes search_fuel_news (TOOL-05 deferred to Phase 5 per Open Question 3) -- prevents hallucinated tool calls
- [Phase 02]: Plan 05: D-11 fallback wraps whole Gemini path in try/except (Exception, ValidationError); trace status stays ok because narration is always produced (LLM or deterministic)
- [Phase 03]: Plan 03-01: aiosqlite pinned to 0.20.0 (not 0.22.1) -- 0.22.x removed Connection.is_alive() that langgraph-checkpoint-sqlite 2.0.11 requires; Rule 1 fix during Task 3 fixture verification
- [Phase 03]: Plan 03-01: in_memory_checkpointer fixture uses 'async with aiosqlite.connect()' not bare 'await' -- raw await does not activate connection thread; AsyncSqliteSaver.setup() needs is_alive=True
- [Phase 03]: Plan 03-01: AgentState v2 appends 6 D-05 fields (origin, destination, user_intent, missing_fields, clarification_reason, errors) AFTER existing v1 fields; errors uses operator.add reducer for parallel-write safety
- [Phase 03]: Plan 03-02: Response Node uses deterministic prose (no Gemini call in v1) per RESEARCH OQ 3/5 -- final hop renders prose+table from Python f-strings, fully testable, saves Gemini quota for Planner+Fuel+Route+Pricing
- [Phase 03]: Plan 03-02: PlannerOutput.next_step Literal includes 'search_context' even though v1 prompt instructs LLM never to emit it -- keeping it in schema means stray emission validates instead of triggering D-02 parse_failed cycle (Phase 5 enables search without re-touching schema)
- [Phase 03]: Plan 03-02: D-13 fetched_at attached to fuel_data/route_data AFTER model_dump() (state-level annotation, not Pydantic field) -- preserves clean tool-output schema; trace_entry.tool_output reflects exactly what tool returned
- [Phase 03]: Plan 03-03: _wrap_error_sink uses per-state attempt counter (id(state)) to re-raise transient errors until max_attempts is reached -- without this RetryPolicy never sees retryable exceptions and D-22 retry behaviour fails
- [Phase 03]: Plan 03-03: Pricing Agent intentionally NOT wrapped in error sink -- D-09 mandates ValueError from lookup_rate must bubble uncaught; wrapper would re-raise ValueError but skipping the wrap removes a stack frame and clarifies test failures
- [Phase 03]: Plan 03-03: Planner short-circuits on state.errors BEFORE D-04 loop-budget guard and BEFORE Gemini call -- reconciles D-03 planner-loop topology with D-24 error-sink force-respond, prevents infinite loop on persistent transient failures
- [Phase 03]: Plan 03-03: AgentState.final_payload added as Optional[dict] TypedDict field -- response_node output otherwise dropped by StateGraph(AgentState) merge; Plan 03-04 SSE handler will detect this key via astream_events
- [Phase 03]: Plan 03-04: Lifespan stores BOTH checkpointer AND graph on app.state -- Plan 03-05 GET /api/conversations needs direct saver access for thread enumeration; graph.aget_state alone retrieves only one thread's snapshot
- [Phase 03]: Plan 03-04: Chat handler filters astream_events on (on_chain_end + node-name allow-list) -- on_chain_start has no useful payload, on_chain_stream fragments single trace entries; one SSE trace event per node completion is the contract
- [Phase 03]: Plan 03-04: Manual SSE framing via raw StreamingResponse + format_sse() bytes helper -- EventSourceResponse not available in FastAPI 0.128.8 (Pitfall 5); explicit Cache-Control: no-cache + X-Accel-Buffering: no headers required
- [Phase 03]: Plan 03-04: Test fixture explicitly delenv()s CHECKPOINT_PATH on cleanup BEFORE reloading config -- Rule 1 fix; without it, importlib.reload re-reads the still-set monkeypatched env var and tmp-path leaks into later tests like test_checkpoint_path_default
- [Phase 03]: Plan 03-05: Reuse chat-test fixture pattern (env-var manipulation + lifespan reload + LLM/tool monkey-patch) for /api/conversations tests; seed real checkpoints via POST /api/chat then exercise GETs -- proves end-to-end against the same lifespan-managed AsyncSqliteSaver
- [Phase 03]: Plan 03-05: /api/conversations preview generation wraps graph.aget_state() in try/except so corrupt/partial checkpoints log a warning + return blank preview rather than 500-ing the whole listing call -- robustness over precision
- [Phase 03]: Plan 03-05: /api/fuel-prices reads data/raw/eppo_diesel_prices.csv directly per D-20 (Phase 1 only seeded rate_table); FastAPI Query(ge=1, le=365) handles validation implicitly -- no test_validates_days_parameter needed per Plan 03-01 stub list
- [Phase 04]: Plan 04-01: Pinned Next 15.5.x over create-next-app's default Next 16 — required deleting auto-generated frontend/{AGENTS,CLAUDE,README}.md that targeted Next 16 deprecation notes
- [Phase 04]: Plan 04-01: Migrated eslint.config.mjs to FlatCompat (@eslint/eslintrc) — eslint-config-next 15.5.x exports .js subpaths that the v16 native ESM imports could not resolve under ESLint 9 flat-config (Rule 3 fix)
- [Phase 04]: Plan 04-01: react-is collapsed to single 19.2.5 via package.json overrides.react-is — verified via 'npm ls react-is | grep -oE react-is@... | sort -u' returning a single line; mitigates Recharts × React 19 blank-chart pitfall before any chart code is written
- [Phase 04]: Plan 04-01: Hand-mirrored backend snake_case verbatim into frontend/types/{api,agent}.types.ts — explicit anti-camelCase comments enforce the rule; downstream plans import via @/types alias
- [Phase 04]: Plan 04-02: parseSseStream tolerates malformed JSON via console.error+continue — one bad frame cannot poison a whole turn (matches D-08 current-turn-only liveTrace intent)
- [Phase 04]: Plan 04-02: useChatStream uses threadIdRef alongside state.threadId — useCallback empty-deps + ref read prevents stale-closure bugs where rapid back-to-back sends both submit with the pre-meta threadId
- [Phase 04]: Plan 04-02: DONE dispatch deferred to finally block (not 'done' SSE case) — error→done sequences from backend would otherwise clobber status='error' back to 'done'
- [Phase 04]: Plan 04-02: Map-backed Storage polyfill installed in __tests__/setup.ts — Node 25 ships an experimental globalThis.localStorage that vitest 4's jsdom populator skips because (k in global) is true; polyfill is the only Node-version-agnostic fix
- [Phase 04]: Plan 04-02: D-08 abort assertion reformulated to inspect liveTrace contents (must equal the 5 second-turn events) instead of upstream stream cancel() callback — MSW does not propagate fetch consumer reader.cancel() to source, but consumer-side invariant is what the test validates
- [Phase 04]: Plan 04-03: D-11 strip-the-line over blockquote-override approach (CAP_LINE_RE.replace removes leading > line before ReactMarkdown sees it; CapCallout renders above stripped markdown) — avoids RESEARCH dual-render anti-pattern
- [Phase 04]: Plan 04-03: PartialCard delegates breakdown render to MarkdownAnswer when surcharge_result is non-null — avoids duplicating GFM table override and inherits capped-banner if backend ever returns capped+partial
- [Phase 04]: Plan 04-03: FeedbackButtons stores JSON ARRAY under localStorage[feedback] (append-on-vote) — matches eventual Phase 5 batch-flush api.postFeedback semantics; MessageList gates buttons on threadId !== null to keep votes attributable
- [Phase 04]: Plan 04-03: TraceStatusBadge accepts TraceStatus | 'running' even though backend never emits 'running' — UI-SPEC documents the running animate-pulse style for future in-flight indicator without schema change
- [Phase 04]: Plan 04-04: Inlined ChartErrorBoundary in DashboardView and animate-pulse skeletons in chart components — Wave 3 parallel-write boundary forbids touching frontend/components/shared/ owned by 04-03; integrator (04-05) swaps to canonical imports post-merge
- [Phase 04]: Plan 04-04: Test-only vi.mock('recharts') with ResponsiveContainer cloneElement shim — jsdom has no ResizeObserver, so the shim forces fixed width/height into the inner LineChart/BarChart; without it the Pitfall 3 SVG-path smoke would silently pass via the empty-state fallback
- [Phase 04]: Plan 04-04: useSurchargeHistory uses Promise.all over per-thread getConversation calls with .catch(() => null) per-call — Pitfall 8 mitigation; one failed thread cannot blank the whole chart
- [Phase 04]: Plan 04-04: Tooltip formatter coerces ValueType via 'typeof === number ? value : Number(value)' — Recharts 3 typed the formatter signature stricter than its 2.x examples; coercion preserves runtime behaviour while satisfying tsc
- [Phase 04]: Plan 04-05: ChatColumn tab toggle uses Tailwind hidden visibility (not conditional unmount) — preserves chat state, scroll position, and in-flight stream across Chat ↔ Dashboard switches
- [Phase 04]: Plan 04-05: ChatApp lifts useChatStream + useConversations once at the root and threads state down via props/callbacks — keeps ChatColumn / TracePanel / ConversationSidebar as pure-renderers with single AbortController + single SSE consumer
- [Phase 04]: Plan 04-05: Resume flow constructs a minimal FinalPayload per replayed assistant message (markdown + surcharge_result + status='ok') so MarkdownAnswer renders persisted answers through the same pipeline as live ones; trace panel intentionally does NOT swap on resume per D-08 (deferred to Phase 5)
- [Phase 04]: Plan 04-05: Phase-3 CORS gap surfaced during human-verify Verify 1 (browser preflight OPTIONS /api/chat returned 405); fixed in-band by adding CORSMiddleware to backend/api/main.py (commit 750cf5d). Phase 3 (API-01) shipped without CORS because TestClient never exercises preflight; production deploy needs env-driven allow-list
- [Phase 05]: Plan 05-01: Python 3.11.15 venv + langfuse 4.5.1 + tavily-python 0.7.24 pinned — langfuse 4.x requires Python 3.11+, hence the runtime bump
- [Phase 05]: Plan 05-01: AgentState extended additively with approval_decision (D-07) and search_context (D-11) — no rename of existing v1/v2 fields preserves Phase 4 contracts
- [Phase 05]: Plan 05-01: observability.py uses graceful no-op (return None when LANGFUSE_* keys missing) so local dev runs identically without Langfuse — preserves CLAUDE.md local-reproducibility constraint
- [Phase 05]: Plan 05-01: seed_trace_id falls back to md5(f'chat_turn_{thread_id}_{turn_idx}') when client missing — guarantees deterministic 32-hex trace ID in tests AND production; load-bearing for D-14 callback wiring + D-16 feedback Score attachment without name lookup
- [Phase 05]: Plan 05-01: post_formula_accuracy_score (D-15) re-imports the Phase 1 PURE function (not the @tool wrapper) so the auto-eval is independent of the agent path; failures are logged + swallowed — eval failure MUST NOT impact user response

### Pending Todos

None yet.

### Blockers/Concerns

- Research flagged LOW confidence on package versions -- must verify at install time (Phase 1)
- EPPO API response format undocumented -- may need reverse engineering (Phase 2)
- Gemini structured output reliability unknown -- test early in Phase 2

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260425-vc6 | Rename product scope from Central Region to Bangkok Metro (resolves backlog 999.2-b) | 2026-04-25 | 4889bf6 |  | [260425-vc6-rename-product-scope-from-central-region](./quick/260425-vc6-rename-product-scope-from-central-region/) |
| 260425-vyj | Fix planner bugs 999.1 (state merge on follow-ups) and 999.3 (stale next_step in trace) | 2026-04-25 | 231a54b | Verified | [260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo](./quick/260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo/) |
| 260425-x2i | Fix D-04 loop-budget guard to window per turn (resolves 999.4 — cross-turn short-circuit) | 2026-04-25 | bd27c33 | Smoke-confirmed | [260425-x2i-fix-d-04-loop-budget-guard-to-window-per](./quick/260425-x2i-fix-d-04-loop-budget-guard-to-window-per/) |

## Session Continuity

Last session: 2026-05-02T15:51:24.723Z
Stopped at: Phase 5 UI-SPEC approved
Resume file: /Users/pollot/Desktop/express-dynamic-workflow/.planning/phases/05-polish-observability-docs/05-UI-SPEC.md
