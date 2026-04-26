# Phase 4: Frontend & Reasoning Trace - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 04-frontend-reasoning-trace
**Mode:** discuss
**Areas discussed:** Layout & navigation, Trace panel UX, Surcharge breakdown rendering, Dashboard + UI-05 scope

---

## Gray-area selection

| Area | Selected |
|------|----------|
| Layout & navigation | ✓ |
| Trace panel UX | ✓ |
| Surcharge breakdown rendering | ✓ |
| Dashboard + UI-05 scope | ✓ |

User chose to discuss all 4 areas.

---

## Layout & navigation

### Q1: How should the app be structured at the routing level?

| Option | Description | Selected |
|--------|-------------|----------|
| Single page, panels (Recommended) | One `/` route with sidebar + chat+trace + collapsible dashboard | ✓ |
| Multi-page (/chat, /dashboard) | Separate routes, cleaner separation but more nav clicks | |
| Hybrid | Chat + sidebar on `/`, dashboard as a top-tab inside the layout | |

### Q2: How should the conversation history sidebar (UI-06) behave by default?

| Option | Description | Selected |
|--------|-------------|----------|
| Always-visible left rail (Recommended) | Fixed on desktop, drawer on mobile, active thread highlighted | ✓ |
| Collapsible drawer | Hidden by default, hamburger toggle | |
| Top dropdown / menu | Compact but weakens 'past conversations' affordance | |

### Q3: Where should the reasoning trace panel live inside the chat view?

| Option | Description | Selected |
|--------|-------------|----------|
| Right rail, always-visible (Recommended) | Fixed right column showing live trace — maximizes Phase 3 D-17 visible-reasoning grading lever | ✓ |
| Inline under each message | Cleaner per-message context but events arrive before the answer — awkward | |
| Bottom drawer / modal | De-emphasizes the trace, weakens grading argument | |

### Q4: Where does the dashboard live in the single-page layout?

| Option | Description | Selected |
|--------|-------------|----------|
| Top-tab toggle (Recommended) | `Chat | Dashboard` toggle inside center column | ✓ |
| Modal / overlay | Full-screen modal triggered by header button | |
| Always-visible bottom panel | Pinned charts, but cramps chat | |
| Separate /dashboard route | Overrides single-page choice for dashboard only | |

### Q5: How should the 3-column layout collapse on narrow screens?

| Option | Description | Selected |
|--------|-------------|----------|
| Chat-only, drawers for sidebar+trace (Recommended) | Hamburger for sidebar, "Show reasoning" for trace, dashboard via tab | ✓ |
| Stacked vertical | Sidebar to top-bar, trace inline below messages | |
| Desktop-only | Skip mobile polish — contradicts PROJECT.md "responsive design" | |

**User's choice on continuation:** Move to next area (Trace panel UX).

---

## Trace panel UX

### Q1: How should trace entries appear during SSE streaming?

| Option | Description | Selected |
|--------|-------------|----------|
| Append live as events arrive (Recommended) | Each `trace` event renders immediately with running→complete transitions | ✓ |
| Render all-at-once after `done` | Buffer until stream closes — loses live-thinking effect | |
| Live-append with skeleton placeholders | 5 grey rows pre-rendered, but assumes fixed flow — breaks for clarify/error | |

### Q2: What level of detail per trace step by default?

| Option | Description | Selected |
|--------|-------------|----------|
| Headline + expandable detail (Recommended) | Agent name + summary collapsed; click to expand tool I/O + reasoning | ✓ |
| Headline only | Detail in separate inspect modal — hides reasoning text | |
| Full detail always | Wall of text, bad UX | |

### Q3: What does the trace panel show when the user clicks an older message?

| Option | Description | Selected |
|--------|-------------|----------|
| Trace of currently-streaming or last-completed turn (Recommended) | Tracks current activity; past traces NOT swappable — D-21 doesn't carry per-turn trace | ✓ |
| Per-message trace, click message to switch | Requires backend D-21 extension | |
| Latest only, no history | Trace clears between turns | |

### Q4: What does the trace panel show before the user sends their first message?

| Option | Description | Selected |
|--------|-------------|----------|
| Explainer + example queries (Recommended) | Short explainer plus 2-3 clickable example prompts | ✓ |
| Diagram of the agent graph | Static Mermaid-style image — not interactive | |
| Empty / placeholder text only | Wastes demo real estate | |

**User's choice on continuation:** Move to next area (Surcharge breakdown rendering).

---

