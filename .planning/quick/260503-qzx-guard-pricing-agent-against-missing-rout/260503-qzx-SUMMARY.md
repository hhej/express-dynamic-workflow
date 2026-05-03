---
quick_task: 260503-qzx
type: execute
subsystem: backend/agent
tags: [pricing_agent, gap-closure, defense-in-depth, UAT]
dependency-graph:
  requires:
    - backend/agent/nodes/pricing_agent.py (existing pricing logic)
    - backend/agent/nodes/route_agent.py (D-24 error-sink reference pattern from gap-2)
    - backend/agent/state.py (operator.add reducers on errors and reasoning_trace)
  provides:
    - "Defensive precondition guard in pricing_agent_node against missing route_data/fuel_data"
    - "2 regression tests asserting graceful short-circuit on missing inputs"
    - "gap-4 closure documentation in 05-UAT.md"
  affects:
    - backend/api SSE error-event paths (no longer triggered by KeyError on missing route/fuel)
    - frontend trace panel (now surfaces a status='warn' entry on the rare hallucinated-routing case)
tech-stack:
  added: []
  patterns:
    - "Defense-in-depth at consumer node: guard upstream contract violations at the point of consumption rather than fixing the producer (planner LLM hallucination)"
    - "D-24 error-sink shape reuse: same {node, exception_type, message, timestamp} tuple emitted by route_agent gap-2 fix"
key-files:
  created:
    - .planning/quick/260503-qzx-guard-pricing-agent-against-missing-rout/260503-qzx-SUMMARY.md
  modified:
    - backend/agent/nodes/pricing_agent.py
    - backend/tests/test_pricing_agent.py
    - .planning/phases/05-polish-observability-docs/05-UAT.md
decisions:
  - "Mirrored route_agent.py:128-159 D-24 error-sink shape verbatim — only node identity (\"pricing_agent\") and missing-key text differ; preserves trace-panel + Langfuse rendering with no UI/observability changes"
  - "next_step=\"respond\" (NOT \"planner\") on guard fire — Pitfall: routing back to planner risks an infinite loop with a misbehaving planner LLM that keeps emitting next_step=\"calculate_price\""
  - "Truthy check (not route_data) over None check (route_data is None) — covers both None and empty-dict edge cases for defense in depth"
  - "tdd=\"true\" in plan, but task ordering is fix-then-test (Task 1 = fix + Task 2 = tests) — followed plan task atomicity over strict TDD RED/GREEN ordering, since splitting into a 4th commit would break the plan's 3-commit contract"
metrics:
  duration: ~3min
  completed: 2026-05-03
---

# Quick Task 260503-qzx: Guard pricing_agent against missing route_data/fuel_data Summary

Defense-in-depth precondition guard added to `pricing_agent_node` so a misbehaving planner LLM that emits `next_step="calculate_price"` before route_agent/fuel_agent have populated state cannot crash the user's conversation with `KeyError: 'route_data'`.

## What Was Built

Three atomic commits:

1. **`fix(pricing_agent):`** (`8c47ee4`) — Added a precondition guard at the top of `pricing_agent_node` that fires when either `state.get("route_data")` or `state.get("fuel_data")` is None/falsy. On fire: emits a D-24-shaped error-sink entry, a status="warn" reasoning_trace entry, and returns `next_step="respond"` (NOT "planner" — loop risk). Happy path at line 138+ unchanged.

2. **`test(pricing_agent):`** (`03bf4fa`) — Added 2 regression tests:
   - `test_guards_missing_route_data` — `route_data=None` → no raise, errors[0].node="pricing_agent", warn trace
   - `test_guards_missing_fuel_data` — symmetric for `fuel_data=None`
   Both reuse the existing `_full_state()` helper and require zero mocking (guard short-circuits before `lookup_rate` / `get_chat_model` are touched).

3. **`docs(uat):`** (`79d8ee0`) — Appended gap-4 entry to `05-UAT.md ## Gaps` section after gap-3 (status: resolved, resolved_by: quick-task 260503-qzx, test: 20, severity: medium). Frontmatter, Tests section, and Summary block (total: 7, passed: 4) unchanged.

## Test Results

- **Before:** 184/184 backend tests green (baseline)
- **After:** 186/186 backend tests green (+2 new pricing_agent guard tests)
- All 5 tests in `backend/tests/test_pricing_agent.py` pass (3 existing happy-path + 2 new guard tests)

## Verification Against Plan Success Criteria

- [x] pricing_agent_node guards against missing route_data and missing fuel_data without raising
- [x] Guard emits D-24-shaped error sink entry (node="pricing_agent", exception_type="KeyError", message, timestamp)
- [x] Guard emits reasoning_trace entry with status="warn"
- [x] Guard returns next_step="respond" (NOT "planner")
- [x] 2 regression tests added, both passing
- [x] Existing 3 pricing_agent tests still pass (no regression on happy path)
- [x] Full backend suite green: 186/186
- [x] gap-4 appended to 05-UAT.md after gap-3, frontmatter and Summary block untouched
- [x] Three atomic commits land in task order, each independently revertable

## Deviations from Plan

None — plan executed exactly as written. The plan declared `tdd="true"` on Tasks 1 and 2 but explicitly defined fix-then-test commit ordering (Task 1 = fix + verify existing tests still pass; Task 2 = add new regression tests). Followed the plan's atomic 3-commit contract over strict TDD RED/GREEN, since splitting tests into a separate RED commit before Task 1 would have broken the contract.

## Commits

| Task | Hash      | Type | Message |
| ---- | --------- | ---- | ------- |
| 1    | `8c47ee4` | fix  | guard against missing route_data/fuel_data (gap-4 from UAT 260503-qzx) |
| 2    | `03bf4fa` | test | regression tests for missing route_data/fuel_data (gap-4) |
| 3    | `79d8ee0` | docs | document gap-4 — pricing_agent missing route_data/fuel_data |

## Self-Check: PASSED

Verified all claimed artifacts exist on disk and all claimed commits are in the git log.
