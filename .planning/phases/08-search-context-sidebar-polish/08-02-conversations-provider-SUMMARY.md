---
phase: 08-search-context-sidebar-polish
plan: 02
subsystem: ui
tags: [react, context, hooks, vitest, msw, audit-issue-4]

# Dependency graph
requires:
  - phase: 04-frontend-reasoning-trace
    provides: useConversations hook, ConversationSidebar, SurchargeHistoryChart, ChatApp three-column layout
  - phase: 06-hitl-approval-ui-wiring
    provides: ChatApp.integration.test.tsx (D-15.3 approve/deny baseline)
provides:
  - ConversationsProvider Context-backed shared instance for the conversations list
  - useConversations() throws when called outside the provider
  - ChatApp split into outer ChatApp (provider mount) + ChatAppInner (consumer) per Pitfall 1
  - D-14 sidebar-refresh integration test as drift-prevention layer
affects: [phase-08-verify, future-frontend-work, audit-followups]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - React Context provider colocated with the hook in a single .tsx file (D-06)
    - useMemo on context value to stabilize identity for consumer effect deps (Pitfall 3)
    - renderHook { wrapper } pattern for context-backed hooks (Pitfall 2)
    - Outer/inner component split (ChatApp / ChatAppInner) so consumers sit below the provider (Pitfall 1)

key-files:
  created: []
  modified:
    - frontend/hooks/useConversations.tsx (renamed from .ts via git mv; now exports ConversationsProvider + useConversations)
    - frontend/components/ChatApp.tsx (split: outer ChatApp mounts provider, inner ChatAppInner consumes; deps narrowed to conversations.refresh)
    - frontend/__tests__/hooks/useConversations.test.tsx (renderHook wrapped in <ConversationsProvider>)
    - frontend/__tests__/components/ChatApp.integration.test.tsx (added D-14 sidebar-refresh test, +1 test → 3 total)
    - frontend/__tests__/components/ConversationSidebar.test.tsx (renderWithProvider helper added — Rule 1 fix)
    - frontend/__tests__/components/SurchargeHistoryChart.test.tsx (renderWithProvider helper added — Rule 1 fix)

key-decisions:
  - "Plan 08-02: ConversationsProvider colocated with useConversations in a single .tsx file (D-06) — two named exports preserve a clean import surface; provider sentinel is `null` (not a default object) so wrapper hook can detect 'called outside provider' and throw a clear error"
  - "Plan 08-02: ChatApp split into outer ChatApp (mounts <ConversationsProvider>) + inner ChatAppInner (calls useConversations) — Pitfall 1 mitigation; consumer must sit below provider in the React tree"
  - "Plan 08-02: useMemo on context value AND narrowed useEffect deps from [conversations] to [conversations.refresh] — defense-in-depth against the unbounded refetch loop where every items update would re-create the value object and refire the post-done effect (Pitfall 3)"
  - "Plan 08-02: D-14 integration test scopes the sidebar assertion to the Resume button's aria-label (`/Resume Surcharge for 15kg Bounce/`) instead of bare text — the chat-answer markdown also contains the preview text so a getByText(/Surcharge for 15kg Bounce/) collides; aria-label scoping is the disambiguator (Rule 1 fix discovered during test execution)"
  - "Plan 08-02: ConversationSidebar.test.tsx and SurchargeHistoryChart.test.tsx gained renderWithProvider helpers — Rule 1 fix because the provider migration broke standalone component renders that previously worked with the per-call-site useState hook (out-of-scope deduction would have been wrong: these are direct consumers of useConversations broken by THIS task's changes)"

