---
quick_id: 260514-vrc
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/agent/nodes/response_node.py
  - backend/tests/test_response_node.py
  - .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md
autonomous: true
branch: fix/quick-260514-vrc-response-node-fresh-truth-gate
commits_expected: 3

must_haves:
  truths:
    - "When pricing_agent did NOT run in the current turn, final_payload.surcharge_result is None (regardless of state.surcharge_result)"
    - "When search_agent did NOT run in the current turn, final_payload.search_context is None AND _market_context_line returns None (regardless of state.search_context)"
    - "When pricing_agent ran in the current turn, the breakdown table + status='ok' still render (no regression on happy path)"
    - "state.surcharge_result and state.search_context are NEVER mutated by response_node — FE trace panel + Langfuse trace + checkpointer replay paths see unchanged state"
    - "The refusal branch (lines 230-280) and deny branch (lines 282-336) are UNCHANGED — they have their own dedicated state-handling and are out of scope for this gate"
    - "All existing 358 backend tests stay green"
  artifacts:
    - path: "backend/agent/nodes/response_node.py"
      provides: "Fresh-truth gate at top of main response_node body (post-refusal, post-deny, pre-status-ladder)"
      contains: "pricing_ran_this_turn"
    - path: "backend/agent/nodes/response_node.py"
      provides: "_market_context_line accepts explicit search_context arg (no longer reads from state directly)"
      contains: "def _market_context_line(search_context"
    - path: "backend/tests/test_response_node.py"
      provides: "Three new tests covering stale-surcharge-on-search-turn, stale-surcharge-on-clarify-turn, fresh-pricing happy path"
      contains: "test_response_node_gates_stale_surcharge_on_search_turn"
    - path: ".planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md"
      provides: "Cross-link note: sibling state-leak fix shipped mid-freeze, signals shared root cause class"
      contains: "Related Fixes Shipped Mid-Freeze"
  key_links:
    - from: "response_node main branch (post-deny, pre-status-ladder)"
      to: "state.reasoning_trace scan"
      via: "Find latest entry where agent=='response' → current_turn = entries AFTER that index"
      pattern: "current_turn_entries"
    - from: "render-time local variables (surcharge_result_for_render, search_context_for_render)"
      to: "status precedence ladder + table render + market context line + final_payload assembly"
      via: "Local-only — state itself is never modified"
      pattern: "surcharge_result_for_render"
    - from: "_market_context_line callsite (around line 406)"
      to: "search_context_for_render local"
      via: "Explicit argument; helper no longer reads from state"
      pattern: "_market_context_line(search_context_for_render)"
---

<objective>
Fix a state-leak in `response_node` where `state.surcharge_result` and `state.search_context` from prior turns persist into the rendered `final_payload` for subsequent non-pricing / non-search turns. Add a "current-turn freshness gate" that scans `reasoning_trace` for current-turn `pricing_agent` / `search_agent` entries and locally nulls the render values when the corresponding agent did not run this turn.

Purpose: Prevent stale `surcharge_result` / `search_context` from prior turns leaking into the current turn's user-facing markdown + final_payload. Sibling defect to `.planning/debug/999.12` (duplicate message_id) — same family of "AgentState fields meant to be turn-scoped behave as thread-scoped because no path explicitly nulls them at turn boundaries".

Output:
- Updated `backend/agent/nodes/response_node.py` with a render-time freshness gate that operates on local variables only (state is never mutated).
- Three new tests in `backend/tests/test_response_node.py` proving the gate works on search-turn stale-surcharge, clarify-turn stale-surcharge, and fresh-pricing happy path.
- Cross-link note appended to `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md` signalling this sibling fix to the post-demo investigation.
</objective>

<execution_context>
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@backend/agent/nodes/response_node.py
@backend/tests/test_response_node.py
@backend/agent/state.py
@.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md

<interfaces>
<!-- Key contracts the executor needs. Extracted from the codebase. -->
<!-- Executor should use these directly — no codebase exploration needed. -->

From backend/agent/state.py:
```python
class AgentState(TypedDict):
    messages: List[dict]
    surcharge_result: Optional[dict]   # SurchargeResult.model_dump() output, or None
    reasoning_trace: Annotated[List[dict], operator.add]  # accretes across turns via reducer
    search_context: Optional[dict]     # Tavily search result; written by search_agent_node
    # ... other fields omitted ...
```

