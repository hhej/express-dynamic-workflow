# Phase 4: Frontend & Reasoning Trace - Research

**Researched:** 2026-04-26
**Domain:** Next.js 15 / React 19 / Tailwind CSS v4 / Recharts / SSE-streamed chat UI
**Confidence:** HIGH (stack and patterns verified against npm registry and official docs; one MEDIUM caveat on Recharts × React 19.2.x rendering)

## Summary

Phase 4 builds a Next.js 15 + React 19 + Tailwind v4 frontend that consumes the existing FastAPI SSE backend as a chat product with an always-visible reasoning trace panel and a Recharts dashboard. The frontend directory is empty (`frontend/.gitkeep` only) — this phase establishes all TypeScript conventions, scaffolding, components, hooks, and tests from scratch. Backend is fully done (Phase 3, 103 tests passing) and exposes the four endpoints the frontend needs, with a typed SSE envelope (`meta | trace | answer | error | done`) the frontend dispatches on.

CONTEXT.md (D-01..D-20) locks the high-level decisions: three-column desktop layout, always-on reasoning trace (the explicit grading lever per Core Value), `Chat | Dashboard` tab inside the center column, hand-rolled `fetch` + `ReadableStream` SSE consumer, `react-markdown` + `remark-gfm` for the locked 4-row markdown table, Recharts for both dashboard charts, and a UI-only feedback button stub (the wire-up moves to Phase 5).

**Primary recommendation:** Scaffold with `npx create-next-app@latest frontend --ts --tailwind --eslint --app --import-alias '@/*' --no-src --no-turbopack --use-npm`, pin to Next.js 15.5.x (the latest 15.x is `15.5.15` as of 2026-04-26 — CONTEXT.md locks the major to 15, not 16), add the React 19 `react-is` `overrides` block to package.json before installing Recharts 3.8.x, and consume SSE with a hand-rolled `parseSseStream(reader, onEvent)` helper backing a `useChatStream` reducer. Mirror `backend/api/models.py` field-for-field in `frontend/types/api.types.ts` plus a separate `agent.types.ts` for the trace entry shape (12 fields, sourced from `backend/agent/nodes/*.py`).

## Project Constraints (from CLAUDE.md)

CLAUDE.md repeats the locked tech stack — the planner must respect every line below:

- **Frameworks (locked):** Next.js 15, React 19, Tailwind CSS, Recharts. Do not introduce alternative frameworks (Remix, Vite-only React, Chart.js, D3 directly, etc.).
- **TypeScript file naming:** `PascalCase.tsx` for components, `use<Name>.ts` for hooks, `camelCase.ts` for utilities, `*.types.ts` for type files (CLAUDE.md → `## Conventions → TypeScript`).
- **Path aliases:** `@/` prefix for absolute imports (`@/components`, `@/lib`, `@/types`).
- **Variable/function naming:** `camelCase` for variables, `PascalCase` for types/interfaces/components, `use<PascalCase>()` for hooks.
- **Styling:** Tailwind CSS — no CSS-in-JS, no styled-components.
- **No secrets in code:** `.env` never committed; `.env.example` carries placeholders. `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` belongs in `.env.example`.
- **Git practice:** Descriptive commit messages, feature branches; IT Lead holds majority of commits (graded at 20%).
- **Configuration:** Loaded from environment. Frontend reads `NEXT_PUBLIC_*` vars at build time (per Next.js convention).
- **GSD workflow enforcement:** All file edits must originate from a GSD command (which this RESEARCH satisfies as the lead-in to `/gsd:plan-phase`).

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Layout & navigation**
- **D-01:** Single-page Next.js app with a three-column layout — conversation sidebar (left) | chat + breakdown (center) | reasoning trace panel (right). One `/` route is the entire product.
- **D-02:** Conversation history sidebar (UI-06) is an always-visible left rail on desktop. Active thread highlighted; click resumes via `GET /api/conversations/:id` + thread_id reuse on next `POST /api/chat`.
- **D-03:** Reasoning trace panel (UI-02) is an always-visible right rail on desktop. Visible reasoning is the explicit grading lever (Phase 3 D-17 / PROJECT.md Core Value), so always-on maximizes the rubric.
- **D-04:** Dashboard (UI-04) lives behind a `Chat | Dashboard` top-tab toggle inside the center column. No separate `/dashboard` route — sidebar and trace panel stay in place when toggling.
- **D-05:** Mobile breakpoint (<768px) collapses to chat-only with a hamburger drawer for the sidebar (left) and a "Show reasoning" drawer for the trace panel (right). Dashboard tab still available in the top toggle.

**Reasoning trace panel (UI-02)**
- **D-06:** Trace entries append live as `trace`-typed SSE events arrive. Each new step renders immediately with a `running` state; the next event resolves it to `ok | warn | error` (Phase 2 D-12 trace schema). No batching — the live-thinking effect is the agentic differentiator.
- **D-07:** Each step shows headline only by default — agent name + one-line summary + status badge — collapsed. Click to expand tool inputs, tool outputs, reasoning prose, and `fetched_at` (Phase 3 D-13). Scannable list, inspectable on demand.
- **D-08:** Trace panel shows the currently-streaming or last-completed turn only. Clicking an older message in chat does NOT swap the trace — past-turn trace is **deferred** (would require backend D-21 extension to persist per-turn `reasoning_trace`).
- **D-09:** Empty state (before first message) shows a short explainer plus 2–3 clickable example prompts (e.g., *"Surcharge for 15kg Bounce, Bangkok → Nonthaburi"*, *"What about Retail Fast?"*). Onboarding + demo seed.

**Chat + surcharge breakdown rendering (UI-01, UI-03)**
- **D-10:** Render `answer.payload.markdown` (Phase 3 D-10 / D-11) verbatim via `react-markdown` + `remark-gfm` for table support. Backend remains the source of truth for prose and the 4-row breakdown structure; FE doesn't reconstruct the table from `surcharge_result`.
- **D-11:** When `answer.payload.capped === true`, render a Tailwind yellow-50 callout banner (warning icon + "Cap/floor applied — review recommended") **above** the markdown breakdown. Either strip the leading `> ⚠ Cap/floor applied — review recommended` line from the markdown before passing it to react-markdown, or override the `blockquote` component when capped is true. Planner picks the cleaner of the two.
- **D-12:** Distinct visual treatments per `answer.payload.status`:
  - `ok` → normal markdown render (prose + breakdown table)
  - `clarify` → blue info card containing the clarification question; no breakdown table
  - `partial` → orange card containing whatever data was gathered + "limited result" label; show breakdown if `surcharge_result` is non-null, otherwise just the prose
- **D-13:** Surcharge breakdown is the markdown table from D-10. Frontend does NOT separately render `answer.payload.surcharge_result` as JSON in the chat surface; that structured object is reserved for **Dashboard** consumption (D-15) where typed access matters.

**Conversation sidebar (UI-06)**
- **D-14:** Sidebar lists threads from `GET /api/conversations` (Phase 3 D-21): `{thread_id, last_updated, first_message_preview}`. Clicking a thread loads `GET /api/conversations/:id`, replays messages into the chat surface, and persists `thread_id` to localStorage so the next `POST /api/chat` continues that thread (Phase 3 D-19). "New conversation" button at top clears thread_id; backend assigns a fresh UUID via `meta` event.

**Dashboard (UI-04)**
- **D-15:** Dashboard ships **two charts** in Phase 4:
  1. **Fuel price line chart** — `GET /api/fuel-prices?days=N` (Phase 3 D-20). Range toggle: `7d | 30d | 90d`, default `30d`.
  2. **Surcharge history bar/line chart** — derived **client-side** from `GET /api/conversations` + per-thread `GET /api/conversations/:id`. Walk the last ~20 threads, extract `final_payload.surcharge_result` (when present), plot total/surcharge_pct over `last_updated`. NO new backend endpoint in Phase 4.
- **D-16:** Surcharge breakdown by shipping type (bar) and zone heat-map were considered and **rejected** from Phase 4 charts to keep dashboard scope tight. May surface as v2.

**Feedback UI (UI-05) — stub-only in Phase 4**
- **D-17:** UI-05 thumbs up/down buttons render on each assistant message with **local-only** state. Click captures `{thread_id, message_id, score, reason?}` to console + `localStorage` (debug aid) and shows a "voted" visual state. NO `POST /api/feedback` call — API-05 is Phase 5 (alongside Langfuse Score API). Phase 5 swaps the local handler to the real API call without other UI changes.
- **D-18:** REQUIREMENTS.md UI-05 traceability stays mapped to Phase 4 (the buttons ship in Phase 4); Phase 5 owns the wire-up. Phase 4 verification accepts the stub as UI-05 complete.

**SSE consumption**
- **D-19:** Native `fetch()` + `ReadableStream` reader to consume `POST /api/chat` SSE (EventSource is GET-only). The reader parses `data: {...}\n\n` frames and dispatches by `payload.type`:
  - `meta` → store `thread_id` to localStorage, render in sidebar as the active thread
  - `trace` → append to live trace panel (D-06)
  - `answer` → render in chat surface with D-10/D-11/D-12 treatments
  - `error` → toast + render error card; trace panel preserves what arrived before the error
  - `done` → close the reader; flip chat input back to enabled
