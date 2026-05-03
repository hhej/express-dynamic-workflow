---
phase: 05-polish-observability-docs
plan: 09
subsystem: testing
tags: [route-agent, error-handling, langgraph, gap-closure, docs, bangkok-metro]

# Dependency graph
requires:
  - phase: 03-graph-assembly-and-api-layer
    provides: D-23 retry-allow-list (excludes ValueError) + D-24 _wrap_error_sink (re-raises ValueError unchanged) — together these forced the in-node catch to live INSIDE route_agent_node, not in the sink.
  - phase: 02-tools-and-agents
    provides: D-10 ValueError contract on missing origin/destination — preserved verbatim by the gap-2 selective catch.
  - phase: 05-polish-observability-docs
    provides: Plan 05-07 docs/data-sources.md baseline (incorrect zone mapping); Plan 05-08 parallel sibling closing gap-1 (also touches test_graph.py — coordinated via append-to-end pattern per parallel_file_warning).

provides:
  - route_agent_node selectively catches ValueError("No Bangkok Metro zone for ...") and converts it to a graceful state.errors entry + next_step='respond' (UAT test 4 path).
  - 3 new tests proving the fix and asserting the D-10 ValueError on missing origin/destination is preserved.
  - docs/data-sources.md zone mapping corrected to match data/raw/zone_definitions.json verbatim (Plan 05-07 baseline was wrong about central-1/2/3 split).
  - README.md Limitations section enumerates supported provinces per zone tier and documents the graceful out-of-scope clarify response.
  - docs/architecture.md Phase 5 Error Paths section gains a Zone miss (gap-2) bullet with full state-flow narration.

