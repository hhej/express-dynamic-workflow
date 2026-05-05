---
status: resolved
phase: 05-polish-observability-docs
source: [manual orchestrator UAT — Phase 5 demo prep, 7-question test set]
started: 2026-05-03T10:41Z
updated: 2026-05-03T18:30Z
---

## Current Test

[manual UAT complete; 3 critical bugs blocking demo recording and v1.0 tag]

## Tests

### 1. Standard surcharge with parallel fan-out (Q1)
expected: 15kg bounce Bangkok→Nonthaburi → ~140 THB total, fuel_agent + route_agent in same trace superstep
result: PASS — 139.89 THB, parallel fan-out timestamps overlap (fuel + route both at step 2)

### 2. Standard surcharge retail_standard (Q2)
expected: 8kg retail_standard Bangkok→Pathum Thani → ~77 THB total
result: PASS — 77.11 THB, central-1 zone correct

### 3. Follow-up query reuses cached state (Q3)
expected: After Q1 completes, "What about 25kg instead?" should preserve shipping_type=bounce + destination=Nonthaburi from prior turn, only swap weight to 25kg
result: FAIL — planner emitted shipping_type=retail_standard (was bounce) AND destination=Chiang Mai (was Nonthaburi). Used cached Nonthaburi route metrics (19.2 km central-1) but applied retail_standard's 0.5x multiplier. **Surcharge calculation is wrong by ~5 percentage points.**

### 4. HITL trigger via Ayutthaya central-3 query (Q4)
expected: 200kg retail_fast Bangkok→Ayutthaya → route resolves to central-3, surcharge > 500 THB → approval_required SSE event
result: FAIL — hard error: `No Bangkok Metro zone for 'Ayutthaya'`. Error event emitted, no graceful clarify response. **Bangkok Metro rename (quick task 260425-vc6) shrank zone coverage but route tool still raises uncaught ValueError on out-of-Metro provinces.**

### 5. HITL trigger via Saraburi (Q5)
expected: 300kg bounce Bangkok→Saraburi → surcharge > 500 THB → approval_required
result: PASS — 511.15 THB, `approval_required` SSE event emitted with surcharge_result + threshold + thread_id payload

### 6. Search agent / news intent (Q6)
expected: "Why are diesel prices rising this week?" → planner routes once to search_context → search_agent populates state → response renders Market context blockquote + news-appropriate prose
result: FAIL — planner classified as `user_intent="out_of_scope"` and routed to `search_context` 5 TIMES IN A ROW (loop budget exhausted at step 11). Tavily called 5x (cache hit so no double-billing, but 5 redundant LLM planner calls). Response correctly renders Market context blockquote with sources, BUT the prose body wrongly says "I need a bit more information to calculate your surcharge. (planner_loop_budget_exhausted)" — misleading user message for a news query. **Planner doesn't recognize state.search_context being populated as the search step being done.**

### 9. Clarification path (Q9)
expected: "Calculate a surcharge" with no fields → clean clarify response listing missing fields
result: PASS — single planner step → response with clarify status, lists shipping_type/weight_kg/origin/destination

### 10. User-supplied traffic hint (Q10)
expected: "during heavy traffic" hint should at least be reflected in trace OR override live Google Maps signal
result: WARN — live Google Maps measured traffic_severity=1 (light) and the agent ignored the user's "heavy traffic" hint silently. No mention in reasoning trace. Working as designed (live > user hint) but not honest about the override.

## Summary

total: 7
passed: 4
issues: 3
pending: 0
skipped: 0
blocked: 0

## Gaps

### gap-1: follow-up planner hallucinates context
status: resolved
resolved_by: 05-08
test: 3
severity: critical
symptom: |
  After a successful surcharge calculation, a follow-up query that swaps only ONE field
  ("What about 25kg instead?") causes the planner to fabricate fresh values for
  shipping_type and destination instead of preserving the prior turn's state.
  The cached route_data is reused (so distance/zone are right) but the calculation
  uses the wrong multiplier and the prose names a city that was never in the conversation.