`reasoning_trace` entry shape (per existing entries in response_node.py and tests):
```python
{
  "step": int,                  # cumulative across all turns
  "agent": str,                 # one of: "planner", "fuel_agent", "route_agent",
                                # "search_agent", "pricing_agent", "response",
                                # "guard_input", "guard_output", "hitl_gate"
  "tool": Optional[str],
  "tool_input": dict,
  "tool_output": dict,
  "reasoning": str,
  "timestamp": str,             # ISO-8601 UTC "Z"
  "status": str,                # "ok" | "error" | ...
}
```

Key fact for the "current turn" boundary:
- `reasoning_trace` uses `operator.add` reducer → entries accrete across turns.
- `response_node` itself emits an `agent == "response"` entry at the END of each turn (see line ~419-430 for happy path, ~249-267 for guard refusal, ~305-319 for deny).
- Therefore: the LATEST `agent == "response"` entry marks the boundary between "prior turns" and "current turn". Entries AFTER that index are the current turn.
- If NO `agent == "response"` entry exists yet → this is the first turn → all entries are current-turn.

Current call shape in response_node.py (the lines we are touching):

Line 282 (state surcharge read — REPLACE):
```python
surcharge_result: Optional[dict] = state.get("surcharge_result")
```

Line 351 (search_context read — REPLACE):
```python
sc = state.get("search_context")
```

Line 406 (market context helper call — REPLACE):
```python
mc_line = _market_context_line(state)
```

Line 415 (final_payload search_context — REPLACE):
```python
"search_context": state.get("search_context"),  # Phase 8 D-07 — always present, None when state lacks it
```

Lines 59-74 (`_market_context_line` signature — REPLACE):
```python
def _market_context_line(state: dict) -> Optional[str]:
    sc = state.get("search_context")
    if not sc:
        return None
    summary = (sc.get("summary") or "").strip()
    if not summary:
        return None
    return f"> **Market context:** {summary}"
```

Existing test fixture `_ok_state()` at backend/tests/test_response_node.py:12-49 — initial `reasoning_trace: []` (empty), so the existing happy-path tests treat "all entries are current turn" — those tests stay green because pricing_agent IS implicitly assumed to have run (state.surcharge_result is set). The fix preserves that semantic when reasoning_trace is empty (no prior `response` entry → all entries count as current turn → if reasoning_trace has zero entries, both `pricing_ran_this_turn` and `search_ran_this_turn` are False — BUT existing tests set `surcharge_result` without an empty reasoning_trace and expect status='ok'). **This requires careful handling — see Task 1 action note below.**
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement current-turn freshness gate in response_node</name>
  <files>backend/agent/nodes/response_node.py</files>
  <behavior>
    Render-time gate operates on local variables only:
    - Test 1 (existing happy path preserved): When state.surcharge_result is set AND reasoning_trace is empty (single-turn happy path), status='ok' and surcharge_result renders. This is the existing test_renders_locked_markdown_structure path. Must stay green.
    - Test 2 (new): When state.surcharge_result is set, state.search_context is set, AND reasoning_trace contains [pricing_agent, response, search_agent] in that order (prior turn ran pricing, current turn ran search only) → status='search_only', final_payload.surcharge_result is None, markdown does NOT contain "| Base rate |" / "| Surcharge % |" / "| Total |".
    - Test 3 (new): When state.surcharge_result is set AND reasoning_trace ends with [..., response] (prior turn ran pricing, current turn has no pricing/search entries — pure clarify) → status='clarify', final_payload.surcharge_result is None, markdown is the clarify prose ("I need a bit more information ...").
    - Test 4 (new): When state.surcharge_result is set AND reasoning_trace contains a pricing_agent entry but no prior response entry (single-turn happy path) → status='ok', final_payload.surcharge_result matches state.surcharge_result, breakdown table renders. (Defensive marker for the explicit-trace happy path.)
    - State is never mutated: assertions on `state["surcharge_result"]` and `state["search_context"]` AFTER calling response_node show identity preserved (same dict object reference).
  </behavior>
  <action>
**Step 1 — Update `_market_context_line` to take an explicit argument (lines 59-74).**

Replace the existing function with:

```python
def _market_context_line(search_context: Optional[dict]) -> Optional[str]:
    """D-11 (Phase 5): "Market context: ..." prefix when search_context present.

    Returns ``None`` when ``search_context`` is missing/None or when its
    ``summary`` is empty/whitespace. Frontend may also render this from
    the trace panel, but emitting the prose here keeps the markdown
    self-contained for Langfuse trace inspection and any non-FE consumers.

    Quick task 260514-vrc: now takes ``search_context`` as an explicit
    argument (not pulled from state) so the response_node main branch
    can pass a render-gated local (None when search_agent did not run
    this turn) without touching state itself. Helper stays pure.
    """
    if not search_context:
        return None
    summary = (search_context.get("summary") or "").strip()
    if not summary:
        return None
    return f"> **Market context:** {summary}"
```

**Step 2 — Add the freshness-gate block at the TOP of the main response_node body.**

Insert AFTER the deny-branch return (currently ends ~line 339, `return {...}` closes the `if state.get("approval_decision") == "deny":` block) and BEFORE the existing `errors = state.get("errors") or []` (~line 280, which currently sits ABOVE the deny branch but needs to be moved — see Step 3).

The cleanest structural change:
1. Keep refusal branch (lines 238-278) unchanged.
2. Keep deny branch unchanged BUT move the `errors`/`clarification_reason`/`surcharge_result` reads (lines 280-282) to AFTER the deny branch, so they sit in the main fall-through path only. The deny branch already does its own `state.get("surcharge_result")` read internally (line 290) so it does not depend on the moved reads.

Concretely, after the deny branch closes (~line 339), insert:

```python
    # Quick task 260514-vrc: current-turn freshness gate.
    #
    # state.surcharge_result and state.search_context are turn-producing
    # fields but state itself is thread-scoped (LangGraph SQLite checkpointer
    # persists the whole AgentState across turns). Without an explicit
    # null-at-turn-boundary path, a prior turn's surcharge_result leaks
    # into the current turn's rendered markdown when the current turn does
    # NOT route through pricing_agent (e.g., a follow-up "what's the news?"
    # search-only turn after a pricing turn, or a clarify turn).
    #
    # We detect the current turn boundary by scanning reasoning_trace for
    # the most recent agent=='response' entry (response_node always emits
    # one at the END of a turn). Entries AFTER that index are the current
    # turn; everything at-or-before is prior turns.
    #
    # The gate is LOCAL-ONLY — state.surcharge_result and state.search_context
    # are never modified, so the FE trace panel + Langfuse trace +
    # checkpointer replay paths see the same state they always did.
    #
    # Sibling defect: .planning/debug/999.12 (duplicate message_id). Same
    # family of "AgentState fields meant to be turn-scoped behave as
    # thread-scoped because no path explicitly nulls them at turn boundaries".
    trace = state.get("reasoning_trace") or []
    last_response_idx = -1
    for i in range(len(trace) - 1, -1, -1):
        entry = trace[i]
        if isinstance(entry, dict) and entry.get("agent") == "response":
            last_response_idx = i
            break
    current_turn_entries = trace[last_response_idx + 1:]
    pricing_ran_this_turn = any(
        isinstance(e, dict) and e.get("agent") == "pricing_agent"
        for e in current_turn_entries
    )
    search_ran_this_turn = any(
        isinstance(e, dict) and e.get("agent") == "search_agent"
        for e in current_turn_entries
    )

    # Backward-compat shim: when reasoning_trace is EMPTY (no entries at
    # all), preserve the pre-gate semantic where state.surcharge_result /
    # state.search_context are trusted at face value. This covers:
    #   (a) unit tests that build state directly without populating trace
    #       (e.g., the existing test_renders_locked_markdown_structure
    #       fixture sets reasoning_trace=[] and expects status='ok').
    #   (b) any harness / replay path that synthesises state without
    #       reconstructing the full trace.
    # In production, every real turn produces at least one trace entry
    # before response_node fires (planner always emits one), so this
    # shim does NOT mask real state-leak bugs — it only preserves
    # synthetic-fixture semantics.
    if not trace:
        surcharge_result_for_render: Optional[dict] = state.get("surcharge_result")
        search_context_for_render: Optional[dict] = state.get("search_context")
    else:
        surcharge_result_for_render = (
            state.get("surcharge_result") if pricing_ran_this_turn else None
        )
        search_context_for_render = (
            state.get("search_context") if search_ran_this_turn else None
        )

    errors = state.get("errors") or []
    clarification_reason = state.get("clarification_reason")
    surcharge_result: Optional[dict] = surcharge_result_for_render
```