patterns-established:
  - "Context-backed hook with sentinel null: createContext<T | null>(null) + wrapper hook throws when ctx === null. Pattern future cross-tree shared state in this repo should follow."
  - "Outer/inner component split for provider-mounting parents: outer mounts the provider tree, inner consumes; inner is private to the file (not exported). Avoids the Pitfall 1 'consumer above provider' anti-pattern."
  - "renderHook wrapper option for context-backed hooks: const wrapper = ({ children }) => <Provider>{children}</Provider> + renderHook(() => useThing(), { wrapper })."
  - "Standalone-component test wrapping helper: renderWithProvider(ui) = render(<Provider>{ui}</Provider>) — mirrors the production tree without recreating the full ChatApp layout."

requirements-completed: [UI-06]

# Metrics
duration: 6min
completed: 2026-05-05
---

# Phase 8 Plan 02: Conversations Provider Summary

**Audit Issue 4 closed: useConversations promoted from 3 independent useState instances to a single React Context provider, so post-`done` `conversations.refresh()` propagates from ChatApp to ConversationSidebar and SurchargeHistoryChart without a page reload — UI-06 restored to fully satisfied.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-05T05:53:22Z
- **Completed:** 2026-05-05T05:58:52Z
- **Tasks:** 3 (1+2 commit batched, 3 separate)
- **Files modified:** 6 (1 renamed, 5 edited)

## Accomplishments

- `frontend/hooks/useConversations.tsx` (renamed from `.ts` via `git mv`) now exports `ConversationsProvider` (Context Provider component) AND `useConversations` (hook that throws when called outside the provider). `useMemo` stabilises the context value identity so consumer effects keyed on `conversations.refresh` do not refire on every items/loading update.
- `frontend/components/ChatApp.tsx` split: outer `ChatApp` mounts `<ConversationsProvider>` around the inner `ChatAppInner` (Pitfall 1 mitigation — the consumer of `useConversations` now sits BELOW the provider in the React tree). Post-`done` useEffect deps narrowed from `[conversations]` to `[conversations.refresh]` (Pitfall 3 defense-in-depth).
- New `D-14 sidebar refresh integration test` in `frontend/__tests__/components/ChatApp.integration.test.tsx` exercises the production prop chain end-to-end through MSW: empty list on mount → user sends a query → answer table renders → sidebar's thread row appears → exactly two GET /api/conversations calls. Drift-prevention test that catches any regression dropping the provider wrap.
- 3 existing `useConversations.test.tsx` tests wrapped in `<ConversationsProvider>` via the `renderHook { wrapper }` option (Pitfall 2 mitigation).
- 2 existing component test files (`ConversationSidebar.test.tsx`, `SurchargeHistoryChart.test.tsx`) gained `renderWithProvider` helpers because their direct consumers of `useConversations` now require provider scope (Rule 1 fix — see Deviations section).

## Task Commits

1. **Task 1+2 batched: ConversationsProvider + ChatApp split + hook test wrapper** — `16aaf29` (refactor)
2. **Task 3: D-14 sidebar-refresh integration test** — `0eb58dc` (test)

_Note: Task 1 by design left the suite intentionally red (3 hook tests throw "must be called inside provider"). The plan instructed to commit Task 1 + Task 2 together so the branch tip is never green-then-red-then-green; we did exactly that. Task 3 (TDD-flagged) was not strictly RED-first because Task 2 had already wired the production code that makes the test pass — the test is a regression-prevention layer, not a behaviour-driving spec._

## Files Created/Modified

