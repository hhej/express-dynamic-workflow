---
phase: 08-search-context-sidebar-polish
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/hooks/useConversations.ts
  - frontend/hooks/useConversations.tsx
  - frontend/components/ChatApp.tsx
  - frontend/__tests__/hooks/useConversations.test.tsx
  - frontend/__tests__/components/ChatApp.integration.test.tsx
autonomous: true
requirements:
  - UI-06
gap_closure: true

must_haves:
  truths:
    - "useConversations is backed by a single React Context instance shared across ChatApp, ConversationSidebar, and SurchargeHistoryChart — calling useConversations() outside <ConversationsProvider> throws a clear error"
    - "When a turn completes (chat.status==='done' and chat.finalPayload arrives), the existing void conversations.refresh() call in ChatApp propagates to ConversationSidebar AND SurchargeHistoryChart via the shared provider, with no page reload"
    - "ChatApp renders <ConversationsProvider> wrapping its three-column layout, with the body that calls useConversations() living in a child component (ChatAppInner) so the consumer sits BELOW the provider in the React tree (Pitfall 1)"
    - "All 3 existing tests in __tests__/hooks/useConversations.test.tsx still pass via a new <ConversationsProvider> wrapper passed to renderHook (Pitfall 2)"
    - "New ChatApp.integration.test.tsx case proves the sidebar updates after a fresh-turn `done` event without reload (audit Issue 4 drift-prevention)"
    - "Existing 2 ChatApp.integration tests (approve flow + deny flow from Plan 06-03) still pass after the provider migration"
    - "ConversationsContext value object identity is stabilized via useMemo so the existing ChatApp.tsx:71 useEffect deps array does not cause unbounded refetches (Pitfall 3)"
  artifacts:
    - path: "frontend/hooks/useConversations.tsx"
      provides: "ConversationsProvider component + useConversations hook (Context-backed) — both named exports from a single file"
      contains: "export function ConversationsProvider"
    - path: "frontend/hooks/useConversations.tsx"
      provides: "useConversations() throws with a clear error when context is null (called outside provider)"
      contains: "must be called inside"
    - path: "frontend/components/ChatApp.tsx"
      provides: "Top-level ChatApp wraps <ConversationsProvider> around <ChatAppInner /> — ChatAppInner houses the body that calls useConversations() (Pitfall 1)"
      contains: "ChatAppInner"
    - path: "frontend/__tests__/hooks/useConversations.test.tsx"
      provides: "renderHook calls wrapped in <ConversationsProvider> via the wrapper option"
      contains: "ConversationsProvider"
    - path: "frontend/__tests__/components/ChatApp.integration.test.tsx"
      provides: "New `it('D-14 sidebar refresh: ...')` test asserting sidebar appends thread-B after a completed turn without reload"
      contains: "D-14 sidebar refresh"
  key_links:
    - from: "frontend/components/ChatApp.tsx — top-level ChatApp"
      to: "frontend/components/sidebar/ConversationSidebar.tsx + frontend/components/dashboard/SurchargeHistoryChart.tsx"
      via: "<ConversationsProvider> wrapping the three-column <main>...</main> tree, with ChatAppInner calling useConversations() inside"
      pattern: "<ConversationsProvider>"
    - from: "ChatApp.tsx useEffect (formerly line 71) calling void conversations.refresh()"
      to: "ConversationSidebar items + SurchargeHistoryChart items (single shared instance)"
      via: "Context provider re-renders all consumers when items state updates"
      pattern: "conversations\\.refresh"
    - from: "useConversations() outside provider"
      to: "throws Error with message containing 'must be called inside'"
      via: "useContext returns null sentinel; wrapper hook raises"
      pattern: "throw new Error"
---

<objective>
Close audit Issue 4 (`v1.0-MILESTONE-AUDIT.md` §2.3): promote `useConversations` from per-call-site `useState` (3 independent instances today) to a single `ConversationsProvider` Context-backed instance shared by `ChatApp`, `ConversationSidebar`, and `SurchargeHistoryChart`. After this plan, the existing `void conversations.refresh()` call inside `ChatApp.tsx` (fired on `done`) propagates to all three consumers via the shared provider, so the sidebar updates immediately after a completed turn without a page reload — restoring UI-06 to fully satisfied.

Purpose: Closes the last cross-phase wiring gap from the v1.0 milestone audit. Provider pattern is established as the React-19 idiom for cross-tree shared state in this repo.

Output:
- `frontend/hooks/useConversations.ts` deleted; `frontend/hooks/useConversations.tsx` created with both `ConversationsProvider` + `useConversations` named exports (rename via git mv to preserve blame)
- `frontend/components/ChatApp.tsx` split into outer `ChatApp` (mounts provider) + inner `ChatAppInner` (consumes via `useConversations()`)
- 3 existing hook tests get the `<ConversationsProvider>` renderHook wrapper
- 1 new integration test in `ChatApp.integration.test.tsx` proves the sidebar refresh wire end-to-end
</objective>

