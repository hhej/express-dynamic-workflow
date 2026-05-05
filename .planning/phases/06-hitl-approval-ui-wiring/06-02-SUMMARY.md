---
phase: 06-hitl-approval-ui-wiring
plan: 02
subsystem: ui
tags: [react, nextjs, hitl, sse, vitest, testing-library]

# Dependency graph
requires:
  - phase: 05-polish-observability-docs
    provides: useChatStream.approve, ApprovalCard, awaiting_approval status, sixth SSE event approval_required
  - phase: 04-frontend-reasoning-trace
    provides: ChatApp prop-lift pattern, ChatColumn layout, MessageList dispatch
provides:
  - HITL approval prop chain wired ChatApp -> ChatColumn -> MessageList -> ApprovalCard
  - inputDisabled boolean (streaming || awaiting_approval) replacing the misnamed isStreaming
  - Contextual ChatInput placeholder during HITL pause ("Awaiting your approval — use Approve / Deny above")
  - Inline red error surface inside ApprovalCard for failed approve/deny POSTs (D-10/D-11)
  - Pending-assistant-slot lifecycle (placeholder appended on awaiting_approval, stripped + replaced on done)
  - ChatColumn props-forwarding test (D-15.2) preventing future prop-chain drift
affects: [phase-07-message-id-rewrite, phase-08-sidebar-refresh-search-context]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional-prop forwarding chain: ChatApp computes value, layers below forward verbatim"
    - "Pending-slot lifecycle via ref guard (mirrors lastAppendedPayloadRef from Plan 04-05)"
    - "Boolean prop name semantic over situational (inputDisabled, not isStreaming)"

key-files:
  created: []
  modified:
    - frontend/components/ChatApp.tsx
    - frontend/components/chat/ChatColumn.tsx
    - frontend/components/chat/MessageList.tsx
    - frontend/components/chat/ChatInput.tsx
    - frontend/components/chat/ApprovalCard.tsx
    - frontend/__tests__/components/ApprovalCard.test.tsx
    - frontend/__tests__/components/ChatColumn.test.tsx

key-decisions:
  - "ChatColumn isStreaming -> inputDisabled rename: name the boolean for what it gates (input), not for the state that happens to be true (streaming). Same bug class as the original audit Issue 5."
  - "Pending-assistant-slot strip-and-replace on done: placeholder id pending-${ts} never persists into history, keeping the Phase 7 message_id rewrite contract clean."
  - "ApprovalCard waiting state resets via useEffect when errorMessage flips truthy: parent-supplied error means prior attempt failed, so buttons must re-enable (D-11). Cleaner than threading parent-side reset signal."
  - "Two-render pattern in D-15.2 test: ApprovalCard internal waiting state would otherwise disable the second click without an errorMessage to reset it. Test bug, not production bug — fixed by re-rendering with fresh state for each button assertion."
  - "ChatInput placeholder default preserved as the ORIGINAL literal string so all pre-existing ChatInput tests pass without modification — the optional prop is purely additive."

patterns-established:
  - "Layered optional-prop forwarding: ChatColumn / MessageList accept optional approval props; layers below MessageList unchanged. Same pattern works for any future feature that needs to reach ApprovalCard or ChatInput."
  - "useEffect on errorMessage changes inside ApprovalCard: parent error signal acts as a reset trigger for internal waiting flag. Reusable pattern for any leaf component with internal in-flight state plus parent error surface."

requirements-completed: [ORCH-09, UI-01]

# Metrics
duration: 7min
completed: 2026-05-04
---

# Phase 06 Plan 02: HITL Approval UI Wiring Summary

**Wires the HITL approval prop chain ChatApp -> ChatColumn -> MessageList -> ApprovalCard, locks ChatInput while awaiting_approval with contextual placeholder, and adds an inline red error surface for failed approve/deny POSTs**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-04T05:06:33Z
- **Completed:** 2026-05-04T05:14:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Audit Issue 2 closed in code: ApprovalCard now reaches the rendered React tree via the full ChatApp -> ChatColumn -> MessageList prop chain when chat.status === 'awaiting_approval'.
- Audit Issue 5 closed in code: ChatInput is locked while paused (inputDisabled = streaming || awaiting_approval) AND shows a contextual placeholder telling the user what to do.
- ApprovalCard inline error path (D-10/D-11): failed approve/deny POSTs surface a red text-red-700 line below the buttons; buttons stay clickable for retry.
- Pending-assistant-slot lifecycle (D-06): placeholder pushed on awaiting_approval, stripped and replaced by the real payload on done — placeholder id (pending-${ts}) never persists into history.
- ChatColumn isStreaming -> inputDisabled rename closes the underlying naming bug class that produced the original audit gap.
- 3 new ChatColumn tests (D-15.2 props forwarding, D-13 errorMessage forwarding, D-08 placeholder forwarding) prevent future drift on the same prop chain.
- 3 new ApprovalCard tests (D-10 red error line, D-11 buttons clickable on error, baseline absent-error) lock the new error surface.

## Task Commits

Each task was committed atomically:

1. **Task 1: ApprovalCard errorMessage prop + MessageList approvalErrorMessage forwarding + ChatInput placeholder prop** - `ff68f26` (feat)
2. **Task 2: ChatColumn props rename + ChatApp HITL wiring + pending assistant slot + ChatColumn forwarding test** - `6b8eac2` (feat)

**Plan metadata:** _to be added by final commit_ (docs)

## Files Created/Modified

- `frontend/components/chat/ApprovalCard.tsx` — Added optional `errorMessage` prop with inline red `role="alert"` line below buttons; useEffect resets internal `waiting` when errorMessage flips truthy so buttons stay clickable (D-10/D-11).
- `frontend/components/chat/MessageList.tsx` — Added optional `approvalErrorMessage` prop; forwards to `ApprovalCard.errorMessage` (D-13). Existing isLast slot semantics unchanged.
- `frontend/components/chat/ChatInput.tsx` — Added optional `placeholder` prop with the existing literal as default; textarea now consumes the prop instead of a hard-coded literal (D-08).
- `frontend/components/chat/ChatColumn.tsx` — Renamed `isStreaming` -> `inputDisabled` (D-07); added 5 optional props (`awaitingApproval`, `onApprove`, `onDeny`, `approvalErrorMessage`, `placeholder`) and forwards verbatim to MessageList + ChatInput.
- `frontend/components/ChatApp.tsx` — Consumes `chat.approve` / `chat.approvalPayload` / `chat.error`; computes `inputDisabled` / `placeholder` / `approvalErrorMessage`; adds `handleApprove` / `handleDeny` callbacks (D-03); adds `pendingApprovalSlotRef` and a useEffect that pushes a placeholder pending assistant message on awaiting_approval (D-06); strip-and-replace lifecycle in the existing done-effect; `handleNewConversation` clears the new ref.
- `frontend/__tests__/components/ApprovalCard.test.tsx` — Added 3 tests covering D-10 (red error line), D-11 (buttons stay clickable on error), and the baseline absent-error case.
- `frontend/__tests__/components/ChatColumn.test.tsx` — Renamed `isStreaming` -> `inputDisabled` across 6 pre-existing tests; added 3 new tests covering D-15.2 (props forwarding to MessageList -> ApprovalCard), D-13 (errorMessage forwarding), and D-08 (placeholder forwarding).

## Decisions Made

- **Boolean rename over comment**: `isStreaming` -> `inputDisabled` instead of leaving the name and adding a comment that it now means "streaming OR awaiting_approval". The audit Issue 5 root cause was the misleading name — the rename is the durable fix.
- **Strip-and-replace placeholder lifecycle**: Pending placeholder is removed from `messages` state when the real payload arrives on done, NOT kept around with a flag. Eliminates the question of "does Phase 7 need to handle pending-* ids" — the answer is no, they never persist.
- **useEffect-driven waiting reset on errorMessage change**: Cleaner than threading a separate `clearWaiting` callback from parent. The parent surfacing errorMessage IS the signal that the prior attempt failed.
- **Two-render test pattern for D-15.2**: Splits the Approve assertion and Deny assertion into separate render() calls (with unmount() between) to dodge the ApprovalCard internal waiting state. The alternative (passing errorMessage to keep buttons clickable) would muddy the test intent — the test is about prop forwarding, not error handling.
- **Default ChatInput placeholder preserved verbatim**: All 5 pre-existing ChatInput tests use a regex against the original placeholder copy; setting the default to that exact literal means zero test churn for ChatInput.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ApprovalCard buttons stayed disabled forever after a successful click**
- **Found during:** Task 1 (ApprovalCard test for D-11)
- **Issue:** The pre-existing handle() helper in ApprovalCard sets `waiting=true` on click and only resets it in the catch block. With a successful click, `waiting` stays `true` indefinitely, locking BOTH buttons. The D-11 test ("buttons stay clickable on error") correctly fails because clicking Approve disables Deny.
- **Fix:** Added a useEffect that resets `waiting` to false whenever `errorMessage` becomes truthy (parent signal that the prior attempt failed) AND introduced `buttonsDisabled = waiting && !errorMessage` so the disable predicate honours the parent override. This implements D-11 ("buttons stay clickable on POST error") faithfully.
- **Files modified:** frontend/components/chat/ApprovalCard.tsx
- **Verification:** All 9 ApprovalCard tests pass including D-11 (Approve clicks onApprove, then Deny clicks onDeny — both buttons remain enabled when errorMessage is set).
- **Committed in:** ff68f26

**2. [Rule 1 - Test bug] D-15.2 ChatColumn props-forwarding test failed because ApprovalCard internal waiting state disabled the second button click**
- **Found during:** Task 2 (Step B GREEN — D-15.2 test ran red after the prop chain wired, but for a test-side reason, not a production-side reason)
- **Issue:** Plan-prescribed test clicked Approve and Deny in sequence on a single ApprovalCard instance. After the first click, ApprovalCard's `waiting=true` disabled both buttons (no errorMessage in this test to reset).
- **Fix:** Restructured the test to render twice — first render verifies "Approval required" appears + Approve fires onApprove; unmount; second render fires Deny and verifies onDeny. The test now exercises the prop chain for both callbacks without bumping into ApprovalCard's internal waiting state.
- **Files modified:** frontend/__tests__/components/ChatColumn.test.tsx
- **Verification:** All 9 ChatColumn tests pass.
- **Committed in:** 6b8eac2

