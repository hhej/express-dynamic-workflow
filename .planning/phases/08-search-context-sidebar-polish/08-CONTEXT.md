# Phase 8: Search Context Wiring + Sidebar Polish - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Make Tavily news queries surface typed sources via the existing `SearchContextLine` component, declare the `'search_only'` `FinalStatus` branch in the type system and dispatch it explicitly in `MessageList`, and make the conversation sidebar refresh after every completed turn by promoting `useConversations` to a single shared React Context instance across `ChatApp`, `ConversationSidebar`, and `SurchargeHistoryChart`. Closes audit Issues 4 and 6 (`v1.0-MILESTONE-AUDIT.md` §2.3). Restores Flow 4 (Tavily news_query) to full UX fidelity and flips UI-06 from degraded to satisfied.

**In scope (this phase):**
- Backend: `response_node` `final_payload` always carries `search_context` (`state.get("search_context")` — `null` when absent).
- Frontend types: `FinalStatus` union extended with `'search_only'`; `FinalPayload.search_context` stays declared optional.
- Frontend rendering: `MessageList` status switch gains an explicit `case 'search_only'` returning `MarkdownAnswer` (which already renders `SearchContextLine` when `payload.search_context.summary` is present).
- Frontend state: `useConversations` becomes a single Context-backed instance. New `ConversationsProvider` lives inside `ChatApp.tsx` and wraps the three-column layout; `useConversations` consumers (`ChatApp`, `ConversationSidebar`, `SurchargeHistoryChart`) read the same `items / loading / error / refresh / resume` from the shared instance. `useConversations()` throws when called outside the provider.
- Refresh trigger: existing `void conversations.refresh()` call in `ChatApp.tsx:70` (fires on `done`) propagates to all consumers via the shared instance — no new call sites.
- Drift-prevention tests: BE `response_node` `final_payload` test (search_context presence + null when absent); FE Vitest+MSW sidebar-refresh integration test; FE `'search_only'` rendering test.

