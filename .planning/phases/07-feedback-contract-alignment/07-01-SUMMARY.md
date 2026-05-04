---
phase: 07-feedback-contract-alignment
plan: 01
subsystem: api
tags: [fastapi, sse, langgraph, langfuse, feedback, contract-alignment, tdd]

# Dependency graph
requires:
  - phase: 05-polish-observability-docs
    provides: "feedback.py regex + thread_id cross-check + seed_trace_id helper (D-16); _make_config + Langfuse CallbackHandler attach (D-14)"
  - phase: 06-hitl-ui-wiring
    provides: "FinalPayload type + ChatApp resume scaffolding"
provides:
  - "Backend stamps message_id = '{thread_id}-{turn_idx}' on every SSE answer payload (fresh + resume) — single source of truth (D-01/D-02)"
  - "GET /api/conversations/:id attaches message_id to LAST assistant per turn; user + non-last in-turn assistants have NO field (D-05/D-06/D-07)"
  - "response_node now persists rendered assistant markdown into state.messages so resume path actually has assistant rows (Rule 2 critical functionality)"
  - "Production-shape UUIDv4 backend feedback test (D-10) — drift prevention against future regex tightening"
affects: [phase-07-02-frontend-wiring, phase-07-03-docs-and-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-source-of-truth message_id stamping at _drain_events answer-yield site (BE never delegates string construction to FE)"
    - "Three-pass turn-derivation helper _attach_message_ids: turn_for / last_assistant_per_turn / stamping"
    - "Append-style state.messages return from response_node (no operator.add reducer; full list returned)"

key-files:
  created: []
  modified:
    - "backend/api/routes/chat.py"
    - "backend/api/routes/conversations.py"
    - "backend/agent/nodes/response_node.py"
    - "backend/tests/test_api_chat.py"
    - "backend/tests/test_api_conversations.py"
    - "backend/tests/test_api_feedback.py"

key-decisions:
  - "_drain_events keyword-only thread_id+turn_idx params: explicit > positional drift risk"
  - "_resume_stream passes cfg_turn (clamped) to preserve Phase 5 D-14 trace continuity across the HITL pause — same trace_id the CallbackHandler attached to during the original turn"
  - "Rule 2: response_node now appends assistant message to state.messages on BOTH happy and deny paths — without this, GET /api/conversations/:id has no assistant rows to stamp and the FE resume path renders zero assistants (degenerate)"
  - "_attach_message_ids stamps ONLY the last assistant per turn (D-07). User and earlier-in-turn assistant rows get no message_id field (silent absence per D-06/D-08)"
  - "feedback.py is NOT modified (LOCKED Phase 5 D-16) — UUIDv4 test exercises the regex anchor-on-trailing-digits behavior end-to-end without regex changes"

patterns-established:
  - "Pattern 1: BE-stamped contract strings (message_id) — FE never reconstructs from parts; eliminates audit Issue 3 drift class"
  - "Pattern 2: Per-turn message_id derivation via 1-user-message-=-1-turn rule mirrors chat.py:_next_turn_idx semantics verbatim"
  - "Pattern 3: Append-style messages return when no operator.add reducer is set — read prior list, append, return full list"

requirements-completed: [API-05, OBS-02, UI-05]

# Metrics
duration: 7min
completed: 2026-05-04
---

# Phase 7 Plan 01: Feedback Contract Alignment (Backend) Summary

**Backend stamps the canonical `message_id = '{thread_id}-{turn_idx}'` on every SSE answer payload AND on the LAST assistant per turn returned by GET /api/conversations/:id, closing audit Issue 3 root cause (cross-phase contract drift between FE id construction and BE feedback regex).**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-04T06:59:55Z
- **Completed:** 2026-05-04T07:06:44Z
- **Tasks:** 3
- **Files modified:** 6 (3 source, 3 test)

## Accomplishments

- `_drain_events` now takes keyword-only `thread_id: str` + `turn_idx: int` and stamps `final_payload["message_id"] = f"{thread_id}-{turn_idx}"` before yielding. Both `_fresh_stream` (uses `turn_idx`) and `_resume_stream` (uses `cfg_turn` to preserve Phase 5 D-14 trace continuity across the HITL pause) updated.
- New `_attach_message_ids` helper in `conversations.py` walks messages and stamps `message_id` on the LAST assistant of each turn. User messages and non-last in-turn assistants get NO `message_id` field (silent absence per D-06).
- `response_node` now persists the rendered assistant markdown into `state.messages` on both happy and deny paths so GET /api/conversations/:id actually has assistant rows to stamp and the FE `handleResume` can replay them.
- +5 backend tests: 2 in `test_api_chat.py` (literal `t-happy-0` + feedback regex round-trip), 2 in `test_api_conversations.py` (last-assistant-stamp + user-rows-have-no-field), 1 in `test_api_feedback.py` (UUIDv4 production-shape happy path).
- 191/191 backend tests green; 9 → 11 in chat suite; 3 → 5 in conversations suite; 6 → 7 in feedback suite.

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend — stamp message_id on _drain_events answer yield (D-01, D-02)** — `38fb77f` (feat)
2. **Task 2: Backend — attach message_id per LAST assistant per turn in GET /api/conversations/:id (D-05, D-06, D-07)** — `b82bc91` (feat)
3. **Task 3: Backend — UUIDv4 production-shape feedback test (D-10)** — `fbe8135` (test)

## Files Created/Modified

- `backend/api/routes/chat.py` — `_drain_events` signature change (keyword-only `thread_id` + `turn_idx`); both `_fresh_stream` and `_resume_stream` updated to pass them through.
- `backend/api/routes/conversations.py` — added `_attach_message_ids` helper; `get_conversation` wraps `messages` through it.
- `backend/agent/nodes/response_node.py` — both happy-path and deny-path branches now append assistant message to `state.messages` (Rule 2 critical functionality fix).
- `backend/tests/test_api_chat.py` — `+test_happy_path_answer_payload_contains_message_id`, `+test_answer_message_id_matches_feedback_regex`.
- `backend/tests/test_api_conversations.py` — `+test_get_conversation_attaches_message_id_to_last_assistant`, `+test_get_conversation_message_id_user_messages_have_no_field`.
- `backend/tests/test_api_feedback.py` — `+test_feedback_uuidv4_thread_id_happy_path`.

## Decisions Made

- `_resume_stream` passes `cfg_turn` (the clamped `max(0, turn_idx - 1)` value), NOT `turn_idx`, into `_drain_events`. This guarantees the message_id matches the same Langfuse trace the CallbackHandler attached to during the original paused turn (Phase 5 D-14). Without the clamp, a thumbs-up on a post-resume answer would land on a different trace than the agent's reasoning trace, breaking OBS-02 attribution.
- `response_node` returns the FULL appended messages list (read prior + append + return) rather than relying on a reducer. `state.messages` has no `operator.add` annotation, so a partial return would overwrite. Append-style preserves all prior turns AND the just-rendered assistant.
- `_attach_message_ids` uses three passes (turn_for / last_assistant_per_turn / stamping) instead of a single pass with bookkeeping. Three small loops are easier to read AND each loop has an obvious O(N) cost; total is still 3N which is the same big-O as the cleverest alternative.
- The new UUIDv4 test asserts the `comment` kwarg landed verbatim from the request `reason` field — proves the body-to-Score field mapping survives across UUIDv4-shaped ids (not just canonical 'abc-0').

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] response_node now persists assistant messages into state.messages**

