# Express Dynamic Surcharge Orchestrator

## What This Is

An Agentic AI product that dynamically calculates fuel surcharges for Express logistics operations in Thailand's Bangkok Metro. The agent reasons over live fuel prices, route data, and internal rate tables to produce surcharge recommendations — it is the core decision-making product, not a feature on a dashboard. Built as a MADT7204 course project demonstrating multi-agent AI architecture with real-world logistics impact.

## Core Value

The agent must transparently reason through fuel price, route, and shipping data to produce an accurate, explainable surcharge recommendation — visible reasoning is what makes this agentic, not just automated.

## Current State: Between Milestones (v1.1 Shipped 2026-05-12)

**Status:** v1.1 milestone complete. Code freeze for W5 / W6 final demo recording. No active milestone.

**Most recent milestone — v1.1 Real-World Routing & Demo Hardening:** Shipped 2026-05-12 after a 4-day burndown (102 commits; +7241/-348 LOC across 69 source files). Closed the gap from synthetic origin-destination pairs to a real 10-hub Express network (HQ + 9 branches) with HubPicker UI + 135-row origin × destination rate matrix, unified refusal copy across `guard_input` and planner bypass paths, and root-cause-fixed the live SSE hang on the legit baseline diesel-price query (W6 demo gate cleared at 5/5 fresh-uvicorn runs PASS_UNDER_30S at ~7.6–7.9 s). 22/22 v1.1 requirements satisfied (10 active phase-mapped + 12 retroactive via quick tasks + debugs). See [.planning/milestones/v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md).

**Next actions:** Record W6 demo video against the shipped product, then `/gsd:new-milestone` if a v1.2 / v2.0 cycle is desired.

## Requirements

### Validated

- [x] All agent responses use structured Pydantic output models for deterministic, testable results — Validated in Phase 1: Foundation & Data Pipeline
- [x] Three shipping types supported: Bounce (B2B, 1.0x multiplier), Retail Standard (B2C 3-5 day, 0.5x), Retail Fast (B2C same/next-day, 0.8x) — Validated in Phase 1: Foundation & Data Pipeline
- [x] Surcharge formula with configurable baseline, shipping type multipliers, traffic adjustment (Bounce only), and cap/floor (max 15%, min -5%) — Validated in Phase 1: Foundation & Data Pipeline
- [x] Three Bangkok Metro zones: central-1 (Bangkok inner), central-2 (Bangkok outer), central-3 (extended central) — Validated in Phase 1: Foundation & Data Pipeline
- [x] Rate table stored in SQLite with 3 shipping types, 3 zones, multiple weight tiers — Validated in Phase 1: Foundation & Data Pipeline
- [x] Data pipeline: fetch_fuel_prices.py (daily EPPO), generate_rate_table.py (simulated), seed_database.py (CSV → SQLite) — Validated in Phase 1: Foundation & Data Pipeline
- [x] Planner agent orchestrates specialist sub-agents via LangGraph conditional routing — Validated in Phase 3: Graph Assembly & API Layer
- [x] Pricing Agent computes surcharge using rate table lookup + formula with shipping type multipliers — Validated in Phase 3: Graph Assembly & API Layer
- [x] Agentic retry loop: agent autonomously retries with exponential backoff on tool failure, falls back gracefully — Validated in Phase 3: Graph Assembly & API Layer
- [x] Conversation memory via LangGraph SQLite checkpointer — follow-up questions reuse cached data — Validated in Phase 3: Graph Assembly & API Layer
- [x] Reasoning trace visible in UI — every agent step, tool call, and decision logged and displayed — Validated in Phase 4: Frontend & Reasoning Trace
- [x] Chat-based UI for querying surcharges with SSE streaming — Validated in Phase 4: Frontend & Reasoning Trace
- [x] Dashboard showing surcharge trends across routes, shipping types, and time periods (Recharts) — Validated in Phase 4: Frontend & Reasoning Trace
- [x] Next.js 15 + React 19 + Tailwind CSS frontend — Validated in Phase 4: Frontend & Reasoning Trace
- [x] Human-in-the-loop approval gate for high-value shipment surcharge recommendations — Validated in Phase 6: HITL Approval UI Wiring + Compile Fix
- [x] User feedback (thumbs up/down) forwarded to Langfuse for evaluation scoring — Validated in Phase 7: Feedback Contract Alignment

