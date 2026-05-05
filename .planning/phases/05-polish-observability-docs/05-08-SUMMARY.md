---
phase: 05-polish-observability-docs
plan: 08
subsystem: agent-orchestration
tags: [planner, langgraph, gemini, followup-inheritance, gap-closure, uat]

# Dependency graph
requires:
  - phase: 03-graph-assembly-api-layer
    provides: planner_node + 999.1 null-only state-merge
  - phase: 05-polish-observability-docs
    provides: Plan 05-03 fan-out promotion + Plan 05-04 search_context routing (gap-1 fix must preserve both)
provides:
  - "gap-1 fix: defensive null-out branch for hallucinated extraction fields when user_intent='followup_query' (runs BEFORE the 999.1 merge so explicit overrides still win)"
  - "Tightened planner SYSTEM_PROMPT with explicit followup_query inheritance contract and concrete 25kg-instead example"
  - "Two unit-level regression tests + one E2E integration test reproducing UAT test 3 verbatim"
affects: [demo-prep, phase-05-uat, orch-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Null-only inheritance branch ABOVE the 999.1 null-coalesce — preserves explicit-override semantics"
    - "User-message token check (lowercased substring + shipping-type keyword set + digit detection for weight) as the explicit-override signal"

key-files:
  created: []
  modified:
    - "backend/agent/prompts/planner.py — SYSTEM_PROMPT inheritance paragraph"
    - "backend/agent/nodes/planner.py — gap-1 inheritance branch BEFORE 999.1 merge"
    - "backend/tests/test_planner.py — 2 new unit tests"
    - "backend/tests/test_graph.py — 1 new E2E integration test"

key-decisions:
  - "gap-1 branch is defense-in-depth: prompt update tells the LLM to emit null on unmentioned followup fields; the post-LLM null-out branch defends against Gemini ignoring the contract"
  - "Token detection for shipping_type uses both the parsed token AND a fixed keyword set (bounce, retail_standard, retail_fast etc.) — covers the case where the LLM emits a hallucinated value but the user message contains a DIFFERENT shipping-type keyword"
  - "weight_kg uses digit detection (any(c.isdigit()) in user message) as the explicit-override signal — simpler than NLP and covers '25kg', '25 kilos', 'change to 30', etc."
  - "Inheritance only fires when prior state has a value (avoids erasing genuinely fresh extractions on the first turn of a thread that happens to be classified as followup_query)"

patterns-established:
  - "Defense-in-depth follow-up inheritance: SYSTEM_PROMPT contract + post-LLM null-out + null-only 999.1 merge — three layers cooperating to inherit unmentioned fields without overriding explicit ones"

requirements-completed: [ORCH-07]

# Metrics
duration: ~25min
completed: 2026-05-03
---

# Phase 05 Plan 08: gap-1 Follow-up Hallucination Fix Summary

**Defensive null-out branch in planner_node that prevents the LLM from corrupting cached follow-up state when it hallucinates truthy values for fields the user did not explicitly mention.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-03T17:35Z (continuation of Phase 5 gap-closure wave)
- **Completed:** 2026-05-03 (TBD timestamp)
- **Tasks:** 2 (both autonomous)
- **Files modified:** 4 (1 prompt, 1 node, 2 test files)

## Accomplishments

- Restored Phase 5 ROADMAP success criterion #3 (cache reuse on follow-ups produces correct numbers, not just correct routing)
- ORCH-07 (parallel fan-out) demo evidence remains valid — cache-skip path on follow-ups now produces correct surcharge with inherited shipping_type/destination
- UAT test 3 ("What about 25kg instead?" preserves bounce + Nonthaburi) now passes end-to-end against the assembled graph

## Task Commits

Each task was committed atomically with `--no-verify` per parallel-execution discipline:

1. **Task 1: Tighten planner SYSTEM_PROMPT for followup_query inheritance** — `60df0c3` (feat)
2. **Task 2: Add followup-aware inheritance to planner_node + regression tests** — `710fb9c` (fix)

**Plan metadata:** TBD (final commit with SUMMARY.md + STATE.md + ROADMAP.md)

## Files Created/Modified

- `backend/agent/prompts/planner.py` — SYSTEM_PROMPT now contains a "Follow-up query inheritance (D-05/999.1)" paragraph between the user_intent enum and the Normalisation rules. Names the four inheritable fields (shipping_type, weight_kg, origin, destination), instructs the LLM to emit null for unmentioned fields on followup_query, gives a concrete "What about 25kg instead?" example, and clarifies that surcharge_query queries should still extract every field provided.
- `backend/agent/nodes/planner.py` — New gap-1 fix block inserted BETWEEN the existing parse loop and the 999.1 merge (line 203, with the merge at line 263). The block runs only when `parsed.user_intent == "followup_query"` and selectively nulls out parsed.shipping_type / parsed.origin / parsed.destination / parsed.weight_kg when prior state has a value AND the current user message lacks a token that would explain the LLM's emission. Token detection per field:
  - **shipping_type:** lowercase user-message substring match against the parsed token, OR fallback fixed keyword set (`bounce`, `retail_standard`, `retail standard`, `retail_fast`, `retail fast`).
  - **destination / origin:** lowercase substring match against EITHER the prior-state value OR the parsed token.
  - **weight_kg:** any-digit check on the user message (digits = explicit weight override signal).
  All 999.1, 999.3, Phase 5 D-01 (fan-out), and D-12 (cache-aware) blocks below remain unchanged.
- `backend/tests/test_planner.py` — Appended two unit tests:
  - `test_followup_inherits_unmentioned_fields` — prior state full (bounce/15/Bangkok/Nonthaburi); message "What about 25kg instead?"; LLM emits hallucinated retail_standard + Chiang Mai. Asserts shipping_type='bounce', weight_kg=25, origin='Bangkok', destination='Nonthaburi' after planner_node.
  - `test_followup_explicit_override_wins_over_inheritance` — same prior state; message "Switch to retail_fast"; LLM emits retail_fast + three nulls. Asserts shipping_type='retail_fast' (override wins), other three inherited.
- `backend/tests/test_graph.py` — Appended `test_followup_25kg_preserves_bounce_and_nonthaburi`, an E2E reproducer for UAT test 3. Turn 1: standard surcharge query establishes caches + bounce + Nonthaburi. Turn 2: "What about 25kg instead?" with the planner LLM scripted to hallucinate retail_standard + Chiang Mai. Asserts post-turn-2 snapshot.values shows shipping_type='bounce', destination='Nonthaburi', weight_kg=25.0, AND that fuel + route caches were NOT re-fetched (D-12 still works because destination inheritance preserves the route_match).

## Decisions Made

- **gap-1 branch is null-only — explicit overrides still win.** The branch erases parsed.X only when prior state has a value AND the user message lacks a recognisable token. If the user said "switch to retail_fast", the token "retail_fast" appears in the message, the branch leaves parsed.shipping_type alone, and the 999.1 merge accepts the explicit value.
- **Token detection uses lowercase substring matching + shipping-type keyword set.** Robust enough for the demo (handles "Bounce", "bounce", "retail standard", "retail_standard"); not full NLP. The plan-spec'd detection is intentional — heavier intent classification would belong in the planner prompt, not the post-processor.
- **weight_kg uses digit detection.** Any digit in the user message is treated as an explicit weight signal. This covers "25kg", "change to 25 kilos", "make it 30", etc. The risk of a non-weight digit triggering a stale-weight override is low given the conversational shape of follow-ups.
- **Inheritance only fires when prior state has a value.** Prevents erasing genuinely fresh extractions on the first turn of a thread that happens to be classified as followup_query (defensive — should be rare given D-07 enum semantics).

## Deviations from Plan

None — plan executed exactly as written. The two-task structure with TDD-flavoured Task 2 (RED→GREEN→full-suite verify) ran cleanly:

- RED phase: new unit tests + integration test failed as expected on the unmodified planner_node.
- GREEN phase: gap-1 fix block insertion turned all 3 new tests green without touching any of the existing 999.1 / 999.3 / fan-out / D-12 blocks below it.
- Verify phase: 178/178 backend tests passing (172 baseline + 3 new from this plan + the 3-test delta from parallel Plan 05-09 already on the branch).

## Issues Encountered

- **Test scripting subtlety (resolved without code change):** The integration test's first RED run revealed that without the fix, the LLM-response cycle of FakeMessagesListChatModel CYCLES past 3 entries because the planner re-enters multiple times when route_data does not match the hallucinated destination. With the fix in place, turn 2 only requires ONE planner LLM call (followup → inheritance → cache-hit → calculate_price → respond), so the original 1-response turn-2 script size is correct for the FIXED behaviour. The test asserts the fix is in place by virtue of NOT cycling past the scripted hallucination on turn 2.

## User Setup Required

None — code-only change. No env vars, no external service config.

## Next Phase Readiness

- gap-1 closed; UAT test 3 demo prep can resume.
- Plans 05-09 (gap-2 zone-miss) and 05-10 (gap-3 search-loop) are running in parallel and remain orthogonal to this fix.
- ORCH-07 parallel-fan-out demo evidence stays valid — cache-reuse path on follow-ups now produces correct surcharge numbers.

## Self-Check: PASSED

**Files verified:**
- FOUND: backend/agent/prompts/planner.py (gap-1 paragraph present)
- FOUND: backend/agent/nodes/planner.py (gap-1 fix block at line 203, 999.1 merge preserved at line 263)
- FOUND: backend/tests/test_planner.py (2 new tests)
- FOUND: backend/tests/test_graph.py (1 new test)

**Commits verified:**
- FOUND: 60df0c3 (feat(05-08): tighten planner SYSTEM_PROMPT...)
- FOUND: 710fb9c (fix(05-08): close gap-1 — null-out hallucinated fields...)

**Test suite:** 178/178 backend tests passing (verified via `.venv/bin/pytest backend/tests/ --no-header`).

---
*Phase: 05-polish-observability-docs*
*Completed: 2026-05-03*
