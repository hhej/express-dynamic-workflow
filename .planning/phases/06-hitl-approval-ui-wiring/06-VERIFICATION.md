---
phase: 06-hitl-approval-ui-wiring
verified: 2026-05-04T12:26:00Z
status: passed
score: 5/5 must-haves verified
---

# Phase 6: HITL Approval UI Wiring Verification Report

**Phase Goal:** Production frontend bundles cleanly, ApprovalCard renders end-to-end on high-value queries, and ChatInput is locked during awaiting_approval — closing the HITL flow break that the v1.0 audit surfaced.
**Verified:** 2026-05-04T12:26:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Success Criteria from Phase Goal)

| #   | Truth                                                                                                                                       | Status     | Evidence                                                                                                                                                         |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `next build` completes with no TS errors (TraceStep.AGENT_LABEL covers all 7 AgentName keys)                                                | VERIFIED   | `npm run build` exits 0 (Next.js 15 production bundle compiles, static pages generate); `npx tsc --noEmit` exits 0; AGENT_LABEL has 7 keys at TraceStep.tsx:7-15 |
| 2   | A high-value shipment query causes ApprovalCard to render in the rendered React tree, with working Approve / Deny buttons                   | VERIFIED   | `ChatApp.integration.test.tsx` "approve flow" + "deny flow" both render ApprovalCard via real MSW SSE stream and assert "Approval required" heading is in the DOM; both tests pass |
| 3   | Clicking Approve resumes the graph via `chat.approve()` and the response_node delivers a final answer                                       | VERIFIED   | Integration test approve flow asserts resume POST body has `thread_id='thread-hitl'` + `approve=true`, then MarkdownAnswer table renders with `152.50 THB` HAPPY_PAYLOAD value |
| 4   | Clicking Deny short-circuits via Command(resume=denied) and surfaces the deny path response                                                 | VERIFIED   | Integration test deny flow asserts resume POST body has `approve=false`, then PartialCard renders with PARTIAL_PAYLOAD prose "Limited result — fuel data fetched but route lookup failed" |
| 5   | ChatInput is disabled while `chat.status === 'awaiting_approval'`                                                                            | VERIFIED   | ChatApp.tsx:148-149 computes `inputDisabled = streaming \|\| awaiting_approval` and passes through ChatColumn → ChatInput; integration test asserts `getByRole('button', { name: 'Send message' }).toBeDisabled()` after approval_required event |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact                                                              | Expected                                                                          | Status   | Details                                                                                                                                                                                                                                       |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/components/trace/TraceStep.tsx`                             | AGENT_LABEL covers all 7 AgentName keys (D-01)                                    | VERIFIED | All 7 keys present: planner, fuel_agent, route_agent, pricing_agent, response, hitl_gate ('Approval gate'), search_agent ('Search agent'). Static `Record<AgentName, string>` type guarantees compile-time completeness                       |
| `frontend/__tests__/components/TraceStep.test.tsx`                    | Exhaustive AGENT_NAMES loop test (D-15.1)                                         | VERIFIED | Line 8 declares `const AGENT_NAMES: readonly AgentName[]` with 7 literals; line 61 contains the loop test; renders TraceStep for each AgentName variant and asserts non-empty label                                                          |
| `frontend/components/ChatApp.tsx`                                     | Consumes `chat.approve` + `chat.approvalPayload`; computes inputDisabled/placeholder/approvalErrorMessage; pending-slot ref guard (D-03/D-06/D-07/D-08/D-13) | VERIFIED | Lines 32 (pendingApprovalSlotRef), 73 (`'awaiting_approval'`), 80 (`pending-${Date.now()}`), 97-105 (handleApprove/handleDeny call `chat.approve`), 148-160 (computed values), 174-181 (props passed to ChatColumn) |
| `frontend/components/chat/ChatColumn.tsx`                             | Layout-only forwarder for awaitingApproval/onApprove/onDeny/inputDisabled/placeholder/approvalErrorMessage (D-04/D-07) | VERIFIED | Lines 11-25 Props interface contains all required optional/required props; lines 75-87 forward to MessageList + ChatInput; only stale `isStreaming` reference is in JSDoc comment at line 14 (renamed-from note)                              |
| `frontend/components/chat/MessageList.tsx`                            | Forwards approvalErrorMessage to ApprovalCard (D-13)                              | VERIFIED | Line 31 declares `approvalErrorMessage?: string \| null`; line 39 passes through renderAssistant signature; line 48 forwards `errorMessage={approvalErrorMessage}` to ApprovalCard                                                            |
| `frontend/components/chat/ApprovalCard.tsx`                           | Optional `errorMessage` prop renders red error line below buttons (D-10/D-11)     | VERIFIED | Line 10 declares `errorMessage?: string \| null`; line 32-36 useEffect resets `waiting` when errorMessage flips truthy; line 50 `buttonsDisabled = waiting && !errorMessage` (D-11 buttons stay clickable); lines 105-112 render `role="alert"` + `text-red-700` line |
| `frontend/components/chat/ChatInput.tsx`                              | Optional `placeholder` prop with default fallback preserved (D-08)                | VERIFIED | Line 9 declares `placeholder?: string`; line 15 default preserves original literal; line 45 textarea consumes the prop                                                                                                                        |
| `frontend/__tests__/components/ChatColumn.test.tsx`                   | Props-forwarding test asserts ChatColumn passes approval props to MessageList (D-15.2) | VERIFIED | Line 128 contains "D-15.2" test name; tests assert ApprovalCard appears, error message forwards, and placeholder forwards through ChatColumn                                                                                                  |
| `frontend/__tests__/components/ChatApp.integration.test.tsx`          | End-to-end approve + deny SSE integration via MSW (D-15.3)                        | VERIFIED | File exists; contains `installPauseThenResumeHandler` call-counter MSW handler; defensive `expect(body.thread_id).toBe('thread-hitl')` + `expect(typeof body.approve).toBe('boolean')` inside handler closure; both `approve flow` and `deny flow` test names present |

### Key Link Verification

| From                                                              | To                                                                       | Via                                                                              | Status | Details                                                                                                                                                                |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/components/trace/TraceStep.tsx`                         | `frontend/types/agent.types.ts AgentName`                                | `Record<AgentName, string>` type-driven completeness                             | WIRED  | TraceStep.tsx:7 uses `Record<AgentName, string>` — TS would error if any of the 7 AgentName variants were missing                                                      |
| `frontend/__tests__/components/TraceStep.test.tsx`                | `frontend/components/trace/TraceStep.tsx AGENT_LABEL`                    | runtime exhaustive loop over all 7 AgentName literals                            | WIRED  | TraceStep.test.tsx:71 `for (const agent of AGENT_NAMES) { ... }` walks all 7 literals and asserts non-empty rendered label                                            |
| `frontend/components/ChatApp.tsx`                                 | `frontend/hooks/useChatStream.ts approve/approvalPayload`                | `useChatStream()` destructure + handler callbacks                                | WIRED  | ChatApp.tsx:23 `const chat = useChatStream()`; lines 99, 104 call `chat.approve(chat.threadId, true/false)`; line 158, 176 read `chat.approvalPayload`              |
| `frontend/components/ChatApp.tsx`                                 | `frontend/components/chat/ChatColumn.tsx`                                | props: awaitingApproval, onApprove, onDeny, inputDisabled, placeholder, approvalErrorMessage | WIRED  | ChatApp.tsx:171-181 passes 9 props to ChatColumn including all approval-related fields                                                                                 |
| `frontend/components/chat/ChatColumn.tsx`                         | `frontend/components/chat/ChatInput.tsx`                                 | `disabled={inputDisabled}` + `placeholder={placeholder}`                         | WIRED  | ChatColumn.tsx:83-87 forwards `disabled={inputDisabled}` and `placeholder={placeholder}` to ChatInput                                                                  |
| `frontend/components/chat/ChatColumn.tsx`                         | `frontend/components/chat/MessageList.tsx`                               | `awaitingApproval`, `onApprove`, `onDeny`, `approvalErrorMessage` forwarded     | WIRED  | ChatColumn.tsx:75-82 forwards all 4 approval props to MessageList                                                                                                      |
| `frontend/components/chat/MessageList.tsx`                        | `frontend/components/chat/ApprovalCard.tsx`                              | `errorMessage={approvalErrorMessage}` forwarded; `payload={awaitingApproval}` set in last assistant slot | WIRED  | MessageList.tsx:42-50 conditional `if (awaitingApproval && onApprove && onDeny)` returns ApprovalCard with all 4 props including `errorMessage`                       |
| `frontend/__tests__/components/ChatApp.integration.test.tsx`      | `frontend/components/ChatApp.tsx + ChatColumn.tsx + MessageList.tsx + ApprovalCard.tsx` | `render(<ChatApp />)` + MSW SSE mock + `userEvent.click` on Approve/Deny       | WIRED  | Test renders production ChatApp tree; clicks Approve/Deny; both tests pass under MSW                                                                                  |
| `frontend/__tests__/components/ChatApp.integration.test.tsx`      | `frontend/__tests__/mocks/server.ts`                                     | `server.use(http.post(...))` MSW SSE handler                                     | WIRED  | Test imports `server` and registers `http.post('http://localhost:8000/api/chat', ...)` handler with call-counter switching                                            |