- [x] Fuel Agent fetches diesel prices via 3-level fallback chain (live scrape stub → cached CSV → hardcoded baseline) — Validated in Phase 2: Tools & Agent Nodes (TOOL-01)
- [x] Route Agent calculates distance, duration, and traffic severity via Google Maps Directions + 15-min TTL cache — Validated in Phase 2: Tools & Agent Nodes (TOOL-02)
- [x] Fuel and Route agents execute in parallel via LangGraph list-returning conditional edge (~165µs trace delta) — Validated in Phase 5: Polish, Observability & Docs (ORCH-07)
- [x] Tavily web search tool for fuel news context with TTL cache and graceful-warn node — Validated in Phase 5/8 (TOOL-05)
- [x] FastAPI backend with POST /api/chat (SSE), GET /api/conversations, GET /api/fuel-prices, POST /api/feedback — Validated in Phase 3/5/7 (API-01..05)
- [x] Langfuse observability — per-turn callback handler, formula_accuracy auto-eval, user_feedback Score forwarding — Validated in Phase 5/7 (OBS-01/02/03)

<!-- v1.1 retroactively-validated work (shipped before formal milestone declaration) -->
- [x] Dark cosmic glass-morphism UI theme across 23 view components (Tailwind v4 @theme tokens + glass-surface/glass-panel/brand-gradient utilities) — Validated in v1.1: Quick task 260509-e0p
- [x] Cold-start fuel-price refresh on FastAPI lifespan — `is_csv_stale` + `refresh_csv` with timezone-aware (Asia/Bangkok) staleness predicate; D-03 log-and-continue on failure — Validated in v1.1: Quick task 260509-eum
- [x] Pricing Agent emits 3-5 visible reasoning bullets with 7-day fuel-volatility flag (low/normal/high); deterministic-fallback bullet shape preserved — Validated in v1.1: Quick task 260509-uwb
- [x] Two-layer adversarial guardrails: SECURITY_PREAMBLE on all agent prompts, guard_input rules-first regex classifier, guard_output SurchargeResult-invariant validator, per-turn `tool_call_count` cap (=6) via `Annotated[int, operator.add]` reducer, branded refusal copy + adversarial_pack.txt (15 attacks) — Validated in v1.1: Quick task 260509-utd
- [x] EPPO fuel-price scraper rewritten after EPPO site URL + Excel structure restructure — Validated in v1.1: Debug 999.6
- [x] 90-day daily fuel-price history backfilled via Bangchak historical scraper — Validated in v1.1: Debug 999.7
- [x] Resume flow no longer appends duplicate assistant message on conversation reload — Validated in v1.1: Debug 999.5
- [x] Unified refusal copy on planner bypass paths — `out_of_scope` LLM-tagged + `parse_failed` exhaustion both set `guard_decision` and route to `response_node` refusal branch; CI-deterministic regression across 4 adversarial-pack cases — Validated in Phase 10 / 999.10 (GUARD-07)
- [x] Live SSE hang root-cause fix on legit baseline diesel-price query — destination-less follow-up short-circuit in `planner_node` (pre-LLM, fires when `fuel_data` cached and all logistics fields null) prevents the cache-aware override at `planner.py:509` from promoting `next_step="fetch_route"` on null destination; 5/5 fresh-uvicorn runs PASS_UNDER_30S at ~7.6-7.9s with `answer + done` events — Validated in Phase 11 / 999.11 (FIX-02)

