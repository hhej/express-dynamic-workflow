---
phase: 07-feedback-contract-alignment
plan: 02
subsystem: frontend
tags: [react, nextjs, vitest, msw, typescript, feedback, contract-alignment, tdd]

# Dependency graph
requires:
  - phase: 07-feedback-contract-alignment
    plan: 01
    provides: "Backend stamps message_id on /api/chat answer payload + on LAST assistant per turn returned from GET /api/conversations/:id"
  - phase: 06-hitl-ui-wiring
    provides: "ChatApp resume scaffolding (handleResume + useConversations.resume), MessageList feedback-button gate scaffold"
provides:
  - "FinalPayload.message_id REQUIRED at the type system boundary — TypeScript blocks any future answer-payload literal that omits message_id (D-04)"
  - "ChatApp live-append + resume map now read BE-stamped message_id verbatim (D-03/D-05); broken `a-${Date.now()}` and `replay-${i}` constructions eliminated"
  - "MessageList FeedbackButtons gate extended with payload.message_id truthy check (D-08); messageId prop reads the explicit feedback identity instead of the React reconciliation key"
  - "ChatApp.feedback.integration.test.tsx — Vitest+MSW round-trip tests for both live (D-09) and resume (D-11) paths"
  - "useChatStream.setThreadId — public setter for resume-time thread propagation (Rule 2 deviation; closes silent feedback failure on every resumed conversation)"
