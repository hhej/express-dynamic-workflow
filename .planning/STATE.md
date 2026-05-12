---
gsd_state_version: 1.0
milestone: null
milestone_name: ""
status: between_milestones
stopped_at: "v1.1 (Real-World Routing & Demo Hardening) shipped 2026-05-12. 22/22 v1.1 requirements satisfied; 23/23 cross-phase wires PASS; 6/6 E2E flows operational; W6 demo gate cleared (5/5 fresh-uvicorn runs PASS_UNDER_30S on legit baseline diesel-price query). v1.1 archived to .planning/milestones/. No active milestone — code freeze for W5 / W6 final demo recording. Next: W6 demo or /gsd:new-milestone to begin v1.2/v2.0."
last_updated: "2026-05-12T14:30:00.000Z"
last_activity: 2026-05-12
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-12 — v1.1 milestone closed)

**Core value:** The agent must transparently reason through fuel price, route, and shipping data to produce an accurate, explainable surcharge recommendation.
**Current focus:** Between milestones — v1.1 shipped 2026-05-12. Awaiting W6 demo recording or `/gsd:new-milestone`.

## Current Position

Phase: —
Plan: —
Last completed: v1.1 milestone (Phases 9, 10, 11) — 2026-05-12
Status: v1.1 milestone complete; between milestones
Last activity: 2026-05-12 — Closed v1.1 milestone (archived ROADMAP + REQUIREMENTS + AUDIT to .planning/milestones/v1.1-*)

