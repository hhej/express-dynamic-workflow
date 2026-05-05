---
phase: 08-search-context-sidebar-polish
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/agent/nodes/response_node.py
  - backend/tests/test_response_node.py
  - frontend/types/agent.types.ts
  - frontend/components/chat/MessageList.tsx
  - frontend/__tests__/components/MessageList.search_only.test.tsx
autonomous: true
requirements:
  - TOOL-05
  - UI-02
gap_closure: true

must_haves:
  truths:
    - "response_node final_payload always carries search_context (the value, with None when state lacks it) on BOTH the happy path AND the deny path"
    - "FinalStatus union declares 'search_only' so TypeScript stops permitting silent fallthrough on that backend status"
    - "MessageList renderAssistant explicitly dispatches case 'search_only' to MarkdownAnswer"
    - "When backend emits status='search_only' with non-empty search_context, the rendered chat surface shows the typed Market context caption AND the collapsible Sources details with target=_blank rel=noopener noreferrer links AND no surcharge breakdown table"
    - "BE drift-prevention test catches a future regression that drops 'search_context' from final_payload (asserts both presence and None-when-absent)"
    - "FE drift-prevention test catches a future regression that loses the 'search_only' switch case in MessageList"
  artifacts:
    - path: "backend/agent/nodes/response_node.py"
      provides: "final_payload dict on happy path AND deny path includes 'search_context': state.get('search_context')"
      contains: '"search_context": state.get("search_context")'
    - path: "backend/tests/test_response_node.py"
      provides: "Two new assertions covering search_context presence + None-when-absent in final_payload"
      contains: 'final_payload"]["search_context"]'
    - path: "frontend/types/agent.types.ts"
      provides: "FinalStatus union extended with 'search_only'"
      contains: "'search_only'"
    - path: "frontend/components/chat/MessageList.tsx"
      provides: "Explicit case 'search_only' branch routing to MarkdownAnswer"
      contains: "case 'search_only':"
    - path: "frontend/__tests__/components/MessageList.search_only.test.tsx"
      provides: "Vitest test that mounts MessageList with status='search_only' and asserts SearchContextLine + sources + no surcharge table"
      contains: "status: 'search_only'"
  key_links:
    - from: "backend/agent/nodes/response_node.py happy-path final_payload (lines 307-312)"
      to: "frontend FinalPayload.search_context consumer in MarkdownAnswer.tsx"
      via: "always-present 'search_context' key on the SSE 'answer' event payload"
      pattern: 'state\.get\("search_context"\)'
    - from: "backend/agent/nodes/response_node.py deny-path final_payload (lines 232-241)"
      to: "frontend FinalPayload.search_context consumer in MarkdownAnswer.tsx"
      via: "same key forwarded on the deny branch so provenance survives decline"
      pattern: 'state\.get\("search_context"\)'
    - from: "frontend/components/chat/MessageList.tsx renderAssistant switch"
      to: "frontend/components/chat/MarkdownAnswer.tsx (which renders SearchContextLine when payload.search_context.summary is non-blank)"
      via: "explicit case 'search_only' return statement"
      pattern: "case 'search_only':\\s*\\n\\s*return <MarkdownAnswer"
---

<objective>
Close the backend half + frontend type/dispatch half of audit Issue 6 (`v1.0-MILESTONE-AUDIT.md` §2.3): make the Tavily news_query flow surface typed sources end-to-end. Today `response_node` builds `final_payload` without forwarding `state["search_context"]`, the FE `FinalStatus` union omits `'search_only'`, and `MessageList` falls through to the default `MarkdownAnswer` case implicitly. After this plan, BE always emits `search_context` (None-or-value) in `final_payload` on both the happy and deny paths, FE types declare `'search_only'`, and `MessageList` dispatches it explicitly to `MarkdownAnswer` (which already renders `SearchContextLine` when `payload.search_context.summary` is present).

Purpose: Restores TOOL-05 + UI-02 from "degraded" (markdown blockquote only) to fully satisfied (typed `SearchContextLine` with clickable sources visible in the chat answer).

Output:
- Backend: 1-line addition to two `final_payload` dict literals + 2 new pytest assertions
- Frontend: 1-token addition to `FinalStatus` + 1 case branch in `MessageList` switch + 1 new Vitest test file
</objective>

