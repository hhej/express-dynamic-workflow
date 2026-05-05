# Phase 7: Feedback Contract Alignment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 07-feedback-contract-alignment
**Areas discussed:** turn_idx delivery to FE, Resume path id reconstruction, Drift-prevention test surface, Live verification protocol

---

## turn_idx delivery to FE

### Q1 — Where should the backend deliver turn_idx so the frontend can construct {thread_id}-{turn_idx}?

| Option | Description | Selected |
|--------|-------------|----------|
| On the answer SSE event | (Recommended) Backend adds `message_id`/`turn_idx` to the answer event payload. FE receives canonical id pre-built; aligns with the moment the assistant message becomes "real". | ✓ |
| On the meta SSE event | Backend extends meta payload from `{thread_id}` to `{thread_id, turn_idx}`. FE caches turn_idx until done. | |
| On both meta + answer | Belt-and-braces: turn_idx on meta AND message_id on answer. Two contracts to keep in lockstep. | |
| FE counts user messages locally | No backend change. ChatApp tracks turn_idx by counting role==user messages locally. Drift class the audit flagged. | |

**User's choice:** On the answer SSE event
**Notes:** Aligns with the moment the assistant message becomes real; FE doesn't need to hold turn_idx in component state.

### Q2 — Full message_id pre-built or just turn_idx?

| Option | Description | Selected |
|--------|-------------|----------|
| Full message_id pre-built | (Recommended) Backend single source of truth; if format changes, only one place updates. | ✓ |
| Just turn_idx, FE concatenates | Smaller payload but format string duplicated → drift risk. | |
| Both fields in payload | Redundant; no concrete consumer for turn_idx alone. | |

**User's choice:** Full message_id pre-built
**Notes:** Single source of truth; matches audit lesson on avoiding two-end string construction.

### Q3 — Top-level on answer envelope or inside FinalPayload?

| Option | Description | Selected |
|--------|-------------|----------|
| Inside FinalPayload | (Recommended) Travels with assistant message; matches existing destructuring; FinalPayload type already widened to nullable. | ✓ |
| Top-level on answer envelope | Forces new envelope shape; harder to thread through MarkdownAnswer/PartialCard. | |

**User's choice:** Inside FinalPayload
**Notes:** Aligns with how FE already consumes the answer event.

### Q4 — Required or optional with FE fallback?

| Option | Description | Selected |
|--------|-------------|----------|
| Required (always present) | (Recommended) Contract unambiguous; aligns with CLAUDE.md "no half-finished implementations"; tests must include message_id (drift-prevention requires it anyway). | ✓ |
| Optional with FE fallback | Tolerant to old payloads but silent degradation IS the audit's bug class. | |

**User's choice:** Required (always present)
**Notes:** Optional + silent degradation is the bug class the audit flagged.

---

## Resume path id reconstruction

### Q1 — How should each replayed assistant message get its {thread_id}-{turn_idx} id?

| Option | Description | Selected |
|--------|-------------|----------|
| BE returns id per message | (Recommended) Same source-of-truth principle as answer event; FE just stores; replayed feedback works identically to live feedback. | ✓ |
| FE infers turn_idx by counting | Zero backend change but BE's `_next_turn_idx` is source of truth → drift class. | |
| Disable feedback on replayed messages | Zero contract risk but degrades UI-05 for past conversations. | |
| Best-effort heuristic now, fix later | Re-introduces drift class; would need a Phase 9 to fix. | |

**User's choice:** BE returns id per message
**Notes:** Replayed feedback works identically to live feedback.

### Q2 — Where on each assistant message should `message_id` live?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-message field on each msg | (Recommended) Travels with the message; FE map function reads m.message_id directly; user messages get no id. | ✓ |
| Top-level message_ids[] aligned by index | Index-aligned arrays fragile to filtering; awkward to consume. | |
| Top-level next_turn_idx hint | Forces FE to mirror BE's _next_turn_idx semantics; defeats the purpose. | |

