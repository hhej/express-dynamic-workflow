# Phase 8: Search Context Wiring + Sidebar Polish - Research

**Researched:** 2026-05-05
**Domain:** React Context state-sharing + LangGraph state forwarding + TypeScript discriminated-union extension + Vitest+MSW drift-prevention testing
**Confidence:** HIGH

## Summary

Phase 8 closes the last two minor cross-phase integration gaps from the v1.0 milestone audit (Issues 4 + 6) without touching any agent reasoning, tool, or graph topology. The work is **three small surface changes plus three drift-prevention tests**:

1. Backend: one-line addition to `response_node.py` `final_payload` dict (forward `state.get("search_context")`).
2. Frontend types: one-token addition to the `FinalStatus` union (`'search_only'`).
3. Frontend rendering: one-case addition to the `MessageList` status switch (explicit `case 'search_only'` returning `<MarkdownAnswer />`).
4. Frontend state: refactor `useConversations` from per-call-site `useState` into a single `ConversationsProvider` Context-backed instance shared across `ChatApp`, `ConversationSidebar`, and `SurchargeHistoryChart`.

CONTEXT.md has fully locked all 16 implementation decisions (D-01 through D-16). Research's role is **verification and enrichment**, not exploration: confirm the decisions are technically sound, surface the React-19 idiom for the Context provider, and document the Vitest+MSW pattern Phase 8 reuses verbatim from Phases 6 + 7.

**Primary recommendation:** Two-wave plan split. **Wave 1**: backend `response_node` field forwarding + BE drift-prevention test, plus FE types extension + `MessageList` switch case + `'search_only'` rendering test (all changes touch independent files; can land together). **Wave 2**: `ConversationsProvider` migration with `.ts` → `.tsx` rename, three call-site swaps, and the sidebar-refresh integration test (touches ChatApp + Sidebar + Dashboard; needs to land atomically). A single-plan path is also defensible since total LOC is small (~120 lines net delta including tests).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sidebar state-sharing (Issue 4 — `useConversations` runs as 3 independent instances)**

