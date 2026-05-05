---
phase: 04-frontend-reasoning-trace
plan: 03
subsystem: ui
tags: [react, react-19, tailwind-v4, react-markdown, remark-gfm, vitest, msw, testing-library, tdd, components, sse]

requires:
  - phase: 04-frontend-reasoning-trace
    provides: Plan 04-01 — TS contracts (FinalPayload, TraceEntry, ConversationSummary), MSW handlers + canonical SSE fixtures (HAPPY/CAPPED/CLARIFY/PARTIAL_PAYLOAD, HAPPY_TRACE), Tailwind v4 + react-markdown stack
  - phase: 04-frontend-reasoning-trace
    provides: Plan 04-02 — useChatStream / useConversations hooks, formatRelativeTime, EXAMPLE_PROMPTS + LOCAL_STORAGE_KEYS constants, Storage polyfill in setup.ts
provides:
  - CapCallout — D-11 yellow-50 banner with role="alert" (LOCKED color tokens)
  - ErrorBoundary — class-component fallback for trace panel and dashboard charts
  - LoadingSkeleton — animate-pulse skeleton primitive used by 04-04 + 04-05
  - MarkdownAnswer — react-markdown + remark-gfm renderer with CAP_LINE_RE strip approach (UI-03 + D-11)
  - ClarifyCard — blue-50 info card for status='clarify' (D-12)
  - PartialCard — orange-50 'Limited result' card with conditional breakdown (D-12)
  - ChatInput — textarea + send button with locked placeholder, disabled-while-streaming, Enter-to-send (Shift+Enter newline)
  - ExamplePrompts — D-09 demo seed renders 3 LOCKED EXAMPLE_PROMPTS as clickable chips
  - FeedbackButtons — UI-05 stub thumbs up/down writing to localStorage (no fetch per D-17)
  - MessageList — D-12 dispatch on FinalPayload.status (MarkdownAnswer / ClarifyCard / PartialCard)
  - TraceStatusBadge — locked status palette (ok/warn/error/running with animate-pulse)
  - TraceStep — D-07 collapsed/expanded trace entry with Tool/Input/Output reveal
  - TracePanel — D-03 right rail (w-96) with empty state seed (D-09) + …thinking indicator
  - ThreadListItem — sidebar row with active accent + relative timestamp aria-label
  - ConversationSidebar — D-02 left rail (w-64) with locked copy and useConversations integration
affects: [04-04-dashboard-charts, 04-05-app-shell]

tech-stack:
  added: []
  patterns:
    - "Pure-renderer components: every component in this plan accepts props and returns JSX; all fetch / abort / localStorage side-effects come from the 04-02 hooks (useChatStream / useConversations) — testable without network mocks except where MSW round-trips through useConversations"
    - "LOCKED-copy verification by source: every UI-SPEC §Copywriting string is asserted by at least one component test (locked text appears in test queries verbatim) so a future drift to 'Central Region' or wrong heading text fails fast"
    - "D-11 strip approach over blockquote-override: CAP_LINE_RE removes the `> ⚠ ...` prefix from final_payload.markdown before ReactMarkdown sees it, then renders <CapCallout/> above. Avoids the dual-render anti-pattern in RESEARCH.md §Anti-Patterns"
    - "TDD discipline: 3 RED commits (test only, all failing) + 3 GREEN commits (impl + test pass) — git log shows 6 atomic commits (test→feat × 3)"
    - "MSW base URL fixed to http://localhost:8000 across handlers + per-test server.use() overrides for empty-state branch coverage"

