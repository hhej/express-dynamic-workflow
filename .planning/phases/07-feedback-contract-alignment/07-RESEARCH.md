# Phase 7: Feedback Contract Alignment - Research

**Researched:** 2026-05-04
**Domain:** Cross-phase contract drift between FE assistant `message_id` construction and BE `^(.+)-(\d+)$` regex + Langfuse Score attachment
**Confidence:** HIGH (every load-bearing claim verified against the live source files; CONTEXT.md is fully locked and the audit document independently corroborates the bug)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Live answer path: turn_idx delivery to FE (Issue 3 — root cause)**
- **D-01:** Backend stamps `message_id: '{thread_id}-{turn_idx}'` on the SSE `answer` event (NOT on `meta`). The answer event is the moment the assistant message becomes "real"; carrying the id with the payload eliminates any need for FE to hold turn_idx in component state until `done`. Site: `backend/api/routes/chat.py:149-150` inside `_drain_events` where `output["final_payload"]` is yielded — augment the dict before yield.
- **D-02:** Backend sends the FULL message_id pre-built (NOT just `turn_idx` for FE concatenation). Single source of truth: if the contract format ever changes (separator, prefix, etc.), only one place updates. FE template literal `${threadId}-${turnIdx}` is exactly the duplication the audit's Issue 3 was caused by.
- **D-03:** `message_id` lives INSIDE `FinalPayload` (NOT at the answer event envelope level). The type already widened to `FinalPayload | null` in Plan 05-06 — adding one more required field follows the same path. ChatApp's existing `useEffect` on `chat.finalPayload` reads `payload.message_id` directly when constructing the assistant `ChatMessage`. Touches: `frontend/types/agent.types.ts:58` (FinalPayload), `frontend/components/ChatApp.tsx:60` (replace `a-${Date.now()}`).
- **D-04:** `message_id` is REQUIRED (always present) on every emitted answer payload — `FinalPayload.message_id: string` (NOT `string | undefined`). Backend invariant: every `_drain_events` answer yield must include it; backend tests assert presence. Rationale: optional with FE fallback IS the silent-degradation bug class the audit flagged. Any test that mocks an answer payload now MUST include message_id (drift-prevention requires this anyway).

**Resume path: id reconstruction for past conversations**
- **D-05:** Backend returns `message_id` per qualifying assistant message in the `GET /api/conversations/:id` response. Site: `backend/api/routes/conversations.py:112-120` — augment the messages list before return. FE `ChatApp.handleResume` (`frontend/components/ChatApp.tsx:114-126`) reads `m.message_id` and replaces the broken `replay-${i}` construction.
- **D-06:** Per-message field on each assistant row (NOT a parallel `message_ids[]` array, NOT a top-level `next_turn_idx` hint). Shape: `{role: 'assistant', content: '...', message_id: 'abc-0'}`. User messages get NO `message_id` field (no feedback affordance on user turns; field absence is the natural signal). Index-aligned arrays are fragile to filtering; `next_turn_idx` hint forces FE to mirror BE's `_next_turn_idx` semantics — exact drift class the audit flagged.
- **D-07:** turn_idx rule for replayed assistant messages: **1 turn = 1 user message**. Walk the messages list; turn_idx for an assistant message at position N = count of `role==user` messages at positions `[0..N]` (matches existing `_next_turn_idx` semantics verbatim — `backend/api/routes/chat.py:111-127`). HITL approve+deny resume that produces multiple assistant messages in a single turn (e.g., a pre-pause partial then a post-resume final) shares the same turn_idx — feedback attaches to the same Langfuse trace, which is correct. ONLY the LAST assistant message of each turn carries `message_id`; earlier in-turn assistant rows get no `message_id` field (silent absence → no FeedbackButtons via D-08).
- **D-08:** FeedbackButtons render gate: only on the LAST assistant message of each turn (i.e., assistant rows with a non-null `message_id`). Reuses the existing `isLast` gating pattern in `frontend/components/chat/MessageList.tsx`. Live path: the appended `done`-payload assistant is always the last → always shows buttons. Resume path: only the last assistant per turn (which is the only one with `message_id`) → buttons render. Earlier in-turn assistant rows (HITL pre-pause partials, if any persist in checkpointer messages) get no buttons.

**Drift-prevention test surface (audit lesson)**
- **D-09:** PRIMARY surface = Vitest+MSW round-trip integration test in ChatApp. Mocks `POST /api/chat` to emit a full SSE stream including an `answer` event whose payload contains `message_id`. Mounts ChatApp, sends a query, sees the assistant message render, clicks the thumbs-up button, asserts that `POST /api/feedback` fires with body `{thread_id, message_id, score: 'up'}` whose `message_id` parses cleanly through the backend regex `^(.+)-(\d+)$` AND whose extracted `thread_id` equals `body.thread_id`. Catches FE id construction + payload threading + click handler + URL all in one test — the exact wiring path that broke. Lives at `frontend/__tests__/components/ChatApp.feedback.integration.test.tsx` (planner picks: extend existing `ChatApp.integration.test.tsx` from Phase 6 OR create sibling file — both fit).
- **D-10:** SECONDARY surface = ONE production-shape backend test in `backend/tests/test_api_feedback.py`. POST with UUIDv4 thread_id (e.g., `'a4b27c8e-d4f1-4ddd-aaaa-1234567890ab'`) and integer turn_idx (e.g., `3`) → message_id `'a4b27c8e-d4f1-4ddd-aaaa-1234567890ab-3'`. Asserts 200 and that the parsed `(thread_id, turn_idx)` tuple matches input. Catches any future BE-side regex tightening that would reject UUIDv4 — production-shape coverage at near-zero cost. Belt-and-braces with D-09.
- **D-11:** RESUME PATH surface = dedicated Vitest+MSW test that mocks `GET /api/conversations/:id` with messages carrying `message_id` on the last assistant of each turn, mounts ChatApp, triggers `handleResume`, clicks thumbs-up on a replayed assistant message, asserts `POST /api/feedback` fires with the same `message_id` the BE returned. Lives alongside D-09 file. Without this, only the live path is verified — same bug class could recur on the resume rendering path.
- **D-12:** Existing `test_feedback_thread_mismatch_returns_400` and `test_feedback_malformed_message_id_returns_400` stay untouched — adding UUIDv4 variants of these adds zero coverage; the regex/mismatch behavior is already proven. YAGNI.

**Live verification protocol (success criterion 4)**
- **D-13:** Documented manual smoke test. NOT an automated test gated on env keys (slow, flaky against real cloud APIs, free-tier quota pollution); NOT a curl-only recipe (bypasses the FE click path that the audit broke). The smoke test exercises the same path a real user would: backend with `LANGFUSE_*` keys → frontend → query → click → Langfuse dashboard.
- **D-14:** Verification doc location: append a `## Live Verification (Langfuse Feedback)` section to the bottom of `docs/data-sources.md` (created in Phase 5 D-19). One less file to track; data-sources.md already documents Langfuse as an external service. Numbered checklist of 6 steps: (1) ensure backend `.env` has `LANGFUSE_*` keys + restart uvicorn (per Quick 260503-rs8 note: server holds old `_make_config` in memory until restart), (2) start frontend, (3) ask one surcharge query, (4) click thumbs-up on the answer, (5) open `https://cloud.langfuse.com` → Observations → filter on trace name `express-surcharge-agent`, (6) confirm a `user_feedback` Score row with value=1 appears on the matching `chat_turn_{thread_id}_{turn_idx}` trace.
- **D-15:** Add a screenshot artifact: extend Phase 5 D-20 screenshot list from 5 → 6 PNGs OR enrich the existing `langfuse-trace.png` placeholder to include the Score row (planner picks; 6 PNGs is cleaner). New filename suggestion: `docs/screenshots/langfuse-feedback-score.png`. README references it from the Langfuse mention. The filename is added to `docs/screenshots/.gitkeep` planning so the directory is tracked even before the human capture lands.
- **D-16:** Live verification = HUMAN checkpoint in the plan (autonomous: false). Matches Phase 5 D-20 / Plan 05-07 Task 4 pattern. The plan codifies the exact 6 steps; IT lead runs them once with real keys during W5 code freeze; screenshot capture lands alongside the 5 Phase 5 PNGs. Plan does NOT mark the phase complete until this checkpoint is ticked.

