# Phase 4: Frontend & Reasoning Trace - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the Next.js 15 + React 19 + Tailwind frontend that consumes the existing FastAPI backend (Phase 3) and renders the surcharge agent as a chat product with visible, live reasoning. Frontend dir is greenfield (only `.gitkeep`).

End state: a user opens the app, sees a conversation sidebar (left), the chat + breakdown surface (center), and a live reasoning trace panel (right). Sending a message streams `meta → trace* → answer → done` SSE events from `POST /api/chat`; trace entries append in real time, the final response renders as markdown with a structured breakdown table, and a `Chat | Dashboard` tab swap reveals fuel-price + surcharge-history charts. Conversations resume via the sidebar (D-21).

**In scope (this phase):** UI-01 (chat + SSE display), UI-02 (live reasoning trace panel), UI-03 (surcharge breakdown table), UI-04 (fuel-price + surcharge-history charts), UI-05 (feedback button **UI stub** — local-only, no backend wire), UI-06 (conversation history sidebar).

**Out of scope (Phase 5):** API-05 (POST /api/feedback wire), past-turn trace inspection (would require D-21 extension), backend `/api/surcharge-history` endpoint (Phase 4 derives client-side instead), Langfuse OBS-01..03, ORCH-07 parallel agents, ORCH-09 HITL gate, TOOL-05 search.

**Out of scope (deferred entirely):** authentication, mobile native app, token-level SSE streaming.

</domain>

<decisions>
## Implementation Decisions

### Layout & navigation
- **D-01:** Single-page Next.js app with a three-column layout — conversation sidebar (left) | chat + breakdown (center) | reasoning trace panel (right). One `/` route is the entire product.
- **D-02:** Conversation history sidebar (UI-06) is an always-visible left rail on desktop. Active thread highlighted; click resumes via `GET /api/conversations/:id` + thread_id reuse on next `POST /api/chat`.
- **D-03:** Reasoning trace panel (UI-02) is an always-visible right rail on desktop. Visible reasoning is the explicit grading lever (Phase 3 D-17 / PROJECT.md Core Value), so always-on maximizes the rubric.
- **D-04:** Dashboard (UI-04) lives behind a `Chat | Dashboard` top-tab toggle inside the center column. No separate `/dashboard` route — sidebar and trace panel stay in place when toggling.
- **D-05:** Mobile breakpoint (<768px) collapses to chat-only with a hamburger drawer for the sidebar (left) and a "Show reasoning" drawer for the trace panel (right). Dashboard tab still available in the top toggle.

### Reasoning trace panel (UI-02)
- **D-06:** Trace entries append live as `trace`-typed SSE events arrive. Each new step renders immediately with a `running` state; the next event resolves it to `ok | warn | error` (Phase 2 D-12 trace schema). No batching — the live-thinking effect is the agentic differentiator.
- **D-07:** Each step shows headline only by default — agent name + one-line summary + status badge — collapsed. Click to expand tool inputs, tool outputs, reasoning prose, and `fetched_at` (Phase 3 D-13). Scannable list, inspectable on demand.
- **D-08:** Trace panel shows the currently-streaming or last-completed turn only. Clicking an older message in chat does NOT swap the trace — past-turn trace is **deferred** (would require backend D-21 extension to persist per-turn `reasoning_trace`).
- **D-09:** Empty state (before first message) shows a short explainer plus 2–3 clickable example prompts (e.g., *"Surcharge for 15kg Bounce, Bangkok → Nonthaburi"*, *"What about Retail Fast?"*). Onboarding + demo seed.

### Chat + surcharge breakdown rendering (UI-01, UI-03)
- **D-10:** Render `answer.payload.markdown` (Phase 3 D-10 / D-11) verbatim via `react-markdown` + `remark-gfm` for table support. Backend remains the source of truth for prose and the 4-row breakdown structure; FE doesn't reconstruct the table from `surcharge_result`.
- **D-11:** When `answer.payload.capped === true`, render a Tailwind yellow-50 callout banner (warning icon + "Cap/floor applied — review recommended") **above** the markdown breakdown. Either strip the leading `> ⚠ Cap/floor applied — review recommended` line from the markdown before passing it to react-markdown, or override the `blockquote` component when capped is true. Planner picks the cleaner of the two.
- **D-12:** Distinct visual treatments per `answer.payload.status`:
  - `ok` → normal markdown render (prose + breakdown table)
  - `clarify` → blue info card containing the clarification question; no breakdown table
  - `partial` → orange card containing whatever data was gathered + "limited result" label; show breakdown if `surcharge_result` is non-null, otherwise just the prose
