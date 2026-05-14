# Deferred Items — Out of Scope for 260514-vrc

These items surfaced during execution but are unrelated to the response_node
state-leak gate. Logged here per the executor scope-boundary rule (only
auto-fix issues DIRECTLY caused by the current task's changes).

## Pre-existing failing tests on `fix/quick-260514-vrc-response-node-fresh-truth-gate`

Both failures present on the branch BEFORE any 260514-vrc edits landed
(verified via `git stash && pytest && git stash pop` cross-check).

1. `backend/tests/test_prompt_hardening.py::test_config_has_guard_knobs`
   - Asserts `backend.config.MAX_TOOL_CALLS_PER_TURN == 6` (documented default).
   - Actual value: `10`. The config got bumped at some point without the
     test being updated, or the documented default drifted.
   - Surface: configuration / documentation drift, not a behaviour bug.

2. `backend/tests/test_guard_input.py::test_tool_call_count_trips_guard`
   - Likely a knock-on of the same `MAX_TOOL_CALLS_PER_TURN` change — the
     test fixture probably trips the cap at a value tied to the old `6`.

## Recommendation

These are independent housekeeping items. Suggest a separate quick task
(or a follow-up commit on this branch after the freshness-gate PR merges)
to reconcile `MAX_TOOL_CALLS_PER_TURN` between code (`backend/config.py`),
test fixtures, and the documented default mentioned in
`backend/tests/test_prompt_hardening.py`.

NOT touched by this task — the freshness-gate fix is purely a render-layer
change in `response_node`.