<!-- v1.1 Validated (all shipped 2026-05-09 → 2026-05-12) -->
- [x] HQ/branch origin model: 10-hub network (1 HQ + 9 branches), HubPicker UI, single-leg routing, 135-row origin×destination rate matrix — Validated in v1.1 / Phase 9 (HUB-01..08)
- [x] Unified refusal copy on planner bypass paths (`out_of_scope` + `parse_failed` render REFUSAL_COPY + `status='refused'` like guard_input) — Validated in v1.1 / Phase 10 (GUARD-07)
- [x] Live `POST /api/chat` no longer hangs on legit baseline diesel-price query — root cause was destination-less follow-up over-routing in `planner_node`; pre-LLM short-circuit fix; 5/5 fresh-uvicorn runs PASS_UNDER_30S at ~7.6–7.9 s — Validated in v1.1 / Phase 11 (FIX-02)

### Active

<!-- No active requirements — between milestones. Run /gsd:new-milestone to define v1.2 / v2.0 scope. -->

(None — v1.1 shipped 2026-05-12. v2 candidate requirements captured in [milestones/v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md) §"v2 Requirements".)

### Out of Scope

- Multi-region support beyond Bangkok Metro — scope limited for course timeline
- Real-time webhook push notifications — polling/SSE sufficient for demo
- Mobile native app — web-first, responsive design only
- OAuth/social login — not relevant to agent architecture grading
- Production deployment infrastructure — local reproducibility is the requirement
- Rate table admin CRUD — rate data is seeded via scripts, not managed in-app

## Context

**Course:** MADT7204 Vibe Coding Project — "Bangkok Oil Price Crisis: Build an Agentic AI Solution"
**Timeline:** Shipped v1.0 in 32 days (2026-04-04 → 2026-05-05). Code freeze for final submission.
**Team:** 1 IT Lead + 5 Management Members. IT Lead owns agent architecture, codebase, tools, data pipeline, Git, and technical docs.
**Grading (IT Lead):** Agent Architecture & Technical Execution (35%), Data Integration (20%), Technical Documentation & Git Practice (20%), AI/Vibe-Coding Tool Leverage (15%), Team Technical Leadership (10%).
**Key grading insight:** "The agent is the product — not a feature bolted onto a CRUD app." All four optional enhancements were targeted and shipped: multi-agent pattern (planner + 4 specialists), RAG-style tool augmentation (Tavily), conversation memory (AsyncSqliteSaver), and agentic retry loop (D-22 RetryPolicy + D-24 error sink).

**Current State (v1.1 shipped 2026-05-12):**
- 11 phases (8 v1.0 + 3 v1.1), 48 plans, ~113 tasks, 162+ feat commits across both milestones
- ~23,000 LOC across Python (backend) + TypeScript (frontend) — +7,241/-348 LOC delta during v1.1 across 69 source files
- 358/358 backend pytest pass, 145/145 frontend vitest pass
- 22/22 v1.1 requirements satisfied + 43/43 v1.0 requirements still satisfied (65/65 total)
- All 6 E2E flows fully wired (v1.1): cold-start happy path + prose override + cross-zone surcharge + adversarial off-topic + adversarial parse-fail + follow-up turn `origin_hub_id` inheritance
- W6 demo gate cleared: 5/5 fresh-uvicorn runs of legit baseline diesel-price query PASS_UNDER_30S at ~7.6–7.9 s on commit e550256
- Live observability proven: Langfuse Cloud trace `express-surcharge-agent` carrying `formula_accuracy` + `user_feedback` Scores
- All 6 submission screenshots landed; demo.mp4 still deferred (W6 recording window)
- v1.0.0 git tag pending on main merge commit; v1.1 git tag created 2026-05-12