### Claude's Discretion
- Exact field ordering of `message_id` inside `FinalPayload` (alongside `markdown` vs at the bottom alongside `surcharge_result`).
- Whether to extract a single FE id-builder utility (`buildAssistantMessageId(threadId, turnIdx)`) for the test files to reuse, vs inline string template (single-use today).
- Whether to add `message_id` on user messages too (probably absent — only assistant rows need it for feedback; user-message ids are not in scope for any v1 requirement).
- Whether to extend the existing `langfuse-trace.png` placeholder OR add a new `langfuse-feedback-score.png` (D-15) — both work; visibility favors a separate screenshot.
- Plan ordering and Wave assignment — likely two plans (Wave 1: backend contract change in chat.py + conversations.py + answer-event payload + 1 BE test; Wave 2: FE FinalPayload extension + ChatApp wiring + ChatMessage type + 2 FE Vitest+MSW tests; doc update can be in either wave) but planner has full discretion. A single-plan path is also defensible given the small surface.
- Exact Vitest+MSW handler shape for the round-trip tests (extend existing `ChatApp.integration.test.tsx` MSW handlers vs new file with sibling handlers).
- Whether the BE answer-event `_drain_events` augmentation happens at the `_drain_events` yield site (single source of truth for both fresh + resume streams) vs at the per-route `format_sse` call site (two sites = small drift risk; planner picks).
- Whether the planner explicitly leaves the HITL placeholder `pending-${Date.now()}` id alone (Phase 6 D-06 strip-and-replace already verified) or migrates it to a `pending-${threadId}-${turnIdx}` shape for consistency. Strip-and-replace makes this irrelevant; planner can confirm and move on.
- Whether to update the Phase 5 D-20 screenshot list documentation to reflect 6 instead of 5, or just append.

### Deferred Ideas (OUT OF SCOPE)
- **Toast/snackbar global error UI on feedback POST failure** — Phase 5 D-16 silent-failure pattern stays; v2 if a real workflow ever needs visible feedback failure UX.
- **Backfill story for old localStorage feedback entries** (Phase 4 D-17 array shape) — out of scope.
- **Read-side Langfuse Score API verification** automated with pytest — deferred per D-13.
- **Migration of `pending-${Date.now()}` placeholder id** — strip-and-replace already prevents persistence; not required.
- **AgentState schema change to persist `message_id` alongside each message** — avoided in favor of read-time inference per D-07.
- **User-message `message_id`s** — explicitly absent in D-06.
- **Phase 8 (search_context wiring + sidebar refresh)** — deferred per ROADMAP §Phase 8. Audit Issues 4 + 6.
- **Tightening backend regex to enforce UUIDv4** — explicitly NOT done.
- **`FinalPayload` optional fallback for `message_id`** — explicitly rejected per D-04.
- **Top-level `message_id` on the SSE answer event envelope** — rejected per D-03.
- **Backend hint `next_turn_idx` for resume** — rejected per D-06.
- **FE-counted `turn_idx`** — rejected per D-04 + D-06.
- **Combined documented smoke + curl recipe** — D-13 picks documented smoke only.
- **Changes to `feedback.py` regex / `FeedbackRequest` Pydantic shape / thread_id consistency check** — locked Phase 5 D-16; audit confirmed correct.
- **Changes to `seed_trace_id` / `_make_config` / Langfuse trace name `chat_turn_{thread_id}_{turn_idx}`** — locked Phase 5 D-14.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| API-05 | POST /api/feedback accepts user feedback (score + reason) and forwards to Langfuse | Backend handler is already correct (`backend/api/routes/feedback.py`). API-05 flips from `partial` → `satisfied` once the FE-supplied `message_id` matches the regex `^(.+)-(\d+)$` AND the extracted thread_id equals the body thread_id. Research path: D-01 (live), D-05 (resume), D-09/D-10 (drift prevention tests). |
| OBS-02 | User feedback scores forwarded to Langfuse Score API for evaluation tracking | Same root cause as API-05 — `client.create_score(name="user_feedback", trace_id=seed_trace_id(thread_id, turn_idx), value=±1)` already wired in `feedback.py:78-84`. Once D-01 + D-05 ship, the Score lands on the same trace the chat handler attached its CallbackHandler to (Plan 05-02 D-14 — `langfuse_trace_id` in metadata). D-13/D-14/D-15/D-16 codify the live verification artifact. |
| UI-05 | User feedback buttons (thumbs up/down) on agent responses with reason selector on thumbs down | `FeedbackButtons` component is implemented and wired to `api.postFeedback`. The buttons render today via `MessageList.tsx:98-100`; the only break is the value of `messageId` flowing in. D-03 (live) + D-08 (resume gate) + D-09/D-11 close it. Reason selector on thumbs-down is NOT in scope for Phase 7 (Phase 4 D-17 / Plan 05-06 left it as a flat thumbs vote; the `reason` field is already plumbed in `FeedbackRequest` if a future phase wires a UI for it). |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **LLM:** Gemini 2.0 Flash only — no paid model APIs (no impact on Phase 7).
- **Budget:** Free-tier APIs only. Live verification (D-13) burns one Langfuse Score; well within free tier.
- **Secrets:** Never commit `.env` — `.env.example` required. Phase 7 verification doc references the keys but commits no secret values.
- **Git practice:** Descriptive commit messages, feature branches, IT-lead-majority commits at 20%. Plan must commit per task in clear chunks.
- **Repo structure:** Backend stays inside `backend/api/routes/`, frontend stays inside `frontend/components/`, `frontend/types/`, `frontend/__tests__/components/`, `frontend/__tests__/hooks/`. Documentation stays in `docs/`.
- **Type hints required for all Python signatures**; **TypedDict / Pydantic patterns**; `from __future__ import annotations` at the top of every Python module.
- **TypeScript:** snake_case across the wire (mirrors backend Pydantic). PascalCase.tsx components. Path alias `@/` for absolute imports.
- **Logging:** Tool invocations + cache hits/misses + fallback mechanisms + errors with full context.
- **GSD Workflow Enforcement:** All edits must go through a GSD command. Phase 7 is a planned phase, so `/gsd:execute-phase` is the entry point.
- **Local reproducibility:** Langfuse no-op when keys missing must stay (the existing graceful fallback in `feedback.py:64-73` is correct and locked per CONTEXT.md).
- **35% Agent Architecture rubric:** visible reasoning + observability is the demo lever — Phase 7 directly improves this by making feedback Scores actually land in Langfuse.

## Summary

Phase 7 closes a single contract-drift bug between Phase 4 and Phase 5: the frontend constructs assistant message ids as `` `a-${Date.now()}` `` (e.g. `"a-1714706402381"`), but the backend `POST /api/feedback` validator parses `message_id` against `^(.+)-(\d+)$` AND cross-checks the extracted thread_id against the body's `thread_id`. The regex matches on the trailing digits (so `a-1714706402381` parses thread_id=`"a"`, turn_idx=`1714706402381`), but the cross-check fails because `body.thread_id` is the real UUIDv4 thread id, not `"a"`. Every production thumbs click therefore returns HTTP 400 — and `FeedbackButtons.tsx:30-32` swallows the error to console only, so the user sees no signal. **No `user_feedback` Score has ever landed in Langfuse from a real user click.**

The fix is small, low-risk, and entirely about contract alignment: the backend already has `(thread_id, turn_idx)` in scope at the `_drain_events` answer-yield site (via the closure that calls `_make_config`); it just needs to stamp `final_payload['message_id'] = f"{thread_id}-{turn_idx}"` before yielding. The same string is reconstructed for past conversations by walking the messages list in `GET /api/conversations/:id` and attaching `message_id` to the LAST assistant of each turn (1 user message = 1 turn). The frontend then reads `payload.message_id` (live) and `m.message_id` (resume), eliminating the broken `` `a-${Date.now()}` `` and `` `replay-${i}` `` constructions. The `FeedbackButtons` component, the `api.postFeedback` client, the backend regex, the cross-check, and the Langfuse Score creation are all already correct — the only break is the value of the string flowing in.

