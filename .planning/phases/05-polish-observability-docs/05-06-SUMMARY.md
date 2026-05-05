---
phase: 05-polish-observability-docs
plan: 06
subsystem: api
tags: [feedback, langfuse, hitl, sse, ui, postFeedback, approve, react, fastapi]

requires:
  - phase: 05-polish-observability-docs/01
    provides: FeedbackRequest Pydantic model + observability helpers (seed_trace_id, get_langfuse_client)
  - phase: 05-polish-observability-docs/02
    provides: deterministic seed_trace_id pattern wired into POST /api/chat — feedback POST resolves the SAME trace_id without name lookup
  - phase: 05-polish-observability-docs/04
    provides: search_context AgentState field — SearchContextLine renders payload.search_context above MarkdownAnswer prose
  - phase: 05-polish-observability-docs/05
    provides: approval_required SSE event + Command(resume) wire — ApprovalCard + useChatStream.approve() wire to this
provides:
  - POST /api/feedback handler — backend/api/routes/feedback.py with deterministic trace_id resolution from message_id ("{thread_id}-{turn_idx}")
  - app.include_router(feedback_router) wired into backend/api/main.py
  - frontend/types/agent.types.ts extended — sixth SSE event variant (approval_required), AgentName += {hitl_gate, search_agent}, SearchContext + ApprovalPayload interfaces, FinalPayload.search_context optional field
  - frontend/types/api.types.ts ChatRequest.message widened to optional + ChatRequest.approve added (HITL resume body)
  - frontend/lib/api.ts postFeedback wrapper + FeedbackRequestBody / FeedbackResponse types
  - frontend/hooks/useChatStream.ts — APPROVAL_REQUIRED + RESUME_START actions, approvalPayload state field, awaiting_approval ChatStatus, approve(threadId, decision) callback that POSTs {thread_id, approve}
  - frontend/components/chat/ApprovalCard.tsx — yellow-50/yellow-300 inline gate with neutral-outline Approve/Deny buttons + Bangkok Metro phrasing
  - frontend/components/chat/SearchContextLine.tsx — gray-50 + blue-200 left rule, "Market context:" semibold prefix + italic summary + optional Sources details
  - frontend/components/chat/FeedbackButtons.tsx — localStorage stub swapped for api.postFeedback (UI unchanged)
  - frontend/components/chat/MarkdownAnswer.tsx — prepends SearchContextLine when search_context.summary present, strips backend-emitted Market context blockquote to avoid duplication
  - frontend/components/chat/MessageList.tsx — branches to ApprovalCard when awaitingApproval prop populated on the LAST assistant slot; AssistantMessage.payload widened to FinalPayload | null
affects: [05-07-docs-tag]

tech-stack:
  added: []  # all libs already pinned by 05-01; this plan is wire-up only
  patterns:
    - "Deterministic trace_id resolution from message_id parser: re-use seed_trace_id(thread_id, turn_idx) so feedback Score lands on the EXACT trace recorded by the chat handler (no name lookup, no drift)"
    - "Reducer-level Pitfall 2 guard: DONE action preserves status when state.status === 'awaiting_approval' so the unconditional finally-block dispatch can't auto-flip the FE out of the paused state"
    - "Last-assistant-slot approval: only the trailing assistant message can host an ApprovalCard; FeedbackButtons gated on `!slotApproval` so they never show on a paused turn"
    - "MarkdownAnswer dual-source consistency: backend response_node also emits the Market context as a markdown blockquote (so non-FE consumers see it); FE strips that blockquote and renders the typed SearchContextLine instead — no duplication"

key-files:
  created:
    - backend/api/routes/feedback.py
    - backend/tests/test_api_feedback.py
    - frontend/components/chat/ApprovalCard.tsx
    - frontend/components/chat/SearchContextLine.tsx
    - frontend/__tests__/components/ApprovalCard.test.tsx
    - frontend/__tests__/components/SearchContextLine.test.tsx
    - frontend/__tests__/hooks/useChatStream-approval.test.ts
  modified:
    - backend/api/main.py
    - frontend/types/agent.types.ts
    - frontend/types/api.types.ts
    - frontend/lib/api.ts
    - frontend/hooks/useChatStream.ts
    - frontend/components/chat/FeedbackButtons.tsx
    - frontend/components/chat/MarkdownAnswer.tsx
    - frontend/components/chat/MessageList.tsx
    - frontend/__tests__/components/FeedbackButtons.test.tsx

