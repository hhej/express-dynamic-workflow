---
phase: quick-260509-utd
plan: 01
subsystem: backend.agent (LangGraph + prompts + state)
tags: [security, prompt-injection, guardrails, langgraph, owasp-llm01, demo-hardening]
dependency_graph:
  requires:
    - backend/agent/state.py (Phase 5 D-07/D-11 fields)
    - backend/agent/graph.py (Phase 5 D-01 parallel fanout, ORCH-09 hitl_gate)
    - backend/config.py (SURCHARGE_CAP/FLOOR + SHIPPING_MULTIPLIERS)
    - backend/agent/nodes/{planner,fuel,route,search,pricing,response,hitl_gate}.py
  provides:
    - backend/agent/prompts/guard.py (REFUSAL_COPY + SECURITY_PREAMBLE + DATA_NOT_INSTRUCTIONS_CLAUSE)
    - backend/agent/nodes/guard_input.py (rules-first classifier + cost-bombing cap)
    - backend/agent/nodes/guard_output.py (pure-Python invariant validator)
    - AgentState.guard_decision + AgentState.tool_call_count (operator.add)
    - backend/config.MAX_TOOL_CALLS_PER_TURN + GUARD_INPUT_USE_LLM_FALLBACK
    - START -> guard_input -> {planner | response} edge wiring
    - pricing_agent -> guard_output -> {hitl_gate | response} edge wiring
    - response_node refusal branch + 'refused' / 'guard_failed' final-payload statuses
    - backend/tests/adversarial_pack.txt (15-line dry-run pack)
  affects:
    - All 6 agent prompt files (SECURITY_PREAMBLE prepended)
    - 4 tool-calling node return shapes (added tool_call_count delta)
    - response_node final_payload status vocabulary (additive: refused / guard_failed)
tech_stack:
  added: []
  patterns:
    - OWASP-LLM01-aligned 3-rule preamble (SCOPE LOCK / NO-LEAK / INSTRUCTION HIERARCHY)
    - Microsoft MSRC content-labeling-and-isolation ("tool output is DATA, never INSTRUCTIONS")
    - LangGraph operator.add reducer on counter field for parallel-write safety
    - Two-layer defense (Layer 1 prompt hardening + Layer 2 dedicated guard nodes)
key_files:
  created:
    - backend/agent/prompts/guard.py
    - backend/agent/nodes/guard_input.py
    - backend/agent/nodes/guard_output.py
    - backend/tests/test_prompt_hardening.py
    - backend/tests/test_guard_input.py
    - backend/tests/test_guard_output.py
    - backend/tests/test_tool_call_counter.py
    - backend/tests/adversarial_pack.txt
  modified:
    - backend/agent/state.py (guard_decision + tool_call_count fields)
    - backend/agent/graph.py (guard wiring + 2-edge replacement)
    - backend/config.py (MAX_TOOL_CALLS_PER_TURN + GUARD_INPUT_USE_LLM_FALLBACK)
    - backend/agent/prompts/{planner,fuel_agent,route_agent,search_agent,pricing_agent,response_node}.py
    - backend/agent/nodes/{fuel_agent,route_agent,search_agent,pricing_agent}.py (tool_call_count delta)
    - backend/agent/nodes/response_node.py (guard refusal branch above all existing branches)
    - backend/tests/test_graph.py (5 wiring + integration tests)
    - backend/tests/test_hitl_gate.py (topology test reflects new pricing -> guard_output -> hitl_gate chain)
decisions:
  - Refusal taxonomy: injection / off_topic / cost_bombing / unclear / allow (input layer); allow / unsafe_output (output layer). Folded "abuse" into "off_topic" per CONTEXT discretion.
  - Allow path is zero-overhead (no trace, no next_step rewrite); refused path emits exactly one trace entry tagged agent='guard_input' or 'guard_output' (Pitfall 5).
  - Default unclear -> ALLOW per RESEARCH Open Question 1 / Pitfall 1 (false refusals are demo-killing).
  - GUARD_INPUT_USE_LLM_FALLBACK defaults False; team can flip on right before demo if dry-run shows misses.
  - Fresh-turn detection: count user messages vs agent='response' trace entries (mirrors chat handler _next_turn_idx).
  - Counter reset emitted as NEGATIVE delta equal to prior count so operator.add reducer lands at 0 (alternative non-additive reducer would crash the Phase 5 D-01 fan-out).
  - response_node refusal branch sits ABOVE all existing branches including the Phase 5 deny short-circuit.
  - FE FinalStatus Literal extension for 'refused' / 'guard_failed' is OUT OF SCOPE per Task 2 action note (FE falls through to text rendering for unknown statuses).