**Step 3 — Delete the now-duplicated reads at the old location.**

The lines that originally sat at ~280-282 (now moved into the block above):
```python
    errors = state.get("errors") or []
    clarification_reason = state.get("clarification_reason")
    surcharge_result: Optional[dict] = state.get("surcharge_result")
```
…must be deleted from their original position (between the refusal branch and the deny branch). Verify by reading the file around lines 280-340 after the edit: refusal branch closes → deny branch (`if state.get("approval_decision") == "deny":`) opens directly with no orphaned reads in between.

Wait — re-checking the current code: lines 280-282 sit BEFORE the deny branch (line 289). The deny branch references `state.get("approval_decision")` and `state.get("surcharge_result")` directly (line 290), so it does NOT depend on the line-282 binding. Therefore: **delete lines 280-282 in their original position**, then place the new gate block (which re-declares `errors`, `clarification_reason`, `surcharge_result`) AFTER the deny branch's return statement (line 339).

**Step 4 — Update the search_context local read (line 351).**

Replace:
```python
    sc = state.get("search_context")
```
with:
```python
    sc = search_context_for_render
```

The `sc_has_content` line below (line 352-354) stays unchanged — it operates on `sc`.

**Step 5 — Update the _market_context_line callsite (line 406).**

Replace:
```python
    mc_line = _market_context_line(state)
```
with:
```python
    mc_line = _market_context_line(search_context_for_render)
```

**Step 6 — Update final_payload.search_context (line 415).**

Replace:
```python
        "search_context": state.get("search_context"),  # Phase 8 D-07 — always present, None when state lacks it
```
with:
```python
        "search_context": search_context_for_render,  # 260514-vrc — gated by current-turn freshness; None when search_agent did not run this turn
```

**Critical DO-NOT-TOUCH list:**
- Refusal branch (lines ~238-278): unchanged.
- Deny branch (lines ~289-339): unchanged. Its internal `state.get("surcharge_result")` (line 290), `state.get("search_context")` (line 335), and `_market_context_line(state)` call (line 301) all stay as-is. The deny branch has its own dedicated state-handling per the D-07 contract and is OUT OF SCOPE for this gate. (Open question for future: should deny-branch ALSO gate? Defer to post-demo /gsd:debug; this quick task is the minimal fix.)
- Phase 7 messages-persistence (lines 432-445): unchanged — it depends on rendered `markdown`, not the gated locals.
- `_render_table`, `_pricing_reasoning_bullets`, `_render_prose_ok`, `_render_prose_clarify`, `_render_prose_partial`: unchanged. They read from `state` directly for fuel/route/shipping metadata that is independent of the surcharge_result render gate (and those reads are not affected by the leak — they only render when status==ok which only happens when pricing_ran_this_turn anyway).

**Final commit message (Task 1 atomic commit):**
```
fix(quick-260514-vrc): gate stale surcharge_result + search_context behind current-turn freshness in response_node

state.surcharge_result and state.search_context from prior turns were
leaking into the current turn's final_payload + rendered markdown
whenever the current turn did not route through pricing_agent /
search_agent (e.g., a clarify-only follow-up after a pricing turn).

Add a render-time gate that scans reasoning_trace for current-turn
pricing_agent / search_agent entries (boundary = latest agent=='response'
entry) and locally nulls the render value when the corresponding agent
did not run this turn. State itself is unchanged — FE trace panel +
Langfuse trace + checkpointer replay paths are preserved.

Refusal branch (guard) and deny branch (HITL) are out of scope — they
have their own dedicated state-handling. Sibling defect:
.planning/debug/999.12 (duplicate message_id). Same family of
"AgentState fields meant to be turn-scoped behave as thread-scoped
because no path explicitly nulls them at turn boundaries".
```
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && source .venv/bin/activate && pytest backend/tests/test_response_node.py -x -q</automated>
  </verify>
  <done>
    - `_market_context_line` takes `search_context` as an explicit Optional[dict] arg (not state).
    - Main response_node body has the freshness gate block AFTER the deny branch return and BEFORE the status precedence ladder.
    - `surcharge_result_for_render` and `search_context_for_render` locals exist; `surcharge_result` is bound to the local (not from state directly).
    - Line 351 reads from `search_context_for_render` (via the `sc` rename).
    - Line 406 passes `search_context_for_render` to `_market_context_line`.
    - Line 415 reads from `search_context_for_render`.
    - Refusal branch + deny branch + helper functions are byte-identical to pre-fix versions (only the `_market_context_line` signature changed, and its call inside the deny branch at line 301 still passes `state` — WAIT: this needs special handling. Re-read the action note carefully.)

    **Correction to "done" criteria — deny-branch call to `_market_context_line`:** The deny branch at line 301 currently calls `_market_context_line(state)`. With the new helper signature `_market_context_line(search_context: Optional[dict])`, this call MUST be updated to `_market_context_line(state.get("search_context"))` to preserve the existing deny-branch behaviour (provenance survives decline per the existing test `test_response_node_deny_with_market_context_keeps_prefix`). This is a SIGNATURE-COMPATIBILITY update inside the deny branch, NOT a behavioural change — the deny branch still reads from state directly, just via the new helper interface. The deny branch is otherwise untouched.

    Add the deny-branch callsite update to the action above when implementing.

    - All existing 12 tests in `test_response_node.py` pass.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add three tests covering the freshness gate</name>
  <files>backend/tests/test_response_node.py</files>
  <action>