<execution_context>
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/workflows/execute-plan.md
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/08-search-context-sidebar-polish/08-CONTEXT.md
@.planning/phases/08-search-context-sidebar-polish/08-RESEARCH.md
@.planning/phases/08-search-context-sidebar-polish/08-VALIDATION.md
@.planning/v1.0-MILESTONE-AUDIT.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->
<!-- Executor should use these directly — no codebase exploration needed. -->

From frontend/hooks/useConversations.ts (TODAY — full file, 44 lines, before this plan):
```typescript
'use client';
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { ConversationDetail, ConversationSummary } from '@/types/api.types';

/**
 * Hook for the conversation history sidebar. Owns fetch + refresh and the
 * D-14 resume flow which persists thread_id to localStorage so the next
 * chat turn continues the resumed thread (D-20).
 */
export function useConversations() {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await api.listConversations(50);
      setItems(next);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  /** D-14: load history + persist thread_id so the next chat continues it (D-20). */
  const resume = useCallback(async (threadId: string): Promise<ConversationDetail> => {
    const detail = await api.getConversation(threadId);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LOCAL_STORAGE_KEYS.threadId, threadId);
    }
    return detail;
  }, []);

  return { items, loading, error, refresh, resume };
}
```

Public hook contract (unchanged after this plan, per D-05):
```typescript
{ items: ConversationSummary[], loading: boolean, error: Error | null,
  refresh: () => Promise<void>, resume: (threadId: string) => Promise<ConversationDetail> }
```

Three call sites (unchanged after this plan, per D-05):
- frontend/components/ChatApp.tsx:24 — `const conversations = useConversations();`
- frontend/components/sidebar/ConversationSidebar.tsx:16 — `const { items, loading } = useConversations();`
- frontend/components/dashboard/SurchargeHistoryChart.tsx:29 — `const { items, loading: convLoading, error: convError } = useConversations();`

ChatApp current structure (TODAY — full file, 217 lines, before this plan):
- Line 22-217: `export function ChatApp() { ... }` — single component containing all state/effect logic AND the three-column JSX return
- Line 24: `const conversations = useConversations();` (called at top of body — runs BEFORE the return JSX)
- Line 36-71: useEffect that fires `void conversations.refresh()` on `done`. Deps array at line 71: `[chat.finalPayload, chat.status, conversations]`
- Line 188-216: returned JSX is `<main className="...">` containing `<ConversationSidebar />`, `<ChatColumn />`, `<TracePanel />`

From frontend/components/sidebar/ConversationSidebar.tsx (line 16, unchanged):
```typescript
const { items, loading } = useConversations();
```

From frontend/components/dashboard/SurchargeHistoryChart.tsx (line 29, unchanged):
```typescript
const { items, loading: convLoading, error: convError } = useConversations();
```

From frontend/__tests__/hooks/useConversations.test.tsx (TODAY — full file, 46 lines):
```typescript
import { describe, expect, it, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { useConversations } from '@/hooks/useConversations';
import { server } from '../mocks/server';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { ConversationDetail } from '@/types/api.types';

beforeEach(() => {
  window.localStorage.clear();
});

describe('useConversations', () => {
  it('loads SAMPLE_CONVERSATIONS on mount', async () => {
    const { result } = renderHook(() => useConversations());
    // ...
  });
  // 3 tests total — all use renderHook(() => useConversations()) without a wrapper.
});
```

From frontend/__tests__/components/ChatApp.integration.test.tsx (TODAY — full file, 220 lines):
- Two existing tests: `it('approve flow: ...')` and `it('deny flow: ...')` from Plan 06-03 D-15.3
- Uses MSW `installPauseThenResumeHandler` pattern with call-counter switching
- This plan EXTENDS the file with one new `it('D-14 sidebar refresh: ...')` test

From frontend/__tests__/fixtures/sse.ts:
```typescript
export function happyTurnEvents(threadId = 'thread-happy'): SSEEvent[] {
  return [
    { type: 'meta', payload: { thread_id: threadId } },
    ...HAPPY_TRACE.map((entry) => ({ type: 'trace' as const, payload: entry })),
    { type: 'answer', payload: HAPPY_PAYLOAD },
    { type: 'done', payload: {} },
  ];
}
// HAPPY_PAYLOAD has message_id: 'thread-happy-0'
```

