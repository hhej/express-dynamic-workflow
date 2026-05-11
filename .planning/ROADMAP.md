# Roadmap: Express Dynamic Surcharge Orchestrator

## Milestones

- ✅ **v1.0 MVP** — Phases 1–8 (shipped 2026-05-05) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- 🔄 **v1.1 Real-World Routing & Demo Hardening** — Phases 9–11 (started 2026-05-10)

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

## Milestone v1.1 — Real-World Routing & Demo Hardening

**Started:** 2026-05-10
**Goal:** Move from synthetic origin-destination pairs to a real Express hub network, tighten the agent against adversarial-bypass refusal-copy drift, and root-cause-fix the live SSE hang on the legit baseline diesel-price query — making the v1.0 demo bulletproof for W6 grading.

**Phase numbering:** Continues v1.0 sequence at integer 9. Existing on-disk backlog directory names are LOAD-BEARING (`999.9-...`, `999.10-...`, `999.11-...`) — they are already on the `feature/hq-branch-model` branch with commits. The roadmap maps:

- Phase 9 ↔ `.planning/phases/999.9-hq-branch-origin-model-real-world-hub-to-destination-shipping/`
- Phase 10 ↔ `.planning/phases/999.10-guard-input-bypass-paths-return-inconsistent-refusal-copy/`
- Phase 11 ↔ `.planning/phases/999.11-investigate-live-sse-hang-on-legit-baseline-diesel-price-query/`

### v1.1 Phases (active)

- [x] **Phase 9: HQ/Branch Origin Model** (4/4 plans) — completed 2026-05-10 — Replace implicit-origin model with hub-based origin selection (HQ + 9 branches), 135-row origin×destination rate matrix, HubPicker UI
- [ ] **Phase 10: Unify Refusal Copy on Planner Bypass Paths** — `out_of_scope` LLM emission and `parse_failed` exhaustion both render the locked `REFUSAL_COPY` + `status='refused'` (not the generic clarify copy)
- [ ] **Phase 11: Live SSE Hang Root-Cause Fix** — Diagnose AND fix the live `POST /api/chat` hang on the legit baseline diesel-price query; demo-gating for W6

**Already shipped this milestone (retroactively validated):**

- Quick task `260509-e0p` — Dark cosmic glass-morphism UI theme (THEME-01)
- Quick task `260509-eum` — Cold-start fuel-price refresh on FastAPI lifespan (DATA-06)
- Quick task `260509-uwb` — Pricing Agent visible reasoning bullets + 7-day volatility flag (PRICE-01, PRICE-02)
- Quick task `260509-utd` — Two-layer adversarial guardrails (GUARD-01..06)
- Debug `999.5` — Resume flow no longer appends duplicate assistant message (FIX-01)
- Debug `999.6` — EPPO fuel-price scraper rewrite after URL+Excel restructure (DATA-07)
- Debug `999.7` — 90-day Bangchak historical fuel-price backfill (DATA-08)

12 of 22 v1.1 requirements were retroactively validated by the work above. The 3 active phases below cover the remaining 10 requirements.

## Phase Details