affects: [phase-07-03-docs-and-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Required-field-as-drift-prevention — required FinalPayload.message_id forces the TypeScript type system to fail every answer-payload literal that omits the BE-stamped id; no runtime guard needed"
    - "Empty-string fallback as suppress signal — payload.message_id='' on non-canonical resume rows reads as falsy in the MessageList gate; same wire shape, different semantics for canonical vs in-turn-partial rows"
    - "Round-trip Vitest+MSW assertion mirrors BE contract — D-09 test re-encodes the backend's regex `^(.+)-(\\d+)$` and the thread_id cross-check INSIDE the MSW handler so any future drift in either layer fails the test immediately"

key-files:
  created:
    - "frontend/__tests__/components/ChatApp.feedback.integration.test.tsx"
  modified:
    - "frontend/types/agent.types.ts"
    - "frontend/types/api.types.ts"
    - "frontend/__tests__/fixtures/sse.ts"
    - "frontend/components/ChatApp.tsx"
    - "frontend/components/chat/MessageList.tsx"
    - "frontend/hooks/useChatStream.ts"

key-decisions:
  - "FinalPayload.message_id REQUIRED (not optional) per D-04 — propagated cleanly through fixtures with zero cascading test-file edits because every test reuses the four shared fixtures (HAPPY/CAPPED/CLARIFY/PARTIAL)"
  - "ReplayedMessage.message_id OPTIONAL per D-05/D-06 — backend silently omits the field on user rows and non-last in-turn assistant rows, so the FE contract has to permit absence at the type level"
  - "Resume map fallback id is a synthetic non-canonical literal (`replay-noncanonical-${i}`), NOT empty string — keeps React reconciliation keys stable while payload.message_id='' tells the MessageList gate to suppress FeedbackButtons"
  - "MessageList messageId prop reads m.payload.message_id, NOT m.id — explicit data-flow change. Both are equal for canonical rows post-Task 2, but reading from the payload makes the feedback identity-of-truth visible at the call site"
  - "[Rule 2 deviation] useChatStream.setThreadId added — without it chat.threadId stays null after resume and the MessageList gate's `threadId &&` check silently suppresses every replayed FeedbackButtons. Pre-existing bug deeper than audit Issue 3 captured; closing it satisfies D-11 acceptance criteria"
  - "FeedbackButtons.tsx NOT modified (LOCKED Phase 5 D-16 props shape) — only the value flowing into messageId changes"
  - "useChatStream answer-reducer NOT modified (Pitfall 4 — type system is the drift-prevention chokepoint, not the reducer)"

patterns-established:
  - "Pattern 1: Drift prevention via required-field at the type-system boundary — REQUIRED message_id on FinalPayload makes any future regression that drops the field a compile error, not a runtime bug"
  - "Pattern 2: Resume-path data flow — handleResume reads BE-supplied per-message message_id, propagates into payload.message_id (or empty fallback) AND ChatMessage.id, AND now also into chat.threadId via setThreadId"
  - "Pattern 3: Round-trip integration test mirrors the BE contract — MSW handler re-encodes the BE regex assertion in-test so FE + BE drift fails the test before it lands in production"

requirements-completed: [API-05, OBS-02, UI-05]

# Metrics
duration: 7min
completed: 2026-05-04
---

# Phase 7 Plan 02: Feedback Contract Alignment (Frontend) Summary

**Frontend now reads the BE-stamped `message_id` on both live-append and resume paths, with the TypeScript type system enforcing message_id presence on every answer payload — closes the FE half of audit Issue 3 and adds round-trip Vitest+MSW tests as the lasting drift-prevention layer.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-04T07:10:53Z
- **Completed:** 2026-05-04T07:17:49Z
- **Tasks:** 3
- **Files modified:** 6 (3 production + 1 fixture + 2 type + 1 new test)

## Accomplishments

- `FinalPayload.message_id` is now REQUIRED at the type-system boundary (D-04). Any future answer-payload literal that omits the field fails `tsc --noEmit` — drift prevention is structural, not runtime.
- `ReplayedMessage.message_id` added as OPTIONAL (D-05/D-06). Mirrors backend silent absence on user rows and non-last in-turn assistant rows.
- All four canonical fixtures (HAPPY/CAPPED/CLARIFY/PARTIAL) carry concrete BE-shape `message_id` strings (`thread-{kind}-0`).
- ChatApp live-append: assistant ChatMessage.id now reads `chat.finalPayload!.message_id` (BE-stamped) instead of the broken `a-${Date.now()}` clock construction (D-03).
- ChatApp resume map: assistant rows use `m.message_id` from GET /api/conversations/:id when present, with synthetic `replay-noncanonical-${i}` fallback for HITL pre-pause partials (D-05). `payload.message_id` is also propagated (or empty-string fallback) so the MessageList gate suppresses FeedbackButtons on non-canonical rows.
- MessageList FeedbackButtons gate now also checks `m.payload.message_id` truthy (D-08); messageId prop reads `m.payload.message_id` (the explicit feedback identity) instead of `m.id` (the React reconciliation key).
- New `frontend/__tests__/components/ChatApp.feedback.integration.test.tsx`:
  - **D-09 live path:** sends a query, clicks thumbs-up, asserts POST /api/feedback fires with the BE-stamped UUIDv4-shaped message_id AND that the wire body satisfies the BE regex `^(.+)-(\d+)$` AND the parsed thread_id equals body.thread_id (BE contract mirrored in-test).
  - **D-11 resume path:** mocks GET /api/conversations/:id with per-message message_id, clicks sidebar to trigger handleResume, clicks thumbs-up on the replayed assistant, asserts POST /api/feedback uses the BE-supplied id (`replay-thread-0`, NOT a `replay-${i}` reconstruction).
- 120/120 frontend tests green (118 baseline + 2 new D-09/D-11 tests).

## Task Commits

Each task was committed atomically:

1. **Task 1: Frontend types — required FinalPayload.message_id and fixtures (D-04)** — `2e7044b` (feat)
2. **Task 2: Frontend ChatApp — live-append + resume-map BE-stamped message_id (D-03, D-05)** — `36ae2b0` (feat)
3. **Task 3: Frontend MessageList gate (D-08) + ChatApp.feedback.integration.test.tsx (D-09 + D-11)** — `bda5abc` (feat)

## Files Created/Modified

### Created

- `frontend/__tests__/components/ChatApp.feedback.integration.test.tsx` — Vitest+MSW round-trip tests covering D-09 (live path) and D-11 (resume path). Defensive in-test assertions mirror the backend regex + thread_id cross-check inside the MSW POST /api/feedback handler so any future contract drift on either layer fails the test immediately.

### Modified

- `frontend/types/agent.types.ts` — `FinalPayload.message_id` is now REQUIRED (D-04). Doc comment explicitly forbids FE reconstruction (audit Issue 3 root cause).
- `frontend/types/api.types.ts` — `ReplayedMessage.message_id` added as OPTIONAL (D-05/D-06). Doc comment notes silent absence as the FE feedback-button gate signal.
- `frontend/__tests__/fixtures/sse.ts` — HAPPY_PAYLOAD/CAPPED_PAYLOAD/CLARIFY_PAYLOAD/PARTIAL_PAYLOAD all carry concrete `thread-{kind}-0` message_ids.
- `frontend/components/ChatApp.tsx` — live-append useEffect uses `chat.finalPayload!.message_id` (D-03); handleResume map uses `m.message_id` with `replay-noncanonical-${i}` fallback (D-05); `chat.setThreadId(threadId)` called post-resume (Rule 2 deviation).
- `frontend/components/chat/MessageList.tsx` — FeedbackButtons gate adds `m.payload.message_id` truthy check (D-08); messageId prop reads `m.payload.message_id` instead of `m.id` for explicit data flow.
- `frontend/hooks/useChatStream.ts` — added `setThreadId` public helper (Rule 2 deviation) so handleResume in ChatApp can propagate the resumed thread_id into chat state. Without this fix, chat.threadId stayed null after every resume click and feedback was silently broken on every resumed conversation.

## Decisions Made

- **Required-field-as-drift-prevention.** Making `FinalPayload.message_id` required (not optional) means the TypeScript compiler — not the production code — is the drift-prevention chokepoint. Every test fixture, every component prop type, every reducer state literal that constructs a FinalPayload now MUST include message_id. Any future regression where an answer-payload mock or production builder omits the field fails `tsc --noEmit` before it reaches CI. Per Pitfall 4 in 07-RESEARCH.md, this is structurally stronger than runtime guards.
- **Cascade impact was minimal.** Per Plan 07-01 Rule 2 deviation expectations, I anticipated cascading tsc errors across ~6 test files that construct FinalPayload literals (MessageList.test, MarkdownAnswer.test, PartialCard.test, ClarifyCard.test, useChatStream.test, useChatStream-approval.test). The actual cascade was zero — every test file imports HAPPY_PAYLOAD or builds payloads via spread `{...HAPPY_PAYLOAD, status: 'partial' as const}`, so updating the four shared fixtures propagated automatically. Only ChatApp.tsx's resume-map literal (which Task 2 already owned) needed the field added.
- **Synthetic non-canonical-id fallback in handleResume.** The resume map's `m.message_id ?? \`replay-noncanonical-${i}\`` fallback keeps React reconciliation keys stable for non-canonical assistant rows (HITL pre-pause partials). `payload.message_id` separately falls back to `''` (empty string), which the MessageList gate reads as falsy and uses to suppress FeedbackButtons. Two distinct values for two distinct concerns: React keying vs feedback identity.
- **MessageList messageId prop reads `m.payload.message_id`, NOT `m.id`.** Both are equal for canonical rows post-Task 2 (live-append sets `id: chat.finalPayload.message_id` and resume sets `id: m.message_id`). But reading from `payload.message_id` makes the data-flow explicit at the call site: feedback identity-of-truth lives in the payload, not in the React reconciliation key. Future readers see the wire-format origin without having to trace back to ChatApp.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added `useChatStream.setThreadId` public helper and wired it into `ChatApp.handleResume`**

- **Found during:** Task 3 (D-11 resume-path integration test failed — `Helpful` button not found in DOM)
- **Issue:** The plan's D-11 test renders ChatApp, clicks a sidebar conversation entry to trigger handleResume, expects the replayed assistant table to render, then expects to find a `Helpful` thumbs-up button to click. The button never appeared because `MessageList`'s FeedbackButtons render gate is `{threadId && m.payload && m.payload.message_id && !slotApproval && ...}`, and `threadId` (from `chat.threadId` in ChatApp.tsx line 173) was null. Tracing back: `useChatStream` only sets `state.threadId` via the `META` SSE event during a `send()` call OR by reading `localStorage.threadId` on initial mount (line 118-121). `useConversations.resume()` writes to localStorage AFTER the user clicks a sidebar entry — but the chat hook is already mounted so it never re-reads. Result: chat.threadId stayed null after every resume click, and the FeedbackButtons gate's `threadId &&` check silently suppressed every replayed FeedbackButtons. **Feedback was silently broken on every resumed conversation pre-Phase-7** — deeper than audit Issue 3 captured, but exactly the bug class Plan 07-01's Rule 2 deviation already hinted at ("the entire resume rendering path is degenerate today").
- **Fix:** Added a public `setThreadId(threadId: string)` callback to `useChatStream` that dispatches `{ type: 'RESET', threadId }`, mirroring the existing reducer semantics that already accept a non-null threadId on RESET. Wired it into `ChatApp.handleResume` after `setMessages(replayed)`. The handleResume `useCallback` dependency array also updated from `[conversations]` to `[conversations, chat]` to satisfy exhaustive-deps and pick up the new `chat.setThreadId` reference.
- **Files modified:** `frontend/hooks/useChatStream.ts`, `frontend/components/ChatApp.tsx`
- **Verification:** D-11 integration test now passes; full Vitest suite 120/120 green; tsc clean. The fix is the minimal required change — no new state shape, no new reducer action (RESET already handled the case), no breaking changes to existing consumers (`reset` and `approve` are unchanged).
- **Committed in:** `bda5abc` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality — Rule 2)
**Impact on plan:** Without the deviation, the D-11 acceptance criterion was unmeetable. The fix is the minimum required change AND closes a pre-existing silent feedback failure on every resumed conversation. No scope creep — the new behavior is exactly what the plan's Test 2 contract implicitly requires.