- `frontend/hooks/useConversations.tsx` — Renamed from `.ts`. Now exports `ConversationsProvider` and `useConversations`. `'use client'` preserved at line 1 (Pitfall 6). `createContext<ConversationsContextValue | null>(null)` with sentinel; wrapper hook throws on null. `useMemo` stabilises value identity (Pitfall 3).
- `frontend/components/ChatApp.tsx` — Split into outer `ChatApp` (mounts `<ConversationsProvider><ChatAppInner /></ConversationsProvider>`) and inner `ChatAppInner` (consumes via `useConversations`). Imports updated: `import { ConversationsProvider, useConversations } from '@/hooks/useConversations'`. Post-`done` useEffect deps narrowed to `[chat.finalPayload, chat.status, conversations.refresh]`.
- `frontend/__tests__/hooks/useConversations.test.tsx` — Imports `ConversationsProvider` and `ReactNode`; declares a `wrapper` const; passes `{ wrapper }` to all three `renderHook` calls. Body of each test unchanged.
- `frontend/__tests__/components/ChatApp.integration.test.tsx` — `happyTurnEvents` added to fixtures import; new describe block `'ChatApp sidebar refresh integration (Phase 8 D-14)'` with one test `'completed turn appends new thread to ConversationSidebar without page reload (audit Issue 4)'`. Existing approve/deny tests untouched.
- `frontend/__tests__/components/ConversationSidebar.test.tsx` — Imports `ConversationsProvider` and `ReactNode`; added `renderWithProvider(ui)` helper; replaced 6 `render(...)` call sites with `renderWithProvider(...)`. Test assertions unchanged.
- `frontend/__tests__/components/SurchargeHistoryChart.test.tsx` — Same pattern as ConversationSidebar.test.tsx: `renderWithProvider` helper added; 4 affected `render(...)` call sites updated. The 5th test (source-code grep) needed no change.

## Decisions Made

See key-decisions in frontmatter. The five decisions logged document:
1. Single-file colocation of `ConversationsProvider` and `useConversations` (D-06).
2. Outer/inner component split (Pitfall 1).
3. Defense-in-depth around the unbounded refetch loop (`useMemo` + narrowed deps — Pitfall 3).
4. Sidebar-assertion scoping via `aria-label` regex instead of bare text (resolves multiple-match failure in the new D-14 test).
5. Two existing component test files gained `renderWithProvider` helpers (Rule 1 fix detailed below).

Confirmation that ConversationSidebar.tsx and SurchargeHistoryChart.tsx **call sites were left untouched** (D-05 — public hook contract `{ items, loading, error, refresh, resume }` unchanged). Only their **test harnesses** needed to wrap render in the provider.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Wrap `ConversationSidebar.test.tsx` and `SurchargeHistoryChart.test.tsx` in `<ConversationsProvider>` to satisfy the new wrapper hook contract**

- **Found during:** Task 2, after running the full FE suite with `npm test -- --run`.
- **Issue:** Both test files render their components standalone (`render(<ConversationSidebar ... />)`, `render(<SurchargeHistoryChart />)`) — they are direct consumers of `useConversations()`. After Task 1 introduced the throwing wrapper hook ("must be called inside <ConversationsProvider>"), all 10 tests across these two files began throwing at render time with that exact error. Plan 08-02 enumerated the test files it would touch and DID NOT include these two — but the failures are caused directly by this task's changes, so they are inside the SCOPE BOUNDARY.
- **Fix:** Added a `renderWithProvider(ui: ReactNode)` helper to each file (`render(<ConversationsProvider>{ui}</ConversationsProvider>)`) and replaced every relevant `render(...)` call site. Test assertions and bodies unchanged. Imported `ConversationsProvider` from `@/hooks/useConversations` and `ReactNode` from `react`.
- **Files modified:** `frontend/__tests__/components/ConversationSidebar.test.tsx`, `frontend/__tests__/components/SurchargeHistoryChart.test.tsx`.
- **Verification:** Full FE suite went from 110/120 to 121/121 passing across 27 test files; tsc green.
- **Committed in:** `16aaf29` (Task 1+2 batched commit — these test fixes were folded in alongside the Task 2 production migration).

**2. [Rule 1 — Bug] Scope the sidebar `getByText` assertion in the new D-14 test to the Resume button's `aria-label` to disambiguate from the chat-answer markdown**