Progress: [██████████] 100% (v1.1 — 3 of 3 phases complete)

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
| Phase 06 P02 | 7min | 2 tasks | 7 files |
| Phase 06 P03 | 2min | 1 tasks | 1 files |
| Phase 07 P01 | 7min | 3 tasks | 6 files |
| Phase 07 P02 | 7min | 3 tasks | 7 files |
| Phase 07 P03 | 2 min | 3 tasks | 2 files |
| Phase 08 P02 | 6min | 3 tasks | 6 files |
| Phase 999.9 P01 | 9min | 3 tasks | 9 files |
| Phase 999.9 P02 | 17min | 3 tasks | 14 files |
| Phase 999.9 P03 | 9min | 3 tasks tasks | 12 files files |
| Phase 999.10 P01 | 2min | 1 tasks | 1 files |
| Phase 999.10 P02 | 3min | 1 tasks | 2 files |
| Phase 999.11 P01 | 8min | 2 tasks | 4 files |
| Phase 999.11 P02 | 44min | 2 tasks | 53 files |
| Phase 999.11 P03 | 25min | 2 tasks | 4 files |
| Phase 999.11 P04 | ~15min | 2 tasks | 3 files |
| Phase 999.11 P05 | ~8min | 3 tasks | 4 files (999.11-SUMMARY.md + REQUIREMENTS.md + ROADMAP.md + STATE.md) |

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
- [Quick 260509-uwb]: PricingReasoning extended to {summary, bullets} (D-04 backward compat); LLM gets augmented JSON payload (rate/surcharge/fuel_data/route_data/shipping_type/volatility_flag/search_context_summary/seed_bullets); LLM-bullets-win predicate is strict (3-5 non-empty items only) — borderline emissions fall through to deterministic seed so trace is consistently rich.
- [Quick 260509-uwb]: Volatility thresholds — recent_delta > 0.5 * mean_abs_delta AND mean > 0 → 'high'; < 0.2 * mean_abs_delta → 'low'; else 'normal'. Pure CSV reader (data/raw/eppo_diesel_prices.csv); never raises (returns 'normal' on any I/O or parse error). No new APIs added (D-03 honoured).
- [Quick 260509-uwb]: D-11 deterministic-fallback contract enriched — Gemini failure now returns same bullet shape as LLM happy path (3+ newline-joined `- bullet` lines, not single sentence); trace status='ok' invariant preserved.
- [Quick 260509-uwb]: Test deviation Rule 1 — plan's illustrative LLM payloads used 124.80 / 126.00 totals but calculate_surcharge formula given the test state actually produces 129.05 (bounce) / 122.12 (retail); test fixtures updated to use formula's actual values, honouring the LLM-as-narrator invariant.
- [Phase 06]: Plan 06-01 D-01 + D-15.1: extended TraceStep.AGENT_LABEL with hitl_gate -> 'Approval gate' and search_agent -> 'Search agent'; added Vitest exhaustive-loop test (AGENT_NAMES) so any future AgentName addition that forgets AGENT_LABEL fails BOTH at tsc (Record<AgentName,string> TS2739) AND at runtime (loop assertion). Defense-in-depth drift prevention.
- [Phase 06]: Plan 06-01 PROCESS DEVIATION: parallel 06-02 executor agent's git stage swept Plan 06-01's already-staged TraceStep.tsx + TraceStep.test.tsx files into commit ff68f26 'feat(06-02): add ApprovalCard errorMessage prop'. Code is correct AND committed (git show ff68f26 confirms exact spec match), only commit-message slug attribution drifted from (06-01) to (06-02). SUMMARY.md commit will land under (06-01) for grep-by-plan traceability. No functional impact.
- [Phase 06]: ChatColumn isStreaming -> inputDisabled rename per D-07: name boolean for what it gates (input), not state that happens to be true (streaming)
- [Phase 06]: Pending-assistant-slot strip-and-replace on done: placeholder id pending-${ts} never persists into history per D-06
- [Phase 06]: ApprovalCard waiting state resets via useEffect when errorMessage flips truthy: parent-supplied error means prior attempt failed, so buttons must re-enable per D-11
- [Phase 06]: Two-render pattern in D-15.2 ChatColumn props-forwarding test: ApprovalCard internal waiting would otherwise disable second click without errorMessage to reset
- [Phase 06]: ChatInput placeholder default preserved as ORIGINAL literal so all pre-existing tests pass without modification — optional prop is purely additive
- [Phase 06]: Plan 06-03 D-15.3: end-to-end MSW SSE integration test in ChatApp.integration.test.tsx exercises both approve and deny flows through the production prop chain — drift-prevention layer that catches any future regression dropping chat.approve/chat.approvalPayload from ChatApp
- [Phase 06]: Plan 06-03 call-counter MSW handler installPauseThenResumeHandler — single server.use registration switches behaviour on call number; first call returns paused fresh-turn SSE, second call returns resume SSE with defensive thread_id/approve assertions inside the handler closure
- [Phase 06]: Plan 06-03 deviation: ChatInput Send-button disabled predicate is 'disabled || empty-textarea' — re-enable assertion needs a follow-up keystroke first to disambiguate the inputDisabled-driven lock from the empty-text lock; mirrors pre-existing ChatApp.test.tsx line-79 pattern
- [Phase 07]: Plan 07-01: BE stamps message_id at _drain_events answer-yield site (D-01/D-02) — single source of truth eliminates audit Issue 3 drift class; FE never reconstructs from parts
- [Phase 07]: Plan 07-01: _resume_stream passes cfg_turn (clamped) NOT turn_idx into _drain_events so message_id matches the SAME Langfuse trace the CallbackHandler attached to during the original paused turn — preserves Phase 5 D-14 trace continuity
- [Phase 07]: Plan 07-01 [Rule 2 deviation]: response_node now appends rendered assistant markdown to state.messages on BOTH happy and deny paths — without this the FE resume path renders zero assistants (degenerate) and the plan's _attach_message_ids contract has no rows to stamp; deeper symptom of audit Issue 3 surfaced during RED phase
- [Phase 07]: Plan 07-01: _attach_message_ids uses three-pass derivation (turn_for / last_assistant_per_turn / stamping) mirroring chat.py:_next_turn_idx semantics verbatim — 1 user message = 1 turn; ONLY last assistant per turn carries message_id (D-07); user + non-last assistants get silent absence (D-06)
- [Phase 07]: Plan 07-02: FinalPayload.message_id REQUIRED at type-system boundary (D-04) — TypeScript compiler is the drift-prevention chokepoint, not runtime guards; cascade impact zero because all four shared fixtures propagated the field cleanly
- [Phase 07]: Plan 07-02: handleResume map fallback id is synthetic literal (replay-noncanonical-i) NOT empty string — keeps React reconciliation keys stable while payload.message_id='' tells the MessageList gate (D-08) to suppress FeedbackButtons; two distinct values for two distinct concerns
- [Phase 07]: Plan 07-02 [Rule 2 deviation]: useChatStream.setThreadId added — without it chat.threadId stayed null after every resume click and FeedbackButtons gate's threadId-truthy check silently suppressed feedback on EVERY resumed conversation; deeper bug than audit Issue 3 captured but exactly the class Plan 07-01 Rule 2 deviation hinted at
- [Phase 07]: Plan 07-02: MessageList messageId prop reads m.payload.message_id NOT m.id (D-08) — both equal for canonical rows post-Task 2 but reading from payload makes feedback identity-of-truth visible at the call site; explicit data flow over reuse-the-React-key shortcut
- [Phase 07]: Plan 07-03: Live verification PERFORMED end-to-end (Score row confirmed visible in Langfuse Cloud) but PNG artifact at docs/screenshots/langfuse-feedback-score.png DEFERRED — user chose to capture screenshot later. OBS-02 stays partial until PNG lands.
- [Phase 07]: Plan 07-03: docs/data-sources.md ends with  6-step checklist (D-14); docs/screenshots/.gitkeep reserves langfuse-feedback-score.png filename (D-15); audit Issue 3 closed end-to-end across Plans 07-01 + 07-02 + 07-03 live click — only the lasting PNG evidence remains outstanding.
- [Phase 08]: Plan 08-02: ConversationsProvider colocated with useConversations in single .tsx file (D-06); sentinel-null Context with wrapper hook that throws on null — clear error when called outside provider
- [Phase 08]: Plan 08-02: ChatApp split into outer ChatApp (mounts <ConversationsProvider>) + inner ChatAppInner (consumes via useConversations) — Pitfall 1 mitigation; consumer must sit below provider in React tree
- [Phase 08]: Plan 08-02: useMemo on context value AND narrowed useEffect deps from [conversations] to [conversations.refresh] — defense-in-depth against unbounded refetch loop where every items update would re-create the value object and refire the post-done effect (Pitfall 3)
- [Phase 08]: Plan 08-02: D-14 integration test scopes sidebar assertion to Resume button aria-label (/Resume Surcharge for 15kg Bounce/) — chat-answer markdown also contains preview text so getByText collides; aria-label scoping disambiguates (Rule 1 fix discovered during test execution)
- [Phase 08]: Plan 08-02: ConversationSidebar.test.tsx and SurchargeHistoryChart.test.tsx gained renderWithProvider helpers — Rule 1 fix because provider migration broke standalone component renders; in-scope because direct consumers of useConversations broken by THIS task's changes
- [Phase 999.9]: Plan 01: ORIGIN_DEST_MULTIPLIER 3x3 symmetric matrix replaces legacy single-zone multipliers; diagonal=1.0 preserves v1.0 byte-for-byte (Pitfall 3); off-diagonals 1.25 / 1.45 / 1.70 calibrated by zone-distance
- [Phase 999.9]: Plan 01: hubs.py mirrors _ZONE_INDEX pattern -- _HUB_INDEX built once at module import time; uvicorn restart required to pick up hubs.json edits (matches Phase 2 D-08 baseline cache philosophy)
- [Phase 999.9]: Plan 01: lookup_rate signature change is breaking in arity (3 -> 4); pricing_agent.py:460 still on 3-arg form -- documented inter-wave breakage that Wave 2 Plan 999.9-02 Task 1 closes FIRST so test suite returns to all-green within one merge window
- [Phase 999.9]: Plan 01: hub display strings (the 'name' field in hubs.json) are FULL strings from UI-SPEC -- frontend renders verbatim with zero concatenation; UI-SPEC locks these literals
- [Phase 999.9]: Plan 02: Pitfall 1 — API-boundary default 'hq-lat-krabang' lands in _fresh_stream BEFORE initial_state construction; the agent layer never sees None at planner entry. Consequence: D-09 narration bullet only fires on direct unit calls to pricing_agent_node, not at the API integration layer.
- [Phase 999.9]: Plan 02: _route_matches in planner.py compares state.origin_hub_id == route_data.origin_hub_id when both sides have hub_id information; falls back to legacy free-text origin compare only for pre-999.9 RouteData payloads. Without this, follow-up turns missed the route cache (test_graph.py:test_followup_only_runs_pricing surfaced this — Rule 3 fix in scope of Task 1).
- [Phase 999.9]: Plan 02: D-08 follow-up token-detection extended to origin_hub_id with bare-province expansion. The address 'Mueang Nonthaburi, Nonthaburi' yields tokens [mueang nonthaburi, nonthaburi] PLUS bare 'nonthaburi' (Mueang prefix stripped) so prose like 'What about from Nonthaburi?' is detected. Initial implementation only checked the first comma-split chunk and missed bare-province mentions.
- [Phase 999.9]: Plan 03: Static-import frontend/data/hubs.json over runtime fetch (UI-SPEC §Open Discretion resolution) — simpler, build-time stable, no new endpoint; trade-off is duplication with data/raw/hubs.json that future phase can centralize
- [Phase 999.9]: Plan 03: HubPicker renders ABOVE ChatInput in flex-col wrapper (UI-SPEC §Spacing Scale locked); border-t lifted from ChatInput <form> to wrapper so visual border draws above HubPicker; ChatInput retains p-4 for standalone-test compatibility
- [Phase 999.9]: Plan 03: post-hydration sessionStorage seeding via useEffect([]) avoids SSR mismatch (Pitfall 6); allowlist-guard silently falls back to DEFAULT_HUB_ID on invalid stored values; resume + new-conversation paths preserve originHubId per UI-SPEC §Interaction Contracts
- [Phase 999.10]: Plan 01: GuardCategory Literal extended additively from 5 to 7 members (planner_off_topic, planner_parse_failed appended in stable order); doc comment names which node emits which subset (guard_input_node: first 5; planner_node Plan 02: last 2); zero logic change in guard_input.py — _classify/_DOMAIN_ALLOW_PATTERNS/_llm_fallback/guard_input_node byte-identical otherwise; 345/345 backend pytest green; Wave 1 type-system gate opens for Plan 02 emission edits.
- [Phase 999.10]: Plan 02: _set_guard_refusal helper centralizes the verdict-dict shape (layer='input', refused=True, violations=[]) shared by both planner-tripped refusal branches; placed at module level adjacent to other helpers (between _loop_budget_exhausted and _parse_structured). Both call sites stay declarative ('refuse with this category, route to respond').
- [Phase 999.10]: Plan 02: D-04 (out_of_scope) refusal branch placed IMMEDIATELY after the parse-success assert and BEFORE the origin_hub_id allowlist validation + 999.1 merge — an out_of_scope user message must never reach those downstream blocks because their semantics (logistics extraction, hub lookup, follow-up null-out, fan-out promotion) do not apply to refused messages. Keeps the refusal return shape minimal: just next_step + guard_decision.
- [Phase 999.10]: Plan 02: D-05 (parse_failed) refusal is UNCONDITIONAL inside the D-02 retry loop's attempt==2 block — no further conditioning on user message content (D-06/D-07 invariant). The trigger is the parse exhaustion itself; adding a second-pass classifier would duplicate guard_input's work and risk false-clarifies on legit messages that happen to crash JSON parsing.
- [Phase 999.10]: Plan 02: D-11 trace ownership stays with response_node — planner emits NO refusal trace entry of its own. The existing response_node refusal branch already emits an agent='response' trace entry; adding a planner-tagged refusal trace would either duplicate that entry (poor signal) or split the refusal across two trace nodes (split observability). Matches the existing guard_input -> response_node refusal flow.
- [Phase 999.10]: Plan 03: backend/tests/test_adversarial_pack_regression.py parametrises 4 representative adversarial-pack cases + 1 false-positive guard. CI-deterministic substitute for ROADMAP success criterion 4's manual live re-run; verbatim coupling to adversarial_pack.txt strings means a pack edit forces a test edit (caught at code review). 354/354 backend pytest green (349 baseline + 5 new).
- [Phase 999.10]: Plan 03: PLAN's <action> specified a defensive monkeypatch on `guard_input.get_chat_model` but that attribute doesn't exist at module level (imported lazily inside _llm_fallback at line 134). Removed the monkeypatch and module import; defensive guard was non-load-bearing because GUARD_INPUT_USE_LLM_FALLBACK defaults False and the regex catches the four cases. Layer differentiation still proven by per-case guard_decision.category assertion (injection/off_topic for guard_input cases; planner_off_topic/planner_parse_failed for planner cases).
- [Phase 999.10]: Plan 03: test_legit_baseline_does_not_refuse invokes planner_node directly (not the full graph) — the legit-vs-refusal fork happens entirely inside planner_node, so unit-level assertion is the correct scope. Avoids requiring fuel/route/pricing specialist-agent network mocks for the false-positive regression guard.
- [Phase 999.10]: Plan 03 deviation: executor agent timed out (stream idle) after the RED-stub commit (9a8613a); orchestrator inherited the work via workflow's spot-check fallback rule, wrote the full GREEN test content per the PLAN <action> block, ran pytest (5 pass), committed GREEN (d1156a6), then landed SUMMARY + STATE + ROADMAP + GUARD-07 completion. The RED-stub strategy gave a clear, grep-able marker of exactly where the agent stalled — recovery was mechanical.
- [Phase 999.11]: Plan 01: out-of-process repro harness (subprocess.Popen uvicorn + httpx) with dual wall-clock+elapsed-ms timestamping; D-06 toggles (--skip-coldstart-refresh, --warmup-first) wired for hypothesis (c) isolation; 5-run orchestrator exits 0 only when 5/5 PASS_UNDER_30S
- [Phase 999.11]: Plan 02 RULED OUT (c) cold-start — step 4 combined --warmup-first --skip-coldstart-refresh still fails 5/5 with bit-identical ValueError; proceeding to Plan 03 (b) planner re-loop. Smoking gun: SSE trace planner -> fuel_agent -> planner with next_step=fetch_route despite destination=None.
- [Phase 999.11]: Plan 02 Rule 3 fix to run_5x.sh — `${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}` bash safe-expansion idiom for set -u compatibility when zero extra args passed (step 1 baseline); pre-existing latent bug in Plan 01's deliverable, exposed by Plan 02's zero-arg call site.
- [Phase 999.11]: Plan 02 symptom-shift documented: reproduction surface is fast ~10s deterministic ValueError (route_agent_node requires destination), NOT the original 60s body=0 hang from backlog. Both are critical legit-baseline failures; Plan 03 proceeds on the live signature; Plan 05 reconciles narrative.
- [Phase 999.11]: Plan 03 Hypothesis (b) planner re-loop CONFIRMED + FIXED: destination-less short-circuit in planner_node (4 preconditions: fuel_data populated AND no destination AND no shipping_type AND no weight_kg) routes directly to respond BEFORE LLM invoke, closing the live SSE hang on legit baseline diesel-price query. 5/5 fresh-uvicorn runs PASS_UNDER_30S at ~7.8s. Phase root cause CLOSED. Plan 04 (hypothesis a) becomes NO-OP.
- [Phase 999.11]: Plan 03 D-10 pinning test test_planner_does_not_loop_on_destination_less_baseline_query — pins Phase 11 / FIX-02 root cause (RED on pre-fix, GREEN on post-fix). Defense-in-depth pin test_tool_call_count_reducer_aggregates_parallel_writes mirrors test_parallel_fanout.py for setup, asserts final_state['tool_call_count'] >= 2 to guard the Annotated[int, operator.add] reducer under fan-out against future last-write-wins regressions (passes on current main; pins the invariant).
- [Phase 999.11]: Plan 03 Rule 1 deviation: 3 pre-existing planner tests (test_skips_fetch_when_fuel_fresh, test_planner_no_fanout_when_fuel_fresh, test_trace_tool_output_reflects_post_override_next_step) updated with shipping_type='bounce' state pre-population — they modeled a non-production-realistic synthetic state shape (fresh state with pre-populated fuel_data but no other logistics fields). In real production, a state with cached fuel always inherits prior logistics fields from prior turns via the 999.1 merge; the test updates make them representative of realistic follow-up paths.
- [Phase 999.11]: Plan 04 (a) SSE termination RULED OUT — static analysis trio (response_node returns all carry final_payload; _fresh_stream only intentional approval_required early-return; graph response→END is the only terminal edge) + integration probe via app_with_mocks emitted meta→trace×6→answer→done cleanly with answer.status='ok'. All 3 variants structurally impossible. Defense-in-depth test landed in test_api_chat.py with 'defense-in-depth invariant: Phase 11 / FIX-02 — additive coverage, not the D-10 pin' marker (NO D-10 marker; phase-wide invariant: single D-10 pin lives on Plan 03's test_planner.py:1319).
- [Phase 999.11]: Plan 04 no backend production code modified — chat.py, response_node.py, graph.py, planner.py untouched per must_haves.truths.3 'If RULED OUT: no backend code changes land'. Only files changed: backend/tests/test_api_chat.py (+89 lines test), 999.11-04-EVIDENCE.md (+58 lines closure note), 999.11-04-SUMMARY.md (new). Full backend pytest 358/358 GREEN (+1 over 357 baseline, zero regressions, zero flakes).
- [Phase 999.11]: Plan 04 escalation NOT APPLICABLE — Phase 11 root cause is SINGULAR (hypothesis (b) planner re-loop CONFIRMED + FIXED at commit e550256 in Plan 03), CLOSED before Plan 04 ran. EVIDENCE.md 'Escalation: all three hypotheses RULED OUT' section header present for plan acceptance-criterion compliance, but marked NOT APPLICABLE inline. D-04 escalation clause (Langfuse traces + AgentState snapshots) NOT invoked. No Phase 999.12 follow-up needed. Plan 05 closes the phase with REQUIREMENTS stamp + live-bar gate.
- [Phase 999.11]: Plan 05 Phase 11 closure — FIX-02 stamped Complete (Phase 11) in REQUIREMENTS.md (line 53 + traceability table line 125); ROADMAP.md Phase 11 detail block flipped Status to Complete (2026-05-11), active-phases checklist + Progress table row reflect 5/5 complete; STATE.md Current Position advanced to Phase 999.11 COMPLETE with v1.1 progress 3/3 phases (100%). D-09 live-bar gate honored via Plan 03's post-fix-baseline/summary.jsonl archive per user verdict (no backend code changed between e550256 and HEAD; archive remains representative). Phase-level 999.11-SUMMARY.md is the canonical wrap-up per plan output spec — no per-plan 999.11-05-SUMMARY.md authored. v1.1 milestone now ready for closure via /gsd:complete-milestone. (FIX-02)

### Pending Todos

None yet.

### Blockers/Concerns

(None — all v1.0 blockers resolved)

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260425-vc6 | Rename product scope from Central Region to Bangkok Metro (resolves backlog 999.2-b) | 2026-04-25 | 4889bf6 |  | [260425-vc6-rename-product-scope-from-central-region](./quick/260425-vc6-rename-product-scope-from-central-region/) |
| 260425-vyj | Fix planner bugs 999.1 (state merge on follow-ups) and 999.3 (stale next_step in trace) | 2026-04-25 | 231a54b | Verified | [260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo](./quick/260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo/) |
| 260425-x2i | Fix D-04 loop-budget guard to window per turn (resolves 999.4 — cross-turn short-circuit) | 2026-04-25 | bd27c33 | Smoke-confirmed | [260425-x2i-fix-d-04-loop-budget-guard-to-window-per](./quick/260425-x2i-fix-d-04-loop-budget-guard-to-window-per/) |
| 260503-qzx | Guard pricing_agent against missing route_data/fuel_data (resolves gap-4 from 20-question UAT — KeyError on hallucinated planner routing) | 2026-05-03 | 79d8ee0 | Verified (186/186 backend tests green) | [260503-qzx-guard-pricing-agent-against-missing-rout](./quick/260503-qzx-guard-pricing-agent-against-missing-rout/) |
| 260503-rs8 | Pin langchain==0.3.28 (fixes silent CallbackHandler import failure) + add constant langfuse_trace_name='express-surcharge-agent' to /api/chat trace metadata (OBS-FIX-LANGCHAIN-PIN, OBS-FIX-TRACE-NAME) | 2026-05-03 | 529075f | Verified (186/186 backend tests green; uvicorn restart required for live metadata pickup) | [260503-rs8-pin-langchain-dep-set-langfuse-trace-nam](./quick/260503-rs8-pin-langchain-dep-set-langfuse-trace-nam/) |
| 260503-s2h | Set top-level RunnableConfig.run_name='express-surcharge-agent' so Langfuse Observations 'Name' column matches 'Trace Name' column from 260503-rs8 (OBS-FIX-RUN-NAME) | 2026-05-03 | 0606e43 | Verified (186/186 backend tests green; uvicorn restart required for live root-span-name pickup) | [260503-s2h-set-runnableconfig-run-name-so-langfuse-](./quick/260503-s2h-set-runnableconfig-run-name-so-langfuse-/) |
| 260509-e0p | Restyle frontend with dark cosmic glass morphism theme (Tailwind v4 @theme tokens + glass-surface/glass-panel/brand-gradient @utility classes + static gradient mesh body background; 23 view components reskinned) | 2026-05-09 | b4e6fa2, 3e56e2a | Verified visually + readability follow-ups (PR #11 merged) | [260509-e0p-i-want-to-change-our-application-theme-i](./quick/260509-e0p-i-want-to-change-our-application-theme-i/) |
| 260509-eum | Backend cold-start fuel-price refresh: lifespan schedules background asyncio task; reuses fetch_fuel_prices.refresh_csv with timezone-aware (Asia/Bangkok) staleness predicate; D-03 log-and-continue on any failure (QUICK-260509-EUM-01..03) | 2026-05-09 | 9bf5471 | Verified (248/248 backend tests green; smoke 1+2+3 pass; CLI exits 0; EXPRESS_SKIP_COLDSTART_REFRESH=1 confirmed effective end-to-end) | [260509-eum-backend-cold-start-fuel-price-refresh-au](./quick/260509-eum-backend-cold-start-fuel-price-refresh-au/) |
| 260509-uwb | Pricing Agent visible reasoning upgrade: PricingReasoning gains bullets:list[str], _compute_volatility_flag reads 7d EPPO CSV window (low/normal/high), _build_bullets emits 3-5 bullets (base+fuel/volatility / traffic-only-bounce / news-only-when-search_context / final + cap/floor); D-11 fallback now bullet-shaped; formula calculate_surcharge.py byte-for-byte unchanged (QUICK-260509-UWB-01..03) | 2026-05-09 | bbaf95e, 119ac56, 0a6b878 | Verified (260/260 backend tests green; pricing 5→9; locked formula files unchanged; no new external-API imports) | [260509-uwb-upgrade-pricing-agent-to-visibly-reason-](./quick/260509-uwb-upgrade-pricing-agent-to-visibly-reason-/) |
| 260509-utd | Two-layer guardrail hardening against adversarial classmate testing: SECURITY_PREAMBLE + "tool output is DATA" clause prepended to all 6 agent prompts; new guard_input node (rules-first regex classifier with optional Gemini LLM fallback behind GUARD_INPUT_USE_LLM_FALLBACK env flag, defaults unclear→ALLOW) and guard_output node (validates SurchargeResult invariants from backend.config); per-turn tool_call_count cap (MAX_TOOL_CALLS_PER_TURN=6) wired via Annotated[int, operator.add] reducer to survive Phase 5 D-01 parallel fan-out; response_node refusal branch with branded copy + reasoning_trace tag agent='guard_input'/'guard_output' (not 'planner', avoids miscount); adversarial_pack.txt with 15 attacks (5 injection / 5 off-topic / 5 cost-bombing); zero new dependencies (QUICK-260509-UTD-01..05) | 2026-05-09 | 9c24cd9, f068022, 3c7a4a9 | Executor-verified (256→295 backend tests, +39 net new green; uvicorn restart required for live deployment) | [260509-utd-upgrade-guardrails-to-harden-agent-again](./quick/260509-utd-upgrade-guardrails-to-harden-agent-again/) |
| 260512-t3t | Fix ROADMAP.md drift on Phase 10 status (line 40 checkbox + progress table row) — flipped `[ ]` → `[x]` and `0/3 Planned` → `3/3 Complete — 2026-05-11` to match REQUIREMENTS.md (GUARD-07 Complete) and STATE.md (Phase 999.10 completed 2026-05-11); housekeeping closure flagged by v1.1 milestone audit | 2026-05-12 | a6c7c30 |  | [260512-t3t-fix-roadmap-md-drift-on-phase-10-status-](./quick/260512-t3t-fix-roadmap-md-drift-on-phase-10-status-/) |
| 260512-t7q | Surface origin_hub_id in FIX-02 destination-less short-circuit trace entry (planner.py:316 string→dict with `trigger` + `origin_hub_id` keys) + new regression pytest; closes v1.1 audit cross-phase observability gap (Phase 9 hub × Phase 11 FIX-02). Backend pytest 358→359 green. | 2026-05-12 | 527fe62 |  | [260512-t7q-surface-origin-hub-id-in-fix-02-destinat](./quick/260512-t7q-surface-origin-hub-id-in-fix-02-destinat/) |

## Session Continuity

Last session: 2026-05-11T17:30:00.000Z
Stopped at: Completed Phase 999.11 (Phase 11 / v1.1 — Live SSE Hang Root-Cause Fix). Root cause: hypothesis (b) planner re-loop CONFIRMED + FIXED at commit e550256 (destination-less short-circuit in planner_node); hypotheses (c) cold-start and (a) SSE termination cleanly RULED OUT. Backend pytest 355 -> 358 (+3: D-10 pin + 2 defense-in-depth). 5/5 live-bar runs PASS_UNDER_30S at ~7.6-7.9s (D-09 demo gate cleared). FIX-02 marked Complete (Phase 11) in REQUIREMENTS.md with 'Validated in v1.1: Phase 11' suffix. Branch: develop. Next: v1.1 milestone closure (run /gsd:complete-milestone) or W6 demo recording.
Resume file: None
Next: Demo recording (W6); or close v1.1 milestone with milestone audit via /gsd:complete-milestone. Pre-existing ROADMAP.md drift on Phase 10 active-checklist + Progress table row logged to .planning/phases/999.11-.../deferred-items.md (out of scope for Plan 05; fix in housekeeping commit or milestone audit).
