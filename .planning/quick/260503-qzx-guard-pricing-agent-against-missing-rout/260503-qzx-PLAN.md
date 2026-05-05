---
quick_task: 260503-qzx
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/agent/nodes/pricing_agent.py
  - backend/tests/test_pricing_agent.py
  - .planning/phases/05-polish-observability-docs/05-UAT.md
autonomous: true
requirements:
  - gap-4 (UAT)
must_haves:
  truths:
    - "pricing_agent_node never raises KeyError when route_data or fuel_data is missing/None"
    - "Missing precondition produces a structured state.errors entry (D-24 sink shape) with node='pricing_agent'"
    - "Missing precondition routes the turn to response_node (next_step='respond') so the user sees a status='partial' answer"
    - "A reasoning_trace entry with status='warn' is emitted so the trace panel surfaces the guarded miss"
    - "Existing happy-path pricing logic at lines 138+ is unchanged (no regression to 184/184 backend tests)"
    - "UAT.md gap-4 row appended after gap-3, status=resolved, resolved_by='quick-task 260503-qzx'"
  artifacts:
    - path: "backend/agent/nodes/pricing_agent.py"
      provides: "Defensive precondition guard at the top of pricing_agent_node"
      contains: "state.get(\"route_data\")"
    - path: "backend/tests/test_pricing_agent.py"
      provides: "Two regression tests for missing route_data and missing fuel_data"
      contains: "test_guards_missing_route_data"
    - path: ".planning/phases/05-polish-observability-docs/05-UAT.md"
      provides: "gap-4 entry appended to ## Gaps section"
      contains: "### gap-4: pricing_agent crashes on missing route_data/fuel_data"
  key_links:
    - from: "pricing_agent_node guard"
      to: "AgentState.errors (operator.add reducer)"
      via: "return {'errors': [{node, exception_type, message, timestamp}], ...}"
      pattern: "\"node\": \"pricing_agent\""
    - from: "pricing_agent_node guard"
      to: "response_node"
      via: "return next_step='respond' in partial state"
      pattern: "\"next_step\": \"respond\""
    - from: "pricing_agent_node guard"
      to: "trace panel"
      via: "reasoning_trace entry with status='warn'"
      pattern: "\"status\": \"warn\""
---

<objective>
Add a defensive precondition guard to `pricing_agent_node` so a misbehaving planner LLM that hallucinates `next_step="calculate_price"` before route_agent / fuel_agent have populated state cannot crash the user's conversation with `KeyError: 'route_data'`.

Purpose: UAT Q06 ("Surcharge for 100kg bounce Bangkok to Samut Sakhon?") crashed in 2.7s because the planner skipped fetch_route. This is stochastic (same query may pass on retry) but it is a real defect — defense-in-depth at the consumer (pricing_agent) is the right layer per the upstream task brief (do NOT modify the planner to prevent hallucination).

Output:
- pricing_agent.py guarded against missing route_data / fuel_data, mirroring the route_agent.py:128-159 error-sink shape (D-24)
- 2 regression tests asserting no raise + state.errors entry + next_step='respond'
- 05-UAT.md gap-4 row appended documenting the find + fix
- Backend test suite still green (185+/185+ — adds 2 new tests)
</objective>

<execution_context>
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md
@backend/agent/nodes/pricing_agent.py
@backend/agent/nodes/route_agent.py
@backend/agent/state.py
@backend/tests/test_pricing_agent.py
@.planning/phases/05-polish-observability-docs/05-UAT.md

<interfaces>
<!-- Canonical D-24 error-sink entry shape used elsewhere in the codebase.   -->
<!-- Source: backend/agent/nodes/route_agent.py:128-159 (gap-2 fix pattern). -->
<!-- The pricing_agent guard MUST emit this exact shape so existing trace    -->
<!-- panel + Langfuse error rendering work without changes.                  -->

D-24 error-sink entry (from route_agent.py:150-156):
```python
{
    "node": "pricing_agent",          # was "route_agent" in route_agent.py
    "exception_type": "KeyError",     # the would-have-been raised type
    "message": str(<reason>),         # human-readable cause
    "timestamp": ts,                  # ISO-8601 UTC 'Z'
}
```

