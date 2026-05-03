---
phase: 05-polish-observability-docs
plan: 04
subsystem: agent
tags: [tavily, search, langgraph, planner, response-node, ttl-cache]

requires:
  - phase: 05-polish-observability-docs/01
    provides: SearchInput / SearchSource / SearchResult Pydantic models, search_context AgentState field, TAVILY_API_KEY + SEARCH_CACHE_TTL_SECONDS config
  - phase: 05-polish-observability-docs/03
    provides: planner sentinel pattern + cache-aware override block (Phase 5 search routing extends both)
provides:
  - backend/agent/tools/search_fuel_news.py — Tavily-backed news search with TTL cache (D-12)
  - backend/agent/nodes/search_agent.py — graceful-warn node mirroring fuel_agent shape
  - backend/agent/prompts/search_agent.py — Bangkok Metro phrasing + no-fabricate-numbers contract
  - Planner SYSTEM_PROMPT unlocks search_context emission for news/trend intent (D-09)
  - Graph wires search_agent between planner and response_node
  - Response node prepends "Market context: <summary>" blockquote when present (D-11)
affects: [05-06-feedback-frontend, 05-07-docs-tag]

tech-stack:
  added: []  # tavily-python pinned in 05-01; search_agent + planner integration only
  patterns:
    - "Lazy SDK import: TavilyClient constructed inside _client() not at module load (D-16)"
    - "Cache-aware override bypass: next_step=search_context skips D-12 fuel/route freshness override so news queries don't depend on cache state"
    - "Graceful warn pattern reuses Phase 2 fuel_agent shape: search_fuel_news raises RuntimeError → search_agent catches → trace status=warn → search_context stays None → planner unblocked"
    - "Snippet hard-ceiling 240 chars (Pitfall 2: Langfuse trace bloat from raw Tavily content)"

key-files:
  created:
    - backend/agent/tools/search_fuel_news.py
    - backend/agent/nodes/search_agent.py
    - backend/agent/prompts/search_agent.py
    - backend/tests/test_search_fuel_news.py
    - backend/tests/test_search_agent.py
  modified:
    - backend/agent/graph.py
    - backend/agent/nodes/planner.py
    - backend/agent/prompts/planner.py
    - backend/agent/nodes/response_node.py
    - backend/tests/test_planner.py
    - backend/tests/test_response_node.py

key-decisions:
  - "search_fuel_news raises RuntimeError on missing TAVILY_API_KEY rather than silent no-op — search_agent_node catches and converts to warn-status trace; explicit raise gives users a clear log signal when keys are missing"
  - "TTLCache reused from Phase 2 _cache.py module — same shape as route cache, single normalized-query cache key (lowercase + collapsed whitespace) per Pitfall 3"
  - "Planner cache-aware override block early-returns when next_step=='search_context' — search routes do not depend on fuel/route freshness, so the override would incorrectly demote a news query to fetch_fuel"
  - "Response node prepends Market context as a markdown blockquote (\"> Market context: ...\") above any other content — matches the existing CapCallout/MarkdownAnswer rendering pipeline (D-11)"
  - "Empty/None summary treated as no-prefix — avoids rendering an empty Market context line when Tavily returns no answer"
  - "Default fallback query 'Thailand diesel fuel price news' when no user message is present — keeps search_agent invocable in tests/edge cases without crashing"

requirements-completed:
  - TOOL-05

duration: ~30 min (executor stalled mid-task; orchestrator finished commits + SUMMARY)
completed: 2026-05-03
---

# Phase 5 Plan 04: Search Agent Summary

**TOOL-05 search agent: Tavily-backed news search with TTL cache, graceful-warn node, planner news-intent routing, and Market-context markdown prefix**

## Performance

- **Duration:** ~30 min agent + ~10 min orchestrator wrap-up
- **Tasks:** 3
- **Files modified:** 11 (5 new, 6 modified)

## Accomplishments
- Tavily-backed `search_fuel_news` tool with normalized-query TTL cache (D-12) and 240-char snippet ceiling
- `search_agent_node` mirrors `fuel_agent` shape — D-11 LLM-or-deterministic narration fallback, D-12 graceful warn on RuntimeError
- Planner SYSTEM_PROMPT unlocks `search_context` emission for news/market/trend intent (D-09)
- Cache-aware override block early-returns for `search_context` — news queries are not gated on fuel/route freshness
- Graph topology: planner → search_agent → response_node
- Response node prepends `> Market context: <summary>` blockquote when `state.search_context.summary` is present (D-11)
- Backend test suite green: 152/152 passing (was 132 before Wave 3)

## Task Commits