## Auth Gates

None — no external service authentication exercised in this plan (MSW handlers mock all network I/O at the FE boundary).

## Issues Encountered

- **Single tsc error after Task 1.** The fixture/type updates surfaced one tsc error in `ChatApp.tsx`'s resume-map FinalPayload literal — but Task 2 owns ChatApp.tsx and immediately closed it. Vitest stayed green throughout (vite tolerates tsc-failing literals when the fixture used by tests is shape-correct). Committed Task 1 atomically with the known tsc error documented in the commit message; Task 2 cleared it 30 seconds later. Pragmatic atomicity over global tsc-after-every-task.
- **D-11 test initial fail.** The test failed on first run because of the resume-time threadId propagation gap above (Rule 2 deviation). Fix landed in the same task commit (bda5abc) and both D-09 and D-11 now pass.

## Locked Contracts (Untouched)

Per Phase 7 D-16 / Plan 07-01 invariants, the following files were NOT modified:

- `frontend/components/chat/FeedbackButtons.tsx` — Phase 5 D-16 LOCKED. Props shape `{threadId, messageId}` and api.postFeedback call unchanged. Only the value flowing into messageId changed.
- `frontend/hooks/useChatStream.ts` answer reducer (`case 'ANSWER'`) — already pipes the FinalPayload through transparently; required-field on FinalPayload is the drift-prevention chokepoint, not the reducer (Pitfall 4 mitigation).
- `backend/api/routes/feedback.py` — `_TURN_RE` regex `^(.+)-(\d+)$` and thread_id cross-check unchanged. The D-09 test re-encodes the regex assertion in-test, mirroring the BE contract.