From frontend/__tests__/mocks/handlers.ts (default GET /api/conversations handler — overridable per-test via server.use):
```typescript
http.get(`${API_BASE}/api/conversations`, () => {
  return HttpResponse.json(SAMPLE_CONVERSATIONS);
}),
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create ConversationsProvider + Context-backed useConversations hook in renamed useConversations.tsx; remove the legacy .ts file via git rename</name>
  <files>frontend/hooks/useConversations.ts, frontend/hooks/useConversations.tsx</files>
  <read_first>
    - frontend/hooks/useConversations.ts (full 44-line current file — must lift this body verbatim into the provider; preserve `'use client'`, `api.listConversations(50)` cap, error wrapping, localStorage thread_id persistence)
    - .planning/phases/08-search-context-sidebar-polish/08-CONTEXT.md (decisions D-01, D-02, D-05, D-06)
    - .planning/phases/08-search-context-sidebar-polish/08-RESEARCH.md (Architecture Patterns section — verbatim provider example; Pitfall 3 — useMemo around context value; Pitfall 6 — 'use client' directive must remain at line 1)
  </read_first>
  <action>
    1. Rename the file via git to preserve blame history. From the repo root run:

```
git mv frontend/hooks/useConversations.ts frontend/hooks/useConversations.tsx
```

       Verify with `git status` that the file shows as renamed (`R  useConversations.ts -> useConversations.tsx`), NOT as `D` + `??`.

    2. Write the new contents of `frontend/hooks/useConversations.tsx` verbatim (overwrites the old hook-only body). Single file, two named exports per D-06. Keeps the `'use client'` directive at line 1 per Pitfall 6:

```typescript
'use client';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api } from '@/lib/api';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { ConversationDetail, ConversationSummary } from '@/types/api.types';

/**
 * Phase 8 D-01 / D-02 — single React Context instance shared by ChatApp,
 * ConversationSidebar, and SurchargeHistoryChart. The provider owns the
 * useState/useEffect/useCallback block; consumers read via useContext.
 *
 * Closes audit Issue 4: when ChatApp.tsx fires `void conversations.refresh()`
 * on `done`, all three consumers re-render with the fresh items list.
 */

interface ConversationsContextValue {
  items: ConversationSummary[];
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  /** D-14 (Phase 4): load history + persist thread_id so the next chat continues it (D-20). */
  resume: (threadId: string) => Promise<ConversationDetail>;
}

// Sentinel `null` — wrapper hook detects "called outside provider" and throws.
const ConversationsContext = createContext<ConversationsContextValue | null>(null);

export function ConversationsProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await api.listConversations(50);
      setItems(next);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const resume = useCallback(async (threadId: string): Promise<ConversationDetail> => {
    const detail = await api.getConversation(threadId);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LOCAL_STORAGE_KEYS.threadId, threadId);
    }
    return detail;
  }, []);

  // Pitfall 3: stabilize value identity so consumer effects keyed on
  // `conversations.refresh` don't refire on every items/loading update.
  const value = useMemo<ConversationsContextValue>(
    () => ({ items, loading, error, refresh, resume }),
    [items, loading, error, refresh, resume],
  );

  return (
    <ConversationsContext.Provider value={value}>{children}</ConversationsContext.Provider>
  );
}

/**
 * Read the shared conversations state. Throws when called outside
 * <ConversationsProvider>. Wrap your tree in ChatApp.tsx.
 */
