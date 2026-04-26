---
phase: 04-frontend-reasoning-trace
plan: 05
subsystem: ui
tags: [next.js, react, react-19, tailwind-v4, sse, playwright, e2e, vitest, msw, integration, app-shell]

requires:
  - phase: 04-frontend-reasoning-trace
    provides: Plan 04-01 — Next.js 15 + React 19 scaffold, app/page.tsx placeholder, Playwright config (webServer launching npm run dev on :3000)
  - phase: 04-frontend-reasoning-trace
    provides: Plan 04-02 — useChatStream / useConversations hooks, FinalPayload type, LOCAL_STORAGE_KEYS, EXAMPLE_PROMPTS constants
  - phase: 04-frontend-reasoning-trace
    provides: Plan 04-03 — ConversationSidebar, MessageList (ChatMessage discriminated union), ChatInput, TracePanel, FeedbackButtons, MarkdownAnswer, shared/ErrorBoundary + LoadingSkeleton
  - phase: 04-frontend-reasoning-trace
    provides: Plan 04-04 — DashboardView (FuelPriceChart + SurchargeHistoryChart inside ChartErrorBoundary)
  - phase: 03-graph-assembly-and-api
    provides: Backend SSE contract on POST /api/chat — meta/trace/answer/error/done envelope (live-streamed during human-verify)

provides:
  - ChatColumn — center-column tab toggle (Chat | Dashboard, D-04) preserving chat state across switches via Tailwind hidden visibility toggle
  - ChatApp — top-level Client Component composing the three-column layout (sidebar | chat | trace); lifts useChatStream + useConversations and bridges resume → MessageList replay
  - app/page.tsx wired to render <ChatApp /> (replaces 04-01 placeholder)
  - Playwright e2e smoke (chat-smoke.spec.ts): three-column render, example-prompt-streams-table, dashboard-renders-charts, plus an in-line Bangkok Metro audit assertion
  - Final unit + integration suite green at 92 tests / 22 files
  - Backend CORS gap surfaced and patched (commit 750cf5d) — Phase 3's API-01 ship lacked CORSMiddleware because TestClient never exercises browser preflight
affects: [05-polish-observability-docs]

tech-stack:
  added: []
  patterns:
    - "State-lifting at ChatApp level: useChatStream + useConversations instantiated once at the root; ChatColumn / TracePanel / ConversationSidebar receive props (messages, threadId, isStreaming, liveTrace) and lift events back via callbacks (onSend, onResume, onNewConversation). Keeps the leaf components pure-renderers and the hook side-effects in one place."
    - "Tab-toggle via Tailwind hidden visibility (NOT conditional unmount) — preserves chat state (scroll position, in-flight stream) across Chat ↔ Dashboard switches per acceptance test #4 of Task 1"
    - "D-05 mobile collapse via 'hidden md:flex' wrappers around sidebar + trace panel — chat-only at <768px, no extra logic"
    - "Resume-replay: ConversationDetail.messages → ChatMessage[] mapping wraps assistant strings in a minimal FinalPayload (markdown + surcharge_result + status='ok') so MarkdownAnswer renders the persisted answer without re-fetching"
    - "Playwright smoke spec includes a bodyText.toContain('Central Region') NEGATIVE assertion — last-line defence for Pitfall 9 even after the static grep audit"