Reducer note (from backend/agent/state.py:35, 61):
- `errors: Annotated[List[dict], operator.add]` — return a SINGLE-ITEM list `[{...}]`, the reducer concatenates with prior entries.
- `reasoning_trace: Annotated[List[dict], operator.add]` — same single-item-list contract.

Reasoning-trace entry shape (from route_agent.py:135-148):
```python
{
    "step": prior_steps + 1,
    "agent": "pricing_agent",
    "tool": None,                     # no tool was actually invoked
    "tool_input": None,
    "tool_output": None,
    "reasoning": "<why we short-circuited>",
    "timestamp": ts,
    "status": "warn",                 # NOT "ok" — guard fired
}
```

Return-value shape for short-circuit (from route_agent.py:149-158):
```python
return {
    "errors": [{...}],
    "next_step": "respond",
    "reasoning_trace": [warn_trace],
}
```

Existing pricing_agent_node signature (preserve verbatim):
```python
def pricing_agent_node(
    state: dict, config: Optional[RunnableConfig] = None
) -> dict
```

Top of function today (lines 136-140 — these reads MUST move BELOW the guard):
```python
shipping_type = state["shipping_type"]
weight_kg = state["weight_kg"]
zone = state["route_data"]["zone"]              # <-- crashes here on Q06
current_diesel_price = state["fuel_data"]["price"]
traffic_severity = state["route_data"]["traffic_severity"]
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add precondition guard to pricing_agent_node</name>
  <files>backend/agent/nodes/pricing_agent.py</files>
  <behavior>
    - Guard fires BEFORE any subscript reads on state["route_data"] or state["fuel_data"]
    - Guard fires when EITHER state.get("route_data") is None/falsy OR state.get("fuel_data") is None/falsy
    - When the guard fires, the function returns a partial state dict with three keys:
        * errors: single-item list [{node: "pricing_agent", exception_type: "KeyError", message: <which key was missing>, timestamp: <ISO-8601 UTC Z>}]
        * next_step: "respond"
        * reasoning_trace: single-item list [{step, agent: "pricing_agent", tool: None, tool_input: None, tool_output: None, reasoning: <human-readable>, timestamp, status: "warn"}]
    - Guard does NOT raise. Guard does NOT route to "planner" (loop risk per upstream brief).
    - Happy path (both keys present and truthy) is UNCHANGED — guard is a pure prepend, lines 136+ stay as-is.
    - The `message` field clearly identifies which input was missing: "missing route_data", "missing fuel_data", or "missing route_data and fuel_data" when both absent.
  </behavior>
  <action>
At the TOP of `pricing_agent_node` (immediately after the docstring, BEFORE the existing `shipping_type = state["shipping_type"]` line at line 136), insert a precondition guard that mirrors the route_agent.py:128-159 error-sink shape exactly.

Implementation outline (do NOT copy verbatim — adapt to fit pricing context):

```python
# Defense-in-depth (gap-4 fix from UAT 260503-qzx, 2026-05-03):
# A misbehaving planner LLM may emit next_step="calculate_price" before
# route_agent or fuel_agent have run. Without this guard, the subscript
# reads at lines 138-140 raise KeyError ('route_data' or 'fuel_data')
# which propagates as an SSE error event with no recovery path. Catch
# the missing-input case here, emit a D-24 error-sink entry, and route
# to response_node so the user sees a status='partial' answer.
# Do NOT route back to planner (loop risk with a misbehaving planner).
route_data = state.get("route_data")
fuel_data = state.get("fuel_data")
if not route_data or not fuel_data:
    missing = []
    if not route_data:
        missing.append("route_data")
    if not fuel_data:
        missing.append("fuel_data")
    msg = f"missing {' and '.join(missing)}"
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    prior_steps = len(state.get("reasoning_trace") or [])
    warn_trace = {
        "step": prior_steps + 1,
        "agent": "pricing_agent",
        "tool": None,
        "tool_input": None,
        "tool_output": None,
        "reasoning": (
            f"Pricing agent invoked before required inputs were populated "
            f"({msg}). Planner likely routed to calculate_price prematurely; "
            f"short-circuiting to response with a partial answer."
        ),
        "timestamp": ts,
        "status": "warn",
    }
    return {
        "errors": [{
            "node": "pricing_agent",
            "exception_type": "KeyError",
            "message": msg,
            "timestamp": ts,
        }],
        "next_step": "respond",
        "reasoning_trace": [warn_trace],
    }