**3. [Rule 3 - Blocking] Plan 06-01 staged TraceStep changes silently included in Task 1 commit**
- **Found during:** Task 1 commit
- **Issue:** Plan 06-01 (running in parallel as Wave 1) had already staged its TraceStep.tsx + TraceStep.test.tsx changes when this plan started. The `git add <file>` for Task 1's specific files committed those parallel-staged files too, so the Task 1 commit ff68f26 contains 6 files instead of the planned 4. Plan 06-01 subsequently completed cleanly (commit 796f3e8 visible in `git log`).
- **Fix:** No corrective action — Plan 06-01's content is correct and the parallel orchestrator handled the rest. This is a parallel-execution coordination side effect, not a logic error: TraceStep's content matches what Plan 06-01 intended, and Plan 06-01's own commit at 796f3e8 was a no-op delta on those files.
- **Files modified:** frontend/components/trace/TraceStep.tsx, frontend/__tests__/components/TraceStep.test.tsx (NOT in scope of Plan 06-02)
- **Verification:** Plan 06-01 SUMMARY confirms the same content; full vitest suite (116/116) and `next build` clean post-commit.
- **Committed in:** ff68f26 (mixed with Task 1)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 3 parallel-staging coordination)
**Impact on plan:** All three were necessary for correctness or parallel-safety. Deviations 1 and 2 are minor code-quality fixes that close test-side flaws; deviation 3 is a parallel-execution wrinkle that left Plan 06-01's content correct in HEAD without rework.

## Issues Encountered

None beyond the deviations documented above. The plan was extremely well-specified — every acceptance criterion mapped to a verifiable file change, and the only friction was the two test-side issues caught in TDD-RED.

## User Setup Required

None — no external service configuration required. All wiring is purely client-side React with existing useChatStream / SSE infrastructure from Phase 5.

## Next Phase Readiness

- **Audit Issues 2 and 5 closed in code.** A live UAT (high-value query end-to-end) will verify the closure end-to-end; no further code work expected.
- **Plan 06-03** (the planned MSW SSE integration test that exercises the full Approve + Deny flows) is now unblocked — it can rely on the prop chain being correct and assert against ApprovalCard rendering inside ChatApp.
- **Phase 7 message_id rewrite** is unaffected: the placeholder pending-${ts} id is stripped by the done-effect before any payload is appended, so the contract Phase 7 will rewrite (`a-${ts}` -> `${thread_id}-${turn_idx}`) is the only id surface that ever lands in history.
- **Phase 8 search_context wiring + sidebar refresh** is unaffected by this plan.

## Self-Check: PASSED

Verified via Read + Grep before writing this section:

- ApprovalCard.tsx contains `errorMessage?: string | null` (line 10), `text-red-700` (line 95), `role="alert"` (line 94)
- MessageList.tsx contains `approvalErrorMessage?: string | null` (line 30), `errorMessage={approvalErrorMessage}` (line 46)
- ChatInput.tsx contains `placeholder?: string` (line 8), `placeholder={placeholder}` (line 39)
- ChatColumn.tsx contains `inputDisabled: boolean` (line 15), `awaitingApproval?: ApprovalPayload | null` (line 18), `onApprove?:` (line 19), `onDeny?:` (line 20), `approvalErrorMessage?: string | null` (line 22), `placeholder?: string` (line 24), `disabled={inputDisabled}` (line 84), `awaitingApproval={awaitingApproval}` (line 78), `approvalErrorMessage={approvalErrorMessage}` (line 81); does NOT contain `isStreaming` outside a comment.
- ChatApp.tsx contains `chat.approve` (line 99, line 104), `chat.approvalPayload` (line 158, line 176), `Awaiting your approval — use Approve / Deny above` (line 153), `'awaiting_approval'` (line 73, line 151), `inputDisabled={inputDisabled}` (line 174), `pendingApprovalSlotRef` (line 29, etc.), `pending-` (line 80).
- ApprovalCard.test.tsx contains literal "Could not send your decision", "D-10", "D-11".
- ChatColumn.test.tsx contains `inputDisabled` (8 occurrences in test bodies); does NOT contain `isStreaming=`; contains `D-15.2`, `Awaiting your approval — use Approve / Deny above`.
- Commits ff68f26 and 6b8eac2 both visible in `git log --oneline`.
- vitest run __tests__/components/{ApprovalCard,ChatColumn,ChatApp,MessageList,ChatInput}.test.tsx — 32/32 pass; full vitest run — 116/116 pass; npx tsc --noEmit — clean; npm run build — clean.

---
*Phase: 06-hitl-approval-ui-wiring*
*Completed: 2026-05-04*
