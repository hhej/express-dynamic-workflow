---
phase: 05-polish-observability-docs
plan: 05
subsystem: agent
tags: [hitl, langgraph, interrupt, command-resume, sse, response-node, approval-gate]

requires:
  - phase: 05-polish-observability-docs/01
    provides: HITL_TOTAL_THB_THRESHOLD config, AgentState.approval_decision field
  - phase: 05-polish-observability-docs/02
    provides: _make_config helper, _next_turn_idx, deterministic langfuse_trace_id metadata (resume reuses Pitfall 1)
  - phase: 05-polish-observability-docs/04
    provides: search_agent in _NODE_NAMES filter, response_node Market context prefix (preserved on deny path)
provides:
  - backend/agent/nodes/hitl_gate.py — HITL gate node (bypass / interrupt / resume paths)
  - Graph topology: pricing_agent → hitl_gate → response (replaces pricing → planner; Pitfall 6 invariant)
  - Sixth SSE event type "approval_required" (D-06)
  - POST /api/chat resume contract: {thread_id, approve} → Command(resume=approve)
  - response_node deny short-circuit: status='partial', no breakdown table, prose contains 'declined'
affects: [05-06-feedback-frontend, 05-07-docs-tag]

tech-stack:
  added: []  # langgraph.types.{interrupt, Command} already in dependency tree
  patterns:
    - "HITL via langgraph.types.interrupt() + Command(resume=...) — pause inside node, resume by invoking the graph again with a Command sentinel; the interrupt() return value IS the resume value (D-05/D-07)"
    - "Pitfall 1: resume reuses _make_config so Langfuse callbacks + metadata + deterministic trace_id are preserved across the pause"
    - "Pitfall 2: stream emitting approval_required closes WITHOUT a trailing 'done' so FE keeps Approve/Deny buttons live; pending_approval flag in finally block enforces this"
    - "Pitfall 6: pricing → hitl_gate → response replaces pricing → planner in-turn loop edge — pricing is the final compute step within a turn, next-turn planner loop is entered via fresh chat invocations"
    - "Centralized _drain_events helper — fresh and resume paths share the SAME astream_events filter logic so no contract drift can creep in"
    - "Bypass path on hitl_gate emits ZERO trace entries (low-value totals) — keeps the common case overhead-free; only high-value totals emit pre-pause warn + post-resume ok trace pair (D-08)"

key-files:
  created:
    - backend/agent/nodes/hitl_gate.py
    - backend/tests/test_hitl_gate.py
    - .planning/phases/05-polish-observability-docs/05-05-SUMMARY.md
  modified:
    - backend/agent/graph.py
    - backend/api/sse.py
    - backend/api/routes/chat.py
    - backend/agent/nodes/response_node.py
    - backend/tests/test_response_node.py
    - backend/tests/test_api_chat.py
    - backend/tests/test_graph.py

key-decisions:
  - "HITL gate uses langgraph.types.interrupt() (Pattern 2) rather than a custom polling loop — graph pauses cleanly, checkpointer persists the paused state, resume is a single Command(resume=...) call"
  - "Bypass path (low-value totals) returns just {approval_decision: 'approve'} with NO trace entry — zero trace bloat for the ~91% of demo queries below the 500 THB threshold"
  - "interrupt() return value mapping: True (bool) and 'approve' (string) → 'approve'; anything else → 'deny' — defensive against frontend serialisation surprises while still booleanly clean"
  - "Pricing → hitl_gate → response REPLACES pricing → planner — pricing is the final compute step within a turn; the next-turn planner loop is entered via fresh POST /api/chat calls, not via the in-turn planner loop edge (Pitfall 6 invariant; documented inline)"
  - "Sixth SSE event type approval_required is added INTO the EventType Literal (not a sibling Literal) — keeps a single source of truth for the SSE contract and the static-type check forces all emit sites to update together"
  - "Resume path requires thread_id; missing → HTTP 400 (defensive — without thread_id the checkpointer cannot locate the paused state)"
  - "Resume path turn_idx clamps at max(0, turn_idx-1) — _next_turn_idx returns count of user messages already on thread; the resume call does NOT add a new user message so the in-flight turn is one less than the next-fresh-turn count"
  - "response_node deny path nulls out surcharge_result in the final_payload AND emits no breakdown table (D-07) — the FE must clearly distinguish accepted vs declined recommendations; preserves Market context prefix (D-11) on deny path"
  - "_drain_events centralizes astream_events filter logic — fresh and resume paths cannot drift apart on what counts as a trace/answer event"

requirements-completed:
  - ORCH-09

duration: ~25 min agent + ~10 min wrap-up (Task 1 by prior agent ~15 min)
completed: 2026-05-03
---

# Phase 5 Plan 05: HITL Approval Gate Summary

