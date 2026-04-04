# Express Dynamic Surcharge Orchestrator

## What This Is

An Agentic AI product that dynamically calculates fuel surcharges for Express logistics operations in Thailand's Central Region. The agent reasons over live fuel prices, route data, and internal rate tables to produce surcharge recommendations — it is the core decision-making product, not a feature on a dashboard. Built as a MADT7204 course project demonstrating multi-agent AI architecture with real-world logistics impact.

## Core Value

The agent must transparently reason through fuel price, route, and shipping data to produce an accurate, explainable surcharge recommendation — visible reasoning is what makes this agentic, not just automated.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Planner agent orchestrates specialist sub-agents via LangGraph conditional routing
- [ ] Fuel Agent fetches live diesel prices from EPPO/PTT API with multi-level fallback chain (API → scrape → cached CSV → last-known)
- [ ] Route Agent calculates distance and traffic via Google Maps API with 15-min caching
- [ ] Pricing Agent computes surcharge using rate table lookup + formula with shipping type multipliers
- [ ] Fuel and Route agents execute in parallel (LangGraph Send API) since they are independent
- [ ] All agent responses use structured Pydantic output models for deterministic, testable results
- [ ] Human-in-the-loop approval gate for high-value shipment surcharge recommendations
- [ ] Agentic retry loop: agent autonomously retries with exponential backoff on tool failure, falls back gracefully
- [ ] Three shipping types supported: Bounce (B2B, 1.0x multiplier), Retail Standard (B2C 3-5 day, 0.5x), Retail Fast (B2C same/next-day, 0.8x)
- [ ] Surcharge formula with configurable baseline, shipping type multipliers, traffic adjustment (Bounce only), and cap/floor (max 15%, min -5%)
- [ ] Three Central Region zones: central-1 (Bangkok inner), central-2 (Bangkok outer), central-3 (extended central)
- [ ] Rate table stored in SQLite with 3 shipping types, 3 zones, multiple weight tiers
- [ ] Conversation memory via LangGraph SQLite checkpointer — follow-up questions reuse cached data
- [ ] Reasoning trace visible in UI — every agent step, tool call, and decision logged and displayed
- [ ] Chat-based UI for querying surcharges with SSE streaming
- [ ] Dashboard showing surcharge trends across routes, shipping types, and time periods (Recharts)
- [ ] User feedback (thumbs up/down) forwarded to Langfuse for evaluation scoring
- [ ] Tavily web search tool for fuel news context and trend reasoning
- [ ] Data pipeline: fetch_fuel_prices.py (daily EPPO), generate_rate_table.py (simulated), seed_database.py (CSV → SQLite)
- [ ] FastAPI backend with endpoints: POST /api/chat (SSE), GET /api/conversations, GET /api/fuel-prices, POST /api/feedback
- [ ] Next.js 15 + React 19 + Tailwind CSS frontend

### Out of Scope

- Multi-region support beyond Central Region — scope limited for course timeline
- Real-time webhook push notifications — polling/SSE sufficient for demo
- Mobile native app — web-first, responsive design only
- OAuth/social login — not relevant to agent architecture grading
- Production deployment infrastructure — local reproducibility is the requirement
- Rate table admin CRUD — rate data is seeded via scripts, not managed in-app

## Context

**Course:** MADT7204 Vibe Coding Project — "Bangkok Oil Price Crisis: Build an Agentic AI Solution"
**Timeline:** 6 weeks total. Repo created, architecture drafted. Now entering build phase (W2-W4).
**Team:** 1 IT Lead (you) + 5 Management Members. IT Lead owns agent architecture, codebase, tools, data pipeline, Git, and technical docs.
**Grading (IT Lead):** Agent Architecture & Technical Execution (35%), Data Integration (20%), Technical Documentation & Git Practice (20%), AI/Vibe-Coding Tool Leverage (15%), Team Technical Leadership (10%).
**Key grading insight:** "The agent is the product — not a feature bolted onto a CRUD app." Optional enhancements that earn extra marks: multi-agent pattern, RAG, memory, agentic loop. This architecture targets all four.

**Existing scaffold:** Directory structure follows brief requirements. Architecture doc (`docs/architecture.md`) is the detailed technical reference with agent state schema, tool specs, surcharge formula, zone definitions, API endpoints, and error handling.

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
| LangGraph over CrewAI/AutoGen | Stateful graph with conditional routing best demonstrates agent orchestration patterns | -- Pending |
| Gemini 2.0 Flash | Free tier, sufficient for reasoning; matches budget constraint | -- Pending |
| SQLite over Postgres | Zero-config, file-based; simplifies local reproducibility (grading requirement) | -- Pending |
| Parallel Fuel+Route agents | Independent data fetches; demonstrates LangGraph Send API sophistication | -- Pending |
| Structured Pydantic outputs | Deterministic agent responses; testable; shows engineering rigor | -- Pending |
| Human-in-the-loop gate | Demonstrates agent safety patterns; differentiator for grading | -- Pending |
| Multi-level fuel fallback | EPPO API → PTT → cached CSV → hardcoded; shows resilience design | -- Pending |
| SSE streaming for chat | Real-time token streaming; better UX for reasoning trace visibility | -- Pending |

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
*Last updated: 2025-04-04 after initialization*