- **Found during:** Task 3, first test run after writing the D-14 test as specified in the plan.
- **Issue:** Plan instructed `expect(screen.getByText(/Surcharge for 15kg Bounce/)).toBeInTheDocument()` for the post-refresh sidebar assertion. This failed with `TestingLibraryElementError: Found multiple elements with the text: /Surcharge for 15kg Bounce/` because the chat answer's markdown (rendered alongside the sidebar after the SSE turn completes) also contains that exact preview text — both are visible by the time the assertion runs.
- **Fix:** Switched the assertion to `screen.getByRole('button', { name: /Resume Surcharge for 15kg Bounce/ })`. The Resume button's `aria-label` is `Resume ${preview} — last updated ${relative}` (set in `frontend/components/sidebar/ThreadListItem.tsx:20`), so the regex matches only the sidebar's row. The literal substring `Surcharge for 15kg Bounce` still appears in the test file (acceptance criterion satisfied).
- **Files modified:** `frontend/__tests__/components/ChatApp.integration.test.tsx`.
- **Verification:** D-14 test passes; full FE suite 121/121 green; tsc green.
- **Committed in:** `0eb58dc` (Task 3 commit).

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs caused directly by this task's changes; both inside scope boundary).
**Impact on plan:** Both fixes were necessary for the suite to be green and for the new test to actually validate what it claims. No scope creep — neither fix touched files or behaviours outside the plan's stated boundary; the broken tests are direct consumers of the migrated hook and the assertion fix is a textual disambiguation in the same test the plan introduced.

## Issues Encountered

- **Default `git diff --stat` rename detection threshold (50%) classified the `useConversations.ts → .tsx` rename as `D + A` instead of `R`** because the content delta is large enough (the provider/Context machinery is substantial). The plan acceptance criterion mentioned "rename as `R`" but the underlying mechanic — `git mv` at the working-tree level — was performed correctly, and `git log --follow -M30%` confirms history continuity (`16aaf29 → 6fdeb09 feat(04-02): implement useChatStream, useConversations, useFuelPrices hooks`). Blame tools that use `--follow` will track the file. Documented here for transparency; no code change required.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Audit Issue 4 closed end-to-end** with a drift-prevention test that exercises the production prop chain. UI-06 is restored to fully satisfied.
- **Phase 8 verify-phase** can proceed against the milestone audit checklist.
- **Manual smoke (deferred to verify-phase per plan):** live `npm run dev`, send a query, observe sidebar entry appears within ~1s of the answer rendering. Programmatic test now exists for this exact contract.
- **No blockers; no concerns.**

---
*Phase: 08-search-context-sidebar-polish*
*Completed: 2026-05-05*

## Self-Check: PASSED

Verified post-write:

- [x] `frontend/hooks/useConversations.tsx` exists; `frontend/hooks/useConversations.ts` removed.
- [x] `frontend/components/ChatApp.tsx` contains literal `<ConversationsProvider>` (1 match), `function ChatAppInner` (1 match), `conversations.refresh]` (1 match in deps).
- [x] `frontend/hooks/useConversations.tsx` contains literal `useMemo` (2 matches: import + use site), `must be called inside`, `createContext<ConversationsContextValue | null>(null)`, `'use client'` at line 1.
- [x] `frontend/__tests__/hooks/useConversations.test.tsx` contains `ConversationsProvider`, `{ wrapper }`, 3 `renderHook` calls.
- [x] `frontend/__tests__/components/ChatApp.integration.test.tsx` contains `Phase 8 D-14`, `convCallCount`, `No conversations yet`, `Surcharge for 15kg Bounce`, `expect(convCallCount).toBe(2)`, `happyTurnEvents` import from `'../fixtures/sse'`.
- [x] Commit `16aaf29` exists in `git log --oneline --all`.
- [x] Commit `0eb58dc` exists in `git log --oneline --all`.
- [x] `git log --follow -M30% -- frontend/hooks/useConversations.tsx` traces to `6fdeb09 feat(04-02): implement useChatStream, useConversations, useFuelPrices hooks` (history preserved).
- [x] `cd frontend && npx tsc --noEmit` exits 0.
- [x] `cd frontend && npm test -- --run` exits 0 (27 files, 121 tests passing — was 120, now +1 D-14 test).
