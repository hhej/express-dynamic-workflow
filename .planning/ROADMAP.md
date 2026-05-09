# Roadmap: Express Dynamic Surcharge Orchestrator

## Milestones

- ✅ **v1.0 MVP** — Phases 1–8 (shipped 2026-05-05) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–8) — SHIPPED 2026-05-05</summary>

- [x] Phase 1: Foundation & Data Pipeline (3/3 plans) — completed 2026-04-08
- [x] Phase 2: Tools & Agent Nodes (5/5 plans) — completed 2026-04-18
- [x] Phase 3: Graph Assembly & API Layer (5/5 plans) — completed 2026-04-25
- [x] Phase 4: Frontend & Reasoning Trace (5/5 plans) — completed 2026-04-26
- [x] Phase 5: Polish, Observability & Docs (10/10 plans) — completed 2026-05-03
- [x] Phase 6: HITL Approval UI Wiring + Compile Fix (3/3 plans) — completed 2026-05-04 (gap closure)
- [x] Phase 7: Feedback Contract Alignment (3/3 plans) — completed 2026-05-04 (gap closure)
- [x] Phase 8: Search Context Wiring + Sidebar Polish (2/2 plans) — completed 2026-05-05 (gap closure)

**Delivered:** Multi-agent LangGraph orchestrator with parallel fan-out, HITL approval gate, Tavily search, full Langfuse observability, Next.js 15 chat UI with reasoning trace + dashboard. 43/43 v1 requirements satisfied. See [milestones/v1.0-MILESTONE-AUDIT.md](milestones/v1.0-MILESTONE-AUDIT.md).

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & Data Pipeline | v1.0 | 3/3 | Complete | 2026-04-08 |
| 2. Tools & Agent Nodes | v1.0 | 5/5 | Complete | 2026-04-18 |
| 3. Graph Assembly & API Layer | v1.0 | 5/5 | Complete | 2026-04-25 |
| 4. Frontend & Reasoning Trace | v1.0 | 5/5 | Complete | 2026-04-26 |
| 5. Polish, Observability & Docs | v1.0 | 10/10 | Complete | 2026-05-03 |
| 6. HITL Approval UI Wiring | v1.0 | 3/3 | Complete | 2026-05-04 |
| 7. Feedback Contract Alignment | v1.0 | 3/3 | Complete | 2026-05-04 |
| 8. Search Context + Sidebar Polish | v1.0 | 2/2 | Complete | 2026-05-05 |

## Backlog

Out-of-band items surfaced during execution (not part of the planned milestone). Resolved during v1.0:

- **999.1** — Planner state merge on follow-up turns (resolved 2026-04-25)
- **999.2** — Scope-naming mismatch "Central Region" → "Bangkok Metro" (resolved 2026-04-25)
- **999.3** — Planner trace tool_output narration mismatch (resolved 2026-04-25)
- **999.4** — D-04 loop budget windowed per turn (resolved 2026-04-25)

Full details in [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

### Open backlog

### Phase 999.5: Fix resume flow appending duplicate assistant message (BACKLOG)

**Goal:** [Captured for future planning]
**Requirements:** TBD
**Plans:** 0 plans

**Symptom:** React `Encountered two children with the same key, a-{thread_id}-{turn_idx}` warning in [MessageList.tsx](frontend/components/chat/MessageList.tsx); the logical messages array contains a duplicate of the last assistant row, which renders as a doubled answer bubble after resuming a finished conversation from the sidebar.

**Hypothesis (root cause):** After [handleResume in ChatApp.tsx](frontend/components/ChatApp.tsx) runs `setMessages(replayed)` and `lastAppendedPayloadRef.current = null`, the `done` `useEffect` re-fires — likely because `conversations.refresh` in its dependency array gets a fresh reference each render of `useConversations` — and re-appends the last turn's `chat.finalPayload` as a new assistant row. Both rows then carry the same backend-stamped `message_id` (`{thread_id}-{turn_idx}`) and React's reconciliation breaks.

**Defensive band-aid already shipped (quick task 260509-e0p):** Suffixed the React key with the array index (`key={\`a-${m.id}-${i}\`}`) so React stops crashing. The duplicate logical row still exists in `messages` — visible-symptom only fix.

**Likely real fixes (pick one during planning):**
- (a) Memoize `useConversations.refresh` with `useCallback` so it's a stable reference and the `done` effect stops re-firing.
- (b) Narrow the `done` `useEffect` deps to `[chat.finalPayload, chat.status]` only; drop `conversations.refresh` (call it but don't depend on it).
- (c) In `handleResume`, seed `lastAppendedPayloadRef.current = chat.finalPayload` (instead of `null`) so an immediate re-fire is suppressed.

**Reproduce:** Open a finished conversation from the sidebar → observe duplicate-key warning in console + duplicated last assistant bubble in DOM.

Plans:
- [ ] TBD (promote with `/gsd:review-backlog` when ready)
