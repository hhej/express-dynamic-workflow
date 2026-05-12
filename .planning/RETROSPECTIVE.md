# Retrospective: Express Dynamic Surcharge Orchestrator

Living retrospective updated at every milestone completion.

---

## Milestone: v1.0 — MVP

**Shipped:** 2026-05-05
**Phases:** 8 | **Plans:** 36 | **Tasks:** 87

### What Was Built

A multi-agent LangGraph orchestrator that reasons over EPPO diesel prices, Google Maps route data, and a SQLite rate table to produce explainable surcharge recommendations for Bangkok Metro logistics. Planner routes to Fuel + Route specialists in parallel, then Pricing computes the surcharge, an HITL gate pauses high-value totals for human approval, and a Response node renders a markdown breakdown table. Tavily provides news-context for fuel-trend questions. Next.js 15 + React 19 frontend with live SSE streaming, reasoning trace panel, Recharts dashboard, and conversation sidebar. Full Langfuse observability (per-turn callback handler + formula_accuracy auto-eval + user_feedback Score wire).

### What Worked

- **Phase-bounded execute → verify → audit loop** caught cross-phase contract drift early. The 2026-05-03 audit surfaced 6 integration issues (3 critical) that no individual phase verification could detect. Three gap-closure phases (6/7/8) closed all of them with drift-prevention tests.
- **Type-system as drift chokepoint.** Phase 7 made `FinalPayload.message_id` REQUIRED in the TypeScript boundary; Phase 8 added `Record<AgentName, string>` exhaustiveness for `AGENT_LABEL`. Each turned a runtime contract into a compile-time error.
- **D-11 deterministic narration fallback** on every Gemini path meant LLM JSON parse failures never broke a turn — 184/184 backend tests stayed green even when the planner LLM returned malformed output.
- **Single-source-of-truth `_drain_events` helper** for SSE framing avoided contract drift between fresh and resume paths. When Phase 7 added the `message_id` stamp, it landed in exactly one place.
- **Wholesale README rewrite** (vs incremental) for DOC-01 was faster and cleaner than trying to edit a Phase 4-era document into Phase 5 shape.

### What Was Inefficient

- **Phase 5 over-scoped.** Original 7 plans became 10 (closure plans 05-08/09/10 added during execution for UAT-discovered gaps). Should have audited mid-phase rather than at the end. Roadmap label "Wave 6 PARTIAL" lingered in `ROADMAP.md` for days after the work shipped.
- **Audit Issues 1–6 were all Phase-4-meets-Phase-5 contract drift.** Phase 4 verification passed in isolation; Phase 5 verification passed in isolation; the integration only broke at the seam. A milestone-mid integration check would have caught these earlier than the final audit.
- **Process deviations from sandbox limits.** Plans 05-04, 05-06, 05-07, and 06-01 hit executor-agent sandbox blocks on `git` mutations or test runs; orchestrator absorbed the work. Each cost real wall-clock minutes. A pre-flight sandbox capability check would have caught these upfront.
- **`SUMMARY.md` `requirements_completed` frontmatter convention not adopted.** All 36 SUMMARY.md files lack the field, so the audit's 3-source cross-reference fell back to VERIFICATION.md only. Not catastrophic but reduces audit precision.

### Patterns Established

- **Drift-prevention test layer per closure phase.** Each gap-closure phase ships a test whose entire job is to catch the same bug class regressing — D-15.1 exhaustive AgentName loop, D-15.3 ChatApp.integration MSW, Phase 7 round-trip Vitest+MSW, Phase 8 D-14 sidebar-refresh.
- **Backlog 999.X numbering for live-smoke discoveries.** Smoke testing on 2026-04-25 surfaced 4 separate planner/state-merge bugs (999.1–999.4). Numbered backlog kept them traceable across the quick-fix flow without churning the main roadmap.
- **Decimal phase numbering for gap closure.** Phases 6/7/8 closed v1.0 audit gaps without renumbering original 5 phases. ROADMAP.md kept "Phase 5: Polish" as the original scope marker.
- **Live verification gate for OBS / DOC requirements.** Phase 7 OBS-02 stayed `partial` until `langfuse-feedback-score.png` actually landed. Submission-deliverable artifacts gated on visual evidence, not just code.

