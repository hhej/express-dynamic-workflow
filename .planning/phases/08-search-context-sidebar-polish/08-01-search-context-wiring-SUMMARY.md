---
phase: 08-search-context-sidebar-polish
plan: 01
subsystem: ui
tags: [search-context, tavily, sse, react, typescript, response-node, drift-prevention]

# Dependency graph
requires:
  - phase: 05-polish-observability-docs
    provides: state.search_context populated by search_agent_node, SearchContextLine component, MarkdownAnswer.tsx blockquote-strip pattern, SearchContext type
provides:
  - response_node final_payload always carries search_context (the value, with None when state lacks it) on BOTH happy and deny paths
  - FinalStatus union extended with 'search_only'
  - Explicit MessageList renderAssistant case 'search_only' branch routing to MarkdownAnswer
  - 3 backend drift-prevention pytest assertions guarding the BE final_payload contract
  - 1 frontend drift-prevention vitest test mounting MessageList with status='search_only'
affects: [08-02-sidebar-polish-or-similar, future status-value extensions like partial_news]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BE→FE drift-prevention: 3-test triplet (present, absent-equals-None, deny-symmetric) catching key-presence regressions on final_payload contract"
    - "TypeScript union as drift chokepoint: extending FinalStatus before adding the dispatch case forces compile errors at every consumer not yet updated"

key-files:
  created:
    - frontend/__tests__/components/MessageList.search_only.test.tsx
  modified:
    - backend/agent/nodes/response_node.py
    - backend/tests/test_response_node.py
    - frontend/types/agent.types.ts
    - frontend/components/chat/MessageList.tsx

key-decisions:
  - "Used state.get('search_context') (not 'state.get(...) or None') so legitimate empty-dict structured values pass through unchanged — defends against the Pitfall 5 regression class"
  - "Deny-path final_payload mirrors the field for symmetry — provenance survives decline"
  - "Kept the default: branch in MessageList switch as a safety net for any future status the BE might emit before FE is updated"
  - "Preserved the BE Market context blockquote emission so non-FE consumers (Langfuse trace inspection, future API consumers) still see provenance even though FE strips it in MarkdownAnswer"
  - "Removed the planned 'message_id' field from the test fixture — it is not part of FinalPayload on this worktree branch (Phase 7 type bump not yet merged into this base) — non-functional adaptation, no scope change"

patterns-established:
  - "Drift-prevention test triplet for any new optional FE-visible field on a BE payload: assert (1) present-value flows through, (2) absent-key still appears with VALUE=None on the payload, (3) symmetric branches (deny/error) preserve the same wire"
  - "Type-union extension before dispatch wiring: change FinalStatus first to flush all consumer compile errors, then satisfy each one"

requirements-completed: [TOOL-05, UI-02]

# Metrics
duration: 7min
completed: 2026-05-05
---

# Phase 8 Plan 01: Search Context Wiring Summary

**`response_node` now always emits `search_context` in `final_payload` (happy + deny paths), `FinalStatus` declares `'search_only'`, and `MessageList` dispatches it explicitly to `MarkdownAnswer` — closes audit Issue 6 backend half + frontend type/dispatch half.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-05T05:53:22Z
- **Completed:** 2026-05-05T06:00:05Z
- **Tasks:** 2
- **Files modified:** 4 (backend/agent/nodes/response_node.py, backend/tests/test_response_node.py, frontend/types/agent.types.ts, frontend/components/chat/MessageList.tsx) + 1 created (frontend/__tests__/components/MessageList.search_only.test.tsx)

## Accomplishments

- Backend `response_node` happy-path final_payload literal now carries `state.get("search_context")` as the 5th key, never missing
- Backend `response_node` deny-path final_payload literal mirrors the field for symmetry — provenance survives decline
- Frontend `FinalStatus` union extended from 3 to 4 values: `'ok' | 'partial' | 'clarify' | 'search_only'`
- Frontend `MessageList.renderAssistant` switch gains an explicit `case 'search_only':` branch routing to `MarkdownAnswer`
- 3 new BE drift-prevention pytest assertions catch any future regression that drops `search_context` from `final_payload` (asserts both presence and None-when-absent, on happy AND deny paths)
- 1 new FE drift-prevention vitest test catches future regression that loses the rendering wire (`SearchContextLine` + sources details + no surcharge table on `status='search_only'` payloads)