```

Notes:
- `datetime` and `timezone` are already imported at the top of pricing_agent.py — no new imports needed.
- DO NOT touch the existing pricing logic at lines 138+ — only insert this block above it.
- DO NOT add a try/except wrapper around the existing reads — the guard makes them safe by precondition.
- Use `not route_data` (truthy check) rather than `is None` — covers both None and empty dict (defense in depth).

Reference the route_agent.py:128-159 pattern when in doubt — same shape, different node identity.

Verify-then-commit:
1. Run `pytest backend/tests/test_pricing_agent.py -x` to confirm existing 3 tests still pass (the guard does NOT fire on `_full_state()` which has both keys populated).
2. Run `pytest backend/tests/ -x` to confirm full backend suite still 184/184.
3. Commit with: `fix(pricing_agent): guard against missing route_data/fuel_data (gap-4 from UAT 260503-qzx)`
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow &amp;&amp; pytest backend/tests/test_pricing_agent.py -x -q</automated>
  </verify>
  <done>
- backend/agent/nodes/pricing_agent.py contains the precondition guard at the top of pricing_agent_node
- Existing 3 pricing_agent tests still pass (guard does not fire on full state)
- Full backend suite still 184/184
- Commit lands with message starting `fix(pricing_agent):`
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add regression tests for missing route_data and missing fuel_data</name>
  <files>backend/tests/test_pricing_agent.py</files>
  <behavior>
    - Test 1: `test_guards_missing_route_data` — state with route_data=None (all other keys present). Asserts:
        * pricing_agent_node returns WITHOUT raising
        * result["next_step"] == "respond"
        * result["errors"] is a list of length 1
        * result["errors"][0]["node"] == "pricing_agent"
        * result["errors"][0]["exception_type"] == "KeyError"
        * "route_data" in result["errors"][0]["message"]
        * result["reasoning_trace"][0]["status"] == "warn"
        * result["reasoning_trace"][0]["agent"] == "pricing_agent"
        * "surcharge_result" NOT in result (or is absent — the partial-state return omits it)
    - Test 2: `test_guards_missing_fuel_data` — state with fuel_data=None (all other keys present). Same assertions but with "fuel_data" in the error message.
    - Both tests use the existing `_full_state()` helper as a baseline and override the relevant key to None. NO mocking of lookup_rate / get_chat_model is needed because the guard short-circuits before either is invoked.
  </behavior>
  <action>
Append two new test functions to backend/tests/test_pricing_agent.py (after `test_gemini_failure_deterministic_fallback` on line 144). Reuse the existing `_full_state()` helper (line 27-59) as the baseline.

Implementation outline:

```python
def test_guards_missing_route_data():
    """gap-4 (UAT 260503-qzx): when planner hallucinates next_step='calculate_price'
    before route_agent ran, pricing_agent must short-circuit gracefully instead of
    raising KeyError on state['route_data']['zone']."""
    state = _full_state()
    state["route_data"] = None

    # Should NOT raise.
    result = pricing_agent_node(state)

    assert result["next_step"] == "respond"
    assert len(result["errors"]) == 1
    err = result["errors"][0]
    assert err["node"] == "pricing_agent"
    assert err["exception_type"] == "KeyError"
    assert "route_data" in err["message"]
    assert err["timestamp"].endswith("Z")

    assert len(result["reasoning_trace"]) == 1
    trace = result["reasoning_trace"][0]
    assert trace["agent"] == "pricing_agent"
    assert trace["status"] == "warn"
    assert trace["tool"] is None

    # Partial-state return must NOT include a surcharge_result key
    # (response_node renders status='partial' on its absence).
    assert "surcharge_result" not in result