### Key Lessons

1. **Run an integration audit between phases, not just at milestone end.** A mid-milestone run of `gsd-integration-checker` after Phase 5 would have caught audit Issues 1–6 weeks earlier.
2. **Type-system contracts are cheaper than runtime validators.** `Record<AgentName, string>` and `FinalPayload.message_id: string` (required, no `?`) cost zero runtime overhead and surface drift at compile time.
3. **Wholesale rewrites of docs/READMEs beat incremental edits when scope shifts.** Less risk of stale prose surviving the rewrite.
4. **Single source of truth for SSE-stamped fields.** Stamping `message_id` in `_drain_events` (one place) eliminated an entire class of drift that the prior `a-${Date.now()}` FE construction created.
5. **Sandbox-limited sub-agents need work handoff conventions, not retries.** The orchestrator absorbing committed-work + writing SUMMARY inline became the established pattern for Plans 05-04 through 06-01.

### Cost Observations

- Model mix: ~80% Sonnet (research, planning, execution); ~15% Opus (audit, gap-closure planning); ~5% Haiku (status checks, lightweight extracts)
- Sessions: dozens of GSD slash-command invocations across 32 days
- Notable: per-phase verifier + integration-checker subagents kept main-conversation context bounded — the v1.0 milestone audit was authored in a single Opus turn after delegated research, not a multi-turn back-and-forth

---

## Milestone: v1.1 — Real-World Routing & Demo Hardening

**Shipped:** 2026-05-12
**Phases:** 3 (9, 10, 11) | **Plans:** 12 | **Tasks:** ~26
**Timeline:** 4 days active execution (2026-05-09 → 2026-05-12); 102 commits; +7241/-348 LOC across 69 source files

### What Was Built

Moved from synthetic origin-destination pairs to a real 10-hub Express network (1 HQ + 9 branches) with HubPicker dropdown UI, sessionStorage persistence, 135-row origin × destination rate matrix, and 4-arg `lookup_rate(shipping_type, origin_zone, dest_zone, weight_kg)`. Unified refusal copy across `guard_input` and the planner's two bypass paths (`out_of_scope` LLM emission + `parse_failed` retry exhaustion) — both now route to `response_node`'s refusal branch with locked `REFUSAL_COPY` + `status='refused'`. Root-cause-fixed the live `POST /api/chat` hang on the legit baseline diesel-price query: a pre-LLM destination-less short-circuit in `planner_node` prevents the cache-aware override at `planner.py:509` from promoting destination-less follow-ups to `fetch_route` after fuel is cached (5/5 fresh-uvicorn runs PASS_UNDER_30S at ~7.6–7.9 s; W6 demo gate cleared). Twelve retroactive validations covered work shipped via quick tasks + debugs before formal milestone declaration: dark cosmic glass UI theme (THEME-01), cold-start fuel-price refresh on FastAPI lifespan (DATA-06), pricing-agent reasoning bullets + 7-day volatility flag (PRICE-01/02), two-layer adversarial guardrails (GUARD-01..06), EPPO scraper rewrite (DATA-07), 90-day Bangchak backfill (DATA-08), resume-flow duplicate-message fix (FIX-01).

### What Worked