## Task Commits

Each task followed strict TDD (RED → GREEN):

1. **Task 1 RED — backend tests for search_context in final_payload** — `2468f40` (test)
2. **Task 1 GREEN — forward state.search_context into final_payload on happy + deny paths** — `b3334e3` (feat)
3. **Task 2 RED — MessageList search_only rendering drift-prevention test** — `3496e3a` (test)
4. **Task 2 GREEN — add 'search_only' to FinalStatus union and dispatch in MessageList** — `b15a7fe` (feat)

_Note: TDD pairs are committed as test → feat. No refactor commits needed; the change set is small enough that no cleanup pass surfaced._

## Files Created/Modified

- `backend/agent/nodes/response_node.py` — Both happy-path and deny-path `final_payload` dict literals now include `"search_context": state.get("search_context")` as the 5th key. Comments cite Phase 8 D-07.
- `backend/tests/test_response_node.py` — Appended 3 drift-prevention tests at end of file: `test_response_forwards_search_context_in_final_payload_when_present`, `test_response_search_context_is_none_in_final_payload_when_absent`, `test_response_deny_path_forwards_search_context_in_final_payload`.
- `frontend/types/agent.types.ts` — `FinalStatus` union extended to include `'search_only'` (4 values total).
- `frontend/components/chat/MessageList.tsx` — `renderAssistant` switch gains explicit `case 'search_only':` branch returning `<MarkdownAnswer payload={payload} />`. The `default:` branch is preserved as a safety net.
- `frontend/__tests__/components/MessageList.search_only.test.tsx` — New file. Mounts `MessageList` with one assistant `ChatMessage` whose payload has `status='search_only'` + non-empty `search_context` and asserts (a) "Market context:" caption, (b) "Sources: 1" toggle, (c) source link `target='_blank'` + `rel='noopener noreferrer'`, (d) no surcharge breakdown table.

## Decisions Made

- **Preserve Market context blockquote emission in BE markdown**: Kept the existing BE-side `> **Market context:** ...` line emission even though `MarkdownAnswer` strips it on the FE. The blockquote keeps the provenance self-contained for Langfuse trace inspection and any non-FE consumers (per the existing comment in `_market_context_line`).
- **`state.get("search_context")` over `state.get(...) or None`**: The `or` form would swallow legitimately falsy structured values (e.g. empty-dict variants if the search_agent ever emits them). Explicit `state.get(...)` returns `None` only when the key is missing, exactly matching the test contract.
- **Default branch retained in MessageList switch**: Keeps the safety net that the original code had — any future BE status value the FE doesn't yet recognize falls through to MarkdownAnswer rather than rendering nothing.
- **TypeScript exhaustiveness `const _check: never = status;` skipped**: Per CONTEXT D-11 — the explicit case is sufficient documentation; a `never` check would be load-bearing only if the default branch were removed, which it isn't.

## Deviations from Plan

### Adaptations to worktree branch state (non-functional, scope-preserving)

**1. [Rule 3 - Blocking] Removed `message_id` from the FE test fixture**
- **Found during:** Task 2 GREEN (running `npx tsc --noEmit`)
- **Issue:** The plan's interface block (PLAN.md lines 100-107) showed `FinalPayload.message_id: string;` as a required field — that reflects the post-Phase-7 state. This worktree's branch base is `94ab36c` (post-Phase 5, pre-Phase 6/7), so `message_id` is not yet on `FinalPayload`. The plan-supplied fixture caused TS2353 "Object literal may only specify known properties".
- **Fix:** Removed the `message_id: 'thread-news-0'` line from the test fixture. The four test assertions (a/b/c/d) do not depend on `message_id`, so contract is unchanged.
- **Files modified:** `frontend/__tests__/components/MessageList.search_only.test.tsx`
- **Verification:** `npx tsc --noEmit` reports zero errors in `MessageList.search_only.test.tsx`; vitest passes.
- **Committed in:** `b15a7fe` (Task 2 GREEN commit, alongside the union extension and case branch).

