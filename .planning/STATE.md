---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 06-01-PLAN.md
last_updated: "2026-05-04T05:11:30.003Z"
last_activity: 2026-05-04
progress:
  total_phases: 8
  completed_phases: 5
  total_plans: 31
  completed_plans: 29
  percent: 71
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-04)

**Core value:** The agent must transparently reason through fuel price, route, and shipping data to produce an accurate, explainable surcharge recommendation.
**Current focus:** Phase 06 — hitl-approval-ui-wiring

## Current Position

Phase: 06 (hitl-approval-ui-wiring) — EXECUTING
Plan: 2 of 3
Status: Ready to execute
Last activity: 2026-05-04

Progress: [███░░░░░░░] 71%

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
| Phase 05 P03 | 7min | 2 tasks | 5 files |
| Phase 05 P02 | 30min | 2 tasks | 5 files |
| Phase 05 P04 | ~30min | 3 tasks | 11 files |
| Phase 05 P05 | ~50min | 2 tasks | 9 files |
| Phase 05 P06 | ~45min | 3 tasks | 16 files |
| Phase 05 P07 | ~30min | 3 of 5 tasks (T4+T5 pending human) | 4 files docs + SUMMARY.md |
| Phase 05 P08 | 25min | 2 tasks | 4 files |
| Phase 05 P09 | 6min | 2 tasks | 6 files |
| Phase 05 P10 | 15min | 2 tasks | 6 files |
| Phase 06 P01 | 3 min | 1 tasks | 2 files |

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
- [Phase 05]: [Phase 05]: Plan 05-03: List-returning conditional edge over Send API for ORCH-07 -- both branches read same state keys, so dynamic per-branch state slicing buys nothing; list return is the smaller, safer change
- [Phase 05]: [Phase 05]: Plan 05-03: Sentinel-based promotion (fanout_fuel_route) keeps PlannerOutput.next_step Literal stable; LLM still emits fetch_fuel/fetch_route, router promotes to fan-out based on cache state
- [Phase 05]: [Phase 05]: Plan 05-03: Pre-conditions enforce D-12 cache-skip precedence -- fan-out only fires with both caches stale + 4 extraction fields present; cache-warm follow-ups continue running sequentially
- [Phase 05]: [Phase 05]: Plan 05-03: No new reducers (D-02 invariant) -- operator.add on reasoning_trace + errors carries parallel writes; fuel_data + route_data scalar-dict last-write-wins is safe (disjoint branches)
- [Phase 05]: [Phase 05]: Plan 05-03: Trace timestamp delta on parallel turn measured at ~165 microseconds -- demo evidence for ROADMAP Phase 5 success criterion 1 captured live
- [Phase 05]: Plan 05-02: _make_config exposes langfuse_trace_id in metadata (not just inside the CallbackHandler trace_context) so pricing_agent_node can read the SAME trace_id without re-deriving — eliminates drift between handler attach and Score post
- [Phase 05]: Plan 05-02: _next_turn_idx counts prior user messages in checkpointer snapshot; falls back to 0 on any exception so first-ever turn or transient checkpointer errors are always safe (D-14 deterministic trace_id seed remains valid)
- [Phase 05]: Plan 05-02: pricing_agent_node config typed as Optional[RunnableConfig] (not Optional[dict]) — silences LangGraph UserWarning about node config typing while remaining Optional so unit tests invoke without a config (Rule 1 fix)
- [Phase 05]: Plan 05-02: D-15 fire-and-forget invariant double-enforced — post_formula_accuracy_score swallows internal errors AND the call site wraps in try/except; even synthetic helper exceptions never affect the user response (proven by test_pricing_swallows_auto_eval_exception)
- [Phase 05]: Plan 05-02: POST /api/chat now rejects fresh turns lacking `message` with HTTP 400 — leaves room for Plan 05-04 HITL resume to branch ABOVE this guard via req.approve != None
- [Phase 05]: Plan 05-04: search_fuel_news raises RuntimeError on missing TAVILY_API_KEY (not silent no-op) — search_agent_node converts to warn-status trace; explicit raise gives users a clear log signal when keys are missing
- [Phase 05]: Plan 05-04: Cache-aware override block in planner early-returns when next_step==search_context — news queries shouldn't be gated on fuel/route freshness, otherwise the override would incorrectly demote a news query to fetch_fuel
- [Phase 05]: Plan 05-04: TTLCache key is normalized (lowercase + collapse whitespace) but NOT punctuation-stripped — Pitfall 3 mitigated; punctuation-equivalence deferred (would expand cache hit rate but is a behavior change beyond plan scope)
- [Phase 05]: Plan 05-04: Response node prepends Market context as a markdown blockquote (`> Market context: <summary>`) above any other content — matches existing CapCallout/MarkdownAnswer rendering pipeline; empty/None summary treated as no-prefix
- [Phase 05]: Plan 05-04: Default fallback query 'Thailand diesel fuel price news' when no user message present — keeps search_agent invocable in tests/edge cases without crashing
- [Phase 05]: Plan 05-04: PROCESS DEVIATION — original gsd-executor agent stalled (no progress 600s) before committing or writing SUMMARY; orchestrator inspected WIP, fixed one test typo, committed work in 3 task-aligned chunks (loses strict TDD red/green pairing but preserves task atomicity); 152/152 tests green
- [Phase 05]: Plan 05-05: HITL gate via langgraph.types.interrupt() + Command(resume=...) — pricing → hitl_gate → response REPLACES pricing → planner edge (Pitfall 6 invariant); pricing is final compute step within a turn, next-turn planner loop is entered via fresh chat invocations
- [Phase 05]: Plan 05-05: Bypass path on hitl_gate emits ZERO trace entries for low-value totals (~91% of demo queries below 500 THB threshold) — keeps the common case overhead-free; only high-value totals emit pre-pause warn + post-resume ok trace pair (D-08)
- [Phase 05]: Plan 05-05: interrupt() return value mapping — True (bool) AND 'approve' (string) → 'approve'; anything else → 'deny'; defensive against frontend serialisation surprises while still booleanly clean
- [Phase 05]: Plan 05-05: Sixth SSE event type approval_required added INTO the EventType Literal (not a sibling Literal) — single source of truth for the SSE contract; static-type check forces all emit sites to update together
- [Phase 05]: Plan 05-05: Pitfall 1 mitigation — resume path REUSES _make_config so Langfuse callbacks + metadata + deterministic langfuse_trace_id are preserved across the pause; turn_idx clamps at max(0, turn_idx-1) since resume does not add a new user message
- [Phase 05]: Plan 05-05: Pitfall 2 mitigation — pending_approval flag in finally block enforces NO done after approval_required; FE keeps Approve/Deny buttons live until the resume POST arrives
- [Phase 05]: Plan 05-05: _drain_events helper centralizes astream_events filter logic across fresh + resume paths — eliminates contract-drift risk on what counts as a trace/answer event
- [Phase 05]: Plan 05-05: response_node deny short-circuit — status='partial', surcharge_result=None in final_payload, prose contains 'declined', NO breakdown table (D-07); Market context prefix (D-11) preserved on deny path so provenance applies regardless of accept/decline
- [Phase 05]: Plan 05-05: Test fixture pattern adapted from `async_client` (referenced in plan but doesn't exist in conftest) to existing TestClient + app_with_mocks pattern — install MagicMock graph stub AFTER lifespan enters since lifespan replaces app.state.graph with the real compiled graph (Rule 3 blocking + Rule 1 bug fixes documented in 05-05-SUMMARY.md)
- [Phase 05]: Plan 05-06: Deterministic feedback wire — backend POST /api/feedback parses message_id "{thread_id}-{turn_idx}" (anchored on trailing -<digits>) and calls seed_trace_id(thread_id, turn_idx); SAME helper Plan 05-02 used to attach the per-turn Langfuse CallbackHandler, so user_feedback Score lands on the EXACT trace WITHOUT a name lookup
- [Phase 05]: Plan 05-06: Defense-in-depth thread_id mismatch returns 400 — body thread_id and message_id-encoded thread_id must agree; protects against accidental cross-thread Score posting if FE serialises inconsistently
- [Phase 05]: Plan 05-06: D-13 graceful no-op preserved on /api/feedback — when LANGFUSE_* keys missing, returns 200 with delivered=false (NOT a user-facing error), so FE silent-error contract stays clean
- [Phase 05]: Plan 05-06: useChatStream reducer DONE guard for Pitfall 2 — `if state.status === 'awaiting_approval' return state` prevents the unconditional finally-block DONE dispatch from auto-flipping the FE out of the paused HITL state; single chokepoint vs forking send()/approve() finally logic
- [Phase 05]: Plan 05-06: FeedbackButtons UI is intentionally unchanged from Phase 4 (same glyphs, same aria-pressed, same disabled-after-vote) — only the side-effect swaps from localStorage write to api.postFeedback POST; on POST failure, error is console.error'd and button stays voted (silent — no toast)
- [Phase 05]: Plan 05-06: ApprovalCard uses NEUTRAL outline buttons (border-gray-300 bg-white) NOT accent blue per UI-SPEC D-07 — deliberate user choice; CapCallout's yellow-50/yellow-300 palette reused so no new color tokens introduced
- [Phase 05]: Plan 05-06: MarkdownAnswer strips backend-emitted "> **Market context:**" blockquote and renders typed SearchContextLine instead — avoids dual-rendering anti-pattern; backend still emits the blockquote so non-FE consumers see the provenance
- [Phase 05]: Plan 05-06: AssistantMessage.payload widened to FinalPayload | null so the awaiting-approval slot can render ApprovalCard with no payload yet; backward-compatible since existing consumers always pass non-null
- [Phase 05]: Plan 05-06: ChatRequest.message widened from required to optional in frontend/types/api.types.ts to mirror Plan 05-02 backend ChatRequest contract — required for the resume path that sends only {thread_id, approve}
- [Phase 05]: Plan 05-06: PROCESS DEVIATION — executor agent's bash sandbox blocked git mutations (git add, git commit, gsd-tools commit) AND test runs (pytest, npm test); read-only git status/diff allowed. Per parallel_execution wrap-up discipline, executor finished all 3 tasks of code work, ran static verification via Read+Grep on every acceptance criterion, wrote SUMMARY.md and STATE.md updates inline, and handed off to orchestrator to commit the 16 staged files in task-aligned chunks. Same pattern as Plan 05-04 stall and Plan 05-01 wrap-up.
- [Phase 05]: Plan 05-07: DOC-01 README wholesale rewrite (vs incremental edit) — Phase 4-era README was missing Phase 5 differentiator narrative (parallel / HITL / search / Langfuse) AND missing AI Tools Used + Limitations sections per AI/Vibe-Coding 15% rubric; wholesale rewrite per D-17 outline is the safer + faster path
- [Phase 05]: Plan 05-07: DOC-02 architecture.md targeted update (vs full rewrite) — preserved high-quality Phase 1-4 sections (Surcharge Logic, Tools, Tech Stack, Shipping Types); appended Phase 5 sections (Observability Architecture Mermaid + Parallel Execution + Phase 5 Error Paths); REPLACED ASCII Agent Graph Flow with Mermaid + ASCII fallback inside <details> per D-18 hybrid layout
- [Phase 05]: Plan 05-07: docs/screenshots/.gitkeep stub created so the directory is tracked even before Task 4 lands the 5 PNG artifacts — README references the EXACT 5 filenames the human will produce in Task 4
- [Phase 05]: Plan 05-07: PROCESS DEVIATION — sandbox blocked git mutations (same as 05-04, 05-06); executor finished all 3 autonomous tasks (README + architecture.md + data-sources.md + screenshots stub), wrote SUMMARY.md inline, and handed off to orchestrator for the 3 task-aligned commits. Tasks 4 (demo recording + 5 screenshots) and Task 5 (develop->main merge + v1.0 annotated tag per D-21) are HUMAN-only checkpoints by plan design — autonomous: false.
- [Phase 05]: Plan 05-08: gap-1 fix is null-only inheritance branch ABOVE 999.1 merge — preserves explicit-override semantics; defense-in-depth pairs with SYSTEM_PROMPT contract update telling LLM to emit null on unmentioned followup fields
- [Phase 05]: Plan 05-08: token-detection signals — shipping_type uses substring + fixed keyword set (bounce/retail_standard/retail_fast); destination/origin use substring against parsed token OR prior state value; weight_kg uses any-digit detection. Plain string ops sufficient for demo-grade robustness without NLP
- [Phase 05]: Plan 05-08: integration test (test_followup_25kg_preserves_bounce_and_nonthaburi) uses 1 turn-2 planner LLM response — only correct for the FIXED behaviour because turn 2 with inheritance immediately routes followup→fetch_fuel→D-12 cascade→calculate_price→pricing→hitl→response (no planner re-entry within turn)
- [Phase 05]: Plan 05-09: Selective ValueError prefix-match catch ('No Bangkok Metro zone') in route_agent_node — preserves D-10 ValueError on missing origin/destination while gracefully handling out-of-Metro destinations as state.errors entry + next_step='respond' (gap-2 fix from UAT test 4)
- [Phase 05]: Plan 05-09: Doc fix corrects docs/data-sources.md central-1/2/3 split to match data/raw/zone_definitions.json verbatim (Plan 05-07 baseline was wrong). 15 supported provinces enumerated explicitly across README, data-sources.md, and architecture.md; out-of-scope provinces (Chiang Mai, Phuket etc.) noted with the graceful clarify response — DOC-01/02/04 honesty restored
- [Phase 05]: Plan 05-10: gap-3 fix — planner early-return guard fires when state.search_context is populated AND user_intent in {news_query, out_of_scope}, BEFORE Gemini call. Guard placed between D-24 errors short-circuit and D-04 budget guard. Emits a minimal trace entry so observability shows 'planner ran twice, second was a short-circuit'.
- [Phase 05]: Plan 05-10: news_query is a new PlannerOutput.user_intent Literal value distinct from out_of_scope; SYSTEM_PROMPT documents it for fuel/market questions. Early-return guard accepts BOTH values for backward compatibility (today's LLM still emits out_of_scope before being retrained on the updated prompt).
- [Phase 05]: Plan 05-10: response_node status='search_only' branch renders 'Here's the latest market context.' prose when search_context populated AND no surcharge_result AND no errors. Status precedence: errors > search_only > clarify > ok > clarify(fallback). search_only sits BEFORE clarify so the news prose wins even if a future regression sets clarification_reason='planner_loop_budget_exhausted'.
- [Quick 260503-rs8]: Pin langchain==0.3.28 in requirements.txt — root cause of silent Langfuse no-op was that `from langfuse.langchain import CallbackHandler` requires the top-level `langchain` package, but only `langchain-core` was pinned. The graceful no-op fallback (D-13) hid the import failure across all 186 tests; live install of 0.3.28 verified 25 traces reaching Langfuse Cloud.
- [Quick 260503-rs8]: langfuse_trace_name in /api/chat metadata is a STRING CONSTANT 'express-surcharge-agent' (not derived from message/intent/turn_idx) — single stable name to filter all agent traces by in the Langfuse dashboard. Per-question dynamic naming explicitly out-of-scope.
- [Quick 260503-rs8]: uvicorn must be restarted after deploying this fix — running server holds the OLD `_make_config` in memory; pytest exercises a fresh import each run so the test suite covers the new key without a server restart, but live `/api/chat` traffic does not pick up the trace_name until uvicorn is recycled.
- [Quick 260503-s2h]: Top-level RunnableConfig.run_name='express-surcharge-agent' (sibling to configurable/callbacks/metadata, NOT inside metadata) — populates the Langfuse Observations 'Name' column via the langfuse-langchain CallbackHandler reading the LangChain root span name. Pairs with 260503-rs8's metadata.langfuse_trace_name (which populates the 'Trace Name' column) so both columns now match under one constant agent identity for dashboard filtering.
- [Quick 260503-s2h]: Single in-place test extension in test_chat_attaches_callback_when_enabled (no new test function) — preserves the 186-test baseline established post-260503-rs8; success criteria explicitly required no test count delta.
- [Phase 06]: Plan 06-01 D-01 + D-15.1: extended TraceStep.AGENT_LABEL with hitl_gate -> 'Approval gate' and search_agent -> 'Search agent'; added Vitest exhaustive-loop test (AGENT_NAMES) so any future AgentName addition that forgets AGENT_LABEL fails BOTH at tsc (Record<AgentName,string> TS2739) AND at runtime (loop assertion). Defense-in-depth drift prevention.
- [Phase 06]: Plan 06-01 PROCESS DEVIATION: parallel 06-02 executor agent's git stage swept Plan 06-01's already-staged TraceStep.tsx + TraceStep.test.tsx files into commit ff68f26 'feat(06-02): add ApprovalCard errorMessage prop'. Code is correct AND committed (git show ff68f26 confirms exact spec match), only commit-message slug attribution drifted from (06-01) to (06-02). SUMMARY.md commit will land under (06-01) for grep-by-plan traceability. No functional impact.

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
| 260503-qzx | Guard pricing_agent against missing route_data/fuel_data (resolves gap-4 from 20-question UAT — KeyError on hallucinated planner routing) | 2026-05-03 | 79d8ee0 | Verified (186/186 backend tests green) | [260503-qzx-guard-pricing-agent-against-missing-rout](./quick/260503-qzx-guard-pricing-agent-against-missing-rout/) |
| 260503-rs8 | Pin langchain==0.3.28 (fixes silent CallbackHandler import failure) + add constant langfuse_trace_name='express-surcharge-agent' to /api/chat trace metadata (OBS-FIX-LANGCHAIN-PIN, OBS-FIX-TRACE-NAME) | 2026-05-03 | 529075f | Verified (186/186 backend tests green; uvicorn restart required for live metadata pickup) | [260503-rs8-pin-langchain-dep-set-langfuse-trace-nam](./quick/260503-rs8-pin-langchain-dep-set-langfuse-trace-nam/) |
| 260503-s2h | Set top-level RunnableConfig.run_name='express-surcharge-agent' so Langfuse Observations 'Name' column matches 'Trace Name' column from 260503-rs8 (OBS-FIX-RUN-NAME) | 2026-05-03 | 0606e43 | Verified (186/186 backend tests green; uvicorn restart required for live root-span-name pickup) | [260503-s2h-set-runnableconfig-run-name-so-langfuse-](./quick/260503-s2h-set-runnableconfig-run-name-so-langfuse-/) |

## Session Continuity

Last session: 2026-05-04T05:11:30.000Z
Stopped at: Completed 06-01-PLAN.md
Resume file: None