key-decisions:
  - "Deterministic trace_id from message_id: backend feedback handler parses message_id as '{thread_id}-{turn_idx}' (anchored on trailing -<digits>) and calls seed_trace_id(thread_id, turn_idx) — same helper Plan 05-02 used to attach the per-turn Langfuse CallbackHandler. Score lands on the matching trace WITHOUT a name lookup."
  - "Defense-in-depth thread_id mismatch returns 400: body thread_id and message_id-encoded thread_id must agree — protects against accidental cross-thread Score posting if FE serialises inconsistently."
  - "D-13 graceful no-op preserved: when LANGFUSE_* keys missing, POST /api/feedback returns 200 with delivered=false (NOT a user-facing error) so the FE silent-error contract stays clean."
  - "useChatStream reducer guard for Pitfall 2: DONE action returns state unchanged when status === 'awaiting_approval' — the finally block dispatches DONE unconditionally on stream close, but Pitfall 2 demands the FE keep Approve/Deny buttons live across the no-trailing-done HITL pause; reducer-level guard is the chokepoint that enforces this without forking send() vs approve()."
  - "FeedbackButtons UI is intentionally unchanged from Phase 4 (same glyphs, same aria-pressed, same disabled-after-vote) — only the side-effect swaps from localStorage write to api.postFeedback POST; on POST failure, error is console.error'd and button stays voted (silent — no toast)."
  - "ApprovalCard uses NEUTRAL outline buttons (border-gray-300 bg-white) NOT accent blue — D-07 demands deliberate user choice; matching CapCallout's yellow-50/yellow-300 palette signals 'review required' without inventing a new color."
  - "MarkdownAnswer strips the backend-emitted '> **Market context:**' blockquote line and renders the typed SearchContextLine component instead — avoids dual rendering when both code paths exist (response_node prose + FE typed prefix)."
  - "MessageList AssistantMessage.payload widened to FinalPayload | null — null while awaiting_approval, so the slot can render ApprovalCard in place of MarkdownAnswer; existing consumers (ChatApp.tsx) always pass non-null so the widening is backward-compatible."
  - "Last-assistant-slot-only approval rendering: only the trailing assistant message can host an ApprovalCard (isLast guard) — historical messages above it stay rendered as completed answers."
  - "ChatRequest.message widened from required to optional in frontend/types/api.types.ts to mirror the Phase 5 (Plan 05-02) backend ChatRequest contract — required for the resume path that sends only {thread_id, approve}."

patterns-established:
  - "Deterministic feedback wire: FE postFeedback({thread_id, message_id, score}) → BE parses message_id → seed_trace_id(thread_id, turn_idx) → langfuse.create_score(trace_id=...). Same helper used for callback init, no name lookup."
  - "FE state-machine extension via reducer-level guards: when adding new statuses to a tagged-union state machine, update existing action handlers (e.g. DONE) to preserve the new status — single chokepoint vs scattering checks across send()/approve()."
  - "Component-level UI-SPEC palette reuse: ApprovalCard reuses CapCallout yellow-50/yellow-300; SearchContextLine reuses the gray-50 caption pattern — no new color tokens introduced."

requirements-completed:
  - API-05
  - OBS-02

duration: ~45 min
completed: 2026-05-03
---

# Phase 5 Plan 06: Feedback API + Frontend Wires Summary

**API-05 / OBS-02 — POST /api/feedback resolves trace_id deterministically from message_id and forwards to Langfuse user_feedback Score; frontend ApprovalCard + SearchContextLine + FeedbackButtons swap + useChatStream.approve() complete the HITL + search-context + feedback wires.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 3 (all auto, all TDD)
- **Files modified:** 16 (7 new, 9 modified)
- **Tests added:** 6 backend + 4 useChatStream-approval + 6 SearchContextLine + 6 ApprovalCard + 5 FeedbackButtons (rewrite from localStorage→API stub)