- **Found during:** Task 2 (RED phase — `test_get_conversation_attaches_message_id_to_last_assistant` failed because the seeded thread had ZERO assistant rows)
- **Issue:** The plan's Task 2 contract states "GET /api/conversations/:id attaches message_id to LAST assistant of each turn." But the existing `response_node` only returned `final_payload` + `reasoning_trace` — it never appended the rendered assistant markdown back into `state.messages`. So a real seeded happy-path turn left `state.messages` with ONLY the user message. The plan's tests cannot pass against this behavior, and (more importantly) the FE `ChatApp.handleResume` code at `frontend/components/ChatApp.tsx:114` iterates `detail.messages` looking for `m.role === 'assistant'` — meaning the entire resume rendering path is degenerate today (the audit's Issue 3 lurks deeper than the message_id format alone).
- **Fix:** Updated `response_node` to append `{"role": "assistant", "content": markdown}` to `state.messages` on BOTH happy-path and deny-path returns. Append-style: read prior list, append, return full list (state.messages has no `operator.add` reducer).
- **Files modified:** `backend/agent/nodes/response_node.py`
- **Verification:** All 14 existing `test_response_node.py` tests still pass (they use `_ok_state()` with `messages=[]` and never assert on the returned `messages` shape). Plan 07-01 tests `test_get_conversation_attaches_message_id_to_last_assistant` and `test_get_conversation_message_id_user_messages_have_no_field` go GREEN. Full backend suite: 191/191.
- **Committed in:** `b82bc91` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality — Rule 2)
**Impact on plan:** Without the deviation the plan's Task 2 contract was unmeetable. The fix is the minimal required change and unlocks the FE resume path that Plan 07-02 will wire end-to-end. No scope creep — the new behavior is exactly what the plan's contract implicitly requires.

