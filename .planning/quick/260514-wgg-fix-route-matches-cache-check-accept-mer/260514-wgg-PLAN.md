---
quick_id: 260514-wgg
type: quick
mode: execute
created: 2026-05-14
branch: fix/quick-260514-wgg-route-matches-merged-hub
files_modified:
  - backend/agent/nodes/planner.py
  - backend/tests/test_planner.py
  - .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md
autonomous: true
must_haves:
  truths:
    - "_route_matches accepts an explicit origin_hub_id parameter that overrides state.origin_hub_id when passed non-None"
    - "All 3 call sites in planner_node pass merged_origin_hub_id (the post-merge hub) into _route_matches"
    - "Prose-override turns ('Ship 5kg from Bang Na to Nonthaburi' with dropdown on HQ Lat Krabang) correctly invalidate the route cache and re-invoke route_agent"
    - "Backward compatibility preserved — callers that omit the 4th arg fall back to state.get('origin_hub_id')"
    - "999.12 debug file's 'Related Fixes Shipped Mid-Freeze' section gains a new bullet for this fix, completing the 3-sibling cluster"
  artifacts:
    - path: "backend/agent/nodes/planner.py"
      provides: "_route_matches with 4-arg signature; 3 updated call sites"
      contains: "def _route_matches"
    - path: "backend/tests/test_planner.py"
      provides: "3 new regression tests pinning the fix + backward-compat fallback"
      contains: "test_route_matches_uses_passed_origin_hub_id_over_state"
    - path: ".planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md"
      provides: "Cross-link bullet under 'Related Fixes Shipped Mid-Freeze'"
      contains: "quick-260514-wgg"
  key_links:
    - from: "planner_node call sites (lines 542, 562, 570)"
      to: "_route_matches(state, merged_origin, merged_destination, merged_origin_hub_id)"
      via: "explicit 4th positional/keyword arg"
      pattern: "_route_matches\\(state, merged_origin, merged_destination, merged_origin_hub_id\\)"
    - from: "_route_matches body"
      to: "state_hub local"
      via: "if origin_hub_id is not None else state.get('origin_hub_id')"
      pattern: "origin_hub_id if origin_hub_id is not None else state\\.get"
---

