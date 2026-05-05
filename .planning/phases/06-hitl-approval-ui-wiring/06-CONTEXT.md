# Phase 6: HITL Approval UI Wiring + Compile Fix - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the HITL approval flow through the production frontend so a high-value Bangkok Metro shipment query renders ApprovalCard with working Approve / Deny, fix the TypeScript compile failure that blocks `next build`, and lock ChatInput while `chat.status === 'awaiting_approval'`. Closes audit Issues 1, 2, 5; reopens Flow 1+2 (compile) and Flow 3 (HITL E2E).

**In scope (this phase):**
- ORCH-09 (HITL approval rendered to user) — flip from "partial" to "satisfied"
- UI-01 (chat interface produces a clean production bundle) — flip from "partial" to "satisfied"
- TraceStep.AGENT_LABEL extended to cover all 7 `AgentName` keys (`hitl_gate`, `search_agent` added)
- ChatApp → ChatColumn → MessageList prop chain for `awaitingApproval` / `onApprove` / `onDeny`
- ChatInput disable predicate extended to `awaiting_approval`; contextual placeholder swap
- Inline error surface inside ApprovalCard for failed approve/deny POST; retry without dismissing
- Test coverage that prevents the same class of integration drift recurring (Vitest + MSW SSE integration; exhaustive AgentName loop over TraceStep)

**Explicitly out of scope (deferred to Phase 7 / 8 / v2):**
- API-05 / OBS-02 / UI-05 message_id contract drift — Phase 7 owns this (ChatApp `a-${Date.now()}` → `{thread_id}-{turn_idx}`)
- TOOL-05 / UI-02 search_context omission from final_payload + SearchContextLine dead branch — Phase 8 owns this
- UI-06 conversation sidebar refresh after a completed turn — Phase 8 owns this
- Phase 5 pending human deliverables (`docs/screenshots/*.png`, `docs/demo.mp4`, `git tag v1.0`) — they are NOT regressions; they are awaiting human action and are tracked in audit §6 tech debt
- Backend changes to `interrupt()` / `Command(resume)` / sixth SSE event / `approval_required` payload — Phase 5 already shipped these and the audit found them functional; Phase 6 is purely a frontend wiring + compile fix

</domain>

<decisions>
## Implementation Decisions

### Trace agent labels (Issue 1 — TS compile blocker)
- **D-01:** `TraceStep.AGENT_LABEL` extended to cover all 7 `AgentName` keys verbatim. Display strings:
  - `planner` → `'Planner'` (existing)
  - `fuel_agent` → `'Fuel agent'` (existing)
  - `route_agent` → `'Route agent'` (existing)
  - `pricing_agent` → `'Pricing agent'` (existing)
  - `response` → `'Response'` (existing)
  - `hitl_gate` → `'Approval gate'` (NEW)
  - `search_agent` → `'Search agent'` (NEW)
- **D-02:** Label choices justified: `'Approval gate'` matches the user-facing `'Approval required'` heading in `ApprovalCard.tsx` (Plan 05-05) and avoids the internal `HITL` jargon in user copy. `'Search agent'` is parallel-construction with `'Fuel agent'` / `'Route agent'` so the trace panel column reads consistently.