- **D-13:** Surcharge breakdown is the markdown table from D-10. Frontend does NOT separately render `answer.payload.surcharge_result` as JSON in the chat surface; that structured object is reserved for **Dashboard** consumption (D-15) where typed access matters.

### Conversation sidebar (UI-06)
- **D-14:** Sidebar lists threads from `GET /api/conversations` (Phase 3 D-21): `{thread_id, last_updated, first_message_preview}`. Clicking a thread loads `GET /api/conversations/:id`, replays messages into the chat surface, and persists `thread_id` to localStorage so the next `POST /api/chat` continues that thread (Phase 3 D-19). "New conversation" button at top clears thread_id; backend assigns a fresh UUID via `meta` event.

### Dashboard (UI-04)
- **D-15:** Dashboard ships **two charts** in Phase 4:
  1. **Fuel price line chart** — `GET /api/fuel-prices?days=N` (Phase 3 D-20). Range toggle: `7d | 30d | 90d`, default `30d`.
  2. **Surcharge history bar/line chart** — derived **client-side** from `GET /api/conversations` + per-thread `GET /api/conversations/:id`. Walk the last ~20 threads, extract `final_payload.surcharge_result` (when present), plot total/surcharge_pct over `last_updated`. NO new backend endpoint in Phase 4.
- **D-16:** Surcharge breakdown by shipping type (bar) and zone heat-map were considered and **rejected** from Phase 4 charts to keep dashboard scope tight. May surface as v2.

### Feedback UI (UI-05) — stub-only in Phase 4
- **D-17:** UI-05 thumbs up/down buttons render on each assistant message with **local-only** state. Click captures `{thread_id, message_id, score, reason?}` to console + `localStorage` (debug aid) and shows a "voted" visual state. NO `POST /api/feedback` call — API-05 is Phase 5 (alongside Langfuse Score API). Phase 5 swaps the local handler to the real API call without other UI changes.
- **D-18:** REQUIREMENTS.md UI-05 traceability stays mapped to Phase 4 (the buttons ship in Phase 4); Phase 5 owns the wire-up. Phase 4 verification accepts the stub as UI-05 complete.

### SSE consumption
- **D-19:** Native `fetch()` + `ReadableStream` reader to consume `POST /api/chat` SSE (EventSource is GET-only). The reader parses `data: {...}\n\n` frames and dispatches by `payload.type`:
  - `meta` → store `thread_id` to localStorage, render in sidebar as the active thread
  - `trace` → append to live trace panel (D-06)
  - `answer` → render in chat surface with D-10/D-11/D-12 treatments
  - `error` → toast + render error card; trace panel preserves what arrived before the error
  - `done` → close the reader; flip chat input back to enabled
- **D-20:** `thread_id` lifecycle: read from `localStorage` on app boot; sent on `POST /api/chat` body when present, omitted on "New conversation". Server's first `meta` event is the authoritative source — overwrite localStorage with whatever the server returns. If a stored thread_id is unknown to the backend, the server emits a fresh UUID in `meta` and the client follows.