**User's choice:** Per-message field on each msg
**Notes:** Cleanest consumption path; absence is the natural signal for "no feedback".

### Q3 — How should backend compute turn_idx per message?

| Option | Description | Selected |
|--------|-------------|----------|
| 1 turn = 1 user message | (Recommended) Walk messages list; turn_idx = count of role==user at positions [0..N]. Matches `_next_turn_idx` exactly. HITL pause+resume shares one turn_idx (correct). LAST assistant gets the message_id. | ✓ |
| 1 turn = 1 assistant message | Each assistant gets its own incrementing turn_idx — diverges from BE's `_next_turn_idx`. | |
| Backend returns whatever it logged at creation time | Requires AgentState schema change + backfill — large blast radius for a gap-closure. | |

**User's choice:** 1 turn = 1 user message
**Notes:** Mirrors `_next_turn_idx` semantics for consistent Langfuse trace alignment.

### Q4 — Should FeedbackButtons render on every assistant message or only the last per turn?

| Option | Description | Selected |
|--------|-------------|----------|
| Last assistant per turn only | (Recommended) Matches existing isLast-gating pattern; one feedback opportunity per query. | ✓ |
| Every assistant message | Confusing UX; duplicate Score writes if user clicks both. | |

**User's choice:** Last assistant per turn only
**Notes:** Reuses existing isLast pattern in MessageList.

---

## Drift-prevention test surface

### Q1 — Primary drift-prevention test surface?

| Option | Description | Selected |
|--------|-------------|----------|
| Vitest+MSW round-trip | (Recommended) Mocks /api/chat → click thumbs-up → assert /api/feedback fires with regex-parseable shape. Catches the exact wiring path that broke. | ✓ |
| BE production-shape ids only | Smallest diff but doesn't catch FE-side construction errors. | |
| Shared contract fixture | Cross-language fixture sharing adds infra; overkill for one regex. | |
| FE unit on id constructor | Cheapest but doesn't exercise the full wire; misses the wiring bug class. | |

**User's choice:** Vitest+MSW round-trip
**Notes:** Catches the exact wiring path the audit flagged.

### Q2 — Add a UUIDv4 BE happy-path test alongside?

| Option | Description | Selected |
|--------|-------------|----------|
| Add UUIDv4 BE test | (Recommended) Belt-and-braces; one fixture row catches future BE-side regex tightening. | ✓ |
| Skip BE add-on | Smaller diff but BE blind to production id shape. | |

**User's choice:** Add UUIDv4 BE test
**Notes:** Near-zero cost belt-and-braces.

### Q3 — Dedicated test for resume-path feedback?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, dedicated resume test | (Recommended) Mock /api/conversations/:id with message_ids → click thumbs-up on replayed msg → assert /api/feedback. Covers the second half of the contract. | ✓ |
| Just add an assertion to existing tests | Less explicit; future refactor could silently lose the assertion. | |
| Skip — already covered by BE returns-id test | Doesn't exercise the click-and-POST path on replayed messages — same bug class could recur. | |

**User's choice:** Yes, dedicated resume test
**Notes:** Without this, only the live path is verified.

### Q4 — Update existing thread-mismatch tests to add UUIDv4 variants?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave as-is | (Recommended) Mismatch behavior is regex-shape-agnostic; existing canonical-shape test is enough. YAGNI. | ✓ |
| Add UUIDv4 mismatch variant | Tests the same code path twice; doesn't catch a different bug class. | |

**User's choice:** Leave as-is
**Notes:** YAGNI; mismatch is regex-shape-agnostic.

---

## Live verification protocol

### Q1 — How should success criterion 4 be verified?