<execution_context>
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/workflows/execute-plan.md
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/08-search-context-sidebar-polish/08-CONTEXT.md
@.planning/phases/08-search-context-sidebar-polish/08-RESEARCH.md
@.planning/phases/08-search-context-sidebar-polish/08-VALIDATION.md
@.planning/v1.0-MILESTONE-AUDIT.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->
<!-- Executor should use these directly — no codebase exploration needed. -->

From frontend/types/agent.types.ts (current state, before this plan):
```typescript
// line 39 — TODAY:
export type FinalStatus = 'ok' | 'partial' | 'clarify';

// line 50-55 — already correct, no change:
export interface SearchContext {
  query: string;
  summary: string | null;
  sources: SearchContextSource[];
  fetched_at: string;
}

// line 58-73 — already correct, no change:
export interface FinalPayload {
  markdown: string;
  message_id: string;
  surcharge_result: SurchargeResult | null;
  capped: boolean;
  status: FinalStatus;
  search_context?: SearchContext | null;  // already optional+nullable per D-10
}
```

From backend/agent/nodes/response_node.py (current state):
```python
# Lines 307-312 — happy-path final_payload literal:
final_payload = {
    "markdown": markdown,
    "surcharge_result": surcharge_result,
    "capped": capped,
    "status": status,
}

# Lines 232-241 — deny-path final_payload literal:
return {
    "final_payload": {
        "markdown": markdown,
        "surcharge_result": None,
        "capped": False,
        "status": "partial",
    },
    "reasoning_trace": [deny_trace],
    "messages": prior_messages,
}
```

From frontend/components/chat/MessageList.tsx (current state, lines 54-62):
```typescript
switch (payload.status) {
  case 'clarify':
    return <ClarifyCard payload={payload} />;
  case 'partial':
    return <PartialCard payload={payload} />;
  case 'ok':
  default:
    return <MarkdownAnswer payload={payload} />;
}
```

From frontend/components/chat/MarkdownAnswer.tsx (already correct — reference only):
```typescript
// Reads payload.search_context and renders SearchContextLine above prose.
const sc = payload.search_context;
const hasMarketContext = !!(sc && (sc.summary ?? '').trim().length > 0);
// ...
{hasMarketContext && sc && <SearchContextLine context={sc} />}
```

From frontend/components/chat/SearchContextLine.tsx (already correct — reference only):
```typescript
// Returns null when summary is blank/whitespace.
// Renders "Market context: <summary>" caption + collapsible <details> with sources.
// Source links carry target="_blank" rel="noopener noreferrer".
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Forward state.search_context into final_payload on BOTH happy and deny paths in response_node, with drift-prevention pytest assertions</name>
  <files>backend/agent/nodes/response_node.py, backend/tests/test_response_node.py</files>
  <read_first>
    - backend/agent/nodes/response_node.py (full file — must understand both happy-path final_payload at lines 307-312 AND deny-path final_payload at lines 232-241; both need the same field added per D-07 and per RESEARCH note "Both happy path (response_node.py:307-312) and deny path (:232-241) need search_context for symmetry")
    - backend/tests/test_response_node.py (full file — already 365 lines; existing search_context tests at lines 121-179 cover the markdown blockquote prefix; this task ADDS final_payload-shape assertions, does not duplicate existing prefix tests)
    - .planning/phases/08-search-context-sidebar-polish/08-CONTEXT.md (decisions D-07, D-08, D-13)
  </read_first>
  <behavior>
    - Test 1 (test_response_forwards_search_context_in_final_payload_when_present): Build _ok_state(), set state["search_context"] = {"query": "q", "summary": "s", "sources": [], "fetched_at": "z"}, call response_node(state), assert out["final_payload"]["search_context"] == state["search_context"] (the same dict-equal value flows through unchanged on the happy path).
    - Test 2 (test_response_search_context_is_none_in_final_payload_when_absent): Build _ok_state(), call state.pop("search_context", None) to ensure the key is absent from state, call response_node(state), assert "search_context" in out["final_payload"] (KEY present per D-07) AND out["final_payload"]["search_context"] is None (VALUE is None — guards against `state.get(..., {})` style regressions per Pitfall 5).
    - Test 3 (test_response_deny_path_forwards_search_context_in_final_payload): Build _ok_state(), set state["approval_decision"] = "deny", set state["search_context"] = {"query": "q", "summary": "S", "sources": [], "fetched_at": "z"}, call response_node(state), assert out["final_payload"]["search_context"] == state["search_context"] (deny branch symmetry per D-07 + RESEARCH).
  </behavior>
  <action>
    1. RED — write the 3 tests in backend/tests/test_response_node.py at the end of the file (after `test_response_renders_news_prose_even_when_loop_budget_exhausted` at line 364). Verbatim function bodies:

```python
# ---------------------------------------------------------------------------
# Phase 8 D-07 / D-13: search_context always present in final_payload
# (audit Issue 6 backend half — closes drift class where FE could not tell
# `undefined` from `null`).
# ---------------------------------------------------------------------------