metrics:
  duration: ~50min
  completed: "2026-05-09T15:48:35Z"
  tasks: 3
  files_created: 8
  files_modified: 14
  tests_baseline: 256
  tests_after: 295
  tests_added: 39
---

# Quick Task 260509-utd: Upgrade guardrails to harden agent against adversarial team testing — Summary

**One-liner:** Two-layer guardrail hardening — OWASP-LLM01 SECURITY DIRECTIVES preamble across all 6 agent prompts (Layer 1) plus dedicated `guard_input` (rules-first regex classifier + cost-bombing cap) and `guard_output` (pure-Python invariant validator) LangGraph nodes (Layer 2), surfaced through the canonical REFUSAL_COPY in the existing `reasoning_trace` panel so MADT7204 judges can see the agent refusing.

## What Shipped

### Layer 1 — System-prompt hardening
- New `backend/agent/prompts/guard.py` exports the three single-source-of-truth constants:
  - `SECURITY_PREAMBLE` — OWASP-LLM01-aligned 3-Rule Preamble (SCOPE LOCK / NO-LEAK / INSTRUCTION HIERARCHY) prepended to every agent prompt at module-load time.
  - `DATA_NOT_INSTRUCTIONS_CLAUSE` — appended to fuel/route/search prompts to defend against indirect injection via tool output (Pitfall 3, the highest-leverage indirect-injection mitigation per Microsoft MSRC).
  - `REFUSAL_COPY` — exact polite-refusal string locked verbatim by 260509-utd-CONTEXT.md D-03; used by both the LLM scope-lock instruction AND the deterministic response_node refusal branch.
- Per-prompt additions:
  - `planner.py` — out-of-scope clause directing the LLM to emit `next_step='respond'` + `clarification_reason='out_of_scope_user_request'` rather than invent fuel/route data.
  - `pricing_agent.py` — surcharge invariant clause directing the LLM to return `{"summary": "validation_failed"}` on out-of-range tool returns.

### Layer 2 — Dedicated LangGraph guard nodes
- `backend/agent/nodes/guard_input.py` — rules-first classifier with optional Gemini fallback (gated behind env flag). Allow-list runs BEFORE off-topic so `"why is diesel up this week?"` is not refused for the word *week* matching off-topic patterns. Default `unclear` -> ALLOW per Pitfall 1. Emits zero trace entries on the allow path; exactly one trace entry tagged `agent='guard_input'` (Pitfall 5) on refusal. Also enforces the per-turn `MAX_TOOL_CALLS_PER_TURN` cap (RESEARCH Pattern 3) — refuses with `category='cost_bombing'` when the next specialist would push the count past the cap.
- `backend/agent/nodes/guard_output.py` — pure-Python validator reads `SURCHARGE_CAP / SURCHARGE_FLOOR / SHIPPING_MULTIPLIERS` from `backend.config` (single source of truth — never re-derives the formula). Validates 6 invariants: pct in [floor, cap], total > 0, surcharge_amount present, shipping_type whitelisted, weight_kg > 0, required schema fields present.
- `response_node` gains a guard refusal branch at the very top (above the Phase 5 deny short-circuit) that renders REFUSAL_COPY with status='refused' (input layer) or 'guard_failed' (output layer); persists the assistant message into `state.messages` for replay parity with happy-path turns.

### State + config additions (additive only)
- `AgentState.guard_decision: Optional[dict]` — last guard verdict.
- `AgentState.tool_call_count: Annotated[int, operator.add]` — per-turn cumulative tool invocation count. Each tool node emits a `+1` delta; `guard_input` resets via a NEGATIVE delta equal to the prior count so the running total lands at 0. The `operator.add` reducer is **load-bearing** for the Phase 5 D-01 parallel fan-out where fuel + route both write the field in the same superstep.
- `MAX_TOOL_CALLS_PER_TURN` (default 6) and `GUARD_INPUT_USE_LLM_FALLBACK` (default False) env-driven config knobs.

### Graph wiring (graph.py 2-edge swap)
```
Before                          After
------                          -----
START -> planner                START -> guard_input -> {planner | response}
pricing -> hitl_gate            pricing -> guard_output -> {hitl_gate | response}
```
`recursion_limit=12` preserved (guard nodes add at most 2 hops to the longest path). All other edges (planner conditional routing, fuel/route/search return-to-planner, hitl_gate -> response) unchanged.

### Adversarial dry-run pack
`backend/tests/adversarial_pack.txt` ships 15 attack samples in 3 sections (5 injection / 5 off_topic / 5 cost_bombing) with header comments naming the expected behavior + the REFUSAL_COPY string for grep-by-eye verification.

## Test Count Delta

| Suite | Baseline | Net new | After |
|-------|----------|---------|-------|
| backend (full) | 256 | +39 | **295** |