### Data-Flow Trace (Level 4)

| Artifact                                | Data Variable                                                  | Source                                                                                  | Produces Real Data | Status                                                  |
| --------------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------ | ------------------------------------------------------- |
| `ApprovalCard.tsx` (render)             | `payload: ApprovalPayload`, `errorMessage`                     | Parent prop chain from ChatApp `chat.approvalPayload` (real `useChatStream` SSE state) | Yes                | FLOWING — integration test confirms real MSW SSE event populates the payload, ApprovalCard renders with totals + threshold |
| `ChatInput.tsx` (textarea)              | `disabled` prop                                                | ChatColumn → ChatApp `inputDisabled` (computed from `chat.status`)                      | Yes                | FLOWING — integration test asserts `toBeDisabled()` after approval_required SSE event arrives |
| `MessageList.tsx` (last assistant slot) | `awaitingApproval`, `approvalErrorMessage`                     | ChatColumn → ChatApp `chat.approvalPayload` and computed `approvalErrorMessage`         | Yes                | FLOWING — `useChatStream` writes `approvalPayload` from SSE; ChatApp surfaces error from `chat.error?.message`           |
| `TraceStep.tsx` (label render)          | `AGENT_LABEL[entry.agent]`                                     | Static map; type-checked at compile time against `AgentName` union                      | Yes                | FLOWING — every AgentName variant produces a non-empty label (verified by exhaustive loop test) |