The audit's broader lesson is that two ends of a contract constructing the same string from parts is a recurring drift class. Phase 7 prevents this from regressing by (1) making `message_id` REQUIRED on `FinalPayload` (silent degradation IS the bug class), (2) building the string ONCE on the backend and shipping the full string to the FE (not the parts), and (3) adding a Vitest+MSW round-trip test that exercises the FE id construction → POST /api/feedback → backend regex → cross-check chain end-to-end (D-09 + D-11), plus a single UUIDv4-shape backend test (D-10) so a future regex tightening can't silently break production-shape thread ids.

**Primary recommendation:** Implement the four code touches verbatim per the locked decisions (D-01 backend answer-event stamp, D-05 backend conversations enrichment, D-03/D-04 frontend FinalPayload field + ChatApp wiring, D-09/D-10/D-11 drift-prevention tests). Then the IT lead runs the 6-step manual smoke (D-13/D-14) with real Langfuse keys during W5 code freeze and captures `docs/screenshots/langfuse-feedback-score.png` (D-15/D-16). API-05, OBS-02, UI-05 flip from `partial` → `satisfied` and audit Issue 3 closes.

## Standard Stack

No new dependencies are introduced. Phase 7 reuses the already-installed Phase 5 stack verbatim.

### Core (already installed; verified by `pip show` and `npm view`)

| Library | Version (installed) | Latest available | Purpose | Why Standard |
|---------|---------------------|------------------|---------|--------------|
| `langfuse` (Python) | 4.5.1 | 3.38.20 (release-line); 4.x is the major-line for python ≥3.11 | Langfuse Python SDK; `client.create_score(name="user_feedback", trace_id=..., value=1\|-1)` | Locked Phase 5 D-13/D-14/D-16 — `seed_trace_id(thread_id, turn_idx)` deterministic resolver lives here |
| `@langfuse/langchain` (npm) | n/a (Python-side only) | 5.2.0 | LangChain CallbackHandler — Python equivalent already pinned | n/a for Phase 7 |
| `langchain` | 0.3.28 | 0.3.x | Required by `from langfuse.langchain import CallbackHandler` (Quick 260503-rs8) | Already pinned; do not change |
| `fastapi` | 0.128.8 | 0.128.x | API layer; `HTTPException`, `APIRouter` patterns reused | Already pinned |
| `pydantic` | 2.12.5 | 2.12.x | `FeedbackRequest` BaseModel (locked Phase 5) | Already pinned |
| `next` | 15.5.x | 15.5.x | Frontend framework | Already pinned |
| `react` | 19.2.x | 19.2.x | UI library | Already pinned |
| `vitest` | 4.1.5 | 4.1.x | FE test runner | Already used for Phase 6 ChatApp.integration.test.tsx |
| `msw` | 2.13.6 | 2.13.x | FE HTTP mocking — exact handler used by Phase 6 06-03 (`installPauseThenResumeHandler`) | Reuse pattern verbatim |
| `@testing-library/react` | 16.3.x | 16.3.x | FE rendering for integration tests | Already used |
| `@testing-library/user-event` | 14.x | 14.x | User interaction simulation | Already used |

**Version verification:** All versions verified live via `pip show langfuse` and `npm view <pkg> version` on 2026-05-04.

**No installs required.** Phase 7 changes code paths only.

### Alternatives Considered

| Instead of | Could Use | Tradeoff | Decision |
|------------|-----------|----------|----------|
| Per-message `message_id` field on assistant rows in resume payload | Parallel `message_ids[]` array | Index-aligned arrays drift if FE filters messages | Rejected per D-06 |
| Per-message `message_id` field | Top-level `next_turn_idx` hint | Forces FE to mirror BE `_next_turn_idx` semantics — same drift class | Rejected per D-06 |
| Backend stamps full `message_id` string | Backend sends only `turn_idx`, FE concatenates | Same drift class as audit Issue 3 | Rejected per D-02 |
| `message_id` inside `FinalPayload` | `message_id` at the SSE answer-event envelope level | Forces a new envelope shape; FinalPayload already nullable in Plan 05-06 | Rejected per D-03 |
| `message_id: string` (REQUIRED) | `message_id?: string` (OPTIONAL with FE fallback) | Silent degradation IS the audit's bug class | Rejected per D-04 |
| Vitest+MSW round-trip test | Additional canonical-shape backend tests only | BE already has canonical-shape coverage; FE wiring is what broke | D-09 round-trip + D-10 single UUIDv4 BE test |
| Documented manual smoke | pytest.mark.skipif automated read-side Score verification | Free-tier quota pollution + flakiness against real cloud | Rejected per D-13 |

## Architecture Patterns

### Recommended Project Structure

Phase 7 stays inside the existing `Phase 3 + Phase 4 + Phase 5` layout:

```
backend/
├── api/
│   ├── routes/
│   │   ├── chat.py                      # MODIFY — augment _drain_events answer yield (D-01)
│   │   ├── conversations.py             # MODIFY — attach message_id per assistant (D-05)
│   │   ├── feedback.py                  # READ-ONLY — locked Phase 5 D-16
│   │   └── ...
│   └── models.py                        # READ-ONLY — FeedbackRequest locked
├── agent/
│   └── observability.py                 # READ-ONLY — seed_trace_id locked
└── tests/
    ├── test_api_chat.py                 # MODIFY — assert message_id present in answer payload
    ├── test_api_conversations.py        # MODIFY (or create new test) — per-message message_id assertion
    └── test_api_feedback.py             # MODIFY — add UUIDv4 happy-path test (D-10)

frontend/
├── components/
│   ├── ChatApp.tsx                      # MODIFY — replace `a-${Date.now()}` (D-03) and `replay-${i}` (D-05)
│   └── chat/
│       ├── MessageList.tsx              # READ-ONLY (verify isLast gating still works post-D-08)
│       └── FeedbackButtons.tsx          # READ-ONLY — props unchanged
├── hooks/
│   └── useChatStream.ts                 # READ-ONLY — answer dispatch already pipes payload through transparently
├── types/
│   ├── agent.types.ts                   # MODIFY — add `message_id: string` to FinalPayload (D-04)
│   └── api.types.ts                     # MODIFY — add `message_id?: string` to ReplayedMessage (D-05/D-06)
└── __tests__/components/
    ├── ChatApp.integration.test.tsx     # MODIFY (extend) OR
    └── ChatApp.feedback.integration.test.tsx  # NEW (sibling) — D-09 + D-11

docs/
├── data-sources.md                      # APPEND — `## Live Verification (Langfuse Feedback)` (D-14)
└── screenshots/
    └── .gitkeep                         # MODIFY — list 6th filename `langfuse-feedback-score.png` (D-15)

README.md                                # MODIFY (planner verifies) — reference new screenshot from Langfuse section
```

### Pattern 1: Single-Source-of-Truth Contract Strings (audit lesson)

**What:** When two ends of a wire need to agree on a structured string, BUILD IT ONCE on one end and SHIP THE FULL STRING. Never have both ends construct it from parts.

**When to use:** Any cross-process contract where format drift is a real risk (i.e., always).

**Example (D-01 implementation pattern, drawn from CONTEXT.md):**
```python
# Source: backend/api/routes/chat.py:130-150 (current code, with Phase 7 augmentation)
async def _drain_events(graph, payload, config, _node_names=_NODE_NAMES, *, thread_id: str, turn_idx: int):
    """Yield (event_type, payload_dict) tuples, stamping message_id on answer payloads."""
    async for event in graph.astream_events(payload, config=config, version="v2"):
        ev_type = event.get("event")
        name = event.get("name", "")
        if ev_type == "on_chain_end" and name in _node_names:
            output = (event.get("data") or {}).get("output") or {}
            for entry in (output.get("reasoning_trace") or []):
                yield "trace", entry
            if name == "response" and "final_payload" in output:
                final_payload = output["final_payload"]
                # D-01 / D-02: stamp the FULL message_id string here, once.
                final_payload["message_id"] = f"{thread_id}-{turn_idx}"
                yield "answer", final_payload
