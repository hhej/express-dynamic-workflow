---
phase: quick-260425-vyj
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/agent/nodes/planner.py
  - backend/tests/test_planner.py
  - backend/tests/test_graph.py
  - .planning/ROADMAP.md
autonomous: true
requirements:
  - BUG-999.1
  - BUG-999.3
must_haves:
  truths:
    - "On a follow-up turn that mentions only one of the four extraction fields (e.g. switches shipping_type), the planner does NOT emit next_step=clarify when prior state already has the unmentioned fields."
    - "After the D-12 cache-aware override mutates the local next_step, the trace entry's tool_output.next_step matches the actual routed step (not the pre-override LLM emission)."
    - "After the merge, the trace entry's tool_output.shipping_type / weight_kg / origin / destination / missing_fields reflect the merged values returned to the graph (not the raw LLM emission)."
    - "All 103 existing backend tests still pass after the fix."
    - "At least one new pytest test fails on the unfixed planner.py and passes after the fix for bug 999.1 (state merge on follow-up)."
    - "At least one new pytest test fails on the unfixed planner.py and passes after the fix for bug 999.3 (trace narration matches routed step)."
  artifacts:
    - path: "backend/agent/nodes/planner.py"
      provides: "Post-merge recompute of missing_fields + next_step; trace tool_output reflects post-override merged values."
      contains: "merged_shipping"
    - path: "backend/tests/test_planner.py"
      provides: "Unit regression tests for 999.1 (state merge promotes clarify->fetch_*) and 999.3 (trace next_step matches override)."
      contains: "test_followup_merges_prior_state"
    - path: "backend/tests/test_graph.py"
      provides: "E2E regression test for 999.1 covering parameter-switch follow-up on the same thread_id."
      contains: "test_followup_param_switch"
    - path: ".planning/ROADMAP.md"
      provides: "Backlog entries for 999.1 and 999.3 marked Resolved 2026-04-25."
      contains: "999.1"
  key_links:
    - from: "backend/agent/nodes/planner.py merge block (lines ~200-213)"
      to: "next_step / missing_fields recompute"
      via: "merged_* locals computed BEFORE the trace dict is built and BEFORE the return"
      pattern: "merged_shipping|merged_weight|merged_origin|merged_destination"
    - from: "backend/agent/nodes/planner.py trace entry tool_output"
      to: "post-override next_step + merged extraction fields"
      via: "explicit dict construction (not parsed.model_dump())"
      pattern: "tool_output.*next_step"
    - from: "backend/tests/test_graph.py follow-up test"
      to: "in_memory_checkpointer fixture from conftest.py"
      via: "graph.ainvoke with same thread_id across two turns"
      pattern: "in_memory_checkpointer"
---

<objective>
Fix two related planner narration / state-handling bugs surfaced by live smoke testing on 2026-04-25:

- **999.1 (HIGH IMPACT)** — `planner_node` invokes the LLM with only the latest user message, so on follow-up turns the LLM emits `null` for unmentioned fields, populates `missing_fields`, and emits `next_step=clarify`. The post-LLM merge (`parsed.X or state.get("X")`) fills in extraction fields after the fact, but `next_step` and `missing_fields` were already decided based only on the new message. Result: parameter-switch follow-ups (e.g. "What if I switched it to a Bounce shipment instead?") incorrectly route to `clarify` instead of through `fetch_route`/`fetch_fuel`/`calculate_price`.

- **999.3 (LOW IMPACT — narration only)** — The trace entry emits `parsed.model_dump()` as `tool_output`, which contains the pre-override `next_step` (and the un-merged extraction fields). The graph routes on the post-override `next_step`, so the trace panel shows a stale value that does not match what actually ran.

Purpose: restore the D-12 cache-skip UX promise on parameter-change follow-ups, and make the reasoning trace honestly reflect what the graph routed.

Output:
- `backend/agent/nodes/planner.py` updated with post-merge recompute (option b) and a corrected trace `tool_output`
- `backend/tests/test_planner.py` updated with two new regression tests
- `backend/tests/test_graph.py` updated with one new E2E follow-up test
- `.planning/ROADMAP.md` Backlog section updated marking 999.1 and 999.3 Resolved
</objective>

<execution_context>
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/workflows/execute-plan.md
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@backend/agent/nodes/planner.py
@backend/agent/prompts/planner.py
@backend/tests/test_planner.py
@backend/tests/test_graph.py
@backend/tests/conftest.py
@.planning/ROADMAP.md

