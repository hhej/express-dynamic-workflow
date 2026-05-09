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
- **999.6** — Fix EPPO fuel-price scraper after URL restructure (resolved 2026-05-09) — see [debug/resolved/fix-eppo-scraper-url-restructure.md](debug/resolved/fix-eppo-scraper-url-restructure.md)

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

### Phase 999.7: Backfill daily fuel-price history so 90d dashboard window stays populated (BACKLOG)

**Goal:** [Captured for future planning]
**Requirements:** TBD
**Plans:** 0 plans
**Captured:** 2026-05-09 (follow-up to 999.6 EPPO scraper fix)

**Symptom:** After 999.6 fix landed, `/api/fuel-prices?days=7` and `?days=30` return only 1 row each (today's snapshot). The dashboard window contract is "rolling 90 days of daily prices", but right now:
- 2025-10 → 2026-04-03 has daily seed data (load-bearing history)
- 2026-04-04 → 2026-05-08 is a 35-day gap (no daily data — EPPO restructure happened during this window)
- 2026-05-09 onward will accumulate one daily row per cold-start (forward-only)

As the rolling 90d window advances, seed data falls out the back AND the gap stays unfilled, so the 90d view degrades over time. By ~2026-08-07 the entire seed will be out of window and only forward-collected days will show.

**Investigation needed:**
- (a) Does any public EPPO surface expose ≥90 days of daily diesel B7 retail prices? P09.xls is monthly-aggregated (WT.AVG by month); oil-share PHP page is today-only. Check for archived daily snapshots, JSON API endpoints, or downloadable per-day datasets.
- (b) PTT Price Board — does it expose historical daily prices via API or scrape-able archive? Documented in CLAUDE.md as backup source.
- (c) Wayback Machine snapshots of the old EPPO oil-share URL between 2026-04-04 and 2026-05-08 (one-shot gap fill via archive.org Memento API).
- (d) BangchakOilPrice / other Thai retailer APIs as parallel daily sources.
- (e) Scope decision: is "90d rolling daily" the actual UX requirement, or is "monthly aggregates + today's snapshot" acceptable for the demo? If the latter, this becomes a frontend chart change, not a data-pipeline change.

**Out of scope:**
- Fabricating synthetic data to fill the gap (CLAUDE.md: at least one real dataset must be queried).
- Changing the cold-start hook contract or staleness predicate (works as designed).
- Touching the 999.6 URL-restructure fix (separate concern, already shipped).

**Verify after fix:**
- `/api/fuel-prices?days=7` returns ≥5 rows (allowing weekend gaps in market data).
- `/api/fuel-prices?days=30` returns ≥20 rows.
- `/api/fuel-prices?days=90` returns ≥60 rows AND continues to do so as the rolling window advances past the seed CSV cutoff.

Plans:
- [ ] TBD (start with `/gsd:debug` to investigate data-source options before committing to an approach)