- **D-20:** `thread_id` lifecycle: read from `localStorage` on app boot; sent on `POST /api/chat` body when present, omitted on "New conversation". Server's first `meta` event is the authoritative source — overwrite localStorage with whatever the server returns. If a stored thread_id is unknown to the backend, the server emits a fresh UUID in `meta` and the client follows.

### Claude's Discretion

The CONTEXT.md "Claude's Discretion" block grants the planner freedom on:
- **SSE client implementation:** hand-rolled `fetch` + `ReadableStream` (D-19) vs `@microsoft/fetch-event-source`. **Recommendation: hand-rolled** — see "Don't Hand-Roll" caveat below; @microsoft/fetch-event-source is feature-rich but last published 2021-04 and not actively maintained.
- **State management library:** React state + custom hooks (`useChatStream`, `useConversations`, `useFuelPrices`) vs TanStack Query vs Zustand. **Recommendation: native React** — `useReducer` for the streaming chat (event-sourced state matches the SSE event types), simple `useEffect` + `useState` for the two GETs. Surface is too small to justify TanStack Query's footprint and the demo doesn't need cache invalidation; revisit only if `useFuelPrices` and `useConversations` re-fetch flicker becomes an issue.
- **Markdown lib choice:** `react-markdown` + `remark-gfm` vs smaller renderer. **Recommendation: keep react-markdown** — the locked D-11 4-row table needs GFM and the prose is LLM-generated (length and shape vary). Don't trade away resilience for ~30KB.
- **Component file split:** feature folders (`components/chat/`, `components/trace/`, `components/dashboard/`, `components/sidebar/`) vs flat `components/`. **Recommendation: feature folders** — `code_context` in CONTEXT.md already names paths under feature folders, and the integration points (`MessageList`, `MarkdownAnswer`, `FeedbackButtons`, `TracePanel`, `TraceStep`, `ConversationSidebar`, `FuelPriceChart`, `SurchargeHistoryChart`) cluster naturally.
- **TypeScript types:** hand-write vs OpenAPI-generated. **Recommendation: hand-write** — surface is 4 endpoints + 5 SSE event payloads + the trace entry. OpenAPI generation pays off above ~10 endpoints (Phase 5+).
- **Tailwind theme tokens:** colors/spacing/font scale beyond the locked `yellow-50` callout (D-11).
- **Project scaffold mechanics:** `create-next-app` (default) vs hand-built. **Recommendation: `create-next-app`** with the flag set documented below.
- **Currency formatting helper** (`frontend/lib/formatters.ts`).
- **Loading skeletons** for streaming chat input, dashboard charts (no data yet), sidebar (empty list).
- **Error boundaries** around the trace panel and dashboard charts.
- **Accessibility:** keyboard nav for trace expand/collapse, focus management for mobile drawers, ARIA labels on chart toggles. Hit "reasonable a11y" without a full audit.
- **Debug affordance:** "Show JSON" debug toggle under the breakdown table for `surcharge_result` inspection.

### Deferred Ideas (OUT OF SCOPE)

- **Past-turn trace inspection** (D-08) — backend `GET /api/conversations/:id` doesn't persist per-turn trace; Phase 5 candidate alongside Langfuse OBS-01..03.
- **Backend `/api/surcharge-history` endpoint** — D-15.2 derives client-side; promote only if dev performance suffers.
- **POST /api/feedback wire-up** — UI-05 stub buttons ship in Phase 4; API-05 + Langfuse Score API in Phase 5.
- **Surcharge by shipping type chart** and **zone heat-map** — rejected from Phase 4 (D-16); v2 candidates.
- **Token-level streaming** for the final markdown — Phase 3 D-17 locked node-completion granularity; out of scope.
- **OpenAPI-generated TS types** — hand-written for v1.
- **Authentication / multi-user** — out of scope (PROJECT.md).
- **Mobile-native polish beyond responsive breakpoints.**
- **Theme toggle (light/dark)** — Phase 5+ stretch.
- **Internationalization** — single-language English for the demo.
- **Conversation deletion / archive** — sidebar is read-only.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **UI-01** | Chat interface with SSE streaming display | Hand-rolled `fetch` + `ReadableStream` consumer pattern (Pattern 2 below); `useReducer` event-sourced state pattern (Pattern 5); `react-markdown` + `remark-gfm` for assistant messages (Pattern 4); typed SSE envelope mirrors `backend/api/sse.py` (`{type, payload}`) and `_NODE_NAMES` filter from `backend/api/routes/chat.py`. |
| **UI-02** | Reasoning trace panel — agent steps, tool calls, decisions | Trace entry shape (12 fields) verified from `backend/agent/nodes/*.py` — see "Trace Entry Schema" sidebar. Live append via SSE `trace` events (Pattern 6). Headline + collapsible detail (D-07) implementation pattern in Pattern 7. |
| **UI-03** | Surcharge breakdown table | Backend already renders the locked 4-row table inside `final_payload.markdown` (Phase 3 D-11, verified in `backend/agent/nodes/response_node.py` `_render_table`). Frontend's only job is to pass markdown through `react-markdown` + `remark-gfm` (no client-side table reconstruction per D-13). |
| **UI-04** | Dashboard with fuel-price + surcharge-history charts (Recharts) | Recharts 3.8.1 + `<LineChart>` + `<BarChart>` (verified versions Pattern 8); `<ResponsiveContainer>` for sizing. React 19 compatibility caveat — see Pitfall 3. Surcharge-history derivation walks `GET /api/conversations` then per-thread `GET /api/conversations/:id` and reads `surcharge_result` (verified shape in `backend/api/routes/conversations.py:112-119`). |
| **UI-05** | Feedback buttons (thumbs up/down) — UI stub only in Phase 4 | Local-only state per D-17; localStorage helper pattern (Pattern 9). API wiring is Phase 5. |
| **UI-06** | Conversation history sidebar | `GET /api/conversations` returns `[{thread_id, last_updated, first_message_preview}]` (verified shape in `backend/api/models.py:36-42` `ConversationSummary`). Sidebar resume flow uses `GET /api/conversations/:id` then sets `thread_id` in localStorage so the next `POST /api/chat` continues the thread (Pattern 10). |

## Standard Stack

### Core (verified versions, npm registry 2026-04-26)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `next` | `^15.5.15` (latest 15.x) | Next.js framework, App Router | Locked by PROJECT.md and CONTEXT.md to "Next.js 15"; do NOT auto-bump to 16.x without user approval (next@latest is `16.2.4` as of 2026-04-26). |
| `react` | `^19.2.5` | React (canary used internally by App Router; declare in `package.json` for tooling per official docs). | Locked by PROJECT.md. |
| `react-dom` | `^19.2.5` | DOM renderer | Locked by PROJECT.md. Pinned to same major as `react`. |
| `typescript` | `^5.7.x` (current `6.0.3` is unreleased major) | TS compiler. CLAUDE.md and STACK.md require TS for the frontend. | Industry default; ships with `create-next-app`. |
| `tailwindcss` | `^4.2.4` | Utility-first CSS | Locked by PROJECT.md. Tailwind v4 requires `@tailwindcss/postcss` plugin (not the v3 PostCSS plugin). |
| `@tailwindcss/postcss` | `^4.2.4` | PostCSS plugin (v4 setup) | Required wiring for Next.js → Tailwind v4. |
| `recharts` | `^3.8.1` | Chart library | Locked by PROJECT.md. peerDependencies include `react ^19.0.0` (verified via `npm view recharts peerDependencies`). |

### Supporting (verified versions, 2026-04-26)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `react-markdown` | `^10.1.0` | Markdown → React components | Render `final_payload.markdown` from backend (D-10). |
| `remark-gfm` | `^4.0.1` | GFM tables, strikethrough, tasklists | Required for the locked 4-row breakdown table to render. |
| `clsx` | `^2.1.1` | Conditional className join | Tiny (~500 bytes), useful for the tab toggle, capped banner toggle, status cards. Optional. |

### Dev / Test (verified versions, 2026-04-26)