**Tech debt accepted into v1.1 (8 items across 3 phases — non-functional / documentation hygiene):**
- Phase 9 (999.9): no phase-level `999.9-SUMMARY.md`; Plans 02 + 03 use design-decision markers in `requirements-completed` frontmatter instead of HUB-XX REQ-IDs; `999.9-VALIDATION.md` `wave_0_complete: false` stale
- Phase 10 (999.10): no phase-level `999.10-SUMMARY.md`; `999.10-VALIDATION.md` was reconstructed retroactively
- Phase 11 (999.11): `999.11-VALIDATION.md` `wave_0_complete: false` stale; `repro/logs/final/summary.jsonl` never created (user-authorized deviation — canonical D-09 evidence at `repro/logs/post-fix-baseline/summary.jsonl`)

**Tech debt inherited from v1.0 (still accepted):**
- `_scrape_eppo_live()` remains intentional NotImplementedError stub — CSV fallback returns real data (DATA-02 satisfied)
- Nyquist VALIDATION.md drafts exist for phases 1, 4, 5, 8 (not load-bearing; tests pass)

**Tech stack (locked):**
- LLM: Google Gemini 2.0 Flash (free tier)
- Agent framework: LangGraph
- Backend: FastAPI + Uvicorn
- Frontend: Next.js 15 + React 19 + Tailwind CSS
- Database: SQLite (rate tables + checkpoints)
- Observability: Langfuse (tracing + evaluation)
- External APIs: EPPO/PTT (fuel), Google Maps (routing), Tavily (search)
- Charts: Recharts

**POV deck:** Frames the business case around profitability protection, pricing agility, operational efficiency, and management transparency via reasoning trace.

## Constraints

