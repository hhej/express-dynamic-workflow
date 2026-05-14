---
quick_id: 260514-wgg
phase: quick
plan: 260514-wgg
type: quick
one_liner: "_route_matches now accepts merged origin_hub_id from caller, fixing the prose-override-doesn't-trigger-route-fetch bug"
branch: fix/quick-260514-wgg-route-matches-merged-hub
completed: 2026-05-14
commits: 3 source/test/doc + 1 wrap-up
sibling_family: 999.12 (3 confirmed siblings)
requirements_completed: []
---

# Quick 260514-wgg — _route_matches accepts merged origin_hub_id

## What Shipped

Fixed a stale-state read in `backend/agent/nodes/planner.py::_route_matches`:
the cache-check predicate was reading `state.get("origin_hub_id")` directly,
but the caller (`planner_node`) had already computed the freshest hub value
as `merged_origin_hub_id` (line 505 — the post-999.1-merge local that combines
`parsed.origin_hub_id` from this turn's prose with prior state via the
null-only coalesce). On prose-override turns ("Ship 5kg from Bang Na to
Nonthaburi" with dropdown on HQ Lat Krabang), the cache-check saw the stale
state hub and falsely matched a cached `(hq-lat-krabang, Nonthaburi)`
route_data, skipping `route_agent` entirely.

## Changes

- **`backend/agent/nodes/planner.py`** (+18 / -5) — `_route_matches` now
  accepts an optional 4th arg `origin_hub_id: Optional[str] = None`. Inside,
  the hub-compare reads from the passed param when non-None, falling back to
  `state.get("origin_hub_id")` for backward compat. All 3 in-file call sites
  (lines 542, 562, 570) pass `merged_origin_hub_id`. Docstring updated with a
  third paragraph documenting the override semantics.

- **`backend/tests/test_planner.py`** (+146 / -0) — 3 new tests appended:
  1. `test_route_matches_uses_passed_origin_hub_id_over_state` — direct unit
     pin: passed hub overrides state.
  2. `test_route_matches_falls_back_to_state_when_param_omitted` — backward
     compat pin (exercises the `else state.get(...)` fallback branch).
  3. `test_planner_invokes_route_agent_on_prose_origin_override` —
     end-to-end: prose override invalidates route cache, re-invokes
     route_agent (asserts `next_step in ("fetch_route", "fanout_fuel_route")`
     and `origin_hub_id == "branch-bang-na"`).

- **`.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`**
  (+4 / -0) — appended a cross-link bullet under "Related Fixes Shipped
  Mid-Freeze"; 999.12 family now has 3 confirmed siblings. Common pattern:
  AgentState fields meant to be turn-scoped behave thread-scoped because
  this turn's parsed values aren't yet visible in state when downstream
  helpers read it directly. Post-demo `/gsd:debug` should treat all four
  (duplicate message_id + vrc + wgg) as one cluster.

## Verification

- `pytest backend/tests/test_planner.py` — 41 tests, all green (38 prior +
  3 new). Test deltas: backend planner count rose by exactly 3.
- Full backend suite (`pytest backend/tests/`) — 2 pre-existing failures
  (`test_prompt_hardening.py::test_config_has_guard_knobs`,
  `test_guard_input.py::test_tool_call_count_trips_guard`) remain in the
  same pre-existing state, both caused by the `.env`
  `MAX_TOOL_CALLS_PER_TURN=10` cap bump — NOT introduced by this PR. No
  new failures.

## Out of Scope / Did NOT Change

- v1.1.0 tag (NOT bumped — fix lives on a feature branch off develop).
- `.env` / `.env.example`.
- `data/raw/eppo_diesel_prices.csv` (unstaged refresh; intentionally left
  alone).
- `.planning/ROADMAP.md`.
- Any other planner logic — D-04 budget guard, D-02 retry, refusal branches,
  FIX-02 short-circuit, 999.1 merge, gap-1 followup null-out, gap-3 search
  short-circuit, 999.9 D-10 hub validation — all untouched.
- Frontend (no changes).

## Orchestrator Handoff

Branch `fix/quick-260514-wgg-route-matches-merged-hub` ready for push + PR
→ develop. Four commits on the branch in order:

  1. `fix(quick-260514-wgg): _route_matches accepts merged origin_hub_id`
  2. `test(quick-260514-wgg): pin _route_matches merged-hub fix + backward-compat`
  3. `docs(quick-260514-wgg): cross-link _route_matches fix to 999.12 family`
  4. `docs(quick-260514-wgg): close _route_matches merged-hub fix (SUMMARY + STATE)`

### Visual Verification Deferred

After merge to develop, orchestrator restarts uvicorn and the user runs
the demo's turn 3 prompt with HubPicker on HQ Lat Krabang:

> "Ship 5kg bounce from Bang Na to Nonthaburi"

Expected: trace panel shows `route_agent` entry with
`origin_hub_id="branch-bang-na"`; distance reflects the Bang Na origin;
zone stays central-1 by coincidence (both origins are in central-1).

## Sibling Family Status

999.12 cluster (post-W6-demo `/gsd:debug` scope):

- Duplicate `message_id` (the open 999.12 deferred investigation)
- response_node fresh-truth gate (quick-260514-vrc, 2026-05-14)
- `_route_matches` cache-key merged hub (this fix, 2026-05-14)

Common architectural pattern across all three: AgentState fields meant to
be turn-scoped behave as thread-scoped because parsed values from this
turn aren't yet visible in state when downstream functions read it
directly.

## Self-Check: PASSED

- `backend/agent/nodes/planner.py` — `_route_matches` signature updated with
  4th arg; 3 call sites pass `merged_origin_hub_id`; docstring updated.
- `backend/tests/test_planner.py` — 3 new tests present, all green.
- `.planning/debug/999.12-...md` — new bullet appended (grep
  `quick-260514-wgg` returns 2 matches).
- 3 commits landed (fix → test → docs); wrap-up commit follows this file.