| Library | Version | Purpose |
|---------|---------|---------|
| `eslint` | `^9.x` (Next.js 15.5+ supports ESLint 9) | Linting |
| `eslint-config-next` | `^15.5.15` (or matching `next` version) | Next.js + React preset |
| `prettier` | `^3.x` | Formatter |
| `vitest` | `^4.1.5` | Test runner — faster than Jest, Vite-native, JSDOM env |
| `@vitejs/plugin-react` | `^6.0.1` | Vitest + React |
| `@testing-library/react` | `^16.3.2` | User-centric component testing |
| `@testing-library/user-event` | `^14.x` | Simulated user interactions |
| `@testing-library/jest-dom` | `^6.x` | Custom matchers (`toBeInTheDocument`, etc.) |
| `jsdom` | `^29.x` | Browser env for Vitest |
| `msw` | `^2.13.6` | Mock Service Worker — intercept SSE + GET in unit/integration tests |
| `@playwright/test` | `^1.59.1` | E2E (smoke test for the full chat flow) — optional but recommended for the verifier gate |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled SSE consumer | `@microsoft/fetch-event-source` (2.0.1) | Battle-tested (2M weekly downloads, retry + visibility-API support), but **last published 2021-04** — effectively unmaintained. The hand-rolled version is ~40 lines of code (Pattern 2) and avoids a dependency on a stale package. |
| Native React state + hooks | TanStack Query (`@tanstack/react-query` 5.100.5) | TanStack Query is excellent for non-streaming GETs (caching, background refetch, optimistic updates). For 4 endpoints and a demo timeline, the bundle cost and learning surface aren't justified. **Defer to v2.** |
| Recharts | Visx, Tremor, Chart.js, ECharts | PROJECT.md locks Recharts. Don't substitute. |
| `react-markdown` + `remark-gfm` | `marked` + DOMPurify | `react-markdown` is the React-native choice and integrates cleanly with custom component overrides (needed for D-11 capped banner). |
| Vitest | Jest | Vitest starts faster, ships TypeScript out of the box, and matches the modern toolchain. Either is fine but Vitest is the lower-friction default for a Next.js 15 + TS project. |
| ESLint | Biome | Biome is faster but `eslint-config-next` is the canonical Next.js linting story. Stay with ESLint. |

**Installation (recommended order):**

```bash
# 1. Scaffold (run from repo root). Note: --no-turbopack keeps webpack as the
#    bundler — Turbopack is the new default but Recharts + React 19 + Turbopack
#    has had transient render issues; webpack is the safer baseline for now.
#    Re-evaluate Turbopack at Phase 5.
cd frontend && npx create-next-app@latest . \
  --ts --tailwind --eslint --app --import-alias '@/*' \
  --no-src --no-turbopack --use-npm

# 2. Pin Next.js 15.5.x explicitly (create-next-app@latest installs Next 16
#    by default — CONTEXT.md locks the major to 15).
npm install next@^15.5.15 eslint-config-next@^15.5.15

# 3. Add the React 19 react-is override BEFORE installing Recharts
#    (see Pitfall 3). Edit package.json to include:
#      "overrides": { "react-is": "^19.2.5" }
# Then:
npm install recharts@^3.8.1 react-markdown@^10.1.0 remark-gfm@^4.0.1 clsx@^2.1.1

# 4. Dev/test tooling
npm install -D vitest@^4.1.5 @vitejs/plugin-react@^6.0.1 \
  @testing-library/react@^16.3.2 @testing-library/user-event@^14 \
  @testing-library/jest-dom@^6 jsdom@^29 msw@^2.13.6 \
  prettier@^3 @playwright/test@^1.59.1
```

**Version verification:** All versions above were confirmed via `npm view <pkg> version` and `npm view <pkg> peerDependencies` on 2026-04-26. Re-verify at install time per project policy (RESEARCH HIGH-confidence claims about versions are time-sensitive).

## Architecture Patterns

### Recommended Project Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout, fonts, Tailwind import, error boundary
│   ├── page.tsx                # Single route; composes Sidebar + ChatColumn + TracePanel (D-01)
│   └── globals.css             # @import "tailwindcss"; (Tailwind v4 entry)
├── components/
│   ├── chat/
│   │   ├── ChatColumn.tsx      # Center column; Chat | Dashboard tab toggle (D-04)
│   │   ├── MessageList.tsx     # Renders user + assistant messages
│   │   ├── MarkdownAnswer.tsx  # react-markdown + remark-gfm + capped banner override (D-10/D-11)
│   │   ├── ClarifyCard.tsx     # status='clarify' blue info card (D-12)
│   │   ├── PartialCard.tsx     # status='partial' orange card (D-12)
│   │   ├── ChatInput.tsx       # Textarea + send button; disabled while streaming
│   │   ├── ExamplePrompts.tsx  # Empty-state demo seed (D-09)
│   │   └── FeedbackButtons.tsx # UI-05 thumbs up/down stub (D-17)
│   ├── trace/
│   │   ├── TracePanel.tsx      # Right rail (D-03), live-append (D-06), empty state (D-09)
│   │   ├── TraceStep.tsx       # Headline + collapsible (D-07)
│   │   └── TraceStatusBadge.tsx# ok | warn | error | running pill
│   ├── sidebar/
│   │   ├── ConversationSidebar.tsx # Left rail (D-02), thread list, "New" button (D-14)
│   │   └── ThreadListItem.tsx
│   ├── dashboard/
│   │   ├── DashboardView.tsx
│   │   ├── FuelPriceChart.tsx       # Recharts <LineChart> + 7d|30d|90d toggle (D-15.1)
│   │   ├── SurchargeHistoryChart.tsx# Recharts client-derived (D-15.2)
│   │   └── RangeToggle.tsx
│   └── shared/
│       ├── ErrorBoundary.tsx
│       ├── LoadingSkeleton.tsx
│       └── CapCallout.tsx       # Yellow-50 banner (D-11)
├── hooks/
│   ├── useChatStream.ts         # fetch + ReadableStream SSE consumer (D-19); useReducer for events
│   ├── useConversations.ts      # GET /api/conversations + per-thread loader (D-14, D-15.2)
│   └── useFuelPrices.ts         # GET /api/fuel-prices?days=N (D-15.1)
├── lib/
│   ├── api.ts                   # fetch wrappers; throws typed ApiError
│   ├── sse.ts                   # parseSseStream(reader, onEvent) generic helper
│   ├── formatters.ts            # THB currency, percentage, relative-time
│   └── constants.ts             # API_BASE_URL, EXAMPLE_PROMPTS, RANGE_OPTIONS
├── types/
│   ├── api.types.ts             # Mirrors backend/api/models.py (ChatRequest, ConversationSummary, FuelPricePoint)
│   └── agent.types.ts           # TraceEntry, SurchargeResult, FinalPayload, the 5 SSE event payloads
├── __tests__/
│   ├── setup.ts                 # Vitest setup; jest-dom matchers; MSW server
│   ├── mocks/
│   │   ├── handlers.ts          # MSW handlers for /api/chat (SSE), /api/conversations, /api/fuel-prices
│   │   └── server.ts
│   └── integration/
│       └── chat-flow.test.tsx
├── e2e/
│   └── chat-smoke.spec.ts       # Playwright smoke (optional but recommended for verifier)
├── package.json
├── tsconfig.json                # @/* path aliases per CONVENTIONS.md
├── tailwind.config.ts           # v4 minimal config; colors anchored on yellow-50 callout
├── postcss.config.mjs           # @tailwindcss/postcss plugin
├── next.config.ts
├── eslint.config.mjs            # @next/next + React preset
├── .prettierrc
├── vitest.config.ts
├── playwright.config.ts
└── .gitignore                   # node_modules/, .next/, coverage/, playwright-report/
```

### Pattern 1: SSE Event Envelope and Trace Entry Schema (FROM the backend)

The backend emits exactly five SSE event types (verified in `backend/api/sse.py:13` and `backend/api/routes/chat.py:29`). The TypeScript types must mirror these field-for-field.

```typescript
// frontend/types/agent.types.ts

/** Verified from backend/agent/nodes/*.py — every node uses this exact shape. */
export interface TraceEntry {
  step: number;                 // monotonic step counter
  agent: 'planner' | 'fuel_agent' | 'route_agent' | 'pricing_agent' | 'response';
  tool: string | null;          // tool name when the node called a tool, else null
  tool_input: Record<string, unknown>;
  tool_output: Record<string, unknown>;
  reasoning: string;            // one-line human-readable reasoning
  timestamp: string;            // ISO-8601 UTC with 'Z' (e.g., "2026-04-26T10:15:30.123Z")
  status: 'ok' | 'warn' | 'error';
  // Phase 3 D-13: tool_output may include fetched_at on cache hits
}

/** SurchargeResult shape — verified from backend response_node._render_table(). */
export interface SurchargeResult {
  surcharge_pct: number;        // fraction (0.10 = 10%)
  surcharge_amount: number;     // THB
  total: number;                // THB
  capped: boolean;
}

/** FinalPayload shape — verified from backend AgentState.final_payload + response_node. */
export interface FinalPayload {
  markdown: string;
  surcharge_result: SurchargeResult | null;
  capped: boolean;
  status: 'ok' | 'partial' | 'clarify';
}

/** SSE envelope — verified from backend/api/sse.py format_sse(). */
export type SSEEvent =
  | { type: 'meta';   payload: { thread_id: string } }
  | { type: 'trace';  payload: TraceEntry }
  | { type: 'answer'; payload: FinalPayload }
  | { type: 'error';  payload: { message: string; retryable: boolean } }
  | { type: 'done';   payload: Record<string, never> };
```

### Pattern 2: Hand-rolled SSE Consumer (D-19)

Source pattern verified against `backend/api/routes/chat.py` (which writes `data: <json>\n\n` frames) and `backend/api/sse.py` (envelope shape).

```typescript
// frontend/lib/sse.ts
import type { SSEEvent } from '@/types/agent.types';

