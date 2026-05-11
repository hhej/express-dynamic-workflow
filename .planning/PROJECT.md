# Express Dynamic Surcharge Orchestrator

## What This Is

An Agentic AI product that dynamically calculates fuel surcharges for Express logistics operations in Thailand's Bangkok Metro. The agent reasons over live fuel prices, route data, and internal rate tables to produce surcharge recommendations — it is the core decision-making product, not a feature on a dashboard. Built as a MADT7204 course project demonstrating multi-agent AI architecture with real-world logistics impact.

## Core Value

The agent must transparently reason through fuel price, route, and shipping data to produce an accurate, explainable surcharge recommendation — visible reasoning is what makes this agentic, not just automated.

## Current Milestone: v1.1 Real-World Routing & Demo Hardening

**Goal:** Move from synthetic origin-destination pairs to a real Express hub network, tighten the agent against adversarial inputs, and ensure fuel data stays fresh — making the v1.0 demo bulletproof for W6 grading.

**Target features:**
- HQ/branch origin model — sender picks hub via dropdown or prose; single-leg routing from chosen hub to destination (Phase 9 / 999.9)
- Unified refusal copy on planner bypass paths — `out_of_scope` and `parse_failed` render the same locked `REFUSAL_COPY` as guard_input trips (Phase 10 / 999.10)
- Live SSE hang root-cause fix on legit baseline diesel-price query — demo-gating for W6 (Phase 11 / 999.11)
- Already shipped this milestone (retroactive): dark cosmic glass UI theme, cold-start fuel refresh, pricing-agent reasoning bullets with volatility flag, two-layer adversarial guardrails, EPPO scraper rewrite, 90-day Bangchak backfill, resume-flow duplicate-message fix

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

### Active

<!-- v1.1 in-flight requirements — formalized in REQUIREMENTS.md -->

- [ ] HQ/branch origin model: 10-hub network (1 HQ + 9 branches), HubPicker UI, single-leg routing, 135-row origin×destination rate matrix (Phase 9 / 999.9)
- [ ] Live SSE hang on legit baseline diesel-price query — investigate AND fix root cause (cold-start vs reducer vs SSE termination); 5-fresh-uvicorn-runs verification bar (Phase 11 / 999.11)

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

**Current State (v1.0 shipped 2026-05-05):**
- 8 phases, 36 plans, 87 tasks, 60+ feat commits
- ~16,000 LOC across Python (backend) + TypeScript (frontend)
- 194/194 backend pytest pass, 122/122 frontend vitest pass
- 43/43 v1 requirements satisfied (3-source cross-reference verified)
- All 4 E2E flows fully wired: surcharge happy path, follow-up cache reuse, HITL high-value approval, Tavily news_query
- Live observability proven: Langfuse Cloud trace `express-surcharge-agent` carrying `formula_accuracy` + `user_feedback` Scores
- 5 of 6 submission screenshots landed (`langfuse-feedback-score.png`, `chat-breakdown.png`, `trace-parallel.png`, `dashboard.png`, `hitl-approval.png`, `langfuse-trace.png`); demo.mp4 deferred
- v1.0.0 git tag pending on main merge commit

**Tech debt accepted into v1.0:**
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
*Last updated: 2026-05-11 — Phase 10 / 999.10 (Unify Refusal Copy on Planner Bypass Paths, GUARD-07) moved Active → Validated. Active now: HQ/branch (Phase 9 — also moved Validated separately in its own update) and Phase 11 (Live SSE Hang Root-Cause Fix).*