```

The same pattern Phase 5 D-14 used for `langfuse_trace_name = "express-surcharge-agent"` (a single string constant). Phase 7 applies it to the per-turn `message_id`.

### Pattern 2: Per-Message Field with Silent Absence as Signal (D-06)

**What:** When some rows in a list need an attribute and others do not, OMIT THE FIELD on rows that don't have it (rather than emitting `null` or a sentinel) AND let the renderer use field-presence as the gating signal.

**When to use:** Per-item gating where the absence is the answer (e.g., user messages have no feedback affordance; HITL pre-pause partials are not the canonical answer for a turn).

**Example (D-05/D-06/D-08 implementation pattern):**
```python
# Source: backend/api/routes/conversations.py — Phase 7 augmentation per D-05/D-06/D-07
def _attach_message_ids(messages: list[dict], thread_id: str) -> list[dict]:
    """Walk messages; attach message_id to LAST assistant of each turn (1 turn = 1 user msg)."""
    out = []
    user_count = 0  # Mirrors backend/api/routes/chat.py:_next_turn_idx counting rule
    # First pass: count user messages preceding-or-at each position so we know
    # which turn each assistant message belongs to.
    turn_for = []
    n_users = 0
    for m in messages:
        if (m or {}).get("role") == "user":
            n_users += 1
        turn_for.append(max(0, n_users - 1))  # zero-indexed turn this message belongs to
    # Second pass: identify the LAST assistant of each turn and stamp message_id.
    last_assistant_idx_per_turn: dict[int, int] = {}
    for i, m in enumerate(messages):
        if (m or {}).get("role") == "assistant":
            last_assistant_idx_per_turn[turn_for[i]] = i
    last_indices = set(last_assistant_idx_per_turn.values())
    for i, m in enumerate(messages):
        m_out = dict(m or {})
        if i in last_indices:
            m_out["message_id"] = f"{thread_id}-{turn_for[i]}"
        out.append(m_out)
    return out