- **D-01:** Convert `useConversations` to a React Context-backed shared instance. New `ConversationsProvider` component owns the single `useState`/`useEffect`/`useCallback` block currently in `useConversations.ts`. Public hook name stays `useConversations` (call sites unchanged). `useConversations()` throws a clear error when called outside the provider — idiomatic React, matches audit §7 recommendation. Closes audit Issue 4.
- **D-02:** Provider lives **inside** `ChatApp.tsx` (top of the rendered tree, wrapping the existing `<main>...</main>` three-column layout). Smallest blast radius — both `ConversationSidebar` (rendered directly under `<main>`) and `SurchargeHistoryChart` (rendered through `ChatColumn`'s dashboard tab) sit under `ChatApp`'s subtree. No `frontend/app/page.tsx` or `frontend/app/layout.tsx` changes; no new wrapper component above `ChatApp`.
- **D-03:** `SurchargeHistoryChart.tsx` consumes the **same** shared instance (single source of truth). When `ChatApp.refresh()` fires on a completed turn, the dashboard's surcharge history chart updates too. One fetch per refresh, three readers; eliminates a redundant `/api/conversations` call. Matches audit's single-source-of-truth lesson.
- **D-04:** `refresh()` fires **after every completed turn** — and only there. The single existing call site at `frontend/components/ChatApp.tsx:70` (`void conversations.refresh()` inside the `chat.finalPayload` `useEffect`) is unchanged in location; the change is that it now propagates to all consumers via the shared provider instance. HITL approve/deny resume flows through the same `done` path so it's covered too. No on-error refresh, no background polling.
- **D-05:** Public hook contract is unchanged: `{ items, loading, error, refresh, resume }` — same return shape as today. The 3 call-site swaps (`ChatApp.tsx:24`, `ConversationSidebar.tsx:16`, `SurchargeHistoryChart.tsx:29`) keep their existing destructuring; only the underlying source changes from "own state per call" to "shared state from context." Tests in `frontend/__tests__/hooks/useConversations.test.tsx` get a thin `<ConversationsProvider>` wrapper around `renderHook` and otherwise stay as-is.
- **D-06:** File layout: provider component + hook live in `frontend/hooks/useConversations.tsx` (rename from `.ts` to `.tsx` because the provider returns JSX). Single file, two named exports (`ConversationsProvider`, `useConversations`). No separate `frontend/components/providers/` directory introduced for one feature.

**search_context payload shape (Issue 6 backend)**

- **D-07:** `response_node` `final_payload` **always** includes `search_context`. Construction: `final_payload["search_context"] = state.get("search_context")` — `None` when state lacks it. Site: `backend/agent/nodes/response_node.py:307-312` (the dict literal building `final_payload`). Always-present keys make tests simpler, eliminate the FE `undefined` vs `null` ambiguity that is the audit's exact bug class (Issue 3 root cause), and mirror Phase 7 D-04's "single source of truth on the wire" pattern.
- **D-08:** No normalization of empty-summary search_context (passing through whatever is in state). `SearchContextLine` already returns `null` when `summary` is blank/whitespace; duplicating that gate upstream in `response_node` is redundant complexity.

**search_only status branch and rendering (Issue 6 frontend)**

- **D-09:** Extend `FinalStatus` union to include `'search_only'`. Site: `frontend/types/agent.types.ts:39`. Backend already emits this status — the FE type currently lies. Required type-system change for audit Issue 6 success criterion 2.
- **D-10:** `FinalPayload.search_context` stays declared as `SearchContext | null` (unchanged from today's `frontend/types/agent.types.ts:72`). Type is already optional+nullable; no escalation to required like Phase 7 D-04 message_id. Different semantics: `message_id` is mandatory identity for feedback wiring; `search_context` is genuinely optional content (most turns don't trigger search). Type change is contained to the union extension only.
- **D-11:** `MessageList` switch gains an explicit `case 'search_only'` returning `<MarkdownAnswer payload={payload} />`. Site: `frontend/components/chat/MessageList.tsx:54-62`. `MarkdownAnswer` already renders `SearchContextLine` above the prose when `payload.search_context.summary` is present — no `MarkdownAnswer` changes needed. Explicit case > default fallthrough.
- **D-12:** Trace panel rendering is unchanged. Sources are surfaced through the chat answer surface only (via `SearchContextLine`'s collapsible `<details>` block with `target="_blank" rel="noopener noreferrer"` source links). Trace step rows continue to show the `search_agent` step's `tool_input`/`tool_output` as JSON.

**Drift-prevention tests (audit lesson)**

- **D-13:** **Backend test:** add a `response_node` test (extend `backend/tests/test_response_node.py`) asserting `final_payload['search_context']` is the exact `state['search_context']` dict when state has it, AND is `None` when state doesn't. Two assertions, single test function.
- **D-14:** **Frontend sidebar-refresh integration test:** Vitest+MSW round-trip in `ChatApp.integration.test.tsx`. MSW handler for `GET /api/conversations` returns `[thread-A]` first call, `[thread-A, thread-B]` second call; MSW handler for `POST /api/chat` emits a complete fresh-turn SSE stream including `done`; assert that after the turn completes, `ConversationSidebar` displays both `thread-A` and `thread-B` without a page reload.
- **D-15:** **Frontend 'search_only' rendering test:** extend `frontend/__tests__/components/SearchContextLine.test.tsx` OR add a new `frontend/__tests__/components/MessageList.search_only.test.tsx` (planner picks). Mount `MessageList` with a `[{ role: 'assistant', payload: { status: 'search_only', search_context: {...with sources...}, surcharge_result: null, ... } }]`; assert (a) `SearchContextLine` text "Market context:" is in the document, (b) the sources `<details>` toggle is in the document, (c) NO surcharge breakdown table is in the document.
- **D-16:** No Playwright E2E for Phase 8. Bug class is catchable at the Vitest+MSW integration layer (faster, deterministic, no flakiness against headless browsers). Reuses the same Phase 6 D-14 / Phase 7 D-09 decision.

### Claude's Discretion

- **Wave / plan splitting.** Likely two plans: (Wave 1: backend response_node 1-line addition + BE test; FE types + MessageList switch case + 'search_only' rendering test — small, low-risk surface) (Wave 2: ConversationsProvider migration + 3 consumer swaps + sidebar-refresh integration test). A single-plan path is also defensible. Planner picks based on dependency analysis.
- **Test file location for D-15.** Extending `SearchContextLine.test.tsx` keeps related tests co-located but the test asserts MessageList behavior; new `MessageList.search_only.test.tsx` is more accurate but adds a file. Both fit.
- **Provider component naming.** `ConversationsProvider` is the obvious choice; `ConversationContextProvider` is more verbose without adding clarity. Planner confirms `ConversationsProvider` and moves on.
- **`useConversations.ts` → `useConversations.tsx` rename mechanics.** Git rename + content swap; planner verifies no `import '@/hooks/useConversations'` ESM-extension-sensitive consumers exist (TypeScript path aliases erase the extension at compile time, so this is safe).
- **Whether to add a separate `useConversationsRefresh()` hook** (write-only, returns the `refresh` callback). Rejected in discuss-phase as overkill for a 3-consumer surface; planner confirms and skips.
- **`refresh()` side-effect ergonomics.** Today the hook auto-fetches on mount via `useEffect`. After provider migration, the auto-fetch fires once when the provider mounts (same behavior as today's first consumer mount). No change.
- **Whether to add a TS-level exhaustiveness check** (`const _check: never = status;`) inside the `MessageList` status switch default branch. Future-proof for new statuses, but adds boilerplate; the explicit `case 'search_only'` (D-11) plus the union narrowing already give the same protection. Planner picks.
- **Bangkok Metro phrasing review.** No new user-facing copy is added in Phase 8 (sources are titles+URLs from Tavily, not project copy). Planner confirms no `central-region`-ish strings creep into provider error messages or test fixtures.

### Deferred Ideas (OUT OF SCOPE)

- **Trace panel sources affordance** (clickable sources rendered inline in the trace step row). Out of audit scope; chat answer is the surface for sources per D-12.
- **`NewsAnswer` component** (dedicated FE component for `'search_only'` status). One-line diff from `MarkdownAnswer` today; v2 if the news-only response ever needs distinctive UX.
- **Background polling of `/api/conversations`** for multi-tab sync. No demo benefit; v2.
- **Playwright E2E for sidebar refresh + search sources rendering.** Bug class is catchable at Vitest+MSW layer; same lesson as Phase 6 D-14 / Phase 7 D-09. v2 if a flow gap surfaces that the integration layer can't catch.
- **Zustand or other global state library.** No precedent in the repo; React Context is idiomatic React for this surface size. v2 if cross-tree shared state ever balloons.
- **`FinalPayload.search_context` upgrade to required (`SearchContext | null`).** Different semantics from message_id (Phase 7 D-04) — search_context is genuinely optional. Type stays optional+nullable per D-10.
- **Tightening `FinalStatus` exhaustiveness via `never` check** in MessageList default branch. Phase 8 D-11 already adds the explicit case; the default fallthrough remains for safety but a future TS strictness pass could enforce exhaustiveness if status semantics ever diverge.
- **Bangkok Metro phrasing in error messages from the new provider.** Generic "useConversations must be used within ConversationsProvider" — no scope reference, safe.
- **Refresh on error / refresh on HITL approve / refresh on resume.** The single `done`-path refresh covers all of these (HITL deny path also goes through `done` after Plan 05-05). No need to add more call sites.
- **Migration of `useConversations.test.tsx` to a renamed `useConversations.test.tsx` post-`.tsx` rename.** Test file stays at the same path; it's the source file that picks up the `.tsx` extension. No test-side migration.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-05 | search_fuel_news tool searches fuel trends via Tavily API for reasoning context | Backend tool + search_agent + state.search_context all shipped in Phase 5 (Plan 05-04). Phase 8 closes the last-mile rendering gap so the sources are visible in the chat answer (via existing `SearchContextLine` component). The tool is functionally complete; this phase is rendering completeness only — D-07 forwards `state.search_context` into `final_payload` so the FE can read it. |
| UI-02 | Reasoning trace panel showing agent steps, tool calls, and decisions for each query | Backend already emits `status='search_only'` in `response_node` (Plan 05-10 gap-3 fix). FE `FinalStatus` union is missing the value, so the dispatcher silently falls through to the default branch instead of rendering the explicit search-only treatment. D-09 + D-11 declare the value and dispatch it. |
| UI-06 | Conversation history sidebar for resuming past threads | Sidebar UI shipped in Phase 4 with a working `useConversations` hook. The audit found that each `useConversations()` call instantiates an independent `useState`/`useEffect` cell — when `ChatApp` calls `refresh()` after a completed turn, only `ChatApp`'s instance updates; the sidebar's separate instance still holds the stale list. D-01–D-06 promote `useConversations` to a Context-backed shared instance so a single `refresh()` call propagates to all three consumers. |

All three requirements are already marked Complete in REQUIREMENTS.md. The audit downgraded them via cross-phase integration check; Phase 8 restores them to fully-satisfied.
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Budget:** Free-tier APIs only (Gemini Flash, Google Maps, EPPO, Tavily). Phase 8 introduces zero new external API calls — all changes are internal wiring.
- **LLM:** Gemini 2.0 Flash only. Phase 8 introduces zero new LLM calls. `response_node` remains deterministic Python f-string rendering (no Gemini in the response hop, per Phase 3 D-11 / RESEARCH OQ 3+5).
- **Repo structure:** Brief-mandated `agent/`, `app/`, `data/`, `docs/`, `notebooks/`. Phase 8 stays inside `backend/agent/nodes/` (BE) and `frontend/{components,hooks,types,__tests__}/` (FE) — no new top-level directories.
- **Secrets:** Never commit `.env`. Phase 8 adds zero secret-handling code. The new provider error message uses generic React idiom only (no env values, no secrets).
- **Git practice:** Descriptive commit messages, feature branches, IT Lead majority commits (graded 20%). Phase 8 plans should commit per-task with clear `feat(08)` / `test(08)` / `refactor(08)` slugs.
- **Local reproducibility (CLAUDE.md + PROJECT.md):** No new external dependencies. React Context is built into React 19; no `npm install` required. Verified — all required packages are already in `frontend/package.json`.
- **Python conventions (CLAUDE.md §Python):** PEP 8, line length 88, type hints, Google-style docstrings, `from __future__ import annotations`. Phase 8 BE change is a single dict-literal addition inside an existing function — convention-preserving.
- **TypeScript conventions (CLAUDE.md §TypeScript):** PascalCase components, `useX.ts/.tsx` hooks (`.tsx` when JSX is returned), camelCase utilities, `*.types.ts`, `@/` path aliases, JSDoc on public APIs. The `ConversationsProvider` component will be PascalCase + `.tsx`; rename `useConversations.ts` → `useConversations.tsx` is correct per convention since the file now exports a JSX-returning component alongside the hook.
- **Agent/node conventions (CLAUDE.md §LangGraph Agent Nodes):** Each node in `backend/agent/nodes/<node>.py`, exports a single callable matching the node name, uses `AgentState` type hint. `response_node` already follows this; no structural change.
- **Bangkok Metro phrasing (resolved backlog 999.2):** No `central-region`-ish strings introduced. Verified — Phase 8 introduces no new user-facing copy (sources are Tavily titles/URLs; provider error message is generic React idiom).
- **GSD workflow enforcement:** All Edit/Write tools must run inside a GSD command. Phase 8 will be executed via `/gsd:execute-phase 08` after planning.

## Standard Stack

### Core (already in use, no install required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | ^19.2.5 | UI library — Context API for cross-component state sharing | Phase 8 D-01 uses `createContext` + `useContext` (built-in, zero deps). React 19 added the Context-as-Provider shorthand (`<MyContext value={...}>`) but the legacy `<MyContext.Provider>` syntax still works and matches existing repo patterns. |
| Next.js | ^15.5.15 | App framework — `'use client'` directive on the provider file | Existing pattern; all `frontend/components/**` and `frontend/hooks/**` files use `'use client'` directive at the top. |
| TypeScript | ^5 (via `@types/react` 19) | Static typing for the Context value shape and discriminated union extension | Existing pattern. The `FinalStatus` union extension is single-token; the Context value type is the existing `useConversations` return shape (`{ items, loading, error, refresh, resume }`) — no new shapes. |
| Vitest | (via dev dep `@vitejs/plugin-react` ^6.0.1) | Frontend test runner | Phase 4 → Phase 7 established pattern. `npm test` runs the suite. |
| MSW | ^2.13.6 | Network mocking for SSE + REST integration tests | Phase 6 D-15.3 → Phase 7 D-09 reused. Phase 8 D-14 extends `ChatApp.integration.test.tsx`. |
| @testing-library/react | ^16.3.2 | DOM-level test queries (`render`, `screen`, `waitFor`) | Existing pattern. `renderHook` + new `<ConversationsProvider>` wrapper for D-05 hook-test migration. |
| pytest | (existing) | Backend test runner | Phase 1 → Phase 7 established. Phase 8 BE test extends `backend/tests/test_response_node.py`. |

### Supporting (already in use)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| react-markdown | ^10.1.0 | Markdown rendering inside MarkdownAnswer | Reference only — no changes. The `'search_only'` branch routes to existing `MarkdownAnswer` per D-11. |
| remark-gfm | ^4.0.1 | GFM tables in markdown | Reference only — no changes. |

### Alternatives Considered (rejected per CONTEXT.md decisions)

| Instead of | Could Use | Why Rejected (per CONTEXT) |
|------------|-----------|---------------------------|
| React Context | Zustand / Jotai / Redux Toolkit | No precedent in the repo (Deferred §"Zustand or other global state library"). Three consumers + one piece of state is the smallest possible context surface; introducing a new global-state lib for it would be over-engineering. Idiomatic React = built-in Context. |
| `<ConversationsProvider>` wrapper component | Direct `useContext` with an exported `ConversationsContext` | The provider component owns the `useState`/`useEffect`/`useCallback` block (the "implementation" of the hook). The previous file already encapsulates this — D-01 keeps the encapsulation, just lifts it out of the per-call instantiation. Direct `useContext` would force every consumer to set up their own state. |
| New `useConversationsRefresh()` write-only hook | Single `useConversations` hook returning `{ refresh }` plus other fields | Discretion item — rejected as overkill for 3 consumers (CONTEXT §Claude's Discretion). |
| New SSE event type `search_context_event` | Single-key addition to existing `answer` payload | Out of scope (CONTEXT §Explicitly out of scope) — no SSE event contract change; same precedent as Phase 7 D-03. |
| Promoting `FinalPayload.search_context` to required | Keep as `SearchContext \| null` (today's shape) | D-10 — different semantics from `message_id`. Most turns don't trigger search; type stays optional+nullable. |

**Installation:** Zero new dependencies. Phase 8 uses only what's already in `frontend/package.json` and `requirements.txt`.

**Version verification:** All versions above are read directly from `frontend/package.json` (verified via `Read` tool, line-numbered). No fresh `npm view` lookup needed because no new packages are being added.

## Architecture Patterns

### React Context Provider for cross-tree shared state (NEW pattern for this repo)

**What:** A Context object holds the single shared instance of a stateful hook's value; a wrapper component (`ConversationsProvider`) renders the `Context.Provider` with the value derived from a single `useState`/`useEffect`/`useCallback` block; consumers call a small wrapper hook (`useConversations()`) that calls `useContext` and throws if the context is the sentinel/undefined value.

**When to use:** When 3+ consumers in the same subtree need to read/write the same state and prop-drilling would require routing the same `{items, loading, error, refresh}` through 2+ intermediate components that don't otherwise care about the state. Phase 8 has exactly this shape — `ChatApp`, `ConversationSidebar` (under `<main>`), and `SurchargeHistoryChart` (under `ChatColumn`'s dashboard tab). Prop-drilling would touch `ChatColumn` purely for forwarding.

**Example (verified against React 19 docs — react.dev/reference/react/createContext):**

```typescript
// Source: https://react.dev/reference/react/createContext (React 19 official)
'use client';
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api } from '@/lib/api';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { ConversationDetail, ConversationSummary } from '@/types/api.types';

interface ConversationsContextValue {
  items: ConversationSummary[];
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  resume: (threadId: string) => Promise<ConversationDetail>;
}

// Sentinel `null` lets the consumer hook detect "called outside provider" cleanly.
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

  return (
    <ConversationsContext.Provider value={{ items, loading, error, refresh, resume }}>
      {children}
    </ConversationsContext.Provider>
  );
}

/**
 * Read the shared conversations state. Throws when called outside
 * <ConversationsProvider> — matches the React-19 idiomatic "fail loudly"
 * pattern (react.dev best practice).
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

**Key points (verified):**
- The sentinel `null` (instead of an empty object `{}`) makes "called outside provider" a runtime-detectable failure, which is the React-recommended pattern when `defaultValue` doesn't represent a meaningful state.
- `useCallback` with empty deps is correct — `setItems`/`setLoading`/`setError` are stable references and `api` is a module-level import.
- The auto-fetch `useEffect` fires once when the provider mounts (under `ChatApp`), exactly matching today's behavior on the first consumer mount. No double-fetch concern.
- React 19 also supports `<ConversationsContext value={...}>` shorthand (without `.Provider`), but the legacy `.Provider` form remains valid and is more explicit. Either is fine; planner picks.

### Optional + nullable field with explicit null-when-absent on the wire

**What:** Backend always emits the field key, with a `None`/`null` value when the data is absent, instead of conditionally including the key.

**When to use:** Any cross-language wire field that the consumer needs to test for. Eliminates the `undefined` vs `null` ambiguity that was the root cause of audit Issue 3.

**Example (Phase 8 D-07 application — verified pattern from Plan 05-04 and Phase 7 D-04):**

```python
# Source: backend/agent/nodes/response_node.py:307-312 (today)
# After D-07 change:
final_payload = {
    "markdown": markdown,
    "surcharge_result": surcharge_result,
    "capped": capped,
    "status": status,
    "search_context": state.get("search_context"),  # NEW: always present, None when state lacks it
}
```

The FE type already declares `search_context?: SearchContext | null` (verified at `frontend/types/agent.types.ts:72`), so no FE type change is needed for D-07. D-09 separately extends the `FinalStatus` union — orthogonal change.

### Discriminated-union extension pattern

**What:** Adding a new value to a TypeScript union and a corresponding `case` in the dispatching `switch` statement.

**When to use:** When the backend extends an enum/Literal and the frontend dispatches by status. Phase 4 D-12 established this for `FinalStatus`; Phase 8 D-09 + D-11 extends it.

**Example (verified against today's `MessageList.tsx:54-62`):**

```typescript
// Source: frontend/components/chat/MessageList.tsx (today's renderAssistant switch, lines 54-62)
// After D-11 change:
switch (payload.status) {
  case 'clarify':
    return <ClarifyCard payload={payload} />;
  case 'partial':
    return <PartialCard payload={payload} />;
  case 'search_only':                                // NEW per D-11
    return <MarkdownAnswer payload={payload} />;     // Reuses existing component
  case 'ok':
  default:
    return <MarkdownAnswer payload={payload} />;
}
```

`MarkdownAnswer` already conditionally renders `<SearchContextLine>` above the prose when `payload.search_context.summary` is non-blank (verified at `frontend/components/chat/MarkdownAnswer.tsx:23-33`). The `'search_only'` case routes to the same component, so no `MarkdownAnswer` change is required — the rendering wire is already complete on the FE; only the dispatch case is missing.

### Vitest+MSW round-trip integration test pattern (REUSED from Phases 6 + 7)

**What:** Mount the production component (`ChatApp`), install MSW handlers that simulate the backend SSE + REST contracts, drive interactions with `userEvent`, and assert on rendered DOM after the round trip completes.

**When to use:** Cross-phase contract assertions where unit tests pass per layer but the wire boundary breaks. The audit's lesson is that this is the only test layer that catches the bug class Phase 8 closes.

**Example (Phase 8 D-14 sketch — extends today's `ChatApp.integration.test.tsx` pattern):**

```typescript
// Source: frontend/__tests__/components/ChatApp.integration.test.tsx (Phase 6 / 7 baseline)
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';

it('D-14 sidebar refresh: completed turn appends new thread to ConversationSidebar without page reload', async () => {
  const user = userEvent.setup();

  // Two-call MSW handler for /api/conversations: empty first, then [thread-A].
  let convCallCount = 0;
  server.use(
    http.get('http://localhost:8000/api/conversations', () => {
      convCallCount += 1;
      if (convCallCount === 1) return HttpResponse.json([]);
      return HttpResponse.json([
        {
          thread_id: 'thread-A',
          last_updated: '2026-05-04T10:00:00Z',
          first_message_preview: 'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
        },
      ]);
    }),
    // Standard happy turn SSE for /api/chat (reuses HAPPY_TRACE + HAPPY_PAYLOAD).
    http.post('http://localhost:8000/api/chat', () => {
      const stream = makeSseStream(happyTurnEvents('thread-A'));
      return new HttpResponse(stream, {
        headers: { 'Content-Type': 'text/event-stream' },
      });
    }),
  );

  render(<ChatApp />);

  // Wait for first /api/conversations call to settle (empty list).
  await waitFor(() =>
    expect(screen.getByText(/No conversations yet/)).toBeInTheDocument(),
  );

  // Send a query — fires SSE turn that completes with `done`.
  await user.type(
    screen.getByPlaceholderText(/Ask about a surcharge/),
    'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
  );
  await user.click(screen.getByRole('button', { name: 'Send message' }));

  // Wait for the chat answer to render (proves `done` fired and refresh() ran).
  await waitFor(
    () => expect(screen.getByRole('table')).toBeInTheDocument(),
    { timeout: 4000 },
  );

  // Assert the sidebar now shows thread-A WITHOUT a page reload.
  // (If the sidebar instance were separate from ChatApp's, it would still
  //  show the empty-state copy because its own useState was never updated.)
  await waitFor(() =>
    expect(
      screen.getByText(/Surcharge for 15kg Bounce/),
    ).toBeInTheDocument(),
  );
  expect(convCallCount).toBe(2); // mount + post-`done` refresh.
});
```

### Anti-Patterns to Avoid

- **Don't add a `useConversationsRefresh` write-only hook** — three consumers can comfortably destructure `refresh` from the existing return; introducing a second hook for one method splits the API surface for no gain. (CONTEXT §Discretion explicitly rejects this.)
- **Don't pass `defaultValue` to `createContext` as if it were the real shape** — use `null` as the sentinel so consumers detect "called outside provider" and throw a clear error. The audit recommendation (§7) is to make the missing-provider case fail loudly.
- **Don't introduce a `frontend/components/providers/` directory** — single feature, single file (`useConversations.tsx`), two named exports. Per CONTEXT D-06.
- **Don't add background polling of `/api/conversations`** — no demo benefit; v2 if multi-tab sync is ever needed. (CONTEXT §Deferred.)
- **Don't normalize empty-summary search_context in `response_node`** — `SearchContextLine` already has the gate; duplicating it upstream is redundant. (CONTEXT D-08.)
- **Don't render sources in the trace panel as clickable list** — chat answer is the surface for sources per D-12; trace step rows stay JSON-only. v2 polish.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-component shared state | Custom event bus, `window` global, manual subscription registry | React Context (`createContext` + `useContext`) | Built-in, zero deps, idiomatic, type-safe. CONTEXT D-01 already locks this. |
| Provider missing-detection | Defensive `if (!ctx) return defaultData` everywhere | Single `if (ctx === null) throw new Error(...)` in the wrapper hook | Audit §7 recommendation — fail loudly. Consumers don't need defensive code. |
| SSE stream mocking | Manual fetch monkey-patching | MSW `http.post` returning `HttpResponse(makeSseStream(events))` | Existing helper in `frontend/__tests__/fixtures/sse.ts:8-18` (verified). Phase 6 / 7 baseline reused. |
| Two-call MSW switching | Conditional handler with closure-mutated counter | Same — that's the existing pattern (`installPauseThenResumeHandler` at `ChatApp.integration.test.tsx:78-99`) | Reuses the verified pattern. D-14 just swaps "pause vs resume" logic for "first vs second" call list. |
| Forwarding `search_context` over the wire | Custom envelope, dual-event SSE, side-channel | Single-key addition to existing `final_payload` dict | CONTEXT D-07 + Phase 7 D-04 precedent — single source of truth on the wire. |
| Markdown rendering for `'search_only'` | Custom `NewsAnswer` component | Existing `MarkdownAnswer` (already renders `SearchContextLine` above prose) | CONTEXT explicit OOS — `MarkdownAnswer` is already correct for this case. |

**Key insight:** Phase 8 is a "wire what's already built" phase. Every problem above is solved by an existing repo pattern or framework primitive — the work is connection, not construction.

## Runtime State Inventory

> Phase 8 is **not** a rename/refactor/migration phase. It introduces a new code structure (Context provider) but does not touch persisted data, live service config, OS state, secrets, or build artifacts.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by reading `backend/agent/state.py` references in CONTEXT and confirming `state.search_context` shape is unchanged from Plan 05-04. No checkpoint migration needed; existing `data/checkpoints.db` rows stay valid because the `final_payload` field addition is purely on the wire (final_payload is regenerated each turn, never persisted long-term in the same shape consumed by FE). | None |
| Live service config | None — verified by checking that no Tavily/Langfuse/Google Maps configuration changes. Phase 8 does not touch external API call sites. | None |
| OS-registered state | None — verified by checking that no new processes, ports, schedulers, or daemons are introduced. Phase 8 stays inside the existing FastAPI + Next.js dev servers. | None |
| Secrets/env vars | None — verified by Grep for `os.environ` / `process.env` in CONTEXT scope. No new env vars; no renames of existing ones. | None |
| Build artifacts | One concern: `useConversations.ts` → `useConversations.tsx` rename. Action: ensure git tracks this as a rename (not delete + add) so blame history is preserved. Verify via `git status` after the rename. TypeScript path aliases (`@/hooks/useConversations`) erase the file extension at compile time, so no consumer needs an import update. Confirmed via Grep search of CONTEXT canonical refs — all 3 consumer call sites use `@/hooks/useConversations` without a file extension. | Use `git mv` (or git-renamed via Edit if no `git mv` available); verify via `git status` shows "renamed:" not "deleted:" + "new file:". |

## Common Pitfalls

### Pitfall 1: Provider mounted below a consumer (consumer renders first, gets `null` from context, throws)

**What goes wrong:** If `ConversationsProvider` is rendered inside a component that already calls `useConversations()` at its top level (or if a sibling above it calls it), `useContext` returns `null` and the wrapper hook throws.

**Why it happens:** React renders parents before children. `ChatApp` calls `useConversations()` at line 24 today; if the provider is rendered as part of `ChatApp`'s return JSX without restructuring, `ChatApp` itself reads context BEFORE its own provider runs.

**How to avoid:** Per CONTEXT D-02, the provider wraps the returned JSX (`<main>`). For `ChatApp` to consume from the same provider it renders, either (a) split `ChatApp` into a thin outer component that mounts `<ConversationsProvider>` and a thin inner component that calls `useConversations()` and renders the three columns, OR (b) keep ChatApp's `useConversations()` call after restructure but understand that ChatApp itself sits OUTSIDE the provider — only its children consume. CONTEXT explicitly mentions this in D-02 and §code_context: "Move the existing `void conversations.refresh()` call (D-04) into the provider-aware code path — likely via a thin internal component or by reading `useConversations()` after wrapping. Planner picks the cleanest split."

**Warning signs:** Tests throw "useConversations() must be called inside <ConversationsProvider>" when running `ChatApp.test.tsx` or `ChatApp.integration.test.tsx`. The plan MUST address the split-vs-restructure choice explicitly.

**Recommended fix (planner discretion):** Split `ChatApp` into:
```typescript
export function ChatApp() {
  return (
    <ConversationsProvider>
      <ChatAppInner />
    </ConversationsProvider>
  );
}

function ChatAppInner() {
  const conversations = useConversations(); // safe — inside provider
  // ... rest of the existing ChatApp body, unchanged ...
}
```
This is the smallest restructure and preserves all 100+ lines of existing `ChatApp` body.

### Pitfall 2: `useConversations.test.tsx` breaks because `renderHook` doesn't wrap with the provider

**What goes wrong:** Three existing tests in `frontend/__tests__/hooks/useConversations.test.tsx` call `renderHook(() => useConversations())` directly. After D-01, this throws because there's no provider.

**Why it happens:** `renderHook`'s default wrapper is `<>`. The hook's "called outside provider" guard fires.

**How to avoid:** Per CONTEXT D-05, wrap `renderHook` with the provider:
```typescript
import { ConversationsProvider, useConversations } from '@/hooks/useConversations';

const wrapper = ({ children }: { children: ReactNode }) => (
  <ConversationsProvider>{children}</ConversationsProvider>
);
const { result } = renderHook(() => useConversations(), { wrapper });
```
Apply to all 3 existing tests. This is a one-line-per-test mechanical change.

**Warning signs:** Three test failures with the "must be called inside <ConversationsProvider>" error.

### Pitfall 3: ESLint exhaustive-deps warning when `chat.finalPayload` useEffect lists `conversations`

**What goes wrong:** Today, `ChatApp.tsx:71` lists `[chat.finalPayload, chat.status, conversations]` as the deps of the post-`done` useEffect. After provider migration, `conversations` is the context value object — its identity changes on every provider re-render (every `setItems`/`setLoading`/`setError` call inside the provider). The effect would refire on every conversation list update, potentially causing duplicate appends.

**Why it happens:** Object identity in React useEffect deps. The provider re-creates `{items, loading, error, refresh, resume}` on every render unless wrapped in `useMemo`.

**How to avoid:** Either (a) `useMemo` the context value inside the provider so its identity is stable when its members are stable, OR (b) split the deps to only the function the effect actually calls (`conversations.refresh` — itself stable via `useCallback`).

**Recommended:** Both. `useMemo` the provider value AND list only `conversations.refresh` in the effect deps:
```typescript
// In provider:
const value = useMemo(
  () => ({ items, loading, error, refresh, resume }),
  [items, loading, error, refresh, resume],
);
return <ConversationsContext.Provider value={value}>{children}</ConversationsContext.Provider>;

// In ChatApp useEffect:
useEffect(() => {
  // ... existing logic ...
  void conversations.refresh();
}, [chat.finalPayload, chat.status, conversations.refresh]); // narrowed
```

**Warning signs:** ESLint reports `react-hooks/exhaustive-deps` warning, OR the integration test fails with double-append behavior, OR the sidebar refresh fires more than `convCallCount === 2` (unbounded loop).

### Pitfall 4: TypeScript switch exhaustiveness — adding `'search_only'` to the union without a case branch

**What goes wrong:** TypeScript with `strict: true` will not warn that the `MessageList` switch is missing `'search_only'`; it falls through to `default` silently.

**Why it happens:** No `never` exhaustiveness check exists today (Discretion item D-11 explicitly skips this).

**How to avoid:** D-11 adds the explicit `case 'search_only'` BEFORE landing the union extension (or in the same commit). Order matters: if D-09 lands first and the FE is shipped before D-11, the user sees the same dead-code state as today (just more typed). Plan must atomically land D-09 + D-11.

**Warning signs:** Manual smoke test shows `'search_only'` payloads rendering with `MarkdownAnswer` (correct accidentally — the default branch happens to do the right thing) but the planner can't tell if a future status would also work. The integration test (D-15) catches the case explicitly.

### Pitfall 5: Backend test asserting field presence without checking `None` value

**What goes wrong:** A naive D-13 implementation might assert `'search_context' in final_payload` only, missing the case where the field is `None` vs missing.

**Why it happens:** Python dicts treat key-absent and key-with-None-value differently. The audit's exact bug class.

**How to avoid:** Two assertions in one test, per CONTEXT D-13:
```python
def test_response_forwards_search_context_when_present():
    state = _ok_state()
    state["search_context"] = {"query": "q", "summary": "s", "sources": [], "fetched_at": "z"}
    out = response_node(state)
    assert out["final_payload"]["search_context"] == state["search_context"]

def test_response_search_context_is_none_when_absent():
    state = _ok_state()
    state.pop("search_context", None)  # ensure absent
    out = response_node(state)
    assert "search_context" in out["final_payload"]  # KEY present
    assert out["final_payload"]["search_context"] is None  # VALUE is None
```

**Warning signs:** A future regression where someone sets `final_payload["search_context"] = state.get("search_context") or None` (the `or` swallows empty dicts) passes the first assertion but fails the second only if the test is structured this way.

### Pitfall 6: SSR (Next.js App Router) — ConversationsProvider must be a Client Component

**What goes wrong:** Without `'use client'` directive at the top of `useConversations.tsx`, Next.js tries to render the provider on the server, where `useState`/`useEffect`/`useContext` are not available, and throws.

**Why it happens:** Next.js 15 App Router defaults to Server Components.

**How to avoid:** First line of `useConversations.tsx` MUST be `'use client';`. Today's `useConversations.ts` already has this directive (verified at line 1) — preserve it during the rename.

**Warning signs:** Build error: "Server Components cannot use useState/useContext". Never happens at dev server startup but happens at `next build` time (which would be a regression of audit Issue 1's compile-failure class).

### Pitfall 7: SearchContextLine's empty-summary gate is the only gate

**What goes wrong:** D-08 deliberately skips upstream normalization. If `state["search_context"]` has `summary=""` and `sources=[]`, the FE rendering chain is: `MarkdownAnswer` checks `(sc.summary ?? '').trim().length > 0` → false → does not render `SearchContextLine`. Good. But for `'search_only'` status with truly empty content, `MessageList` still routes through `MarkdownAnswer`, which renders the prose ("Here's the latest market context.") — is that misleading?

**Why it happens:** Backend response_node sets `status='search_only'` based on `sc_has_content = bool(sc and ((sc.get("summary") or "").strip() or sc.get("sources")))` (verified at `response_node.py:253-255`). So if `sc` has neither summary nor sources, `sc_has_content` is False and status falls through to `'clarify'` — meaning `'search_only'` is only emitted when at least one of summary/sources is non-empty.

**How to avoid:** Trust the backend gate (verified). The FE renders the news prose only when status is `'search_only'`, which only happens when there's content to render. No additional gate needed.

**Warning signs:** A `'search_only'` payload arrives with both summary blank AND sources empty — would indicate backend regression. The D-13 test (presence + null) catches the structural side; a future test could catch the semantic side, but not in scope here.

## Code Examples

### Example 1: Backend response_node final_payload extension (D-07)

```python
# Source: backend/agent/nodes/response_node.py (verified line 307-312 today)
# Phase 8 D-07 single-line addition:
final_payload = {
    "markdown": markdown,
    "surcharge_result": surcharge_result,
    "capped": capped,
    "status": status,
    "search_context": state.get("search_context"),  # Phase 8 D-07 — always present
}
```

That's the entire BE production change. The deny-path final_payload at `response_node.py:233-238` should also receive the same field for symmetry — verified by inspecting the deny branch:

```python
# response_node.py:232-241 (today) — needs same D-07 augmentation:
return {
    "final_payload": {
        "markdown": markdown,
        "surcharge_result": None,
        "capped": False,
        "status": "partial",
        "search_context": state.get("search_context"),  # Phase 8 D-07 — preserve provenance on deny
    },
    "reasoning_trace": [deny_trace],
    "messages": prior_messages,
}
```

The deny path already preserves the Market context blockquote via `_market_context_line(state)` (line 204-206) — adding `search_context` to the deny `final_payload` keeps the `SearchContextLine` typed-rendering reachable on the deny branch too. Confirmed deliberate per the existing precedent.

### Example 2: FinalStatus union extension (D-09)

```typescript
// Source: frontend/types/agent.types.ts (verified line 39 today is `export type FinalStatus = 'ok' | 'partial' | 'clarify';`)
// Phase 8 D-09 single-token addition:
export type FinalStatus = 'ok' | 'partial' | 'clarify' | 'search_only';
```

That's the entire type-system change. `FinalPayload.search_context?: SearchContext | null` at line 72 stays exactly as-is per D-10 (verified — already correct).

### Example 3: MessageList switch case extension (D-11)

```typescript
// Source: frontend/components/chat/MessageList.tsx:54-62 (verified today)
// Phase 8 D-11 — single case addition before `case 'ok'`:
switch (payload.status) {
  case 'clarify':
    return <ClarifyCard payload={payload} />;
  case 'partial':
    return <PartialCard payload={payload} />;
  case 'search_only':                                  // NEW per D-11
    return <MarkdownAnswer payload={payload} />;       // Reuses existing component
  case 'ok':
  default:
    return <MarkdownAnswer payload={payload} />;
}
```

### Example 4: 'search_only' rendering test (D-15 — recommended in `MessageList.search_only.test.tsx`)

```typescript
// Source: planner picks file location per CONTEXT D-15 discretion
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageList } from '@/components/chat/MessageList';
import type { ChatMessage } from '@/components/chat/MessageList';

describe('MessageList — search_only status (Phase 8 D-15)', () => {
  it('renders SearchContextLine and sources details, omits surcharge breakdown table', () => {
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        id: 'thread-news-0',
        payload: {
          markdown: "Here's the latest market context.\n\n*Reasoning trace available below.*",
          surcharge_result: null,
          capped: false,
          status: 'search_only',
          message_id: 'thread-news-0',
          search_context: {
            query: 'diesel news',
            summary: 'Diesel up 3% on supply concerns',
            sources: [
              { title: 'Reuters: Thailand diesel rises', url: 'https://reuters.example/x', snippet: '...', published_at: '2026-05-04' },
            ],
            fetched_at: '2026-05-04T10:00:00Z',
          },
        },
      },
    ];
    render(<MessageList messages={messages} threadId="thread-news" />);

    // SearchContextLine renders the typed market context caption.
    expect(screen.getByText('Market context:')).toBeInTheDocument();
    // Sources <details> toggle is in the document.
    expect(screen.getByText('Sources: 1')).toBeInTheDocument();
    // The clickable source link has the safety attributes (verified pattern from SearchContextLine.test.tsx).
    const link = screen.getByRole('link', { name: /Reuters/ });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    // No surcharge breakdown table is rendered (search-only flow has surcharge_result=null).
    expect(screen.queryByRole('table')).toBeNull();
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `<Context.Provider value={...}>` | `<Context value={...}>` (shorthand) | React 19 (2024) | Both syntaxes work in React 19; legacy `.Provider` still supported. Phase 8 can use either; existing repo has no Context precedent so either is "the first one." Slight preference for the legacy form because it's more explicit about provider semantics. |
| `useContext(Ctx)` only inside component bodies | `use(Ctx)` (works in conditionals/loops) | React 19 `use()` hook | Phase 8 doesn't need conditional reads, so `useContext` is fine. `use()` would be over-applying a new feature. |
| Defensive `ctx ?? defaultValue` checks at every consumer | Single throw in the wrapper hook | Long-standing React community pattern, codified in `react.dev` examples | Phase 8 D-01 follows. |

**Deprecated / outdated:**
- React Class-component `Context.Consumer` render-prop pattern — never used in this repo. Don't introduce.
- Legacy `defaultValue` pattern (passing real default state to `createContext`) — replaced by sentinel `null` + throwing hook.

## Open Questions

None. CONTEXT.md has fully locked all 16 implementation decisions plus 7 discretion items. The two minor "planner picks" items (Wave 1+2 split vs single plan; D-15 test file location) are scoped narrowly enough that the planner has unambiguous direction.

## Environment Availability

> Phase 8 introduces zero new external dependencies. All listed tools are confirmed present and at-version via `frontend/package.json` and `requirements.txt` (verified by Read).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| React | All FE changes | yes | ^19.2.5 | — |
| Next.js | FE app framework | yes | ^15.5.15 | — |
| TypeScript types `@types/react` | Context type signatures | yes | ^19 | — |
| Vitest | Test runner | yes | (via @vitejs/plugin-react ^6.0.1) | — |
| MSW | SSE + REST mocking | yes | ^2.13.6 | — |
| @testing-library/react | DOM tests + renderHook | yes | ^16.3.2 | — |
| Python 3.11+ | BE test runner | assumed available (Phase 1 baseline) | 3.11.15 | — |
| pytest | BE test runner | yes | (existing) | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework (frontend) | Vitest + @testing-library/react + MSW (^2.13.6) |
| Framework (backend) | pytest |
| Config file (frontend) | `frontend/vitest.config.ts` (existing, no change needed) |
| Config file (backend) | `pyproject.toml` / `pytest.ini` (existing) |
| Quick run command (FE) | `cd frontend && npm test -- --run [path]` |
| Quick run command (BE) | `pytest backend/tests/test_response_node.py -x` |
| Full suite command (FE) | `cd frontend && npm test -- --run` |
| Full suite command (BE) | `pytest backend/tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-05 | `final_payload['search_context']` forwarded from state (presence + null cases) | unit (BE) | `pytest backend/tests/test_response_node.py::test_response_forwards_search_context_when_present -x` | extend existing file |
| TOOL-05 | `final_payload['search_context']` is None when state lacks it | unit (BE) | `pytest backend/tests/test_response_node.py::test_response_search_context_is_none_when_absent -x` | extend existing file |
| UI-02 | `MessageList` dispatches `'search_only'` to `MarkdownAnswer` and SearchContextLine renders with sources, no surcharge table | integration (FE) | `cd frontend && npm test -- --run __tests__/components/MessageList.search_only.test.tsx` | NEW file (or extend `SearchContextLine.test.tsx` per D-15 discretion) |
| UI-06 | Sidebar updates immediately after a completed turn without a page reload (single shared `useConversations` instance) | integration (FE, MSW round-trip) | `cd frontend && npm test -- --run __tests__/components/ChatApp.integration.test.tsx` | extend existing file |
| (cross) | `useConversations` hook tests pass with the new `<ConversationsProvider>` wrapper | unit (FE) | `cd frontend && npm test -- --run __tests__/hooks/useConversations.test.tsx` | exists; add wrapper per D-05 |

### Sampling Rate

- **Per task commit:** Run only the test file(s) touched by the task (`pytest -x backend/tests/test_response_node.py` for BE; `npm test -- --run __tests__/.../specific.test.tsx` for FE) — should complete in < 10 s.
- **Per wave merge:** Full FE suite (`cd frontend && npm test -- --run`) + full BE suite (`pytest backend/tests/ -x`). Both must be green before merging the wave.
- **Phase gate:** Full suite green (FE + BE) AND `npx tsc --noEmit` (frontend type-check) AND `npm run build` (Next.js production build smoke) before `/gsd:verify-work`.

### Wave 0 Gaps

None — existing test infrastructure covers all phase requirements:
- `backend/tests/test_response_node.py` (existing, 365 lines) — extend for D-13.
- `frontend/__tests__/components/ChatApp.integration.test.tsx` (existing, 220 lines) — extend for D-14, reusing the established MSW SSE harness.
- `frontend/__tests__/components/SearchContextLine.test.tsx` (existing, 87 lines) OR new `MessageList.search_only.test.tsx` — for D-15 (planner discretion).
- `frontend/__tests__/hooks/useConversations.test.tsx` (existing, 46 lines) — wrap `renderHook` calls with `<ConversationsProvider>` per D-05.

No new test framework install. No new fixture files needed (`HAPPY_TRACE` and `HAPPY_PAYLOAD` from `frontend/__tests__/fixtures/sse.ts` cover Wave 1 SSE; `SAMPLE_CONVERSATIONS` from `agentState.ts` is the baseline for D-14 sidebar handler).

## Sources

### Primary (HIGH confidence)

- `frontend/package.json` — verified all dependency versions in-repo (Read).
- `backend/agent/nodes/response_node.py` (line numbers verified) — final_payload construction site at lines 232-241 (deny path) and 307-312 (happy path).
- `frontend/types/agent.types.ts` (line numbers verified) — FinalStatus union at line 39, FinalPayload.search_context at line 72.
- `frontend/components/chat/MessageList.tsx` (line numbers verified) — switch dispatch at lines 54-62.
- `frontend/components/chat/MarkdownAnswer.tsx` (line numbers verified) — SearchContextLine integration at lines 23-33.
- `frontend/components/chat/SearchContextLine.tsx` (line numbers verified) — empty-summary gate at lines 14-16, target=_blank rel=noopener noreferrer at lines 32-36.
- `frontend/hooks/useConversations.ts` (verified entire file — 44 lines) — current hook shape and behavior.
- `frontend/components/ChatApp.tsx` (verified entire file — 217 lines) — refresh trigger at line 70, useConversations call at line 24.
- `frontend/components/sidebar/ConversationSidebar.tsx` (verified entire file) — useConversations call at line 16.
- `frontend/components/dashboard/SurchargeHistoryChart.tsx` (verified entire file) — useConversations call at line 29.
- `frontend/__tests__/components/ChatApp.integration.test.tsx` (verified entire file — 220 lines) — Phase 6/7 baseline for D-14 extension.
- `frontend/__tests__/hooks/useConversations.test.tsx` (verified entire file — 46 lines) — three tests need provider wrapper.
- `frontend/__tests__/components/SearchContextLine.test.tsx` (verified entire file — 87 lines) — pattern reference for D-15 if planner picks the extend-this-file path.
- `frontend/__tests__/fixtures/sse.ts` (verified entire file) — `makeSseStream`, `HAPPY_TRACE`, `HAPPY_PAYLOAD`, `happyTurnEvents` reusable for D-14.
- `frontend/__tests__/mocks/handlers.ts` and `server.ts` — MSW server setup verified.
- `backend/tests/test_response_node.py` (verified entire file — 365 lines) — extension target for D-13. Includes pre-existing search_context tests (lines 121-179) — D-13 augments these with `final_payload`-level assertions.
- `.planning/phases/08-search-context-sidebar-polish/08-CONTEXT.md` — full decision lock from `/gsd:discuss-phase`.
- `.planning/v1.0-MILESTONE-AUDIT.md` — original gap descriptions for Issues 4 + 6.
- `.planning/REQUIREMENTS.md` — TOOL-05, UI-02, UI-06 traceability.
- `.planning/STATE.md` — Phase 5 + 6 + 7 decision log informing what's already shipped.

### Secondary (MEDIUM confidence)

- [React 19 createContext docs](https://react.dev/reference/react/createContext) — verified Context API shape and `<Context value={...}>` shorthand availability via WebSearch.
- [React 19 useContext docs](https://react.dev/reference/react/useContext) — verified consumer pattern and "throw outside provider" idiom.

### Tertiary (LOW confidence)

None — no LOW confidence findings in this research. All claims are verified against in-repo files (HIGH) or React's own documentation (HIGH-MEDIUM).

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all dependencies verified in `frontend/package.json`; zero new packages.
- Architecture: HIGH — Context provider pattern verified against React 19 official docs; existing repo files line-number-verified for every CONTEXT integration point.
- Pitfalls: HIGH — pitfalls 1, 3, 6 are derived directly from inspecting `ChatApp.tsx`'s structure and the deps array at line 71; pitfalls 2, 5 are from inspecting the test files; pitfall 4 is a known TypeScript gotcha.
- Code examples: HIGH — every snippet is either lifted verbatim from in-repo files (with line numbers) or constructed from the verified existing pattern.
- Test architecture: HIGH — every test file referenced exists at the cited path; the Vitest+MSW pattern is the verified Phase 6 / 7 baseline.

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (30 days — stable React 19 + Next 15 baseline; no fast-moving dependencies in scope)

---

*Phase: 08-search-context-sidebar-polish*
*Research complete: 2026-05-05*