Append three new test functions at the END of `backend/tests/test_response_node.py` under a new section header. Use the existing `_ok_state()` fixture as the base; mutate it per test.

**Section header comment to add at the bottom of the file:**
```python
# ---------------------------------------------------------------------------
# Quick task 260514-vrc — current-turn freshness gate for stale state-leak.
# Sibling fix to .planning/debug/999.12 (duplicate message_id family).
# Boundary heuristic: latest reasoning_trace entry where agent=='response'
# marks the end of the PRIOR turn; entries AFTER that index are the CURRENT
# turn. response_node renders surcharge_result / search_context ONLY when
# pricing_agent / search_agent (respectively) appear in the current-turn
# slice. State is never mutated — the gate is render-time only.
# ---------------------------------------------------------------------------
```

**Test 1 — stale surcharge gated on a search-only turn:**
```python
def test_response_node_gates_stale_surcharge_on_search_turn():
    """260514-vrc: state.surcharge_result populated from a PRIOR turn must
    NOT render in the current turn when only search_agent ran this turn.
    Boundary: reasoning_trace = [..., pricing_agent, response, search_agent].
    Expected: status='search_only', final_payload.surcharge_result=None,
    markdown is the news prose (no breakdown table).
    """
    state = _ok_state()
    state["surcharge_result"] = {
        "surcharge_pct": 0.10,
        "surcharge_amount": 12.0,
        "total": 132.0,
        "capped": False,
    }
    state["search_context"] = {
        "query": "diesel news",
        "summary": "Refinery shutdown nudges prices.",
        "sources": [],
        "fetched_at": "2026-05-14T10:00:00Z",
    }
    # Prior turn: pricing ran, response wrapped it up.
    # Current turn: search_agent only.
    state["reasoning_trace"] = [
        {
            "step": 1,
            "agent": "pricing_agent",
            "tool": "calculate_surcharge",
            "tool_input": {},
            "tool_output": {},
            "reasoning": "prior turn pricing",
            "timestamp": "2026-05-14T09:59:00Z",
            "status": "ok",
        },
        {
            "step": 2,
            "agent": "response",
            "tool": None,
            "tool_input": {"status": "ok"},
            "tool_output": {},
            "reasoning": "prior turn response",
            "timestamp": "2026-05-14T09:59:30Z",
            "status": "ok",
        },
        {
            "step": 3,
            "agent": "search_agent",
            "tool": "search_fuel_news",
            "tool_input": {},
            "tool_output": {},
            "reasoning": "current turn search",
            "timestamp": "2026-05-14T10:00:00Z",
            "status": "ok",
        },
    ]

    # Capture pre-call state identity to verify NO mutation.
    pre_call_surcharge = state["surcharge_result"]
    pre_call_search_ctx = state["search_context"]

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    # Gate fired: stale surcharge nulled in final_payload.
    assert payload["status"] == "search_only", (
        f"expected status='search_only' (stale surcharge gated, fresh search), got: {payload['status']!r}; md={md!r}"
    )
    assert payload["surcharge_result"] is None, (
        f"stale surcharge_result leaked into final_payload: {payload['surcharge_result']!r}"
    )

    # Markdown has the news prose, NOT the breakdown table.
    assert "Here's the latest market context" in md
    assert "| Base rate |" not in md, f"stale base rate leaked into markdown: {md!r}"
    assert "| Surcharge % |" not in md
    assert "| Surcharge amount |" not in md
    assert "| Total |" not in md
    # Market context blockquote prepends (D-11 contract preserved).
    assert md.startswith("> **Market context:** Refinery shutdown nudges prices.")

    # State NOT mutated — same dict identity, same contents.
    assert state["surcharge_result"] is pre_call_surcharge
    assert state["search_context"] is pre_call_search_ctx
    assert state["surcharge_result"]["total"] == 132.0
```

