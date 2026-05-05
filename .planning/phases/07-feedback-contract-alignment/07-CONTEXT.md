# Phase 7: Feedback Contract Alignment - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Make production thumbs-up/down clicks succeed end-to-end and land a `user_feedback` Score in Langfuse Cloud, by aligning the frontend assistant `message_id` construction with the backend `{thread_id}-{turn_idx}` contract that Phase 5 D-16 shipped. Closes audit Issue 3 (`v1.0-MILESTONE-AUDIT.md` §2.2). Flips API-05, OBS-02, UI-05 from `partial` to `satisfied`.

**In scope (this phase):**
- Backend: SSE `answer` event payload extended with `message_id: '{thread_id}-{turn_idx}'` (inside FinalPayload).
- Backend: `GET /api/conversations/:id` response extended so each LAST assistant message of a turn carries `message_id`.
- Frontend: ChatApp consumes `payload.message_id` for the live append path AND `m.message_id` for the resume replay path. Replaces the broken `a-${Date.now()}` and `replay-${i}` constructions.
- Frontend: `FinalPayload.message_id: string` (required); `ChatMessage` type / `replayed messages` type carry it through.
- Drift-prevention tests: Vitest+MSW round-trip in ChatApp for live + resume; one UUIDv4-shaped happy-path test added to `test_api_feedback.py`.
- Documentation: live verification protocol (steps + screenshot artifact) appended to `docs/data-sources.md`; one HUMAN-only checkpoint in the plan (autonomous: false) for IT lead to run with real Langfuse keys during W5.