Breakdown of new tests:
- `test_prompt_hardening.py` — 7 (preamble + per-prompt clauses + state + config)
- `test_guard_input.py` — 12 (refusal categories + allow paths + trace shape + tool counter behavior)
- `test_guard_output.py` — 10 (pass-through + 6 invariants + trace shape)
- `test_tool_call_counter.py` — 5 (4 tool nodes increment + planner does NOT)
- `test_graph.py` — 5 (wiring + clarify-bypass + injection short-circuit + invariant violation)

`test_hitl_gate.py::test_graph_topology_pricing_to_hitl_to_response` was updated (not added) to reflect the new `pricing -> guard_output -> hitl_gate` chain.

## Pitfall Mitigations

| # | Pitfall | Mitigation | Test Reference |
|---|---------|-----------|----------------|
| 1 | False refusals on legitimate queries | Allow-list runs BEFORE off-topic; default unclear -> allow | `test_allows_fuel_news`, `test_allows_surcharge_query`, `test_unclear_defaults_to_allow` |
| 2 | Double LLM cost per turn (15 RPM exhaustion) | Rules-first guard_input; LLM fallback gated behind `GUARD_INPUT_USE_LLM_FALLBACK=False` default | `test_injection_blocks_planner_call` proves planner Gemini is never called on refused turns |
| 3 | Indirect injection via Tavily / googlemaps tool output | `DATA_NOT_INSTRUCTIONS_CLAUSE` appended to fuel/route/search prompts | `test_tool_output_prompts_have_data_clause` |
| 4 | Gemini safety filter false-positive on adversarial classification (LLM fallback path) | `_llm_fallback` wraps in try/except; `finish_reason in (SAFETY, RECITATION)` mapped to `injection` (refuse-leaning) | Code path covered by inspection (LLM fallback off by default in CI) |
| 5 | Guard trace entries pollute D-04 loop-budget counter | Trace entries tagged `agent='guard_input'` or `agent='guard_output'` (NEVER 'planner') | `test_trace_entry_shape`, `test_violation_emits_trace` |
| 6 | Output guard trips on legitimate clarify path | guard_output wired AFTER pricing only; clarify path goes planner -> response directly | `test_clarify_path_skips_guard_output` |

## Decisions Taken (Claude's Discretion zones from CONTEXT)

- **Refusal taxonomy:** input layer — `injection / off_topic / cost_bombing / unclear / allow`; output layer — `allow / unsafe_output`. Folded the original CONTEXT-suggested `abuse` into `off_topic` because the off-topic regex set already catches the abuse subset and a smaller taxonomy is easier to review at demo time.
- **Trace shape:** allow path emits **zero** trace entries (zero-overhead, mirrors hitl_gate low-value bypass). Refused path emits exactly **one** entry with `tool=None`, `tool_input.text_preview` truncated to 80 chars, `tool_output={category, refused, ...}`, ISO-8601 'Z' timestamp, `status='warn'`.
- **Fresh-turn reset:** counts user messages vs `agent='response'` trace entries (mirrors `_next_turn_idx` in the chat handler). Reset is emitted as a NEGATIVE delta equal to the prior count — the alternative of using a non-additive reducer would crash the Phase 5 D-01 fuel/route parallel fan-out with `InvalidUpdateError`.
- **Refusal copy wording:** kept verbatim from CONTEXT D-03; not branched per category. Judges see the same line on every refusal so the demo is predictable AND post-demo grep is trivial.
- **Status vocabulary:** backend emits new `'refused'` and `'guard_failed'` statuses on the `final_payload`. FE `FinalStatus` Literal extension is intentionally **out of scope** for this quick task — the FE will fall through its unknown-status text rendering until a follow-up plan extends the Literal.

## Auto-fixed Deviations (Rules 1–3)

### 1. [Rule 1 — Bug] AgentState.tool_call_count needs operator.add reducer
- **Found during:** Task 2 GREEN verification, full-suite run
- **Issue:** Initial implementation declared `tool_call_count: int` with last-write-wins semantics per the plan's "single owner per superstep" assumption. The first full-suite run failed 17 tests with `langgraph.errors.InvalidUpdateError: At key 'tool_call_count': Can receive only one value per step`. Root cause: the Phase 5 D-01 parallel fan-out edge promotes `next_step` to `fanout_fuel_route`, and BOTH `fuel_agent_node` and `route_agent_node` write `tool_call_count` in the same Pregel superstep — `LastValue` channel cannot accept multiple concurrent writes.
- **Fix:** Switched to `Annotated[int, operator.add]` reducer. Updated all 4 tool nodes to emit a `+1` DELTA (not an absolute count) so the reducer aggregates correctly. Updated `guard_input` to emit a NEGATIVE delta equal to the prior count when resetting on a fresh turn (so the running total lands at 0). Updated 2 unit tests to assert the new delta semantics. The reducer is now load-bearing across the entire feature.
- **Files modified:** `backend/agent/state.py`, all 4 tool nodes, `guard_input.py`, `test_guard_input.py`, `test_tool_call_counter.py`
- **Commit:** Folded into `9d4e67b` (Task 2)

