---
phase: 7
slug: feedback-contract-alignment
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-04
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) / vitest 4.1.5 + jsdom + MSW 2.13.6 (frontend) |
| **Config file** | backend/pytest.ini, frontend/vitest.config.ts |
| **Quick run command** | `cd /Users/pollot/Desktop/express-dynamic-workflow && pytest backend/tests/test_api_chat.py backend/tests/test_api_conversations.py backend/tests/test_api_feedback.py -x -q` (BE) / `cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npx vitest run __tests__/components/ChatApp.feedback.integration.test.tsx` (FE) |
| **Full suite command** | `cd /Users/pollot/Desktop/express-dynamic-workflow && pytest backend/tests/ -q && cd frontend && npx vitest run && npx tsc --noEmit` |
| **Estimated runtime** | ~30 seconds (BE) + ~20 seconds (FE) = ~50 seconds total |

---

## Sampling Rate

- **After every task commit:** Run quick command for the layer touched (backend or frontend)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01 / Task 1 | 07-01 | 1 | API-05, UI-05 | unit (BE) | `cd /Users/pollot/Desktop/express-dynamic-workflow && pytest backend/tests/test_api_chat.py -x -q` | New tests added in this task (`test_happy_path_answer_payload_contains_message_id`, `test_answer_message_id_matches_feedback_regex`) | ⬜ pending |
| 07-01 / Task 2 | 07-01 | 1 | API-05, UI-05 | unit (BE) | `cd /Users/pollot/Desktop/express-dynamic-workflow && pytest backend/tests/test_api_conversations.py -x -q` | New tests added in this task (`test_get_conversation_attaches_message_id_to_last_assistant`, `test_get_conversation_message_id_user_messages_have_no_field`) | ⬜ pending |
| 07-01 / Task 3 | 07-01 | 1 | API-05, OBS-02 | unit (BE) | `cd /Users/pollot/Desktop/express-dynamic-workflow && pytest backend/tests/test_api_feedback.py -x -q` | New test added in this task (`test_feedback_uuidv4_thread_id_happy_path`) | ⬜ pending |
| 07-02 / Task 1 | 07-02 | 2 | API-05, UI-05 | type-check + unit (FE) | `cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npx tsc --noEmit && npx vitest run` | Existing fixtures `frontend/__tests__/fixtures/sse.ts` updated; full FE suite is the gate | ⬜ pending |
| 07-02 / Task 2 | 07-02 | 2 | API-05, UI-05 | unit (FE) | `cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npx tsc --noEmit && npx vitest run __tests__/components/ChatApp.test.tsx __tests__/components/ChatApp.integration.test.tsx` | Existing tests cover `ChatApp.tsx`; full FE suite is the gate | ⬜ pending |
| 07-02 / Task 3 | 07-02 | 2 | API-05, OBS-02, UI-05 | integration (FE Vitest+MSW round-trip) | `cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npx tsc --noEmit && npx vitest run` | New file `frontend/__tests__/components/ChatApp.feedback.integration.test.tsx` (D-09 + D-11) | ⬜ pending |
| 07-03 / Task 1 | 07-03 | 3 | OBS-02 | docs (grep) | `grep -q "## Live Verification (Langfuse Feedback)" docs/data-sources.md && grep -q "express-surcharge-agent" docs/data-sources.md && grep -q "uvicorn" docs/data-sources.md` | Existing `docs/data-sources.md` extended | ⬜ pending |
| 07-03 / Task 2 | 07-03 | 3 | OBS-02 | docs (grep) | `grep -q "langfuse-feedback-score.png" docs/screenshots/.gitkeep` | Existing `docs/screenshots/.gitkeep` extended | ⬜ pending |
| 07-03 / Task 3 | 07-03 | 3 | OBS-02 | manual (HUMAN — see Manual-Only Verifications below) | (see Manual-Only Verifications) | New artifact `docs/screenshots/langfuse-feedback-score.png` (HUMAN-captured) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Existing infrastructure covers all phase requirements.

No Wave 0 setup is required for Phase 7. The phase reuses the already-installed Phase 5 stack verbatim:

- **Backend:** `pytest` + `fastapi.testclient` + the existing `app_with_mocks` (`backend/tests/test_api_chat.py:62-144`), `app_with_seeded_thread` (`backend/tests/test_api_conversations.py:60-152`), and `monkeypatch.setattr(fb_mod, ...)` patterns (`backend/tests/test_api_feedback.py:18-48`) are all in place.
- **Frontend:** `vitest 4.1.5` + `msw 2.13.6` + `@testing-library/react 16.3.x` + `@testing-library/user-event 14.x` are all installed (verified live in research). The MSW server (`frontend/__tests__/mocks/server.ts`), the SSE fixtures (`frontend/__tests__/fixtures/sse.ts`), the Map-backed Storage polyfill (`frontend/__tests__/setup.ts`), and the `installPauseThenResumeHandler` reference pattern (`frontend/__tests__/components/ChatApp.integration.test.tsx:78-99`) are all reusable verbatim.
- **Documentation:** `docs/data-sources.md` and `docs/screenshots/.gitkeep` already exist (Plan 05-07 D-19 / D-20).

The only "new" test infrastructure is the `frontend/__tests__/components/ChatApp.feedback.integration.test.tsx` file, which Plan 07-02 Task 3 creates from scratch using the established Vitest+MSW pattern. No framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live thumbs-up click produces `user_feedback` Score row in Langfuse | OBS-02 | Requires real Langfuse credentials (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST), a fresh-restarted uvicorn (per Quick 260503-rs8 — running server holds old `_make_config` in memory until recycled), a real backend instance, and a human-driven UI click. The appearance of a remote Score row in the Langfuse SaaS dashboard cannot be asserted from automated tests within free-tier quota constraints (Phase 7 D-13 — automated cloud verification was rejected for free-tier quota pollution + flakiness). | Follow the 6-step checklist in `docs/data-sources.md § Live Verification (Langfuse Feedback)` (added by Plan 07-03 Task 1). At a glance: 1) Restart uvicorn with LANGFUSE_* env vars; 2) Start frontend dev server; 3) Send `Surcharge for 15kg Bounce Bangkok to Nonthaburi`; 4) Click thumbs-up (`👍`, aria-label "Helpful"); 5) Open `https://cloud.langfuse.com` → Observations, filter on trace name `express-surcharge-agent`; 6) Confirm a `user_feedback` Score row with `value=1` appears on the matching `chat_turn_{thread_id}_{turn_idx}` trace; 7) Save screenshot to `docs/screenshots/langfuse-feedback-score.png`. (Optional Step 8: also exercise the resume-path fix by reloading, clicking the prior conversation in the sidebar, and clicking thumbs-up on the replayed message.) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (Plan 07-03 Task 3 is the only manual task; documented in Manual-Only Verifications above)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (Tasks 1-2 of Plan 07-03 are docs grep; Task 3 is manual but is the LAST task of the phase by design)
- [x] Wave 0 covers all MISSING references (no Wave 0 setup needed; existing infra covers everything)
- [x] No watch-mode flags
- [x] Feedback latency < 60s (BE quick run ~10s, FE quick run ~5s, full suite ~50s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved by gsd-planner 2026-05-04