### Claude's Discretion
- SSE client implementation: hand-rolled `fetch` + `ReadableStream` (D-19) vs a small lib (e.g., `@microsoft/fetch-event-source`). Either is acceptable as long as the 5 event types route correctly.
- State management library: React state + custom hooks (`useChatStream`, `useConversations`, `useFuelPrices`) vs TanStack Query (good for the non-streaming GETs) vs Zustand. Streaming chat is naturally a `useReducer`; the GETs benefit from query caching.
- Markdown lib choice: `react-markdown` + `remark-gfm` is the default for the GFM table; planner may swap to a smaller renderer if the locked D-11 structure (prose + 4-row table + footer) can be covered without GFM.
- Component file split: feature folders (`components/chat/`, `components/trace/`, `components/dashboard/`, `components/sidebar/`) vs flat `components/` per CONVENTIONS.md. Both fit the documented PascalCase.tsx + camelCase.ts conventions.
- TypeScript types: hand-write TS interfaces mirroring `backend/api/models.py` vs generate from FastAPI's OpenAPI schema. Hand-written is fine for v1; the surface is small.
- Tailwind theme tokens beyond the locked yellow-50 callout (D-11) — colors, spacing, font scale are open. Recharts default palette is acceptable.
- Project scaffold mechanics: `create-next-app` (App Router, TS, Tailwind, ESLint preset) vs hand-built. The output must match the `frontend/app + components + hooks + lib + types` layout from CONVENTIONS.md.
- Currency formatting helper (THB symbol placement, decimal precision) in `frontend/lib/formatters.ts`.
- Loading skeletons for the streaming chat input, dashboard charts (no data yet), and sidebar (empty list).
- Error boundaries around the trace panel and dashboard charts so a single render failure doesn't blank the whole app.
- Accessibility: keyboard navigation for trace expand/collapse, focus management for the mobile drawers, ARIA labels on the chart toggles. Phase 4 should hit "reasonable a11y" without being a full audit.
- Whether to render `surcharge_result` as a "Show JSON" debug affordance under the breakdown table for inspection.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & API contract
- `docs/architecture.md` — System overview diagram (Frontend ↔ FastAPI), Conditional Routing table, Memory Management, Error Handling sections
- `docs/architecture.md` §Conditional Routing — next_step vocabulary maps to trace step labels (D-07)

### Phase 3 inputs (what Phase 4 consumes)
- `.planning/phases/03-graph-assembly-api-layer/03-CONTEXT.md` — Phase 3 locked decisions, especially:
  - **D-10** Response payload shape `{markdown, surcharge_result, capped, status}` — drives D-10/D-11/D-12/D-13/D-15 above
  - **D-11** Markdown structure (locked) — prose + 4-row table + cap callout — drives D-10/D-11
  - **D-12** Cache-aware planner reuse on follow-ups — drives the demo story behind D-09 example prompts
  - **D-17** SSE event granularity (one event per node completion via `astream_events`) — drives D-06 live append
  - **D-18** Typed SSE envelope `{type, payload}` with `meta | trace | answer | error | done` — drives D-19 dispatch
  - **D-19** thread_id flow + first `meta` event — drives D-14 sidebar wiring + D-20 lifecycle
  - **D-20** `/api/fuel-prices?days=N` returns `[{date, price, unit, source}]` — drives D-15 fuel chart
  - **D-21** `/api/conversations` list + `/:id` replay — drives D-14 sidebar + D-15 surcharge-history derivation
- `backend/api/routes/chat.py` — production SSE handler (5 event types)
- `backend/api/routes/conversations.py` — sidebar + surcharge-history derivation source
- `backend/api/routes/fuel_prices.py` — fuel chart source
- `backend/api/models.py` — Pydantic request/response models; TS types should mirror these names and field types
- `backend/agent/state.py` — `AgentState` including `reasoning_trace`, `surcharge_result`, `final_payload` shape used by SSE events

### Requirements & project framing
- `.planning/REQUIREMENTS.md` — UI-01..UI-06 (Phase 4 scope), UI-05 ↔ API-05 split note (D-17/D-18 above)
- `.planning/PROJECT.md` — Tech stack lock (Next.js 15 + React 19 + Tailwind + Recharts), grading rubric (Agent Architecture 35%, Documentation/Git 20%), Core Value ("visible reasoning is what makes this agentic")
- `.planning/ROADMAP.md` §Phase 4 — success criteria 1–5 (chat streaming, trace panel, breakdown table, dashboard, sidebar resume)

### Coding conventions
- `.planning/codebase/CONVENTIONS.md` §TypeScript — file naming (PascalCase.tsx components, useX.ts hooks, camelCase.ts utilities, *.types.ts types), Prettier + ESLint, path aliases (`@/components`, `@/lib`, `@/types`), import organization, JSDoc on public APIs
- `.planning/codebase/STRUCTURE.md` §Frontend — `frontend/app/`, `components/`, `hooks/`, `lib/`, `types/` layout
- `.planning/codebase/STACK.md` — Tailwind, Recharts, Node 18+, npm

### Backlog (informs phrasing only)
- ROADMAP.md §Backlog 999.2 — product scope is "Bangkok Metro" in user-facing copy (resolved 2026-04-25). Frontend copy must say Bangkok Metro, NOT Central Region; internal zone IDs `central-1/2/3` stay as-is per the backlog decision.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **None on the frontend** — `frontend/` directory is empty (only `.gitkeep`). Phase 4 establishes all frontend conventions, scaffolding, and components from scratch.
- **All backend endpoints live and tested** (Phase 3, 103 backend tests passing):
  - `POST /api/chat` — SSE stream with `meta | trace | answer | error | done` envelope (D-18)
  - `GET /api/conversations` — list of threads with preview (D-21)
  - `GET /api/conversations/:id` — message history + final surcharge_result for replay (D-21)
  - `GET /api/fuel-prices?days=N` — JSON array `[{date, price, unit, source}]`, capped 1≤N≤365 (D-20)