## Accomplishments

- POST /api/feedback wired end-to-end with deterministic trace_id resolution: backend parses `message_id="{thread_id}-{turn_idx}"`, calls `seed_trace_id(thread_id, turn_idx)` (same helper Plan 05-02 used to attach the Langfuse CallbackHandler), and posts `langfuse.create_score(trace_id=..., name="user_feedback", value=1|-1)` — the Score lands on the matching trace WITHOUT a name lookup.
- Defense-in-depth: body `thread_id` and `message_id`-encoded `thread_id` must agree (400 on mismatch); malformed message_id (no trailing `-<digits>` suffix) → 400; langfuse `create_score` raises → 502 with detail.
- D-13 graceful no-op preserved: when `LANGFUSE_*` keys missing, POST /api/feedback returns 200 with `delivered=false` and `reason="langfuse_disabled"` — FE never sees a user-facing error from missing observability keys.
- Frontend types extended without rewrite: SSEEvent union grew the sixth `approval_required` variant; AgentName grew `hitl_gate` (Plan 05-05) + `search_agent` (Plan 05-04); FinalPayload grew the optional `search_context` field; ApprovalPayload + SearchContext + SearchContextSource interfaces added.
- `api.postFeedback` wrapper added to `frontend/lib/api.ts` with `FeedbackRequestBody` / `FeedbackResponse` types (snake_case across the wire — Phase 4 hand-mirroring invariant preserved).
- `useChatStream` extended additively: `awaiting_approval` ChatStatus, `approvalPayload` state field, APPROVAL_REQUIRED + RESUME_START actions, and an `approve(threadId, decision)` callback that POSTs `{thread_id, approve}` and re-streams the response through the same reducer pipeline as `send()`. Pitfall 2 (no trailing `done` after `approval_required`) enforced via a reducer-level guard on the DONE action that preserves `awaiting_approval` — single chokepoint, no fork between send() and approve().
- `ApprovalCard` matches UI-SPEC contract verbatim: yellow-50 bg + yellow-300 border + yellow-900 text (CapCallout palette reuse), 16px semibold "Approval required" heading, surcharge breakdown table, neutral-outline Approve/Deny buttons (D-07 deliberate choice), italic 12px "Sending your decision…" caption with `aria-live="polite"` while waiting, Bangkok Metro phrasing in body copy.
- `SearchContextLine` matches UI-SPEC: gray-50 bg + blue-200 left rule + p-2, 12px text-gray-700 with semibold "Market context:" prefix + italic summary, optional collapsed `<details>` "Sources: N" with `target="_blank" rel="noopener noreferrer"` links.
- `FeedbackButtons` swapped localStorage write for `api.postFeedback({thread_id, message_id, score})`; UI is intentionally unchanged from Phase 4 (same glyphs, same aria-pressed, same disabled-after-vote); on failure, console.error logs the error and the button stays voted (silent — no toast).
- `MarkdownAnswer` prepends `<SearchContextLine context={...} />` when `payload.search_context.summary` is non-empty; strips the backend-emitted `> **Market context:**` blockquote line so the typed component is the single source of truth visually.
- `MessageList` branches to `<ApprovalCard>` when `awaitingApproval` prop is populated AND the slot is the last assistant message; FeedbackButtons gated on `!slotApproval` so they never appear on a paused turn. `AssistantMessage.payload` widened from `FinalPayload` to `FinalPayload | null` to support the awaiting-approval slot.

## Trace_id flow (D-16 recap)

```
chat handler (Plan 05-02)  →  _make_config(thread_id, turn_idx)
                                 ├─ trace_id = seed_trace_id(thread_id, turn_idx)
                                 └─ Langfuse CallbackHandler attaches with that trace_id
                              ▼
LangGraph runs                 (formula_accuracy Score also posts on this trace_id)
                              ▼
FE FeedbackButtons (Plan 05-06)  →  api.postFeedback({thread_id, message_id, score})
                              ▼
POST /api/feedback (Plan 05-06)  →  parse message_id "{thread_id}-{turn_idx}"
                                  →  seed_trace_id(thread_id, turn_idx)   ← SAME helper
                                  →  langfuse.create_score(trace_id=..., name="user_feedback", value=±1)
                              ▼
Langfuse trace `chat_turn_{thread_id}_{turn_idx}` carries:
  - all LLM/tool spans (CallbackHandler)
  - formula_accuracy Score (auto-eval)
  - user_feedback Score (FE thumbs)
```