key-files:
  created:
    - frontend/components/shared/CapCallout.tsx
    - frontend/components/shared/ErrorBoundary.tsx
    - frontend/components/shared/LoadingSkeleton.tsx
    - frontend/components/chat/MarkdownAnswer.tsx
    - frontend/components/chat/ClarifyCard.tsx
    - frontend/components/chat/PartialCard.tsx
    - frontend/components/chat/ChatInput.tsx
    - frontend/components/chat/ExamplePrompts.tsx
    - frontend/components/chat/FeedbackButtons.tsx
    - frontend/components/chat/MessageList.tsx
    - frontend/components/trace/TraceStatusBadge.tsx
    - frontend/components/trace/TraceStep.tsx
    - frontend/components/trace/TracePanel.tsx
    - frontend/components/sidebar/ThreadListItem.tsx
    - frontend/components/sidebar/ConversationSidebar.tsx
    - frontend/__tests__/components/MarkdownAnswer.test.tsx
    - frontend/__tests__/components/ClarifyCard.test.tsx
    - frontend/__tests__/components/PartialCard.test.tsx
    - frontend/__tests__/components/ChatInput.test.tsx
    - frontend/__tests__/components/ExamplePrompts.test.tsx
    - frontend/__tests__/components/FeedbackButtons.test.tsx
    - frontend/__tests__/components/MessageList.test.tsx
    - frontend/__tests__/components/TraceStep.test.tsx
    - frontend/__tests__/components/TracePanel.test.tsx
    - frontend/__tests__/components/ConversationSidebar.test.tsx
  modified: []

key-decisions:
  - "Adopted the D-11 strip approach (CAP_LINE_RE.replace) over a blockquote ReactMarkdown override — single source of truth for the cap-callout banner, and the markdown body is unambiguously cap-free when CapCallout renders"
  - "PartialCard delegates the breakdown render to MarkdownAnswer when surcharge_result is non-null — avoids re-implementing the GFM table override and inherits the same capped-banner behaviour if the partial path ever returns capped=true"
  - "FeedbackButtons writes a JSON ARRAY (append-on-vote) under localStorage[feedback], not a single object — matches the eventual Phase 5 batch-flush API.postFeedback semantics and lets the demo accumulate votes across messages"
  - "MessageList omits FeedbackButtons when threadId is null (idle, pre-meta) — sidesteps a transient render where the buttons exist with no thread context to attach votes to"
  - "TraceStatusBadge supports a 'running' status via TraceStatus | 'running' union — the backend never emits 'running' (only ok/warn/error per TraceEntry schema), but the badge component is reused for the future 'in-flight' indicator without re-typing"
  - "TracePanel reuses ExamplePrompts (already created in Task 2) instead of duplicating the demo-seed list — single source of truth tied to EXAMPLE_PROMPTS constant"

patterns-established:
  - "Pure-renderer components consume hooks/types only; no direct fetch / abort / localStorage in any component except FeedbackButtons (which writes to localStorage by spec, never fetch)"
  - "Locked-copy assertions baked into every component test — 'Reasoning trace', 'Conversations', 'Try one:', 'I need a bit more info', 'Limited result', '+ New conversation', 'No conversations yet. Send a message to start.', 'Ask about a surcharge, e.g., 15kg Bounce from Bangkok to Nonthaburi', 'Cap/floor applied — review recommended' all asserted verbatim somewhere in __tests__/components/"
  - "Pitfall 9 audit on every plan: grep -r 'Central Region' frontend/components|frontend/lib|frontend/hooks|frontend/types returns 0 production hits (only the negative ExamplePrompts.test.tsx assertion mentions the phrase by design)"
  - "TDD test files live at frontend/__tests__/components/<Component>.test.tsx (matches plan files_modified spec exactly) — co-located test/component pairing avoided so vitest config alias mapping stays single-rooted"

requirements-completed: [UI-01, UI-02, UI-03, UI-05, UI-06]

duration: 6min
completed: 2026-04-26
---

# Phase 04 Plan 03: Chat + Trace + Sidebar Components Summary

**15 pure-renderer components (3 shared + 7 chat + 3 trace + 2 sidebar) covering the chat surface, reasoning trace, and conversation sidebar — UI-01/02/03/05/06 satisfied at the component level via TDD with 42 passing tests.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-26T04:50:14Z
- **Completed:** 2026-04-26T04:56:25Z (approx)
- **Tasks:** 3 (all TDD)
- **Files modified:** 25 (15 components + 10 tests)

