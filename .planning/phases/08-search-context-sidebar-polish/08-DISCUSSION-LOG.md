# Phase 8: Search Context Wiring + Sidebar Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 08-search-context-sidebar-polish
**Areas discussed:** Sidebar state-sharing approach, search_context payload shape, 'search_only' status branch rendering, Drift-prevention test surface

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Sidebar state-sharing approach | useConversations runs as 3 independent instances (ChatApp, ConversationSidebar, SurchargeHistoryChart). Audit recommends 'context provider'. | ✓ |
| search_context payload shape | response_node final_payload addition: always include vs conditional include. Phase 7 D-04 set the 'always required' precedent for message_id. | ✓ |
| 'search_only' status branch rendering | Today MessageList switch falls through default → MarkdownAnswer. Options: explicit case vs default fallthrough vs new NewsAnswer component. | ✓ |
| Drift-prevention test surface | What tests prevent regression? Audit-class lessons say Vitest+MSW round-trip is the alarm. | ✓ |

**User's choice:** All four areas selected.

---

## Sidebar share

| Option | Description | Selected |
|--------|-------------|----------|
| React Context provider (Recommended) | Create ConversationsProvider wrapping ChatApp; consumers call useConversationsContext(). Matches audit §7 recommendation. | ✓ |
| Lift to ChatApp + prop-drill | ChatApp owns the single instance; pass items/loading/refresh as props. | |
| Zustand global store | Replace hook with Zustand store; consumers select slices. Adds new dependency. | |
| Event-bus refresh | CustomEvent dispatched by ChatApp; sidebar listens and refetches. Each consumer still hits /api/conversations independently. | |

**User's choice:** React Context provider.
**Notes:** Aligns with audit §7 recommendation; matches single-source-of-truth pattern from Phase 7 D-01/D-02.

---

## Provider scope

| Option | Description | Selected |
|--------|-------------|----------|
| Inside ChatApp (top of return) (Recommended) | Provider lives in ChatApp.tsx wrapping the three-column layout. Smallest blast radius — all three consumers sit under ChatApp's tree. | ✓ |
| Next.js root layout / page | Provider lives in app/page.tsx or layout.tsx. Spreads wiring across more files; server components don't consume client context. | |
| New wrapper component above ChatApp | A small ChatAppShell wraps ChatApp + ConversationsProvider, exported from page.tsx. Adds a file for one-feature need. | |

**User's choice:** Inside ChatApp (top of return).

---

## Dashboard share

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — single source of truth (Recommended) | Dashboard uses the same provider instance. When ChatApp.refresh() fires, the surcharge history chart updates too. | ✓ |
| Keep dashboard independent | SurchargeHistoryChart keeps its own useConversations() instance. | |

**User's choice:** Yes — shared instance.

---

## Hook API

| Option | Description | Selected |
|--------|-------------|----------|
| Keep useConversations name; throw if called outside Provider (Recommended) | Same import path, same return shape. Throws clear error if a future component forgets the provider. | ✓ |
| Rename to useConversationsContext + keep useConversations as inner hook | Public/private split; requires renaming 3 import lines. | |
| Expose a separate refresh-only hook | useConversations() for read; useConversationsRefresh() for write. Overkill for a 3-consumer surface. | |

**User's choice:** Keep useConversations name; throw if called outside Provider.

---

## Refresh timing

| Option | Description | Selected |
|--------|-------------|----------|
| After every completed turn (Recommended) | ChatApp's existing useEffect at line 70 propagates via the shared instance. Approve/Deny resume also goes through `done`. | ✓ |
| Completed turn + explicit on-error refresh | Marginal benefit — backend persists checkpoint regardless of FE error status. | |
| Background polling every 30s | Polling on top of completed-turn refresh. No clear demo benefit. | |

**User's choice:** After every completed turn.

---

## SC payload