```

```typescript
// Source: frontend/components/ChatApp.tsx:114-126 — Phase 7 rewrite per D-05/D-08
const replayed: ChatMessage[] = detail.messages.map((m, i) => {
  if (m.role === 'assistant') {
    const payload: FinalPayload = {
      markdown: m.content,
      surcharge_result: detail.surcharge_result,
      capped: detail.surcharge_result?.capped ?? false,
      status: 'ok',
      // D-05: read message_id from BE (absent on non-last assistants of a turn)
      message_id: m.message_id ?? '',  // NOTE: empty string here means "no buttons"
    };
    // D-08: only assistants with a non-empty message_id get FeedbackButtons.
    // MessageList.tsx existing gate `threadId && m.payload && !slotApproval`
    // is extended to also check `m.payload.message_id`.
    return { role: 'assistant', id: m.message_id ?? `placeholder-${i}`, payload };
  }
  return { role: 'user', content: m.content };
});
```

### Pattern 3: Centralized Helper Augmentation (Phase 5 / Phase 7 reuse)

**What:** Both fresh and resume SSE paths call `_drain_events`. Augmenting the answer yield ONCE in the helper means both code paths gain `message_id` for free — no per-route duplication.

**Example (already used in `chat.py:130-150` and `chat.py:189-296`):** Both `_fresh_stream` and `_resume_stream` iterate `_drain_events(...)`. The only new requirement is to thread `thread_id` and `turn_idx` into the helper so the augmentation can use them. Both call sites already have these in scope (`_fresh_stream` builds them via `_next_turn_idx` + `_make_config`; `_resume_stream` builds them via `_next_turn_idx` with the `cfg_turn = max(0, turn_idx - 1)` clamp).

### Anti-Patterns to Avoid

- **`a-${Date.now()}`-style ids built FE-side from local clock state** — exactly the bug Phase 7 fixes. Any FE-built id whose shape must match a BE regex is a drift bomb waiting to detonate.
- **Optional `message_id` with FE fallback** — silent degradation. If the BE forgets to send it, the FE silently writes a wrong id and 400s on click; same audit bug class, just delayed by one regression. Required field is the only safe contract.
- **Top-level `message_id` on the SSE answer envelope** (alongside `type` + `payload`) — forces a new envelope shape; the existing `FinalPayload | null` widening Plan 05-06 already shipped is the natural home.
- **Backend hint `next_turn_idx` for the resume path** — forces FE to mirror BE `_next_turn_idx` semantics (count of user messages). Same drift class; same audit lesson.
- **AgentState schema change to persist `message_id` alongside each message** — much larger blast radius (touches every checkpointer write, every test fixture, every state migration). Read-time inference per D-07 is far smaller.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trace id resolution from message_id | Custom Langfuse trace id lookup or name-search | `seed_trace_id(thread_id, turn_idx)` (`backend/agent/observability.py:60-76`) | Already deterministic; Phase 5 D-14 contract; same helper attached the CallbackHandler at chat-handler boundary |
| message_id parsing on backend | Custom string parser | Existing `_TURN_RE = re.compile(r"^(.+)-(\d+)$")` in `feedback.py:28` | Locked Phase 5 D-16; audit confirmed correct; battle-tested |
| Counting turns for resume | New counter abstraction | Existing `_next_turn_idx` rule (count `role==user` messages) — see `backend/api/routes/chat.py:111-127` | Single source of truth for "what is turn_idx?" — Phase 7 just applies it twice (live + resume) |
| Mocking SSE for FE tests | Custom EventSource mock | `makeSseStream(events: SSEEvent[])` from `frontend/__tests__/fixtures/sse.ts` + MSW `http.post(...)` handler | Already used by Phase 6 06-03 `ChatApp.integration.test.tsx` end-to-end; reuse verbatim |
| Multi-call MSW handler (different response per call number) | Custom handler counter | `installPauseThenResumeHandler(resumeEvents)` pattern from `frontend/__tests__/components/ChatApp.integration.test.tsx:78-99` | Already proven for HITL approve+deny; D-09 mirrors the pattern (first call = paused turn → second call = resume) |
| Backend Langfuse mock in tests | New fixture | Existing `monkeypatch.setattr(fb_mod, "get_langfuse_client", lambda: fake)` + `monkeypatch.setattr(fb_mod, "seed_trace_id", lambda tid, ti: f"trace-{tid}-{ti}")` from `test_api_feedback.py:28-31` | Reuse verbatim for the D-10 UUIDv4 happy-path test |

**Key insight:** This phase has zero novel infrastructure. Every helper, fixture, regex, and test pattern Phase 7 needs already exists from Phase 3 / 4 / 5 / 6. The work is contract alignment via small, surgical edits at well-known sites.

## Common Pitfalls

### Pitfall 1: Forgetting the `_drain_events` signature change for `thread_id` / `turn_idx` threading

**What goes wrong:** `_drain_events` currently takes `(graph, payload, config, _node_names=_NODE_NAMES)` and has no `thread_id` / `turn_idx` in scope. The augmentation `final_payload["message_id"] = f"{thread_id}-{turn_idx}"` requires both to be available at the yield site.

**Why it happens:** The function was written in Phase 3 / 5 with no need for the per-turn identity inside the helper — the chat handler closures held those values.

**How to avoid:** Pass `thread_id` and `turn_idx` as keyword-only arguments to `_drain_events` (matches the existing positional-then-keyword pattern). Both `_fresh_stream` (line ~199-211) and `_resume_stream` (line ~267-275) already build these values BEFORE calling `_drain_events` — the threading is mechanical.

**Warning signs:** A test asserting `answer.payload["message_id"] == "tid-0"` fails with `KeyError: 'message_id'` (forgot to stamp) or `NameError: name 'thread_id' is not defined` (forgot to thread the parameter).

### Pitfall 2: Replayed multi-assistant turns from HITL (one user → one approve → one final assistant + one pre-pause partial)

**What goes wrong:** If a HITL turn ever persists BOTH a pre-pause partial assistant message and a post-resume final assistant message into the checkpointer (i.e., two assistant rows for ONE user message), naive turn counting could attach `message_id` to the wrong one or to both.

**Why it happens:** The `_next_turn_idx` rule is "count user messages." Two assistants with one preceding user message both belong to the same turn. The rule for which gets the `message_id` is per D-07: ONLY the LAST assistant of each turn.

**How to avoid:** D-07 explicitly says: walk messages, group by turn (1 turn = 1 user message), pick the LAST assistant in each group, stamp `message_id` on it only. See the `_attach_message_ids` example in Pattern 2 above.

**Warning signs:** Two assistants from the same turn both rendering FeedbackButtons in the resume UI; or a thumbs click on the "wrong" assistant landing on a different Langfuse trace than expected (impossible with D-07 rule because both assistants share the same turn_idx, hence the same trace_id — which is also why D-07 calls this out as "feedback attaches to the same Langfuse trace, which is correct").

### Pitfall 3: `message_id` empty-string sentinel ambiguity in `MessageList` rendering gate

**What goes wrong:** If the resume map function uses `message_id: m.message_id ?? ''` (empty string fallback), the `MessageList` gate `threadId && m.payload && !slotApproval` is unchanged but the FeedbackButtons consumer would receive `messageId=""` and submit a feedback POST with an empty message_id → backend regex 400.

**Why it happens:** Defensive `?? ''` patterns are common in TS but the consuming gate doesn't check for empty.

**How to avoid:** Either (a) gate the FeedbackButtons render on `m.payload.message_id` (truthy check, since empty string is falsy), or (b) have the resume map function SKIP the assistant entry if `m.message_id` is absent (don't render anything for non-canonical assistant rows). Per D-08, render gate = "assistant rows with a non-null `message_id`," so option (a) is the documented path; the existing `MessageList.tsx:98-100` gate `threadId && m.payload && !slotApproval` becomes `threadId && m.payload && m.payload.message_id && !slotApproval`.

**Warning signs:** A FeedbackButtons render in a resume scenario where the BE didn't supply `message_id` for that row — the click would 400. The Vitest+MSW resume-path test (D-11) catches this if the mock omits `message_id` on a non-last assistant row.

### Pitfall 4: Type mismatch on `FinalPayload.message_id` in the existing `useChatStream` answer reducer

**What goes wrong:** The reducer dispatches `{ type: 'ANSWER', payload: ev.payload }` (`useChatStream.ts:172-173`). If `FinalPayload` gains a REQUIRED `message_id: string` but a test mock or future Phase regression emits an `answer` event without it, TypeScript will not catch the runtime mismatch (the SSE event is `unknown`-typed at the wire boundary).

**Why it happens:** Trust boundary. The wire is JSON; the type system enforces shape only on what the test mocks declare.

**How to avoid:** Make `message_id` a REQUIRED field on `FinalPayload` (D-04) so any test that mocks an `answer` payload MUST include it. The Vitest+MSW round-trip test (D-09) that emits a real SSE stream provides runtime evidence. The TypeScript `as FinalPayload` assertion at `frontend/components/ChatApp.tsx:61` would still type-cast, so the test mocks are the safety net — make sure the existing fixtures in `frontend/__tests__/fixtures/sse.ts` (`HAPPY_PAYLOAD`, `CAPPED_PAYLOAD`, `CLARIFY_PAYLOAD`, `PARTIAL_PAYLOAD`) all gain a `message_id` field so existing tests pick up the new requirement at compile time.

**Warning signs:** Adding `message_id: string` to `FinalPayload` and running `npm run type-check` should produce errors at every fixture + every existing test that constructs a `FinalPayload` literal. Update them all.

### Pitfall 5: Uvicorn restart required for live verification (per Quick 260503-rs8)

**What goes wrong:** Deploy backend Phase 7 changes; live verify; thumbs click still 400s.

**Why it happens:** A running uvicorn process holds the OLD `_drain_events` and `_make_config` closures in memory. Pytest exercises a fresh import each run, so the test suite covers the new contract. Live `/api/chat` traffic does not.

**How to avoid:** D-14 step 1 explicitly says: "ensure backend `.env` has `LANGFUSE_*` keys + restart uvicorn." Restart is non-negotiable.

**Warning signs:** Tests pass; live click 400s. Check uvicorn process age (`ps -ef | grep uvicorn`) — if it predates the deploy, restart it.

### Pitfall 6: Fixtures in `frontend/__tests__/fixtures/sse.ts` need updating

**What goes wrong:** `HAPPY_PAYLOAD`, `CAPPED_PAYLOAD`, `CLARIFY_PAYLOAD`, `PARTIAL_PAYLOAD` are reused across many existing tests (`MessageList.test.tsx`, `MarkdownAnswer.test.tsx`, `PartialCard.test.tsx`, `ClarifyCard.test.tsx`, `ChatApp.integration.test.tsx`). Adding REQUIRED `message_id: string` to `FinalPayload` will fail tsc on every literal.

**Why it happens:** Required fields propagate across all existing usage.

**How to avoid:** Update all four fixtures in one edit to include `message_id: 'thread-happy-0'` (or similar canonical value). Run `npm run type-check` before and after to verify compile.

**Warning signs:** `tsc --noEmit` errors at fixture sites.

### Pitfall 7: Scope creep into the deferred Phase 8 items

**What goes wrong:** While in `response_node.py` for testing, also fix the `search_context` omission (audit Issue 6); while in ChatApp.tsx, also fix the sidebar refresh (audit Issue 4). These are explicitly Phase 8.

**Why it happens:** Adjacent code; small fixes look tempting.

**How to avoid:** CONTEXT.md `Explicitly out of scope` is the gate. Plan tasks should reference Phase 8 by ROADMAP and decline to touch those files.

**Warning signs:** A diff for a feedback-contract task touching `response_node.py` or `useConversations.ts` — push back to the planner.

## Code Examples

### Example 1: Backend D-01 augmentation at the answer-yield site

```python
# Source: backend/api/routes/chat.py — Phase 7 augmentation (D-01, D-02)
async def _drain_events(
    graph,
    payload,
    config,
    _node_names=_NODE_NAMES,
    *,
    thread_id: str,
    turn_idx: int,
):
    """Async generator yielding (event_type, payload_dict) tuples.

    Phase 7 D-01: stamps `message_id: '{thread_id}-{turn_idx}'` on the answer
    payload before yielding. Single source of truth for the FE assistant
    message id contract — FE never reconstructs the string from parts.
    """
    async for event in graph.astream_events(payload, config=config, version="v2"):
        ev_type = event.get("event")
        name = event.get("name", "")
        if ev_type == "on_chain_end" and name in _node_names:
            output = (event.get("data") or {}).get("output") or {}
            for entry in (output.get("reasoning_trace") or []):
                yield "trace", entry
            if name == "response" and "final_payload" in output:
                final_payload = output["final_payload"]
                final_payload["message_id"] = f"{thread_id}-{turn_idx}"
                yield "answer", final_payload
```

Both `_fresh_stream` and `_resume_stream` already compute `(thread_id, turn_idx)` before invoking `_drain_events`. Pass them as keyword arguments — both call sites become e.g. `async for kind, payload in _drain_events(graph, initial_state, config, thread_id=thread_id, turn_idx=turn_idx):`.

### Example 2: Backend D-05/D-07 walk for `GET /api/conversations/:id`

```python
# Source: backend/api/routes/conversations.py — Phase 7 augmentation (D-05, D-06, D-07)
def _attach_message_ids(
    messages: list[dict[str, Any]],
    thread_id: str,
) -> list[dict[str, Any]]:
    """Attach `message_id` to the LAST assistant message of each turn.

    Turn rule (D-07, mirrors `chat.py:_next_turn_idx`): one user message starts
    one turn; assistants belong to the most recent preceding user message's turn.
    Only the LAST assistant per turn is canonical (the one a thumbs vote should
    score). User messages and non-last in-turn assistant rows get NO message_id
    (silent absence is the FE gate signal — D-06, D-08).
    """
    # First pass: which turn (zero-indexed) does each row belong to?
    turn_for: list[int] = []
    n_users_seen = 0
    for m in messages:
        if (m or {}).get("role") == "user":
            n_users_seen += 1
        turn_for.append(max(0, n_users_seen - 1))

    # Second pass: which row is the LAST assistant in each turn?
    last_assistant_per_turn: dict[int, int] = {}
    for i, m in enumerate(messages):
        if (m or {}).get("role") == "assistant":
            last_assistant_per_turn[turn_for[i]] = i
    last_indices = set(last_assistant_per_turn.values())

    # Third pass: emit copies, stamping message_id on canonical assistants.
    out: list[dict[str, Any]] = []
    for i, m in enumerate(messages):
        m_out = dict(m or {})
        if i in last_indices:
            m_out["message_id"] = f"{thread_id}-{turn_for[i]}"
        out.append(m_out)
    return out