**Test 2 — stale surcharge gated on a pure-clarify turn:**
```python
def test_response_node_gates_stale_surcharge_on_clarify_turn():
    """260514-vrc: state.surcharge_result from a PRIOR turn must NOT render
    when the current turn has neither pricing_agent NOR search_agent
    entries (pure clarify turn — planner asked for missing inputs).
    Expected: status='clarify', final_payload.surcharge_result=None,
    markdown is the clarify prose (no breakdown table).
    """
    state = _ok_state()
    state["surcharge_result"] = {
        "surcharge_pct": 0.10,
        "surcharge_amount": 12.0,
        "total": 132.0,
        "capped": False,
    }
    state["clarification_reason"] = "missing_weight"
    state["missing_fields"] = ["weight_kg"]
    # Prior turn: pricing ran. Current turn: nothing (planner emitted clarify).
    state["reasoning_trace"] = [
        {
            "step": 1,
            "agent": "pricing_agent",
            "tool": "calculate_surcharge",
            "tool_input": {},
            "tool_output": {},
            "reasoning": "prior turn pricing",
            "timestamp": "2026-05-14T09:59:00Z",
            "status": "ok",
        },
        {
            "step": 2,
            "agent": "response",
            "tool": None,
            "tool_input": {"status": "ok"},
            "tool_output": {},
            "reasoning": "prior turn response",
            "timestamp": "2026-05-14T09:59:30Z",
            "status": "ok",
        },
        # Current turn: only a planner entry, no pricing, no search.
        {
            "step": 3,
            "agent": "planner",
            "tool": None,
            "tool_input": {},
            "tool_output": {"next_step": "clarify"},
            "reasoning": "current turn — clarify",
            "timestamp": "2026-05-14T10:00:00Z",
            "status": "ok",
        },
    ]

    pre_call_surcharge = state["surcharge_result"]

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    assert payload["status"] == "clarify", (
        f"expected status='clarify' (stale surcharge gated, no fresh agents), got: {payload['status']!r}; md={md!r}"
    )
    assert payload["surcharge_result"] is None, (
        f"stale surcharge_result leaked: {payload['surcharge_result']!r}"
    )
    # Clarify prose, no breakdown table.
    assert "weight" in md.lower() or "provide" in md.lower()
    assert "| Base rate |" not in md
    assert "| Total |" not in md

    # State unchanged.
    assert state["surcharge_result"] is pre_call_surcharge
    assert state["surcharge_result"]["total"] == 132.0
```

**Test 3 — fresh pricing renders normally (defensive happy-path marker):**
```python
def test_response_node_renders_fresh_pricing_when_pricing_ran_this_turn():
    """260514-vrc defensive marker: the freshness gate must NOT regress
    the single-turn happy path. When the current turn has a pricing_agent
    entry (and no prior response entry), state.surcharge_result still
    renders normally as status='ok' with the breakdown table.

    This complements test_renders_locked_markdown_structure (which uses
    an EMPTY reasoning_trace via the _ok_state fixture and exercises the
    backward-compat shim) by also covering the EXPLICIT-trace happy
    path — a single-turn flow where reasoning_trace has real entries
    including the current-turn pricing_agent entry.
    """
    state = _ok_state()
    # surcharge_result already set by _ok_state(). Trace records the
    # current-turn pricing_agent entry; NO prior response entry.
    state["reasoning_trace"] = [
        {
            "step": 1,
            "agent": "planner",
            "tool": None,
            "tool_input": {},
            "tool_output": {},
            "reasoning": "planner",
            "timestamp": "2026-05-14T10:00:00Z",
            "status": "ok",
        },
        {
            "step": 2,
            "agent": "pricing_agent",
            "tool": "calculate_surcharge",
            "tool_input": {},
            "tool_output": {},
            "reasoning": "current turn pricing",
            "timestamp": "2026-05-14T10:00:01Z",
            "status": "ok",
        },
    ]

    result = response_node(state)
    payload = result["final_payload"]
    md = payload["markdown"]

    assert payload["status"] == "ok", (
        f"expected status='ok' (fresh pricing this turn), got: {payload['status']!r}; md={md!r}"
    )
    assert payload["surcharge_result"] == state["surcharge_result"]
    assert "| Base rate |" in md
    assert "| Total |" in md
```