export function useConversations(): ConversationsContextValue {
  const ctx = useContext(ConversationsContext);
  if (ctx === null) {
    throw new Error(
      'useConversations() must be called inside <ConversationsProvider>. ' +
        'Wrap your tree with the provider in ChatApp.tsx.',
    );
  }
  return ctx;
}
```

    3. Run `cd frontend && npx tsc --noEmit`. The compiler will REPORT NEW ERRORS in the test file `frontend/__tests__/hooks/useConversations.test.tsx` (3 tests now throw at runtime, but tsc itself is OK), and possibly in `ChatApp.tsx` (still works at type level — `useConversations()` returns the same shape). Type errors only matter at the rename boundary; the consumers at ChatApp / Sidebar / Dashboard will continue to type-check because the return shape is unchanged.

    4. Run `cd frontend && npm test -- --run __tests__/hooks/useConversations.test.tsx` — all 3 tests will FAIL with `Error: useConversations() must be called inside <ConversationsProvider>`. This is EXPECTED at this stage. Task 2 will land the test wrapper. Do NOT commit yet — wait for Task 2 to land the integration; commit both together at end of Task 2 to avoid leaving the suite red on the branch tip.

    Constraints:
    - Do NOT introduce a separate file for the Context object (D-06 — single file, two named exports).
    - Do NOT pass a default value to `createContext` other than the `null` sentinel (Anti-pattern; Pitfall recommendation).
    - Do NOT remove the auto-fetch `useEffect` — first consumer mount today triggers a fetch; provider mount under ChatApp matches that exact behavior.
    - Do NOT use the React 19 `<Context value={...}>` shorthand syntax — explicit `<ConversationsContext.Provider value={...}>` is more readable and matches what the rest of the React ecosystem still uses; either works in React 19, but consistency wins.
    - Preserve `'use client'` at line 1 (Pitfall 6 — Next.js Server Components cannot use useState/useContext/useEffect).
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && test -f hooks/useConversations.tsx && ! test -f hooks/useConversations.ts && grep -q "ConversationsProvider" hooks/useConversations.tsx && grep -q "must be called inside" hooks/useConversations.tsx && npx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - File frontend/hooks/useConversations.tsx exists
    - File frontend/hooks/useConversations.ts does NOT exist (verify with `test ! -f frontend/hooks/useConversations.ts`)
    - Command `git status --short frontend/hooks/` shows the rename as `R` (renamed), not `D` + `??`
    - File frontend/hooks/useConversations.tsx line 1 is `'use client';`
    - File frontend/hooks/useConversations.tsx contains the literal string `export function ConversationsProvider`
    - File frontend/hooks/useConversations.tsx contains the literal string `export function useConversations`
    - File frontend/hooks/useConversations.tsx contains the literal string `must be called inside`
    - File frontend/hooks/useConversations.tsx contains the literal string `useMemo` (Pitfall 3 — stabilize value)
    - File frontend/hooks/useConversations.tsx contains the literal string `createContext<ConversationsContextValue | null>(null)`
    - Command `cd frontend && npx tsc --noEmit` exits with status 0
  </acceptance_criteria>
  <done>
    Provider + hook live in single .tsx file; legacy .ts file removed via git rename; tsc green; tests are temporarily red at this checkpoint (intentional — Task 2 lands the consumer migration that re-greens them).
  </done>
</task>

<task type="auto">
  <name>Task 2: Migrate ChatApp to wrap <ConversationsProvider> via ChatAppInner split, narrow useEffect deps to conversations.refresh, and update useConversations.test.tsx renderHook to use the provider wrapper</name>
  <files>frontend/components/ChatApp.tsx, frontend/__tests__/hooks/useConversations.test.tsx</files>
  <read_first>
    - frontend/components/ChatApp.tsx (full 217-line current file — line 22 component start, line 24 useConversations call, line 36-71 the post-`done` useEffect with deps `[chat.finalPayload, chat.status, conversations]`, line 188-216 the returned JSX)
    - frontend/hooks/useConversations.tsx (the new file from Task 1 — public exports `ConversationsProvider`, `useConversations`)
    - frontend/__tests__/hooks/useConversations.test.tsx (full 46-line current file — 3 tests use bare renderHook calls)
    - .planning/phases/08-search-context-sidebar-polish/08-RESEARCH.md (Pitfall 1 — split ChatApp into outer + inner; Pitfall 3 — narrow effect deps to conversations.refresh)
    - .planning/phases/08-search-context-sidebar-polish/08-CONTEXT.md (D-02, D-04, D-05)
  </read_first>
  <action>
    1. Modify `frontend/components/ChatApp.tsx`. The change is structural: split the existing single `ChatApp` component into TWO components in the same file — the outer `ChatApp` mounts the provider, the inner `ChatAppInner` keeps the existing 100+ lines of body unchanged AND consumes via `useConversations()` (now safely below the provider in the tree per Pitfall 1).

       Specifically:
       (a) Add `ConversationsProvider` to the existing import from `@/hooks/useConversations`:
```typescript
// BEFORE (line 7):
import { useConversations } from '@/hooks/useConversations';

// AFTER:
import { ConversationsProvider, useConversations } from '@/hooks/useConversations';
```

       (b) RENAME the existing `export function ChatApp()` declaration at line 22 to `function ChatAppInner()` (drop `export`). All other body lines (24-216) stay BYTE-IDENTICAL except the deps narrowing in step (c).

       (c) Pitfall 3 fix — narrow the post-`done` useEffect deps array. Find the deps array at the end of that effect (currently `}, [chat.finalPayload, chat.status, conversations]);` at approximately line 71). Replace `conversations` with `conversations.refresh`:

```typescript
// BEFORE (line ~71):
}, [chat.finalPayload, chat.status, conversations]);

// AFTER:
}, [chat.finalPayload, chat.status, conversations.refresh]);
```

       Reason: After provider migration, `conversations` is the memoized context value. `conversations.refresh` is a stable `useCallback` reference. Narrowing prevents ESLint react-hooks/exhaustive-deps warnings AND the unbounded refetch loop where every `setItems` re-renders the provider, re-creates `value` (mitigated by useMemo from Task 1 — but defense-in-depth here), and re-fires the effect.

       (d) Add the new top-level `export function ChatApp()` AT THE END of the file (after the closing `}` of `ChatAppInner`):

```typescript
/**
 * Phase 8 D-02 — top-level export wraps ChatAppInner with ConversationsProvider
 * so all three consumers (ChatAppInner, ConversationSidebar, SurchargeHistoryChart)
 * read from the same shared instance. Pitfall 1 mitigation: ChatAppInner
 * sits BELOW the provider in the React tree, so its useConversations() call
 * resolves cleanly.
 */