## Task Commits

1. **Task 1: Backend POST /api/feedback handler** — feat(05-06): POST /api/feedback handler with deterministic trace_id (API-05, OBS-02)
2. **Task 2: Frontend types + api client + useChatStream approval handling** — feat(05-06): SSEEvent + AgentName + ApprovalPayload + SearchContext types; api.postFeedback wrapper; useChatStream.approve() callback + APPROVAL_REQUIRED action + Pitfall 2 guard
3. **Task 3: Components — ApprovalCard + SearchContextLine + FeedbackButtons swap + MessageList branch + MarkdownAnswer prepend** — feat(05-06): ApprovalCard + SearchContextLine UI per UI-SPEC; FeedbackButtons localStorage→api.postFeedback swap; MessageList awaitingApproval branch; MarkdownAnswer SearchContextLine prepend

**Plan metadata:** _pending docs commit by orchestrator_

_Note: All three tasks staged in the working tree. The executor agent's sandbox blocked git mutations (read-only git status/diff allowed), so the orchestrator will commit the staged work in 3 task-aligned chunks plus the docs commit. See "Issues Encountered" below for full context._

## Files Created/Modified

### New (7)
- `backend/api/routes/feedback.py` — POST /api/feedback handler; `_parse_message_id` regex anchored on trailing `-<digits>`; graceful no-op + 502 on langfuse error
- `backend/tests/test_api_feedback.py` — 6 tests (happy up/down, no-op without keys, malformed message_id, thread mismatch, langfuse error → 502)
- `frontend/components/chat/ApprovalCard.tsx` — yellow-50/yellow-300 gate, neutral-outline buttons, Bangkok Metro copy, "Sending your decision…" caption
- `frontend/components/chat/SearchContextLine.tsx` — gray-50 + blue-200 caption, optional sources details with `target="_blank" rel="noopener noreferrer"`
- `frontend/__tests__/components/ApprovalCard.test.tsx` — 6 tests (heading, breakdown, Approve/Deny callbacks, waiting caption, Bangkok Metro phrasing)
- `frontend/__tests__/components/SearchContextLine.test.tsx` — 6 tests (prefix+summary, null on empty/whitespace summary, sources count, omits sources line when empty, link target/rel attributes)
- `frontend/__tests__/hooks/useChatStream-approval.test.ts` — 4 tests (status flips to awaiting_approval, approve(true) POSTs approve:true and resumes, approve(false) POSTs approve:false, resume failure → status='error')

### Modified (9)
- `backend/api/main.py` — `from backend.api.routes.feedback import router as feedback_router` + `app.include_router(feedback_router)`
- `frontend/types/agent.types.ts` — AgentName += {hitl_gate, search_agent}; new SearchContextSource + SearchContext + ApprovalPayload interfaces; FinalPayload.search_context optional; SSEEvent += approval_required variant
- `frontend/types/api.types.ts` — ChatRequest.message widened to optional; ChatRequest.approve added
- `frontend/lib/api.ts` — FeedbackRequestBody + FeedbackResponse types; api.postFeedback wrapper that POSTs JSON and throws ApiError on non-2xx
- `frontend/hooks/useChatStream.ts` — ChatStatus += 'awaiting_approval'; ChatStreamState.approvalPayload added; APPROVAL_REQUIRED + RESUME_START actions; reducer DONE guard preserves 'awaiting_approval' (Pitfall 2); approve(threadId, decision) callback re-streaming through the same reducer pipeline as send()
- `frontend/components/chat/FeedbackButtons.tsx` — localStorage write swapped for `await api.postFeedback({thread_id, message_id, score})`; failure → `console.error('[feedback]', err)`, button stays voted
- `frontend/components/chat/MarkdownAnswer.tsx` — `MARKET_CONTEXT_LINE_RE` strips the backend-emitted blockquote; `<SearchContextLine>` rendered above the prose when `payload.search_context.summary` is non-empty
- `frontend/components/chat/MessageList.tsx` — ApprovalCard branch on `awaitingApproval` prop populated for the last assistant slot; FeedbackButtons gated on `!slotApproval`; AssistantMessage.payload widened to FinalPayload | null
- `frontend/__tests__/components/FeedbackButtons.test.tsx` — rewrote tests: aria-labels still tested, but the localStorage / `fetch NOT called` assertions replaced with `vi.spyOn(apiMod.api, 'postFeedback')` mock + silent-failure assertion