| Option | Description | Selected |
|--------|-------------|----------|
| Documented manual smoke | (Recommended) Steps in docs/data-sources.md; IT lead executes during W5 with screenshot artifact. Matches local-reproducibility constraint. | ✓ |
| Automated test gated on env keys | Slow, flaky against real cloud APIs; pollutes demo Langfuse account. | |
| Curl recipe in README | Bypasses FE entirely; doesn't test the click path the audit broke. | |
| Combine smoke + curl | Belts-and-braces but more docs to maintain. | |

**User's choice:** Documented manual smoke
**Notes:** Same path a real user would exercise.

### Q2 — Where should the verification doc live?

| Option | Description | Selected |
|--------|-------------|----------|
| Append to docs/data-sources.md | (Recommended) One less file to track; data-sources.md already documents Langfuse as external service. | ✓ |
| New docs/observability-verify.md | Yet another doc file; v1 scope doesn't need it. | |
| Inline in README | Bloats README; verification protocol isn't core to project use. | |

**User's choice:** Append to docs/data-sources.md
**Notes:** Co-locates with existing Langfuse documentation.

### Q3 — Capture a screenshot artifact?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add screenshot artifact | (Recommended) Visual proof for graders; matches Phase 5 demo-artifact discipline. 6th PNG in docs/screenshots/. | ✓ |
| Checklist only, no screenshot | Less work but graders can't verify the verification happened. | |

**User's choice:** Yes, add screenshot artifact
**Notes:** Matches Phase 5 D-20 / Plan 05-07 Task 4 pattern.

### Q4 — Live verification = HUMAN checkpoint or automated?

| Option | Description | Selected |
|--------|-------------|----------|
| Human checkpoint (autonomous: false) | (Recommended) Matches Phase 5 D-20 / Plan 05-07 Task 4 pattern; no flaky CI; same artifact-driven verification graders see in Phase 5. | ✓ |
| Try to automate | Requires Langfuse Score read API; flaky against rate limits. | |

**User's choice:** Human checkpoint (autonomous: false)
**Notes:** Same artifact-driven verification graders saw for Phase 5.

---

## Claude's Discretion

Areas the user explicitly delegated to Claude / planner judgment:
- Exact field ordering of `message_id` inside `FinalPayload`.
- Whether to extract a single FE id-builder utility vs inline string template.
- Whether to add `message_id` on user messages too (probably absent — only assistant rows need it).
- Whether to extend existing `langfuse-trace.png` placeholder OR add a new `langfuse-feedback-score.png`.
- Plan ordering and Wave assignment (single plan vs Wave-split).
- Exact Vitest+MSW handler shape (extend existing `ChatApp.integration.test.tsx` vs sibling file).
- Whether the BE answer-event augmentation happens at `_drain_events` yield site vs per-route call site.
- Whether the planner explicitly confirms the HITL placeholder `pending-${Date.now()}` strip-and-replace path and moves on, or migrates to `pending-${threadId}-${turnIdx}`.
- Whether to update the Phase 5 D-20 screenshot list documentation to reflect 6 instead of 5.

## Deferred Ideas

Captured during discussion as out-of-scope for Phase 7:
- Toast/snackbar global error UI on feedback POST failure (Phase 5 D-16 silent-failure pattern stays).
- Backfill story for old localStorage feedback entries.
- Read-side Langfuse Score API verification (free-tier quota concerns).
- Migration of pending-${Date.now()} placeholder id (strip-and-replace already prevents persistence).
- AgentState schema change to persist message_id per message (avoided in favor of read-time inference).
- User-message message_ids (no feature needs them).
- Tightening backend regex to enforce UUIDv4 thread_id (zero security/correctness value).
- FinalPayload optional fallback for message_id (silent degradation IS the audit's bug class).
- Top-level message_id on the SSE answer event envelope (FinalPayload is the natural home).
- Backend hint `next_turn_idx` for resume (forces FE to mirror BE semantics).
- FE-counted turn_idx (silent drift on resume path).
- Combine documented smoke + curl recipe (one form sufficient for v1).
- Phase 8 scope (search_context wiring + sidebar refresh).