## Auth Gates

None — no external service authentication exercised in this plan (Langfuse seam is mocked in all tests).

## Issues Encountered

- The seeded-thread fixture in `test_api_conversations.py` produced empty assistant rows on first run, surfaced via the RED-phase failure in Task 2. Resolved by Rule 2 deviation above (response_node now persists assistants).

## Locked Contracts (Untouched)

Per Phase 7 D-16 / D-14 invariants, the following files/functions were NOT modified:

- `backend/api/routes/feedback.py` — `_TURN_RE` regex `^(.+)-(\d+)$`, `_parse_message_id`, thread_id cross-check, `create_score(name="user_feedback", value=±1)` call
- `backend/agent/observability.py` — `seed_trace_id`, `get_callback_handler`, `get_langfuse_client`
- `backend/api/models.py::FeedbackRequest` — Pydantic shape unchanged
- `_make_config` / `_next_turn_idx` / `_NODE_NAMES` / SSE event envelope shape (Phase 7 only augments the answer-yield site)

## Next Phase Readiness

- **Plan 07-02 (frontend wiring) is unblocked:** the BE answer payload now carries `message_id`, GET /api/conversations/:id messages carry `message_id` on canonical assistant rows, and (via the Rule 2 deviation) the resume path actually has assistant rows to render. Plan 07-02 can confidently:
  - Extend `FinalPayload` with `message_id: string` (REQUIRED, per D-04).
  - Replace the broken `` `a-${Date.now()}` `` construction in ChatApp with `payload.message_id`.
  - Replace the broken `` `replay-${i}` `` construction in `handleResume` with `m.message_id`.
  - Add the Vitest+MSW round-trip test (D-09) and the resume-path test (D-11).
- **Plan 07-03 (docs + manual smoke):** the BE half of audit Issue 3 is closed. Plan 07-03 codifies the 6-step Langfuse manual smoke (D-13/D-14) and captures the `langfuse-feedback-score.png` screenshot (D-15/D-16).

## Self-Check: PASSED

- All 6 modified files present
- All 3 task commits present in git log (38fb77f, b82bc91, fbe8135)
- 191/191 backend tests green
- All acceptance criteria literal-string checks passed via Grep verification
- LOCKED contracts (feedback.py, observability.py, models.py::FeedbackRequest) untouched

---
*Phase: 07-feedback-contract-alignment*
*Completed: 2026-05-04*
