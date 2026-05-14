---
phase: quick
plan: 260514-vrc
one_liner: "Render-time state-leak fix in response_node — locally gate stale state.surcharge_result + state.search_context behind a current-turn freshness check (state never mutated)"
requirements_completed: []
tags:
  - quick-task
  - bugfix
  - response-node
  - state-leak
  - render-layer
  - render-gate
  - sibling-999.12
branch: fix/quick-260514-vrc-response-node-fresh-truth-gate
commits:
  - 3b8b079  # fix: freshness gate
  - ef947c8  # test: 3 new gate tests
  - 2d9e3ac  # docs: cross-link to 999.12
files_touched:
  - backend/agent/nodes/response_node.py        # +92 / -17
  - backend/tests/test_response_node.py         # +220 / -0
  - .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md  # +6 / -0
test_deltas:
  test_response_node_py_before: 19
  test_response_node_py_after:  22  # +3 new
  backend_total_before: 359
  backend_total_after:  362
  backend_passing_before: 357  # 2 pre-existing failures unrelated (MAX_TOOL_CALLS_PER_TURN config drift)
  backend_passing_after:  360  # same 2 pre-existing failures
related:
  sibling_defect: ".planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md"
  family: "AgentState fields meant to be turn-scoped behave as thread-scoped — no explicit null-at-turn-boundary path"
verification:
  automated: "pytest backend/tests/test_response_node.py -q (22/22 green); pytest backend/tests/ (360 passing + 2 pre-existing failures unrelated to the gate)"
  visual_pending: "Orchestrator restarts uvicorn after PR merge; user re-runs the 8-turn demo on a fresh thread to confirm a search query + the FIX-02 short-circuit no longer render the stale pricing breakdown."
---

# Quick Task 260514-vrc: response_node Fresh-Truth Gate Summary

## One-liner

State-leak fix at the render layer of `response_node`: locally gate stale `state.surcharge_result` and `state.search_context` behind a current-turn freshness check. The `state` dict is **never mutated** — the gate only nulls render-bound locals when the corresponding agent (`pricing_agent` / `search_agent`) did not run this turn.

## Why

Without an explicit null-at-turn-boundary path, the LangGraph SQLite checkpointer's thread-scoped persistence of `AgentState` caused a prior turn's `surcharge_result` and `search_context` to leak into the current turn's `final_payload` whenever the current turn skipped pricing / search (e.g., a follow-up clarify turn after a successful pricing turn, or a search-only news query after a pricing turn). The user-facing markdown rendered a stale breakdown table, and the FE trace panel + `final_payload.search_context` shipped stale provenance.

This is a sibling defect to `.planning/debug/999.12` (duplicate `message_id`) — same family: "AgentState fields meant to be turn-scoped behave as thread-scoped because no path explicitly nulls them at turn boundaries."

## How (Mechanism)

Scan `state.reasoning_trace` for the most recent `agent=='response'` entry; entries AFTER that index are the **current turn**. The gate sets two render-bound locals:

```python
surcharge_result_for_render = state.get("surcharge_result") if pricing_ran_this_turn else None
search_context_for_render   = state.get("search_context")   if search_ran_this_turn   else None
```

All downstream render paths (status precedence ladder, `_render_table`, `_market_context_line`, `final_payload.search_context`) read from these locals. The `state` dict is read-only throughout.

**Backward-compat shim:** when `reasoning_trace` is empty (synthetic unit-test fixtures, replay harnesses), trust `state` at face value so the 19 pre-existing tests stay green without modification.

## Scope Boundaries (Preserved)

- **Refusal branch (guard) — untouched.** Has its own dedicated state-handling.
- **Deny branch (HITL) — untouched.** Only signature-compat update: `_market_context_line(state)` → `_market_context_line(state.get("search_context"))` (helper now takes explicit arg).
- **`_render_table`, `_pricing_reasoning_bullets`, `_render_prose_ok/clarify/partial` — untouched.**
- **Phase 7 messages-persistence — untouched.**

## Files Touched