suspected_root_cause: |
  PlannerOutput schema requires shipping_type/weight_kg/origin/destination on every turn.
  The Phase 3 D-05 contract says missing fields should be inherited from prior state,
  but the LLM is treating each turn as a fresh extraction even when user_intent="followup_query".
  Either (a) the system prompt doesn't explicitly tell the LLM to inherit prior fields when
  they're not in the user message, or (b) the planner_node post-processing isn't merging
  prior state into the LLM output.
remediation_hint: |
  In planner_node, after the LLM call but before returning, inherit any field that the
  LLM left null/None from the prior AgentState (shipping_type, weight_kg, origin, destination).
  Add a regression test seeding a thread with one full turn, then sending "What about Nkg instead?"
  and asserting all non-weight fields are preserved.
  Also tighten the planner SYSTEM_PROMPT to say "for followup_query, only override fields the user
  explicitly mentions; leave the rest null and let the post-processor inherit from prior state."
debug_session: null

### gap-2: hard crash on out-of-Metro province
status: resolved
resolved_by: 05-09
test: 4
severity: critical
symptom: |
  Querying for a destination outside the Bangkok Metro zone set (e.g. Ayutthaya) raises
  an uncaught ValueError "No Bangkok Metro zone for 'Ayutthaya'" that propagates as an
  SSE error event. No clarify response, no fallback. The user is left with a dead conversation.
  This is especially bad because the README's data sources still imply broader Thai
  central-region coverage that the route tool no longer supports after the
  Bangkok Metro rename (quick task 260425-vc6).
suspected_root_cause: |
  In backend/agent/tools/calculate_route.py, the zone lookup raises ValueError when a province
  doesn't match _ZONE_INDEX. The Phase 5 error sink wraps tool nodes (D-22 retry policy) but
  ValueError is intentionally non-retryable, so it bubbles. There's no clarify-on-zone-miss path.
remediation_hint: |
  Two-part fix:
  1. In route_agent_node, catch the "No Bangkok Metro zone" ValueError and convert it to a
     clarify-eligible state.errors entry; let the planner short-circuit to clarify with a
     message like "I can only calculate surcharges for Bangkok Metro destinations. Try a
     province in central-1/2/3."
  2. Audit README.md + docs/architecture.md + docs/data-sources.md to be explicit about the
     supported province list (central-1: Bangkok + Nonthaburi + Samut Prakan; central-2:
     Pathum Thani + Nakhon Pathom + Samut Sakhon; central-3: Saraburi + ...).
     Document which provinces from the original Central Region were dropped.
debug_session: null

### gap-3: search agent infinite loop on news intent
status: resolved
resolved_by: 05-10
test: 6
severity: critical
symptom: |
  News/trend queries trigger the planner to route to search_context repeatedly until the
  loop-budget guard exhausts (~5 iterations). Each iteration re-runs search_agent (Tavily
  cache prevents real API duplication, but the LLM planner is called 5 extra times).
  The final response renders the Market context blockquote correctly with sources, BUT
  the prose body wrongly says "I need a bit more information to calculate your surcharge.
  (planner_loop_budget_exhausted)" — completely off-topic for a news query.
  Two underlying issues:
  - user_intent classified as "out_of_scope" instead of a dedicated news/search intent
  - planner doesn't check `state.search_context is not None` to know the search step is done
suspected_root_cause: |
  Plan 05-04 added news-intent routing to the planner SYSTEM_PROMPT and bypassed the
  cache-aware override for next_step=="search_context", but it did NOT add a guard for
  "search_context already populated → route to respond". The planner re-runs after
  search_agent and re-routes to search_context again because the condition that triggered
  the route (news intent in user message) is still true and there's no "search done" sentinel.
remediation_hint: |
  In planner_node, before the LLM call, add an early-return guard:
  if state.get("search_context") is not None and state.get("user_intent") in {"news_query", "out_of_scope"}:
      next_step = "respond"
  Plus update response_node so when the response is rendered FROM a search_context-only
  flow (no surcharge_result), the prose says something like "Here's the latest market context"
  instead of falling through to the clarify template.
  Also consider adding a dedicated user_intent="news_query" enum value so news queries don't
  share the "out_of_scope" bucket with truly unsupported queries.
debug_session: null

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