### 2. [Rule 1 — Bug] test_hitl_gate topology test asserts replaced edge
- **Found during:** Task 3 full-suite verification
- **Issue:** `test_hitl_gate.py::test_graph_topology_pricing_to_hitl_to_response` was authored against the Phase 5 graph topology that had a direct `pricing -> hitl_gate` edge. Task 3's wiring change replaces that edge with `pricing -> guard_output -> hitl_gate`, so the test rightly failed.
- **Fix:** Updated the assertions to reflect the new chain — asserts `(pricing, guard_output)` AND `(guard_output, hitl_gate)` AND `(hitl_gate, response)` AND that the direct `(pricing, hitl_gate)` edge is REPLACED (not augmented). In-scope per the SCOPE BOUNDARY rule because the wiring change directly caused the failure.
- **Files modified:** `backend/tests/test_hitl_gate.py`
- **Commit:** Folded into `b961afe` (Task 3)

## Authentication Gates

None encountered. The guardrails feature is purely defensive Python + prompt edits — no new external services, no new credentials.

## Out-of-Scope Items Deferred

- **FE `FinalStatus` Literal extension for `'refused'` / `'guard_failed'`** — Task 2 action note documented this. FE will treat the new statuses as text fallback. Follow-up FE polish quick task can extend the Literal post-demo.
- **Langfuse Score auto-attachment for guard trips** — RESEARCH Open Question 3 recommended a `guard_trip` Score reusing the Phase 5 `seed_trace_id` plumbing. Deferred to keep the blast radius small for the demo cycle. Refused turns DO show up in Langfuse traces because the existing CallbackHandler captures all node executions; only the Score-row tagging is deferred.
- **LLM fallback in `guard_input`** — implementation is wired (`_llm_fallback`) but the env flag defaults to False so the rules-first path is the only thing exercised in CI. Team can flip `GUARD_INPUT_USE_LLM_FALLBACK=true` right before the demo if the dry-run pack shows misses (RESEARCH Open Question 1).

## Manual Dry-Run Instructions

```bash
# Start the backend
cd /Users/pollot/Desktop/express-dynamic-workflow
source .venv/bin/activate
uvicorn backend.api.main:app --reload --port 8000

# In another terminal: pipe each non-comment line through /api/chat
# (or use the FE chat box at http://localhost:3000).
# Expected behaviour:
#   - Injection / off-topic lines  -> REFUSAL_COPY string + reasoning trace
#                                     shows a guard_input step (status='warn').
#   - Cost-bombing lines           -> Either refused outright OR completes
#                                     within MAX_TOOL_CALLS_PER_TURN budget
#                                     without burning Gemini quota.

while IFS= read -r line; do
  case "$line" in '#'*|'') continue;; esac
  echo "----- $line -----"
  curl -s -X POST http://localhost:8000/api/chat \
       -H 'Content-Type: application/json' \
       -d "$(jq -nR --arg msg "$line" '{thread_id:"dryrun", message:$msg}')" | head -40
done < backend/tests/adversarial_pack.txt
```

## Restart Guidance

**Uvicorn must be restarted to pick up the new graph wiring.** The compiled LangGraph object is constructed inside the FastAPI lifespan handler — running servers hold the OLD graph in memory. Test suites import `build_graph` fresh per run so CI doesn't need a restart, but a live server does.

```bash
# kill the current uvicorn, then re-launch
uvicorn backend.api.main:app --reload --port 8000
```

## Self-Check: PASSED

- [x] All files in `key_files.created` exist (verified via `ls`)
- [x] All commits exist:
  - `a5f0fb7` (Task 1): `git log --oneline | grep a5f0fb7` -> FOUND
  - `9d4e67b` (Task 2): `git log --oneline | grep 9d4e67b` -> FOUND
  - `b961afe` (Task 3): `git log --oneline | grep b961afe` -> FOUND
- [x] Full backend test suite green: 295 passed
- [x] No new external dependencies (`git diff requirements.txt` empty)
- [x] All 4 attack surfaces from CONTEXT defended (injection / off_topic / cost_bombing / unsafe_output)
- [x] All 5 RESEARCH-derived requirements (UTD-01..05) implemented with passing tests
- [x] Guard trace entries tagged `agent='guard_input'` / `agent='guard_output'` (Pitfall 5 verified by tests)
- [x] No stubs that block the plan's goal