def test_guards_missing_fuel_data():
    """gap-4 (UAT 260503-qzx): symmetric to missing route_data — guard fires when
    fuel_data is absent (e.g. fuel_agent skipped or failed silently upstream)."""
    state = _full_state()
    state["fuel_data"] = None

    result = pricing_agent_node(state)

    assert result["next_step"] == "respond"
    assert len(result["errors"]) == 1
    err = result["errors"][0]
    assert err["node"] == "pricing_agent"
    assert err["exception_type"] == "KeyError"
    assert "fuel_data" in err["message"]

    assert result["reasoning_trace"][0]["status"] == "warn"
    assert "surcharge_result" not in result
```

Notes:
- No mocker / monkeypatch fixtures needed — guard short-circuits before lookup_rate / get_chat_model are touched. Both tests are zero-dependency.
- The existing 3 tests (test_computes_surcharge_and_emits_trace, test_bubbles_value_error_from_lookup_rate, test_gemini_failure_deterministic_fallback) MUST still pass — they all populate `_full_state()` with both keys present, so the guard does not fire.

Verify-then-commit:
1. Run `pytest backend/tests/test_pricing_agent.py -x -v` — expect 5 passing (3 existing + 2 new).
2. Run `pytest backend/tests/` — expect 186/186 (was 184, +2 new).
3. Commit with: `test(pricing_agent): regression tests for missing route_data/fuel_data (gap-4)`
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow &amp;&amp; pytest backend/tests/test_pricing_agent.py -x -v &amp;&amp; pytest backend/tests/ -q</automated>
  </verify>
  <done>
- backend/tests/test_pricing_agent.py has 2 new tests: test_guards_missing_route_data, test_guards_missing_fuel_data
- Both new tests pass; all 3 existing tests still pass (5 total in this file)
- Full backend suite is 186/186 (was 184)
- Commit lands with message starting `test(pricing_agent):`
  </done>
</task>

<task type="auto">
  <name>Task 3: Append gap-4 entry to 05-UAT.md</name>
  <files>.planning/phases/05-polish-observability-docs/05-UAT.md</files>
  <action>
Append a single new gap entry at the END of the existing `## Gaps` section in `.planning/phases/05-polish-observability-docs/05-UAT.md` (right after the existing gap-3 block ending at line 143).

DO NOT modify:
- The frontmatter (lines 1-7)
- The `## Current Test` / `## Tests` sections
- The `## Summary` block (lines 47-54) — gap-4 was NOT in the original 7-question manual UAT; it surfaced from the separate 20-question UAT run, so the totals stay at total: 7, passed: 4, issues: 3.
- gap-1, gap-2, or gap-3 entries