/**
 * Parse a fetch ReadableStream of SSE frames. Calls onEvent for each parsed
 * event. Returns when the stream closes (server sends 'done' or connection
 * ends). Designed for POST /api/chat which the native EventSource API can't
 * consume (EventSource is GET-only).
 *
 * Backend frame shape: data: <json>\n\n  (one event per double-newline boundary)
 */
export async function parseSseStream(
  response: Response,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.body) throw new Error('SSE response has no body');
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel();
        return;
      }
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Split on \n\n boundary; last fragment stays in buffer for next chunk.
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        // Each frame is "data: <json>" (one line per backend impl).
        const line = frame.startsWith('data:') ? frame.slice(5).trim() : frame.trim();
        if (!line) continue;
        try {
          onEvent(JSON.parse(line) as SSEEvent);
        } catch (err) {
          console.error('[sse] failed to parse frame', line, err);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

### Pattern 3: API Client Wrapper

```typescript
// frontend/lib/api.ts
import type { ConversationSummary, FuelPricePoint } from '@/types/api.types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function jsonGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new ApiError(res.status, `GET ${path} failed: ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  listConversations: (limit = 50) =>
    jsonGet<ConversationSummary[]>(`/api/conversations?limit=${limit}`),
  getConversation: (threadId: string) =>
    jsonGet<{
      thread_id: string;
      messages: Array<{ role: string; content: string }>;
      surcharge_result: SurchargeResult | null;
      reasoning_trace: TraceEntry[];
      fuel_data: Record<string, unknown> | null;
      route_data: Record<string, unknown> | null;
      errors: Array<Record<string, unknown>>;
    }>(`/api/conversations/${threadId}`),
  fuelPrices: (days = 30) =>
    jsonGet<FuelPricePoint[]>(`/api/fuel-prices?days=${days}`),

  /** Returns the raw Response for SSE consumption — caller passes it to parseSseStream. */
  postChat: (body: { message: string; thread_id?: string }, signal?: AbortSignal) =>
    fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    }),
};
```

### Pattern 4: react-markdown + remark-gfm with the D-11 Capped Banner Override

Two viable approaches per CONTEXT.md D-11. **Recommendation: strip the leading `> ⚠ ...` line before passing to react-markdown** — simpler, doesn't require a custom `blockquote` override that has to distinguish "the cap callout" from "any other blockquote the LLM might emit."

```typescript
// frontend/components/chat/MarkdownAnswer.tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CapCallout } from '@/components/shared/CapCallout';
import type { FinalPayload } from '@/types/agent.types';

const CAP_LINE_RE = /^> ⚠ Cap\/floor applied — review recommended\s*\n\n?/;

export function MarkdownAnswer({ payload }: { payload: FinalPayload }) {
  const cleanMarkdown = payload.capped
    ? payload.markdown.replace(CAP_LINE_RE, '')
    : payload.markdown;

  return (
    <div className="space-y-3">
      {payload.capped && <CapCallout />}
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Backend emits a plain GFM table — let react-markdown handle it.
            // Override only if you need Tailwind table classes.
            table: (props) => <table className="border-collapse" {...props} />,
            th: (props) => <th className="border px-2 py-1 bg-gray-50" {...props} />,
            td: (props) => <td className="border px-2 py-1" {...props} />,
          }}
        >
          {cleanMarkdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}
```

```typescript
// frontend/components/shared/CapCallout.tsx
export function CapCallout() {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-900"
    >
      <span aria-hidden>⚠</span>
      <span>Cap/floor applied — review recommended</span>
    </div>
  );
}
```

### Pattern 5: useChatStream — useReducer Event-Sourced State (D-06, D-19)

```typescript
// frontend/hooks/useChatStream.ts
import { useCallback, useReducer, useRef } from 'react';
import { api } from '@/lib/api';
import { parseSseStream } from '@/lib/sse';
import type { SSEEvent, TraceEntry, FinalPayload } from '@/types/agent.types';

type Status = 'idle' | 'streaming' | 'done' | 'error';

interface ChatStreamState {
  status: Status;
  liveTrace: TraceEntry[];           // current turn only (D-08)
  finalPayload: FinalPayload | null;
  threadId: string | null;
  error: { message: string; retryable: boolean } | null;
}

type Action =
  | { type: 'START' }
  | { type: 'META'; threadId: string }
  | { type: 'TRACE'; entry: TraceEntry }
  | { type: 'ANSWER'; payload: FinalPayload }
  | { type: 'ERROR'; error: { message: string; retryable: boolean } }
  | { type: 'DONE' };

function reducer(state: ChatStreamState, action: Action): ChatStreamState {
  switch (action.type) {
    case 'START':  return { ...state, status: 'streaming', liveTrace: [], finalPayload: null, error: null };
    case 'META':   return { ...state, threadId: action.threadId };
    case 'TRACE':  return { ...state, liveTrace: [...state.liveTrace, action.entry] };
    case 'ANSWER': return { ...state, finalPayload: action.payload };
    case 'ERROR':  return { ...state, status: 'error', error: action.error };
    case 'DONE':   return { ...state, status: state.status === 'error' ? 'error' : 'done' };
  }
}

export function useChatStream(initialThreadId: string | null = null) {
  const [state, dispatch] = useReducer(reducer, {
    status: 'idle',
    liveTrace: [],
    finalPayload: null,
    threadId: initialThreadId,
    error: null,
  });
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (message: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      dispatch({ type: 'START' });

      try {
        const response = await api.postChat(
          { message, thread_id: state.threadId ?? undefined },
          controller.signal,
        );
        if (!response.ok) {
          dispatch({ type: 'ERROR', error: { message: `HTTP ${response.status}`, retryable: false } });
          return;
        }
        await parseSseStream(
          response,
          (ev: SSEEvent) => {
            switch (ev.type) {
              case 'meta':
                dispatch({ type: 'META', threadId: ev.payload.thread_id });
                localStorage.setItem('thread_id', ev.payload.thread_id);
                break;
              case 'trace':  dispatch({ type: 'TRACE', entry: ev.payload }); break;
              case 'answer': dispatch({ type: 'ANSWER', payload: ev.payload }); break;
              case 'error':  dispatch({ type: 'ERROR', error: ev.payload }); break;
              case 'done':   dispatch({ type: 'DONE' }); break;
            }
          },
          controller.signal,
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        dispatch({ type: 'ERROR', error: { message: String(err), retryable: false } });
      } finally {
        if (state.status !== 'error') dispatch({ type: 'DONE' });
      }
    },
    [state.threadId, state.status],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    localStorage.removeItem('thread_id');
    dispatch({ type: 'START' });
    dispatch({ type: 'DONE' });
    // setThreadId-equivalent done by next 'meta' event from server.
  }, []);

  return { ...state, send, reset };
}
```

### Pattern 6: Live-Append Trace Panel (D-06)

The `useChatStream.liveTrace` array is exactly the trace panel's data source. Each entry renders as a `TraceStep`. The "running" placeholder mentioned in D-06 is implemented by reading `status === 'streaming'` from `useChatStream` — you append a synthetic step with `status: 'running'` between the last trace entry and the next anticipated one (or simply show a "..." pulse at the bottom of the list while streaming).

```typescript
// frontend/components/trace/TracePanel.tsx
'use client';
import { TraceStep } from '@/components/trace/TraceStep';
import { ExamplePrompts } from '@/components/chat/ExamplePrompts';
import type { TraceEntry } from '@/types/agent.types';

export function TracePanel(props: {
  entries: TraceEntry[];
  isStreaming: boolean;
  onExamplePromptClick: (text: string) => void;
}) {
  if (!props.isStreaming && props.entries.length === 0) {
    return (
      <aside className="border-l p-4 space-y-3">
        <h2 className="font-semibold">Reasoning trace</h2>
        <p className="text-sm text-gray-600">
          When you ask a question, the agent's planner, fuel, route, and pricing
          steps will stream here in real time.
        </p>
        <ExamplePrompts onClick={props.onExamplePromptClick} />
      </aside>
    );
  }
  return (
    <aside className="border-l p-4 space-y-2 overflow-y-auto" aria-live="polite">
      <h2 className="font-semibold">Reasoning trace</h2>
      <ol className="space-y-2">
        {props.entries.map((entry) => (
          <TraceStep key={`${entry.step}-${entry.agent}`} entry={entry} />
        ))}
      </ol>
      {props.isStreaming && (
        <div className="text-xs text-gray-500 italic animate-pulse">…thinking</div>
      )}
    </aside>
  );
}
```

### Pattern 7: TraceStep Headline + Collapsible Detail (D-07)

```typescript
// frontend/components/trace/TraceStep.tsx
'use client';
import { useState } from 'react';
import clsx from 'clsx';
import type { TraceEntry } from '@/types/agent.types';

const AGENT_LABEL: Record<TraceEntry['agent'], string> = {
  planner: 'Planner',
  fuel_agent: 'Fuel agent',
  route_agent: 'Route agent',
  pricing_agent: 'Pricing agent',
  response: 'Response',
};