**Explicitly out of scope (deferred to Phase 8 / v2):**
- TOOL-05 / UI-02 `search_context` omission from `final_payload` + dead `'search_only'` FinalStatus branch — Phase 8 owns this (audit Issue 6).
- UI-06 conversation sidebar refresh after a completed turn — Phase 8 owns this (audit Issue 4).
- Any changes to backend `feedback.py` regex, Pydantic `FeedbackRequest` shape, or thread_id consistency check (locked Phase 5 D-16; audit confirmed correct).
- Any changes to `seed_trace_id` / `_make_config` / Langfuse trace name `chat_turn_{thread_id}_{turn_idx}` (locked Phase 5 D-14 — load-bearing constant).
- AgentState schema change to persist message_id alongside each message (avoided in favor of read-time inference).
- Migration of old localStorage feedback entries from Phase 4 D-17 (the new wire is per-click POST; no backfill needed).
- Toast/snackbar error UI on feedback POST failure (Phase 5 D-16 silent-failure pattern stays).
- ChatApp.tsx HITL placeholder pending-id `pending-${Date.now()}` (Phase 6 D-06 strip-and-replace already prevents persistence — verified at [frontend/components/ChatApp.tsx:42-55](frontend/components/ChatApp.tsx#L42-L55)).

</domain>

<decisions>
## Implementation Decisions

### Live answer path: turn_idx delivery to FE (Issue 3 — root cause)
- **D-01:** Backend stamps `message_id: '{thread_id}-{turn_idx}'` on the SSE `answer` event (NOT on `meta`). The answer event is the moment the assistant message becomes "real"; carrying the id with the payload eliminates any need for FE to hold turn_idx in component state until `done`. Site: [backend/api/routes/chat.py:149-150](backend/api/routes/chat.py#L149-L150) inside `_drain_events` where `output["final_payload"]` is yielded — augment the dict before yield.
- **D-02:** Backend sends the FULL message_id pre-built (NOT just `turn_idx` for FE concatenation). Single source of truth: if the contract format ever changes (separator, prefix, etc.), only one place updates. FE template literal `${threadId}-${turnIdx}` is exactly the duplication the audit's Issue 3 was caused by.
- **D-03:** `message_id` lives INSIDE `FinalPayload` (NOT at the answer event envelope level). The type already widened to `FinalPayload | null` in Plan 05-06 — adding one more required field follows the same path. ChatApp's existing `useEffect` on `chat.finalPayload` reads `payload.message_id` directly when constructing the assistant `ChatMessage`. Touches: [frontend/types/agent.types.ts:58](frontend/types/agent.types.ts#L58) (FinalPayload), [frontend/components/ChatApp.tsx:60](frontend/components/ChatApp.tsx#L60) (replace `a-${Date.now()}`).
- **D-04:** `message_id` is REQUIRED (always present) on every emitted answer payload — `FinalPayload.message_id: string` (NOT `string | undefined`). Backend invariant: every `_drain_events` answer yield must include it; backend tests assert presence. Rationale: optional with FE fallback IS the silent-degradation bug class the audit flagged. Any test that mocks an answer payload now MUST include message_id (drift-prevention requires this anyway).

### Resume path: id reconstruction for past conversations
- **D-05:** Backend returns `message_id` per qualifying assistant message in the `GET /api/conversations/:id` response. Site: [backend/api/routes/conversations.py:112-120](backend/api/routes/conversations.py#L112-L120) — augment the messages list before return. FE `ChatApp.handleResume` ([frontend/components/ChatApp.tsx:114-126](frontend/components/ChatApp.tsx#L114-L126)) reads `m.message_id` and replaces the broken `replay-${i}` construction.
- **D-06:** Per-message field on each assistant row (NOT a parallel `message_ids[]` array, NOT a top-level `next_turn_idx` hint). Shape: `{role: 'assistant', content: '...', message_id: 'abc-0'}`. User messages get NO `message_id` field (no feedback affordance on user turns; field absence is the natural signal). Index-aligned arrays are fragile to filtering; `next_turn_idx` hint forces FE to mirror BE's `_next_turn_idx` semantics — exact drift class the audit flagged.
- **D-07:** turn_idx rule for replayed assistant messages: **1 turn = 1 user message**. Walk the messages list; turn_idx for an assistant message at position N = count of `role==user` messages at positions `[0..N]` (matches existing `_next_turn_idx` semantics verbatim — [backend/api/routes/chat.py:111-127](backend/api/routes/chat.py#L111-L127)). HITL approve+deny resume that produces multiple assistant messages in a single turn (e.g., a pre-pause partial then a post-resume final) shares the same turn_idx — feedback attaches to the same Langfuse trace, which is correct. ONLY the LAST assistant message of each turn carries `message_id`; earlier in-turn assistant rows get no `message_id` field (silent absence → no FeedbackButtons via D-08).
- **D-08:** FeedbackButtons render gate: only on the LAST assistant message of each turn (i.e., assistant rows with a non-null `message_id`). Reuses the existing `isLast` gating pattern in [frontend/components/chat/MessageList.tsx](frontend/components/chat/MessageList.tsx). Live path: the appended `done`-payload assistant is always the last → always shows buttons. Resume path: only the last assistant per turn (which is the only one with `message_id`) → buttons render. Earlier in-turn assistant rows (HITL pre-pause partials, if any persist in checkpointer messages) get no buttons.

### Drift-prevention test surface (audit lesson)
- **D-09:** PRIMARY surface = Vitest+MSW round-trip integration test in ChatApp. Mocks `POST /api/chat` to emit a full SSE stream including an `answer` event whose payload contains `message_id`. Mounts ChatApp, sends a query, sees the assistant message render, clicks the thumbs-up button, asserts that `POST /api/feedback` fires with body `{thread_id, message_id, score: 'up'}` whose `message_id` parses cleanly through the backend regex `^(.+)-(\d+)$` AND whose extracted `thread_id` equals `body.thread_id`. Catches FE id construction + payload threading + click handler + URL all in one test — the exact wiring path that broke. Lives at `frontend/components/__tests__/ChatApp.feedback.integration.test.tsx` (planner picks: extend existing `ChatApp.integration.test.tsx` from Phase 6 OR create sibling file — both fit).
- **D-10:** SECONDARY surface = ONE production-shape backend test in [backend/tests/test_api_feedback.py](backend/tests/test_api_feedback.py). POST with UUIDv4 thread_id (e.g., `'a4b27c8e-d4f1-4ddd-aaaa-1234567890ab'`) and integer turn_idx (e.g., `3`) → message_id `'a4b27c8e-d4f1-4ddd-aaaa-1234567890ab-3'`. Asserts 200 and that the parsed `(thread_id, turn_idx)` tuple matches input. Catches any future BE-side regex tightening that would reject UUIDv4 — production-shape coverage at near-zero cost. Belt-and-braces with D-09.
- **D-11:** RESUME PATH surface = dedicated Vitest+MSW test that mocks `GET /api/conversations/:id` with messages carrying `message_id` on the last assistant of each turn, mounts ChatApp, triggers `handleResume`, clicks thumbs-up on a replayed assistant message, asserts `POST /api/feedback` fires with the same `message_id` the BE returned. Lives alongside D-09 file. Without this, only the live path is verified — same bug class could recur on the resume rendering path.
- **D-12:** Existing `test_feedback_thread_mismatch_returns_400` and `test_feedback_malformed_message_id_returns_400` stay untouched — adding UUIDv4 variants of these adds zero coverage; the regex/mismatch behavior is already proven. YAGNI.

### Live verification protocol (success criterion 4)
- **D-13:** Documented manual smoke test. NOT an automated test gated on env keys (slow, flaky against real cloud APIs, free-tier quota pollution); NOT a curl-only recipe (bypasses the FE click path that the audit broke). The smoke test exercises the same path a real user would: backend with `LANGFUSE_*` keys → frontend → query → click → Langfuse dashboard.
- **D-14:** Verification doc location: append a `## Live Verification (Langfuse Feedback)` section to the bottom of [docs/data-sources.md](docs/data-sources.md) (created in Phase 5 D-19). One less file to track; data-sources.md already documents Langfuse as an external service. Numbered checklist of 6 steps: (1) ensure backend `.env` has `LANGFUSE_*` keys + restart uvicorn (per Quick 260503-rs8 note: server holds old `_make_config` in memory until restart), (2) start frontend, (3) ask one surcharge query, (4) click thumbs-up on the answer, (5) open `https://cloud.langfuse.com` → Observations → filter on trace name `express-surcharge-agent`, (6) confirm a `user_feedback` Score row with value=1 appears on the matching `chat_turn_{thread_id}_{turn_idx}` trace.
- **D-15:** Add a screenshot artifact: extend Phase 5 D-20 screenshot list from 5 → 6 PNGs OR enrich the existing `langfuse-trace.png` placeholder to include the Score row (planner picks; 6 PNGs is cleaner). New filename suggestion: `docs/screenshots/langfuse-feedback-score.png`. README references it from the Langfuse mention. The filename is added to `docs/screenshots/.gitkeep` planning so the directory is tracked even before the human capture lands.
- **D-16:** Live verification = HUMAN checkpoint in the plan (autonomous: false). Matches Phase 5 D-20 / Plan 05-07 Task 4 pattern. The plan codifies the exact 6 steps; IT lead runs them once with real keys during W5 code freeze; screenshot capture lands alongside the 5 Phase 5 PNGs. Plan does NOT mark the phase complete until this checkpoint is ticked.

### Folded Todos
[None — `gsd-tools todo match-phase 7` returned 0 matches.]

### Claude's Discretion
- Exact field ordering of `message_id` inside `FinalPayload` (alongside `markdown` vs at the bottom alongside `surcharge_result`).
- Whether to extract a single FE id-builder utility (`buildAssistantMessageId(threadId, turnIdx)`) for the test files to reuse, vs inline string template (single-use today).
- Whether to add `message_id` on user messages too (probably absent — only assistant rows need it for feedback; user-message ids are not in scope for any v1 requirement).
- Whether to extend the existing `langfuse-trace.png` placeholder OR add a new `langfuse-feedback-score.png` (D-15) — both work; visibility favors a separate screenshot.
- Plan ordering and Wave assignment — likely two plans (Wave 1: backend contract change in chat.py + conversations.py + answer-event payload + 1 BE test; Wave 2: FE FinalPayload extension + ChatApp wiring + ChatMessage type + 2 FE Vitest+MSW tests; doc update can be in either wave) but planner has full discretion. A single-plan path is also defensible given the small surface.
- Exact Vitest+MSW handler shape for the round-trip tests (extend existing `ChatApp.integration.test.tsx` MSW handlers vs new file with sibling handlers).
- Whether the BE answer-event `_drain_events` augmentation happens at the `_drain_events` yield site (single source of truth for both fresh + resume streams) vs at the per-route format_sse call site (two sites = small drift risk; planner picks).
- Whether the planner explicitly leaves the HITL placeholder `pending-${Date.now()}` id alone (Phase 6 D-06 strip-and-replace already verified) or migrates it to a `pending-${threadId}-${turnIdx}` shape for consistency. Strip-and-replace makes this irrelevant; planner can confirm and move on.
- Whether to update the Phase 5 D-20 screenshot list documentation to reflect 6 instead of 5, or just append.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit (THE driver for this phase)
- `.planning/v1.0-MILESTONE-AUDIT.md` — §2.2 Issue 3 (FE `a-${Date.now()}` vs BE `^(.+)-(\d+)$` contract mismatch + thread_id cross-check); §3 Flow row for OBS-02 (no `user_feedback` Score will ever land); §4.1 partial-status matrix (API-05, OBS-02, UI-05 → satisfied); §7 file paths at the centre of the gaps; §8 recommended next step.

### Phase inputs from earlier phases
- `.planning/phases/05-polish-observability-docs/05-CONTEXT.md` — load-bearing locked decisions:
  - **D-14** Langfuse trace name `chat_turn_{thread_id}_{turn_idx}` is the source of truth for `seed_trace_id`. Phase 7 must NOT change this convention.
  - **D-16** Feedback wire shape `{thread_id, message_id, score, reason?}` and `seed_trace_id(thread_id, turn_idx)` resolution. Phase 7 fixes the FE side of this contract; the BE side is locked.
- `.planning/phases/06-hitl-approval-ui-wiring/06-CONTEXT.md` — Phase 6 locked decisions Phase 7 inherits:
  - **D-06** Pending-assistant placeholder slot uses `pending-${Date.now()}` and is stripped on `done` BEFORE persistence. Phase 7 message_id contract therefore only applies to FINAL assistant messages, not the placeholder.
  - **D-12** Phase 6 explicitly deferred message_id contract drift to Phase 7. Phase 7 owns it; Phase 6 does NOT.
- `.planning/phases/04-frontend-reasoning-trace/04-CONTEXT.md` — Phase 4 locked decisions:
  - **D-17** FeedbackButtons localStorage stub anticipated the swap to `api.postFeedback` — payload shape `{thread_id, message_id, score, reason?}` is the contract Phase 5 D-16 implemented and Phase 7 honours.
- `.planning/phases/03-graph-assembly-api-layer/03-CONTEXT.md` — Phase 3 locked decisions:
  - **D-15** AsyncSqliteSaver checkpointer — required for `_next_turn_idx` to read prior user-message count.
  - **D-17 / D-18 / D-19** SSE event granularity, typed envelope, thread_id flow + first `meta` event. Phase 7 extends `answer` event payload (NOT a new event type).

### Implementation source files (Phase 7 modifies)
- [backend/api/routes/chat.py:149-150](backend/api/routes/chat.py#L149-L150) — `_drain_events` yields the answer payload; augment with `message_id` (D-01). Construction: `final_payload['message_id'] = f'{thread_id}-{turn_idx}'` — read `turn_idx` from the closure that already exists for `_make_config`.
- [backend/api/routes/conversations.py:89-120](backend/api/routes/conversations.py#L89-L120) — `get_conversation` response; walk messages list, attach `message_id` to the LAST assistant of each turn per D-07 (1 user msg = 1 turn).
- [backend/api/models.py:79-94](backend/api/models.py#L79-L94) — `FeedbackRequest` is locked; reference only.
- [backend/api/routes/feedback.py:25-62](backend/api/routes/feedback.py#L25-L62) — regex + thread_id check is locked; reference only.
- [backend/agent/observability.py:60-76](backend/agent/observability.py#L60-L76) — `seed_trace_id(thread_id, turn_idx)` is the resolver; Phase 7 doesn't touch.
- [frontend/types/agent.types.ts:58](frontend/types/agent.types.ts#L58) — `FinalPayload`; add required `message_id: string` field (D-04).
- [frontend/components/ChatApp.tsx:60](frontend/components/ChatApp.tsx#L60) — replace `id: 'a-${Date.now()}'` with `id: chat.finalPayload.message_id`. Drop the `${Date.now()}` clock dependency.
- [frontend/components/ChatApp.tsx:114-126](frontend/components/ChatApp.tsx#L114-L126) — `handleResume` map function; replace `id: 'replay-${i}'` with `id: m.message_id` for assistant rows; gate FeedbackButtons via D-08 (assistant rows without `message_id` get no buttons).
- [frontend/components/chat/MessageList.tsx](frontend/components/chat/MessageList.tsx) — confirm `isLast` gating still works post-D-08 (it does — only the last assistant rendered with a non-null `message_id` shows buttons).
- [frontend/hooks/useChatStream.ts:172-173](frontend/hooks/useChatStream.ts#L172-L173) — `case 'answer'` reducer dispatches `payload` directly into `finalPayload`; the new `message_id` field travels through transparently. No reducer change needed if `FinalPayload` shape just gains a field.
- [frontend/components/chat/FeedbackButtons.tsx:19](frontend/components/chat/FeedbackButtons.tsx#L19) — consumer; props shape unchanged (`{threadId, messageId}`); only the value of `messageId` flowing in changes.

### Test files
- [backend/tests/test_api_feedback.py](backend/tests/test_api_feedback.py) — add UUIDv4 happy-path test per D-10.
- [backend/tests/test_api_chat.py](backend/tests/test_api_chat.py) — extend at least one answer-event assertion to verify `message_id` is in the final_payload payload (so a future answer-event refactor can't silently drop the field).
- `backend/tests/test_api_conversations.py` (existing or new) — assert per-message `message_id` on the LAST assistant of each turn in `GET /api/conversations/:id` response per D-07.
- `frontend/components/__tests__/ChatApp.feedback.integration.test.tsx` (NEW or extension of `ChatApp.integration.test.tsx`) — Vitest+MSW round-trip per D-09 + resume path per D-11.

### Documentation
- [docs/data-sources.md](docs/data-sources.md) — append `## Live Verification (Langfuse Feedback)` section per D-14 with the 6-step checklist.
- [docs/screenshots/.gitkeep](docs/screenshots/.gitkeep) — add 6th screenshot filename `langfuse-feedback-score.png` to the planning list per D-15.
- [README.md](README.md) — reference the new screenshot from the existing Langfuse section if present (planner verifies the README's Phase 5 langfuse-trace.png reference and updates accordingly).

### Requirements & project framing
- `.planning/REQUIREMENTS.md` — Phase 7 scope: API-05 (active → satisfied), OBS-02 (active → satisfied), UI-05 (active → satisfied).
- `.planning/PROJECT.md` — local-reproducibility constraint (Langfuse no-op when keys missing must stay), 35% Agent Architecture rubric (visible reasoning + observability is the demo lever), Bangkok Metro phrasing (no user-facing copy in Phase 7 changes — verification doc is internal).
- `.planning/ROADMAP.md` §Phase 7 — four success criteria (FE id matches BE regex; POST 200 from real click; production-shape BE tests; live `user_feedback` Score in Langfuse).

### Coding conventions
- `.planning/codebase/CONVENTIONS.md` §Python — PEP 8, Black, Google-style docstrings, `from __future__ import annotations`, TypedDict + Pydantic patterns; §TypeScript — PascalCase.tsx components, useX.ts hooks, camelCase.ts utilities, `*.types.ts`.
- `.planning/codebase/STRUCTURE.md` — `backend/api/routes/`, `frontend/components/`, `frontend/types/`, `frontend/hooks/` — Phase 7 stays inside these.
- `.planning/codebase/TESTING.md` — Vitest + MSW patterns established in Phase 4 (Plan 04-01) and reused in Phase 6 (Plan 06-03 ChatApp.integration.test.tsx) — Phase 7 reuses verbatim.

### Quick task references
- `.planning/quick/260503-rs8/` — `langchain==0.3.28` pin + constant `langfuse_trace_name='express-surcharge-agent'`. Phase 7 verification doc (D-14) must mention the uvicorn restart requirement (server holds old `_make_config` in memory until recycled).
- `.planning/quick/260503-s2h/` — top-level `RunnableConfig.run_name='express-surcharge-agent'` populates Langfuse Observations 'Name' column. Phase 7 verification doc (D-14) instructs filtering on this trace name when locating the Score.

### Backlog
- `.planning/ROADMAP.md` §Backlog 999.2 — "Bangkok Metro" phrasing convention. The new verification doc copy in `docs/data-sources.md` must use Bangkok Metro phrasing if it ever references the scope (it likely does not — the steps are observability-focused, not domain-focused).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/api/routes/feedback.py` — contract is locked and audit-confirmed correct. Phase 7 changes nothing here.
- `backend/agent/observability.py::seed_trace_id` — deterministic resolver from `(thread_id, turn_idx)` to `trace_id`. Phase 7 doesn't touch; the contract Phase 7 fixes is the FE side that produces the inputs to this resolver.
- `backend/api/routes/chat.py::_next_turn_idx` ([lines 111-127](backend/api/routes/chat.py#L111-L127)) — the SAME counting rule Phase 7 D-07 reuses for the resume-path `message_id` reconstruction. Single source of truth for "what is turn_idx?". Conversations.py walks messages and applies the same rule.
- `backend/api/routes/chat.py::_drain_events` ([lines 130-150](backend/api/routes/chat.py#L130-L150)) — Phase 3 / Phase 5 helper centralizing fresh + resume astream_events filter logic. Phase 7 augments the answer-yield site once → both fresh and resume answer payloads gain `message_id` for free.
- `backend/api/routes/chat.py::_make_config` ([lines 63-110](backend/api/routes/chat.py#L63-L110)) — already builds the `(thread_id, turn_idx)` tuple Phase 7 needs. The closure that calls `_make_config` also has `turn_idx` in scope; thread it into `_drain_events` (or read from `config["metadata"]["langfuse_trace_id"]` derivation site if cleaner).
- `frontend/types/agent.types.ts::FinalPayload` — already widened to nullable in Plan 05-06; adding one required field follows the same pattern.
- `frontend/components/ChatApp.tsx::useEffect` for `chat.finalPayload` ([lines 36-66](frontend/components/ChatApp.tsx#L36-L66)) — the assistant-message append path. Phase 7 changes ONE line (`id:`).
- `frontend/components/ChatApp.tsx::handleResume` ([lines 107-136](frontend/components/ChatApp.tsx#L107-L136)) — the replayed-message map. Phase 7 changes ONE line per message (`id:`) and adds null-handling for assistant rows without `message_id` (no FeedbackButtons).
- `frontend/hooks/useChatStream.ts::case 'answer'` ([lines 172-173](frontend/hooks/useChatStream.ts#L172-L173)) — dispatches the answer payload into reducer; the new `message_id` field travels through transparently.
- `frontend/components/chat/FeedbackButtons.tsx` — consumer; props `{threadId, messageId}` unchanged. Only the value flowing into `messageId` changes.
- Phase 6 `ChatApp.integration.test.tsx` (Plan 06-03) — full MSW SSE harness; Phase 7 extends this OR creates a sibling `ChatApp.feedback.integration.test.tsx` reusing the same MSW pattern. The `installPauseThenResumeHandler` call-counter pattern from 06-03 is the reference for any multi-call mocking.
- Phase 4 / 5 backend test fixture pattern (`monkeypatch.setattr(fb_mod, "get_langfuse_client", ...)`) in `test_api_feedback.py` — Phase 7 reuses verbatim for the UUIDv4 add-on.

### Established Patterns
- **Single source of truth for shared contracts** (audit's lesson) — Phase 7 D-01/D-02 send the FULL message_id from BE; FE never constructs the string from parts. Same pattern Phase 5 D-14 applied to the Langfuse trace name.
- **Per-route helper centralization** — `_drain_events` (Phase 3 / 5) and `_make_config` (Phase 5) already centralize fresh + resume logic. Phase 7's BE change augments at these single sites.
- **Optional field for "no feedback affordance"** — message_id absence on user rows AND on non-last assistant rows = no FeedbackButtons. Mirrors Phase 4 D-17's `messageId` prop being a positional contract on the consumer.
- **Vitest+MSW round-trip for cross-phase contracts** — Phase 6 Plan 06-03 D-15.3 established this pattern for the HITL approve+deny flow. Phase 7 D-09 + D-11 extend the same harness to feedback POST.
- **`isLast` gating in MessageList** (Phase 4 / 6) — already used to gate FeedbackButtons and ApprovalCard slots. Phase 7 D-08 reuses; for the resume path, "isLast within turn" maps to "has message_id" (BE's responsibility).
- **HUMAN checkpoint with screenshot artifact** (Phase 5 D-20 / Plan 05-07 Task 4) — Phase 7 D-15 + D-16 follow the same pattern for the live verification screenshot.

### Integration Points
- `backend/api/routes/chat.py::_drain_events` — single answer-yield augmentation (D-01). Both fresh and resume answer payloads gain `message_id` from one change.
- `backend/api/routes/conversations.py::get_conversation` — walk messages list and attach `message_id` to the LAST assistant of each turn per D-07. Touches the response-construction block at [lines 112-120](backend/api/routes/conversations.py#L112-L120).
- `frontend/types/agent.types.ts::FinalPayload` — add required `message_id: string`.
- Frontend `ChatMessage.assistant` row type (in `frontend/components/chat/MessageList.tsx` or wherever it's declared) — confirm `id` is already typed; planner verifies the existing type already accepts the new shape.
- `frontend/components/ChatApp.tsx` — two one-line changes (live append D-03, resume map D-05) plus FeedbackButtons gating verification (D-08).
- `backend/tests/test_api_feedback.py` — append UUIDv4 happy-path test (D-10).
- `backend/tests/test_api_chat.py` — answer-event message_id presence assertion.
- `backend/tests/test_api_conversations.py` (existing or new) — per-message message_id assertion.
- `frontend/components/__tests__/ChatApp.feedback.integration.test.tsx` (or extension of `ChatApp.integration.test.tsx`) — D-09 + D-11.
- `docs/data-sources.md` — append verification section (D-14).
- `docs/screenshots/.gitkeep` — add `langfuse-feedback-score.png` to planning list (D-15).

</code_context>

<specifics>
## Specific Ideas

- **The audit's lesson is wider than this phase.** The bug class — two ends of a contract constructing the same string from parts — is exactly what Phase 7 D-01/D-02/D-05 prevents going forward by centralizing message_id construction on the backend. The Vitest+MSW round-trip test (D-09) is the alarm if this regresses; the UUIDv4 BE test (D-10) is the alarm if the BE ever tightens its regex.
- **Langfuse trace name `chat_turn_{thread_id}_{turn_idx}` is load-bearing.** Phase 5 D-14 documented this; Quick 260503-rs8 + 260503-s2h confirmed both `langfuse_trace_name` (metadata) and `RunnableConfig.run_name` (root span) carry the same constant `'express-surcharge-agent'` so the dashboard filters by one name. Phase 7 verification doc (D-14) must instruct filtering on this name when locating the Score.
- **Uvicorn restart is required after deploying Phase 7 BE changes** (per Quick 260503-rs8 note). The verification doc must mention this — running server holds old `_drain_events` and `_make_config` closures in memory; pytest exercises a fresh import each run, so the test suite covers the new contract without restart, but live `/api/chat` traffic does not pick up the message_id field until uvicorn is recycled.
- **Replayed-message feedback is the user-visible improvement.** Today (after Phase 7 ships) a user opening a past conversation and clicking thumbs-up on an old answer will land a Score on the right Langfuse trace — that didn't work pre-Phase-7 (the `replay-${i}` shape was equally broken). Worth highlighting in the demo recording (Phase 5 D-20) and the verification doc (D-14).
- **No backwards-compatibility hacks.** Per CLAUDE.md, "Don't use feature flags or backwards-compatibility shims when you can just change the code." Phase 7 makes `message_id` REQUIRED on FinalPayload (D-04); old answer payloads from in-memory localStorage state during a hot-reload won't have it but a fresh page load reconstructs from `/api/chat` SSE which has it. No migration required.
- **Phase 6 D-06 placeholder pending-id is non-issue for Phase 7.** The strip-and-replace path at [ChatApp.tsx:42-55](frontend/components/ChatApp.tsx#L42-L55) removes the placeholder before the real assistant message is appended on `done`. The placeholder id never persists into history; only the FINAL assistant message id needs the contract shape. Confirmed in code via the `pendingApprovalSlotRef` guard.
- **Backend test count delta.** Phase 7 adds: 1 BE feedback UUIDv4 test (D-10) + 1 BE chat answer-event message_id assertion (D-09 sibling) + at least 1 BE conversations.py per-message message_id test (D-07/D-11 sibling) + 2 FE Vitest+MSW tests (D-09 + D-11). Net delta: +5 tests. None subtracted.
- **No new SSE event type.** Phase 7 EXTENDS the existing `answer` event payload (D-03) rather than introducing a 7th event type. Keeps the SSE event union (`meta|trace|answer|error|done|approval_required`) stable.

</specifics>

<deferred>
## Deferred Ideas

- **Toast/snackbar global error UI on feedback POST failure** — Phase 5 D-16 silent-failure pattern stays; v2 if a real workflow ever needs visible feedback failure UX.
- **Backfill story for old localStorage feedback entries** (Phase 4 D-17 array shape) — out of scope; the new wire is per-click POST and there's no migration story for older entries. v2 if anyone ever needs cross-session feedback persistence.
- **Read-side Langfuse Score API verification** — would let us automate live verification with pytest.mark.skipif on missing keys. Deferred per D-13 (free-tier quota concerns + flakiness against real cloud APIs).
- **Migration of pending-${Date.now()} placeholder id** to a `pending-${threadId}-${turnIdx}` shape — strip-and-replace already prevents persistence; no contract concern. Not required.
- **AgentState schema change to persist message_id alongside each message** — avoided in favor of read-time inference per D-07 (smaller blast radius for a gap-closure phase). v2 if backfill of past conversations ever becomes a problem.
- **User-message message_ids** — explicitly absent in D-06; user rows have no feedback affordance, so no need. v2 if a feature ever needs them (e.g., per-message editing or referencing).
- **Phase 8 (search_context wiring + sidebar refresh)** — explicitly deferred per ROADMAP §Phase 8. Audit Issues 4 + 6.
- **Tightening backend regex** to enforce UUIDv4 thread_id — explicitly NOT done; current regex `^(.+)-(\d+)$` accepts any non-empty thread_id with a trailing `-<digits>` suffix. Tightening would break the existing `'abc-0'` canonical test fixtures and adds zero security/correctness value.
- **FinalPayload optional fallback for message_id** — explicitly rejected per D-04 (silent degradation IS the audit's bug class).
- **Top-level message_id on the SSE answer event envelope** — rejected per D-03 (forces a new envelope shape; FinalPayload is the natural home).
- **Backend hint `next_turn_idx` for resume** — rejected per D-06 (forces FE to mirror BE's `_next_turn_idx` semantics; same drift class).
- **FE-counted turn_idx** — rejected per D-04 + D-06 (silent drift on resume path; exactly the audit's bug class).
- **Combine documented smoke + curl recipe** — one form is sufficient (D-13 picks documented smoke); curl recipe is a v2 addition if a non-FE grader ever needs it.

### Reviewed Todos (not folded)
None — `gsd-tools todo match-phase 7` returned 0 matches.

</deferred>

---

*Phase: 07-feedback-contract-alignment*
*Context gathered: 2026-05-04*
