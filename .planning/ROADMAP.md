# Roadmap: Express Dynamic Surcharge Orchestrator

## Milestones

- ✅ **v1.0 MVP** — Phases 1–8 (shipped 2026-05-05) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Real-World Routing & Demo Hardening** — Phases 9–11 (shipped 2026-05-12) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–8) — SHIPPED 2026-05-05</summary>

- [x] Phase 1: Foundation & Data Pipeline (3/3 plans) — completed 2026-04-08
- [x] Phase 2: Tools & Agent Nodes (5/5 plans) — completed 2026-04-18
- [x] Phase 3: Graph Assembly & API Layer (5/5 plans) — completed 2026-04-25
- [x] Phase 4: Frontend & Reasoning Trace (5/5 plans) — completed 2026-04-26
- [x] Phase 5: Polish, Observability & Docs (10/10 plans) — completed 2026-05-03
- [x] Phase 6: HITL Approval UI Wiring + Compile Fix (3/3 plans) — completed 2026-05-04 (gap closure)
- [x] Phase 7: Feedback Contract Alignment (3/3 plans) — completed 2026-05-04 (gap closure)
- [x] Phase 8: Search Context Wiring + Sidebar Polish (2/2 plans) — completed 2026-05-05 (gap closure)

**Delivered:** Multi-agent LangGraph orchestrator with parallel fan-out, HITL approval gate, Tavily search, full Langfuse observability, Next.js 15 chat UI with reasoning trace + dashboard. 43/43 v1 requirements satisfied. See [milestones/v1.0-MILESTONE-AUDIT.md](milestones/v1.0-MILESTONE-AUDIT.md).

</details>

<details>
<summary>✅ v1.1 Real-World Routing & Demo Hardening (Phases 9–11) — SHIPPED 2026-05-12</summary>

- [x] Phase 9: HQ/Branch Origin Model (4/4 plans) — completed 2026-05-10
- [x] Phase 10: Unify Refusal Copy on Planner Bypass Paths (3/3 plans) — completed 2026-05-11
- [x] Phase 11: Live SSE Hang Root-Cause Fix (5/5 plans) — completed 2026-05-11

**Delivered:** Moved from synthetic origin-destination pairs to a real 10-hub Express network (HQ + 9 branches) with 135-row origin × destination rate matrix and HubPicker UI; unified `REFUSAL_COPY` + `status='refused'` across `guard_input` and planner bypass paths (`out_of_scope` + `parse_failed`); root-cause-fixed the live `POST /api/chat` hang on the legit baseline diesel-price query via a pre-LLM destination-less short-circuit in `planner_node` (5/5 fresh-uvicorn runs PASS_UNDER_30S at ~7.6–7.9 s). 22/22 v1.1 requirements satisfied (10 active phase-mapped + 12 retroactive via quick tasks 260509-e0p/-eum/-uwb/-utd and debug 999.5/999.6/999.7). W6 demo gate cleared. See [milestones/v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md).

</details>

## Progress

**Execution Order:** v1.0 closed at Phase 8. v1.1 closed at Phase 11. No active milestone — code freeze for W5; W6 final demo recording.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & Data Pipeline | v1.0 | 3/3 | Complete | 2026-04-08 |
| 2. Tools & Agent Nodes | v1.0 | 5/5 | Complete | 2026-04-18 |
| 3. Graph Assembly & API Layer | v1.0 | 5/5 | Complete | 2026-04-25 |
| 4. Frontend & Reasoning Trace | v1.0 | 5/5 | Complete | 2026-04-26 |
| 5. Polish, Observability & Docs | v1.0 | 10/10 | Complete | 2026-05-03 |
| 6. HITL Approval UI Wiring | v1.0 | 3/3 | Complete | 2026-05-04 |
| 7. Feedback Contract Alignment | v1.0 | 3/3 | Complete | 2026-05-04 |
| 8. Search Context + Sidebar Polish | v1.0 | 2/2 | Complete | 2026-05-05 |
| 9. HQ/Branch Origin Model | v1.1 | 4/4 | Complete | 2026-05-10 |
| 10. Unify Refusal Copy on Planner Bypass Paths | v1.1 | 3/3 | Complete | 2026-05-11 |
| 11. Live SSE Hang Root-Cause Fix | v1.1 | 5/5 | Complete | 2026-05-11 |

## Backlog

Out-of-band items surfaced during execution. Resolved during v1.0:

- **999.1** — Planner state merge on follow-up turns (resolved 2026-04-25)
- **999.2** — Scope-naming mismatch "Central Region" → "Bangkok Metro" (resolved 2026-04-25)
- **999.3** — Planner trace tool_output narration mismatch (resolved 2026-04-25)
- **999.4** — D-04 loop budget windowed per turn (resolved 2026-04-25)

Resolved during v1.1 (retroactively validated):

- **999.5** — Resume flow appending duplicate assistant message (resolved 2026-05-09) — see [debug/resolved/999.5-fix-resume-flow-appending-duplicate-assistant-message.md](debug/resolved/999.5-fix-resume-flow-appending-duplicate-assistant-message.md)
- **999.6** — EPPO fuel-price scraper after URL restructure (resolved 2026-05-09) — see [debug/resolved/fix-eppo-scraper-url-restructure.md](debug/resolved/fix-eppo-scraper-url-restructure.md)
- **999.7** — Backfill daily fuel-price history via Bangchak (resolved 2026-05-09) — see [debug/resolved/backfill-daily-fuel-price-history-90d-window.md](debug/resolved/backfill-daily-fuel-price-history-90d-window.md)

Promoted into v1.1 milestone (formerly 999.x backlog; on-disk directory names retained):

- **999.9** → Phase 9 (HQ/Branch Origin Model) — promoted 2026-05-10
- **999.10** → Phase 10 (Unify Refusal Copy on Planner Bypass Paths) — promoted 2026-05-10
- **999.11** → Phase 11 (Live SSE Hang Root-Cause Fix) — promoted 2026-05-10

### Open backlog (deferred from v1.1)

#### Phase 999.8: Scale agent coverage beyond Bangkok Central (BACKLOG)

**Goal:** Expand from Bangkok Central to Northeast/North/South regions. Requires regional EPPO fuel baselines (EPPO publishes by region), expanded rate table (zones × ship types × weight tiers grows ~Nx), regional traffic pattern calibration.
**Status:** Explicitly deferred from v1.1 by user during milestone definition; remains in 999.x backlog. Captured 2026-05-09 during scoping discussion. Too risky for current milestone given W5 code freeze. Revisit post-v1.1 demo.
**Requirements:** TBD
**Plans:** 0 plans (promote with `/gsd:review-backlog` when ready)

### v2 candidate requirements (captured but not in roadmap)

See [milestones/v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md) §"v2 Requirements" for the full list (NETW-01/02, PRICE-03/04, GUARD-08/09, OBS-04, API-06). Promote with `/gsd:new-milestone` when ready.

Full v1.0 details in [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md). Full v1.1 details in [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md).