## Decisions Made

See `key-decisions:` frontmatter list. Notable highlights:
- **Deterministic trace_id from message_id parser**: anchoring on trailing `-<digits>` lets thread_ids contain dashes (UUIDv4) while still extracting the turn_idx unambiguously.
- **Reducer-level Pitfall 2 guard on DONE**: single chokepoint vs forking send()/approve() — adding new ChatStatus values requires updating the reducer; the finally-block stays uniform.
- **MarkdownAnswer strips the backend-emitted blockquote**: response_node also emits a `> **Market context:**` blockquote so non-FE consumers see provenance; the FE strips it and renders the typed component to avoid the dual-render anti-pattern from the RESEARCH doc.
- **AssistantMessage.payload widened to FinalPayload | null**: backward-compatible since existing consumers always pass non-null, but enables the awaiting-approval slot to render ApprovalCard in place of MarkdownAnswer with no payload available yet.

## Deviations from Plan

### Process deviation: executor sandbox blocked git mutations

**1. [Rule 3 — Process / Sandbox] Executor agent could not run `git add` or `git commit`**
- **Found during:** Task 1 wrap-up (attempting to commit backend/api/routes/feedback.py + main.py + test_api_feedback.py)
- **Issue:** The executor agent's bash sandbox allowed read-only git commands (`git status`, `git diff`) but blocked all mutating commands (`git add`, `git commit`, `node gsd-tools.cjs commit ...`) — every retry returned the same "Permission to use Bash has been denied" message. Backend pytest + frontend npm test were also blocked (so pre-commit verification ran via static reads + grep + reasoning instead of test runs).
- **Fix:** Per the parallel_execution wrap-up discipline ("If you hit sandbox restrictions on `git add` for `.planning/` files, complete tasks first then write SUMMARY.md and let the orchestrator commit them — DO NOT skip writing SUMMARY.md"), the executor finished all 3 tasks of code work, wrote this SUMMARY.md and the STATE.md updates inline, and handed off to the orchestrator to commit the work in task-aligned chunks. The same pattern was used by the prior 05-04 stall (per STATE.md decision log) and by 05-01.
- **Files modified:** N/A — all underlying code work is complete and on disk; only the commit-side handoff differs from the strict TDD red/green pairing the plan called for.
- **Verification:** Static checks ran: every acceptance-criterion grep (`@router.post("/api/feedback")`, `name="user_feedback"`, `data_type="NUMERIC"`, `feedback_router` import + include, `'approval_required'` in agent.types.ts, `'hitl_gate'` + `'search_agent'`, `postFeedback` in api.ts, `awaiting_approval` + `APPROVAL_REQUIRED` + `const approve = useCallback` + `approvalPayload` in useChatStream.ts, `Approval required` + `Bangkok Metro` + `border-yellow-300` in ApprovalCard.tsx, `Market context:` + `border-l-2 border-blue-200` + `target="_blank"` + `rel="noopener noreferrer"` in SearchContextLine.tsx, `api.postFeedback` in FeedbackButtons.tsx, `ApprovalCard` in MessageList.tsx, `SearchContextLine` in MarkdownAnswer.tsx) returns hits.

### Auto-fixed issues