### Behavioral Spot-Checks

| Behavior                                                              | Command                                                                                                  | Result                                       | Status |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ------ |
| Production bundle compiles cleanly                                    | `cd frontend && npm run build`                                                                           | Exit 0; static pages generated; 266 kB First Load JS | PASS   |
| TypeScript types are sound                                            | `cd frontend && npx tsc --noEmit`                                                                        | Exit 0 (no output)                            | PASS   |
| HITL integration test exercises end-to-end approve + deny flows       | `cd frontend && npx vitest run __tests__/components/ChatApp.integration.test.tsx`                        | 2 tests passed (1 file)                       | PASS   |
| Full Vitest suite passes (no regressions across phase 06 changes)     | `cd frontend && npx vitest run`                                                                          | 26 files / 118 tests passed                   | PASS   |

### Requirements Coverage

| Requirement | Source Plan          | Description                                                                                  | Status    | Evidence                                                                                                                                                         |
| ----------- | -------------------- | -------------------------------------------------------------------------------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ORCH-09     | 06-02-PLAN.md, 06-03-PLAN.md | Human-in-the-loop approval gate for high-value shipments before finalizing surcharge | SATISFIED | Integration test approve flow asserts resume POST body includes `approve: true`; deny flow asserts `approve: false`; ApprovalCard renders threshold + totals; both end-to-end paths covered under MSW |
| UI-01       | 06-01-PLAN.md, 06-02-PLAN.md, 06-03-PLAN.md | Chat interface for natural language surcharge queries with SSE streaming display | SATISFIED | ChatApp + ChatColumn + ChatInput compile cleanly; TraceStep renders all 7 AgentName labels; ChatInput placeholder/disabled state correct during HITL pause; SSE stream correctly drives ApprovalCard render via integration test |