1. **Task 1: search_fuel_news tool** — `438ada5` (feat)
2. **Task 2: search_agent node + prompt** — `0cb8dbc` (feat)
3. **Task 3: graph + planner + response wiring** — `5327fbc` (feat)

_Note: Atomic-per-task commits but not strict TDD red/green pairs — original executor agent stalled before committing; orchestrator inspected the WIP, fixed one test typo, ran the full suite green, then committed the work in task-aligned chunks._

## Files Created/Modified
- `backend/agent/tools/search_fuel_news.py` (new) — Tavily wrapper + TTLCache + normalized-query cache key
- `backend/agent/nodes/search_agent.py` (new) — graceful-warn node with D-11 LLM-or-deterministic narration
- `backend/agent/prompts/search_agent.py` (new) — Bangkok Metro phrasing, no-fabricate-numbers contract
- `backend/agent/graph.py` — registered search_agent node, `_route_from_planner` routes `search_context` → `search_agent`
- `backend/agent/nodes/planner.py` — cache-aware override block bypassed for `search_context` (D-09)
- `backend/agent/prompts/planner.py` — SYSTEM_PROMPT unlocks `search_context` emission for news/trend intent
- `backend/agent/nodes/response_node.py` — prepends `> Market context: <summary>` blockquote when search_context.summary present
- `backend/tests/test_search_fuel_news.py` (new) — 6 tests
- `backend/tests/test_search_agent.py` (new) — 6 tests
- `backend/tests/test_planner.py` — 2 new tests for news-intent routing
- `backend/tests/test_response_node.py` — 3 new tests for Market context prefix variants

## Decisions Made

See frontmatter `key-decisions`. Notable:
- search_fuel_news raises RuntimeError on missing key (not silent no-op) — search_agent_node converts to warn trace
- Cache-aware override bypass for search_context — news queries shouldn't be gated on fuel/route freshness
- Empty/None summary treated as no-prefix — avoids rendering an empty Market context line

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test typo] test_search_fuel_news_normalizes_query**
- **Found during:** Orchestrator wrap-up (post-stall test run)
- **Issue:** Test queries differed by trailing "?" ("today?" vs "today") in addition to case+whitespace — implementation correctly normalized case+whitespace but not punctuation, so the two queries hashed to different cache keys and `assert a is b` failed
- **Fix:** Removed the trailing "?" from the first query so both queries differ only in case+whitespace (the dimensions the test name claims to verify)
- **Files modified:** `backend/tests/test_search_fuel_news.py`
- **Verification:** Full backend suite (152/152) passes
- **Committed in:** `438ada5` (Task 1 commit)

**2. [Rule 4 - Process] Executor agent stalled before committing or writing SUMMARY**
- **Found during:** Wave 3 execution
- **Issue:** Background gsd-executor agent for 05-04 stalled (no progress 600s) after writing all task files but BEFORE making any atomic commits, updating STATE/ROADMAP, or writing SUMMARY.md
- **Fix:** Orchestrator (parent) inspected the WIP working tree, ran the full backend suite, fixed the single test failure (deviation #1), then committed the work in 3 task-aligned chunks (one commit per Task per the plan structure) and authored this SUMMARY.md inline
- **Files modified:** N/A (process deviation; the underlying code work was complete)
- **Verification:** All commits visible in `git log`, full suite green, all expected files present on disk
- **Note:** This breaks the strict TDD red/green commit pairing the plan called for, but preserves task-atomic granularity and produces an honest SUMMARY documenting the deviation

---

**Total deviations:** 2 auto-fixed (1 test typo, 1 process deviation from agent stall)
**Impact on plan:** No scope creep — all plan tasks delivered as specified. Process deviation cost the strict red/green TDD commit pattern; behavioral correctness (152/152 tests) is unaffected.

## Issues Encountered

- Background agent stall (no progress 600s) — see deviation #2. The user paused the session token-conservation; on resume, the orchestrator chose inline finish over spawning a fresh agent to avoid duplicating already-done work.

## Next Phase Readiness

- Wave 4 (Plan 05-05 HITL gate) can land — it touches `pricing_agent`, `response_node`, `chat.py`, none of which are now write-conflicted with 05-04
- Wave 5 (Plan 05-06 feedback API + frontend) gets the `search_context` field on the SSE final payload for free — frontend `SearchContextLine` component can render the same `> Market context:` line that response_node now produces
- TOOL-05 requirement closed; all 4 Phase 5 differentiator requirements (ORCH-07, ORCH-09, TOOL-05, OBS-*) now have either complete or in-progress plans

---
*Phase: 05-polish-observability-docs*
*Completed: 2026-05-03*