## Surcharge breakdown rendering

### Q1: How should the assistant's response render in chat?

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown verbatim via react-markdown (Recommended) | Render `answer.payload.markdown` directly; backend stays source of truth | ✓ |
| Structured: parse surcharge_result, custom React table | Maximum styling control but duplicates backend table logic | |
| Hybrid: markdown for prose, custom React for breakdown | Two render paths, more code | |

### Q2: How should the capped/floor warning render?

| Option | Description | Selected |
|--------|-------------|----------|
| Yellow callout banner above the table (Recommended) | Tailwind yellow-50 banner + warning icon, more prominent than blockquote | ✓ |
| Inline blockquote (default markdown rendering) | Less prominent, zero extra code | |
| Toast / non-blocking snackbar | Transient — user might miss the caveat | |

### Q3: How should non-`ok` statuses render?

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct visual treatments (Recommended) | ok=normal; clarify=blue card; partial=orange card + 'limited result' label | ✓ |
| Same chrome, status badge only | Simpler but less expressive | |
| Hide table when not `ok` | Avoids partial-data confusion but discards real signal | |

**User's choice on continuation:** Move to next area (Dashboard + UI-05 scope).

---

## Dashboard + UI-05 scope

### Q1: UI-04 wants 'surcharge history' but no /api/surcharge-history endpoint exists — how to source it?

| Option | Description | Selected |
|--------|-------------|----------|
| Derive client-side from /api/conversations (Recommended) | Walk threads, extract surcharge_result; no backend changes | ✓ |
| Add a new backend endpoint | Expands Phase 4 scope into backend territory | |
| Drop 'surcharge history' from dashboard | Fuel trends only — UI-04 partial | |
| Mock data for demo | Hardcoded — weakens the live-product framing | |

### Q2: Which chart(s) should the dashboard ship in Phase 4? *(multiSelect)*

| Option | Description | Selected |
|--------|-------------|----------|
| Fuel price line chart (Recommended) | From /api/fuel-prices?days=N (D-20) | ✓ |
| Surcharge history bar/line chart (Recommended if surcharge history is sourced) | Derived from conversations | ✓ |
| Surcharge breakdown by shipping type | Bar chart grouping by bounce/retail_*; rejected to keep scope tight | |
| Zone heat-map / volume | Stretch goal; rejected | |

### Q3: API-05 (feedback) is Phase 5, but UI-05 (feedback buttons) is in Phase 4 traceability. What's the right call?

| Option | Description | Selected |
|--------|-------------|----------|
| Stub UI: render buttons, log click locally only (Recommended) | Visual UX in Phase 4; Phase 5 swaps the handler to /api/feedback | ✓ |
| Defer UI-05 entirely to Phase 5 | Cleanest but reduces Phase 4 demo richness | |
| Build full UI + 501 placeholder API | Contradicts the API-05-is-Phase-5 boundary | |

### Q4: What time range should the fuel price chart support?

| Option | Description | Selected |
|--------|-------------|----------|
| Toggle 7d / 30d / 90d (Recommended) | Three preset buttons, default 30d | ✓ |
| Single range (30d only) | Hides the days param the backend already supports | |
| Toggle 7d / 30d / 90d / 365d | Year option for long-trend reasoning; slightly busier UI | |

**User's choice on continuation (final):** "I'm ready for context" — proceed to write CONTEXT.md.

---

## Claude's Discretion

User did not explicitly defer any decision to Claude during this discussion (every gray area surfaced got a direct answer). The areas left to Claude during planning are listed in CONTEXT.md `<decisions>` § Claude's Discretion: SSE client implementation choice, state-management library, markdown lib, component file split, TS type generation, Tailwind theme tokens beyond the locked yellow callout, scaffold mechanics, currency formatters, loading skeletons, error boundaries, accessibility scope, and the optional "Show JSON" debug affordance.

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section:
- Past-turn trace inspection (Phase 5 — needs D-21 extension or Langfuse coverage)
- Backend `/api/surcharge-history` endpoint (Phase 5 if scale demands)
- POST /api/feedback wire-up (Phase 5 — API-05)
- Surcharge breakdown by shipping type chart (v2)
- Zone heat-map / volume chart (v2)
- Token-level SSE streaming (out of scope)
- OpenAPI-generated TS types (revisit at v2)
- Authentication / multi-user (out of scope)
- Mobile-native polish beyond responsive (out of scope)
- Theme toggle, i18n, conversation deletion (Phase 5+ or v2)
