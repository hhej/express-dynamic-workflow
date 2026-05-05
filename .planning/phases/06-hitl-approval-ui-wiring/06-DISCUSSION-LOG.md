# Phase 6: HITL Approval UI Wiring + Compile Fix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 06-hitl-approval-ui-wiring
**Areas discussed:** Trace agent labels, ChatInput disabled UX, Approve/Deny error handling, Test coverage scope

---

## Trace agent labels

### `hitl_gate` label

| Option | Description | Selected |
|--------|-------------|----------|
| Approval gate | Plain-English, names the function (review gate before final answer). Matches Bangkok Metro non-jargon copywriting in ApprovalCard ('Approval required'). | ✓ |
| HITL gate | Matches the agent name verbatim and the Phase 5 D-05 decision text. Slightly jargony for end users. | |
| Approval | Shorter, mirrors ApprovalCard heading ('Approval required'). Drops 'gate' term entirely. | |

**User's choice:** Approval gate (Recommended)
**Notes:** Aligns with ApprovalCard heading copy and avoids HITL jargon in the user-visible trace.

### `search_agent` label

| Option | Description | Selected |
|--------|-------------|----------|
| Search agent | Parallel construction with 'Fuel agent' and 'Route agent' — visually consistent in the trace panel column. | ✓ |
| Market search | Domain-flavored — emphasizes news/market context vs generic web search. Diverges from the *agent suffix pattern. | |
| Search | Shortest. Drops the agent suffix — inconsistent with siblings. | |

**User's choice:** Search agent (Recommended)
**Notes:** Keeps the trace panel column reading consistently across all four specialist agents.

---

## ChatInput disabled UX

### User-visible affordance

| Option | Description | Selected |
|--------|-------------|----------|
| Disabled + contextual placeholder | Swap placeholder to 'Awaiting your approval — use Approve / Deny above' while paused. Cheap, explains the state, no new components. Reverts to normal placeholder once resumed. | ✓ |
| Disabled only — no copy change | Just toggle disabled=true. Relies on the visible ApprovalCard above the input to communicate state. Smallest diff. | |
| Disabled + inline hint banner above input | Adds a small 'Approve or deny the recommendation above' banner between MessageList and ChatInput. More discoverable but introduces a new UI element to maintain. | |

**User's choice:** Disabled + contextual placeholder (Recommended)
**Notes:** Same disable mechanic plus a one-string change turns "looks broken" into "agent is waiting for you" — strong demo signal at zero new component cost.

### Wire shape

| Option | Description | Selected |
|--------|-------------|----------|
| ChatApp passes a single combined `inputDisabled` boolean | ChatApp computes `chat.status === 'streaming' \|\| chat.status === 'awaiting_approval'` and passes one boolean. ChatColumn stays dumb — it just forwards. Easiest to test, single source of truth. | ✓ |
| Pass `chatStatus` enum down to ChatColumn | ChatColumn receives the full ChatStatus and decides locally. More flexible (e.g., disable on 'error' too), but pushes status semantics into a layout component. | |
| Replace `isStreaming` prop with `awaitingApproval` boolean too | ChatColumn receives both flags and ORs them. Slightly more verbose, but each flag has clear meaning at the call site. | |

**User's choice:** ChatApp passes a single combined `inputDisabled` boolean (Recommended)
**Notes:** Single source of truth for "should the input be disabled"; ChatColumn stays a layout-only forwarder consistent with Plan 04-05 D-05.

---

## Approve/Deny error handling

### Error UX

| Option | Description | Selected |
|--------|-------------|----------|
| Inline error message inside ApprovalCard + buttons stay clickable | ApprovalCard shows a small 'Could not send your decision — try again.' line in red below the buttons when chat.status='error' AND approvalPayload is still set. Buttons stay live so user can retry without leaving the card. Single contained surface, no new global error UI. | ✓ |
| Rely on existing global error card — no ApprovalCard change | Phase 4 already renders error state somewhere (or will after this phase wires it). Keep ApprovalCard pure, surface error via the existing path. Smallest diff but error message visually disconnects from the action. | |
| Toast/snackbar via a new component | Add a transient toast on approve failure. New component, new state. Probably overkill for a one-off network failure during demo. | |