const STATUS_COLOR: Record<TraceEntry['status'], string> = {
  ok: 'bg-green-100 text-green-800',
  warn: 'bg-yellow-100 text-yellow-800',
  error: 'bg-red-100 text-red-800',
};

export function TraceStep({ entry }: { entry: TraceEntry }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded border bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm"
      >
        <span className="flex items-center gap-2">
          <span className="font-mono text-xs text-gray-500">#{entry.step}</span>
          <span className="font-medium">{AGENT_LABEL[entry.agent]}</span>
          <span className="truncate text-gray-700">{entry.reasoning}</span>
        </span>
        <span className={clsx('rounded px-2 py-0.5 text-xs font-medium', STATUS_COLOR[entry.status])}>
          {entry.status}
        </span>
      </button>
      {open && (
        <div className="border-t px-3 py-2 text-xs space-y-2">
          {entry.tool && <div><span className="font-semibold">Tool:</span> <code>{entry.tool}</code></div>}
          <div>
            <div className="font-semibold">Input</div>
            <pre className="overflow-x-auto bg-gray-50 p-2">{JSON.stringify(entry.tool_input, null, 2)}</pre>
          </div>
          <div>
            <div className="font-semibold">Output</div>
            <pre className="overflow-x-auto bg-gray-50 p-2">{JSON.stringify(entry.tool_output, null, 2)}</pre>
          </div>
          <div className="text-gray-500">
            <time dateTime={entry.timestamp} title={entry.timestamp}>
              {entry.timestamp}
            </time>
          </div>
        </div>
      )}
    </li>
  );
}
```

### Pattern 8: Recharts ResponsiveContainer + LineChart (Fuel Price Chart, D-15.1)

```typescript
// frontend/components/dashboard/FuelPriceChart.tsx
'use client';
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { FuelPricePoint } from '@/types/api.types';