- **Three-hypothesis sequential investigation for the SSE hang.** Phase 11 ruled out hypotheses (c) cold-start and (a) SSE termination with reproducible evidence (`999.11-02-EVIDENCE.md` / `999.11-04-EVIDENCE.md`) before committing to a fix on (b) planner re-loop. Prevented diagnosis-by-mitigation; the fix landed surgical and correct (1-commit, 1-file, 1 regression test).
- **Fresh-uvicorn + httpx probe harness as repeatable artifact.** Plan 999.11-01 delivered a 5-run orchestrator with dual wall-clock + elapsed-ms timestamping that deterministically reproduced the hang. The same harness then validated the fix at the D-09 demo gate.
- **Additive type-system extensions as v1.0 contract preservation.** Phase 9 extended `AgentState`, `RouteData`, `ChatRequest`, and `lookup_rate` signature additively (Python `Optional[]` defaults + new 4-arg variant alongside existing call sites). v1.0 central-1 rates remained byte-for-byte identical; zero v1.0 tests regressed.
- **Quick tasks + debug workflows as legitimate milestone work.** 12 of 22 v1.1 requirements were shipped via `/gsd:quick` and `/gsd:debug` outside the formal phase loop, then retroactively validated against REQUIREMENTS.md during milestone declaration. Reduced ceremony for small-scope work without losing traceability.
- **Audit re-run as gate-keeper after blocker closure.** Initial 2026-05-12 audit returned `gaps_found` (Phase 9 missing VERIFICATION.md, HUB-04/07/08 unsatisfied per 3-source matrix, Phase 10 missing VALIDATION.md, FIX-02 trace observability gap, ROADMAP drift). All 5 blockers closed via targeted retroactive runs + 2 quick tasks; re-audit confirmed `passed` before milestone closure.

### What Was Inefficient

- **SUMMARY.md `requirements-completed` frontmatter convention drifted on Plans 02 + 03 of Phase 9.** Both plans used design-decision markers (`PHASE-999.9-D-04/05/08/09/10`, `PHASE-999.9-UI-SPEC`) instead of HUB-XX REQ-IDs from REQUIREMENTS.md. The 3-source audit matrix flagged HUB-04, HUB-07, HUB-08 as `unsatisfied` per SUMMARY frontmatter even though the codebase satisfied them — required a retroactive VERIFICATION.md run to close. Tech debt logged for housekeeping.
- **VALIDATION.md authored retroactively on Phase 10.** Should have landed before execution per Nyquist protocol. Cost an extra reconstruction step on 2026-05-12 to close the audit gap.
- **Two stale `wave_0_complete: false` frontmatter flags** (Phase 9 + Phase 11 VALIDATION.md) never flipped to `true` after Wave 0 artifacts landed. Non-functional but accumulates noise.
- **FIX-02 trace observability gap surfaced only at audit time.** The destination-less short-circuit didn't surface `origin_hub_id` in the trace `tool_input` — required a follow-up quick task (`260512-t7q`) to add the field + a pinning test. Pre-fix design conversation could have caught this.
- **ROADMAP.md Phase 10 checkbox + progress row drifted to incomplete state for one day** between Phase 10 ship and the audit catching it (`a6c7c30` / `f1a1b24` closed via `260512-t3t`).

### Patterns Established

- **EVIDENCE.md companion artifact for hypothesis-driven debug phases.** Phase 11 introduced per-plan `*-EVIDENCE.md` files alongside SUMMARYs to capture probe data + verdict. Cleaner separation than mixing investigation logs into SUMMARY prose.
- **Retroactive validation block in PROJECT.md `### Validated`.** v1.1 items shipped pre-milestone-declaration got an explicit "Validated in v1.1: Quick task XXX" suffix preserving traceability without forcing them through full phase ceremony.
- **Audit re-audit pattern.** Re-running the audit after blocker closure with explicit `is_re_audit: true` + `blockers_closed: [...]` frontmatter creates a clean before/after gate record.
- **D-09 "live verification bar" as demo gate.** Phase 11 used 5 fresh-uvicorn runs of the canonical legit baseline as a quantitative pass/fail check — `PASS_UNDER_30S` framing locked the success criterion to a number, not a vibe.

### Key Lessons