export function ChatApp() {
  return (
    <ConversationsProvider>
      <ChatAppInner />
    </ConversationsProvider>
  );
}
```

       Final ChatApp.tsx structure:
```typescript
'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ChatColumn } from '@/components/chat/ChatColumn';
import { ConversationSidebar } from '@/components/sidebar/ConversationSidebar';
import { TracePanel } from '@/components/trace/TracePanel';
import { useChatStream } from '@/hooks/useChatStream';
import { ConversationsProvider, useConversations } from '@/hooks/useConversations'; // CHANGED
import type { ChatMessage } from '@/components/chat/MessageList';
import type { FinalPayload } from '@/types/agent.types';

/* ... existing JSDoc ... */
function ChatAppInner() {           // CHANGED: was `export function ChatApp() {`
  const chat = useChatStream();
  const conversations = useConversations();  // unchanged — now resolves to provider value
  /* ... entire existing body lines 25-216 BYTE-IDENTICAL ... */
  /* EXCEPT line 71 deps array narrowed: ...conversations.refresh] */
}

export function ChatApp() {
  return (
    <ConversationsProvider>
      <ChatAppInner />
    </ConversationsProvider>
  );
}
```

    2. Modify `frontend/__tests__/hooks/useConversations.test.tsx`. Add the provider wrapper for `renderHook`. Replace the entire file contents with:

```typescript
import { describe, expect, it, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { ConversationsProvider, useConversations } from '@/hooks/useConversations';
import { server } from '../mocks/server';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { ConversationDetail } from '@/types/api.types';

beforeEach(() => {
  window.localStorage.clear();
});

// Phase 8 D-05: renderHook wrapper supplies the provider so the hook resolves
// the shared context. Without this wrapper the hook throws (Pitfall 2).
const wrapper = ({ children }: { children: ReactNode }) => (
  <ConversationsProvider>{children}</ConversationsProvider>
);

describe('useConversations', () => {
  it('loads SAMPLE_CONVERSATIONS on mount', async () => {
    const { result } = renderHook(() => useConversations(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.items.length).toBeGreaterThan(0);
    expect(result.current.items[0]).toHaveProperty('thread_id');
  });

  it('refresh() re-fetches when underlying handler changes', async () => {
    const { result } = renderHook(() => useConversations(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    const initialLen = result.current.items.length;
    server.use(
      http.get('http://localhost:8000/api/conversations', () => HttpResponse.json([])),
    );
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.items.length).toBe(0);
    expect(initialLen).toBeGreaterThan(0);
  });

  it('resume() persists thread_id to localStorage and returns detail', async () => {
    const { result } = renderHook(() => useConversations(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    let detail: ConversationDetail | undefined;
    await act(async () => {
      detail = await result.current.resume('thread-1');
    });
    expect(window.localStorage.getItem(LOCAL_STORAGE_KEYS.threadId)).toBe('thread-1');
    expect(detail?.thread_id).toBe('thread-1');
  });
});
```

       (Note: file extension stays `.test.tsx` — matches existing convention. Three tests; only addition is the `wrapper` constant + `{ wrapper }` second argument to each `renderHook` call. Imports also gain `ReactNode` and `ConversationsProvider`.)

    3. Run `cd frontend && npm test -- --run __tests__/hooks/useConversations.test.tsx`. All 3 tests must PASS.

    4. Run `cd frontend && npm test -- --run __tests__/components/ChatApp.test.tsx __tests__/components/ChatApp.integration.test.tsx`. The existing 2 ChatApp tests + 2 ChatApp.integration tests (approve + deny from Plan 06-03) MUST still pass — the provider wrapping must not break them. If they fail, the most likely cause is Pitfall 1 (consumer above provider — re-check the split).

    5. Run `cd frontend && npx tsc --noEmit`. Must report 0 errors.

    6. Run `cd frontend && npm test -- --run`. Full suite green.

    7. Commit Task 1 + Task 2 together (since Task 1 left tests intentionally red, only Task 2 closes the loop):
       Commit message: `refactor(08-02): promote useConversations to ConversationsProvider Context`

    Constraints:
    - Do NOT change the public hook return shape — D-05 keeps `{ items, loading, error, refresh, resume }`.
    - Do NOT change call sites in ConversationSidebar.tsx or SurchargeHistoryChart.tsx — they continue to read from the same `@/hooks/useConversations` import path; the underlying source changes only.
    - Do NOT introduce ANY new file in `frontend/components/providers/` (CONTEXT D-06 — provider lives in `frontend/hooks/useConversations.tsx`).
    - Do NOT touch the existing post-`done` useEffect logic — only narrow the deps array (Pitfall 3). The body that calls `setMessages`, `lastAppendedPayloadRef`, and `void conversations.refresh()` stays as-is.
    - Do NOT add background polling, on-error refresh, or any new refresh trigger — D-04 is single-source: only the existing `done`-path call site fires refresh.
    - Do NOT use `<Context value={...}>` shorthand inside ChatApp — the provider component handles the JSX; ChatApp uses `<ConversationsProvider>` only.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npm test -- --run __tests__/hooks/useConversations.test.tsx __tests__/components/ChatApp.test.tsx __tests__/components/ChatApp.integration.test.tsx && npx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - File frontend/components/ChatApp.tsx contains the literal string `function ChatAppInner()` (not exported)
    - File frontend/components/ChatApp.tsx contains the literal string `export function ChatApp()` exactly once
    - File frontend/components/ChatApp.tsx contains the literal string `<ConversationsProvider>`
    - File frontend/components/ChatApp.tsx contains the literal string `<ChatAppInner />`
    - File frontend/components/ChatApp.tsx import line for `@/hooks/useConversations` includes BOTH `ConversationsProvider` and `useConversations` (grep `import.*ConversationsProvider.*useConversations\|useConversations.*ConversationsProvider` ChatApp.tsx)
    - File frontend/components/ChatApp.tsx contains the literal string `conversations.refresh]` in the post-`done` useEffect deps array (Pitfall 3 — narrowed deps; trailing `]` proves it's the array close)
    - File frontend/__tests__/hooks/useConversations.test.tsx contains the literal string `ConversationsProvider`
    - File frontend/__tests__/hooks/useConversations.test.tsx contains the literal string `{ wrapper }` (renderHook second argument)
    - Command `cd frontend && npm test -- --run __tests__/hooks/useConversations.test.tsx` exits with status 0
    - Command `cd frontend && npm test -- --run __tests__/components/ChatApp.test.tsx __tests__/components/ChatApp.integration.test.tsx` exits with status 0 (existing 2 ChatApp tests + 2 integration tests)
    - Command `cd frontend && npx tsc --noEmit` exits with status 0
    - Command `cd frontend && npm test -- --run` exits with status 0 (full FE suite green)
  </acceptance_criteria>
  <done>
    ChatApp wraps ChatAppInner with ConversationsProvider; deps narrowed to `conversations.refresh`; existing 3 useConversations hook tests pass via provider wrapper; existing 2 ChatApp.integration tests (approve + deny) still pass; full FE suite + tsc green.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add D-14 sidebar-refresh integration test in ChatApp.integration.test.tsx — proves shared provider propagates ChatApp.refresh() to ConversationSidebar</name>
  <files>frontend/__tests__/components/ChatApp.integration.test.tsx</files>
  <read_first>
    - frontend/__tests__/components/ChatApp.integration.test.tsx (full 220-line current file — line 78-99 `installPauseThenResumeHandler` reference for the call-counter MSW pattern; line 101-103 beforeEach; line 105-219 existing approve+deny tests)
    - frontend/__tests__/fixtures/sse.ts (full file — `happyTurnEvents`, `makeSseStream`, `HAPPY_PAYLOAD.message_id` is 'thread-happy-0')
    - frontend/__tests__/fixtures/agentState.ts (full file — `SAMPLE_CONVERSATIONS` baseline; this test installs custom handlers so default doesn't apply)
    - frontend/__tests__/mocks/handlers.ts (default GET /api/conversations returns SAMPLE_CONVERSATIONS — overridden per-test via server.use)
    - frontend/components/sidebar/ConversationSidebar.tsx (line 32-46 — empty state copy "No conversations yet…", item rendering via ThreadListItem with `item.first_message_preview` text)
    - frontend/components/sidebar/ThreadListItem.tsx (read this file to confirm what text is rendered for each thread row — likely uses `first_message_preview`; the test will assert on that text)
    - .planning/phases/08-search-context-sidebar-polish/08-CONTEXT.md (D-14)
    - .planning/phases/08-search-context-sidebar-polish/08-RESEARCH.md (Vitest+MSW round-trip integration test pattern; sidebar-refresh sketch around line 285-345)
  </read_first>
  <behavior>
    - Mount ChatApp (which mounts ConversationsProvider).
    - MSW handler for GET /api/conversations: call counter switches; first call returns `[]` (empty), second call returns `[{ thread_id: 'thread-happy', last_updated: '...', first_message_preview: 'Surcharge for 15kg Bounce, Bangkok → Nonthaburi' }]`.
    - MSW handler for POST /api/chat: emits a complete fresh-turn happyTurnEvents (using `happyTurnEvents('thread-happy')` from the fixtures — produces meta + 5 traces + answer + done).
    - First assert: after initial mount, sidebar shows the empty-state copy "No conversations yet" (proves first GET resolved with []).
    - User types a query into the chat input + clicks Send.
    - Wait for `screen.getByRole('table')` — proves the answer rendered (which means `done` fired AND `void conversations.refresh()` ran).
    - Assert: sidebar now displays the new thread's first_message_preview text (proves the shared provider propagated the post-`done` refresh — if the sidebar were running its own `useConversations` instance, the prior page-mount-only fetch would NOT have updated it and the empty-state copy would still be visible).
    - Assert: GET /api/conversations call counter equals 2 (mount + post-`done` refresh).
    - The test must FAIL today on a baseline where the sidebar runs its own hook instance — proves it's the provider migration that fixes the sidebar refresh.
  </behavior>
  <action>
    Append to `frontend/__tests__/components/ChatApp.integration.test.tsx` after the existing `describe('ChatApp HITL integration (D-15.3)', () => { ... });` block. Add a NEW describe block for the D-14 test:

```typescript
describe('ChatApp sidebar refresh integration (Phase 8 D-14)', () => {
  it('completed turn appends new thread to ConversationSidebar without page reload (audit Issue 4)', async () => {
    const user = userEvent.setup();

    // Two-call MSW handler: empty list first, then [thread-happy] after refresh.
    let convCallCount = 0;
    server.use(
      http.get('http://localhost:8000/api/conversations', () => {
        convCallCount += 1;
        if (convCallCount === 1) {
          return HttpResponse.json([]);
        }
        return HttpResponse.json([
          {
            thread_id: 'thread-happy',
            last_updated: '2026-05-04T10:00:00Z',
            first_message_preview:
              'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
          },
        ]);
      }),
      // Fresh-turn happy SSE: meta → 5 traces → answer → done.
      http.post('http://localhost:8000/api/chat', () => {
        const stream = makeSseStream(happyTurnEvents('thread-happy'));
        return new HttpResponse(stream, {
          headers: { 'Content-Type': 'text/event-stream' },
        });
      }),
    );

    render(<ChatApp />);

    // Wait for the first GET /api/conversations to settle (empty list →
    // sidebar's empty-state copy is in the document).
    await waitFor(() =>
      expect(
        screen.getByText(/No conversations yet/),
      ).toBeInTheDocument(),
    );

    // Send a query — fires SSE turn that completes with `done`.
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    // Wait for the answer's table to render — proves `done` fired and
    // void conversations.refresh() ran in the post-`done` useEffect.
    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // The sidebar now shows the thread WITHOUT a page reload — this only
    // works if useConversations is a single shared provider instance
    // (audit Issue 4 closure). If the sidebar were running its own
    // useState/useEffect, it would still show "No conversations yet".
    await waitFor(
      () =>
        expect(
          screen.getByText(/Surcharge for 15kg Bounce/),
        ).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // Exactly two GET /api/conversations calls: provider mount + post-`done` refresh.
    // (Pitfall 3 — useMemo on context value AND deps narrowing on conversations.refresh
    // together prevent unbounded refetches.)
    expect(convCallCount).toBe(2);
  });
});
```

       Imports needed at the top of the file (most are already present from existing tests; verify before duplicating):
       - `happyTurnEvents` from `'../fixtures/sse'` — VERIFY it's exported (line 121-128 of `frontend/__tests__/fixtures/sse.ts` confirms yes); add it to the existing import: `import { HAPPY_PAYLOAD, HAPPY_TRACE, PARTIAL_PAYLOAD, makeSseStream, happyTurnEvents } from '../fixtures/sse';`

    Run `cd frontend && npm test -- --run __tests__/components/ChatApp.integration.test.tsx`. 3 tests total — 2 existing (approve, deny) + 1 new (sidebar refresh) — all must PASS.

    Run `cd frontend && npm test -- --run`. Full FE suite green.

    Commit: `test(08-02): add D-14 sidebar-refresh integration test (audit Issue 4 closure)`.

    Constraints:
    - Do NOT modify the existing 2 tests (approve + deny from Plan 06-03 D-15.3) — they validate Phase 6 contracts and must remain byte-identical except possibly for the import line addition of `happyTurnEvents`.
    - Do NOT install both an `installPauseThenResumeHandler`-style handler AND the new fresh-turn handler in the same test — this test uses a fresh-turn happy stream only.
    - Do NOT assert against an exact item count or timestamp — the test is about the propagation contract (empty → has thread), NOT the specific items shape.
    - Use `await waitFor(() => ..., { timeout: 4000 })` for SSE-driven assertions to match the existing test conventions (line 130, 150, 192 of the file).
    - Do NOT depend on the default `SAMPLE_CONVERSATIONS` from `agentState.ts` — install per-test handlers so the empty/non-empty switch is fully controlled.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npm test -- --run __tests__/components/ChatApp.integration.test.tsx</automated>
  </verify>
  <acceptance_criteria>
    - File frontend/__tests__/components/ChatApp.integration.test.tsx contains the literal string `Phase 8 D-14`
    - File frontend/__tests__/components/ChatApp.integration.test.tsx contains the literal string `convCallCount`
    - File frontend/__tests__/components/ChatApp.integration.test.tsx contains the literal string `No conversations yet`
    - File frontend/__tests__/components/ChatApp.integration.test.tsx contains the literal string `Surcharge for 15kg Bounce`
    - File frontend/__tests__/components/ChatApp.integration.test.tsx contains the literal string `expect(convCallCount).toBe(2)`
    - File frontend/__tests__/components/ChatApp.integration.test.tsx imports `happyTurnEvents` from `'../fixtures/sse'`
    - Command `cd frontend && npm test -- --run __tests__/components/ChatApp.integration.test.tsx` exits with status 0 (3 tests passing — 2 existing + 1 new)
    - Command `cd frontend && npm test -- --run` exits with status 0 (full FE suite green — Plan 08-01 + 08-02 combined)
    - Command `cd frontend && npx tsc --noEmit` exits with status 0
  </acceptance_criteria>
  <done>
    Sidebar-refresh integration test passes; full FE suite green; audit Issue 4 closed end-to-end with a drift-prevention test that exercises the production prop chain.
  </done>
</task>

</tasks>

<verification>
- FE: `cd frontend && npm test -- --run __tests__/hooks/useConversations.test.tsx` — 3/3 tests pass with provider wrapper
- FE: `cd frontend && npm test -- --run __tests__/components/ChatApp.integration.test.tsx` — 3/3 tests pass (approve, deny, sidebar refresh)
- FE: `cd frontend && npm test -- --run` — full FE suite green
- FE: `cd frontend && npx tsc --noEmit` — 0 errors
- File rename verification: `test -f frontend/hooks/useConversations.tsx && ! test -f frontend/hooks/useConversations.ts && git log --follow --oneline frontend/hooks/useConversations.tsx | head -2` — should show history continuity (not a new-file commit only)
- grep `<ConversationsProvider>` frontend/components/ChatApp.tsx — exactly 1 match in JSX
- grep `function ChatAppInner` frontend/components/ChatApp.tsx — exactly 1 match
- grep `conversations.refresh]` frontend/components/ChatApp.tsx — at least 1 match (deps array narrowed)
- grep `useMemo` frontend/hooks/useConversations.tsx — at least 1 match (Pitfall 3)
</verification>

<success_criteria>
1. ROADMAP §Phase 8 Success Criterion 3: Conversation sidebar updates immediately after a completed turn without requiring a page reload (single useConversations instance shared via context) — VERIFIED via D-14 integration test
2. Audit Issue 4 closed: provider chain replaces 3 independent useState instances; refresh() propagates to all consumers
3. UI-06 restored from "degraded" to fully satisfied
4. Pitfall 1 mitigated: ChatAppInner sits below the provider in the React tree
5. Pitfall 2 mitigated: existing useConversations.test.tsx tests pass with renderHook wrapper
6. Pitfall 3 mitigated: useMemo on provider value AND narrowed effect deps prevent unbounded refetches
7. Pitfall 6 mitigated: 'use client' directive preserved at line 1 of useConversations.tsx
8. No regression: existing 2 ChatApp.integration tests (approve + deny from Plan 06-03 D-15.3) still pass
9. Manual smoke (deferred to verify-phase): live `npm run dev`, send a query, observe sidebar entry appears within ~1s of the answer rendering
</success_criteria>

<output>
After completion, create `.planning/phases/08-search-context-sidebar-polish/08-02-SUMMARY.md` documenting:
- The git-rename of useConversations.ts → .tsx (verify with `git log --follow`)
- ChatApp split structure: outer ChatApp mounts ConversationsProvider, inner ChatAppInner consumes
- Pitfall 3 mitigation: useMemo on context value + narrowed useEffect deps to `conversations.refresh`
- Test counts: useConversations.test.tsx still 3 tests (now wrapped); ChatApp.integration.test.tsx now 3 tests (was 2)
- Any deviations during execution (per Phase 6 / 7 SUMMARY pattern)
- Confirmation that ConversationSidebar.tsx and SurchargeHistoryChart.tsx call sites were left untouched (D-05 — public hook contract unchanged)
</output>