export function FuelPriceChart({ data }: { data: FuelPricePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis domain={['auto', 'auto']} unit=" THB" />
        <Tooltip formatter={(v: number) => `${v.toFixed(2)} THB/L`} />
        <Line
          type="monotone"
          dataKey="price"
          stroke="#2563eb"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}     // Pitfall 4: avoid React 19 + Recharts animation flicker
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

### Pattern 9: Feedback Stub (UI-05 / D-17)

```typescript
// frontend/components/chat/FeedbackButtons.tsx
'use client';
import { useState } from 'react';

export function FeedbackButtons(props: { threadId: string; messageId: string }) {
  const [voted, setVoted] = useState<'up' | 'down' | null>(null);

  function vote(score: 'up' | 'down') {
    setVoted(score);
    const payload = { thread_id: props.threadId, message_id: props.messageId, score };
    // D-17: local-only in Phase 4. Phase 5 swaps to api.postFeedback(payload).
    console.log('[feedback]', payload);
    try {
      const stored = JSON.parse(localStorage.getItem('feedback') ?? '[]');
      stored.push({ ...payload, ts: new Date().toISOString() });
      localStorage.setItem('feedback', JSON.stringify(stored));
    } catch {/* localStorage may be full; non-fatal */}
  }

  return (
    <div className="flex gap-1 text-sm">
      <button
        aria-label="Helpful"
        aria-pressed={voted === 'up'}
        disabled={voted !== null}
        onClick={() => vote('up')}
        className={voted === 'up' ? 'opacity-100' : 'opacity-50 hover:opacity-100'}
      >👍</button>
      <button
        aria-label="Not helpful"
        aria-pressed={voted === 'down'}
        disabled={voted !== null}
        onClick={() => vote('down')}
        className={voted === 'down' ? 'opacity-100' : 'opacity-50 hover:opacity-100'}
      >👎</button>
    </div>
  );
}
```

### Pattern 10: Conversation Resume Flow (D-14, D-20)

```typescript
// frontend/hooks/useConversations.ts
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { ConversationSummary } from '@/types/api.types';

export function useConversations() {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await api.listConversations(50));
    } catch (err) {
      console.error('[useConversations]', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  /** Resume a thread: load history + persist thread_id so next chat continues it (D-20). */
  const resume = useCallback(async (threadId: string) => {
    const conv = await api.getConversation(threadId);
    localStorage.setItem('thread_id', threadId);
    return conv;
  }, []);

  return { items, loading, refresh, resume };
}
```

### Anti-Patterns to Avoid

- **Reconstructing the breakdown table from `surcharge_result` (D-13 violation).** The backend already renders the locked 4-row table inside `final_payload.markdown`. Re-rendering on the client desyncs the two surfaces and breaks the D-11 "single source of truth" guarantee.
- **Inventing the cap callout from `capped` alone (D-11 antipattern).** Either strip the `> ⚠ ...` line from markdown OR override the blockquote — never both, and never invent a banner from `capped` while leaving the `>` line in the rendered markdown.
- **Polling `GET /api/conversations` to detect new turns.** The SSE stream already reports the active thread via `meta`; refresh the sidebar only on user action ("New conversation" click, page focus, post-chat completion).
- **Putting the dashboard on its own route (`/dashboard`).** D-04 explicitly puts it inside the center-column tab toggle — sidebar and trace panel must stay in place.
- **Calling `useChatStream` inside `app/page.tsx` (a Server Component).** All hook-bearing components must use `'use client'`. The root `page.tsx` may stay a Server Component if it only composes Client Components.
- **Token-level streaming work-around** to make the chat "feel faster." Phase 3 D-17 deliberately picked node-completion granularity. Trace-level live append IS the live-thinking effect — don't try to char-stream the markdown answer.
- **Caching `surcharge-history` in IndexedDB.** D-15.2 derives client-side per page load; if it's slow, the right answer is a Phase 5 backend endpoint, not a cache that risks staleness.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown rendering with GFM tables | Custom MD parser | `react-markdown` + `remark-gfm` | The locked 4-row table needs GFM syntax; rolling your own table parser is a rabbit hole, and react-markdown handles XSS by default (no `dangerouslySetInnerHTML`). |
| Charts (line, bar, axis, tooltip, responsive container) | Plain SVG / canvas / D3 from scratch | `recharts` | PROJECT.md locks Recharts. Rolling your own gives up axis tick math, tooltip hit-testing, responsive resizing, and aria-friendly defaults for zero benefit. |
| SSE frame parsing | Don't pull `eventsource` (GET-only) or write a regex parser for `data:` lines | The 40-line `parseSseStream` helper in Pattern 2 (or `@microsoft/fetch-event-source` if you accept the stale-but-stable tradeoff) | The native `EventSource` API is GET-only and the backend is POST. The buffering + `\n\n` split is the only real subtlety — keep it isolated in `lib/sse.ts`. |
| TypeScript types for backend models | Don't manually duplicate every Pydantic field with mismatched names | Hand-mirror `backend/api/models.py` field-for-field with snake_case preserved (the backend serializes snake_case JSON; do NOT camelCase TS types). | Mismatch between TS type names and JSON wire shape is the #1 source of "data is undefined" bugs. |
| Date formatting (relative + absolute) | `new Date().toLocaleString(...)` everywhere | `Intl.RelativeTimeFormat` (built-in) for relative, `toLocaleString('en-GB')` for absolute. | No need to pull date-fns / dayjs for two formatters. |
| THB currency formatting | Inline `(n).toFixed(2) + ' THB'` | `Intl.NumberFormat('th-TH', { style: 'currency', currency: 'THB' })` in `lib/formatters.ts` | Built-in, locale-aware, handles negatives correctly. |
| Mocking the backend in tests | Custom `fetch` stubs scattered across test files | `msw` 2.x with handlers in `__tests__/mocks/handlers.ts` | MSW intercepts at the network layer — same code path runs in tests as production. SSE streams can be mocked with `ReadableStream` inside a handler. |
| State across `useChatStream` and `useConversations` | Global mutable singleton | Lift to a small context provider (`ChatProvider`) at `app/page.tsx` | Both hooks need to know the current `thread_id`; sharing via a provider beats prop-drilling without pulling in Zustand. |
| Routing for `Chat | Dashboard` toggle | Next.js dynamic route + `useRouter` + URL state | Local `useState<'chat' | 'dashboard'>` in `ChatColumn` | D-04 explicitly mandates a tab toggle inside the center column, NOT a separate route. |

**Key insight:** Frontend tooling has matured enough that hand-rolling almost any of the above is a Phase-5 maintenance burden waiting to happen. The one exception — and it's intentional — is the SSE consumer, where rolling our own ~40-line helper avoids depending on `@microsoft/fetch-event-source` (last published 2021-04, effectively unmaintained) for a 5-event protocol that's trivial to parse.

## Common Pitfalls

### Pitfall 1: Server Component / Client Component confusion

**What goes wrong:** Importing `useState` / `useEffect` / `useReducer` into a file that doesn't have `'use client'` at the top. Build error: "useState only works in client components."

**Why it happens:** Next.js 15 App Router defaults to React Server Components. Hooks require client.

**How to avoid:** Add `'use client'` as the first line of every file that uses hooks (`app/page.tsx` becomes a client root, OR keep `page.tsx` server and put the interactive composition in a `<ChatApp />` client component that `page.tsx` imports).

**Warning signs:** Build error mentions "useState" or "createContext"; runtime hydration mismatch.

### Pitfall 2: SSE buffering by Next.js dev proxy or browser

**What goes wrong:** Trace events arrive in one batch at the end instead of streaming live; the "live thinking" effect is destroyed.

**Why it happens:** Next.js development server, intermediate proxies, or browser extensions (especially ad blockers with anti-tracking heuristics) buffer the response.

**How to avoid:** Backend already sets `Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive` (verified in `backend/api/routes/chat.py:75-79`). On the frontend side, ensure `fetch` is called with no `Content-Encoding` request header that could trigger gzip-then-buffer. Use the browser DevTools "Network → EventStream" tab to verify frames arrive incrementally.

**Warning signs:** All trace entries appear simultaneously; the "…thinking" indicator never shows; DevTools shows the response as one chunk.

### Pitfall 3: Recharts × React 19.2.x — blank charts

**What goes wrong:** `<LineChart>` and `<BarChart>` render nothing — empty SVG, no console errors.

**Why it happens:** Recharts depends on `react-is`; with React 19.2.x, npm may resolve a `react-is` version mismatched with the installed `react`. The `react-is` package is used internally by Recharts to inspect element types; a mismatch silently fails. Documented in [Recharts issue #6857](https://github.com/recharts/recharts/issues/6857) (closed; reproduction needed but the override is the confirmed workaround).

**How to avoid:** Add to `package.json` BEFORE installing Recharts:
```json
{
  "overrides": {
    "react-is": "^19.2.5"
  }
}
```
Then `rm -rf node_modules package-lock.json && npm install`. Verify with `npm ls react-is` — should show only one version, matching `react`.

**Warning signs:** Charts render as empty SVG; `npm ls react-is` shows multiple versions or a 16.x/17.x/18.x version.

### Pitfall 4: Recharts animation flicker on re-render

**What goes wrong:** Each chart data refresh triggers an animation that briefly shows the chart at "zero" before transitioning, looking glitchy on the dashboard.

**Why it happens:** Recharts default `isAnimationActive: true` re-runs the entry animation on prop changes.

**How to avoid:** Set `isAnimationActive={false}` on `<Line>` / `<Bar>` for dashboard charts that re-fetch on the range toggle. (See Pattern 8.)

**Warning signs:** Visible "redraw from zero" when changing the `7d | 30d | 90d` toggle.

### Pitfall 5: Tailwind v4 setup mismatch

**What goes wrong:** Classes like `bg-yellow-50` don't apply; `npm run dev` works but elements are unstyled.

**Why it happens:** Tailwind v4 dropped the JS `tailwind.config.js` content-paths model and uses CSS-first configuration with `@import "tailwindcss"` and the `@tailwindcss/postcss` PostCSS plugin. v3-style configs silently no-op.

**How to avoid:**
- `app/globals.css` has `@import "tailwindcss";` (NOT the old `@tailwind base/components/utilities` triple).
- `postcss.config.mjs` uses `@tailwindcss/postcss`, not `tailwindcss`.
- Theme tokens go in CSS via the `@theme` directive (not `tailwind.config.ts`).
- `create-next-app --tailwind` sets all of this up correctly out of the box; don't fight it.

**Warning signs:** `npm view tailwindcss version` says `4.x` but classes are unstyled; PostCSS config still references `tailwindcss` directly.

### Pitfall 6: localStorage access during SSR / hydration mismatch

**What goes wrong:** `localStorage is not defined` during build, OR initial render uses `null` thread_id then re-renders with the stored value, causing a hydration warning.

**Why it happens:** Next.js renders Client Components on the server during the initial pass; `localStorage` only exists in the browser.

**How to avoid:** Read `localStorage` inside `useEffect` (post-mount) instead of as the `useState` initializer. If you need the value synchronously, accept that the first render shows the "no thread" state and the second shows the loaded state — use a `mounted` flag to suppress the sidebar until mount completes.

```typescript
const [threadId, setThreadId] = useState<string | null>(null);
useEffect(() => { setThreadId(localStorage.getItem('thread_id')); }, []);
```

**Warning signs:** "Text content does not match server-rendered HTML" warnings in dev console; build error mentions `localStorage`.

### Pitfall 7: SSE stream not closing on user navigation / "New conversation" click

**What goes wrong:** The previous SSE stream keeps pushing events after the user navigates away, the new chat starts, OR the user clicks "New conversation" mid-stream — trace entries from the old turn appear in the new turn's panel.

**Why it happens:** `fetch` requests aren't auto-cancelled when components unmount; `ReadableStream` readers held open continue reading.

**How to avoid:** Use `AbortController` per stream (Pattern 5 already does this — `abortRef.current?.abort()` before starting the next stream, `useEffect` cleanup, and `signal: controller.signal` passed to both `fetch` and `parseSseStream`).

**Warning signs:** Stale trace entries appear; React warning "Can't perform state update on unmounted component"; multiple "done" events fire.

### Pitfall 8: Surcharge-history N+1 fetch latency

**What goes wrong:** Dashboard takes 5–10 seconds to load because `SurchargeHistoryChart` fires 20 sequential `GET /api/conversations/:id` calls.

**Why it happens:** D-15.2 derives surcharge history client-side. Naive implementation does `for (const t of threads) await api.getConversation(t.thread_id)`.

**How to avoid:** Use `Promise.all` to parallelize, and cap concurrency (e.g., 5 in flight) if the dev backend chokes:
```typescript
const results = await Promise.all(threads.slice(0, 20).map((t) => api.getConversation(t.thread_id).catch(() => null)));
```
If still painful, the CONTEXT.md `<specifics>` block already flags: "escalate to a Phase 5 backend endpoint rather than caching tricks."

**Warning signs:** Dashboard tab shows loading skeleton for >3 seconds locally.

### Pitfall 9: Bangkok Metro vs Central Region copy drift

**What goes wrong:** UI copy says "Central Region" while the rest of the project uses "Bangkok Metro" (per resolved backlog 999.2 — Quick Task `260425-vc6`).

**Why it happens:** Old screenshots, old PROJECT.md drafts, or copy-paste from internal zone IDs (`central-1`, `central-2`, `central-3`).

**How to avoid:** Single search-and-replace audit before verifier. ALL user-facing strings (example prompts, dashboard titles, error messages, sidebar empty state, mobile drawer labels) say "Bangkok Metro". Internal zone IDs `central-1/2/3` only appear inside the trace panel's `tool_input` / `tool_output` JSON, which is acceptable.

**Warning signs:** Grep for `Central Region` in `frontend/` returns any matches.

### Pitfall 10: Test SSE mock — naive ReadableStream construction

**What goes wrong:** Component tests for `useChatStream` deadlock or timeout because the mock `ReadableStream` doesn't enqueue + close correctly.

**Why it happens:** Constructing a `ReadableStream` of SSE frames in a test requires explicit `controller.enqueue(encoder.encode(...))` calls and a final `controller.close()`. Forgetting `close()` leaves the reader hanging.

**How to avoid:**
```typescript
function makeSseStream(events: SSEEvent[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const ev of events) {
        controller.enqueue(enc.encode(`data: ${JSON.stringify(ev)}\n\n`));
      }
      controller.close();
    },
  });
}
```
And in MSW handlers, return `new Response(makeSseStream([...]), { headers: { 'Content-Type': 'text/event-stream' } })`.

**Warning signs:** Test timeouts in `useChatStream.test.ts`; reader hangs on `read()`.

## Code Examples

The Architecture Patterns section above (Patterns 1–10) provides verified, copy-pasteable code for every integration point listed in CONTEXT.md `<code_context>`. Each example has been cross-checked against the backend implementation files referenced in `## Phase Requirements`.

Additional minimal scaffolding (recommended starting points):

### `frontend/app/page.tsx`

```typescript
import { ChatApp } from '@/components/ChatApp';

export default function HomePage() {
  return <ChatApp />;
}
```

### `frontend/components/ChatApp.tsx` (the client root that composes the three columns)

```typescript
'use client';
import { useState } from 'react';
import { ConversationSidebar } from '@/components/sidebar/ConversationSidebar';
import { ChatColumn } from '@/components/chat/ChatColumn';
import { TracePanel } from '@/components/trace/TracePanel';
import { useChatStream } from '@/hooks/useChatStream';

export function ChatApp() {
  const chat = useChatStream();
  return (
    <main className="grid h-screen grid-cols-[260px_1fr_360px]">
      <ConversationSidebar />
      <ChatColumn chat={chat} />
      <TracePanel
        entries={chat.liveTrace}
        isStreaming={chat.status === 'streaming'}
        onExamplePromptClick={chat.send}
      />
    </main>
  );
}
```

### `frontend/postcss.config.mjs` (Tailwind v4 wiring)

```javascript
export default {
  plugins: {
    '@tailwindcss/postcss': {},
  },
};
```

### `frontend/app/globals.css`

```css
@import "tailwindcss";
```

### `frontend/.env.example` addition

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

(The repo's existing `.env.example` lives at `/Users/pollot/Desktop/express-dynamic-workflow/.env.example` — add this line; do not create a separate `frontend/.env.example`.)

### `frontend/package.json` overrides (Pitfall 3 workaround)

```json
{
  "overrides": {
    "react-is": "^19.2.5"
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind CSS v3 with `tailwind.config.js` + `@tailwind base/components/utilities` | Tailwind CSS v4 with `@import "tailwindcss"` and `@tailwindcss/postcss` plugin | 2025-01 (v4.0 release); 4.2.4 latest as of 2026-04-21 | CSS-first config; ~70% smaller production CSS; `create-next-app --tailwind` already targets v4. |
| `pages/` Router | `app/` Router (App Router with Server Components) | Default since Next.js 13.4 (2023-05); recommended in all Next.js 15+ docs | Hooks require explicit `'use client'`; root `layout.tsx` is required. |
| Recharts 2.x with React 18 only (alpha for React 19) | Recharts 3.x with `react: ^16-19` peerDeps | 3.0 release in 2025; 3.8.1 (2026-03-25) latest | Stable React 19 support; `react-is` override still required as a defensive measure (Pitfall 3). |
| `EventSource` API for SSE | `fetch` + `ReadableStream` for POST-based SSE | N/A — `EventSource` is GET-only by spec; `fetch` POST has always been the way for chat UIs | Hand-rolled is ~40 LOC; library options (`@microsoft/fetch-event-source`) are battle-tested but stale. |
| Webpack as default bundler | Turbopack as default in Next.js 16; webpack opt-in via `--webpack` | Next.js 16.0 (2026); 15.x still defaults to webpack | We're locked to Next.js 15, so webpack remains the default — no flag needed. The `--no-turbopack` flag in the install command above is defensive and only matters if `create-next-app@latest` (which installs Next 16) gets used. |
| Class-based ESLint configs (`.eslintrc.json`) | Flat configs (`eslint.config.mjs`) — required by ESLint 9+ | ESLint 9 (2024) | `create-next-app` already generates the flat config; don't introduce `.eslintrc.json`. |
| `next lint` command | `eslint` CLI directly | Next.js 16 dropped `next lint`; 15.x still ships it but the CLI is the documented path | `package.json` should have `"lint": "eslint"` per official docs. |

**Deprecated/outdated:**
- `next lint` command — being removed in Next.js 16; use `eslint` CLI directly even on 15.x for forward compatibility.
- `tailwind.config.ts` content-paths model — Tailwind v4 auto-detects content; the file may exist but with minimal/empty config.
- Recharts `<Cell>` component (deprecated 3.x) — use `shape` prop. Not relevant to Phase 4 (no Pie chart) but worth noting if a future v2 adds shipping-type breakdown.
- `EventSource` polyfills — irrelevant since chat is POST-based.

## Open Questions

1. **`messages` shape replayed from `GET /api/conversations/:id`**
   - **What we know:** `backend/api/routes/conversations.py:113` returns `messages: values.get("messages") or []`. `AgentState.messages` is `List[dict]` per `backend/agent/state.py:17` — but the v3 plan (per Plan 03-01 notes) upgraded these to LangChain `BaseMessage` instances internally.
   - **What's unclear:** When serialized over JSON, do messages come back as `{role, content}` dicts (the original v1 shape) or as the LangChain `BaseMessage` JSON shape (`{lc, type, id, ...}`)? `conversations.py:67-72` handles both, suggesting either is possible.
   - **Recommendation:** Plan a lightweight normalizer in `frontend/lib/api.ts` that handles both shapes — coerce to `{role, content}` after fetching. Verify with a single live `curl` against `GET /api/conversations/<some-thread>` early in implementation.

2. **Should the FE poll `GET /api/conversations` to refresh the sidebar after each chat completes?**
   - **What we know:** `meta` event already gives the active thread_id; the sidebar only needs a refresh when a NEW thread is created or an existing thread's `last_updated` changes.
   - **What's unclear:** Whether to poll, refresh on `done` event, or refresh on user focus.
   - **Recommendation:** Refresh on (a) "done" event of `useChatStream` when the response was successful, and (b) initial mount. Skip polling — thread list rarely changes outside the user's actions in a single-user demo.

3. **Empty `final_payload.surcharge_result` on `status='clarify'` — type strictness**
   - **What we know:** When status is `clarify`, `surcharge_result` is `null` (verified in `response_node.py:165-176`).
   - **What's unclear:** Whether `MessageList` should render `<MarkdownAnswer>` or `<ClarifyCard>` based on `status` alone or also check `surcharge_result === null`.
   - **Recommendation:** Dispatch on `status` only (the source of truth per D-12). Don't double-check fields that the backend has already gated — that's how desync bugs creep in.

4. **Recharts `<ResponsiveContainer>` height in a flex container**
   - **What we know:** ResponsiveContainer requires a parent with explicit height to compute its own height.
   - **What's unclear:** Whether `DashboardView` needs Tailwind `h-full` or explicit `height` props on each chart wrapper.
   - **Recommendation:** Use fixed pixel heights (e.g., `height={300}`) on each chart's `<ResponsiveContainer>` rather than `100%` heights. Simpler, predictable, and avoids the "ResponsiveContainer reports 0px" footgun.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Next.js, npm scripts, Vitest, Playwright | ✓ (assumed — backend is running, repo standards lock to Node 18+; Next.js 15.5 minimum is Node 20.9 per official docs) | — (run `node --version` at install time) | None — required for build |
| npm | Package install | ✓ (ships with Node) | — | yarn or pnpm if user prefers, but `package-lock.json` standardizes on npm |
| Backend running on `http://localhost:8000` | Live FE smoke testing, Playwright e2e | ✓ (Phase 3 complete, 103 tests passing) | — | Use MSW handlers for unit tests; for e2e, `playwright.config.ts` can launch backend via `webServer` block |
| Backend `data/raw/eppo_diesel_prices.csv` | `GET /api/fuel-prices` (otherwise returns 503) | ✓ (Phase 1 seeded; verified in repo) | — | Backend returns 503 if missing — frontend should catch this and show "Fuel price data unavailable" in `FuelPriceChart` |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — all required tooling is standard.

**Note on Node version:** Next.js 15.5 requires Node 20.9+ per official docs (verified 2026-04-26). The repo's CLAUDE.md says "Node.js 18+" — these are in tension. The planner should add a Wave-0 task to verify `node --version` ≥ 20.9 and update CLAUDE.md / setup instructions if needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.5 (frontend); pytest (backend, already configured for Phase 3 verification) |
| Config file | `frontend/vitest.config.ts` (Wave 0) — none exists yet |
| Quick run command | `cd frontend && npm test -- --run` |
| Full suite command | `cd frontend && npm test -- --run --coverage && npm run e2e` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| **UI-01** | `useChatStream` dispatches `meta`/`trace`/`answer`/`done` from a mocked SSE stream | unit | `cd frontend && npm test -- --run hooks/useChatStream.test.ts` | ❌ Wave 0 |
| **UI-01** | `parseSseStream` handles split-frame buffering (multi-chunk `\n\n` boundary) | unit | `cd frontend && npm test -- --run lib/sse.test.ts` | ❌ Wave 0 |
| **UI-01** | `<ChatInput>` disables while `status === 'streaming'` and re-enables on `done` | component | `cd frontend && npm test -- --run components/chat/ChatInput.test.tsx` | ❌ Wave 0 |
| **UI-02** | `<TracePanel>` appends a new step per `trace` event (live, not batched) | component | `cd frontend && npm test -- --run components/trace/TracePanel.test.tsx` | ❌ Wave 0 |
| **UI-02** | `<TraceStep>` toggles open on click; renders `tool_input`, `tool_output`, `timestamp` when expanded | component | `cd frontend && npm test -- --run components/trace/TraceStep.test.tsx` | ❌ Wave 0 |
| **UI-02** | Empty state shows explainer + 2–3 example prompts (D-09); clicking one calls `send` | component | `cd frontend && npm test -- --run components/chat/ExamplePrompts.test.tsx` | ❌ Wave 0 |
| **UI-03** | `<MarkdownAnswer>` renders the 4-row breakdown table from `final_payload.markdown` (verifies remark-gfm wired) | component | `cd frontend && npm test -- --run components/chat/MarkdownAnswer.test.tsx` | ❌ Wave 0 |
| **UI-03** | When `capped === true`, `<CapCallout>` renders ABOVE the markdown AND the `> ⚠ ...` line is stripped | component | (same file as above) | ❌ Wave 0 |
| **UI-04** | `<FuelPriceChart>` renders an SVG with at least one `<path>` for the Line series given mock data (smoke) | component | `cd frontend && npm test -- --run components/dashboard/FuelPriceChart.test.tsx` | ❌ Wave 0 |
| **UI-04** | `<RangeToggle>` switching from `30d` to `7d` re-fetches with the right query param | component+hook | `cd frontend && npm test -- --run components/dashboard/RangeToggle.test.tsx` | ❌ Wave 0 |
| **UI-04** | `<SurchargeHistoryChart>` derives data points from `useConversations` + per-thread fetches; renders empty state when no threads have `surcharge_result` | component | `cd frontend && npm test -- --run components/dashboard/SurchargeHistoryChart.test.tsx` | ❌ Wave 0 |
| **UI-05** | `<FeedbackButtons>` writes `{thread_id, message_id, score}` to localStorage on click; visually marks "voted" | component | `cd frontend && npm test -- --run components/chat/FeedbackButtons.test.tsx` | ❌ Wave 0 |
| **UI-05** | Buttons do NOT call `fetch` — verifies API-05 wire-up is genuinely deferred | component | (same file) | ❌ Wave 0 |
| **UI-06** | `<ConversationSidebar>` renders threads from `useConversations`; clicking one calls `resume` and persists `thread_id` to localStorage | component+hook | `cd frontend && npm test -- --run components/sidebar/ConversationSidebar.test.tsx` | ❌ Wave 0 |
| **UI-06** | "New conversation" clears `thread_id` from localStorage and resets `useChatStream` | component | (same file) | ❌ Wave 0 |
| **All UI** | E2E smoke: launch app, type "Surcharge for 15kg Bounce, Bangkok → Nonthaburi", verify trace panel populates and breakdown table appears | e2e (Playwright) | `cd frontend && npx playwright test e2e/chat-smoke.spec.ts` | ❌ Wave 0 (requires backend running) |

### Sampling Rate
- **Per task commit:** `cd frontend && npm test -- --run` (Vitest run mode, no watch)
- **Per wave merge:** `cd frontend && npm test -- --run --coverage` (Vitest with coverage report)
- **Phase gate:** Full suite green (`npm test -- --run` + `npx playwright test`) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `frontend/package.json` — entire scaffold; pin `next@^15.5.15`, add `overrides.react-is`, install all libs from "Standard Stack" table
- [ ] `frontend/vitest.config.ts` — Vitest config with JSDOM, React plugin, path aliases
- [ ] `frontend/playwright.config.ts` — Playwright config with `webServer` to launch `npm run dev` on port 3000 + (optionally) the FastAPI backend on 8000
- [ ] `frontend/__tests__/setup.ts` — `@testing-library/jest-dom` matchers; MSW server lifecycle (`beforeAll`/`afterEach`/`afterAll`)
- [ ] `frontend/__tests__/mocks/handlers.ts` — MSW handlers for `POST /api/chat` (returns SSE `ReadableStream`), `GET /api/conversations`, `GET /api/conversations/:id`, `GET /api/fuel-prices`
- [ ] `frontend/__tests__/mocks/server.ts` — MSW server factory
- [ ] `frontend/__tests__/fixtures/sse.ts` — `makeSseStream(events)` helper (Pitfall 10) and canonical event fixtures (a happy-path turn, a clarify turn, a partial turn, a capped turn)
- [ ] `frontend/__tests__/fixtures/agentState.ts` — TraceEntry, FinalPayload, SurchargeResult fixtures matching backend output
- [ ] Framework install: `npm install -D vitest @vitejs/plugin-react @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom msw @playwright/test`
- [ ] `frontend/tsconfig.json` — confirm `paths` for `@/components`, `@/lib`, `@/types`, `@/hooks` (create-next-app emits a basic version; extend per CONVENTIONS.md)
- [ ] `frontend/eslint.config.mjs` — confirm `@next/next` + `react` rule sets

## Sources

### Primary (HIGH confidence)
- **Next.js 15 Installation docs** ([nextjs.org/docs/app/getting-started/installation](https://nextjs.org/docs/app/getting-started/installation)) — verified create-next-app flags, App Router defaults, React 19 declaration requirement, ESLint flat-config requirement.
- **npm registry direct queries (verified 2026-04-26):**
  - `npm view next version` → `16.2.4` (latest), `npm view next@15 versions` → 15.x latest is `15.5.15`
  - `npm view react version` → `19.2.5`
  - `npm view tailwindcss version` → `4.2.4`
  - `npm view recharts version` → `3.8.1`; `npm view recharts peerDependencies` → `react: ^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0`, `react-is: ^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0`
  - `npm view react-markdown version` → `10.1.0`
  - `npm view remark-gfm version` → `4.0.1`
  - `npm view vitest version` → `4.1.5`
  - `npm view @testing-library/react version` → `16.3.2`
  - `npm view msw version` → `2.13.6`
  - `npm view @playwright/test version` → `1.59.1`
- **Backend source files (canonical schema for the entire frontend):**
  - `backend/api/models.py` — `ChatRequest`, `SSEEvent`, `ConversationSummary`, `FuelPricePoint`
  - `backend/api/sse.py` — `format_sse(event_type, payload)` envelope shape
  - `backend/api/routes/chat.py` — SSE handler, `_NODE_NAMES` filter, `meta`/`trace`/`answer`/`error`/`done` flow, response headers
  - `backend/api/routes/conversations.py` — list + get-by-id contracts
  - `backend/api/routes/fuel_prices.py` — `GET /api/fuel-prices?days=N` contract; 503 on missing CSV
  - `backend/agent/state.py` — `AgentState` including `final_payload`
  - `backend/agent/nodes/response_node.py` — `_render_table()` proves the 4-row markdown shape and `_CAP_CALLOUT` line
  - `backend/agent/nodes/planner.py` — TraceEntry shape (12 fields)
- **CONTEXT.md** — `.planning/phases/04-frontend-reasoning-trace/04-CONTEXT.md` (D-01..D-20, deferred ideas, code_context integration points)
- **CLAUDE.md, CONVENTIONS.md, PROJECT.md, REQUIREMENTS.md, STATE.md** — project constraints, locked stack, naming conventions, requirement IDs

### Secondary (MEDIUM confidence — verified against official sources)
- **Recharts 3.x React 19 support** ([Issue #4558](https://github.com/recharts/recharts/issues/4558), [npm peerDependencies](https://www.npmjs.com/package/recharts)) — peerDeps confirm React 19 support; `react-is` override remains the documented defensive workaround.
- **Recharts 3.x release notes** ([github.com/recharts/recharts/releases](https://github.com/recharts/recharts/releases)) — 3.8.0 typed-charts helper, 3.8.1 bug fixes, no breaking changes from 2.x for our LineChart + BarChart usage.
- **Tailwind v4 + Next.js 15 setup** ([tailwindcss.com/docs/guides/nextjs](https://tailwindcss.com/docs/guides/nextjs)) — `@tailwindcss/postcss` plugin requirement, `@import "tailwindcss"` syntax, no JS config file needed.
- **react-markdown + remark-gfm** ([github.com/remarkjs/react-markdown](https://github.com/remarkjs/react-markdown), [npm remark-gfm](https://www.npmjs.com/package/remark-gfm)) — GFM table support requires `remark-gfm` plugin; component overrides via `components` prop.
- **`@microsoft/fetch-event-source` README** ([github.com/Azure/fetch-event-source](https://github.com/Azure/fetch-event-source)) — verified API surface (POST support, retry callbacks, page-visibility integration). Last published 2021-04 per `npm view @microsoft/fetch-event-source time` — flagged as effectively unmaintained.

### Tertiary (LOW confidence — flagged in research, do not depend on)
- Recharts × React 19.2.x specific failure mode ([Issue #6857](https://github.com/recharts/recharts/issues/6857)) — issue closed but reproduction not confirmed; the `react-is` override is the most-cited workaround. Treat as defensive guidance, not a guaranteed bug.
- "Recharts charts blank on React 19" anecdotal reports — verified the version overrides workaround across multiple sources but no single authoritative fix doc exists.

## Metadata

**Confidence breakdown:**
- **Standard Stack:** HIGH — every version verified directly via `npm view` on 2026-04-26; peerDependencies inspected for compatibility.
- **Architecture Patterns:** HIGH for backend-driven patterns (SSE shape, trace entry, final_payload — sourced from production code), HIGH for the SSE consumer pattern (well-established), MEDIUM for Recharts integration (React 19 caveat).
- **Pitfalls:** HIGH for Pitfalls 1, 2, 5, 6, 7, 9, 10 (well-documented Next.js / React / SSE / project-history issues). MEDIUM for Pitfall 3 (Recharts × React 19.2.x — workaround is well-attested but the underlying root cause isn't fully explained in any single authoritative source). HIGH for Pitfalls 4, 8 (verified against Recharts docs and the surcharge-history N+1 trace from CONTEXT.md `<specifics>`).
- **Don't Hand-Roll:** HIGH — every recommendation either has a locked-by-PROJECT.md library or a clearly-superior built-in (`Intl.*`).

**Research date:** 2026-04-26
**Valid until:** ~2026-05-26 (30 days for stable tools); the Recharts × React 19 caveat may shift faster — re-check Pitfall 3 if Recharts ships a 3.9 release that addresses the `react-is` issue at the package level.