<objective>
Fix a stale-state read in `_route_matches` (backend/agent/nodes/planner.py:99-126): the cache-check predicate currently reads `state.get("origin_hub_id")` directly, but the caller (`planner_node`) has already computed the freshest hub value as `merged_origin_hub_id` (line 505 — the post-999.1-merge local that combines `parsed.origin_hub_id` from THIS turn's prose extraction with prior state via the null-only coalesce). On prose-override turns ("Ship 5kg from Bang Na to Nonthaburi" with dropdown on HQ Lat Krabang), `_route_matches` sees the stale `state.origin_hub_id="hq-lat-krabang"` and falsely matches a cached `(hq-lat-krabang, Nonthaburi)` route_data, skipping `route_agent` entirely and producing wrong distance / a missing `route_agent` trace entry.

Purpose: Surgical fix to the cache-key predicate. Same architectural family as quick-260514-vrc (response_node fresh-truth gate) — both close holes where AgentState fields meant to be turn-scoped behave thread-scoped because parsed values from THIS turn aren't yet visible in state when downstream functions read it directly.

Output:
- `_route_matches` with new optional 4th arg `origin_hub_id`; explicit param wins, state fallback preserved.
- 3 new tests pinning the fix + the backward-compat fallback path.
- Cross-link bullet appended to `.planning/debug/999.12-…md` under the existing "Related Fixes Shipped Mid-Freeze" section (added 2026-05-14 by quick-260514-vrc). 999.12 family now has 3 confirmed siblings; the post-demo `/gsd:debug` investigation should treat all of them as one cluster.
- ONE atomic commit per task (3 total) + a 4th wrap-up commit at the end with SUMMARY.md + STATE.md + this PLAN per the workflow convention. Orchestrator (not executor) pushes the branch + opens PR → develop after all commits land.
</objective>

<execution_context>
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/workflows/execute-plan.md
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@backend/agent/nodes/planner.py
@backend/tests/test_planner.py
@.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md

<interfaces>
<!-- The exact contract executor must follow. No codebase exploration needed. -->

CURRENT `_route_matches` signature (planner.py:99-101):
```python
def _route_matches(
    state: dict, origin: Optional[str], destination: Optional[str]
) -> bool:
```

CURRENT `_route_matches` body — the load-bearing line (planner.py:118):
```python
state_hub = state.get("origin_hub_id")
```

NEW signature (after Task 1):
```python
def _route_matches(
    state: dict,
    origin: Optional[str],
    destination: Optional[str],
    origin_hub_id: Optional[str] = None,
) -> bool:
```

NEW body line (after Task 1):
```python
state_hub = origin_hub_id if origin_hub_id is not None else state.get("origin_hub_id")
```

UPSTREAM CALLER context (planner.py:489-505) — the merged hub local already exists:
```python
# Phase 999.9 D-10 / Pitfall 2: 999.1 null-only merge for origin_hub_id.
merged_origin_hub_id = parsed.origin_hub_id or state.get("origin_hub_id")
```

CURRENT call sites needing the 4th arg:
- planner.py:542 — fan-out promotion guard
- planner.py:562 — D-12 cache-skip cascade (fetch_fuel branch)
- planner.py:570 — D-12 cache-skip cascade (fetch_route branch)

NEW call site shape (all 3):
```python
_route_matches(state, merged_origin, merged_destination, merged_origin_hub_id)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: BE fix — _route_matches accepts merged origin_hub_id</name>
  <files>backend/agent/nodes/planner.py</files>
  <behavior>
    After this task, _route_matches MUST:
    - Accept a 4th optional positional argument `origin_hub_id: Optional[str] = None`.
    - When called with `origin_hub_id != None`, use the passed value for the hub compare (NOT state.get("origin_hub_id")).
    - When called with the 4th arg omitted OR explicitly `None`, fall back to state.get("origin_hub_id") (backward compat — preserves all existing test behavior).
    - Otherwise behave identically to the current implementation (rd lookup, destination check, hub-and-hub OR legacy free-text origin compare semantics unchanged).

    The 3 in-file call sites (lines 542, 562, 570) MUST pass `merged_origin_hub_id` as the new 4th arg, picking up the fresh post-merge value computed at line 505.
  </behavior>
  <action>
    Open backend/agent/nodes/planner.py.

    1. Update the `_route_matches` signature at lines 99-101 to add a 4th optional arg:
       ```python
       def _route_matches(
           state: dict,
           origin: Optional[str],
           destination: Optional[str],
           origin_hub_id: Optional[str] = None,
       ) -> bool:
       ```

    2. Replace line 118 (`state_hub = state.get("origin_hub_id")`) with:
       ```python
       state_hub = origin_hub_id if origin_hub_id is not None else state.get("origin_hub_id")
       ```
       This makes the explicit parameter win when passed, falling back to state for backward compat (preserves the semantics every existing _route_matches caller relies on).

    3. Update the docstring (lines 102-112) so the "state.get('origin_hub_id')" reference is accurate AND notes that the explicit parameter overrides. Concretely: keep the existing two paragraphs but append a short third paragraph:
       ```
       The optional ``origin_hub_id`` argument lets callers override the
       state read with a freshly-merged hub value (e.g., ``merged_origin_hub_id``
       in ``planner_node`` after the 999.1 merge). When omitted or None, the
       function falls back to ``state.get("origin_hub_id")`` — preserving the
       pre-Phase-11 behaviour for any caller that does not yet supply the
       parameter. This closes the prose-override cache-leak: on turns where the
       LLM extracts a new ``origin_hub_id`` from prose but ``state.origin_hub_id``
       still holds the prior turn's value, the post-merge local is the only
       fresh-truth source.
       ```
       (Keep the existing docstring sentences verbatim above this — only append.)

    4. Update the 3 call sites in `planner_node` to pass `merged_origin_hub_id` as the 4th positional arg:
       - Line 542 (inside the fan-out promotion guard `if next_step in ("fetch_fuel", "fetch_route") and ... and not _route_matches(...)`):
         change
         ```python
         and not _route_matches(state, merged_origin, merged_destination)
         ```
         to
         ```python
         and not _route_matches(state, merged_origin, merged_destination, merged_origin_hub_id)
         ```
       - Line 562 (inside the D-12 fetch_fuel cache-skip cascade, `if _route_matches(...):`):
         change
         ```python
         if _route_matches(state, merged_origin, merged_destination):
         ```
         to
         ```python
         if _route_matches(state, merged_origin, merged_destination, merged_origin_hub_id):
         ```
       - Lines 570-572 (the elif on the fetch_route branch — note the original spans 2 source lines because the call wraps):
         change
         ```python
         elif next_step == "fetch_route" and _route_matches(
             state, merged_origin, merged_destination
         ):
         ```
         to
         ```python
         elif next_step == "fetch_route" and _route_matches(
             state, merged_origin, merged_destination, merged_origin_hub_id
         ):
         ```

    CRITICAL invariants — DO NOT change:
    - The hub-vs-legacy-origin branching logic at lines 120-126 (compare on rd_hub == state_hub when both sides have hub_ids; legacy free-text origin compare only when neither side has one).
    - The destination-None / route_data-None early-return guards at lines 113-115.
    - Any other planner logic — D-04 budget guard, D-02 retry, refusal branches, FIX-02 short-circuit, 999.1 merge, gap-1 followup null-out, gap-3 search short-circuit, 999.9 D-10 hub validation. All untouched.
    - The merged_origin_hub_id local at line 505 — it already has exactly the value we need.

    DO NOT bump v1.1.0 tag. DO NOT touch .env / .env.example. DO NOT modify data/raw/eppo_diesel_prices.csv.

    After the edit, run the planner-specific test file to confirm no existing test regressed:
    ```bash
    cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/test_planner.py -x -q 2>&1 | tail -30
    ```
    Existing tests MUST all stay green (the new tests are added in Task 2). The 2 pre-existing failures from the MAX_TOOL_CALLS_PER_TURN .env cap bump are unrelated and live in test_guard_input.py / test_chat.py — NOT test_planner.py. test_planner.py should be 100% green.

    Then commit the source change as a single atomic commit:
    ```bash
    cd /Users/pollot/Desktop/express-dynamic-workflow && git add backend/agent/nodes/planner.py && git commit -m "$(cat <<'EOF'
fix(quick-260514-wgg): _route_matches accepts merged origin_hub_id

The cache-check predicate at planner.py:99-126 was reading
state.get("origin_hub_id") directly, but the caller has already computed
the freshest hub value as merged_origin_hub_id (line 505 — the
post-999.1-merge local that combines parsed.origin_hub_id from this
turn's prose with prior state).

On prose-override turns ("Ship 5kg from Bang Na to Nonthaburi" with
dropdown on HQ Lat Krabang), the cache-check saw the stale state hub
and falsely matched a cached (hq-lat-krabang, Nonthaburi) route_data,
skipping route_agent entirely. Trace panel was missing the route_agent
entry; distance was wrong; zone lookup happened to still produce the
correct central-1 result by coincidence.

Fix: _route_matches now accepts an optional 4th argument
origin_hub_id; the 3 in-file call sites pass merged_origin_hub_id.
State-backed fallback preserved when the parameter is omitted
(backward-compat for any external caller, though no such exists today).

Same family as quick-260514-vrc (response_node fresh-truth gate) — both
close holes where turn-scoped AgentState fields behave thread-scoped
because the parsed value from this turn is not yet visible in state when
a downstream helper reads it directly.

Does not bump v1.1.0 tag.
EOF
)"
    ```
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/test_planner.py -x -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    - `_route_matches` has 4-arg signature with `origin_hub_id: Optional[str] = None`.
    - Line 118 reads from `origin_hub_id` parameter with `state.get("origin_hub_id")` fallback.
    - All 3 call sites in `planner_node` pass `merged_origin_hub_id`.
    - Docstring updated to note the override semantics.
    - All existing `pytest backend/tests/test_planner.py` cases stay green.
    - Single atomic commit landed on branch `fix/quick-260514-wgg-route-matches-merged-hub`.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add 3 regression tests pinning the fix + backward-compat</name>
  <files>backend/tests/test_planner.py</files>
  <behavior>
    Three new tests added to backend/tests/test_planner.py, using the file's existing fixture/mocking conventions (`_user_state` helper, `monkeypatch.setattr(mod, "get_chat_model", lambda **_: _scripted_llm(...))` pattern, `FakeMessagesListChatModel`).

    1. `test_route_matches_uses_passed_origin_hub_id_over_state` — direct unit test. Imports `_route_matches` from `backend.agent.nodes.planner` (private but file convention is to test internal helpers — see `_fuel_fresh`-style usage patterns). Builds a minimal state with cached `route_data` for `(hq-lat-krabang, Nonthaburi)` AND state-level `origin_hub_id="hq-lat-krabang"`. Calls `_route_matches(state, None, "Nonthaburi", origin_hub_id="branch-bang-na")`. Asserts `False` (passed hub differs from rd.origin_hub_id → cache miss). This is the load-bearing pin: it would fail against the pre-fix code where state_hub was read from state.

    2. `test_planner_invokes_route_agent_on_prose_origin_override` — integration test. Pre-seeds state with cached route_data for `(hq-lat-krabang, Nonthaburi)` AND fresh fuel_data AND state.origin_hub_id="hq-lat-krabang" (the dropdown selection). User message: "Ship 5kg bounce from Bang Na to Nonthaburi". Mocks the planner LLM to emit `parsed.origin_hub_id="branch-bang-na"` (prose override). Runs `planner_node`. Asserts `result["next_step"]` is `"fetch_route"` OR `"fanout_fuel_route"` — NOT `"calculate_price"`. Confirms the prose override invalidates the route cache end-to-end through the merged_origin_hub_id pass-through.

    3. `test_route_matches_falls_back_to_state_when_param_omitted` — backward-compat. Calls `_route_matches(state, None, "Nonthaburi")` WITHOUT the 4th arg. State has matching `origin_hub_id="hq-lat-krabang"` AND `route_data={"destination": "Nonthaburi", "origin_hub_id": "hq-lat-krabang", ...}`. Asserts `True` (cache hit). This exercises the `else state.get("origin_hub_id")` fallback branch and pins the backward-compat invariant.

    All 3 tests pass with the Task 1 source edit applied. All existing test_planner.py tests stay green.
  </behavior>
  <action>
    Open backend/tests/test_planner.py.

    Append the 3 new tests at the END of the file (after the existing `test_tool_call_count_reducer_aggregates_parallel_writes` block ending at line 1651). Use the existing `_user_state` helper and `_scripted_llm` helper already defined at lines 32 and 26 respectively.

    Add the import for the helper at the top of the new block if needed:
    ```python
    from backend.agent.nodes.planner import _route_matches
    ```
    (Note: `_route_matches` is a private helper, but the file already exercises internal helpers via the `mod` alias for `get_chat_model` patching. Direct import is consistent with the codebase convention for unit-testing private helpers.)

    Then append this complete block:

    ```python


    # ---------------------------------------------------------------------------
    # Phase 11.5 / quick-260514-wgg — _route_matches reads merged hub from caller
    #
    # The cache-check predicate at planner.py:99-126 used to read
    # state.get("origin_hub_id") directly, but the caller has already computed
    # merged_origin_hub_id (line 505 — the post-999.1-merge local that combines
    # parsed.origin_hub_id from THIS turn's prose with prior state). On
    # prose-override turns ("Ship 5kg from Bang Na to Nonthaburi" with dropdown
    # on HQ Lat Krabang), the predicate falsely matched a cached
    # (hq-lat-krabang, Nonthaburi) route_data and skipped route_agent.
    # Fix: _route_matches accepts an optional 4th arg origin_hub_id; all 3
    # in-file call sites pass merged_origin_hub_id. Backward-compat fallback
    # to state.get("origin_hub_id") is preserved when the parameter is omitted.
    #
    # Same family as quick-260514-vrc (response_node fresh-truth gate) — both
    # close holes where turn-scoped AgentState fields behave thread-scoped.
    # ---------------------------------------------------------------------------

    from backend.agent.nodes.planner import _route_matches  # noqa: E402


    def test_route_matches_uses_passed_origin_hub_id_over_state():
        """Pinning test for the prose-override cache leak.

        With state.origin_hub_id == route_data.origin_hub_id == 'hq-lat-krabang'
        but caller passes origin_hub_id='branch-bang-na', the cache MUST miss.
        Pre-fix: state_hub = state.get('origin_hub_id') wins -> match -> bug.
        Post-fix: state_hub = passed param -> mismatch -> cache miss.
        """
        state = {
            "origin_hub_id": "hq-lat-krabang",
            "route_data": {
                "origin": "Bangkok",
                "destination": "Nonthaburi",
                "origin_hub_id": "hq-lat-krabang",
                "distance_km": 18.5,
                "duration_min": 30,
                "traffic_severity": 2,
                "zone": "central-1",
            },
        }
        # Passing a different hub MUST invalidate the cache check.
        assert _route_matches(
            state, None, "Nonthaburi", origin_hub_id="branch-bang-na"
        ) is False


    def test_route_matches_falls_back_to_state_when_param_omitted():
        """Backward-compat: when the 4th arg is omitted, _route_matches falls
        back to state.get('origin_hub_id'). With matching state + route_data,
        the cache MUST hit.

        Exercises the `else state.get("origin_hub_id")` fallback branch of
        `state_hub = origin_hub_id if origin_hub_id is not None else state.get(...)`.
        Pins the invariant so a future refactor can't silently break callers
        that do not yet pass the parameter.
        """
        state = {
            "origin_hub_id": "hq-lat-krabang",
            "route_data": {
                "origin": "Bangkok",
                "destination": "Nonthaburi",
                "origin_hub_id": "hq-lat-krabang",
                "distance_km": 18.5,
                "duration_min": 30,
                "traffic_severity": 2,
                "zone": "central-1",
            },
        }
        # No 4th arg — falls back to state. Same hub on both sides -> hit.
        assert _route_matches(state, None, "Nonthaburi") is True


    def test_planner_invokes_route_agent_on_prose_origin_override(monkeypatch):
        """Integration test for the prose-override cache leak end-to-end.

        Setup: dropdown is on 'hq-lat-krabang'; prior turn cached a route for
        (hq-lat-krabang, Nonthaburi); fuel is also fresh. User's prose says
        'Ship 5kg bounce from Bang Na to Nonthaburi' and the LLM correctly
        extracts origin_hub_id='branch-bang-na'.

        Expected: planner_node must NOT route to calculate_price (which would
        reuse the stale hq-lat-krabang route). It must route to fetch_route
        (or fanout_fuel_route depending on the cascade ordering) so the route
        is recomputed for the new origin hub.

        Pre-fix: cache predicate saw state.origin_hub_id='hq-lat-krabang' and
        matched the cached rd.origin_hub_id, routing to calculate_price.
        Post-fix: predicate sees merged_origin_hub_id='branch-bang-na' and
        misses, routing to fetch_route.
        """
        state = _user_state(
            "Ship 5kg bounce from Bang Na to Nonthaburi",
            shipping_type="bounce",  # FIX-02 short-circuit guard: prior logistics field
            weight_kg=15.0,           # carried over from a prior surcharge turn
            origin="Bangkok",
            destination="Nonthaburi",
            origin_hub_id="hq-lat-krabang",  # dropdown selection (prior turn)
            fuel_data={
                "price": 31.0,
                "baseline": 29.94,
                "delta_pct": 0.0354,
                "date": "2026-05-14",
                "unit": "THB/L",
                "source": "eppo_live",
                "fetched_at": _now_iso_z(),
            },
            route_data={
                "origin": "Bangkok",
                "destination": "Nonthaburi",
                "origin_hub_id": "hq-lat-krabang",  # CACHED for the OLD hub
                "distance_km": 18.5,
                "duration_min": 30,
                "traffic_severity": 2,
                "zone": "central-1",
            },
        )
        monkeypatch.setattr(
            mod,
            "get_chat_model",
            lambda **_: _scripted_llm(
                '{"user_intent": "surcharge_query", '
                '"shipping_type": "bounce", "weight_kg": 5, '
                '"origin": "Bang Na", "destination": "Nonthaburi", '
                '"origin_hub_id": "branch-bang-na", '
                '"missing_fields": [], '
                '"next_step": "fetch_fuel", '
                '"clarification_reason": null}'
            ),
        )

        result = planner_node(state)

        # The prose override picked up branch-bang-na; the cached route is for
        # hq-lat-krabang. Cache MUST miss -> route_agent re-invoked.
        # Acceptable post-fix next_steps: fetch_route (fuel is fresh) OR
        # fanout_fuel_route (if the cache-skip cascade is bypassed for any
        # reason). NOT calculate_price (that would mean the cache hit).
        assert result["next_step"] in ("fetch_route", "fanout_fuel_route"), (
            f"prose-override cache leak: expected re-route to route_agent, "
            f"got next_step={result['next_step']!r}"
        )
        # And the merged hub surfaces correctly downstream.
        assert result["origin_hub_id"] == "branch-bang-na"
    ```

    Important: the existing tests at the top of the file already do `from backend.agent.nodes import planner as mod` (line 18) and `from backend.agent.nodes.planner import planner_node` (line 19). The new `_route_matches` import can either go at the top of the file (alongside the others) OR inline at the new block (the `# noqa: E402` form shown above suppresses the late-import lint warning). Inline is preferred to keep the diff localized.

    After adding the tests, run the full planner test suite to confirm all pass:
    ```bash
    cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/test_planner.py -x -q 2>&1 | tail -20
    ```

    Then run the full backend test suite to confirm nothing else regressed:
    ```bash
    cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/ -q 2>&1 | tail -30
    ```

    The 2 pre-existing failures in `test_guard_input.py` / `test_chat.py` from the MAX_TOOL_CALLS_PER_TURN .env cap bump are unrelated and expected. ALL other tests (~360+) MUST stay green. If a test_planner.py test fails OR a previously-green test elsewhere starts failing, STOP and report — do not commit.

    Then commit the test additions:
    ```bash
    cd /Users/pollot/Desktop/express-dynamic-workflow && git add backend/tests/test_planner.py && git commit -m "$(cat <<'EOF'
test(quick-260514-wgg): pin _route_matches merged-hub fix + backward-compat

Three regression tests added at the end of backend/tests/test_planner.py:

1. test_route_matches_uses_passed_origin_hub_id_over_state — direct unit
   test on _route_matches. State has matching origin_hub_id +
   route_data.origin_hub_id; caller passes a different hub via the new
   4th arg. Asserts False (cache miss). Pre-fix code would return True
   because state_hub was read from state. This is the load-bearing pin.

2. test_route_matches_falls_back_to_state_when_param_omitted —
   backward-compat. Omits the 4th arg; state has matching hub. Asserts
   True. Exercises the `else state.get("origin_hub_id")` fallback so a
   future refactor can't silently break callers that don't pass the
   param.

3. test_planner_invokes_route_agent_on_prose_origin_override —
   integration test. Dropdown on hq-lat-krabang, cached
   (hq-lat-krabang, Nonthaburi) route_data, fresh fuel_data; user prose
   says "from Bang Na", LLM extracts origin_hub_id="branch-bang-na".
   Asserts result["next_step"] in ("fetch_route", "fanout_fuel_route")
   — NOT "calculate_price". Confirms the merged_origin_hub_id pass-
   through invalidates the route cache end-to-end.

All existing test_planner.py tests still green. The 2 pre-existing
backend-suite failures from the MAX_TOOL_CALLS_PER_TURN .env cap bump
(test_guard_input.py / test_chat.py) are unrelated and expected.
EOF
)"
    ```
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/test_planner.py::test_route_matches_uses_passed_origin_hub_id_over_state backend/tests/test_planner.py::test_route_matches_falls_back_to_state_when_param_omitted backend/tests/test_planner.py::test_planner_invokes_route_agent_on_prose_origin_override -v 2>&1 | tail -20</automated>
  </verify>
  <done>
    - All 3 new tests exist in backend/tests/test_planner.py.
    - All 3 new tests PASS (green).
    - All pre-existing test_planner.py tests stay green.
    - Full backend suite has no NEW failures beyond the 2 known MAX_TOOL_CALLS_PER_TURN-related failures in test_guard_input.py / test_chat.py.
    - Single atomic commit landed on branch `fix/quick-260514-wgg-route-matches-merged-hub`.
  </done>
</task>

<task type="auto">
  <name>Task 3: Cross-link to 999.12 family</name>
  <files>.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md</files>
  <action>
    Open .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md.

    Find the existing "## Related Fixes Shipped Mid-Freeze" section near the end (added 2026-05-14 by quick-260514-vrc — currently the section contains exactly one bullet about the response_node fresh-truth gate at line 159 of the file).

    Append a NEW bullet AFTER the existing quick-260514-vrc bullet. Preserve the existing section header (`## Related Fixes Shipped Mid-Freeze`) and the existing vrc bullet verbatim. Insert the new bullet on a fresh blank line below the existing one. The new bullet:

    ```markdown

    - **2026-05-14 — `_route_matches` cache-key reads merged hub (quick-260514-wgg):** Same architectural pattern, different surface — `_route_matches` was reading `state.get("origin_hub_id")` inside the cache-check predicate while the caller had already computed the freshest hub value via the post-merge `merged_origin_hub_id` local. On prose-override turns ("Ship 5kg from Bang Na to Nonthaburi" with dropdown on HQ Lat Krabang), the cache check saw the stale state hub and falsely matched, skipping `route_agent` entirely. Trace panel showed missing route_agent entry; distance was wrong; rate lookup happened to still produce the correct zone result by coincidence (central-1 → central-1 either way). Fix: `_route_matches` now accepts `origin_hub_id` as an explicit parameter; 3 call sites pass `merged_origin_hub_id`. State backed-fallback preserved when parameter omitted (backward compat).

      999.12 family now has 3 confirmed siblings: duplicate `message_id`, response_node fresh-truth gate (quick-260514-vrc), and this `_route_matches` cache-key fix (quick-260514-wgg). Common pattern: **AgentState fields meant to be turn-scoped behave as thread-scoped because parsed values from this turn aren't yet visible in state when downstream functions read it directly.** The post-demo `/gsd:debug` investigation should treat all four as one cluster.
    ```

    Note the indentation on the second paragraph (4 spaces, aligned with the bullet's continuation) — this is the same style the existing vrc bullet uses for its second paragraph at line 161.

    Save the file. Verify only this one section was modified by running git diff and inspecting that no other content changed:
    ```bash
    cd /Users/pollot/Desktop/express-dynamic-workflow && git diff --stat .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md
    ```
    The diff should show exactly an addition with NO deletions (it's a pure append within the section).

    Then commit the doc change:
    ```bash
    cd /Users/pollot/Desktop/express-dynamic-workflow && git add .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md && git commit -m "$(cat <<'EOF'
docs(quick-260514-wgg): cross-link _route_matches fix to 999.12 family

Append a new bullet under .planning/debug/999.12-...'s "Related Fixes
Shipped Mid-Freeze" section (added 2026-05-14 by quick-260514-vrc). The
999.12 family now has three confirmed siblings:

  1. Duplicate message_id (the open 999.12 deferred investigation)
  2. response_node fresh-truth gate (quick-260514-vrc, 2026-05-14)
  3. _route_matches cache-key reads merged hub (this fix, 2026-05-14)

Common pattern flagged for the post-demo /gsd:debug investigation:
AgentState fields meant to be turn-scoped behave as thread-scoped
because parsed values from this turn aren't yet visible in state when
downstream functions read it directly. All four likely share an
architectural cause around how AgentState fields persist across turn
boundaries — worth investigating as one cluster.

No state mutation. No code change in this commit (source + tests
shipped in the two preceding commits on this branch).
EOF
)"
    ```
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && grep -c "quick-260514-wgg" .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md</automated>
  </verify>
  <done>
    - The "Related Fixes Shipped Mid-Freeze" section in .planning/debug/999.12-…md contains 2 bullets (the existing vrc bullet + the new wgg bullet).
    - The new bullet references quick-260514-wgg and includes the "999.12 family now has 3 confirmed siblings" architectural framing.
    - No other content in the 999.12 file was modified.
    - Single atomic commit landed on branch `fix/quick-260514-wgg-route-matches-merged-hub`.
  </done>
</task>

<task type="auto">
  <name>Task 4: Wrap-up — SUMMARY + STATE + PLAN commit</name>
  <files>.planning/quick/260514-wgg-fix-route-matches-cache-check-accept-mer/260514-wgg-SUMMARY.md, .planning/STATE.md, .planning/quick/260514-wgg-fix-route-matches-cache-check-accept-mer/260514-wgg-PLAN.md</files>
  <action>
    1. Create the quick-task SUMMARY at `.planning/quick/260514-wgg-fix-route-matches-cache-check-accept-mer/260514-wgg-SUMMARY.md` using the Write tool. Follow the style of recent quick-task summaries (per memory: the SUMMARY captures what shipped, key files, test results, and orchestrator handoff notes). Suggested content:

       ```markdown
       ---
       quick_id: 260514-wgg
       branch: fix/quick-260514-wgg-route-matches-merged-hub
       completed: 2026-05-14
       commits: 3 source/test/doc + 1 wrap-up
       sibling_family: 999.12 (3 confirmed siblings)
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

       - **`backend/agent/nodes/planner.py`** — `_route_matches` now accepts an
         optional 4th arg `origin_hub_id: Optional[str] = None`. Inside, the
         hub-compare reads from the passed param when non-None, falling back to
         `state.get("origin_hub_id")` for backward compat. All 3 in-file call sites
         (lines 542, 562, 570) pass `merged_origin_hub_id`.

       - **`backend/tests/test_planner.py`** — 3 new tests appended:
         1. `test_route_matches_uses_passed_origin_hub_id_over_state` — direct unit
            pin: passed hub overrides state.
         2. `test_route_matches_falls_back_to_state_when_param_omitted` — backward
            compat pin.
         3. `test_planner_invokes_route_agent_on_prose_origin_override` —
            end-to-end: prose override invalidates route cache, re-invokes
            route_agent.

       - **`.planning/debug/999.12-...md`** — appended a cross-link bullet under
         "Related Fixes Shipped Mid-Freeze"; 999.12 family now has 3 confirmed
         siblings. Common pattern: AgentState fields meant to be turn-scoped behave
         thread-scoped because this turn's parsed values aren't yet visible in
         state when downstream helpers read it directly. Post-demo `/gsd:debug`
         should treat all four as one cluster.

       ## Verification

       - `pytest backend/tests/test_planner.py` — all green, including the 3 new
         tests.
       - Full backend suite — no NEW failures beyond the 2 pre-existing
         MAX_TOOL_CALLS_PER_TURN-related failures in `test_guard_input.py` /
         `test_chat.py` (.env cap bump; unrelated).

       ## Out of Scope / Did NOT Change

       - v1.1.0 tag (NOT bumped — fix lives on a feature branch off develop).
       - `.env` / `.env.example`.
       - `data/raw/eppo_diesel_prices.csv` (unstaged refresh; intentionally left
         alone).
       - `.planning/ROADMAP.md`.
       - Any other planner logic — D-04 budget guard, D-02 retry, refusal branches,
         FIX-02 short-circuit, 999.1 merge, gap-1 followup null-out, gap-3 search
         short-circuit, 999.9 D-10 hub validation — all untouched.

       ## Orchestrator Handoff

       Branch `fix/quick-260514-wgg-route-matches-merged-hub` ready for push + PR
       → develop. After merge, restart uvicorn for live re-verification of the
       prose-override turn ("Ship 5kg bounce from Bang Na to Nonthaburi" with
       dropdown on HQ Lat Krabang). Expected: trace panel shows route_agent entry;
       distance reflects the Bang Na origin; no zone change (still central-1, by
       coincidence — both origins are in central-1).

       ## Sibling Family Status

       999.12 cluster (post-W6-demo `/gsd:debug` scope):
       - Duplicate `message_id` (the open 999.12 deferred investigation)
       - response_node fresh-truth gate (quick-260514-vrc, 2026-05-14)
       - `_route_matches` cache-key merged hub (this fix, 2026-05-14)
       ```

    2. Update `.planning/STATE.md` to reflect the new last activity. Concretely:
       - Update the `stopped_at:` frontmatter field to mention this quick task (append to the existing v1.1 + vrc note).
       - Update `last_updated:` to a fresh ISO-8601 timestamp (use `date -u +"%Y-%m-%dT%H:%M:%S.000Z"` if needed, or just bump to 2026-05-14T19:00:00.000Z if no fresher info available — the exact minute does not matter, just that it's after the vrc timestamp 17:30:00).
       - Update `last_activity:` to: `2026-05-14 — Completed quick task 260514-wgg: _route_matches accepts merged origin_hub_id (sibling state-leak fix in 999.12 cluster)`.
       - Update the matching "Last activity:" line in the "Current Position" body section (around line 32) to the same value.

       Read the file first via the Read tool, then use Edit (NOT Write — only frontmatter + 1 body line change). DO NOT modify any other content (the metrics tables, the progress counters, etc. — all untouched).

    3. Commit all three files in a single wrap-up commit:
       ```bash
       cd /Users/pollot/Desktop/express-dynamic-workflow && git add .planning/quick/260514-wgg-fix-route-matches-cache-check-accept-mer/260514-wgg-SUMMARY.md .planning/quick/260514-wgg-fix-route-matches-cache-check-accept-mer/260514-wgg-PLAN.md .planning/STATE.md && git commit -m "$(cat <<'EOF'
docs(quick-260514-wgg): close _route_matches merged-hub fix (SUMMARY + STATE)

Wrap-up commit for quick task 260514-wgg. Three source/test/doc commits
shipped earlier on this branch:

  - fix(quick-260514-wgg): _route_matches accepts merged origin_hub_id
  - test(quick-260514-wgg): pin _route_matches merged-hub fix + backward-compat
  - docs(quick-260514-wgg): cross-link _route_matches fix to 999.12 family

This commit adds the quick-task SUMMARY.md, archives the PLAN.md
alongside it, and updates STATE.md last_activity + stopped_at. Branch
fix/quick-260514-wgg-route-matches-merged-hub ready for push + PR ->
develop.

Does not bump v1.1.0 tag.
EOF
)"
       ```

    4. Verify the commit landed by running `git log -4 --oneline` and confirming the 4 commits on this branch in order:
       ```
       <hash> docs(quick-260514-wgg): close _route_matches merged-hub fix (SUMMARY + STATE)
       <hash> docs(quick-260514-wgg): cross-link _route_matches fix to 999.12 family
       <hash> test(quick-260514-wgg): pin _route_matches merged-hub fix + backward-compat
       <hash> fix(quick-260514-wgg): _route_matches accepts merged origin_hub_id
       ```

    DO NOT push the branch. DO NOT open a PR. The orchestrator handles push + PR creation after this plan completes.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && git log -4 --oneline 2>&1 | grep -c "quick-260514-wgg"</automated>
  </verify>
  <done>
    - `.planning/quick/260514-wgg-fix-route-matches-cache-check-accept-mer/260514-wgg-SUMMARY.md` exists with the documented frontmatter + sections.
    - `.planning/STATE.md` `last_activity`, `last_updated`, and `stopped_at` reflect the new quick task; no other STATE.md content modified.
    - 4 commits on branch `fix/quick-260514-wgg-route-matches-merged-hub`, all tagged with `quick-260514-wgg` in their subject.
    - Branch NOT pushed; PR NOT opened (orchestrator's job).
  </done>
</task>

</tasks>

<verification>
End-to-end:

1. `python -m pytest backend/tests/test_planner.py -v 2>&1 | tail -30` — full planner suite green, including the 3 new tests added in Task 2.

2. `python -m pytest backend/tests/ -q 2>&1 | tail -10` — full backend suite has no NEW failures (2 pre-existing MAX_TOOL_CALLS_PER_TURN failures in `test_guard_input.py` / `test_chat.py` are expected and unrelated).

3. `git log -4 --oneline` shows 4 commits on `fix/quick-260514-wgg-route-matches-merged-hub`, all subjects begin with `fix(quick-260514-wgg)`, `test(quick-260514-wgg)`, `docs(quick-260514-wgg)`, or `docs(quick-260514-wgg)`.

4. `grep -c "quick-260514-wgg" .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md` returns ≥ 2 (one in the bullet header, one in the architectural framing paragraph).

5. `git diff develop..fix/quick-260514-wgg-route-matches-merged-hub --stat` shows changes ONLY in:
   - `backend/agent/nodes/planner.py`
   - `backend/tests/test_planner.py`
   - `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`
   - `.planning/quick/260514-wgg-fix-route-matches-cache-check-accept-mer/260514-wgg-SUMMARY.md`
   - `.planning/quick/260514-wgg-fix-route-matches-cache-check-accept-mer/260514-wgg-PLAN.md`
   - `.planning/STATE.md`

   And NOT in:
   - `.env`, `.env.example`
   - `data/raw/eppo_diesel_prices.csv`
   - `.planning/ROADMAP.md`
   - Any other file
</verification>

<success_criteria>
- `_route_matches` has the 4-arg signature; explicit param wins over state; state fallback preserved.
- 3 new test_planner.py tests pass; all existing test_planner.py tests still pass.
- 999.12 debug file has the new cross-link bullet under "Related Fixes Shipped Mid-Freeze".
- 4 commits on branch `fix/quick-260514-wgg-route-matches-merged-hub`, in the order: fix → test → docs → docs-wrap.
- v1.1.0 tag NOT bumped. `.env` NOT touched. `data/raw/eppo_diesel_prices.csv` NOT touched. `.planning/ROADMAP.md` NOT touched.
- SUMMARY.md exists in the quick-task directory.
- STATE.md `last_activity` updated; nothing else in STATE.md modified.
- Branch NOT pushed; PR NOT opened (orchestrator does this next).
</success_criteria>

<output>
After completion, the quick-task summary lives at:
`.planning/quick/260514-wgg-fix-route-matches-cache-check-accept-mer/260514-wgg-SUMMARY.md`

Orchestrator next steps (out of executor scope):
1. `git push -u origin fix/quick-260514-wgg-route-matches-merged-hub`
2. `gh pr create --base develop --title "fix(quick-260514-wgg): _route_matches accepts merged origin_hub_id" --body "..."`
3. After merge → develop, restart uvicorn for live verification of the prose-override turn.
</output>