affects: 05-10 (final UAT re-run / submission readiness — gap-2 closure unlocks ROADMAP §Phase 5 success criterion #2 HITL demo via central-3 query and #5 doc accuracy).

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Selective ValueError prefix-match catch — not every ValueError is the same; check the message prefix to preserve unrelated ValueError contracts (e.g. D-10) while gracefully handling a known recoverable case."
    - "Graceful in-node sink AHEAD of _wrap_error_sink — when a node knows a specific exception class is user-recoverable AND the sink would re-raise it, convert to state.errors locally so the planner D-24 short-circuit picks it up cleanly."
    - "Docs-follow-data invariant — when docs and source-of-truth data files diverge, fix the docs to match the data file (zone_definitions.json), not the other way around."

key-files:
  created:
    - .planning/phases/05-polish-observability-docs/05-09-SUMMARY.md
  modified:
    - backend/agent/nodes/route_agent.py
    - backend/tests/test_route_agent.py
    - backend/tests/test_graph.py
    - docs/data-sources.md
    - README.md
    - docs/architecture.md

key-decisions:
  - "Selective ValueError catch via msg.startswith('No Bangkok Metro zone') instead of a broad ValueError catch — preserves the D-10 ValueError on missing origin/destination (Phase 2 Plan 05 contract). Any other ValueError continues to bubble per D-23."
  - "warn-status trace entry on the gap-2 path so the FE reasoning panel surfaces the zone-miss cause to users — not silent. Trace entry naming the supported zone set + pointing to docs/data-sources.md gives users a recovery hint."
  - "Doc updates rewrote docs/data-sources.md central-1/2/3 split to match zone_definitions.json verbatim (Plan 05-07 baseline had central-1=Bangkok only and central-2=everything-else, which is wrong vs the actual data file). README + architecture.md updates reference data-sources.md as the canonical province list."
  - "Integration test reuses the parallel fan-out path (Phase 5 D-01 fanout_fuel_route) to exercise the gap-2 fix end-to-end — the operator.add reducer on errors safely merges the route_agent error append concurrent with the successful fuel_agent path."

patterns-established:
  - "Pattern: Append new test cases to the END of test_graph.py with a labeled section header — coordinates safe parallel-plan editing of the same test file."
  - "Pattern: When fixing a gap raised by a UAT test, write the integration test FIRST mirroring the original UAT scenario (Bangkok -> Lop Buri here), then build the unit-test contract the integration test needs to pass."

requirements-completed: [ORCH-03, ORCH-08, DOC-01, DOC-02, DOC-04]

# Metrics
duration: ~6min
completed: 2026-05-03
---

# Phase 05 Plan 09: Out-of-Bangkok-Metro graceful clarify (gap-2) Summary

**Selective ValueError catch in route_agent_node converts out-of-Metro destinations to a status='partial' clarify response naming route_agent + the supported zone set, plus docs corrected to match data/raw/zone_definitions.json verbatim.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-03T11:18:16Z
- **Completed:** 2026-05-03T11:24:09Z
- **Tasks:** 2
- **Files modified:** 6 (1 source + 2 tests + 3 docs)

## Accomplishments

- **gap-2 fix shipped** — UAT test 4 (Bangkok -> Lop Buri) no longer dead-ends with an SSE error event. The graph reaches END with status='partial' prose naming route_agent as the failed node.
- **D-10 contract preserved** — the ValueError on missing origin/destination still bubbles uncaught (verified by `test_missing_origin_destination_still_raises`).
- **Doc honesty restored** — docs/data-sources.md, README.md, and docs/architecture.md now enumerate the actual 15 supported provinces across central-1/2/3 (matching zone_definitions.json verbatim) and explicitly call out which provinces produce the graceful clarify response (Chiang Mai, Phuket, Khon Kaen, Songkhla examples).
- **178/178 tests green** — all existing 152 backend tests + 3 new gap-2 tests + 23 from Plan 05-08 (parallel sibling) pass together.

## Task Commits

Each task was committed atomically (TDD red/green for Task 1):

1. **Task 1 (RED): Add failing tests for gap-2 zone-miss path** — `6e369d8` (test)
2. **Task 1 (GREEN): Catch zone-miss ValueError in route_agent_node** — `da73024` (fix)
3. **Task 2: Update docs to enumerate Bangkok Metro provinces** — `8c0ed9b` (docs)

**Plan metadata commit:** pending — final commit will include this SUMMARY.md, STATE.md, ROADMAP.md updates per executor protocol.

## Files Created/Modified

- `backend/agent/nodes/route_agent.py` — wrapped `calculate_route` call in try/except that selectively catches ValueError whose message starts with "No Bangkok Metro zone"; appends structured entry to state.errors, returns next_step='respond', emits status='warn' trace entry. The D-10 ValueError on missing origin/destination remains untouched.
- `backend/tests/test_route_agent.py` — added `test_zone_miss_returns_clarify_eligible_state` (graceful path contract) and `test_missing_origin_destination_still_raises` (D-10 invariant).
- `backend/tests/test_graph.py` — added `test_out_of_metro_destination_renders_clarify` at END of file (per parallel_file_warning) reproducing UAT test 4 end-to-end.
- `docs/data-sources.md` — replaced incorrect central-1/2/3 mapping with the verbatim split from zone_definitions.json (15 provinces total); added explicit Out-of-scope provinces note describing the graceful clarify response.
- `README.md` — replaced Limitations "Bangkok Metro only" bullet with a clearer enumeration referencing each zone tier, pointing to data-sources.md for the full list, and citing backlog 999.2 (the 2026-04-25 Bangkok Metro rename).
- `docs/architecture.md` — added a "Zone miss (gap-2, Plan 05-09)" bullet to the Phase 5 Error Paths section documenting the full state-flow: prefix match, state.errors append shape, planner short-circuit (D-24), response_node._render_prose_partial render, warn-status trace entry, D-10 ValueError preservation.

## Decisions Made

See key-decisions in frontmatter above. Highlights:

- **Selective prefix-match catch over broad ValueError catch** — surgical fix that preserves every other ValueError contract.
- **In-node sink ahead of _wrap_error_sink** — the Phase 3 sink re-raises ValueError unchanged, so the catch must live inside route_agent_node to prevent the SSE error channel surprise.
- **warn-status trace entry, not ok** — the FE reasoning panel will render the failure cause visibly so users can self-recover.
- **Docs-follow-data invariant** — Plan 05-07 doc baseline had central-1/2/3 wrong; Task 2 corrected the docs to match zone_definitions.json, not the other way around.

## Deviations from Plan

### Process Deviations

**1. [Rule 0 - Doc-text-formatting] Unwrapped two doc lines so AC greps match single-line**
- **Found during:** Task 2 acceptance-criteria verification
- **Issue:** The plan acceptance criteria use single-line `grep -c "X" file` checks for `"Bangkok, Nonthaburi, Pathum Thani, Samut Prakan, Ayutthaya, Ang Thong"` (data-sources.md), `"Multi-region expansion is V2-02"` (data-sources.md), and `"graceful status='partial' clarify response"` (README.md). The default 80-col line wrap put each phrase on a wrapped line, so the AC greps returned 0 even though the substantive content was correct.
- **Fix:** Unwrapped the three relevant phrases onto single lines (the "Bangkok Metro provinces covered" enumeration, the "Multi-region expansion is V2-02" sentence in data-sources.md, and the "graceful status='partial' clarify response" phrase in README.md). The change is purely formatting — no semantic content modified.
- **Files modified:** docs/data-sources.md, README.md
- **Verification:** All 13 Task 2 ACs pass; the substantive plan content (province enumeration, V2-02 deferred note, graceful clarify reference) remained identical.
- **Committed in:** 8c0ed9b (Task 2 commit, single-shot)

### Auto-fixed Issues

None — no Rule 1/2/3 fixes required during execution.

---

**Total deviations:** 1 minor formatting tweak.
**Impact on plan:** Zero scope creep — the AC greps were over-specific about line breaks; the fix is a doc-formatting trim that preserves all semantic content.

## Issues Encountered

- **Parallel Plan 05-08 conflict avoidance** — Plan 05-08 (sibling, also Wave 7) modifies `backend/tests/test_planner.py` and adds tests to `backend/tests/test_graph.py`. Per `parallel_file_warning` in the prompt, my new integration test was appended to the END of test_graph.py with its own `# Plan 05-09 — gap-2 E2E regression` section header. After Plan 05-08 landed (commits 60df0c3 + 710fb9c), the full suite ran 178/178 green together — no merge conflicts on test_graph.py.
- **Mid-execution test_planner.py temporary RED** — during my own GREEN-phase suite verification, `test_followup_inherits_unmentioned_fields` (a Plan 05-08 RED test) was failing because Plan 05-08's planner.py change hadn't landed yet. Verified my own work was clean by running the test_planner.py suite in isolation and confirming none of my changes touched planner.py. Once Plan 05-08 completed, the test went GREEN and the full suite is now 178/178.

## Self-Check

Verifying the SUMMARY.md claims against disk state:

- File `backend/agent/nodes/route_agent.py` modified — FOUND (43 insertions visible in `git show da73024 --stat`).
- File `backend/tests/test_route_agent.py` modified — FOUND (Test 1 + Test 2 added in 6e369d8).
- File `backend/tests/test_graph.py` modified — FOUND (Test 3 added at end of file in 6e369d8).
- File `docs/data-sources.md` modified — FOUND (Task 2 commit 8c0ed9b).
- File `README.md` modified — FOUND (Task 2 commit 8c0ed9b).
- File `docs/architecture.md` modified — FOUND (Task 2 commit 8c0ed9b).
- Commit 6e369d8 (RED tests) — FOUND in git log.
- Commit da73024 (GREEN fix) — FOUND in git log.
- Commit 8c0ed9b (docs) — FOUND in git log.
- 3 new tests pass — FOUND (`pytest -v` output: 3 passed in 0.41s).
- Full suite 178/178 — FOUND (`pytest backend/tests/` output: 178 passed in 7.55s).

## Self-Check: PASSED

## Next Phase Readiness

- **gap-2 closed** — UAT test 4 scenario now produces a graceful status='partial' clarify response. Ready for Plan 05-10 (final UAT re-run / submission readiness checks).
- **ROADMAP §Phase 5 success criterion #2 unblocked** — HITL demo via central-3 query (Lop Buri / Kanchanaburi / Ratchaburi all map to central-3) is now safe to run; the docs explicitly list those provinces so the demo script can reference them.
- **ROADMAP §Phase 5 success criterion #5 progress** — DOC-01 / DOC-02 / DOC-04 honesty restored. README, architecture.md, and data-sources.md are now consistent and accurate vs zone_definitions.json.
- **No blockers** for Plan 05-10.

---
*Phase: 05-polish-observability-docs*
*Completed: 2026-05-03*