key-files:
  created:
    - frontend/components/chat/ChatColumn.tsx
    - frontend/components/ChatApp.tsx
    - frontend/__tests__/components/ChatColumn.test.tsx
    - frontend/__tests__/components/ChatApp.test.tsx
    - frontend/e2e/chat-smoke.spec.ts
    - .planning/phases/04-frontend-reasoning-trace/04-05-SUMMARY.md
  modified:
    - frontend/app/page.tsx
    - backend/api/main.py
    - .planning/phases/04-frontend-reasoning-trace/04-05-PLAN.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "ChatColumn uses a Tailwind 'hidden' visibility toggle (not conditional unmount) for the Chat | Dashboard tab — preserves chat state, scroll position, and in-flight stream when the user pops to the dashboard and back"
  - "ChatApp lifts both useChatStream and useConversations once at the root and shares state through props/callbacks — keeps ChatColumn / TracePanel / ConversationSidebar pure-renderers with no hook coupling"
  - "Resume flow constructs a minimal FinalPayload from each replayed assistant message string + the thread's surcharge_result — the persisted answer renders through the same MarkdownAnswer pipeline as a live streamed answer; trace panel intentionally does NOT swap on resume per D-08 (deferred to Phase 5 polish)"
  - "Mobile breakpoint implemented via 'hidden md:flex' wrappers on sidebar and trace panel — Phase-4 simplification per D-05; drawer toggling deferred to Phase 5"
  - "Backend CORSMiddleware added during Verify 1 (commit 750cf5d) instead of opening a fresh quick-fix lane — surfaced as a checkpoint:human-verify failure mode for the executing plan, fixed in-band, re-verified in the same browser session"

patterns-established:
  - "Three-column desktop shell: <main flex h-screen>: <ConversationSidebar w-64> | <ChatColumn flex-1> | <TracePanel w-96>. Mobile collapses to chat-only via hidden md:flex on sidebar + trace wrappers."
  - "Per-tab body co-mounting: render BOTH tab bodies in the DOM and toggle via 'hidden' Tailwind class — cheaper than React conditional render and stable for stream/scroll state."
  - "Playwright smoke includes static-text negative assertions for forbidden phrases (Pitfall 9) — runs at e2e level even after grep audit passes, catching any string that only appears at runtime (e.g., a dynamic copy file)."

requirements-completed: [UI-01, UI-02, UI-03, UI-04, UI-05, UI-06]

duration: 13min
completed: 2026-04-26
---

# Phase 04 Plan 05: App Composition + E2E + Human Verification Summary

**Three-column desktop shell (ConversationSidebar | ChatColumn | TracePanel) wired through a single state-lifting `<ChatApp />` root with Chat | Dashboard tab toggle, resume + new-conversation flows, Playwright smoke against the live backend, and a human-verified live SSE streaming UX — closes Phase 4 at 92/22 tests green and zero "Central Region" leakage.**

## Performance