Insert exactly this block at the end of the file (after gap-3's `debug_session: null` line):

```markdown

### gap-4: pricing_agent crashes on missing route_data/fuel_data
status: resolved
resolved_by: quick-task 260503-qzx
test: 20
severity: medium
symptom: |
  Q06 of the 20-question UAT ("Surcharge for 100kg bounce Bangkok to Samut Sakhon?")
  crashed with KeyError: 'route_data' in 2.7 seconds — far below a normal turn's
  latency, indicating the planner LLM emitted next_step="calculate_price" before
  route_agent had run. pricing_agent_node read state["route_data"]["zone"] at line
  138 with no defensive check and the KeyError propagated as an SSE error event,
  killing the conversation. Stochastic — same query may succeed on retry — but
  a real defect that crashes user conversations.
suspected_root_cause: |
  Two contributing causes, only one of which we fix here:
  (1) The planner LLM occasionally hallucinates next_step="calculate_price" without
      first routing through fetch_route (and possibly fetch_fuel). This is a
      planner-side prompt/reliability issue — out of scope for this fix.
  (2) pricing_agent_node had no precondition guard on state["route_data"] or
      state["fuel_data"]. Defense-in-depth at the consumer is the right layer:
      even with a perfect planner, a guard here makes the node robust to upstream
      regressions and stochastic LLM misbehaviour.
remediation_hint: |
  Add a precondition guard at the TOP of pricing_agent_node, before any subscript
  reads. If state.get("route_data") is None/missing OR state.get("fuel_data") is
  None/missing:
    - Append a structured error to state["errors"] (D-24 sink shape:
      {node, exception_type, message, timestamp}; see route_agent.py:128-159
      for the canonical pattern from gap-2)
    - Append a reasoning_trace entry with status="warn" so the trace panel shows
      what happened
    - Return next_step="respond" so response_node renders a status='partial'
      answer
  Do NOT route back to planner (loop risk with a misbehaving planner LLM).
  Add 2 regression tests asserting the function does not raise, returns
  next_step='respond', and state.errors has one entry with node='pricing_agent'.
  Do NOT modify the planner — that's a separate, larger problem.
debug_session: null
```

Notes on field values:
- `test: 20` refers to the 20-question UAT run that surfaced this bug, NOT test #20 in any sequence.
- `severity: medium` — it's a real defect but it's stochastic and has a clean defense-in-depth fix; not "critical" like gap-1/2/3 which were deterministic.
- `resolved_by: quick-task 260503-qzx` — the directory name of THIS quick task.

Verify-then-commit:
1. Visually confirm the file still has its original frontmatter, all 4 gaps in order (gap-1 → gap-2 → gap-3 → gap-4), Summary block unchanged.
2. Confirm no other lines were edited (`git diff .planning/phases/05-polish-observability-docs/05-UAT.md` should show ONLY the appended gap-4 block).
3. Commit with: `docs(uat): document gap-4 — pricing_agent missing route_data/fuel_data (resolved by quick-task 260503-qzx)`
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow &amp;&amp; grep -c '^### gap-' .planning/phases/05-polish-observability-docs/05-UAT.md | grep -q '^4$' &amp;&amp; grep -q 'gap-4: pricing_agent crashes on missing route_data/fuel_data' .planning/phases/05-polish-observability-docs/05-UAT.md &amp;&amp; grep -q 'resolved_by: quick-task 260503-qzx' .planning/phases/05-polish-observability-docs/05-UAT.md</automated>
  </verify>
  <done>
- 05-UAT.md has 4 gap entries (was 3); gap-4 is the new one and appears AFTER gap-3
- Frontmatter, Tests section, and Summary block are unchanged (only gap-4 block was added)
- Commit lands with message starting `docs(uat):`
  </done>
</task>

</tasks>

<verification>
**End-to-end checks (after all 3 tasks land):**

1. `pytest backend/tests/` returns 186/186 passing (was 184/184; +2 new pricing-agent guard tests).
2. `git log --oneline -3` shows three task-aligned commits in order: `fix(pricing_agent): ...`, `test(pricing_agent): ...`, `docs(uat): ...`.
3. The pricing_agent.py guard return shape matches route_agent.py:128-159 verbatim in structure (only node identity and message text differ).
4. .planning/phases/05-polish-observability-docs/05-UAT.md has gap-4 appended with status: resolved, severity: medium, test: 20.
5. No edits to: planner_node.py, response_node.py, ROADMAP.md, or any other phase artifact (out-of-scope per the upstream brief).
</verification>

<success_criteria>
- [ ] pricing_agent_node guards against missing route_data and missing fuel_data without raising
- [ ] Guard emits D-24-shaped error sink entry (node="pricing_agent", exception_type, message, timestamp)
- [ ] Guard emits reasoning_trace entry with status="warn"
- [ ] Guard returns next_step="respond" (NOT "planner")
- [ ] 2 regression tests added, both passing
- [ ] Existing 3 pricing_agent tests still pass (no regression on happy path)
- [ ] Full backend suite green: 186/186
- [ ] gap-4 appended to 05-UAT.md after gap-3, frontmatter and Summary block untouched
- [ ] Three atomic commits land in task order, each independently revertable
</success_criteria>

<output>
After completion, this quick task's directory `.planning/quick/260503-qzx-guard-pricing-agent-against-missing-rout/` should contain only the PLAN.md (no SUMMARY.md required for quick tasks per gsd convention; STATE.md's Quick Tasks Completed table is updated by the orchestrator on close-out).
</output>