| Option | Description | Selected |
|--------|-------------|----------|
| Always include; null when absent (Recommended) | final_payload['search_context'] = state.get('search_context'). Always-present keys make tests simpler. Mirrors Phase 7 D-04 message_id precedent. | ✓ |
| Conditional include (only when populated) | Add the key only when state.search_context exists and is non-empty. Drift risk: FE consumers must handle both undefined and null. | |
| Always include, but normalize empty-summary to null | Frontend SearchContextLine already returns null on blank summary — redundant normalization. | |

**User's choice:** Always include; null when absent.

---

## FE typing

| Option | Description | Selected |
|--------|-------------|----------|
| Keep optional (search_context?: SearchContext \| null) (Recommended) | BE sends the field always, but FE keeps it optional for backward-compat. Less disruption than Phase 7's required-field cascade. | ✓ |
| Make required (search_context: SearchContext \| null) | TS compiler enforces every code path handles the field. Forces every test fixture update. | |

**User's choice:** Keep optional. Different semantics from message_id (mandatory identity vs genuinely optional content).

---

## search_only

| Option | Description | Selected |
|--------|-------------|----------|
| Add explicit case, render MarkdownAnswer (Recommended) | case 'search_only': return <MarkdownAnswer payload={payload} />. Explicit > implicit; matches Phase 4 D-12. | ✓ |
| Leave default fallthrough | Today 'search_only' silently routes to default → MarkdownAnswer which works. Less explicit. | |
| New NewsAnswer component | Dedicated component for news-only responses. One-line difference today; not justified yet. | |

**User's choice:** Add explicit case, render MarkdownAnswer.

---

## Trace sources

| Option | Description | Selected |
|--------|-------------|----------|
| Chat answer only (status quo) (Recommended) | SearchContextLine renders inside MarkdownAnswer with collapsible sources. Trace panel keeps showing search_agent step's tool_input/tool_output JSON. | ✓ |
| Both trace panel and chat answer | Add a sources-list affordance to the trace step row. More UX work than the audit calls for. | |

**User's choice:** Chat answer only — sources surface via SearchContextLine, trace panel unchanged.

---

## Test surface

| Option | Description | Selected |
|--------|-------------|----------|
| BE response_node final_payload test (Recommended) | Pytest asserts response_node returns search_context in final_payload when state has it, AND null when absent. | ✓ |
| FE sidebar-refresh integration test (Recommended) | Vitest+MSW round-trip in ChatApp.integration.test.tsx — completes a turn, asserts ConversationSidebar shows the new thread without reload. | ✓ |
| FE 'search_only' rendering test (Recommended) | Vitest test mounting MessageList with a search_only FinalPayload — asserts SearchContextLine renders with sources, no surcharge breakdown table. | ✓ |
| Playwright E2E for both flows | Heavier than Phase 6/7 chose; same bug class catchable at the integration layer. | |

**User's choice:** All three recommended tests; no Playwright.

---

## Done

**User's choice:** I'm ready for context.

## Claude's Discretion

- Wave / plan splitting (likely two plans: small BE+rendering wave, then provider migration wave; single-plan also defensible)
- Test file location for D-15 (extend SearchContextLine.test.tsx vs new MessageList.search_only.test.tsx)
- Provider component naming (`ConversationsProvider` confirmed)
- `.ts` → `.tsx` rename mechanics (TypeScript path aliases erase extension; safe)
- Whether to add a TS-level `never` exhaustiveness check in MessageList default branch
- Bangkok Metro phrasing review during execution (no expected user-facing copy in Phase 8)

## Deferred Ideas

- Trace panel sources affordance (chat answer is the surface)
- NewsAnswer dedicated component (one-line diff from MarkdownAnswer; v2)
- Background polling of /api/conversations (no demo benefit; v2)
- Playwright E2E (Vitest+MSW catches the same class faster)
- Zustand global state library (no precedent in repo; v2 if surface ever balloons)
- FinalPayload.search_context upgrade to required (different semantics from Phase 7 message_id)
- Tightening FinalStatus exhaustiveness via `never` check (future TS strictness pass)
- Refresh on error / on HITL approve / on resume (single done-path covers all)