**2. [Infrastructure - blocked test run] Copied seeded `data/express.db` and symlinked `frontend/node_modules` into the worktree**
- **Found during:** Task 1 GREEN (full backend pytest run) and Task 2 RED (first `npm test`).
- **Issue:** Worktree initialised without runtime artifacts: `data/express.db` (gitignored seed DB) was missing, causing `test_lookup_rate.py` to crash with `FileNotFoundError`. `frontend/node_modules` was empty, causing `vitest: command not found`.
- **Fix:** Copied `/Users/pollot/Desktop/express-dynamic-workflow/data/express.db` into `<worktree>/data/express.db`; symlinked `<worktree>/frontend/node_modules` to the main repo's `frontend/node_modules`.
- **Files modified:** None tracked. Both items are gitignored (`data/*.db`, `**/node_modules/`). No commit needed.
- **Verification:** Full backend suite 189/189 green; full FE suite 110/110 green.

### Out-of-scope items observed (NOT fixed per scope boundary)

**A. Pre-existing tsc error in `frontend/components/trace/TraceStep.tsx`**
- `error TS2739: Type '{ planner: ... }' is missing the following properties from type 'Record<AgentName, string>': hitl_gate, search_agent`
- Origin: file last touched in commit `1781499` (Plan 04-03), well before this plan. Phase 6's Plan 06-01 fix (per accumulated context) addresses this in a later branch not yet merged into this worktree base.
- Action: Logged here, not fixed. Out of scope per deviation rule's SCOPE BOUNDARY ("Only auto-fix issues DIRECTLY caused by the current task's changes").

---

**Total deviations:** 2 adaptations + 1 out-of-scope observation
**Impact on plan:** Adaptations preserve the plan's contract exactly (4 acceptance criteria for Task 2 still hold). No scope creep. The out-of-scope observation does not block any plan acceptance criterion (which only requires `MessageList.search_only.test.tsx` to typecheck and the case-branch grep to match — both satisfied).

## Issues Encountered

- Initial `Edit` tool call landed on the wrong path (`/Users/pollot/Desktop/express-dynamic-workflow/backend/tests/test_response_node.py` — the main repo, not the worktree). Reverted via `git restore` and re-applied the same patch to the worktree path. No data loss; harmless tooling artifact.

## Verification

- BE: `pytest backend/tests/test_response_node.py -x` → **17/17** (existing 14 + new 3) green
- BE: `pytest backend/tests/` → **189/189** (full backend suite) green
- FE: `npm test -- --run __tests__/components/MessageList.search_only.test.tsx` → **1/1** green
- FE: `npm test -- --run` → **110/110** (full FE suite, 26 test files) green
- FE: `npx tsc --noEmit` on the new test file → 0 errors (the unrelated `TraceStep.tsx` pre-existing error remains; out of scope)
- grep: `state\.get("search_context")` appears 4× in `response_node.py` (2 new from this plan, 2 pre-existing in `_market_context_line` helper / markdown gate)
- grep: `case 'search_only':` appears 1× in `MessageList.tsx`
- grep: `'search_only'` appears in the `FinalStatus` line of `agent.types.ts`

## Next Phase Readiness

- Audit Issue 6 backend half + frontend type/dispatch half are CLOSED.
- The remaining audit Issue 6 work (live smoke test of news query rendering `SearchContextLine` with clickable sources) is deferred to phase verification or to Plan 08-02 if scoped there.
- No blockers introduced. The worktree branch lacks Phase 6 + Phase 7 commits, so the executor verifier (or merge agent) should ensure these BE/FE diffs cleanly merge atop the main branch's `quality/milestone-gaps`.

## Self-Check: PASSED

- File `backend/agent/nodes/response_node.py` exists ✓
- File `backend/tests/test_response_node.py` exists ✓
- File `frontend/types/agent.types.ts` exists ✓
- File `frontend/components/chat/MessageList.tsx` exists ✓
- File `frontend/__tests__/components/MessageList.search_only.test.tsx` exists ✓
- Commit `2468f40` (test BE drift) found in `git log` ✓
- Commit `b3334e3` (feat BE forward search_context) found in `git log` ✓
- Commit `3496e3a` (test FE drift) found in `git log` ✓
- Commit `b15a7fe` (feat FE union + dispatch) found in `git log` ✓

---
*Phase: 08-search-context-sidebar-polish*
*Completed: 2026-05-05*