| File                                                                               | Insertions | Deletions | Purpose                                                                              |
| ---------------------------------------------------------------------------------- | ---------- | --------- | ------------------------------------------------------------------------------------ |
| `backend/agent/nodes/response_node.py`                                             | +92        | -17       | `_market_context_line` signature; freshness-gate block; render-local callsite swaps. |
| `backend/tests/test_response_node.py`                                              | +220       | 0         | 3 new tests covering the gate (search-turn, clarify-turn, fresh-pricing).            |
| `.planning/debug/999.12-...-be-stamping.md`                                        | +6         | 0         | Cross-link note appended (Related Fixes Shipped Mid-Freeze).                         |

## Test Deltas

| Suite                            | Before | After | Notes                                                                  |
| -------------------------------- | ------ | ----- | ---------------------------------------------------------------------- |
| `test_response_node.py`          | 19     | 22    | +3 new: `gates_stale_surcharge_on_search_turn`, `gates_stale_surcharge_on_clarify_turn`, `renders_fresh_pricing_when_pricing_ran_this_turn`. |
| `backend/tests/` (full collected) | 359    | 362   | +3 new, no regressions.                                                |
| Passing                          | 357    | 360   | Same 2 pre-existing failures (unrelated `MAX_TOOL_CALLS_PER_TURN` config drift — see `deferred-items.md`). |

Each new test asserts both rendered payload semantics AND `state` identity preservation (`assert state["surcharge_result"] is pre_call_surcharge`).

## Commit Order

| #   | Hash      | Type   | Subject                                                                                                |
| --- | --------- | ------ | ------------------------------------------------------------------------------------------------------ |
| 1   | `3b8b079` | `fix`  | gate stale `surcharge_result` + `search_context` behind current-turn freshness in `response_node`      |
| 2   | `ef947c8` | `test` | cover current-turn freshness gate in `response_node`                                                   |
| 3   | `2d9e3ac` | `docs` | cross-link `response_node` freshness-gate fix to debug 999.12                                          |

All three on branch `fix/quick-260514-vrc-response-node-fresh-truth-gate`.

## Cross-link

- Sibling defect: `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md` (duplicate `message_id`). Added a `## Related Fixes Shipped Mid-Freeze` section there pointing back to this quick task; signals to the post-demo `/gsd:debug` pickup that the broader "state-scoping across turns" class likely shares a single architectural root cause across both surfaces.

## Deferred Items (Out of Scope)

Pre-existing failures unrelated to this gate, logged in `deferred-items.md`:

1. `test_prompt_hardening.py::test_config_has_guard_knobs` — config drift on `MAX_TOOL_CALLS_PER_TURN` (10 vs documented default 6).
2. `test_guard_input.py::test_tool_call_count_trips_guard` — likely knock-on of the same constant.

Both predate this branch (verified via `git stash` cross-check). Recommend a follow-up housekeeping quick task to reconcile.

## Constraint Compliance

- [x] `state` dict is never mutated (verified in 3 new tests via identity asserts).
- [x] Refusal branch + deny branch unchanged (modulo `_market_context_line` signature compat).
- [x] `.env` / `.env.example` untouched.
- [x] `data/raw/eppo_diesel_prices.csv` untouched (unstaged refresh left alone).
- [x] No frontend files touched.
- [x] No `ROADMAP.md` edits.
- [x] v1.1.0 tag unchanged.
- [x] 3 atomic commits in order `fix → test → docs` on the existing feature branch.

## Visual-Verification Deferral

After this PR merges, the orchestrator restarts uvicorn. The user then re-runs the 8-turn demo on a fresh thread to confirm:

1. A pure search-news follow-up after a pricing turn renders the news prose only — no stale breakdown table.
2. The FIX-02 destination-less short-circuit clarify turn no longer carries a stale pricing breakdown from the prior pricing turn.

Both behaviours are pinned by the new automated tests; the live-uvicorn re-check is a defense-in-depth visual confirmation, not a gate.

## Self-Check: PASSED

- response_node.py changes present at commit `3b8b079` (verified: `git show 3b8b079 --stat`).
- test_response_node.py changes present at commit `ef947c8` (verified: 22 tests pass).
- 999.12 cross-link present at commit `2d9e3ac` (verified: `grep -F "Related Fixes Shipped Mid-Freeze"` returns match).
- Three commits visible in `git log --oneline -4` in correct order.
- State identity assertions pass in all 3 new tests (state never mutated).