**After appending, verify all existing tests + the three new tests pass:**

```bash
cd /Users/pollot/Desktop/express-dynamic-workflow
source .venv/bin/activate
pytest backend/tests/test_response_node.py -x -q
pytest backend/tests/ -q  # full backend suite — must stay at 358 passing
```

**Final commit message (Task 2 atomic commit):**
```
test(quick-260514-vrc): cover current-turn freshness gate in response_node

Three new tests in backend/tests/test_response_node.py:

1. test_response_node_gates_stale_surcharge_on_search_turn — prior turn
   ran pricing; current turn ran search only; final_payload must show
   status='search_only' with surcharge_result=None and no breakdown
   table in markdown. State identity preserved (no mutation).

2. test_response_node_gates_stale_surcharge_on_clarify_turn — prior turn
   ran pricing; current turn is pure clarify (no pricing, no search);
   final_payload.surcharge_result=None and markdown is clarify prose.

3. test_response_node_renders_fresh_pricing_when_pricing_ran_this_turn —
   defensive happy-path marker: with an EXPLICIT current-turn
   pricing_agent trace entry (vs. the existing empty-trace fixture),
   surcharge_result still renders normally as status='ok'.

All existing 12 tests in this file and the full 358-test backend suite
stay green.
```
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && source .venv/bin/activate && pytest backend/tests/test_response_node.py -x -q && pytest backend/tests/ -q</automated>
  </verify>
  <done>
    - Three new test functions exist in `backend/tests/test_response_node.py`, named exactly as specified.
    - `pytest backend/tests/test_response_node.py` passes (15 tests: 12 original + 3 new).
    - `pytest backend/tests/` passes (full 358-test backend suite stays green).
    - Each new test asserts both the rendered payload AND that `state` was not mutated (identity check on the dict reference).
  </done>
</task>

<task type="auto">
  <name>Task 3: Append cross-link note to debug 999.12 file</name>
  <files>.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md</files>
  <action>
Open `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`. Append a new H2 section at the END of the file (after the existing "Why Deferred" section) titled `## Related Fixes Shipped Mid-Freeze`. The section body is the exact prose specified in the task constraints — preserved here for fidelity:

```markdown
## Related Fixes Shipped Mid-Freeze

- **2026-05-14 — `response_node` fresh-truth gate (quick-260514-vrc):** Sibling state-leak in the render path — `state.surcharge_result` and `state.search_context` from prior turns persisted into the rendered `final_payload` for subsequent non-pricing / non-search turns. Surface was different (render-time rather than id-stamping), but the underlying pattern is the same family — "AgentState fields meant to be turn-scoped behave as thread-scoped because no path explicitly nulls them at turn boundaries." Fixed via a fresh-truth gate that scans `reasoning_trace` for current-turn `pricing_agent` / `search_agent` entries and locally nulls the render value when the corresponding agent did not run this turn. State itself is unchanged (FE trace panel + Langfuse trace + checkpointer replay paths preserved).

  Signals to the post-demo /gsd:debug investigation: the broader "state-scoping across turns" class likely needs a holistic root-cause look — both this fix and the 999.12 hypotheses A/B/C may share a single architectural cause around how AgentState fields persist across turn boundaries.
```

DO NOT modify any existing content in the file. ONLY append the new section at the end.