<interfaces>
<!-- Key contracts the executor needs. Extracted from the codebase. -->

From backend/agent/nodes/planner.py:
```python
class PlannerOutput(BaseModel):
    user_intent: Literal["surcharge_query", "followup_query", "clarification", "out_of_scope"]
    shipping_type: Optional[str] = None
    weight_kg: Optional[float] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    next_step: Literal["fetch_fuel", "fetch_route", "calculate_price",
                       "clarify", "respond", "search_context"]
    clarification_reason: Optional[str] = None

def planner_node(state: dict) -> dict: ...
def _fuel_fresh(state: dict) -> bool: ...
def _route_matches(state: dict, origin: Optional[str], destination: Optional[str]) -> bool: ...
```

From backend/tests/test_planner.py (existing patterns):
```python
def _scripted_llm(*responses_json: str) -> FakeMessagesListChatModel: ...
def _user_state(content: str, **overrides) -> dict: ...
# monkeypatch.setattr(mod, "get_chat_model", lambda **_: _scripted_llm(...))
```

From backend/tests/test_graph.py (existing E2E patterns):
```python
def _stateful_factory(*responses_json: str): ...      # shared FakeMessagesListChatModel
def _planner_response(next_step, *, shipping_type=..., weight_kg=..., ...) -> str: ...
def _empty_state(message: str) -> dict: ...
# graph = build_graph(checkpointer=in_memory_checkpointer)
# cfg = {"configurable": {"thread_id": "t-X"}}
# await graph.ainvoke(state, config=cfg)
```

From backend/tests/conftest.py:
```python
@pytest_asyncio.fixture
async def in_memory_checkpointer():
    """AsyncSqliteSaver backed by an in-memory SQLite DB. Required for thread_id reuse across ainvoke calls."""
```

Existing call sites that depend on `tool_output` shape (verify before changing):
- `backend/tests/test_planner.py` — currently asserts only `result["reasoning_trace"][0]["agent"] == "planner"`; does NOT inspect tool_output keys, so re-shaping tool_output is safe for these.
- `backend/tests/test_graph.py` — does NOT inspect planner trace tool_output anywhere (greps for tool_output return zero hits in this file).
</interfaces>

## Design Decision: Option (b) — post-process recompute (chosen)

The task spec offers two fix shapes for 999.1:

- **Option (a)**: inject prior state into the LLM prompt context so the LLM sees `state.shipping_type`/`weight_kg`/etc. and can correctly decide `next_step` itself.
- **Option (b)**: after the existing `parsed.X or state.get("X")` merge, recompute `missing_fields` and `next_step` from the merged values; if the LLM said `clarify` but the merge actually has all fields, promote `next_step` to the appropriate fetch step and let the existing D-12 cache-aware override block (lines 184-198) handle cache skipping.

**Decision: Option (b).** Rationale:

1. **Smaller blast radius** — option (a) requires changing `SYSTEM_PROMPT` (adds D-XX risk of LLM regression on the existing 5 unit tests) and changing the LLM call site to pass `state` summary into the message list. Option (b) is a 10-15 line patch entirely inside `planner_node` after `parsed` is validated.
2. **No token cost increase** — option (a) inflates every planner LLM call with prior-state JSON; option (b) keeps the prompt unchanged.
3. **Deterministic** — option (b) uses pure Python conditionals on already-validated values; option (a) trusts the LLM to do the right thing with the extra context (and the LLM is the thing currently getting it wrong).
4. **Backward compatible with existing 5 planner unit tests** — none of them set prior `state.shipping_type`/`weight_kg`/`origin`/`destination`, so the merge produces the same values the LLM emitted, and the recompute produces the same `next_step`. All existing tests continue to pass unchanged.

Option (a) is documented here as a future possibility if the LLM-emitted `user_intent` field becomes unreliable on follow-ups (currently outside the bug scope).

## Recompute logic (must replicate exactly)