**User's choice:** Inline error message inside ApprovalCard + buttons stay clickable (Recommended)
**Notes:** Error appears next to the action that caused it; retry path is the same buttons; no new component to maintain.

### Retry path

| Option | Description | Selected |
|--------|-------------|----------|
| Stays visible until success | approvalPayload remains in state through the error — useChatStream's RESUME_START already clears it on a fresh attempt. User retries via the same buttons. Matches the Pitfall 2 invariant (paused HITL stream keeps Approve/Deny live). | ✓ |
| Add explicit Cancel button to dismiss | Adds a third button to ApprovalCard. Lets user abandon. But the backend graph stays paused at the interrupt() — abandon means an orphaned checkpoint. Adds complexity for an edge case. | |

**User's choice:** Stays visible until success (Recommended)
**Notes:** Cancel would require backend checkpoint cleanup not justified for v1 demo; resume on a future click works because AsyncSqliteSaver checkpoint persists.

---

## Test coverage scope

### Test scope

| Option | Description | Selected |
|--------|-------------|----------|
| Vitest unit/component + ChatApp integration test with MSW SSE mock | Test 1: TraceStep renders for all 7 AgentName keys (catches the original bug class). Test 2: ChatColumn forwards approval props to MessageList. Test 3: ChatApp integration drives a full approval_required → click Approve → mock resume SSE flow via MSW. Catches the wiring break end-to-end at unit speed. No browser. Fits existing infra. | ✓ |
| Above + Playwright e2e against real backend stub | Adds a real-browser test running through the ChatColumn → ApprovalCard → click → resume flow with a stubbed backend. Highest confidence but adds Playwright-runtime cost; Phase 4 already has the harness so cost is low. | |
| Vitest unit only — no integration test | Just verify TraceStep keys, ChatColumn props, MessageList slot logic in isolation. Smallest. But this is exactly what passed before — unit-level verification is what missed the original gap. | |

**User's choice:** Vitest unit/component + ChatApp integration test with MSW SSE mock (Recommended)
**Notes:** The bug class hides at the integration boundary; the integration test specifically exercises that boundary at unit speed. Playwright stays available for future flow gaps.

### TraceStep test scope

| Option | Description | Selected |
|--------|-------------|----------|
| Exhaustive over the AgentName union | Loop over all 7 AgentName values, assert TraceStep renders a non-undefined label for each. Future-proof: any further AgentName extension that forgets AGENT_LABEL fails the test immediately. Drift prevention. | ✓ |
| Spot-check hitl_gate + search_agent only | Two assertions, narrowly scoped to today's bug. Minimal, but won't catch the next missing key when AgentName grows again. | |

**User's choice:** Exhaustive over the AgentName union (Recommended)
**Notes:** Belt-and-braces against the same bug class recurring on a future AgentName extension.

---

## Claude's Discretion

- Module split between ApprovalCard error rendering vs a small inline `<ApprovalError>` subcomponent
- Placeholder prop on ChatInput vs override via parent
- Single-constant placeholder string vs i18n-ready helper (single constant fine for v1)
- Exact Tailwind classes for the inline error line
- Wave assignment / plan splitting (likely two plans but planner has full discretion)
- Pending placeholder slot id format (must not collide with Phase 7 `{thread_id}-{turn_idx}` final id)

## Deferred Ideas

- Cancel approval — backend cleanup not justified for v1
- Approval timeout / auto-escalation — rejected in Plan 05-05; v2
- Toast/snackbar global error UI — not justified for one-off network failure
- Past-turn approval inspection — Langfuse covers audit need externally
- Playwright e2e for approval flow — next step if integration layer surfaces a gap
- Approval analytics — out of scope
- Phase 7 message_id rewrite — explicitly Phase 7's scope, not Phase 6
- Phase 8 search_context wiring + sidebar refresh — explicitly Phase 8's scope