# Then in get_conversation:
return {
    "thread_id": thread_id,
    "messages": _attach_message_ids(values.get("messages") or [], thread_id),
    "surcharge_result": values.get("surcharge_result"),
    # ...rest unchanged
}
```

### Example 3: Frontend D-03 ChatApp live-append rewrite

```typescript
// Source: frontend/components/ChatApp.tsx:36-66 — Phase 7 rewrite (D-03, D-04)
useEffect(() => {
  if (!chat.finalPayload) return;
  if (chat.status !== 'done') return;
  if (lastAppendedPayloadRef.current === chat.finalPayload) return;
  lastAppendedPayloadRef.current = chat.finalPayload;
  setMessages((prev) => {
    const stripped =
      pendingApprovalSlotRef.current &&
      prev.length > 0 &&
      prev[prev.length - 1].role === 'assistant' &&
      (prev[prev.length - 1] as { payload: FinalPayload | null }).payload === null
        ? prev.slice(0, -1)
        : prev;
    pendingApprovalSlotRef.current = false;
    return [
      ...stripped,
      {
        role: 'assistant',
        // D-03: read message_id from BE's FinalPayload — single source of truth.
        // Drops the broken `a-${Date.now()}` clock-derived id (audit Issue 3 root cause).
        id: chat.finalPayload!.message_id,
        payload: chat.finalPayload as FinalPayload,
      },
    ];
  });
  void conversations.refresh();
}, [chat.finalPayload, chat.status, conversations]);
```

### Example 4: Frontend D-05 ChatApp resume-map rewrite

```typescript
// Source: frontend/components/ChatApp.tsx:107-136 — Phase 7 rewrite (D-05, D-08)
const handleResume = useCallback(
  async (threadId: string) => {
    try {
      const detail = await conversations.resume(threadId);
      const replayed: ChatMessage[] = detail.messages.map((m, i) => {
        if (m.role === 'assistant') {
          // D-05: BE attaches message_id to the LAST assistant of each turn.
          // Earlier in-turn assistants (HITL pre-pause partials) get no field.
          const payload: FinalPayload = {
            markdown: m.content,
            surcharge_result: detail.surcharge_result,
            capped: detail.surcharge_result?.capped ?? false,
            status: 'ok',
            // D-04: REQUIRED field on FinalPayload — empty when BE omitted it,
            // which signals "no FeedbackButtons" to MessageList per D-08.
            message_id: m.message_id ?? '',
          };
          return {
            role: 'assistant',
            // Use BE-supplied id when present; fall back to a synthetic non-canonical
            // id for non-last assistant rows so React's key stays stable.
            id: m.message_id ?? `replay-noncanonical-${i}`,
            payload,
          };
        }
        return { role: 'user', content: m.content };
      });
      setMessages(replayed);
      lastAppendedPayloadRef.current = null;
    } catch (err) {
      console.error('[resume]', err);
    }
  },
  [conversations],
);
```

### Example 5: D-09 round-trip Vitest+MSW test sketch

```typescript
// Source: frontend/__tests__/components/ChatApp.feedback.integration.test.tsx (NEW) — Phase 7 D-09
import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { ChatApp } from '@/components/ChatApp';
import { server } from '../mocks/server';
import { HAPPY_PAYLOAD, HAPPY_TRACE, makeSseStream } from '../fixtures/sse';
import type { SSEEvent } from '@/types/agent.types';