**ORCH-09 HITL gate via langgraph.types.interrupt() + Command(resume) — pricing → hitl_gate → response topology, sixth SSE event approval_required, response_node deny short-circuit, Pitfall 1+2 mitigations enforced**

## Performance

- **Duration:** ~50 min total (Task 1 by prior agent + Task 2 by this agent + wrap-up)
- **Started:** 2026-05-03 (Task 1: hitl_gate_node + graph topology)
- **Completed:** 2026-05-03T09:38Z
- **Tasks:** 2 (Task 1 hitl_gate_node + graph topology; Task 2 SSE + chat resume + response_node deny path)
- **Files modified:** 9 (2 new, 7 modified)

## Accomplishments
- `hitl_gate_node` with bypass / interrupt / resume paths (D-04 / D-05 / D-07 / D-08)
- Graph topology updated: `pricing_agent → hitl_gate → response` replaces `pricing → planner` (Pitfall 6 invariant documented inline)
- Sixth SSE event type `approval_required` (D-06) — emitted on pause, NOT followed by `done` (Pitfall 2)
- POST /api/chat resume contract: `{thread_id, approve}` → `Command(resume=approve)` (D-06) reusing `_make_config` (Pitfall 1)
- `response_node` deny short-circuit: `status='partial'`, `surcharge_result=None`, prose contains "declined", NO breakdown table; Market context prefix (D-11) preserved on deny
- `_drain_events` helper centralizes `astream_events` filter logic across fresh + resume paths
- `_NODE_NAMES` extended with `search_agent` (Plan 05-04) and `hitl_gate` (Plan 05-05) so their `reasoning_trace` entries flow through the SSE trace channel
- Backend test suite green: **166/166 passing** (was 161 before this plan; +5 new HITL chat tests, deny/approve response_node tests already counted in the 161 from prior agent)

## Task Commits

1. **Task 1 RED:** `d66e7f3` — `test(05-05): add failing tests for hitl_gate_node + graph topology (RED)` (prior agent)
2. **Task 1 GREEN:** `95c740e` — `feat(05-05): implement hitl_gate_node + topology pricing -> hitl_gate -> response (GREEN)` (prior agent)
3. **Task 2 RED:** `572621e` — `test(05-05): add failing tests for SSE + chat resume + response_node deny path (RED)`
4. **Task 2 GREEN:** `e9a60b3` — `feat(05-05): wire approval_required SSE + Command(resume) + deny path (GREEN)`

**Plan metadata:** _pending docs commit_

## Files Created/Modified

### New
- `backend/agent/nodes/hitl_gate.py` — D-05 gate (bypass low-value, interrupt high-value, map resume value to approve/deny + trace pair)
- `backend/tests/test_hitl_gate.py` — 6 tests (bypass / interrupt / resume approve / resume deny / low-value-no-trace + threshold-boundary)

### Modified
- `backend/agent/graph.py` — pricing → hitl_gate → response wiring; hitl_gate intentionally not error-sink-wrapped + no retry policy
- `backend/api/sse.py` — `EventType` Literal extended with `"approval_required"`
- `backend/api/routes/chat.py` — `_drain_events` helper, `_fresh_stream` (interrupt detection + Pitfall 2 no-done), `_resume_stream` (`Command(resume=...)` + Pitfall 1 reuse `_make_config`); `_NODE_NAMES` += {search_agent, hitl_gate}
- `backend/agent/nodes/response_node.py` — D-07 deny short-circuit ABOVE the standard precedence ladder; preserves Market context prefix on deny
- `backend/tests/test_response_node.py` — 3 new tests (deny without table; approve renders status='ok'; deny with Market context)
- `backend/tests/test_api_chat.py` — 5 new tests (EventType.__args__ contains approval_required; pause emits approval_required without trailing done; resume approve → status='ok'; resume deny → status='partial' + 'declined'; resume reuses _make_config Pitfall 1)
- `backend/tests/test_graph.py` — Task 1 topology assertions (added by prior agent in 95c740e)

## Decisions Made

See `key-decisions:` frontmatter list for the full set. Highlights:
- **interrupt() over polling** — clean LangGraph-native pause; checkpointer persists paused state for free.
- **Bypass = zero trace** — keeps the common case overhead-free; only high-value totals emit a trace pair.
- **Pricing → hitl_gate → response replaces pricing → planner** — pricing is the final compute step within a turn (Pitfall 6).
- **Pitfall 1: resume reuses `_make_config`** — Langfuse session continuity preserved across the pause.
- **Pitfall 2: no `done` after `approval_required`** — `pending_approval` flag in `finally` block enforces this; FE keeps Approve/Deny buttons live.
- **`_drain_events` centralizes filter** — fresh + resume cannot drift on what counts as a trace/answer event.

## Threshold Configuration

`HITL_TOTAL_THB_THRESHOLD` defaults to **500.0 THB** (set in `backend/config.py`). Override via env:

```bash
export HITL_TOTAL_THB_THRESHOLD=200.0  # demo more frequent gating
export HITL_TOTAL_THB_THRESHOLD=10000.0  # effectively disable for end-to-end smoke
```

Calibrated against `data/express.db` rate distribution to gate ~9% of representative demo queries (per RESEARCH §HITL Threshold Calibration).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test fixture pattern adapted from `async_client` to TestClient**
- **Found during:** Task 2 (RED test authoring)
- **Issue:** Plan §Task 2 referenced an `async_client` fixture that does not exist in `backend/tests/conftest.py` — the existing test_api_chat.py uses sync `TestClient` from FastAPI.
- **Fix:** Adapted the 5 new HITL chat tests to use the existing `app_with_mocks` + `TestClient` pattern with a `_make_stub_graph` helper that constructs a MagicMock graph (`astream_events` + `aget_state`).
- **Files modified:** backend/tests/test_api_chat.py
- **Verification:** All 5 new tests + 4 existing tests pass.
- **Committed in:** 572621e (RED) + e9a60b3 (GREEN, included the install-stub-AFTER-lifespan fix because lifespan replaces app.state.graph with the real compiled graph)

**2. [Rule 1 - Bug] Stub graph install timing**
- **Found during:** Task 2 GREEN verification (first pytest run after implementation)
- **Issue:** Initial test pattern installed the MagicMock graph BEFORE entering `with TestClient(app) as client:` — but the FastAPI lifespan runs on TestClient enter and overwrites `app.state.graph` with the real compiled graph, so the stub was lost.
- **Fix:** Move stub assignment to AFTER `with TestClient(app_with_mocks) as client:` enters; stub installation happens inside the `with` block.
- **Files modified:** backend/tests/test_api_chat.py (3 affected tests)
- **Verification:** All 21 target tests now pass; full suite 166/166 green.
- **Committed in:** e9a60b3 (rolled into GREEN commit since it's part of Task 2 wiring)

---

**Total deviations:** 2 auto-fixed (1 blocking — fixture pattern, 1 bug — stub timing)
**Impact on plan:** Both fixes mechanical; neither changes the contract. Test coverage matches plan §Task 2 §behavior list verbatim (7 tests including the response_node pair).

## Issues Encountered

None — plan §Task 2 action steps applied cleanly aside from the test fixture adaptations above.

## Acceptance Criteria

All Plan 05-05 §verification checks pass:
- ✅ `.venv/bin/pytest backend/tests/test_hitl_gate.py -x -q` exits 0
- ✅ `.venv/bin/pytest backend/tests/test_response_node.py -x -q` exits 0
- ✅ `.venv/bin/pytest backend/tests/test_api_chat.py -x -q` exits 0 (5 new HITL tests + 4 existing)
- ✅ `.venv/bin/pytest backend/tests/ -q` → 166 passed
- ✅ `grep` checks (10/10): approval_required in sse.py + chat.py; Command import + Command(resume= + snapshot.next + pending_approval + hitl_gate + search_agent in chat.py; approval_decision + declined in response_node.py
- ✅ Topology: `pricing_agent → hitl_gate` and `hitl_gate → response` edges present in `backend/agent/graph.py`

## User Setup Required

None — no external service configuration required for this plan. The HITL threshold is configured via `HITL_TOTAL_THB_THRESHOLD` env var with a 500 THB default.

## Next Phase Readiness

Backend HITL plumbing is complete and proven by the test suite. Plan 05-06 (frontend feedback + HITL Approve/Deny UI) can now consume:
- The sixth SSE event type `approval_required` carrying `{thread_id, surcharge_result, threshold}`.
- The resume contract: `POST /api/chat` with `{thread_id, approve: bool}` returns the resumed stream (status='ok' or status='partial').
- The Pitfall 2 invariant: `approval_required` is the LAST event in the stream — frontend can rely on stream-end-without-`done` as the "show buttons" signal.

## Self-Check: PASSED

Verified files exist:
- `backend/agent/nodes/hitl_gate.py` — FOUND
- `backend/tests/test_hitl_gate.py` — FOUND
- `backend/api/sse.py` — FOUND (modified)
- `backend/api/routes/chat.py` — FOUND (modified)
- `backend/agent/nodes/response_node.py` — FOUND (modified)
- `backend/tests/test_response_node.py` — FOUND (modified)
- `backend/tests/test_api_chat.py` — FOUND (modified)

Verified commits exist:
- `d66e7f3` — FOUND (Task 1 RED)
- `95c740e` — FOUND (Task 1 GREEN)
- `572621e` — FOUND (Task 2 RED)
- `e9a60b3` — FOUND (Task 2 GREEN)

---
*Phase: 05-polish-observability-docs*
*Completed: 2026-05-03*