- **Pydantic response models** in `backend/api/models.py` are the canonical TS-type source. Hand-mirror or generate from OpenAPI.

### Established Patterns
- **Backend conventions** (PEP 8, Black, Google docstrings, TypedDict + Pydantic) are settled — Phase 4 establishes the **TypeScript equivalent** (Prettier + ESLint @next/next + React, JSDoc, PascalCase.tsx, camelCase.ts, `@/` path aliases).
- **SSE framing** — backend uses raw `StreamingResponse` + manual `data: ...\n\n` formatting (Phase 3 D-04 plan note); FE consumer must split on `\n\n` and parse each `data:` line as JSON.
- **No EventSource** — backend chat is POST-only, so FE uses `fetch` + `ReadableStream` (D-19) or an SSE lib that supports POST.
- **ISO-8601 UTC `Z` timestamps** in `fetched_at` and `last_updated` — FE should render relative ("2 min ago") with absolute on hover.
- **Bangkok Metro phrasing** (per resolved backlog 999.2) — all user-facing copy says "Bangkok Metro", never "Central Region".

### Integration Points
- `frontend/app/page.tsx` (new) — single-route layout (D-01), composes Sidebar + ChatColumn + TracePanel
- `frontend/app/layout.tsx` (new) — root layout, fonts, Tailwind globals, theme providers
- `frontend/components/chat/ChatColumn.tsx` (new) — center column, hosts the `Chat | Dashboard` tab toggle (D-04), the message list, the input
- `frontend/components/chat/MessageList.tsx` (new) — renders user and assistant messages; assistant messages dispatch on D-12 status to render `MarkdownAnswer` / `ClarifyCard` / `PartialCard`
- `frontend/components/chat/MarkdownAnswer.tsx` (new) — react-markdown + remark-gfm + D-11 capped banner override
- `frontend/components/chat/FeedbackButtons.tsx` (new) — UI-05 stub (D-17), local state only
- `frontend/components/trace/TracePanel.tsx` (new) — right rail (D-03), live-append (D-06), empty-state explainer + example prompts (D-09)
- `frontend/components/trace/TraceStep.tsx` (new) — headline + collapsible detail (D-07)
- `frontend/components/sidebar/ConversationSidebar.tsx` (new) — UI-06 left rail (D-02), thread list + "New conversation" + active highlight (D-14)
- `frontend/components/dashboard/DashboardView.tsx` (new) — D-04 tab content
- `frontend/components/dashboard/FuelPriceChart.tsx` (new) — Recharts line chart with `7d | 30d | 90d` toggle (D-15.1, D-16-toggle)
- `frontend/components/dashboard/SurchargeHistoryChart.tsx` (new) — Recharts bar/line chart from client-side derivation (D-15.2)
- `frontend/hooks/useChatStream.ts` (new) — fetch + ReadableStream SSE consumer (D-19), useReducer for `meta/trace/answer/error/done` events
- `frontend/hooks/useConversations.ts` (new) — list + load thread; powers sidebar (D-14) and surcharge-history derivation (D-15.2)
- `frontend/hooks/useFuelPrices.ts` (new) — `GET /api/fuel-prices?days=N` with the D-15.1 range toggle
- `frontend/lib/api.ts` (new) — fetch wrappers for the four endpoints; throws typed `ApiError`
- `frontend/lib/sse.ts` (new) — generic `parseSseStream(reader, onEvent)` helper backing `useChatStream`
- `frontend/lib/formatters.ts` (new) — THB currency, percentage, relative-time formatters
- `frontend/types/api.types.ts` (new) — TS interfaces mirroring `backend/api/models.py`
- `frontend/types/agent.types.ts` (new) — TS interfaces for `TraceEntry`, `SurchargeResult`, the 5 SSE event payloads
- `frontend/package.json` (new) — Next.js 15, React 19, Tailwind, Recharts, react-markdown, remark-gfm
- `frontend/tsconfig.json` (new) — `@/*` path aliases per CONVENTIONS.md
- `frontend/tailwind.config.ts` (new) — content paths, theme tokens (yellow-50 callout palette anchor)
- `frontend/.eslintrc.json` (new) — `@next/next` + React preset
- `frontend/.prettierrc` (new) — repo-consistent formatting
- `.env.example` — add `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` (read by `frontend/lib/api.ts`)