### Phase 9: HQ/Branch Origin Model
**Goal**: Replace the implicit-origin model (free-text origin + destination-only zone pricing) with explicit hub-based origin selection. Sender picks HQ or one of 9 branches via dropdown OR prose, and the agent calculates route + surcharge from the actual chosen hub to the destination — matching how Kerry/Flash/Thailand Post quote shipments. Bangkok Metro scope only.
**Depends on**: Phase 8 (v1.0 closure) — preserves all v1.0 contracts; AgentState extension is additive
**Requirements**: HUB-01, HUB-02, HUB-03, HUB-04, HUB-05, HUB-06, HUB-07, HUB-08
**Phase directory**: `.planning/phases/999.9-hq-branch-origin-model-real-world-hub-to-destination-shipping/`
**Status**: Ready (CONTEXT + RESEARCH + UI-SPEC + VALIDATION + 4 PLAN docs already drafted; awaiting `/gsd:execute-phase`)
**Success Criteria** (what must be TRUE):
  1. `data/express.db` ships with 10 seeded hubs (1 HQ + 9 branches) and a 135-row origin×destination rate table; `python data/scripts/seed_database.py` produces both idempotently (HUB-01, HUB-06)
  2. `lookup_rate(shipping_type, origin_zone, dest_zone, weight_kg)` returns higher rates for cross-zone shipments than for intra-zone shipments at the same weight tier; multiplier matrix is symmetric (`M[a][b] == M[b][a]`) (HUB-05, HUB-06)
  3. User picks an origin via the HubPicker dropdown adjacent to the chat input; cold-start default selection is HQ Lat Krabang; choice persists across page reloads via sessionStorage (single-tab scope) (HUB-02)
  4. Prose override wins for a single turn — sending "ship 5kg bounce from Bang Na to Nonthaburi" with dropdown=HQ produces a planner trace whose `origin_hub_id="branch-bang-na"` and a surcharge total reflecting central-1 → central-1 pricing; dropdown selection is not mutated (HUB-03, HUB-07)
  5. When neither dropdown nor prose specifies a hub, the agent silently defaults to HQ Lat Krabang and the Pricing Agent emits a reasoning bullet "Origin unspecified — defaulted to HQ Lat Krabang" (HUB-04)
  6. Follow-up turn in the same thread inherits `origin_hub_id` from prior turn unless the user explicitly changes it via dropdown or prose; route TTL cache key includes `origin_hub_id` so cross-hub queries do not collide (HUB-08)
  7. Manual live-demo verification (Plan 04 Task 3, 5 flows): cold-start default + dropdown render, dropdown override → cross-zone surcharge, prose override beats dropdown, default-to-HQ silent at API boundary, sessionStorage persists across reload + isolated cross-tab
**Plans**: 4 plans (already drafted)
**UI hint**: yes

Plans:
- [x] 999.9-01-PLAN.md — Hub data + 135-row rate matrix (data + seeding) [Wave 1]
- [x] 999.9-02-PLAN.md — Backend agent integration: state + tools + planner + chat handler [Wave 2]
- [x] 999.9-03-PLAN.md — Frontend HubPicker UI + sessionStorage + ChatRequest forwarding [Wave 3]
- [x] 999.9-04-PLAN.md — Documentation + end-to-end human-verify checkpoint [Wave 4]

### Phase 10: Unify Refusal Copy on Planner Bypass Paths
**Goal**: When the planner emits `user_intent='out_of_scope'` OR the `parse_failed` retry loop exhausts, render the same locked `REFUSAL_COPY` + `status='refused'` as `guard_input` refusals — instead of the generic `planner_parse_failed` clarify copy with `status='clarify'`. Closes the visible refusal-copy split observed against the adversarial pack (cases 2 "weather/Bangkok" and 4 "loop forever" returned clarify; cases 1 "injection" and 3 "recipe" returned the branded refusal).
**Depends on**: Phase 9 (executes after Phase 9 completes; touches planner.py + guard_input.py — disjoint from HUB scope)
**Requirements**: GUARD-07
**Phase directory**: `.planning/phases/999.10-guard-input-bypass-paths-return-inconsistent-refusal-copy/`
**Status**: Planned (3 PLAN docs drafted 2026-05-11; awaiting `/gsd:execute-phase 10`)
**Success Criteria** (what must be TRUE):
  1. When `planner_node` parses a Gemini emission with `user_intent='out_of_scope'`, it sets `state.guard_decision = {layer: 'input', refused: True, category: 'planner_off_topic', violations: []}` and returns `next_step='respond'`; `response_node`'s existing refusal branch then renders `REFUSAL_COPY` verbatim with `status='refused'` (D-04, D-08, D-09)
  2. When the D-02 retry loop exhausts (`planner parse attempt 2 failed`), planner_node sets `state.guard_decision` (category `'planner_parse_failed'`) and routes to `response_node` refusal branch — no longer returns the generic clarify copy (D-05, D-09)
  3. `GuardCategory` Literal in `backend/agent/nodes/guard_input.py` is extended additively with `'planner_off_topic' | 'planner_parse_failed'`; `state.guard_decision.layer` stays `'input'` so `response_node`'s `status = 'refused' if layer == 'input' else 'guard_failed'` predicate continues to work (D-09, D-10)
  4. Re-run of `backend/tests/adversarial_pack.txt` produces identical `status='refused'` + `REFUSAL_COPY` output for cases 2 and 4 (previously `status='clarify'`); cases 1 and 3 remain `status='refused'` unchanged (D-13)
  5. New focused pytest in `test_planner.py` (or `test_planner_refusal_paths.py`) covers both new categories with deterministic mocked-LLM fixtures; total backend test count increases by ≥2 with zero regressions