**Explicitly out of scope (deferred to v2):**
- New SSE event type — Phase 8 extends the existing `answer` payload only (single-key addition).
- AgentState schema change — `state.search_context` already exists (Plan 05-04 D-11); Phase 8 only forwards it into `final_payload`.
- Trace panel UX upgrade for sources — Phase 8 surfaces sources only via `SearchContextLine` inside the chat answer; trace step rows stay JSON-only.
- Dedicated `NewsAnswer` component — `MarkdownAnswer` already renders the search-only case correctly; a 1-line dispatch difference doesn't justify a new file.
- Backwards-compat shim for code paths calling `useConversations` outside the provider — there are none (3 known consumers, all covered).
- Background polling of `/api/conversations` — no demo benefit; v2 if multi-tab sync is ever needed.
- Playwright E2E — same bug class is catchable at the Vitest+MSW integration layer with faster feedback (matches Phase 6 D-14 / Phase 7 D-09 lesson).
- Zustand or other global state lib — no existing precedent in the repo; Context provider is idiomatic React for this surface size.
- `FinalPayload.search_context` upgrade from optional to required — Phase 7 D-04 set the required-field precedent for `message_id` (mandatory identity); `search_context` is genuinely optional content (most turns don't have it), so the type stays optional. Different semantics, different choice.

</domain>

<decisions>
## Implementation Decisions

### Sidebar state-sharing (Issue 4 — `useConversations` runs as 3 independent instances)
- **D-01:** Convert `useConversations` to a React Context-backed shared instance. New `ConversationsProvider` component owns the single `useState`/`useEffect`/`useCallback` block currently in `useConversations.ts`. Public hook name stays `useConversations` (call sites unchanged). `useConversations()` throws a clear error when called outside the provider — idiomatic React, matches audit §7 recommendation. Closes audit Issue 4.
- **D-02:** Provider lives **inside** `ChatApp.tsx` (top of the rendered tree, wrapping the existing `<main>...</main>` three-column layout). Smallest blast radius — both `ConversationSidebar` (rendered directly under `<main>`) and `SurchargeHistoryChart` (rendered through `ChatColumn`'s dashboard tab) sit under `ChatApp`'s subtree. No `frontend/app/page.tsx` or `frontend/app/layout.tsx` changes; no new wrapper component above `ChatApp`.
- **D-03:** `SurchargeHistoryChart.tsx` consumes the **same** shared instance (single source of truth). When `ChatApp.refresh()` fires on a completed turn, the dashboard's surcharge history chart updates too. One fetch per refresh, three readers; eliminates a redundant `/api/conversations` call. Matches audit's single-source-of-truth lesson.
- **D-04:** `refresh()` fires **after every completed turn** — and only there. The single existing call site at [frontend/components/ChatApp.tsx:70](frontend/components/ChatApp.tsx#L70) (`void conversations.refresh()` inside the `chat.finalPayload` `useEffect`) is unchanged in location; the change is that it now propagates to all consumers via the shared provider instance. HITL approve/deny resume flows through the same `done` path so it's covered too. No on-error refresh, no background polling.
- **D-05:** Public hook contract is unchanged: `{ items, loading, error, refresh, resume }` — same return shape as today. The 3 call-site swaps (`ChatApp.tsx:24`, `ConversationSidebar.tsx:16`, `SurchargeHistoryChart.tsx:29`) keep their existing destructuring; only the underlying source changes from "own state per call" to "shared state from context." Tests in [frontend/__tests__/hooks/useConversations.test.tsx](frontend/__tests__/hooks/useConversations.test.tsx) get a thin `<ConversationsProvider>` wrapper around `renderHook` and otherwise stay as-is.
- **D-06:** File layout: provider component + hook live in `frontend/hooks/useConversations.tsx` (rename from `.ts` to `.tsx` because the provider returns JSX). Single file, two named exports (`ConversationsProvider`, `useConversations`). No separate `frontend/components/providers/` directory introduced for one feature.

### search_context payload shape (Issue 6 backend)
- **D-07:** `response_node` `final_payload` **always** includes `search_context`. Construction: `final_payload["search_context"] = state.get("search_context")` — `None` when state lacks it. Site: [backend/agent/nodes/response_node.py:307-312](backend/agent/nodes/response_node.py#L307-L312) (the dict literal building `final_payload`). Always-present keys make tests simpler, eliminate the FE `undefined` vs `null` ambiguity that is the audit's exact bug class (Issue 3 root cause), and mirror Phase 7 D-04's "single source of truth on the wire" pattern.
- **D-08:** No normalization of empty-summary search_context (passing through whatever is in state). `SearchContextLine` already returns `null` when `summary` is blank/whitespace ([frontend/components/chat/SearchContextLine.tsx:15-16](frontend/components/chat/SearchContextLine.tsx#L15-L16)); duplicating that gate upstream in `response_node` is redundant complexity.

### search_only status branch and rendering (Issue 6 frontend)
- **D-09:** Extend `FinalStatus` union to include `'search_only'`. Site: [frontend/types/agent.types.ts:39](frontend/types/agent.types.ts#L39). Backend already emits this status ([backend/agent/nodes/response_node.py:262, 279-286](backend/agent/nodes/response_node.py#L262)) — the FE type currently lies. Required type-system change for audit Issue 6 success criterion 2.
- **D-10:** `FinalPayload.search_context` stays declared as `SearchContext | null` (unchanged from today's [frontend/types/agent.types.ts:72](frontend/types/agent.types.ts#L72)). Type is already optional+nullable; no escalation to required like Phase 7 D-04 message_id. Different semantics: `message_id` is mandatory identity for feedback wiring; `search_context` is genuinely optional content (most turns don't trigger search). Type change is contained to the union extension only.
- **D-11:** `MessageList` switch gains an explicit `case 'search_only'` returning `<MarkdownAnswer payload={payload} />`. Site: [frontend/components/chat/MessageList.tsx:54-62](frontend/components/chat/MessageList.tsx#L54-L62). `MarkdownAnswer` already renders `SearchContextLine` above the prose when `payload.search_context.summary` is present ([frontend/components/chat/MarkdownAnswer.tsx:24-33](frontend/components/chat/MarkdownAnswer.tsx#L24-L33)) — no `MarkdownAnswer` changes needed. Explicit case > default fallthrough: matches Phase 4 D-12 "distinct visual treatments per `payload.status`" pattern; if a future status (`'partial_news'`, etc.) ever needs a different surface, the extension point is named.
- **D-12:** Trace panel rendering is unchanged. Sources are surfaced through the chat answer surface only (via `SearchContextLine`'s collapsible `<details>` block with `target="_blank" rel="noopener noreferrer"` source links). Trace step rows continue to show the `search_agent` step's `tool_input`/`tool_output` as JSON. Closes audit Issue 6 success criterion 1 ("clickable sources") via the chat answer, NOT the trace panel.

### Drift-prevention tests (audit lesson)
- **D-13:** **Backend test:** add a `response_node` test (extend [backend/tests/test_response_node.py](backend/tests/test_response_node.py)) asserting `final_payload['search_context']` is the exact `state['search_context']` dict when state has it, AND is `None` when state doesn't. Two assertions, single test function. Catches future regressions where someone forgets to forward the field (the same omission that created Issue 6).
- **D-14:** **Frontend sidebar-refresh integration test:** Vitest+MSW round-trip in `ChatApp.integration.test.tsx` (extend the existing Phase 6 / Phase 7 file). Mount `ChatApp` (which mounts `ConversationsProvider`); MSW handler for `GET /api/conversations` returns `[thread-A]` first call, `[thread-A, thread-B]` second call; MSW handler for `POST /api/chat` emits a complete fresh-turn SSE stream including `done`; assert that after the turn completes, `ConversationSidebar` displays both `thread-A` and `thread-B` without a page reload. Catches audit Issue 4 bug class permanently (any future regression that breaks the provider chain fails this test).
- **D-15:** **Frontend 'search_only' rendering test:** extend [frontend/__tests__/components/SearchContextLine.test.tsx](frontend/__tests__/components/SearchContextLine.test.tsx) OR add a new `frontend/__tests__/components/MessageList.search_only.test.tsx` (planner picks; `MessageList` is the surface that the `'search_only'` switch case lives in, so a `MessageList` test catches the dispatch + the rendering in one). Mount `MessageList` with a `[{ role: 'assistant', payload: { status: 'search_only', search_context: {...with sources...}, surcharge_result: null, ... } }]`; assert (a) `SearchContextLine` text "Market context:" is in the document, (b) the sources `<details>` toggle is in the document, (c) NO surcharge breakdown table is in the document. Closes audit Issue 6 frontend half.
- **D-16:** No Playwright E2E for Phase 8. Bug class is catchable at the Vitest+MSW integration layer (faster, deterministic, no flakiness against headless browsers). Reuses the same Phase 6 D-14 / Phase 7 decision.

### Folded Todos
None — `gsd-tools todo match-phase 8` returned 0 matches.

### Claude's Discretion
- **Wave / plan splitting.** Likely two plans: (Wave 1: backend response_node 1-line addition + BE test; FE types + MessageList switch case + 'search_only' rendering test — small, low-risk surface) (Wave 2: ConversationsProvider migration + 3 consumer swaps + sidebar-refresh integration test). A single-plan path is also defensible. Planner picks based on dependency analysis.
- **Test file location for D-15.** Extending `SearchContextLine.test.tsx` keeps related tests co-located but the test asserts MessageList behavior; new `MessageList.search_only.test.tsx` is more accurate but adds a file. Both fit.
- **Provider component naming.** `ConversationsProvider` is the obvious choice; `ConversationContextProvider` is more verbose without adding clarity. Planner confirms `ConversationsProvider` and moves on.
- **`useConversations.ts` → `useConversations.tsx` rename mechanics.** Git rename + content swap; planner verifies no `import '@/hooks/useConversations'` ESM-extension-sensitive consumers exist (TypeScript path aliases erase the extension at compile time, so this is safe).
- **Whether to add a separate `useConversationsRefresh()` hook** (write-only, returns the `refresh` callback). Rejected in discuss-phase as overkill for a 3-consumer surface; planner confirms and skips.
- **`refresh()` side-effect ergonomics.** Today the hook auto-fetches on mount via `useEffect`. After provider migration, the auto-fetch fires once when the provider mounts (same behavior as today's first consumer mount). No change.
- **Whether to add a TS-level exhaustiveness check** (`const _check: never = status;`) inside the `MessageList` status switch default branch. Future-proof for new statuses, but adds boilerplate; the explicit `case 'search_only'` (D-11) plus the union narrowing already give the same protection. Planner picks.
- **Bangkok Metro phrasing review.** No new user-facing copy is added in Phase 8 (sources are titles+URLs from Tavily, not project copy). Planner confirms no `central-region`-ish strings creep into provider error messages or test fixtures.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit (THE driver for this phase)
- `.planning/v1.0-MILESTONE-AUDIT.md` — §2.3 Issue 4 (sidebar not refreshed; `useConversations.ts` separate hook instances; UI-06); §2.3 Issue 6 (`response_node.py:297-302` omits `search_context` from `final_payload`; `agent.types.ts:39` `FinalStatus` missing `'search_only'`; SearchContextLine + status branch dead code; TOOL-05, UI-02). §3 Flow 4 (Tavily news query — degraded UX). §7 file paths at the centre of the gaps. §8 recommended next step.

### Phase inputs from earlier phases
- `.planning/phases/05-polish-observability-docs/05-CONTEXT.md` — Plan 05-04 locked decisions:
  - **D-11** `search_context` state field shape (query, summary, sources[], fetched_at) and the `Market context:` blockquote prefix prepended in response_node — Phase 8 honours both unchanged; only the `final_payload` forwarding is added.
  - Search agent + planner news intent + graph wiring + response_node Market context line — locked; Phase 8 doesn't touch.
  - **05-10 gap-3 fix:** `news_query` planner intent and `'search_only'` status branch — backend already emits this; Phase 8 declares it on the FE type and dispatches it explicitly.
- `.planning/phases/04-frontend-reasoning-trace/04-CONTEXT.md` — Phase 4 locked decisions:
  - **D-12** Distinct visual treatments per `payload.status` in MessageList. Phase 8 D-11 adds `'search_only'` as another treated status (renders `MarkdownAnswer` which already does the right thing).
  - **D-19** SSE consumer dispatches by event type — Phase 8 extends the existing `answer` event payload (single-key addition); no new event type.
- `.planning/phases/06-hitl-approval-ui-wiring/06-CONTEXT.md` — Phase 6 locked decisions:
  - **D-15.3** Vitest+MSW round-trip drift-prevention pattern in `ChatApp.integration.test.tsx`. Phase 8 D-14 extends this file for the sidebar-refresh test.
  - Pending-assistant placeholder slot (`pending-${Date.now()}`) — Phase 8 doesn't touch; placeholder is still stripped on `done` per Phase 6 D-06.
- `.planning/phases/07-feedback-contract-alignment/07-CONTEXT.md` — Phase 7 locked decisions:
  - **D-04** message_id REQUIRED on FinalPayload — sets the precedent that the FE type system is the chokepoint for cross-phase contracts. Phase 8 intentionally does NOT escalate `search_context` to required (different semantics; D-10).
  - **D-08** `isLast`/`message_id` gating in MessageList for FeedbackButtons — Phase 8 doesn't touch this gate; sidebar refresh and search_only rendering are independent concerns.
  - Phase 7 explicitly named Phase 8 as owner of audit Issues 4 + 6 — confirmed.

### Implementation source files (Phase 8 modifies)
- [backend/agent/nodes/response_node.py:307-312](backend/agent/nodes/response_node.py#L307-L312) — `final_payload` dict; add `"search_context": state.get("search_context")` per D-07.
- [frontend/types/agent.types.ts:39](frontend/types/agent.types.ts#L39) — `FinalStatus` union; add `'search_only'` per D-09.
- [frontend/types/agent.types.ts:72](frontend/types/agent.types.ts#L72) — `FinalPayload.search_context?: SearchContext | null` already declared correctly per D-10; no change.
- [frontend/components/chat/MessageList.tsx:54-62](frontend/components/chat/MessageList.tsx#L54-L62) — switch in `renderAssistant`; add explicit `case 'search_only': return <MarkdownAnswer payload={payload} />;` per D-11.
- [frontend/hooks/useConversations.ts](frontend/hooks/useConversations.ts) — rename to `.tsx`; refactor into `ConversationsProvider` + `useConversations` hook backed by `React.createContext`. `useConversations()` throws if called outside the provider per D-01.
- [frontend/components/ChatApp.tsx:24](frontend/components/ChatApp.tsx#L24) — drop `const conversations = useConversations()` from the body and instead wrap the returned `<main>...</main>` with `<ConversationsProvider>...</ConversationsProvider>` per D-02. Move the existing `void conversations.refresh()` call (D-04) into the provider-aware code path — likely via a thin internal component or by reading `useConversations()` after wrapping. Planner picks the cleanest split.
- [frontend/components/sidebar/ConversationSidebar.tsx:16](frontend/components/sidebar/ConversationSidebar.tsx#L16) — call site stays `const { items, loading } = useConversations()`; only the underlying source changes. Per D-05.
- [frontend/components/dashboard/SurchargeHistoryChart.tsx:29](frontend/components/dashboard/SurchargeHistoryChart.tsx#L29) — call site stays `const { items, loading: convLoading, error: convError } = useConversations()`; consumes the shared instance per D-03.
- [frontend/components/chat/MarkdownAnswer.tsx:19-52](frontend/components/chat/MarkdownAnswer.tsx#L19-L52) — already reads `payload.search_context` and renders SearchContextLine; reference only, no change.
- [frontend/components/chat/SearchContextLine.tsx](frontend/components/chat/SearchContextLine.tsx) — existing component handles summary + sources rendering with `target="_blank" rel="noopener noreferrer"`; reference only, no change.

### Test files
- [backend/tests/test_response_node.py](backend/tests/test_response_node.py) — extend with `final_payload['search_context']` presence + null assertions per D-13.
- [frontend/__tests__/components/ChatApp.integration.test.tsx](frontend/__tests__/components/ChatApp.integration.test.tsx) — extend with the sidebar-refresh integration test per D-14. Reuses the existing Phase 6 / Phase 7 MSW SSE harness.
- [frontend/__tests__/components/SearchContextLine.test.tsx](frontend/__tests__/components/SearchContextLine.test.tsx) OR a new `frontend/__tests__/components/MessageList.search_only.test.tsx` — `'search_only'` rendering test per D-15. Planner picks file location.
- [frontend/__tests__/hooks/useConversations.test.tsx](frontend/__tests__/hooks/useConversations.test.tsx) — wrap existing `renderHook` calls in `<ConversationsProvider>` per D-05; otherwise unchanged.

### Requirements & project framing
- `.planning/REQUIREMENTS.md` — Phase 8 scope: TOOL-05 (rendering completeness — sources surface in FE), UI-02 (rendering completeness — `'search_only'` status branch reachable), UI-06 (sidebar refresh after completed turn). All three already mark Complete in REQUIREMENTS.md (the audit downgraded them via cross-phase integration check); Phase 8 restores them to fully-satisfied.
- `.planning/PROJECT.md` — local-reproducibility constraint (no new external deps for the provider migration; React Context is built-in), Bangkok Metro phrasing (no user-facing copy in Phase 8 changes — sources are Tavily-supplied URLs/titles), 35% Agent Architecture rubric (visible reasoning + observable sources is part of the demo).
- `.planning/ROADMAP.md` §Phase 8 — three success criteria: (1) `response_node` emits `search_context` in `final_payload` AND FE `'search_only'` branch renders SearchContextLine with clickable sources; (2) `agent.types.ts` `FinalStatus` includes `'search_only'` and downstream switches handle it; (3) sidebar updates immediately after a completed turn without a page reload.

### Coding conventions
- `.planning/codebase/CONVENTIONS.md` §Python — PEP 8, Black, Google-style docstrings, `from __future__ import annotations`. §TypeScript — PascalCase.tsx components, useX.ts/.tsx hooks, camelCase.ts utilities, `*.types.ts`, `@/` path aliases, JSDoc on public APIs. ConversationsProvider follows PascalCase.tsx; the file rename `useConversations.ts` → `.tsx` follows convention because it now returns JSX.
- `.planning/codebase/STRUCTURE.md` §Frontend — `frontend/components/{chat,trace,sidebar,dashboard}/` layout. Phase 8 stays inside this; the provider lives in `frontend/hooks/useConversations.tsx` per D-06 (no new directory introduced for one feature).
- `.planning/codebase/TESTING.md` — Vitest + MSW patterns established in Phase 4 (Plan 04-01) and reused in Phase 6 (Plan 06-03 ChatApp.integration.test.tsx) and Phase 7 (Plan 07-02). Phase 8 reuses verbatim.

### Quick task references
- `.planning/quick/260503-rs8/`, `.planning/quick/260503-s2h/` — Langfuse trace name + run_name constants. Phase 8 doesn't touch observability wiring; reference only for context that the existing search_agent step is fully traced (Plan 05-02 OBS-01).

### Backlog
- `.planning/ROADMAP.md` §Backlog 999.2 — "Bangkok Metro" phrasing convention. Phase 8 adds no scope-dependent user-facing copy (sources are Tavily titles/URLs; provider error message is generic React idiom). Flag for review during execution.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/components/chat/SearchContextLine.tsx` — fully built; renders typed sources with `target="_blank" rel="noopener noreferrer"` and a collapsible `<details>` block. No changes in Phase 8.
- `frontend/components/chat/MarkdownAnswer.tsx` — already calls `<SearchContextLine context={sc} />` when `payload.search_context.summary` is non-blank. The wire is built end-to-end on the FE; only the BE `final_payload` forwarding is missing today.
- `frontend/hooks/useConversations.ts` — current `useState`/`useEffect`/`useCallback` block is correct in shape; provider migration just lifts the body into a single `ConversationsProvider` and wraps existing call sites.
- `frontend/components/ChatApp.tsx:70` — single existing `void conversations.refresh()` call site on `done`. Provider migration makes this propagate to all consumers automatically.
- `frontend/components/sidebar/ConversationSidebar.tsx`, `frontend/components/dashboard/SurchargeHistoryChart.tsx` — both already destructure `{ items, loading }` (and `error` in the dashboard case) — call sites unchanged after D-05.
- `frontend/__tests__/components/ChatApp.integration.test.tsx` — Phase 6 / 7 MSW SSE harness; Phase 8 extends with sidebar-refresh assertions. The `installPauseThenResumeHandler`-style call-counter pattern from Plan 06-03 is the reference for the two-call `/api/conversations` mock.
- `backend/tests/test_response_node.py` — existing test fixtures for `final_payload` shape; Phase 8 adds two assertions for `search_context` presence + null.

### Established Patterns
- **Single source of truth on the wire** (audit's lesson, repeated Phase 7 D-01/D-02) — Phase 8 D-07 always-include `search_context` in `final_payload` follows this; FE never reconstructs.
- **Distinct visual treatments per `payload.status`** (Phase 4 D-12) — Phase 8 D-11 adds `'search_only'` to the dispatched cases.
- **React Context for cross-component shared state** — new pattern for this repo; established here for Phase 8 D-01 / D-02 / D-03; future phases can follow if cross-tree state-sharing arises again.
- **Vitest+MSW round-trip integration tests for cross-phase contracts** — Phase 6 D-15.3 / Phase 7 D-09. Phase 8 D-14 extends `ChatApp.integration.test.tsx`.
- **Optional + nullable fields with explicit null-when-absent** (Plan 05-04 search_context, Plan 05-06 FinalPayload | null) — Phase 8 D-07 / D-10 keep this style.
- **Bangkok Metro phrasing** (resolved backlog 999.2) — Phase 8 adds no scope-dependent copy; safe.

### Integration Points
- `backend/agent/nodes/response_node.py` — single-line `final_payload` dict augmentation (D-07). The graph contract (state.search_context shape, status='search_only' emission, Market context blockquote prefix) is unchanged.
- `frontend/types/agent.types.ts` — single union extension (D-09). FinalPayload shape per D-10 unchanged.
- `frontend/components/chat/MessageList.tsx` — single switch case addition (D-11). Default fallthrough behavior preserved.
- `frontend/hooks/useConversations.tsx` (renamed) — provider + hook in one file. Public API unchanged.
- `frontend/components/ChatApp.tsx` — wrap return JSX with `<ConversationsProvider>`; existing internal `useConversations()` consumer can stay as-is (it'll resolve to the same provider it just rendered) OR move into a small inner component for cleanliness — planner picks.
- `frontend/components/sidebar/ConversationSidebar.tsx`, `frontend/components/dashboard/SurchargeHistoryChart.tsx` — call sites unchanged in shape (D-05).
- `frontend/__tests__/components/ChatApp.integration.test.tsx` — extension with sidebar-refresh test (D-14). Reuses MSW server setup.
- `backend/tests/test_response_node.py` — extension with search_context assertions (D-13).
- `frontend/__tests__/components/SearchContextLine.test.tsx` OR new `MessageList.search_only.test.tsx` — D-15 search_only rendering test.

</code_context>

<specifics>
## Specific Ideas

- **The audit's lesson is wider than this phase.** Issues 4 and 6 share the same root cause as Issues 1, 2, 3, 5: cross-phase wiring drift introduced after each individual phase passed verification. Phase 8 D-14 sidebar-refresh integration test is the alarm if the provider chain ever regresses; D-15 search_only rendering test is the alarm if the FinalStatus union or MessageList dispatch drifts.
- **Provider migration is small but high-leverage.** Three consumers, single shared instance, one `useEffect` mount per page load instead of three. Reduces `/api/conversations` calls from 3-per-page to 1-per-page as a free byproduct. The Dashboard tab now sees fresh history when chat completes — a UX upgrade that wasn't in the audit but falls out for free.
- **Phase 8 is the last gap closure.** With Phase 8 done, all 6 audit-flagged integration issues are resolved (3 critical via Phase 6, 1 critical via Phase 7, 2 minor via Phase 8). Then the milestone is one re-audit + Nyquist gap-fills + the remaining HUMAN deliverables (demo.mp4, 5 PNG screenshots, langfuse-feedback-score.png, v1.0 tag) away from `passed`.
- **`search_context` is a different precedent class from `message_id`.** Phase 7 made `message_id` REQUIRED on FinalPayload because identity must always exist for feedback. Phase 8 keeps `search_context` OPTIONAL because content is genuinely absent on most turns (only news_query and out_of_scope intents trigger search). The distinction is real, not a regression.
- **No SSE event contract change.** Phase 8 extends the existing `answer` event payload (single key addition); the SSE event union (`meta|trace|answer|error|done|approval_required`) stays stable. Same precedent as Phase 7 D-03.
- **Test count delta.** Phase 8 adds: 1 BE response_node test (D-13) + 1 FE Vitest+MSW integration test in ChatApp.integration (D-14) + 1 FE rendering test (D-15). Net delta: +3 tests. None subtracted.
- **Trace panel sources affordance is intentionally deferred.** A trace step's `tool_output` for `search_agent` already includes the sources JSON; it's just rendered as a JSON blob, not as a clickable list. Surfacing them visually in the trace panel is a UX polish concern outside the gap-closure scope.

</specifics>

<deferred>
## Deferred Ideas

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

### Reviewed Todos (not folded)
None — `gsd-tools todo match-phase 8` returned 0 matches.

</deferred>

---

*Phase: 08-search-context-sidebar-polish*
*Context gathered: 2026-05-04*