```python
# After: parsed = ... (validated PlannerOutput)
# Replace the existing merge block (lines 200-213) with:

merged_shipping = parsed.shipping_type or state.get("shipping_type")
merged_weight = (
    parsed.weight_kg
    if parsed.weight_kg is not None
    else state.get("weight_kg")
)
merged_origin = parsed.origin or state.get("origin")
merged_destination = parsed.destination or state.get("destination")

# 999.1 fix: recompute missing_fields from merged values, not from LLM emission.
missing: list[str] = []
if not merged_shipping:
    missing.append("shipping_type")
if merged_weight is None:
    missing.append("weight_kg")
if not merged_origin:
    missing.append("origin")
if not merged_destination:
    missing.append("destination")

# 999.1 fix: if LLM said clarify but merge fills all gaps, promote next_step
# to fetch_fuel — the existing D-12 cache-aware override below will then
# advance further (fetch_route / calculate_price) based on cache state.
next_step = parsed.next_step
if next_step == "clarify" and not missing:
    next_step = "fetch_fuel"

# Existing D-12 cache-aware override block runs on next_step (which may now
# be the LLM's value OR the promoted "fetch_fuel"). Use merged_origin /
# merged_destination — NOT parsed.origin/destination — for _route_matches
# so cache hits work on follow-ups where origin/destination were inherited.
if next_step == "fetch_fuel" and _fuel_fresh(state):
    if _route_matches(state, merged_origin, merged_destination):
        if merged_shipping and merged_weight is not None:
            next_step = "calculate_price"
        else:
            next_step = "clarify"
    else:
        next_step = "fetch_route"
elif next_step == "fetch_route" and _route_matches(
    state, merged_origin, merged_destination
):
    next_step = "calculate_price" if _fuel_fresh(state) else "fetch_fuel"
```

**Note on the D-12 block**: the existing implementation uses `parsed.origin` / `parsed.destination` in `_route_matches`. After the fix, those calls MUST use `merged_origin` / `merged_destination` so a follow-up that inherits origin/destination from prior state can still hit the route cache. Without this change, parameter-switch follow-ups would get stuck at `fetch_route` even when prior state has the matching `route_data`.

## Trace fix (999.3)

Replace `"tool_output": parsed.model_dump()` with:

```python
"tool_output": {
    "user_intent": parsed.user_intent,
    "shipping_type": merged_shipping,
    "weight_kg": merged_weight,
    "origin": merged_origin,
    "destination": merged_destination,
    "missing_fields": missing,
    "next_step": next_step,            # post-override value
    "clarification_reason": parsed.clarification_reason,
},
```