- **Budget**: Free-tier APIs only — Gemini Flash, Google Maps ($200/mo credit), EPPO public data
- **LLM**: Gemini 2.0 Flash only — no paid model APIs
- **Timeline**: 6 weeks total; W5 is code freeze + docs, W6 is final demo
- **Repo structure**: Must follow brief-mandated layout (agent/, app/, data/, docs/, notebooks/)
- **Secrets**: Never commit .env — .env.example required, violations affect grade
- **Git practice**: Descriptive commit messages, feature branches, IT Lead holds majority of commits — graded at 20%
- **Data**: At least one real dataset must be queried by agent (EPPO fuel prices satisfy this)
- **Submission**: Tag final commit as v1.0, submit repo URL

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LangGraph over CrewAI/AutoGen | Stateful graph with conditional routing best demonstrates agent orchestration patterns | ✓ Good — D-12 cache override + D-22 RetryPolicy + AsyncSqliteSaver + interrupt() all leveraged framework features cleanly |
| Gemini 2.0 Flash | Free tier, sufficient for reasoning; matches budget constraint | ✓ Good — 15 RPM was never the bottleneck; D-11 deterministic fallback handles parse failures |
| SQLite over Postgres | Zero-config, file-based; simplifies local reproducibility (grading requirement) | ✓ Good — express.db (rates) + checkpoints.db (LangGraph state) ship in repo; AsyncSqliteSaver wires cleanly via lifespan |
| Parallel Fuel+Route agents | Independent data fetches; demonstrates LangGraph Send API sophistication | ✓ Good — list-returning conditional edge over Send API was the smaller/safer change; ~165µs trace delta visible |
| Structured Pydantic outputs | Deterministic agent responses; testable; shows engineering rigor | ✓ Good — 5 tool I/O models + AgentState v3 TypedDict; D-11 deterministic narration fallback when LLM JSON parse fails |
| Human-in-the-loop gate | Demonstrates agent safety patterns; differentiator for grading | ✓ Good — `interrupt()` + `Command(resume)` + 6th SSE `approval_required` event; integration test covers approve + deny |
| Multi-level fuel fallback | EPPO API → PTT → cached CSV → hardcoded; shows resilience design | ✓ Good — 3-level chain with NotImplementedError for live scrape (intentional stub); CSV fallback serves real data |
| SSE streaming for chat | Real-time token streaming; better UX for reasoning trace visibility | ✓ Good — manual `data: {json}\n\n` framing + Cache-Control + X-Accel-Buffering headers; per-turn `meta → trace+ → answer → done` envelope |
| Bangkok Metro scope (vs Central Region) | Smaller blast radius than expanding zones; matches actual rate-table coverage | ✓ Good — 999.2 backlog resolved via doc rename; gap-2 selective ValueError catch handles out-of-Metro destinations gracefully |
| Wholesale README rewrite (DOC-01) | Phase 4-era README missing Phase 5 differentiator narrative | ✓ Good — 9 sections + Mermaid topology + AI Tools + Limitations land the AI/Vibe-Coding 15% rubric |
| `message_id = {thread_id}-{turn_idx}` BE-stamp | Single source of truth eliminates audit Issue 3 drift class | ✓ Good — TS type system enforces presence; round-trip Vitest+MSW tests prevent regression |
| `useConversations` Context Provider | Single shared instance for sidebar refresh after `done` event | ✓ Good — closes audit Issue 4; D-14 integration test verifies second `GET /api/conversations` after answer |
| Per-zone (not per-hub) origin in rate table | 3 origin zones × 3 dest zones = 9 cells × 3 ship × 5 weight = 135 rows; per-hub would be 450 rows for 10 hubs with no business signal added | ✓ Good (v1.1 / Phase 9) — symmetric ORIGIN_DEST_MULTIPLIER matrix; v1.0 central-1 rates preserved byte-for-byte; `lookup_rate` 4-arg signature added without renaming the 3-arg call sites |
| Single-leg pricing model (vs two-leg HQ → branch → destination) | Matches how Kerry/Flash/Thailand Post quote shipments; user-facing pricing narrative simpler; deferred two-leg to v2 (PRICE-03) | ✓ Good (v1.1 / Phase 9) — pricing_agent narrates origin zone via `hub_label_for` + `origin_zone_for`; "Origin unspecified" bullet prepended when defaulted to HQ |
| Additive `GuardCategory` Literal extension (`planner_off_topic`, `planner_parse_failed`) | Type-system gate opens before emission sites; keeps `state.guard_decision.layer = 'input'` so the existing `response_node` refusal predicate continues working | ✓ Good (v1.1 / Phase 10) — adversarial_pack cases 2 + 4 now return `status='refused'` + REFUSAL_COPY (previously `clarify`); cases 1 + 3 unchanged |
| Pre-LLM destination-less short-circuit in `planner_node` | Root-cause fix for the live SSE hang on the legit baseline diesel-price query; the cache-aware override at `planner.py:509` was unconditionally promoting destination-less follow-ups to `fetch_route` after fuel was cached, causing `route_agent` to ValueError on null destination and the SSE stream to emit `done` with errors[] | ✓ Good (v1.1 / Phase 11) — 5/5 fresh-uvicorn runs PASS_UNDER_30S at ~7.6–7.9 s on the legit baseline; W6 demo gate cleared; hypotheses (c) cold-start and (a) SSE termination cleanly RULED OUT |
| Sequential hypothesis investigation (c) → (b) → (a) over diagnosis-by-mitigation | Prevents premature workaround; each hypothesis ruled out with reproducible evidence (`999.11-02-EVIDENCE.md` / `999.11-03-EVIDENCE.md` / `999.11-04-EVIDENCE.md`) before moving to next | ✓ Good (v1.1 / Phase 11) — fresh-uvicorn + httpx probe harness deterministically reproduced the hang; root cause confirmed before fix landed |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-12 after v1.1 milestone close — Real-World Routing & Demo Hardening shipped; 22/22 v1.1 requirements satisfied; W6 demo gate cleared; no active milestone (between-milestone state); next action is W6 demo recording or `/gsd:new-milestone` for v1.2/v2.0.*