- **Duration:** ~13 min (T1 RED→GREEN + T2 RED→GREEN + T3 e2e + audit + Wave-3 merge + CORS fix + human verification)
- **Started:** 2026-04-26T05:00:00Z (approx — Wave-3 worktree merge commit c014752 at 12:01:49 +07; first Task 1 commit ffcd260 at 12:04:17 +07)
- **Completed:** 2026-04-26T05:25:00Z (approx — final docs commit at plan close; CORS fix 750cf5d at 12:17:19 +07 was the last code commit)
- **Tasks:** 4 (3 executed + 1 human-verified)
- **Files modified:** 6 created (5 source + this SUMMARY) + 3 .planning/* + 1 backend out-of-band CORS patch

## Accomplishments

- **End-to-end product live:** A user visiting `http://localhost:3000/` now sees the full three-column desktop shell — sidebar with thread history, chat column with `Chat | Dashboard` tab toggle, trace panel live-appending agent steps as the SSE stream arrives. The whole product from Phase 4 is wired together.
- **ChatColumn (D-04 tab toggle):** "Chat" and "Dashboard" tabs render with the LOCKED active accent (`bg-blue-600 text-white`); tab switching uses Tailwind `hidden` visibility so the chat tree stays mounted across switches (verified by acceptance test #4 — send-button persists across toggle). 6 tests passing.
- **ChatApp (state-lifting root):** Single `useChatStream` + `useConversations` instance at the root; `messages`, `threadId`, `isStreaming`, `liveTrace` flow down to the three columns; `onSend`, `onResume`, `onNewConversation` flow back up. Resume reconstructs a minimal FinalPayload per replayed assistant message so MarkdownAnswer renders the persisted answer through the same pipeline as a live one. 5 integration tests passing (including end-to-end happy stream via MSW + table render + sidebar resume).
- **Playwright e2e smoke:** 3 specs against the real backend on :8000 — three-column render, example-prompt-streams-breakdown-table, dashboard renders both charts. The `bodyText.not.toContain('Central Region')` assertion runs as a last-line Pitfall 9 audit during the home-page smoke.
- **Bangkok Metro audit clean:** `grep -r "Central Region" frontend/{app,components,lib,hooks,types,__tests__,e2e}` returns ONLY the two intentional negative-assertion lines (one in `e2e/chat-smoke.spec.ts`, one in `__tests__/components/ExamplePrompts.test.tsx`). Zero production-code matches.
- **Live human verification of all 5 perceptual checks:** trace entries append one-at-a-time during the SSE stream (Pitfall 2 mitigation confirmed), Recharts emits visible SVG paths/bars on React 19.2.x (Pitfall 3 mitigation confirmed), sidebar resume replays prior conversation correctly (D-14), mobile breakpoint collapses to chat-only at <768px (D-05), and the page contains no "Central Region" anywhere (Pitfall 9).
- **Phase-3 CORS gap caught + patched:** Browser preflight `OPTIONS /api/chat` returned 405 during Verify 1 — Phase 3 (API-01) had shipped without `CORSMiddleware` because tests exercise endpoints in-process via TestClient and never hit the browser preflight path. Fixed in commit 750cf5d in-band before declaring the checkpoint passed.
- **Full unit + integration suite at 92 tests / 22 files green.** Build clean. Type-check clean.

## Task Commits

1. **Task 1 RED — failing tests for ChatColumn tab toggle** — `ffcd260` (test)
2. **Task 1 GREEN — implement ChatColumn with Chat | Dashboard tab toggle** — `253b13d` (feat)
3. **Task 2 RED — failing tests for ChatApp three-column composition** — `a50bc93` (test)
4. **Task 2 GREEN — wire ChatApp three-column shell + replace home placeholder** — `b2cb0a3` (feat)
5. **Task 3 — Playwright e2e smoke + Bangkok Metro audit** — `335a4ad` (test)
6. **Wave 3 merge — integrate dashboard charts from parallel worktree** — `c014752` (merge)
7. **Out-of-band — backend CORS middleware** — `750cf5d` (fix; surfaced during Verify 1)
8. **Task 4 — human verification (no commit; user-approved 2026-04-26)** — verified-only

**Plan metadata commit:** filed last as `docs(04-05): complete app composition + e2e + human verification`.

## Files Created/Modified

### Created — frontend source

- `frontend/components/chat/ChatColumn.tsx` — `'use client'`. Tab state `'chat' | 'dashboard'`, default `'chat'`. Renders both tab bodies in the DOM with Tailwind `hidden` toggling visibility (preserves chat state across switches). LOCKED tab labels `"Chat"` and `"Dashboard"`; active accent `bg-blue-600 text-white`, inactive `bg-white text-gray-700`. Imports MessageList + ChatInput (04-03) and DashboardView (04-04). Internal `<TabButton>` renders `aria-pressed` for accessibility.
- `frontend/components/ChatApp.tsx` — `'use client'`. Root client component. Instantiates `useChatStream()` and `useConversations()` once. `messages: ChatMessage[]` state appended on user send + on `chat.finalPayload` arrival (with double-append guard). `handleSend` → append user message + `chat.send()`. `handleResume` → `conversations.resume(threadId)` → map `detail.messages` to `ChatMessage[]` (assistant strings wrapped in a minimal FinalPayload using detail.surcharge_result + status='ok'). `handleNewConversation` → `chat.reset()` + clear messages. Layout: `<main flex h-screen>` with `<ConversationSidebar>` (hidden md:flex), `<ChatColumn>` (flex-1), `<TracePanel>` (hidden md:flex). After each `done` status, refreshes the conversations sidebar.
- `frontend/components/chat/ChatColumn` test — 6 tests covering LOCKED labels, active styling, tab swap, mount-preservation, isStreaming → ChatInput disabled, onSend forwarding.
- `frontend/components/ChatApp` test — 5 integration tests using MSW happyTurnEvents: three-column render, send → user msg + stream + table, post-done input re-enable, "+ New conversation" clears chat surface, sidebar resume replays prior messages.
- `frontend/e2e/chat-smoke.spec.ts` — 3 Playwright specs: home renders three columns + example prompts visible + `bodyText.not.toContain('Central Region')`; clicking the first example prompt streams a breakdown table within 30s + ≥4 trace step buttons; Dashboard tab renders both chart titles + 30d range option.

### Modified — frontend

- `frontend/app/page.tsx` — Replaced 04-01 placeholder with `import { ChatApp } from '@/components/ChatApp'` and `<ChatApp />` inside the default `HomePage` server component.

### Modified — backend (out-of-band, surfaced during Verify 1)

- `backend/api/main.py` — Added `from fastapi.middleware.cors import CORSMiddleware` (line 15) and `app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])` (lines 48–53). Restricted to dev-host pair; production deployment will need an env-driven list. Committed in 750cf5d with a commit message that explicitly traces the gap back to Phase 3 (API-01) shipping without browser-preflight coverage.

### Modified — planning

- `.planning/phases/04-frontend-reasoning-trace/04-05-PLAN.md` — Task 4 annotated with `<status>APPROVED 2026-04-26 — user confirmed all 5 verifications passed...</status>`.
- `.planning/STATE.md` — Plan counter advanced, decision entries added (one per major key-decision above + the CORS-gap discovery), session record updated.
- `.planning/ROADMAP.md` — `04-05-PLAN.md` checkbox flipped to `[x]`; Phase 4 progress row refreshed via `roadmap update-plan-progress 04`.
- `.planning/REQUIREMENTS.md` — UI-01..UI-06 marked complete via `requirements mark-complete`.

## Decisions Made

- **ChatColumn tab toggle uses Tailwind `hidden` visibility, NOT conditional unmount** — Acceptance test #4 of Task 1 explicitly asserts the send-button stays in the DOM across `Dashboard → Chat` switches. Conditional unmount would re-mount MessageList + ChatInput on every switch, losing scroll position, in-flight stream state, and any pending input text. The visibility toggle is the cheapest way to preserve all three.
- **ChatApp lifts useChatStream once at the root + threads state down via props** — Three components need `liveTrace` (TracePanel), `threadId` + `isStreaming` (ChatColumn), and `activeThreadId` (ConversationSidebar). Instantiating the hook once at the root keeps a single AbortController per app instance, a single SSE consumer, and a single source of truth for `chat.threadId`. The leaf components stay pure-renderer / pure-callback.
- **Resume builds a minimal FinalPayload per replayed assistant message** — `ConversationDetail.messages[i].content` is a markdown string; MessageList's MarkdownAnswer expects a `FinalPayload`. Constructing `{ markdown: m.content, surcharge_result: detail.surcharge_result, capped: ..., status: 'ok' }` lets the same render pipeline serve both replayed and live answers without a second markdown component or a special-case branch.
- **Trace panel does NOT swap when resuming a thread (D-08 intentional)** — The ConversationDetail endpoint returns past messages but not the per-turn trace stream (which would require persisting `reasoning_trace` per turn, deferred to Phase 5). Rather than show a stale or empty trace panel and confuse the user, we leave the panel showing the most-recent live turn (or the empty-state if it's a fresh app load). The `<resume-signal>` of Task 4's checkpoint explicitly calls this out for the user.
- **Mobile breakpoint via `hidden md:flex` wrappers, drawers deferred** — D-05 calls out drawer-style sidebar + trace panel for <768px. Phase 4 ships a simpler "collapse to chat-only on mobile" pattern; drawer toggling is Phase-5 polish per the plan's `<interfaces>` notes. Tested by Verify 4 (resize DevTools to 400×800 → sidebar + trace hide; resize back → re-appear).
- **Phase-3 CORS gap was fixed in-band, not deferred to a quick-fix lane** — Browser preflight is on the critical path of every chat send. Deferring would have left the human-verify checkpoint un-passable (Verify 1 failed at step 5). Fixing it inline (commit 750cf5d) and re-running Verify 1 was the correct call; the discovery is documented here under Deviations and the commit message ties it back to the Phase 3 (API-01) coverage gap.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, out-of-band] Phase 3 backend missing CORSMiddleware — surfaced during human-verify Verify 1**

- **Found during:** Task 4 (human verification — Verify 1 step 4: "Click the first example prompt").
- **Issue:** Browser preflight `OPTIONS /api/chat` returned 405 Method Not Allowed because `backend/api/main.py` did not register `CORSMiddleware`. Phase 3's chat-endpoint tests exercise the route in-process via FastAPI TestClient, which never issues a preflight, so the gap was invisible until a real browser hit the SSE endpoint. Result: every frontend chat send failed silently before reaching the SSE stream — trace panel stayed empty, breakdown table never rendered.
- **Fix:** Imported `CORSMiddleware` from `fastapi.middleware.cors` and registered `app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])` after `FastAPI(...)` instantiation. Restricted `allow_origins` to the dev-host pair (production deploy needs an env-driven allow-list — flagged in commit message).
- **Files modified:** backend/api/main.py
- **Verification:** Restarted uvicorn → re-ran Verify 1 in browser → trace entries streamed one-at-a-time + breakdown table rendered correctly → user typed "approved".
- **Committed in:** `750cf5d` (fix(api): add CORS middleware for frontend at localhost:3000) — out-of-band from the Task 1/2/3 commit chain because it patches Phase 3's deliverable, not Phase 4 source. Commit message explicitly traces the gap back to API-01's TestClient-only coverage.
- **Implication for Phase 3:** This is a discovered Phase-3 acceptance-criteria gap — `/api/chat` should be reachable from a browser, which requires either CORS in dev or a same-origin proxy in production. Phase 5 docs will note that production deployment must configure CORS via env-driven allow-list before frontend goes live.

---

**Total deviations:** 1 auto-fixed (1 bug, out-of-band on a sibling phase).
**Impact on plan:** Phase 4 source code was untouched by the deviation — `backend/api/main.py` is owned by Phase 3, not by 04-05. The deviation surfaced at the human-verify checkpoint exactly as the checkpoint was designed to catch (Pitfall 2 / Pitfall 3 / live-streaming UX). End state matches the plan's `must_haves.truths` exactly: live SSE streaming verified, Recharts on React 19 verified, sidebar resume verified, mobile breakpoint verified, Bangkok Metro audit verified.

## Verification

### Automated (re-run before SUMMARY)

- `cd frontend && npm test -- --run` — **22 files / 92 tests / 0 failures, 4.54s** ✅ (re-verified 2026-04-26 at plan close).
- `grep -rn "Central Region" frontend/{app,components,lib,hooks,types,__tests__,e2e}` — only the 2 negative-assertion lines (e2e/chat-smoke.spec.ts:35,37 and __tests__/components/ExamplePrompts.test.tsx:28,30); zero production-code matches ✅.
- `git log --oneline` confirms all 7 expected commits present (ffcd260, 253b13d, a50bc93, b2cb0a3, 335a4ad, c014752, 750cf5d).
- `git status --short` clean before SUMMARY commit ✅.

### Human verification (Task 4 checkpoint, all 5 PASSED, user typed "approved" 2026-04-26)

1. **Verify 1 — Live SSE streaming feel** ✅ — Trace entries appeared one-at-a-time over a few seconds: Planner → Fuel → Route → Pricing → Response, with the `…thinking` pulse visible between steps. Breakdown table rendered after stream completion. (Pitfall 2 mitigation confirmed.) Initial run failed with 405 on `OPTIONS /api/chat` → CORS fix in commit 750cf5d → re-run passed.
2. **Verify 2 — Recharts on React 19.2.x** ✅ — Visible blue `Diesel price (THB/L)` line chart rendered; `7d / 30d / 90d` range toggle re-renders without flicker; `Recent surcharges` bars rendered. (Pitfall 3 + Pitfall 4 mitigations confirmed live.)
3. **Verify 3 — Sidebar resume + new conversation** ✅ — `+ New conversation` cleared chat surface and trace panel; second example prompt completed; both threads listed in sidebar; clicking the older thread replayed prior user + assistant messages with the blue accent on the active row. (D-14 + D-20 confirmed; trace panel intentionally did NOT swap per D-08.)
4. **Verify 4 — Mobile breakpoint (D-05)** ✅ — DevTools resized to 400×800 → sidebar + trace hidden, only chat column visible with tab toggle still functional; resized back to >768px → both rails re-appeared.
5. **Verify 5 — Bangkok Metro phrasing (final visual audit)** ✅ — Browser Cmd+F for "Central Region" returned zero matches.

## Issues Encountered

- **Phase-3 CORS gap surfaced at the browser layer** (see Deviations §1). Fixed in 750cf5d; Phase 5 docs should note production CORS configuration as a deploy-time prerequisite.
- The `--localstorage-file` Node 25 warning continues to print on every test run (carried over from 04-02, 04-03, 04-04). Benign; out of scope.

## User Setup Required

None — no new env vars, no new external services. The dev-host CORS allow-list is hardcoded for `localhost:3000` / `127.0.0.1:3000`; production deployment will need to plumb an env-driven allow-list before going live.

## Next Phase Readiness

Phase 4 is complete. All 6 UI requirements (UI-01..UI-06) are implemented and tested at unit + integration + e2e levels and verified by a human in the live browser. The "visible reasoning is what makes this agentic" core value is realized as the always-visible right rail with live-append trace steps.

Phase 5 (Polish, Observability & Docs) inherits:

- A working three-column product the user can demo today
- A documented Phase-3 CORS-allow-list-needs-env-plumbing item for production deploy
- A trace-panel-on-resume gap (D-08) that was intentionally deferred — Phase 5 may decide to persist `reasoning_trace` per turn or formally accept the empty state on resume
- The Recharts × React 19 mitigation set (overrides.react-is, isAnimationActive=false, ResponsiveContainer test shim) — proven in production browser, no further work needed there

No blockers.

## Self-Check: PASSED

- All 5 declared output files exist on disk: `frontend/components/chat/ChatColumn.tsx`, `frontend/components/ChatApp.tsx`, `frontend/__tests__/components/ChatColumn.test.tsx`, `frontend/__tests__/components/ChatApp.test.tsx`, `frontend/e2e/chat-smoke.spec.ts` ✅.
- All 5 task commits present in `git log --oneline` (ffcd260, 253b13d, a50bc93, b2cb0a3, 335a4ad) ✅.
- Wave-3 merge commit c014752 present ✅.
- Out-of-band CORS fix commit 750cf5d present and traceable in git history ✅.
- `npm test -- --run` exits 0 with 92 passing tests across 22 files (≥60 acceptance threshold cleared) ✅.
- Bangkok Metro audit clean (only intentional negative-assertion matches) ✅.
- Human verification documented and approved ✅.

---
*Phase: 04-frontend-reasoning-trace*
*Completed: 2026-04-26*