## Next Phase Readiness

- **Plan 07-03 (live verification + docs) is unblocked.** The full audit Issue 3 contract is now closed end-to-end: BE stamps message_id (Plan 07-01) → FE reads it verbatim (Plan 07-02) → POST /api/feedback wire body satisfies the BE regex AND the cross-thread guard. A production thumbs-up click should now succeed (HTTP 200) and the resulting Langfuse Score should land on the EXACT trace the chat handler's CallbackHandler attached to during the original turn (Phase 5 D-14). Plan 07-03 codifies the manual smoke (D-13/D-14) and captures the `langfuse-feedback-score.png` screenshot evidence (D-15/D-16).
- **API-05 / OBS-02 / UI-05** can now flip from `partial` → `satisfied` once Plan 07-03's live Langfuse Score lands. The structural and test-harness drift prevention is in place; only the live-trace evidence remains.

## Self-Check: PASSED

- All 6 modified files present (verified via git status)
- New test file `frontend/__tests__/components/ChatApp.feedback.integration.test.tsx` exists
- All 3 task commits present in git log (2e7044b, 36ae2b0, bda5abc)
- 120/120 frontend tests green (118 baseline + 2 new D-09/D-11 tests)
- All acceptance criteria literal-string checks passed via Grep verification (chat.finalPayload!.message_id, m.message_id ??, m.payload.message_id, D-09 live path, D-11 resume path, a4b27c8e-d4f1-4ddd-aaaa-1234567890ab, replay-thread-0, expect(m[1]).toBe(feedbackBody!.thread_id), regex literal `/^(.+)-(\d+)$/`)
- LOCKED contracts (FeedbackButtons.tsx, useChatStream answer reducer) untouched
- tsc --noEmit exits 0

---
*Phase: 07-feedback-contract-alignment*
*Completed: 2026-05-04*