def test_response_forwards_search_context_in_final_payload_when_present():
    """D-07: state.search_context flows verbatim into final_payload['search_context']."""
    state = _ok_state()
    state["search_context"] = {
        "query": "q",
        "summary": "s",
        "sources": [],
        "fetched_at": "z",
    }
    out = response_node(state)
    assert out["final_payload"]["search_context"] == state["search_context"]


def test_response_search_context_is_none_in_final_payload_when_absent():
    """D-07: KEY is always present (Pitfall 5 — guards against `state.get(..., {})`
    style regressions); VALUE is None when state lacks the field."""
    state = _ok_state()
    state.pop("search_context", None)
    out = response_node(state)
    assert "search_context" in out["final_payload"]
    assert out["final_payload"]["search_context"] is None


def test_response_deny_path_forwards_search_context_in_final_payload():
    """D-07 symmetry: the deny-path final_payload also forwards search_context
    so provenance survives decline (Plan 05-05 D-11 contract)."""
    state = _ok_state()
    state["approval_decision"] = "deny"
    state["search_context"] = {
        "query": "q",
        "summary": "Diesel held steady.",
        "sources": [],
        "fetched_at": "z",
    }
    out = response_node(state)
    assert out["final_payload"]["search_context"] == state["search_context"]
```

    Run `pytest backend/tests/test_response_node.py::test_response_forwards_search_context_in_final_payload_when_present backend/tests/test_response_node.py::test_response_search_context_is_none_in_final_payload_when_absent backend/tests/test_response_node.py::test_response_deny_path_forwards_search_context_in_final_payload -x`. All 3 must FAIL with KeyError or assertion failure on `final_payload["search_context"]`. Commit: `test(08-01): add search_context final_payload drift-prevention tests`.

    2. GREEN — modify backend/agent/nodes/response_node.py in TWO places:

       (a) Happy-path final_payload literal at lines 307-312 — add the new key:
```python
final_payload = {
    "markdown": markdown,
    "surcharge_result": surcharge_result,
    "capped": capped,
    "status": status,
    "search_context": state.get("search_context"),  # Phase 8 D-07 — always present, None when state lacks it
}
```

       (b) Deny-path final_payload literal at lines 232-241 — add the same key:
```python
return {
    "final_payload": {
        "markdown": markdown,
        "surcharge_result": None,  # D-07: no breakdown on deny
        "capped": False,
        "status": "partial",
        "search_context": state.get("search_context"),  # Phase 8 D-07 — preserve provenance on deny
    },
    "reasoning_trace": [deny_trace],
    "messages": prior_messages,
}
```

    Use `state.get("search_context")` (NOT `state.get("search_context") or None` — the `or` would swallow legitimate empty-dict values, defeating the test in Pitfall 5).

    Run `pytest backend/tests/test_response_node.py -x` (full file). All 3 new tests + 14 existing tests = 17 total must PASS. Commit: `feat(08-01): forward state.search_context into final_payload on happy + deny paths`.

    3. Verify no other Pydantic validators reject the new key. Run `pytest backend/tests/ -x -q`. The full backend suite (186+ tests, per STATE.md baseline) must remain green.

    Constraints:
    - Do NOT change the deny-path search_context value to None unconditionally — that would break test_response_deny_path_forwards_search_context_in_final_payload.
    - Do NOT add normalization/empty-summary gating in response_node — D-08 explicitly delegates that gate to SearchContextLine.tsx.
    - Do NOT touch backend/agent/state.py — state.search_context shape is unchanged from Plan 05-04.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && python -m pytest backend/tests/test_response_node.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - File backend/agent/nodes/response_node.py at the happy-path final_payload literal (formerly lines 307-312) contains the literal string `"search_context": state.get("search_context")` inside a 5-key dict
    - File backend/agent/nodes/response_node.py at the deny-path final_payload literal (formerly lines 232-241) contains the literal string `"search_context": state.get("search_context")` inside a 5-key dict
    - File backend/tests/test_response_node.py contains a function named `test_response_forwards_search_context_in_final_payload_when_present`
    - File backend/tests/test_response_node.py contains a function named `test_response_search_context_is_none_in_final_payload_when_absent`
    - File backend/tests/test_response_node.py contains a function named `test_response_deny_path_forwards_search_context_in_final_payload`
    - Command `pytest backend/tests/test_response_node.py -x -q` exits with status 0 and reports all tests passed
    - Command `pytest backend/tests/ -x -q` exits with status 0 (full backend suite green)
    - grep `state\.get("search_context")` backend/agent/nodes/response_node.py returns at least 2 matches (happy + deny)
  </acceptance_criteria>
  <done>
    Both BE final_payload literals carry search_context; 3 new pytest assertions in test_response_node.py guard against future regression; full backend test suite is green.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extend FinalStatus union with 'search_only' and add explicit MessageList switch case dispatching to MarkdownAnswer, with Vitest drift-prevention test</name>
  <files>frontend/types/agent.types.ts, frontend/components/chat/MessageList.tsx, frontend/__tests__/components/MessageList.search_only.test.tsx</files>
  <read_first>
    - frontend/types/agent.types.ts (full file — line 39 declares FinalStatus union; line 72 declares search_context optional+nullable; line 7-15 lists AgentName for context only — already correct from Phase 6)
    - frontend/components/chat/MessageList.tsx (full file — switch at lines 54-62 inside renderAssistant; props at lines 23-32; FeedbackButtons gate at line 98)
    - frontend/components/chat/MarkdownAnswer.tsx (full file — already conditionally renders SearchContextLine when sc.summary is non-blank; reference only, no change)
    - frontend/components/chat/SearchContextLine.tsx (full file — renders "Market context:" caption + Sources details; reference only, no change)
    - frontend/__tests__/components/SearchContextLine.test.tsx (full file — pattern reference for the new test; uses render + screen + queryByText/getByText — same idioms)
    - frontend/__tests__/fixtures/sse.ts (full file — HAPPY_PAYLOAD as a reference for FinalPayload shape with message_id field)
    - .planning/phases/08-search-context-sidebar-polish/08-CONTEXT.md (decisions D-09, D-10, D-11, D-12, D-15)
  </read_first>
  <behavior>
    - The new test mounts MessageList with one assistant ChatMessage whose payload has status='search_only', surcharge_result=null, search_context with summary "Diesel up 3% on supply concerns" + 1 source titled "Reuters: Thailand diesel rises", and asserts:
      (a) `screen.getByText('Market context:')` is in the document (proves SearchContextLine rendered via MarkdownAnswer's hasMarketContext branch)
      (b) `screen.getByText('Sources: 1')` is in the document (proves the collapsible details toggle is rendered)
      (c) `screen.getByRole('link', { name: /Reuters/ })` has `target="_blank"` and `rel="noopener noreferrer"` (proves source link safety attributes survive)
      (d) `screen.queryByRole('table')` is null (proves NO surcharge breakdown table is rendered — surcharge_result is null on search-only flow)
    - The test must FAIL on the union extension OR the case branch being missing (TypeScript compile error if union missing; runtime fallthrough to default+MarkdownAnswer happens to pass (a),(b),(c),(d) accidentally TODAY because the default branch already routes to MarkdownAnswer — therefore the test does NOT catch a missing case branch on its own. The TypeScript union extension MUST land first; the test catches future deletion of the rendering wire).
    - Note: drift-prevention scope is the rendering wire (MarkdownAnswer reachable via search_only → SearchContextLine + sources visible + no table). The TypeScript compiler is the chokepoint for the dispatch case (Pitfall 4 — exhaustiveness will not warn but the explicit case is a documentation contract).
  </behavior>
  <action>
    1. RED — create the new test file `frontend/__tests__/components/MessageList.search_only.test.tsx`. Verbatim contents:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageList, type ChatMessage } from '@/components/chat/MessageList';

/**
 * Phase 8 D-15 — drift-prevention test for the 'search_only' rendering wire.
 *
 * Catches future regression that loses the MessageList → MarkdownAnswer →
 * SearchContextLine path for status='search_only' payloads. The audit's
 * lesson is that every layer passed its own unit tests but the dispatch
 * boundary was the actual break (Issue 6).
 */
describe("MessageList — status='search_only' (Phase 8 D-15)", () => {
  it('renders SearchContextLine, sources details, and omits surcharge table', () => {
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        id: 'thread-news-0',
        payload: {
          markdown:
            "> **Market context:** Diesel up 3% on supply concerns\n\nHere's the latest market context.\n\n*Reasoning trace available below.*",
          surcharge_result: null,
          capped: false,
          status: 'search_only',
          message_id: 'thread-news-0',
          search_context: {
            query: 'diesel news',
            summary: 'Diesel up 3% on supply concerns',
            sources: [
              {
                title: 'Reuters: Thailand diesel rises',
                url: 'https://reuters.example/x',
                snippet: '...',
                published_at: '2026-05-04',
              },
            ],
            fetched_at: '2026-05-04T10:00:00Z',
          },
        },
      },
    ];
    render(<MessageList messages={messages} threadId="thread-news" />);

    // (a) SearchContextLine's typed "Market context:" caption is in the document.
    expect(screen.getByText('Market context:')).toBeInTheDocument();
    // (b) The collapsible Sources <details> toggle renders.
    expect(screen.getByText('Sources: 1')).toBeInTheDocument();
    // (c) Source link has the safety attributes.
    const link = screen.getByRole('link', { name: /Reuters/ });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    // (d) No surcharge breakdown table renders (surcharge_result=null on search-only).
    expect(screen.queryByRole('table')).toBeNull();
  });
});
```

    Run `cd frontend && npm test -- --run __tests__/components/MessageList.search_only.test.tsx`. The test must FAIL with a TypeScript compile error: `Type '"search_only"' is not assignable to type 'FinalStatus'` (because FinalStatus union doesn't yet include 'search_only'). Commit: `test(08-01): add MessageList search_only rendering drift-prevention test`.

    2. GREEN step (a) — modify `frontend/types/agent.types.ts` line 39. Replace:
```typescript
export type FinalStatus = 'ok' | 'partial' | 'clarify';
```
    With:
```typescript
export type FinalStatus = 'ok' | 'partial' | 'clarify' | 'search_only';
```

    3. GREEN step (b) — modify `frontend/components/chat/MessageList.tsx` switch at lines 54-62 inside `renderAssistant`. Replace:
```typescript
  switch (payload.status) {
    case 'clarify':
      return <ClarifyCard payload={payload} />;
    case 'partial':
      return <PartialCard payload={payload} />;
    case 'ok':
    default:
      return <MarkdownAnswer payload={payload} />;
  }
```
    With:
```typescript
  switch (payload.status) {
    case 'clarify':
      return <ClarifyCard payload={payload} />;
    case 'partial':
      return <PartialCard payload={payload} />;
    case 'search_only':
      // Phase 8 D-11: explicit dispatch to MarkdownAnswer, which renders
      // SearchContextLine above the prose when payload.search_context.summary
      // is present. Explicit case > default fallthrough so a future status
      // (e.g. 'partial_news') gets a named extension point.
      return <MarkdownAnswer payload={payload} />;
    case 'ok':
    default:
      return <MarkdownAnswer payload={payload} />;
  }
```

    Run `cd frontend && npm test -- --run __tests__/components/MessageList.search_only.test.tsx`. Test must PASS. Commit: `feat(08-01): add 'search_only' to FinalStatus union and dispatch in MessageList`.

    4. Run `cd frontend && npx tsc --noEmit` — must report 0 errors (Pitfall 6 — type-system chokepoint).

    5. Run the full FE test suite to confirm no regression: `cd frontend && npm test -- --run`. All tests green.

    Constraints:
    - Do NOT change `FinalPayload.search_context` from `SearchContext | null` — D-10 keeps it optional+nullable.
    - Do NOT modify MarkdownAnswer or SearchContextLine — both are already correct (verified at lines 24-33 and 14-16 respectively).
    - Do NOT remove the `default:` branch — keep it as a safety net for any future status value the BE might emit before the FE is updated.
    - Do NOT add the TypeScript exhaustiveness `const _check: never = status;` pattern (Discretion item — explicitly skipped per CONTEXT D-11).
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npm test -- --run __tests__/components/MessageList.search_only.test.tsx && npx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - File frontend/types/agent.types.ts contains the literal string `'search_only'` on the FinalStatus union line
    - grep `export type FinalStatus` frontend/types/agent.types.ts returns a line containing all four values: 'ok', 'partial', 'clarify', 'search_only'
    - File frontend/components/chat/MessageList.tsx contains the literal string `case 'search_only':`
    - File frontend/components/chat/MessageList.tsx case 'search_only' branch returns `<MarkdownAnswer payload={payload} />`
    - File frontend/__tests__/components/MessageList.search_only.test.tsx exists and contains the literal string `status: 'search_only'`
    - File frontend/__tests__/components/MessageList.search_only.test.tsx contains the literal string `screen.queryByRole('table')`
    - Command `cd frontend && npm test -- --run __tests__/components/MessageList.search_only.test.tsx` exits with status 0
    - Command `cd frontend && npx tsc --noEmit` exits with status 0 (no TS errors)
    - Command `cd frontend && npm test -- --run` exits with status 0 (full FE suite green)
  </acceptance_criteria>
  <done>
    FinalStatus union has 4 values; MessageList dispatches 'search_only' to MarkdownAnswer explicitly; new Vitest test confirms SearchContextLine renders + sources details + no surcharge table on search-only payloads; full FE suite + tsc are green.
  </done>
</task>

</tasks>

<verification>
- BE: `pytest backend/tests/test_response_node.py -x -q` — 17/17 (existing 14 + new 3) tests pass
- BE: `pytest backend/tests/ -x -q` — full backend suite stays at 186+ green (no regression)
- FE: `cd frontend && npm test -- --run __tests__/components/MessageList.search_only.test.tsx` — new test green
- FE: `cd frontend && npx tsc --noEmit` — 0 errors
- FE: `cd frontend && npm test -- --run` — full FE suite green
- grep verification: `state\.get("search_context")` appears at least 2× in response_node.py (happy + deny)
- grep verification: `case 'search_only':` appears in MessageList.tsx
- grep verification: `'search_only'` appears in agent.types.ts FinalStatus union line
</verification>

<success_criteria>
1. ROADMAP §Phase 8 Success Criterion 1 (BE half): `response_node` emits `search_context` in `final_payload` — VERIFIED via test_response_forwards_search_context_in_final_payload_when_present
2. ROADMAP §Phase 8 Success Criterion 2: `agent.types.ts` `FinalStatus` union includes `'search_only'` AND `MessageList` switch handles it — VERIFIED via grep + new test
3. Audit Issue 6 backend half closed: `final_payload['search_context']` always present (None or value)
4. Audit Issue 6 frontend type+dispatch half closed: `'search_only'` is a declared status value AND has an explicit dispatch case
5. Drift-prevention layer: 3 new BE tests + 1 new FE test guard against future regression
6. Manual smoke (deferred to verify-phase): live news query renders SearchContextLine with clickable sources in the chat answer
</success_criteria>

<output>
After completion, create `.planning/phases/08-search-context-sidebar-polish/08-01-SUMMARY.md` documenting:
- Both response_node final_payload literal sites (line numbers post-edit) carrying `state.get("search_context")`
- The 3 new BE drift-prevention tests by exact name
- The FinalStatus union now has 4 values and MessageList has the explicit case
- Test counts: BE +3, FE +1; full suites green
- Any deviations or surprises (per Phase 7 / Phase 6 SUMMARY pattern — record at the per-task granularity)
</output>