**Final commit message (Task 3 atomic commit):**
```
docs(quick-260514-vrc): cross-link response_node freshness-gate fix to debug 999.12

Append a "Related Fixes Shipped Mid-Freeze" section to the deferred
debug file for the duplicate message_id family. Signals to the
post-W6-demo /gsd:debug pickup that the response_node render-time
state-leak fixed by quick-260514-vrc is likely a sibling of the
duplicate message_id symptoms (hypotheses A/B/C) — all four may share
a single root cause around how AgentState fields persist across turn
boundaries via the operator.add reducer on reasoning_trace and the
absence of explicit null-at-boundary paths.
```
  </action>
  <verify>
    <automated>grep -F "Related Fixes Shipped Mid-Freeze" /Users/pollot/Desktop/express-dynamic-workflow/.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md && grep -F "quick-260514-vrc" /Users/pollot/Desktop/express-dynamic-workflow/.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md</automated>
  </verify>
  <done>
    - The H2 section `## Related Fixes Shipped Mid-Freeze` exists at the end of the file.
    - The section body contains the exact prose with the dated bullet and the signal-to-post-demo-investigation sub-paragraph.
    - No prior content in the file is modified (verify via `git diff` showing ADD-only on this file).
  </done>
</task>

</tasks>

<verification>
**Per-task verification (executor must run these in order):**

1. After Task 1 commit:
   ```bash
   cd /Users/pollot/Desktop/express-dynamic-workflow
   source .venv/bin/activate
   pytest backend/tests/test_response_node.py -x -q
   ```
   All 12 existing tests pass. (No new tests yet.)

2. After Task 2 commit:
   ```bash
   pytest backend/tests/test_response_node.py -x -q   # 15 tests pass
   pytest backend/tests/ -q                            # full 358-test suite passes
   ```

3. After Task 3 commit:
   ```bash
   grep -F "Related Fixes Shipped Mid-Freeze" .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md
   grep -F "quick-260514-vrc" .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md
   ```
   Both grep calls return non-empty matches.

**Final overall verification (after all three commits):**

```bash
git log --oneline -3
```
Should show three commits in order on `fix/quick-260514-vrc-response-node-fresh-truth-gate`:
1. `docs(quick-260514-vrc): cross-link response_node freshness-gate fix to debug 999.12`
2. `test(quick-260514-vrc): cover current-turn freshness gate in response_node`
3. `fix(quick-260514-vrc): gate stale surcharge_result + search_context behind current-turn freshness in response_node`

```bash
git status
```
Should show only the untracked / unrelated files noted in constraints:
- `data/raw/eppo_diesel_prices.csv` (unstaged refresh — DO NOT touch)
- `.planning/milestones/v1.1-MILESTONE-AUDIT.md` (untracked — DO NOT touch)
- `.planning/phases/999.9-.../999.9-VERIFICATION.md` (untracked — DO NOT touch)
- `.planning/quick/260514-vrc-.../260514-vrc-PLAN.md` (this plan, tracked separately by the orchestrator's commit flow)

Nothing else should be modified.

```bash
pytest backend/tests/ -q
```
Full backend suite passes (target: 358 tests, +3 new = 361 passing; orchestrator may verify the exact pre-fix count when wrapping up).
</verification>

<success_criteria>
- Three atomic commits on `fix/quick-260514-vrc-response-node-fresh-truth-gate` — one per task, in the order: `fix(...)` → `test(...)` → `docs(...)`.
- `pytest backend/tests/test_response_node.py` shows 15 passing tests (12 pre-existing + 3 new).
- `pytest backend/tests/` shows the full pre-existing test count + 3 new = all green.
- `state.surcharge_result` and `state.search_context` are never mutated by response_node (verified by the new tests' identity assertions).
- Refusal branch (lines 230-280) and deny branch (lines 282-336) are byte-identical pre/post fix except for the one signature-compatibility update inside the deny branch (`_market_context_line(state)` → `_market_context_line(state.get("search_context"))`).
- `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md` has the new `## Related Fixes Shipped Mid-Freeze` section appended at the end with the exact prose specified.
- `data/raw/eppo_diesel_prices.csv` is unmodified relative to its pre-task working-tree state.
- `.env` / `.env.example` are unmodified.
- ROADMAP.md is unmodified.
- v1.1.0 tag is unchanged.
- No push to remote — orchestrator handles push + PR after all three commits land.
</success_criteria>

<output>
After completion, this plan does NOT produce a `*-SUMMARY.md` (quick tasks log to STATE.md's Quick Tasks Completed table only, per CLAUDE.md and the existing quick-task convention). The orchestrator will:
1. Verify all three commits exist on the feature branch.
2. Push `fix/quick-260514-vrc-response-node-fresh-truth-gate` to origin.
3. Open a PR → `develop`.
4. Append a row to STATE.md's Quick Tasks Completed table.
</output>