1. **Convention-on-frontmatter pays off only if convention holds.** Plans 02 + 03 of Phase 9 broke the `requirements-completed: [HUB-XX, ...]` convention and the audit's 3-source matrix immediately false-flagged HUB-04/07/08. Either enforce in CI or accept it as informational tech debt — silent drift between the two costs audit time.
2. **Hypothesis-ranked debug with EVIDENCE files beats poke-fix-rerun.** Phase 11 spent ~92 minutes total on Plans 01-04 (8 + 44 + 25 + 15 min) to land a 1-commit surgical fix. The probe harness from Plan 01 amortized across all hypotheses + the post-fix D-09 verification.
3. **Retroactive milestone-mapping of quick-task work is fast if traceability lives in REQUIREMENTS.md.** v1.1 declared a milestone over 7 already-shipped quick/debug tasks + 3 active phases by mapping each task to a REQ-ID with "Validated in v1.1: ..." suffix. Zero rework, full audit chain.
4. **Audit returning `gaps_found` is the audit working correctly.** v1.1 initial audit returned gaps; re-audit after closure returned `passed`. The audit is a gate, not a tax — a clean first-pass would have meant the audit wasn't checking hard enough.
5. **`Optional[]` + null defaults preserves v1.0 contracts when extending state.** Phase 9 added `origin_hub_id` to `AgentState`/`RouteData`/`ChatRequest` as `Optional` with API boundary defaulting to HQ Lat Krabang. No v1.0 test required updating; the D-09 narration bullet only fired on direct unit calls.

### Cost Observations

- Model mix: ~70% Sonnet (research, planning, execution); ~25% Opus (audit, hypothesis evaluation, milestone closure orchestration); ~5% Haiku (status/stats extracts)
- Sessions: ~30 GSD slash-command invocations across 4 days (smaller than v1.0's 32-day burndown — milestone scope was tighter and more of it was retroactive validation)
- Notable: Phase 11's hypothesis-driven debug consumed proportionally more Opus tokens than equivalent v1.0 phases (audit-then-fix loop). The per-EVIDENCE.md investment paid back on the surgical fix landing first try.

---

## Cross-Milestone Trends

| Milestone | Phases | Plans | Tasks | Days | Critical Gaps Found at Audit | Drift-Prevention Tests Added |
|---|---|---|---|---|---|---|
| v1.0 MVP | 8 (5 + 3 closure) | 36 | 87 | 32 | 3 critical, 3 minor | 4 (D-15.1, D-15.3, message_id round-trip, D-14 sidebar) |
| v1.1 Real-World Routing & Demo Hardening | 3 (9, 10, 11) | 12 | ~26 | 4 (+ 12 retroactive items shipped pre-declaration) | 0 critical after re-audit; 5 initial blockers closed pre-archive | 3 (D-10 short-circuit pin, defense-in-depth `test_legit_baseline_diesel_price_query_completes`, 4-case adversarial-pack regression) |

(Future milestones append rows here.)

### Trend observations across v1.0 → v1.1

- **Cycle time dropped sharply** (32 days → 4 days). v1.1 scope was tighter AND ~55% of v1.1 work shipped via quick/debug retroactively-validated paths instead of phase loop. Phase loop reserved for genuinely complex/cross-cutting work (Phase 9 HQ/branch model, Phase 11 hypothesis-driven debug).
- **Audit became a gate, not a closer.** v1.0 audit ran once after Phase 5 found 6 gaps that became Phases 6/7/8. v1.1 ran an initial audit that returned `gaps_found`, blockers were closed inline (no new phases), and a re-audit returned `passed`. The audit itself became iterable.
- **EVIDENCE.md pattern emerged for debug phases.** v1.0 had no equivalent — debug investigation lived in SUMMARYs. Worth promoting as a standard artifact for any future debug-shaped phase.
- **Drift-prevention test count per milestone trending down** (4 → 3). Not because v1.1 had less risk — v1.1's tests pin more invariants per file (regression test for FIX-02 + defense-in-depth legit-baseline integration + 4-case adversarial-pack regression).