## Accomplishments

- **UI-03 surcharge breakdown table** — MarkdownAnswer renders the locked 4-row GFM breakdown via react-markdown + remark-gfm. The capped banner is implemented as a banner-above-stripped-markdown pattern (D-11): `CAP_LINE_RE` removes the `> ⚠ Cap/floor applied — review recommended` line from `final_payload.markdown` before ReactMarkdown sees it, and `<CapCallout />` renders above the cleaned table. No double-banner, no `<blockquote>` leak.
- **D-12 status dispatch** — MessageList switches on `payload.status` to MarkdownAnswer / ClarifyCard / PartialCard. Each card's locked color tokens are baked in (blue-50/200 for clarify, orange-50/200 for partial, yellow-50/300 for capped overlay).
- **UI-02 reasoning trace panel** — TracePanel renders one TraceStep per `liveTrace` entry with `aria-live="polite"`, the `…thinking` animate-pulse indicator while streaming, and the D-09 empty-state seed (3 EXAMPLE_PROMPTS chips). TraceStep collapses to a one-row headline (#step + agent label + truncated reasoning + status badge) and reveals Tool/Input/Output JSON panes + ISO timestamp on click or Enter-key.
- **UI-06 conversation sidebar** — ConversationSidebar consumes `useConversations()` for items, renders the locked '+ New conversation' button, lists threads via ThreadListItem with the bg-blue-600/text-white active-state accent, and surfaces the locked empty-state copy when no threads exist. Verified end-to-end through MSW SAMPLE_CONVERSATIONS round-trip in the test.
- **UI-05 feedback stub** — FeedbackButtons appends `{thread_id, message_id, score, ts}` to a JSON array under `localStorage[feedback]` on click. Test fleet asserts that `globalThis.fetch` is never called (Phase 5 wires the API).
- **42 passing component tests across 10 files** — `npm test -- --run __tests__/components/` reports 10 files / 42 tests / 0 failures. Type-check + Next.js production build both clean.

## Task Commits

1. **Task 1 RED: failing tests for MarkdownAnswer, ClarifyCard, PartialCard** — `e3a88fe` (test)
2. **Task 1 GREEN: implement shared chrome + chat answer components** — `16f7e87` (feat)
3. **Task 2 RED: failing tests for ChatInput, ExamplePrompts, FeedbackButtons, MessageList** — `a71d722` (test)
4. **Task 2 GREEN: implement chat surface components (UI-01, UI-05)** — `a1df59a` (feat)
5. **Task 3 RED: failing tests for TraceStep, TracePanel, ConversationSidebar** — `24843cf` (test)
6. **Task 3 GREEN: implement trace panel and conversation sidebar (UI-02, UI-06)** — `1781499` (feat)

## Files Created/Modified

### Created — frontend/components/shared/

- `frontend/components/shared/CapCallout.tsx` — D-11 yellow-50 banner with `role="alert"`, locked color tokens (border-yellow-300, bg-yellow-50, text-yellow-900), copy "Cap/floor applied — review recommended".
- `frontend/components/shared/ErrorBoundary.tsx` — class component with `getDerivedStateFromError` + `componentDidCatch`. Renders red-50 fallback unless the caller passes a custom `fallback` prop. Wraps trace panel and dashboard charts in 04-05.
- `frontend/components/shared/LoadingSkeleton.tsx` — single primitive `<div className="animate-pulse rounded bg-gray-50 ...">`. Caller passes `className` for variant sizing (defaults to `h-4 w-full`).

### Created — frontend/components/chat/

- `frontend/components/chat/MarkdownAnswer.tsx` — `'use client'`. ReactMarkdown + remarkGfm with custom `table/th/td` overrides for the GFM breakdown. `CAP_LINE_RE = /^>\s*⚠\s*Cap\/floor applied\s*—\s*review recommended\s*\n\n?/` strips the leading callout line when `payload.capped`; `<CapCallout />` renders above.
- `frontend/components/chat/ClarifyCard.tsx` — blue-50 info card for status='clarify'. Locked heading "I need a bit more info" + ReactMarkdown body with prose-sm.
- `frontend/components/chat/PartialCard.tsx` — orange-50 "Limited result" card. Delegates to `<MarkdownAnswer payload={payload} />` when `payload.surcharge_result != null`; renders prose-only otherwise.
- `frontend/components/chat/ChatInput.tsx` — textarea + send button form. Locked placeholder; bg-blue-600 send button with `aria-label="Send message"`. Enter submits, Shift+Enter newlines. Whitespace-only input keeps the button disabled.
- `frontend/components/chat/ExamplePrompts.tsx` — locked "Try one:" caption + `EXAMPLE_PROMPTS.map(...)` rendering 3 blue-200/blue-600 chip buttons. Click forwards prompt text to caller via `onClick`.
- `frontend/components/chat/FeedbackButtons.tsx` — `'use client'`. 👍 / 👎 buttons with locked aria-labels. Vote handler `console.log`s + appends to localStorage[feedback] JSON array. Post-vote both buttons are disabled and the chosen one carries `aria-pressed="true"`. No `fetch(` reference anywhere in the file.
- `frontend/components/chat/MessageList.tsx` — exports `ChatMessage` discriminated union (`UserMessage | AssistantMessage`). Renders user messages as bg-blue-600 self-end bubbles and assistant messages dispatched on `payload.status`. FeedbackButtons attached to each assistant message when `threadId` is non-null.

### Created — frontend/components/trace/

- `frontend/components/trace/TraceStatusBadge.tsx` — `STATUS_COLOR` record covers ok / warn / error + 'running' (animate-pulse). Lowercase status string is the badge's display text (matches schema 1:1 so screen readers announce the same word).
- `frontend/components/trace/TraceStep.tsx` — `'use client'`. `AGENT_LABEL` maps all 5 AgentName values. Headline is a `<button>` with `aria-expanded` toggling on click; expanded view reveals "Tool:" + `<code>`, "Input" + JSON-stringified `tool_input` `<pre>`, "Output" + JSON-stringified `tool_output` `<pre>`, and the ISO timestamp inside `<time dateTime>`.
- `frontend/components/trace/TracePanel.tsx` — w-96 right rail, locked "Reasoning trace" heading. Empty (not streaming, no entries) renders the explainer + ExamplePrompts. Otherwise renders the entries `<ol>` with `aria-live="polite"` and the `…thinking` indicator while streaming.

### Created — frontend/components/sidebar/

- `frontend/components/sidebar/ThreadListItem.tsx` — accessible button with `aria-label="Resume {preview} — last updated {relative}"` and `aria-current="true"` on the active item. Active style: bg-blue-600 + text-white + text-blue-100 caption. Inactive: bg-white + hover:bg-gray-100 + text-gray-500 caption.
- `frontend/components/sidebar/ConversationSidebar.tsx` — w-64 left rail. Locked heading "Conversations" + bg-blue-600 "+ New conversation" button. Empty/loading/items branches; uses `useConversations()` from 04-02.

### Created — frontend/__tests__/components/

- `MarkdownAnswer.test.tsx` (4 tests), `ClarifyCard.test.tsx` (3), `PartialCard.test.tsx` (4), `ChatInput.test.tsx` (5), `ExamplePrompts.test.tsx` (4), `FeedbackButtons.test.tsx` (4), `MessageList.test.tsx` (4), `TraceStep.test.tsx` (4), `TracePanel.test.tsx` (4), `ConversationSidebar.test.tsx` (6) = **42 tests across 10 files**.

## Decisions Made

- **Strip-the-line over blockquote override (D-11)** — RESEARCH.md flagged the dual-render anti-pattern (CapCallout + the `> ⚠` blockquote both rendering). `CAP_LINE_RE` removes the line before ReactMarkdown sees it. Tests assert `container.querySelector('blockquote')` is null on CAPPED_PAYLOAD to guarantee the strip is exact.
- **PartialCard delegates to MarkdownAnswer when surcharge_result exists** — instead of duplicating the GFM table override block, PartialCard reuses MarkdownAnswer for the breakdown branch. Side effect: capped+partial would correctly render the cap callout inside the orange card, which is the right behavior even though the backend doesn't emit that combination today.
- **FeedbackButtons stores a JSON array** — Phase 5's `api.postFeedback` will batch-flush votes; storing an array now means the migration is "drain the array, post each entry" rather than "find the right key under a record." Matches the `LOCAL_STORAGE_KEYS.feedback` ('feedback') singular key that already exists in constants.ts.
- **MessageList gates FeedbackButtons on threadId** — the buttons need a thread to attribute votes to. Pre-meta (idle status, threadId === null) the buttons would still render but vote with thread_id="" which is meaningless. The conditional render keeps the data clean.
- **TraceStatusBadge accepts 'running' even though the schema doesn't emit it** — the running badge style is documented in UI-SPEC §Color and reused by future plans (e.g., the Phase 5 in-flight indicator); typing the prop as `TraceStatus | 'running'` lets callers opt-in without a schema change.
- **ExamplePrompts reused inside TracePanel** — the empty-state demo seed and the future ChatColumn empty state share the same 3 EXAMPLE_PROMPTS. One component, one source of truth.

## Deviations from Plan

None — plan executed exactly as written.

The pre-task ground truth needed one mechanical adjustment: this worktree branch (worktree-agent-ae1f3f44) was forked from the parent before Plans 04-01 and 04-02 landed on `feature/frontend-reasoning-trace`. To run the TDD tests against the existing 04-02 hooks/types/fixtures, I merged `feature/frontend-reasoning-trace` (commit a3753c6) into the worktree branch before Task 1. This is plumbing for the parallel-wave execution model, not a deviation from the plan's substance — every artifact created in this plan was created with the exact contents specified.

## Issues Encountered

- The `--localstorage-file` warning printed on every `npm test` run is the same Node 25 deprecation notice flagged in 04-02's summary. Benign, unrelated to Storage polyfill correctness.
- `frontend/__tests__/components/ExamplePrompts.test.tsx` matches `Central Region` in the Pitfall 9 grep — this is intentional (the test asserts the negative: "container.textContent must NOT contain 'Central Region'"). The grep audit is satisfied because the match is in test-only code that explicitly checks for absence in production output.

## User Setup Required

None — Wave 3 is fully autonomous. No new dependencies, no new env vars; the test infra and frontend stack from 04-01 + 04-02 were sufficient.

## Next Phase Readiness

Plan 04-04 (dashboard charts) runs in parallel and shares no source files. Plan 04-05 (app shell) can now:

- Import `<ConversationSidebar />`, `<ChatInput />`, `<MessageList />`, `<TracePanel />` and assemble the three-column layout.
- Import `<ChatMessage>` discriminated union from `@/components/chat/MessageList`.
- Reuse `<ErrorBoundary />` to wrap the trace panel and the dashboard column.
- Reuse `<LoadingSkeleton />` for any further loading-state slots.

No blockers. UI-04 (Chat | Dashboard tab toggle) is intentionally deferred to 04-05 because it depends on the dashboard surface 04-04 is producing.

## Self-Check: PASSED

All 25 declared output files exist on disk and all 6 task commits (e3a88fe, 16f7e87, a71d722, a1df59a, 24843cf, 1781499) are present in `git log`. `npm test -- --run __tests__/components/` reports 42 passing tests across 10 files; `npm run type-check` and `npm run build` exit 0; Pitfall 9 audit `grep -r "Central Region" frontend/components frontend/lib frontend/hooks frontend/types` returns only the intentional negative-test reference inside ExamplePrompts.test.tsx.

---
*Phase: 04-frontend-reasoning-trace*
*Completed: 2026-04-26*