**2. [Rule 1 — Bug] FeedbackButtons.test.tsx required full rewrite (NOT just augmentation)**
- **Found during:** Task 3 component test authoring
- **Issue:** Existing `frontend/__tests__/components/FeedbackButtons.test.tsx` (D-17 stub era) explicitly asserted `localStorage[feedback]` was written AND that `globalThis.fetch` was NEVER called ("UI-05 is wire-deferred to Phase 5"). Both assertions are deliberately violated by the Plan 05-06 swap to `api.postFeedback`.
- **Fix:** Rewrote the file to (a) keep the LOCKED aria-label test, (b) replace localStorage assertion with a `vi.spyOn(apiMod.api, 'postFeedback').mockResolvedValue(...)` call check, (c) replace the "no fetch" test with a silent-failure assertion (mockRejectedValue → button stays voted, console.error called), and (d) keep the disabled-after-vote test.
- **Files modified:** frontend/__tests__/components/FeedbackButtons.test.tsx
- **Verification:** Static read confirms 5 `it(...)` blocks covering all expected behaviors (aria-labels, postFeedback called with up, postFeedback called with down, disabled+aria-pressed after vote, silent failure).

**3. [Rule 1 — Bug] useChatStream reducer DONE guard for Pitfall 2**
- **Found during:** Task 2 implementation review (after writing the approve() callback and the APPROVAL_REQUIRED dispatch)
- **Issue:** Phase 4 reducer's DONE handler was `state.status === 'error' ? state : { ...state, status: 'done' }` — when an `approval_required` event arrives, the SSE stream closes naturally (Pitfall 2: no trailing `done`), the finally block in `send()` dispatches DONE unconditionally because `sawError` is false, and the reducer would auto-flip `awaiting_approval` → `done`. That defeats the entire HITL gate UX — Approve/Deny buttons would disappear.
- **Fix:** Extended the reducer DONE guard to also preserve `awaiting_approval`: `if (state.status === 'error' || state.status === 'awaiting_approval') return state`. Single chokepoint vs forking send()/approve() finally-block logic. Documented inline as the Pitfall 2 mitigation.
- **Files modified:** frontend/hooks/useChatStream.ts
- **Verification:** Static check confirms guard is on line 76 and the new test `flips status to awaiting_approval when approval_required event arrives` covers the case.

---

**Total deviations:** 3 (1 process — sandbox blocking commits; 2 auto-fixed — FeedbackButtons test rewrite + reducer Pitfall 2 guard)
**Impact on plan:** Code work matches plan §Task 1/2/3 §action steps verbatim. Process deviation only affects the commit-side handoff (orchestrator commits the work in task-aligned chunks). Auto-fixes #2 and #3 are mechanical test-data and reducer-guard adjustments; both were called out in the plan §read_first guidance / Pitfall 2 explicitly.

## Issues Encountered

- **Sandbox blocked git mutations and test runs**: Could not execute `git add`, `git commit`, `node gsd-tools.cjs commit ...`, `pytest`, or `npm test` from the executor agent. Static verification ran via Read + Grep on every acceptance criterion. Per the wrap-up discipline directive, the executor completed all code, wrote this SUMMARY.md and STATE.md updates, and handed off to the orchestrator. Recommend orchestrator runs `cd backend && .venv/bin/pytest backend/tests/ -q` and `cd frontend && npm test -- --run` once before staging the docs commit to confirm green.

## Acceptance Criteria

