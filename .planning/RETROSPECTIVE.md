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

## Cross-Milestone Trends

| Milestone | Phases | Plans | Tasks | Days | Critical Gaps Found at Audit | Drift-Prevention Tests Added |
|---|---|---|---|---|---|---|
| v1.0 MVP | 8 (5 + 3 closure) | 36 | 87 | 32 | 3 critical, 3 minor | 4 (D-15.1, D-15.3, message_id round-trip, D-14 sidebar) |

(Future milestones append rows here.)