This makes the trace narration honest: every field shown is what the function actually returned to the graph, and `tool_output.next_step` matches what LangGraph routes on.

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix 999.1 + 999.3 in planner_node and add unit regression tests</name>
  <files>backend/agent/nodes/planner.py, backend/tests/test_planner.py</files>
  <behavior>
    New unit tests in test_planner.py:

    Test A — `test_followup_merges_prior_state_promotes_clarify_to_fetch`:
      - Setup: state has prior shipping_type="bounce", weight_kg=15, origin="Bangkok",
        destination="Pathum Thani"; user message "What if Retail Standard?"
      - Mock LLM returns: shipping_type="retail_standard", weight_kg=null, origin=null,
        destination=null, missing_fields=["weight_kg","origin","destination"],
        next_step="clarify", clarification_reason="missing_inputs", user_intent="followup_query"
      - Assert: result["next_step"] == "fetch_fuel" (promoted; no caches in state)
      - Assert: result["missing_fields"] == [] (recomputed from merged values)
      - Assert: result["shipping_type"] == "retail_standard"
      - Assert: result["weight_kg"] == 15.0 (inherited)
      - Assert: result["origin"] == "Bangkok" (inherited)
      - Assert: result["destination"] == "Pathum Thani" (inherited)
      - This test FAILS on unfixed planner.py (gets next_step=clarify) and PASSES after fix.

    Test B — `test_followup_with_full_cache_routes_calculate_price`:
      - Setup: state has prior shipping_type, weight_kg, origin, destination AND fresh
        fuel_data (fetched_at=now) AND matching route_data (origin/destination match
        merged values).
      - Mock LLM returns the same clarify-with-nulls shape as Test A but with a
        different shipping_type (parameter switch).
      - Assert: result["next_step"] == "calculate_price" (D-12 cascade: clarify ->
        fetch_fuel promotion -> fuel_fresh skip -> route_matches skip -> calculate_price).
      - Asserts D-12 still works on top of the 999.1 promotion AND that _route_matches
        uses merged_origin/destination (not parsed.origin/destination).

    Test C — `test_trace_tool_output_reflects_post_override_next_step` (999.3):
      - Setup: state with fresh fuel_data (fetched_at=now); LLM emits next_step="fetch_fuel"
        with valid parsed extraction fields. D-12 overrides to fetch_route (route not
        cached).
      - Assert: result["next_step"] == "fetch_route"
      - Assert: result["reasoning_trace"][0]["tool_output"]["next_step"] == "fetch_route"
        (NOT "fetch_fuel" — this is the bug fix)
      - Assert: result["reasoning_trace"][0]["tool_output"]["shipping_type"] reflects
        the merged (==parsed for this case) value.
      - This test FAILS on unfixed planner.py (tool_output.next_step == "fetch_fuel")
        and PASSES after fix.

    Test D — `test_trace_tool_output_reflects_merged_inherited_fields` (999.3 + 999.1):
      - Setup: state has prior weight_kg=15; user message "Bounce Bangkok to Nonthaburi"
      - Mock LLM emits weight_kg=null + missing_fields=["weight_kg"] + next_step="clarify"
      - Assert: result["next_step"] == "fetch_fuel" (promoted)
      - Assert: result["reasoning_trace"][0]["tool_output"]["weight_kg"] == 15.0
        (merged, not the LLM's null)
      - Assert: result["reasoning_trace"][0]["tool_output"]["missing_fields"] == []
        (recomputed from merged, not the LLM's ["weight_kg"])
  </behavior>
  <action>
    1. Edit `backend/agent/nodes/planner.py`:
       - Locate the merge block (currently lines 200-213) and the D-12 override block (lines 184-198).
       - Replace per the "Recompute logic" section above. Specifically:
         a. Move `merged_shipping`, `merged_weight`, `merged_origin`, `merged_destination` computation to BEFORE the D-12 override block (so the override can reference merged values).
         b. Compute `missing` list from merged values.
         c. Add `if next_step == "clarify" and not missing: next_step = "fetch_fuel"` BEFORE the D-12 override block.
         d. In the D-12 override calls to `_route_matches`, replace `parsed.origin`/`parsed.destination` with `merged_origin`/`merged_destination`. Also replace `parsed.shipping_type and parsed.weight_kg is not None` checks inside the D-12 block with `merged_shipping and merged_weight is not None` (because the merged values are what actually decide whether pricing has all inputs).
         e. In the return dict, replace the inline `parsed.X or state.get("X")` expressions with the precomputed `merged_*` locals. Replace `parsed.missing_fields` with the recomputed `missing` local.
         f. Build the trace `tool_output` as an explicit dict (per "Trace fix" section) instead of `parsed.model_dump()`. Include the post-override `next_step` and the merged extraction fields.
       - Update the module docstring (top-of-file) to add a one-line bullet noting the 999.1 / 999.3 fix:
         ```
         - 999.1 fix (2026-04-25): post-LLM recompute of missing_fields and
           next_step from merged values so follow-up turns honour cached state.
         - 999.3 fix (2026-04-25): trace tool_output reflects post-override
           next_step and merged extraction fields, not the raw LLM emission.
         ```
       - Do NOT change the `PlannerOutput` schema. Do NOT touch D-04 loop budget guard, D-02 parse retry, or D-24 error sink (the early `if state.get("errors")` branch).

    2. Edit `backend/tests/test_planner.py`:
       - Append the four new tests A, B, C, D described above to the end of the file.
       - Reuse existing helpers `_user_state`, `_scripted_llm`, `_now_iso_z`, and the `mod`/`planner_node` imports. Do NOT introduce new helpers.
       - For Test B's fresh fuel_data + matching route_data, mirror the fixture shape used in `test_skips_fetch_when_fuel_fresh` — fuel_data dict with `fetched_at=_now_iso_z()`, plus a route_data dict with matching origin/destination keys. Pull route_data shape from `_route_matches` definition (lines 81-88 of planner.py): `{"origin": "...", "destination": "...", ...}` is sufficient — extra keys ignored.
       - Each new test follows the existing pattern: build state via `_user_state(...)` overrides, monkeypatch `get_chat_model` with `_scripted_llm(...)`, call `planner_node(state)`, assert.

    3. Run only the new tests first to confirm they FAIL on the unfixed code:
       `python -m pytest backend/tests/test_planner.py::test_followup_merges_prior_state_promotes_clarify_to_fetch -x` should fail BEFORE step 1 changes are saved. (If TDD-strict workflow is preferred, write tests first, run them red, then apply step 1.)

    4. After step 1 changes are in place, run the full planner suite:
       `python -m pytest backend/tests/test_planner.py -v` — all 5 existing + 4 new = 9 tests pass.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/test_planner.py -v</automated>
  </verify>
  <done>
    - `backend/agent/nodes/planner.py` contains `merged_shipping`, `merged_weight`, `merged_origin`, `merged_destination` locals computed BEFORE the D-12 override block.
    - The D-12 override block references `merged_origin`/`merged_destination` (not `parsed.origin`/`parsed.destination`) in `_route_matches` calls and references `merged_shipping`/`merged_weight` in the inputs-present check.
    - A `missing` list is computed from merged values BEFORE the return.
    - A clarify->fetch_fuel promotion guard exists between the merge and the D-12 override block.
    - The trace `tool_output` dict is explicitly constructed (not `parsed.model_dump()`) and contains the post-override `next_step` and merged extraction fields.
    - `python -m pytest backend/tests/test_planner.py -v` reports 9 passed, 0 failed.
    - The `PlannerOutput` schema and the D-02 / D-04 / D-24 branches are unchanged.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add E2E regression test for 999.1 in test_graph.py</name>
  <files>backend/tests/test_graph.py</files>
  <behavior>
    New E2E test `test_followup_param_switch_routes_through_pricing` proves the headline UX fix
    end-to-end via the assembled graph + checkpointer:

    - Turn 1 on thread_id="t-vyj-followup": "Calculate surcharge for 50kg retail_standard from Bangkok to Pathum Thani"
      - Planner LLM script: fetch_fuel -> fetch_route -> calculate_price -> respond (4 responses)
      - Mocked tool returns mirror existing `test_followup_only_runs_pricing` patterns.
      - After turn 1: fuel_calls["n"] == 1, route_calls["n"] == 1, lookup_calls["n"] == 1.

    - Turn 2 (same thread_id): "What if I switched it to a Bounce shipment instead?"
      - Planner LLM script (turn 2): emits a clarify-shaped response with shipping_type="bounce",
        weight_kg=null, origin=null, destination=null, missing_fields=["weight_kg","origin","destination"],
        next_step="clarify", user_intent="followup_query" — i.e. the exact bug-reproducer shape.
      - Then a respond response after the tools complete.
      - Assert: turn 2 final state has surcharge_result NOT None and shipping_type=="bounce"
        (proves the graph routed through pricing despite the LLM's clarify emission).
      - Assert: fuel_calls["n"] == 1 (D-12 cache hit on turn 2 — fuel not re-fetched).
      - Assert: route_calls["n"] == 1 (D-12 cache hit on turn 2 — origin/destination unchanged).
      - Assert: lookup_calls["n"] == 2 (rate re-looked-up because shipping_type changed).
      - Assert: result["final_payload"]["status"] == "ok".

    Without the 999.1 fix, this test would fail at the first assertion (surcharge_result remains
    None because the graph routed to clarify on turn 2). The test is the headline regression
    guard for the user-visible bug.
  </behavior>
  <action>
    1. Append a new test to the end of `backend/tests/test_graph.py` named
       `test_followup_param_switch_routes_through_pricing`.
    2. Decorate with `@pytest.mark.asyncio` and accept fixtures `monkeypatch, mocker, in_memory_checkpointer`.
    3. Reuse the existing `_planner_response`, `_stateful_factory`, `_empty_state`, `_NARR`, `_NARR_R`, `_NARR_P` helpers — do NOT introduce new helpers.
    4. Build planner LLM script as a list of 6 JSON strings (turn 1: fetch_fuel/fetch_route/calculate_price/respond; turn 2: a clarify-shaped response then respond):
       ```python
       turn1 = [
           _planner_response("fetch_fuel", shipping_type="retail_standard",
                             weight_kg=50.0, origin="Bangkok",
                             destination="Pathum Thani"),
           _planner_response("fetch_route", shipping_type="retail_standard",
                             weight_kg=50.0, origin="Bangkok",
                             destination="Pathum Thani"),
           _planner_response("calculate_price", shipping_type="retail_standard",
                             weight_kg=50.0, origin="Bangkok",
                             destination="Pathum Thani"),
           _planner_response("respond", shipping_type="retail_standard",
                             weight_kg=50.0, origin="Bangkok",
                             destination="Pathum Thani"),
       ]
       turn2 = [
           # Reproducer shape: only shipping_type extracted, others null,
           # next_step=clarify, user_intent=followup_query.
           _planner_response("clarify",
                             user_intent="followup_query",
                             shipping_type="bounce",
                             weight_kg=None, origin=None, destination=None,
                             missing_fields=["weight_kg","origin","destination"],
                             clarification_reason="missing_inputs"),
           _planner_response("respond",
                             user_intent="followup_query",
                             shipping_type="bounce",
                             weight_kg=50.0, origin="Bangkok",
                             destination="Pathum Thani"),
       ]
       planner_responses = turn1 + turn2
       ```
    5. Mock `fuel_agent.fetch_fuel_price`, `route_agent.calculate_route`, `pricing_agent.lookup_rate` exactly as in `test_followup_only_runs_pricing` (use side_effect counters). Add a `lookup_calls = {"n": 0}` counter wrapping `lookup_rate` so the test can assert it was called twice (once per turn — the rate tier may change because shipping_type changed).
    6. Use thread_id "t-vyj-followup". Invoke graph twice with the same `cfg`. Assert per Behavior section.
    7. If `_planner_response` does not currently accept `weight_kg=None` cleanly (it does — it's typed `float | None`), no helper changes are needed. If it rejects `None`, build the JSON inline via `json.dumps({...})` for those two responses only.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/test_graph.py::test_followup_param_switch_routes_through_pricing -v</automated>
  </verify>
  <done>
    - `backend/tests/test_graph.py` contains `test_followup_param_switch_routes_through_pricing` decorated with `@pytest.mark.asyncio`.
    - The test uses the in_memory_checkpointer fixture and exercises two graph.ainvoke calls with the same thread_id.
    - The test asserts surcharge_result is non-None on turn 2 AND fuel_calls["n"] == 1 AND route_calls["n"] == 1 AND lookup_calls["n"] == 2 AND final_payload status == "ok".
    - `python -m pytest backend/tests/test_graph.py -v` reports all existing graph tests plus the new one passing.
    - `python -m pytest backend/tests/ -q` reports 105+ passed (103 existing + 4 from Task 1 + 1 from Task 2 = 108; minus any double-counted), 0 failed.
  </done>
</task>

<task type="auto">
  <name>Task 3: Update ROADMAP.md Backlog with 999.1 and 999.3 Resolved entries</name>
  <files>.planning/ROADMAP.md</files>
  <action>
    Append two new subsections to the existing `## Backlog` section in `.planning/ROADMAP.md`,
    after the existing 999.2 entry (the file currently ends at line 140 with the 999.2 Decision
    paragraph — append after that line, preserving the existing 999.2 content).

    Use the same subsection style and tone as the existing 999.2 entry (Status / Origin / Decision).

    Block to append:

    ```markdown

    ### 999.1: Planner state merge on follow-up turns

    **Status**: Resolved 2026-04-25 via quick task `260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo` (option b: post-process recompute).

    **Origin**: Live smoke testing on 2026-04-25 (prompt C) surfaced that on the same thread, "Calculate surcharge for 50kg retail_standard from Bangkok to Pathum Thani" followed by "What if I switched it to a Bounce shipment instead?" returned a clarification asking for weight/origin/destination instead of routing through fetch_route/fetch_fuel/calculate_price using the prior thread's values. Root cause: planner_node invoked the LLM with only the latest user message; the LLM returned null for unmentioned fields, populated missing_fields, and emitted next_step=clarify. The post-LLM `parsed.X or state.get("X")` merge filled extraction fields after the fact, but next_step and missing_fields were already decided.

    **Options considered**:
    - (a) Inject prior state into the LLM prompt context so the LLM sees state.shipping_type / weight_kg / origin / destination — heavier, requires SYSTEM_PROMPT changes plus a token-cost increase on every planner call, and trusts the LLM to do the right thing.
    - (b) After the existing `parsed.X or state.get("X")` merge produces final values, recompute missing_fields and next_step from the merged values. If the LLM said clarify but the merge has all fields, promote next_step to fetch_fuel and let the existing D-12 cache-aware override cascade further (fetch_route / calculate_price) — chosen, smaller blast radius, no prompt change, no token cost increase, deterministic.

    **Decision**: Option (b). The D-12 cache-aware override block was also updated to reference merged_origin/merged_destination (not parsed.origin/parsed.destination) so route-cache hits work on follow-ups where origin/destination were inherited from prior state. Option (a) remains open for future consideration if user_intent classification becomes unreliable on follow-ups.

    ### 999.3: Planner trace tool_output narration mismatch

    **Status**: Resolved 2026-04-25 via quick task `260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo` (folded into the same patch as 999.1).

    **Origin**: Live smoke testing on 2026-04-25 surfaced that the trace panel's planner step displayed `tool_output.next_step` values that did not match the actually-routed step. Root cause: planner_node emitted `parsed.model_dump()` as `tool_output`, capturing the raw LLM emission BEFORE the D-12 cache-aware override mutated the local `next_step` variable. The `reasoning` text was correct (already used post-override next_step); only `tool_output` was stale. Pure narration bug — no impact on graph routing — but undermined the agent's transparency promise.

    **Options considered**:
    - (a) Drop `tool_output` from planner trace entries entirely — would lose trace-panel detail.
    - (b) Construct `tool_output` as an explicit dict from the post-override next_step and merged extraction fields — chosen, preserves trace fidelity and matches what the function actually returns to the graph.

    **Decision**: Option (b). The trace tool_output dict now contains the same values that planner_node returns to the graph, eliminating any narration/routing skew.
    ```

    Do NOT modify the existing 999.2 entry, the milestone summary table, or any other section
    of ROADMAP.md.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && grep -E "^### 999\\.(1|2|3):" .planning/ROADMAP.md | wc -l | tr -d ' '</automated>
  </verify>
  <done>
    - `.planning/ROADMAP.md` ends with three Backlog subsections: 999.2, 999.1, 999.3 in that order (newest appended below).
    - Both 999.1 and 999.3 entries contain a `**Status**: Resolved 2026-04-25` line referencing the quick task slug `260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo`.
    - The verify grep returns "3" (three `### 999.X:` subsections present).
    - The 999.2 entry is unchanged (byte-identical to its prior content above the append).
  </done>
</task>

</tasks>

<verification>
Run the full backend test suite to confirm no regressions:

```bash
cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/ -q
```

Expected: 108 passed (103 existing + 4 new planner unit tests + 1 new graph E2E test), 0 failed, 0 skipped (consistent with the 103/0 baseline noted in STATE.md).

Cross-check the 999.3 narration fix on the new graph test by inspecting its planner trace:
```bash
cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/test_planner.py::test_trace_tool_output_reflects_post_override_next_step -v
```
The test should pass — its assertion that `reasoning_trace[0]["tool_output"]["next_step"] == "fetch_route"` directly proves bug 999.3 is fixed.

Cross-check the 999.1 fix via the unit test for the parameter-switch promotion:
```bash
cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/test_planner.py::test_followup_merges_prior_state_promotes_clarify_to_fetch -v
```
The test should pass — its assertion that `result["next_step"] == "fetch_fuel"` directly proves bug 999.1 is fixed.

Sanity-check unchanged surfaces:
- `grep -n "PlannerOutput" backend/agent/nodes/planner.py` — schema definition is unchanged (Literal vocabulary, all field types, defaults).
- `grep -n "_loop_budget_exhausted\\|errors\\|planner_parse_failed" backend/agent/nodes/planner.py` — D-04 / D-24 / D-02 branches unchanged.

</verification>

<success_criteria>
- All 103 existing backend tests pass unchanged.
- 4 new unit tests in `backend/tests/test_planner.py` pass: parameter-switch promotion, full-cache cascade to calculate_price, trace tool_output post-override next_step, trace tool_output merged inherited fields.
- 1 new E2E test in `backend/tests/test_graph.py` passes: parameter-switch follow-up routes through pricing with fuel + route caches reused.
- `python -m pytest backend/tests/ -q` reports 108 passed, 0 failed.
- `backend/agent/nodes/planner.py` no longer emits `parsed.model_dump()` as trace tool_output; uses an explicit dict with post-override values.
- `backend/agent/nodes/planner.py` recomputes `missing_fields` and `next_step` from merged values; the D-12 override block uses merged_origin/merged_destination.
- `PlannerOutput` Pydantic schema is unchanged. SYSTEM_PROMPT in `backend/agent/prompts/planner.py` is unchanged.
- `.planning/ROADMAP.md` Backlog section contains Resolved entries for 999.1 and 999.3, both citing this quick task slug.
</success_criteria>

<output>
After completion, create `.planning/quick/260425-vyj-fix-planner-bugs-999-1-state-merge-on-fo/260425-vyj-SUMMARY.md`
</output>