**Plans**: 3 plans (drafted 2026-05-11)

Plans:
- [x] 999.10-01-extend-guardcategory-literal-PLAN.md — Additive `GuardCategory` Literal extension (`planner_off_topic`, `planner_parse_failed`) [Wave 1]
- [x] 999.10-02-planner-refusal-paths-PLAN.md — `planner_node` D-04 (out_of_scope) + D-05 (parse_failed) refusal branches + 4 new unit tests [Wave 2]
- [ ] 999.10-03-adversarial-pack-regression-PLAN.md — CI regression test pinning all 4 representative adversarial-pack cases to `status='refused'` + REFUSAL_COPY [Wave 3]

### Phase 11: Live SSE Hang Root-Cause Fix
**Goal**: Diagnose AND fix the live `POST /api/chat` hang observed on the legit baseline query "What's the current diesel price in Bangkok?" during the 260509-utd live probe. Symptom: trace stream emits `planner -> fuel_agent -> planner` (3 steps) then no `answer` SSE event arrives before the urlopen 60s timeout closes the client; response body is 0 bytes. **Demo-gating for W6** — 4/5 cases in the live probe completed cleanly; only the legit baseline hung. Three candidate root causes tested sequentially per D-05: (c) cold-start latency → (b) `tool_call_count` reducer interaction with parallel fan-out → (a) SSE termination bug.
**Depends on**: Phase 10 (executes after Phase 10; investigation can begin in parallel with Phase 10 PLAN drafting if scheduling demands, but commits land sequentially)
**Requirements**: FIX-02
**Phase directory**: `.planning/phases/999.11-investigate-live-sse-hang-on-legit-baseline-diesel-price-query/`
**Status**: Context-ready (CONTEXT.md drafted with D-01..D-11; sequential investigation order c→b→a locked; awaiting `/gsd:plan-phase` to produce PLAN docs)
**Demo gate**: This phase blocks W6 demo confidence. Must complete before final demo recording.
**Success Criteria** (what must be TRUE):
  1. Repro harness (`.planning/phases/999.11/repro/`) deterministically reproduces the hang against a fresh-uvicorn run with 180s client timeout; per-run artifacts are exactly two: full SSE event stream with wall-clock+elapsed-ms timestamps, and full uvicorn stderr (D-03, D-04)
  2. Investigation rules out (c), then (b), then (a) sequentially per D-05; the confirmed root cause is documented in the phase SUMMARY.md with evidence — no diagnosis-by-mitigation; D-02 prefers root-cause fix over runbook workaround
  3. **Live verification bar:** 5 fresh-uvicorn runs of the legit baseline `"What's the current diesel price in Bangkok?"` each produce an `answer` SSE event within 30 seconds; uvicorn restarted between each run (D-09)
  4. ONE permanent regression pytest pinning the confirmed root cause: if (b) reducer → unit test asserting `tool_call_count` reducer behavior on parallel fan-out; if (a) SSE → integration test asserting `answer` event arrives on a normal happy path; if (c) cold-start → smoke test asserting lifespan warmup completes deterministically. CI-friendly, no live network, zero new flakes (D-10)
  5. Backend test suite remains ≥295/295 green (current baseline post-260509-utd) plus the new regression test; frontend tests unaffected
**Plans**: TBD — to be produced by `/gsd:plan-phase 11`

## Progress

**Execution Order:** v1.0 closed at Phase 8. v1.1 phases execute in numeric order: 9 → 10 → 11. Phase 11 is W6-demo-gating.

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
| 10. Unify Refusal Copy on Planner Bypass Paths | v1.1 | 0/3 | Planned (awaiting execute) | - |
| 11. Live SSE Hang Root-Cause Fix | v1.1 | 0/? | Context-ready (PLAN docs pending) — **DEMO GATE** | - |

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

Full v1.0 details in [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).