</code_context>

<specifics>
## Specific Ideas

- **"Visible reasoning is what makes this agentic"** (PROJECT.md Core Value) is the explicit grading lever (35% Agent Architecture). Every Phase 4 decision that maximizes trace visibility — D-03 always-visible right rail, D-06 live append, D-07 headline + expandable, D-09 explainer + examples — targets that rubric. Do not regress these in pursuit of UX minimalism.
- **Cache-reuse demo** (Phase 3 D-12) — a follow-up like *"What about Retail Fast?"* on the same `thread_id` keeps fuel/route from re-fetching. Phase 4 should foreground this: include such a follow-up in the D-09 example prompts and let the trace panel visibly show planner skipping `fetch_fuel`/`fetch_route`. This is the "memory + reasoning" moment for a demo.
- **Markdown is locked, prose is not** (Phase 3 D-11 vs Response Node Discretion). react-markdown + remark-gfm gracefully renders whatever prose tone the Response Node Gemini call returns, while the 4-row table stays predictable.
- **Bangkok Metro phrasing** (resolved backlog 999.2): all FE copy, example prompts, error messages, and dashboard labels say "Bangkok Metro". Never "Central Region". Internal zone IDs `central-1/2/3` are not user-facing — they appear only in trace step `tool_input/tool_output` JSON.
- **Custom-styled capped callout (D-11)** intentionally diverges from the backend's `> ⚠` blockquote markdown line. The backend keeps the line for terminal/log rendering parity; the FE upgrades it to a yellow banner. Both representations stay in sync because the FE either strips the line or overrides the blockquote — never invents the warning from `capped` alone (so a future schema change to `capped` flips both surfaces in lockstep).
- **Surcharge-history derivation cost** (D-15.2): walking 20 threads = 20 `GET /api/conversations/:id` calls. SQLite + AsyncSqliteSaver makes this fast locally; it would NOT scale to a production deploy. If this becomes painful even in dev, escalate to a Phase 5 backend endpoint rather than caching tricks.

</specifics>

<deferred>
## Deferred Ideas

- **Past-turn trace inspection** (D-08 limitation) — would require backend D-21 extension to persist `reasoning_trace` per turn so `GET /api/conversations/:id` returns it. **Phase 5** candidate alongside Langfuse integration (OBS-01..03), since Langfuse spans cover much of this need externally.
- **Backend `/api/surcharge-history` endpoint** — D-15.2 derives client-side; if performance or scale demands it later, a dedicated endpoint querying the checkpointer is the natural Phase 5 addition.
- **POST /api/feedback wire-up** — UI-05 stub buttons (D-17) wait for API-05 (Phase 5). Phase 5 also forwards scores to Langfuse Score API (OBS-02).
- **Surcharge breakdown by shipping type chart** — considered and dropped from Phase 4 dashboard scope (D-16). Possible v2.
- **Zone heat-map / volume chart** — considered and dropped (D-16). Possible v2.
- **Token-level streaming for the final markdown** — alternative to Phase 3 D-17's node-completion granularity. Out of scope; trace-level granularity is already the differentiator.
- **OpenAPI-generated TS types** — hand-written types are fine for v1's small surface. Worth revisiting if API-05 (Phase 5) plus future endpoints push the surface past ~10 endpoints.
- **Authentication / multi-user** — Out of scope (PROJECT.md). All thread_ids are opaque UUIDs; security via obscurity is acceptable for the course demo.
- **Mobile-native polish beyond responsive breakpoints** — D-05 covers the responsive collapse. Native app is explicitly Out of Scope (PROJECT.md).
- **Theme toggle (light/dark)** — Phase 4 ships one default theme; theme toggle is a Phase 5+ stretch.
- **Internationalization** — single-language (English) for the demo. Thai locale is a future possibility.
- **Conversation deletion / archive** — read-only sidebar in Phase 4 (Phase 3 already noted this is out of scope for v1).

</deferred>

---

*Phase: 04-frontend-reasoning-trace*
*Context gathered: 2026-04-25*