describe('ChatApp feedback integration (Phase 7 D-09)', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('thumbs-up POST /api/feedback fires with BE-stamped message_id that parses through `^(.+)-(\\d+)$`', async () => {
    const user = userEvent.setup();
    const THREAD_ID = 'a4b27c8e-d4f1-4ddd-aaaa-1234567890ab';
    const MESSAGE_ID = `${THREAD_ID}-0`;

    // 1. Mock POST /api/chat to emit a happy SSE stream with message_id stamped on FinalPayload.
    const happyEvents: SSEEvent[] = [
      { type: 'meta', payload: { thread_id: THREAD_ID } },
      ...HAPPY_TRACE.map((entry) => ({ type: 'trace' as const, payload: entry })),
      { type: 'answer', payload: { ...HAPPY_PAYLOAD, message_id: MESSAGE_ID } },
      { type: 'done', payload: {} },
    ];
    let feedbackBody: { thread_id: string; message_id: string; score: string } | null = null;
    server.use(
      http.post('http://localhost:8000/api/chat', () =>
        new HttpResponse(makeSseStream(happyEvents), {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
      http.post('http://localhost:8000/api/feedback', async ({ request }) => {
        feedbackBody = (await request.json()) as typeof feedbackBody;
        // Defensive in-test assertions: the wire body must satisfy the BE contract.
        expect(feedbackBody!.message_id).toMatch(/^(.+)-(\d+)$/);
        const m = feedbackBody!.message_id.match(/^(.+)-(\d+)$/)!;
        expect(m[1]).toBe(feedbackBody!.thread_id);
        return HttpResponse.json({ status: 'ok', delivered: true, trace_id: 'fake-trace' });
      }),
    );

    render(<ChatApp />);

    // 2. Send a query.
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'Surcharge for 15kg Bounce Bangkok to Nonthaburi',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    // 3. Wait for answer to render (table appears).
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument(), { timeout: 4000 });

    // 4. Click thumbs-up.
    await user.click(screen.getByRole('button', { name: 'Helpful' }));

    // 5. Verify the POST /api/feedback fired with the BE-stamped message_id.
    await waitFor(() => expect(feedbackBody).not.toBeNull());
    expect(feedbackBody!).toEqual({
      thread_id: THREAD_ID,
      message_id: MESSAGE_ID,
      score: 'up',
    });
  });
});
```

### Example 6: D-10 single UUIDv4-shape backend test

```python
# Source: backend/tests/test_api_feedback.py — Phase 7 addition (D-10)
def test_feedback_uuidv4_thread_id_happy_path(monkeypatch, client):
    """D-10 production-shape: UUIDv4 thread_id + integer turn_idx parses cleanly.

    Drift-prevention belt-and-braces alongside the FE Vitest+MSW round-trip
    (D-09). Catches any future regex tightening that would reject UUIDv4-shaped
    thread ids — the canonical 'abc-0' fixtures elsewhere in this file would
    miss that regression.
    """
    from backend.api.routes import feedback as fb_mod

    captured: dict = {}
    fake = MagicMock()
    fake.create_score = lambda **kw: captured.update(kw)
    monkeypatch.setattr(fb_mod, "get_langfuse_client", lambda: fake)
    monkeypatch.setattr(
        fb_mod,
        "seed_trace_id",
        lambda tid, ti: f"trace-{tid}-{ti}",
    )

    thread_id = "a4b27c8e-d4f1-4ddd-aaaa-1234567890ab"
    turn_idx = 3
    message_id = f"{thread_id}-{turn_idx}"

    resp = client.post(
        "/api/feedback",
        json={
            "thread_id": thread_id,
            "message_id": message_id,
            "score": "up",
            "reason": "uuid-shape verification",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["delivered"] is True
    assert body["trace_id"] == f"trace-{thread_id}-{turn_idx}"
    assert captured["trace_id"] == f"trace-{thread_id}-{turn_idx}"
    assert captured["name"] == "user_feedback"
    assert captured["value"] == 1
    assert captured["comment"] == "uuid-shape verification"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FE constructs assistant message id from `Date.now()` | BE stamps the FULL `{thread_id}-{turn_idx}` string on the answer event payload | Phase 7 (this phase) | Closes audit Issue 3; production thumbs clicks succeed; `user_feedback` Score lands in Langfuse |
| Replay map uses `replay-${i}` for assistant id | BE stamps `message_id` per LAST-assistant-of-turn in `GET /api/conversations/:id`; FE reads it | Phase 7 (this phase) | Resume-path feedback also works (was equally broken pre-Phase-7) |
| `FinalPayload.message_id` field absent | `FinalPayload.message_id: string` REQUIRED | Phase 7 (D-04) | Drift prevention — silent degradation no longer possible |
| Backend tests use only canonical `'abc-0'` ids | Plus one production-shape UUIDv4 test (D-10) | Phase 7 (this phase) | Future regex tightening can't silently break production-shape thread ids |
| FE wiring tested only in unit isolation | Vitest+MSW round-trip exercises FE id construction → POST → BE regex → cross-check end-to-end (D-09 + D-11) | Phase 7 (this phase) | Same bug class can't recur |

**Deprecated/outdated (Phase 7 removes):**
- `` `a-${Date.now()}` `` literal at `frontend/components/ChatApp.tsx:60` — replaced by `chat.finalPayload!.message_id`.
- `` `replay-${i}` `` literal at `frontend/components/ChatApp.tsx:122` — replaced by `m.message_id ?? \`replay-noncanonical-${i}\``.

## Open Questions

1. **Should the `id` field on the React `ChatMessage` type carry the same value as `payload.message_id`, or are they conceptually distinct?**
   - What we know: Today `id` is the React reconciliation key AND the value the FeedbackButtons consumer reads (`MessageList.tsx:99` passes `messageId={m.id}`). Phase 7 unifies them on the canonical answer rows.
   - What's unclear: For non-canonical resume rows (HITL pre-pause partials with no BE-supplied `message_id`), the React key still needs SOMETHING unique. The example sketch above uses `replay-noncanonical-${i}` — planner can pick a different shape.
   - Recommendation: Keep `id` and `payload.message_id` aligned for canonical rows; use any synthetic key for non-canonical rows since FeedbackButtons won't render anyway.

2. **Plan ordering — single plan vs two plans split by wave?**
   - What we know: CONTEXT.md `Claude's Discretion` notes both shapes are defensible. Total surface is small (3 BE files + 3 FE files + 4 tests + 2 docs).
   - What's unclear: Whether the planner prefers to ship BE first then FE, or one atomic plan. A single-plan path means BE + FE land together; a two-wave path means BE can ship first and FE catches up.
   - Recommendation: Two plans, one wave each (or two waves in one plan). Wave 1: backend contract change in chat.py + conversations.py + answer-event payload + 1 BE test (D-10). Wave 2: FE FinalPayload extension + ChatApp wiring + ChatMessage type + 2 FE Vitest+MSW tests (D-09 + D-11). Doc update can be in either wave. Live verification (D-13/D-14/D-15/D-16) is Task 4 in the final wave (HUMAN-only).

3. **Should `FinalPayload.message_id` field placement matter inside the type definition?**
   - What we know: TypeScript field order is conventional, not load-bearing.
   - What's unclear: Whether to place it next to `markdown` (alphabetical-ish) or at the bottom alongside `surcharge_result`.
   - Recommendation: At the top, immediately after `markdown` — it's the identity field for the message and reads more naturally there. Planner has full discretion.

4. **Do we extract `buildAssistantMessageId(threadId, turnIdx)` as a shared FE utility?**
   - What we know: The string is now built ONLY on the backend (D-02). The FE consumes the prebuilt string.
   - What's unclear: Tests might reuse `buildAssistantMessageId` for setup convenience.
   - Recommendation: Don't extract a utility on the FE — it would be tempting to call it from production code and re-introduce the drift. Inline the test fixture string. (Per CONTEXT.md `Claude's Discretion`.)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Backend changes | ✓ | 3.11.x (already used by Phase 5) | — |
| Node.js 18+ | Frontend changes + Vitest | ✓ (assumed; Phase 4 uses Node 25) | — | — |
| `langfuse` Python SDK | Backend Score creation (no-op without keys) | ✓ | 4.5.1 (`pip show langfuse`) | Graceful no-op when LANGFUSE_* env missing — feedback POST returns 200 with `delivered=false` |
| `vitest` + `msw` + `@testing-library/react` | FE drift-prevention tests | ✓ | 4.1.5 / 2.13.6 / 16.3.x (`frontend/package.json`) | — |
| `pytest` + `fastapi.testclient` | BE drift-prevention test | ✓ | already used | — |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | Live verification (D-13/D-14) ONLY | Required only at IT lead's machine for the manual smoke; tests do not need them | — | Smoke is HUMAN-only checkpoint (D-16); skipped in CI |
| Running uvicorn on port 8000 | Live verification step 1 | Required for the manual smoke; pytest does not use it | — | Restart required after deploy per Pitfall 5 |
| Running Next.js dev server | Live verification step 2 | Required for the manual smoke | — | — |
| Browser access to https://cloud.langfuse.com | Live verification step 5 | Required for the manual smoke | — | — |

**Missing dependencies with no fallback:** None. All required tooling is installed; the live-verification dependencies (Langfuse keys, browser, two dev servers) are only needed by the IT lead at the documented checkpoint, not by autonomous code work.

**Missing dependencies with fallback:** None. Phase 7 has zero install steps.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest (already configured in `backend/tests/`) |
| Backend config file | `pyproject.toml` / `pytest.ini` (existing); `backend/tests/conftest.py` |
| Frontend framework | vitest 4.1.5 + jsdom + @testing-library/react 16.3.x + MSW 2.13.6 |
| Frontend config file | `frontend/vitest.config.ts` (existing); `frontend/__tests__/setup.ts` |
| Backend quick run command | `pytest backend/tests/test_api_feedback.py backend/tests/test_api_chat.py backend/tests/test_api_conversations.py -x` |
| Backend full suite command | `pytest backend/tests/ -q` |
| Frontend quick run command | `cd frontend && npx vitest run __tests__/components/ChatApp.feedback.integration.test.tsx` |
| Frontend full suite command | `cd frontend && npm test -- --run` |
| Phase gate | All BE + FE suites green before `/gsd:verify-work` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| API-05 | Production-shape thread_id (UUIDv4) parses through backend regex + cross-check | unit (BE) | `pytest backend/tests/test_api_feedback.py::test_feedback_uuidv4_thread_id_happy_path -x` | ❌ Wave (D-10 new) |
| API-05 | FE click → POST /api/feedback fires with BE-stamped message_id matching `^(.+)-(\d+)$` and `body.thread_id == parsed thread_id` | integration (FE Vitest+MSW round-trip) | `npx vitest run __tests__/components/ChatApp.feedback.integration.test.tsx` | ❌ Wave (D-09 new file or extension of `ChatApp.integration.test.tsx`) |
| API-05 | Resume-path FE click on a replayed assistant message also satisfies the contract | integration (FE Vitest+MSW resume path) | same file as D-09 | ❌ Wave (D-11 new test in same file) |
| OBS-02 | `client.create_score(name="user_feedback", trace_id=seed_trace_id(...), value=±1)` fires when keys are present | unit (BE) | already covered by `test_feedback_posts_score` and `test_feedback_score_down_maps_to_negative_one` in `test_api_feedback.py` | ✅ Existing |
| OBS-02 | Live `user_feedback` Score row appears in Langfuse Cloud on the matching `chat_turn_{thread_id}_{turn_idx}` trace | manual-only (HUMAN smoke per D-13/D-14) | `docs/data-sources.md` § Live Verification (Langfuse Feedback) | ❌ Wave (D-14 doc append) |
| UI-05 | Backend stamps `message_id` on every `answer` SSE payload | unit (BE) | `pytest backend/tests/test_api_chat.py::test_happy_path_sse_sequence -x` (extend with `assert "message_id" in answer["payload"]`) | ✅ Existing test, ❌ assertion to be added |
| UI-05 | Backend attaches `message_id` to LAST assistant of each turn in `GET /api/conversations/:id` | unit (BE) | `pytest backend/tests/test_api_conversations.py -x` (extend with per-message message_id assertion) | ✅ Existing test, ❌ assertion to be added |
| UI-05 | FE `MessageList` renders FeedbackButtons only on assistant rows with non-null `message_id` | unit (FE) | `npx vitest run __tests__/components/MessageList.test.tsx` (extend) | ✅ Existing test, ❌ assertion may need addition |
| UI-05 | FE click handler is unchanged; only the value flowing into `messageId` changes | covered by D-09 | (above) | ❌ |

### Sampling Rate

- **Per task commit:** Run the touched file's tests (e.g., on the FE FinalPayload edit, `npx vitest run __tests__/fixtures __tests__/components/MessageList.test.tsx __tests__/components/ChatApp.feedback.integration.test.tsx`).
- **Per wave merge:** Backend full suite (`pytest backend/tests/ -q`) + frontend full suite (`npm test -- --run`). Both must be green.
- **Phase gate:** Both full suites green before `/gsd:verify-work`. Plus the manual smoke checkpoint (D-13/D-14/D-16) ticked by the IT lead with screenshot artifact `docs/screenshots/langfuse-feedback-score.png`.

### Wave 0 Gaps

- [ ] `frontend/__tests__/components/ChatApp.feedback.integration.test.tsx` — NEW file (D-09 round-trip + D-11 resume path), OR equivalent extension of `frontend/__tests__/components/ChatApp.integration.test.tsx`.
- [ ] `backend/tests/test_api_feedback.py::test_feedback_uuidv4_thread_id_happy_path` — NEW test (D-10).
- [ ] `backend/tests/test_api_chat.py` — assertion addition: every `answer` event payload contains `message_id` matching `^(.+)-(\d+)$` with thread_id matching the request body.
- [ ] `backend/tests/test_api_conversations.py` — assertion addition: per-message `message_id` on the LAST assistant of each turn (or new dedicated test in the same file).
- [ ] `frontend/__tests__/fixtures/sse.ts` — update `HAPPY_PAYLOAD`, `CAPPED_PAYLOAD`, `CLARIFY_PAYLOAD`, `PARTIAL_PAYLOAD` to carry `message_id` (becomes required by `FinalPayload` type — Pitfall 6).
- [ ] `frontend/__tests__/components/MessageList.test.tsx` — verify existing tests still pass after the `message_id` requirement; possibly add an assertion that FeedbackButtons does NOT render for assistant rows lacking `message_id` (resume-path drift prevention sibling).
- [ ] `docs/data-sources.md` — append `## Live Verification (Langfuse Feedback)` 6-step checklist (D-14).
- [ ] `docs/screenshots/.gitkeep` — list the new screenshot filename `langfuse-feedback-score.png` (D-15).

No framework install needed; all tooling is already in place.

## Sources

### Primary (HIGH confidence — verified live in this session)

- `.planning/phases/07-feedback-contract-alignment/07-CONTEXT.md` — fully locked; D-01 through D-16; Claude's Discretion explicitly enumerated; deferred ideas explicitly enumerated.
- `.planning/v1.0-MILESTONE-AUDIT.md` § 2.2 Issue 3 — root cause documented with file paths and line numbers; § 4.1 partial-status matrix for API-05/OBS-02/UI-05; § 7 file paths at the centre of the gaps.
- `.planning/REQUIREMENTS.md` — API-05/OBS-02/UI-05 mapped to Phase 7 in the traceability matrix.
- `backend/api/routes/feedback.py` — `_TURN_RE = re.compile(r"^(.+)-(\d+)$")`, thread_id cross-check, `client.create_score(name="user_feedback", ...)`, graceful no-op fallback. Locked.
- `backend/api/routes/chat.py` — `_drain_events`, `_make_config`, `_next_turn_idx`, `_fresh_stream`, `_resume_stream`. Confirmed `(thread_id, turn_idx)` are in scope at the call sites.
- `backend/api/routes/conversations.py` — `get_conversation` returns `messages` list; planner walks it for D-05/D-07.
- `backend/api/models.py` — `FeedbackRequest` is locked Pydantic shape.
- `backend/agent/observability.py` — `seed_trace_id(thread_id, turn_idx)` deterministic resolver.
- `backend/tests/test_api_feedback.py` — existing canonical-shape tests; no UUIDv4 coverage today.
- `backend/tests/test_api_chat.py` — existing happy-path SSE assertions; no message_id assertion today.
- `backend/tests/test_api_conversations.py` — existing GET assertions; no per-message message_id assertion today.
- `frontend/components/ChatApp.tsx` — `id: 'a-${Date.now()}'` at line 60 (the bug); `id: 'replay-${i}'` at line 122 (the resume-path bug).
- `frontend/types/agent.types.ts` — `FinalPayload` definition at line 58; no `message_id` field today.
- `frontend/types/api.types.ts` — `ReplayedMessage` at line 31; no `message_id` field today.
- `frontend/components/chat/MessageList.tsx` — render gate `threadId && m.payload && !slotApproval` at line 98-100; consumer `<FeedbackButtons threadId={threadId} messageId={m.id} />` at line 99.
- `frontend/components/chat/FeedbackButtons.tsx` — `api.postFeedback({thread_id, message_id, score})` at line 25-29.
- `frontend/hooks/useChatStream.ts` — `case 'answer': dispatch({ type: 'ANSWER', payload: ev.payload })` at line 172-173 — pipes payload through transparently.
- `frontend/__tests__/components/ChatApp.integration.test.tsx` — Phase 6 06-03 D-15.3 MSW round-trip pattern; `installPauseThenResumeHandler` at line 78-99 — the exact pattern Phase 7 D-09 reuses.
- `frontend/__tests__/components/FeedbackButtons.test.tsx` — existing canonical-shape unit tests; show `api.postFeedback` mock pattern.
- `frontend/__tests__/fixtures/sse.ts` — `makeSseStream`, `HAPPY_PAYLOAD`, `HAPPY_TRACE`, `happyTurnEvents`. Reusable verbatim.
- `frontend/__tests__/mocks/server.ts` + `handlers.ts` — MSW `setupServer` + handler pattern.
- `frontend/lib/api.ts` — `api.postFeedback` client, `FeedbackRequestBody` shape.
- `docs/data-sources.md` — Langfuse section already documents the trace name and Score names; D-14 appends to this file.
- `frontend/package.json` — versions verified: vitest 4.1.5, msw 2.13.6, @testing-library/react 16.3.x, @testing-library/user-event 14.x.
- `requirements.txt` — versions verified: langfuse 4.5.1, langchain 0.3.28, fastapi 0.128.8, pydantic 2.12.5.
- `.planning/STATE.md` — Phase 5 + 6 history; Quick 260503-rs8 (uvicorn restart requirement); Plan 05-06 D-16 (feedback wire shape locked); Plan 05-02 D-14 (deterministic trace_id).

### Secondary (MEDIUM confidence — registry / npm view)

- `npm view langfuse version` → 3.38.20 (note: this is the JS SDK release line). The Python SDK installed is 4.5.1.
- `npm view @langfuse/langchain version` → 5.2.0 (JS LangChain integration; Python uses `from langfuse.langchain import CallbackHandler`).
- `pip show langfuse` → 4.5.1 installed locally.

### Tertiary (LOW confidence — not used as authoritative)

- None. All Phase 7 claims are verified against either the locked CONTEXT.md, the audit document, or the live source files.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — no new dependencies; every version verified live.
- Architecture: **HIGH** — every modification site has been read in this session and matches CONTEXT.md verbatim.
- Pitfalls: **HIGH** — pitfalls 1-7 derive from concrete properties of the existing code (closure scopes, fixture reuse, render gate logic) and the audit document's lessons.
- Drift-prevention test design: **HIGH** — D-09/D-11 reuse the Phase 6 06-03 `installPauseThenResumeHandler` pattern verbatim; D-10 reuses the existing `monkeypatch.setattr(fb_mod, ...)` fixture pattern verbatim.
- Live verification protocol: **MEDIUM** — D-13/D-14/D-16 are HUMAN-only and depend on the IT lead having Langfuse keys. The 6-step checklist is exhaustive but the actual outcome (Score row appearing) cannot be proven by automated code.

**Research date:** 2026-05-04
**Valid until:** 2026-06-03 (30 days — stack is stable; Phase 7 surface is small and entirely contract-alignment).