No orphaned requirements. REQUIREMENTS.md maps Phase 6 → ORCH-09 + UI-01; both IDs declared in plan frontmatter.

### Anti-Patterns Found

| File                                            | Line | Pattern                                                  | Severity | Impact                                                                                                                                                                                          |
| ----------------------------------------------- | ---- | -------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/components/chat/ChatColumn.tsx`       | 14   | Comment references old `isStreaming` name                | Info     | Documentation reference only — JSDoc says "RENAMED from isStreaming" to explain the rename. Acceptance criterion was "isStreaming fully removed", but the doc note is informative, not a stub |
| `frontend/components/chat/ChatInput.tsx`        | 8-15 | "placeholder" string literals                            | Info     | These are the legitimate `placeholder` prop name and default text — false positive in stub scanner                                                                                              |
| `frontend/components/chat/FeedbackButtons.tsx`  | 31   | Unused eslint-disable directive                          | Info     | Reported by `next build` linter — pre-existing from earlier phase, not introduced by Phase 6, no functional impact                                                                              |

No blocker or warning anti-patterns. No TODOs, FIXMEs, or stub returns introduced by Phase 6.

### Human Verification Required

None required for the automated verification surface. The Phase 6 plans flagged a "live UAT (high-value query end-to-end)" as the residual evidence for closing audit Issue 2 in production (06-02-SUMMARY.md "Next Phase Readiness"), but the integration test under MSW now exercises the full prop chain end-to-end with realistic SSE stream framing, satisfying success criteria 2-5 programmatically.

If a manual UAT is desired before tagging v1.0:

### 1. Live HITL flow against the real backend

**Test:** Start backend (`uvicorn backend.api.main:app --port 8000`) and frontend (`npm run dev`); send a high-value shipment query that exceeds the approval threshold; observe ApprovalCard appears with surcharge totals; click Approve; observe MarkdownAnswer renders the final answer; repeat with Deny.
**Expected:** ApprovalCard renders within 5 seconds of submitting query; ChatInput is locked + shows "Awaiting your approval — use Approve / Deny above" placeholder; clicking Approve produces a final markdown answer in the chat; clicking Deny produces a partial-status response.
**Why human:** Visual confirmation of yellow-50/yellow-300 ApprovalCard palette and color contrast; real-time SSE behavior end-to-end against the production backend (the integration test mocks the SSE stream).

### Gaps Summary

No gaps found. All five Success Criteria from the phase goal are programmatically verified:

- SC 1 — `next build` clean exit: TraceStep.AGENT_LABEL has all 7 AgentName keys; production bundle compiles
- SC 2 — ApprovalCard renders end-to-end on high-value queries: integration test confirms via real MSW SSE stream
- SC 3 — Approve resumes the graph: integration test asserts resume POST body, MarkdownAnswer renders final answer
- SC 4 — Deny short-circuits: integration test asserts `approve: false`, PartialCard renders deny prose
- SC 5 — ChatInput disabled during awaiting_approval: integration test asserts `.toBeDisabled()`

Drift-prevention layer (D-15.1 exhaustive loop, D-15.2 prop forwarding, D-15.3 end-to-end MSW) is in place to catch the same bug class in any future phase. Both phase requirement IDs (ORCH-09, UI-01) are SATISFIED.

---

_Verified: 2026-05-04T12:26:00Z_
_Verifier: Claude (gsd-verifier)_