### ChatApp ↔ ChatColumn ↔ MessageList prop chain (Issue 2 — HITL unreachable)
- **D-03:** ChatApp consumes `chat.approvalPayload` and `chat.approve` from `useChatStream()` (both already exposed in Plan 05-06 — see [frontend/hooks/useChatStream.ts:215-284](frontend/hooks/useChatStream.ts#L215-L284) and the returned `{ ...state, send, reset, approve }` at line 295). ChatApp creates two thin handler callbacks `handleApprove = () => chat.approve(threadId, true)` and `handleDeny = () => chat.approve(threadId, false)` and forwards them — plus `chat.approvalPayload` — to ChatColumn.
- **D-04:** `ChatColumn` Props interface gains three new optional fields: `awaitingApproval?: ApprovalPayload | null`, `onApprove?: () => void | Promise<void>`, `onDeny?: () => void | Promise<void>`. ChatColumn forwards them verbatim to MessageList. No conditional logic inside ChatColumn — it is a dumb forwarder so the responsibility split mirrors Plan 04-05 D-05 (ChatColumn = layout-only).
- **D-05:** No new wrapper component. `MessageList.tsx` already accepts `awaitingApproval / onApprove / onDeny` (see [frontend/components/chat/MessageList.tsx:24-30](frontend/components/chat/MessageList.tsx#L24-L30)) and renders `ApprovalCard` in the **last assistant slot** (lines 84-92 — `isLast && awaitingApproval` gates the slot). The phase 6 work is purely the missing prop pipe from ChatApp → ChatColumn → MessageList; no MessageList changes.
- **D-06:** Approval-pending slot semantics. The last assistant message MAY have `payload === null` while `awaitingApproval` is set — the `AssistantMessage.payload: FinalPayload | null` widening from Plan 05-06 stays. ChatApp's existing `useEffect` that appends an assistant message when `chat.finalPayload` arrives is **unchanged** (it appends after the resume completes); for the pause window the FE needs an empty assistant slot whose `id` and `payload === null` are the placeholder ApprovalCard hangs off. ChatApp adds: when `chat.status === 'awaiting_approval'` AND the previous render had no awaiting slot, push a `{ role: 'assistant', id: \`pending-${Date.now()}\`, payload: null }` placeholder. The placeholder must NOT be appended a second time on re-render (use a ref guard mirroring `lastAppendedPayloadRef`).

### ChatInput disabled UX (Issue 5 — input enabled while paused)
- **D-07:** Disabled predicate is computed in ChatApp as a single `inputDisabled = chat.status === 'streaming' || chat.status === 'awaiting_approval'` boolean and passed to ChatColumn via a renamed `inputDisabled` prop. The current `isStreaming` prop is **renamed** to `inputDisabled` (semantics drift was the original bug class — pick a name that says what the boolean is FOR, not what state happens to be true today). ChatColumn forwards verbatim to ChatInput's existing `disabled` prop.
- **D-08:** Contextual placeholder swap. ChatInput receives a new optional `placeholder?: string` prop (or its existing default placeholder is conditionally overridden by the parent — planner picks the cleaner of the two). ChatApp computes the placeholder string:
  - `chat.status === 'awaiting_approval'` → `"Awaiting your approval — use Approve / Deny above"`
  - any other status → existing default (presumably `"Type a message..."` or similar — preserve current copy)
- **D-09:** No new "hint banner" component between MessageList and ChatInput. The visible ApprovalCard above plus the placeholder swap is sufficient; one less surface to maintain or test.

### Approve / Deny error handling
- **D-10:** Inline error surface inside ApprovalCard. ApprovalCard accepts a new optional `errorMessage?: string | null` prop. When present, render a `text-red-700` line below the buttons reading `"Could not send your decision — try again."` (or the more specific message when available). ApprovalCard's existing `waiting` local state still resets on click error so the buttons remain clickable.
- **D-11:** Approve/Deny buttons stay clickable on error — no disable. The approvalPayload remains in `useChatStream` state (Plan 05-06 RESUME_START clears it on a fresh attempt; the `'error'` status is non-clearing on its own, which is desired here).
- **D-12:** No Cancel button. Abandoning an approval would orphan a checkpointer state at the `interrupt()` boundary; the rate-limited demo scope (15 RPM Gemini, free-tier) does not justify the backend cleanup work to support cancel. Resume on a future click works because the AsyncSqliteSaver checkpoint remains valid for the thread.
- **D-13:** ChatApp threads `chat.error?.message` (when `chat.status === 'error'` AND `chat.approvalPayload` is non-null) down to ApprovalCard via the prop chain ChatColumn → MessageList → ApprovalCard. Same wire mechanism as the approve/deny callbacks (one optional prop added at each layer; layers below MessageList unchanged in shape).

### Test coverage (drift prevention)
- **D-14:** Vitest unit + integration only. No new Playwright e2e in Phase 6 — Plan 04-05 already established the Playwright harness, but Phase 6's bug class is a prop-wiring + compile-time gap that unit/integration tests catch faster, deterministically, and at every PR. Re-evaluate Playwright in a later phase if a flow gap surfaces that cannot be reproduced at the unit/integration layer.
- **D-15:** Three required test surfaces:
  1. **Exhaustive `TraceStep.AGENT_LABEL` test** — loop over all 7 `AgentName` literal values, assert `TraceStep` renders a non-empty, non-`undefined` label for each. Future-proof: any new `AgentName` literal that forgets to update `AGENT_LABEL` will fail the loop. Lives at `frontend/components/trace/TraceStep.test.tsx`.
  2. **ChatColumn props-forwarding test** — assert `ChatColumn` passes `awaitingApproval / onApprove / onDeny` through to `MessageList` unchanged when given. Lives at `frontend/components/chat/ChatColumn.test.tsx`.
  3. **ChatApp integration test with MSW SSE mock** — mock `POST /api/chat` to emit a `meta` → `trace` → `approval_required` SSE sequence; assert `ApprovalCard` renders inside the rendered tree; click Approve; mock the resume `POST /api/chat` to emit `meta` → `trace` → `answer` → `done`; assert `MarkdownAnswer` renders the final answer; ChatInput is disabled across the whole sequence. Lives at `frontend/components/__tests__/ChatApp.integration.test.tsx` (or the equivalent location existing tests use). MUST also cover the deny path: click Deny, mock the resume to emit a `partial`-status `answer`, assert `PartialCard` renders.
- **D-16:** Coverage gate. Phase 6 success criteria are not met until all three test surfaces above pass. The execution plan must include the failing-test-first TDD ordering (write test → see it fail → wire props → see it pass) for the ChatApp integration test specifically — the audit's lesson is that the bug class hides when the integration is never exercised.

### Claude's Discretion
- Exact module split between ApprovalCard error rendering vs a small inline `<ApprovalError>` subcomponent — both fit; planner picks based on file readability.
- Whether to use a placeholder prop on ChatInput vs override the existing default placeholder via the parent — both are clean; planner picks.
- Whether the placeholder text is a constant in a single file or threaded via i18n-ready helper — single constant is fine for v1 (no i18n in scope).
- Exact Tailwind classes for the ApprovalCard inline error line — `text-red-700` is the intent; planner reuses any existing red-error pattern from PartialCard / error states elsewhere if one exists, otherwise picks a consistent token.
- Wave assignment / plan splitting — likely two plans (Wave 1: TraceStep keys + tests; Wave 2: ChatApp ↔ ChatColumn ↔ MessageList wiring + ChatInput predicate + ApprovalCard error prop + integration test) but planner has full discretion.
- Whether the placeholder pending-assistant slot uses `id: \`pending-${Date.now()}\`` or a more deterministic id (e.g., `pending-${chat.threadId}-${turnIdx}`). Note: Phase 7 will rewrite assistant message id construction across the board to `{thread_id}-{turn_idx}` — the placeholder id chosen here must not collide with the Phase 7 final id, OR the placeholder must be replaced by the real assistant message on `done` so the id surface is irrelevant. Planner verifies the substitution path.
- Whether to add a regression test for the AgentName ↔ AGENT_LABEL invariant via a TS-level type test (`Record<AgentName, string>` is already enforced by the type — the broken state was a compile error, so the test is `next build` itself). The Vitest exhaustive loop in D-15 is belt-and-braces.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit (THE driver for this phase)
- `.planning/v1.0-MILESTONE-AUDIT.md` — §2.2 Issue 1 (TraceStep compile), Issue 2 (HITL unreachable), §2.3 Issue 5 (ChatInput awaiting_approval). §3 Flow 1+2 (compile-blocked), Flow 3 (HITL broken). §7 file paths at the centre of the gaps. §8 recommended next step.

### Phase inputs from earlier phases
- `.planning/phases/05-polish-observability-docs/05-CONTEXT.md` — Phase 5 locked decisions, especially:
  - **D-04 / D-05** HITL trigger condition + `interrupt()` placement — backend contract Phase 6 frontend honours unchanged
  - **D-06** Sixth SSE event `approval_required` — payload shape `{surcharge_result, threshold, thread_id}` drives ApprovalCard props (already wired in Plan 05-06)
  - **D-07** `approval_decision` AgentState field + deny `status="partial"` — backend contract; FE renders PartialCard on deny resume
  - **D-08** Trace step pre-pause warn + post-resume ok — already emitted; Phase 6 only labels them via D-01
- `.planning/phases/04-frontend-reasoning-trace/04-CONTEXT.md` — Phase 4 locked decisions:
  - **D-12** Distinct visual treatments per `answer.payload.status` — ApprovalCard added in Phase 5 sits ABOVE the dispatch (renders in place of MarkdownAnswer when `awaitingApproval` is set)
  - **D-19** SSE consumer dispatches by event type — extended in Phase 5 to include `approval_required`; Phase 6 is consumer-facing only
  - **D-08** Trace panel = current-turn only — preserved (resume turn = own trace stream)

### Implementation source files (Phase 6 modifies)
- `frontend/components/trace/TraceStep.tsx` (lines 7-13) — extend `AGENT_LABEL: Record<AgentName, string>` with `hitl_gate` + `search_agent` per D-01. Closes audit Issue 1.
- `frontend/components/ChatApp.tsx` — consume `chat.approvalPayload` / `chat.approve` / `chat.error`; thread to ChatColumn. Compute `inputDisabled` boolean (D-07). Compute placeholder string (D-08). Append placeholder pending assistant slot (D-06). Closes audit Issue 2 + Issue 5.
- `frontend/components/chat/ChatColumn.tsx` — extend Props with `awaitingApproval / onApprove / onDeny / inputDisabled / placeholder / approvalErrorMessage`; rename `isStreaming` to `inputDisabled` per D-07; forward verbatim to MessageList + ChatInput. Closes audit Issue 5.
- `frontend/components/chat/ChatInput.tsx` — accept optional `placeholder` prop (or accept the parent's override mechanism — planner picks); existing `disabled` prop semantics unchanged.
- `frontend/components/chat/MessageList.tsx` — already accepts `awaitingApproval / onApprove / onDeny` (Plan 05-06). Phase 6 ADDS optional `approvalErrorMessage` and forwards to ApprovalCard.
- `frontend/components/chat/ApprovalCard.tsx` — accept optional `errorMessage` prop per D-10; render inline red error line below buttons when set. Buttons stay clickable per D-11.
- `frontend/types/agent.types.ts` — `AgentName` already covers 7 keys (Plan 05-04 / 05-05); no changes. Phase 6 only adds AGENT_LABEL coverage.
- `frontend/components/trace/TraceStep.test.tsx` (NEW or extended) — exhaustive AgentName loop per D-15.1.
- `frontend/components/chat/ChatColumn.test.tsx` (NEW or extended) — props-forwarding per D-15.2.
- `frontend/components/__tests__/ChatApp.integration.test.tsx` (NEW; planner verifies the existing test layout convention) — full approve + deny SSE integration via MSW per D-15.3.

### Phase 6 does NOT modify
- `backend/agent/nodes/hitl_gate.py` — backend contract is correct (audit confirmed)
- `backend/api/routes/chat.py` — sixth SSE event + Command(resume) is correct (audit confirmed)
- `backend/agent/state.py` — `approval_decision` field already present (Plan 05-01 D-07)
- `frontend/hooks/useChatStream.ts` — `approve()` and `approval_required` reducer already present (Plan 05-06)
- `frontend/components/chat/ApprovalCard.tsx` body styling, copy, palette — locked by Plan 05-05 D-07 + UI-SPEC

### Requirements & project framing
- `.planning/REQUIREMENTS.md` — Phase 6 scope: ORCH-09 (move from Active to Complete), UI-01 (move from Active to Complete)
- `.planning/PROJECT.md` — Tech stack lock (Next.js 15 + React 19 + Tailwind, Bangkok Metro phrasing per backlog 999.2), local-reproducibility constraint
- `.planning/ROADMAP.md` §Phase 6 — five success criteria (compile clean, ApprovalCard renders, Approve resumes, Deny short-circuits, ChatInput disabled while awaiting_approval)

### Coding conventions
- `.planning/codebase/CONVENTIONS.md` §TypeScript — PascalCase.tsx components, camelCase.ts utilities, `*.types.ts`, `@/` path aliases, JSDoc on public APIs
- `.planning/codebase/STRUCTURE.md` §Frontend — `frontend/components/{chat,trace,sidebar,dashboard}/` layout

### Backlog
- `.planning/ROADMAP.md` §Backlog 999.2 — "Bangkok Metro" phrasing in user-facing copy. The new placeholder text and inline error message in this phase are user-facing — must use Bangkok Metro phrasing if the copy ever references the scope (it likely does not, but flag for review).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/components/chat/ApprovalCard.tsx` — fully built, locked styling per Plan 05-05 D-07; only needs an optional `errorMessage` prop for D-10.
- `frontend/components/chat/MessageList.tsx` — already accepts `awaitingApproval / onApprove / onDeny`; the `isLast && slotApproval` gate at lines 84-92 is correct. Phase 6 only adds the optional `approvalErrorMessage` plumbing.
- `frontend/hooks/useChatStream.ts` — `approve()` callback (line 215), `approvalPayload` state field (line 28), `'awaiting_approval'` ChatStatus (line 18), DONE-guard for awaiting_approval (lines 76-78), RESUME_START reducer (lines 88-95) — all already shipped in Plan 05-06.
- `frontend/types/agent.types.ts` — `AgentName` already 7-keyed (lines 8-15), `ApprovalPayload` interface (lines 67-72), `'approval_required'` SSE event variant (line 81) — all already shipped.
- Phase 4 Vitest + RTL + MSW infra (Plan 04-01) — fixture/setup pattern at `frontend/__tests__/setup.ts` (storage polyfill noted in Plan 04-02 D-04 — Node 25 quirk); planner reuses for the integration test.
- Phase 4 SSE event mocking precedent — `useChatStream` and `parseSseStream` already covered by unit tests (Plan 04-02); planner reuses the MSW SSE handler shape.

### Established Patterns
- **Optional-prop forwarding chain** — Plan 04-05 D-02 lifts `useChatStream + useConversations` once at ChatApp and threads state via props. Phase 6 follows the same pattern for the three new approval-related props.
- **D-12 status switch in MessageList** — MessageList dispatches on `payload.status` to render `MarkdownAnswer / ClarifyCard / PartialCard`. ApprovalCard is rendered ABOVE this dispatch when `slotApproval` is set; deny path eventually flows back to PartialCard via `payload.status === 'partial'` after resume.
- **`isLast` gating for action buttons** — MessageList already gates FeedbackButtons (line 93) and the ApprovalCard slot (lines 84-86) on the last assistant message. Pattern is established.
- **Pitfall 2 invariant** — `useChatStream` reducer DONE-guard preserves `'awaiting_approval'` (lines 76-78). Phase 6 must not regress this — disable predicate is read-only, no state mutations.
- **Bangkok Metro phrasing** (resolved backlog 999.2) — applies to any new user-facing copy added in this phase. The placeholder text (D-08) does not reference the scope; the inline error text (D-10) does not reference the scope. Both are scope-agnostic copy and safe.

### Integration Points
- `frontend/components/ChatApp.tsx` — main wiring change: consume + forward `chat.approvalPayload / chat.approve / chat.error / chat.status`; compute `inputDisabled`, `placeholder`, `approvalErrorMessage`; create handlers for approve/deny; append placeholder pending assistant slot; thread props down.
- `frontend/components/chat/ChatColumn.tsx` — shape change: new optional props, rename `isStreaming` → `inputDisabled`; verbatim forward.
- `frontend/components/chat/ChatInput.tsx` — minor: optional `placeholder` prop accepted; default preserved.
- `frontend/components/chat/MessageList.tsx` — minor: optional `approvalErrorMessage` accepted and forwarded to ApprovalCard.
- `frontend/components/chat/ApprovalCard.tsx` — minor: optional `errorMessage` prop accepted; conditional red error line rendered.
- `frontend/components/trace/TraceStep.tsx` — single-line fix: extend `AGENT_LABEL` with two new entries.

</code_context>

<specifics>
## Specific Ideas

- **The audit's lesson is wider than this phase.** Every individual phase passed verification — what failed was the cross-phase integration boundary. The Phase 6 ChatApp integration test (D-15.3) is specifically designed to catch the bug class in *future* phases too. If a Phase 9+ ever reshapes useChatStream or ApprovalCard, this test is the alarm.
- **Placeholder semantics matter for the demo.** Per PROJECT.md core value ("visible reasoning is what makes this agentic"), the user-visible HITL pause IS the agentic differentiator on the 35% Agent Architecture rubric. A blank disabled input during pause looks broken; the contextual placeholder turns the same UI moment into "the agent is waiting for you" — same code, much stronger demo signal.
- **Don't over-engineer the error path.** D-10 / D-11 / D-12 are deliberately minimal: inline red line, no toast, no Cancel, no global error UI. The course is graded on agent architecture, not on feedback UX polish — and Phase 7 / 8 still have surface to cover.
- **Phase 7 message_id rewrite affects the placeholder pending-assistant id.** D-06 places `id: \`pending-${Date.now()}\`` on the pending slot; Phase 7 rewrites assistant message id to `{thread_id}-{turn_idx}`. The two ids must not collide once Phase 7 lands. Either (a) the placeholder is replaced by the real assistant message on `done` (so the placeholder id is irrelevant after), or (b) the placeholder id avoids the `{thread_id}-{turn_idx}` shape (the `pending-` prefix already does this). Both are safe; planner verifies (a) is the actual code path so the placeholder never persists into history.
- **TraceStep test is a TS-correctness regression test.** A `Record<AgentName, string>` typed lookup is already enforced at compile time — the bug existed because *someone overrode the type with explicit keys instead of a const computed from the union*. The Vitest loop in D-15.1 is the runtime backup; the real fix is keeping `Record<AgentName, string>` as the source of truth.

</specifics>

<deferred>
## Deferred Ideas

- **Cancel approval** (D-12) — would require backend cleanup of orphaned `interrupt()` checkpoints; not justified for v1 demo. v2 if a real workflow ever needs cancelable approvals.
- **Approval timeout / auto-escalation** — explicitly rejected in Plan 05-05 discussion; auto-approve was deemed weak grading signal. v2 if SLA-bound approval is ever needed.
- **Toast / snackbar global error UI** — not justified for one-off network failures; inline error in ApprovalCard suffices.
- **Past-turn approval inspection** — Phase 4 D-08 deferred past-turn trace; same applies to past approval decisions. Langfuse traces (Plan 05-02 OBS-01) cover the audit need externally.
- **Playwright e2e for the approval flow** — Phase 6 ships unit + integration; Playwright is the next step if a future bug surfaces that the integration layer cannot catch.
- **Approval analytics / count of approve-vs-deny** — out of scope; Langfuse Score (Plan 05-06 D-16) covers thumbs feedback already, approve/deny is a different signal class and is not in v1 requirements.
- **Phase 7 (message_id contract alignment)** — explicitly deferred to Phase 7 per ROADMAP §Phase 7. Phase 6 does NOT touch ChatApp's `\`a-${Date.now()}\`` id construction even though the line is in the same file (audit Issue 3 is Phase 7's scope; mixing it into Phase 6 violates the gap-closure ordering and risks recurrence of cross-phase contract drift).
- **Phase 8 (search_context wiring + sidebar refresh)** — deferred per ROADMAP §Phase 8.

### Reviewed Todos (not folded)
None — `gsd-tools todo match-phase 6` returned 0 matches.

</deferred>

---

*Phase: 06-hitl-approval-ui-wiring*
*Context gathered: 2026-05-03*