Plan §verification items 1-4 verified statically (grep-based since pytest/npm test unavailable):
- ✅ `backend/api/routes/feedback.py` exists; `@router.post("/api/feedback")` on line 44; `name="user_feedback"` on line 80; `data_type="NUMERIC"` on line 82; `from backend.agent.observability import` present.
- ✅ `backend/api/main.py` has `from backend.api.routes.feedback import router as feedback_router` (line 21) + `app.include_router(feedback_router)` (line 58).
- ✅ `backend/tests/test_api_feedback.py` exists with 6 tests matching plan §behavior list (test_feedback_posts_score, test_feedback_score_down_maps_to_negative_one, test_feedback_no_op_without_keys, test_feedback_malformed_message_id_returns_400, test_feedback_thread_mismatch_returns_400, test_feedback_langfuse_error_returns_502).
- ✅ `frontend/types/agent.types.ts`: `'approval_required'` (line 81), `'hitl_gate'` (line 14), `'search_agent'` (line 15), `search_context` (FinalPayload extension line 63).
- ✅ `frontend/lib/api.ts`: `postFeedback` (line 73).
- ✅ `frontend/hooks/useChatStream.ts`: `awaiting_approval` (multiple lines), `APPROVAL_REQUIRED` (lines 40, 82, 183, 262), `const approve = useCallback` (line 215), `approvalPayload` (lines 28, 49, 61, 86, 94).
- ✅ `frontend/__tests__/hooks/useChatStream-approval.test.ts` exists with 4 `it(...)` blocks.
- ✅ `frontend/components/chat/ApprovalCard.tsx` exists, exports ApprovalCard; contains "Approval required", "Bangkok Metro", "border-yellow-300".
- ✅ `frontend/components/chat/SearchContextLine.tsx` exists, exports SearchContextLine; contains "Market context:", "border-l-2 border-blue-200", `target="_blank"`, `rel="noopener noreferrer"`.
- ✅ `frontend/components/chat/FeedbackButtons.tsx` has `api.postFeedback` and 0 `localStorage` references.
- ✅ `frontend/components/chat/MessageList.tsx` imports + uses ApprovalCard.
- ✅ `frontend/components/chat/MarkdownAnswer.tsx` imports + uses SearchContextLine.

Pytest + Vitest runs deferred to orchestrator (sandbox blocked).

## User Setup Required

None — no new external services. Existing LANGFUSE_* env vars (set in Phase 5 Plan 01) drive the feedback path; without them, POST /api/feedback returns 200 with `delivered=false` (graceful no-op).

## Next Phase Readiness

Phase 5 is now ONE plan from complete:
- Plan 05-07 (docs + tag) can proceed — all behavioral plans (01–06) are in.
- The deterministic trace_id contract is fully end-to-end: chat handler attaches CallbackHandler with `seed_trace_id(thread_id, turn_idx)` → pricing_agent posts formula_accuracy on the same trace → POST /api/feedback resolves the same trace_id from message_id and posts user_feedback. All three Score sources collide on the SAME trace by design (no name lookup anywhere).
- Frontend now renders the full Phase 5 UI surface: ApprovalCard for HITL gate, SearchContextLine for search-agent provenance, postFeedback wired for thumbs votes — ready for the manual e2e smoke (per plan §verification §Manual e2e smoke 1-5).

## Self-Check: PASSED

Verified files exist (all listed in `key-files`):
- `backend/api/routes/feedback.py` — FOUND
- `backend/tests/test_api_feedback.py` — FOUND
- `backend/api/main.py` — FOUND (modified, includes feedback_router)
- `frontend/types/agent.types.ts` — FOUND (modified, adds approval_required, hitl_gate, search_agent, SearchContext, ApprovalPayload)
- `frontend/types/api.types.ts` — FOUND (modified, ChatRequest.approve added)
- `frontend/lib/api.ts` — FOUND (modified, postFeedback added)
- `frontend/hooks/useChatStream.ts` — FOUND (modified, awaiting_approval + approvalPayload + approve())
- `frontend/components/chat/ApprovalCard.tsx` — FOUND (new)
- `frontend/components/chat/SearchContextLine.tsx` — FOUND (new)
- `frontend/components/chat/FeedbackButtons.tsx` — FOUND (modified, api.postFeedback)
- `frontend/components/chat/MarkdownAnswer.tsx` — FOUND (modified, prepends SearchContextLine)
- `frontend/components/chat/MessageList.tsx` — FOUND (modified, branches to ApprovalCard)
- `frontend/__tests__/hooks/useChatStream-approval.test.ts` — FOUND (new)
- `frontend/__tests__/components/ApprovalCard.test.tsx` — FOUND (new)
- `frontend/__tests__/components/SearchContextLine.test.tsx` — FOUND (new)
- `frontend/__tests__/components/FeedbackButtons.test.tsx` — FOUND (modified, full rewrite for postFeedback)

Commits: pending — orchestrator will commit (sandbox blocked executor commits, see "Issues Encountered").

---
*Phase: 05-polish-observability-docs*
*Completed: 2026-05-03*
