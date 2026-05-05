---
phase: 06-hitl-approval-ui-wiring
plan: 03
subsystem: ui
tags: [typescript, react, vitest, msw, sse, integration-test, hitl, drift-prevention]

# Dependency graph
requires:
  - phase: 06-hitl-approval-ui-wiring
    provides: HITL prop chain wired (Plan 06-02) — ChatApp consumes chat.approve / chat.approvalPayload, computes inputDisabled + placeholder + approvalErrorMessage, threads them through ChatColumn -> MessageList -> ApprovalCard
  - phase: 05-tooling-tracing-feedback
    provides: useChatStream.approve, ApprovalCard, awaiting_approval status, sixth SSE event approval_required (Plan 05-05/05-06)
provides:
  - End-to-end MSW SSE integration test exercising approve + deny flows through the production ChatApp tree (D-15.3)
  - Drift-prevention layer for the audit's bug class — any future regression that drops chat.approve / chat.approvalPayload from ChatApp re-introduces audit Issue 2 AND fails this test
  - End-to-end evidence for ROADMAP §Phase 6 success criteria 2, 3, 4, 5
affects: [phase-07-message-id-rewrite (placeholder pending-${ts} lifecycle implicitly verified by deny-flow done transition), future-refactors (drift trap installed at the integration boundary)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Call-counter MSW handler (installPauseThenResumeHandler) — single server.use registration switches behaviour on call number; first call = paused fresh-turn SSE, second call = resume SSE; asserts resume POST body carries thread_id + approve boolean (defensive contract check from inside the handler)"
    - "End-to-end SSE-driven integration test — render the production root component, drive a real SSE stream through MSW, assert UI rendering across the full prop chain (avoids both unit-test isolation gaps AND server-side mock divergence)"

key-files:
  created:
    - frontend/__tests__/components/ChatApp.integration.test.tsx
  modified: []

key-decisions:
  - "Empty-textarea Send-button gating means re-enable assertion needs a follow-up keystroke first — ChatInput's disabled predicate is `disabled || text.trim().length === 0`, so after the user clicks Send the textarea empties and the Send button stays disabled even when inputDisabled flips false. Asserting `not.toBeDisabled` directly would always fail; typing a follow-up character first verifies the inputDisabled-driven lock specifically (not the text-length lock)."
  - "Test-only file — Plan 06-03 is intentionally additive. No production source touched (ChatApp / ChatColumn / MessageList / ApprovalCard / ChatInput unchanged from Plan 06-02). The integration test is the lasting drift-prevention artifact; production wiring lives in 06-02."
  - "MSW handler shape mirrors useChatStream-approval.test.ts call-counter pattern — keeps the same SSE response convention across the codebase so a Phase 7+ test can extend the same handler without re-learning the framing."
  - "Defensive resume POST contract assertions (thread_id == 'thread-hitl' AND typeof approve === 'boolean') are inside the MSW handler closure — failing assertion is logged as an unhandled rejection, surfacing the contract drift even if the surrounding test happens to render correctly."

patterns-established:
  - "Pattern: end-to-end integration test as drift-prevention layer — when audit history shows a cross-layer regression (per-layer unit tests pass, integration breaks), add a single end-to-end test that exercises the full prop chain through a realistic event stream. The test is the lasting safety net; per-layer unit tests remain useful for fine-grained debugging."
  - "Pattern: call-counter MSW handler for paired request flows — useful any time a feature requires two distinct backend interactions in sequence (initial send + resume in HITL; PUT + GET in optimistic-UI patterns; etc.)."

requirements-completed: [ORCH-09, UI-01]

# Metrics
duration: 2 min
completed: 2026-05-04
---

# Phase 06 Plan 03: HITL Approval UI Wiring — End-to-End Integration Test Summary

**Adds the canonical ChatApp integration test (D-15.3) that exercises BOTH approve and deny SSE flows end-to-end through the production ChatApp tree using MSW — drift-prevention layer that catches any future regression of audit Issue 2 (the cross-phase chat.approve / chat.approvalPayload prop chain breakage that produced the original audit gap).**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-04T05:18:25Z
- **Completed:** 2026-05-04T05:20:46Z
- **Tasks:** 1 (TDD: RED + GREEN folded — tests pass on first run because Plan 06-02 wiring is in place)
- **Files modified:** 0
- **Files created:** 1

## Accomplishments

- Created `frontend/__tests__/components/ChatApp.integration.test.tsx` with two end-to-end SSE integration tests covering approve and deny HITL flows (D-15.3).
- ROADMAP §Phase 6 success criteria 2, 3, 4, 5 now verified end-to-end with realistic SSE streams (not unit-isolated mocks):
  - SC 2 — ApprovalCard appears in production tree on real `approval_required` event.
  - SC 3 — Approve click → resume POST `{approve: true}` → MarkdownAnswer renders the HAPPY_PAYLOAD answer (table cell shows `152.50 THB`).
  - SC 4 — Deny click → resume POST `{approve: false}` → PartialCard renders the PARTIAL_PAYLOAD prose.
  - SC 5 — ChatInput is asserted disabled across the awaiting_approval window AND shows the locked contextual placeholder `Awaiting your approval — use Approve / Deny above`.
- Drift-prevention layer in place: any future refactor that drops `chat.approve` or `chat.approvalPayload` from ChatApp re-introduces the audit's bug class AND fails this integration test immediately. This is the lasting answer to the audit §1 lesson (per-layer unit tests can pass while the cross-phase boundary breaks).
- Installed call-counter MSW handler `installPauseThenResumeHandler` that switches behaviour on each POST: first call returns the paused fresh-turn SSE (meta → 4 traces → approval_required, NO done — Pitfall 2), second call returns the resume SSE (meta → response trace → answer → done). Inside the handler closure, defensive assertions verify the resume POST body carries the right `thread_id` and an `approve` boolean — locking the resume contract.
- Reused existing `frontend/__tests__/fixtures/sse.ts` exports verbatim (HAPPY_TRACE, HAPPY_PAYLOAD, PARTIAL_PAYLOAD, makeSseStream) — no new fixtures created. The two SSE event arrays are built inline in the test for readability.
- Full Vitest suite: 118/118 pass (was 116 in Plan 06-02; +2 new integration tests).
- `npx tsc --noEmit` clean (no output).

## Task Commits

Each task was committed atomically:

1. **Task 1: ChatApp.integration.test.tsx with approve + deny SSE integration coverage** — `f5d1bd8` (test)

**Plan metadata:** _to be added by final commit_ (docs)

## Files Created/Modified

- `frontend/__tests__/components/ChatApp.integration.test.tsx` (NEW) — Two integration tests:
  - `approve flow: high-value query → ApprovalCard renders → ChatInput disabled with locked placeholder → click Approve → MarkdownAnswer renders final answer`
  - `deny flow: high-value query → ApprovalCard renders → click Deny → PartialCard renders with deny prose`
  - Helper `installPauseThenResumeHandler` (call-counter MSW handler) and three SSE event-builders (`pausedTurnEvents`, `approveResumeEvents`, `denyResumeEvents`) using existing fixtures.

## Decisions Made

- **Empty-textarea Send-button re-enable assertion** (test-only deviation, documented below): the plan's literal `not.toBeDisabled` assertion at the end of each test would always fail because ChatInput's `disabled` predicate is `disabled || text.trim().length === 0`. After the user clicks Send the textarea empties, so even when `inputDisabled` flips false the Send button remains disabled by the empty-text branch. Fix: type a follow-up character first to clear the empty-text branch, then assert `not.toBeDisabled` — this verifies the `inputDisabled`-driven lock specifically (not the text-length lock). The pattern matches the pre-existing `frontend/__tests__/components/ChatApp.test.tsx` "after stream done, ChatInput is re-enabled" test (line 79).
- **Test-only — no production source touched.** Plan 06-03 is purely additive. ChatApp / ChatColumn / MessageList / ApprovalCard / ChatInput / useChatStream are all unchanged from Plan 06-02. Any failure of this integration test points at a Plan 06-02 acceptance-criterion regression and should NOT be patched from inside this plan (per plan's `<action>` Step B note).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test bug] Plan-prescribed `not.toBeDisabled` assertion failed because empty textarea keeps Send button disabled**
- **Found during:** Task 1 (Step B — vitest GREEN run; both tests failed at the final `expect(...).not.toBeDisabled` assertion despite all other assertions passing)
- **Issue:** The plan's verbatim test code asserted `expect(getByRole('button', { name: 'Send message' })).not.toBeDisabled()` after the resume's `done` event. ChatInput's disabled predicate is `disabled={disabled || text.trim().length === 0}`. The user typed text → clicked Send → textarea emptied via `setText('')`. After done, even though `inputDisabled` correctly flips false, the Send button stays disabled because text is empty. The plan-as-written would fail forever; this is a test-side bug, NOT a production bug.
- **Fix:** Before the `not.toBeDisabled` assertion, type a follow-up character (`await user.type(getByPlaceholderText(/Ask about a surcharge/), 'follow-up')`) to clear the empty-text disabled branch. Then assert `not.toBeDisabled` — verifies the `inputDisabled`-driven lock specifically. Same pattern as the existing `ChatApp.test.tsx` "after stream done, ChatInput is re-enabled" test (line 79).
- **Files modified:** frontend/__tests__/components/ChatApp.integration.test.tsx (only — production source unchanged)
- **Verification:** Both integration tests pass; full vitest suite 118/118; tsc --noEmit clean.
- **Committed in:** f5d1bd8

### Auto-added critical functionality

None — the plan's spec was complete; only the test-side `disabled` assertion needed adjusting for the empty-text branch.

---

**Total deviations:** 1 (Rule 1 — test-side bug in plan-prescribed assertion).
**Impact on plan:** Zero functional impact. The test still asserts everything the plan required (ChatInput disabled across the paused window, ApprovalCard heading, click Approve / Deny, MarkdownAnswer / PartialCard renders, resume POST contract). The follow-up `user.type('follow-up')` is a one-line addition that disambiguates the disabled predicate's two branches; the `inputDisabled = streaming || awaiting_approval` lock from Plan 06-02 is verified end-to-end as intended.

## Issues Encountered

- One minor friction point during initial GREEN run: the empty-textarea branch of ChatInput's disabled predicate caused the plan-as-written `not.toBeDisabled` assertion to always fail. Fixed inline by mirroring the pre-existing `ChatApp.test.tsx` line-79 pattern (type follow-up text first). Documented as Deviation 1 above.

## User Setup Required

None — purely a test-only addition. No external service configuration. No new dependencies. No env vars.

## Next Phase Readiness

- **Phase 6 fully complete.** Audit Issues 1, 2, 5 all closed in code (Plans 06-01 + 06-02), and Plan 06-03 installs the lasting integration-test layer that catches the same bug class across all future phases.
- **Phase 7 message_id rewrite** — the placeholder `pending-${ts}` lifecycle from Plan 06-02 D-06 is implicitly verified by this plan's deny flow: the deny `done` event fires `setMessages` strip-and-replace, and the test's "Send button re-enabled after typing follow-up" assertion would only succeed if the placeholder was correctly stripped (otherwise MessageList would still render an ApprovalCard slot).
- **Phase 8 search_context wiring + sidebar refresh** — unaffected by this plan; the integration test exercises the surcharge SSE path only.

## Self-Check: PASSED

Verified via Read + Grep before writing this section:

- `frontend/__tests__/components/ChatApp.integration.test.tsx` exists on disk
- File contains literal `approval_required` (3 occurrences; plan requires ≥ 2)
- File contains literal `D-15.3` (line 16, 105)
- File contains literal `Awaiting your approval — use Approve / Deny above` (line 140)
- File contains BOTH `approve flow` (line 106) AND `deny flow` (line 171)
- File contains `'Approval required'` (line 128, 190)
- File contains `Limited result` (line 202)
- File contains `toBeDisabled` (lines 135, 167, 217)
- File contains `installPauseThenResumeHandler` (lines 78, 108, 173)
- File contains `expect(body.thread_id).toBe('thread-hitl')` (line 94)
- File contains `expect(typeof body.approve).toBe('boolean')` (line 95)
- `cd frontend && npx vitest run __tests__/components/ChatApp.integration.test.tsx` exits 0 — 2 tests passing
- `cd frontend && npx vitest run` exits 0 — 118/118 tests pass (was 116 in Plan 06-02; +2 new)
- `cd frontend && npx tsc --noEmit` exits 0 (no output)
- Code commit `f5d1bd8` exists in git log
- No production source modified — `git show --stat f5d1bd8` shows exactly one file: `frontend/__tests__/components/ChatApp.integration.test.tsx` (220 insertions, 0 deletions)

---
*Phase: 06-hitl-approval-ui-wiring*
*Completed: 2026-05-04*
