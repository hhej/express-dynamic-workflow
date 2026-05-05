---
status: resolved
trigger: "08-dangling-trace-footer-search-only — dangling 'Reasoning trace available below.' footer with empty space below on status='search_only' (Tavily news) payloads"
created: 2026-05-05T15:30:00Z
updated: 2026-05-05T16:10:00Z
---

## Current Focus

hypothesis: CONFIRMED. backend/agent/nodes/response_node.py line 280-287 (search_only branch) explicitly appends `_FOOTER = "*Reasoning trace available below.*"` to the markdown body. FE MarkdownAnswer.tsx strips ONLY the cap-callout blockquote and the Market context blockquote — it does NOT strip the footer line. The TracePanel that renders the trace lives in a DIFFERENT COLUMN (right column of three-column app shell, mounted in ChatApp.tsx), not "below" the markdown. So the footer text is literal-rendered in the chat bubble with nothing under it.
test: read response_node.py search_only branch (lines 280-287); read MarkdownAnswer.tsx strip regexes; confirm ChatApp mounts TracePanel as a sibling column not a child of MessageList
expecting: confirm the footer is emitted unconditionally on search_only, FE has no strip pass for the footer, TracePanel is in a sibling column
next_action: apply fix — drop the _FOOTER append from the search_only branch in response_node.py (minimum-change). Update the existing FE drift-prevention test fixture to drop the footer line and existing BE tests if any assert presence of the footer on search_only.

## Symptoms

expected: |
  On status='search_only' payloads, the answer renders SearchContextLine + Sources WITHOUT a dangling
  "Reasoning trace available below." footer (or, if the footer is shown, an actual trace component must
  render below it). The footer text should not appear with empty space beneath.

actual: |
  SearchContextLine ("Market context:" caption) + collapsible Sources details render correctly (Test 1
  main path PASSED). However, after the answer body, the literal text "Reasoning trace available below."
  appears with NOTHING beneath it — no trace panel, no expander, just empty space. User reported
  verbatim: "it's show Market Context + Sources, but we got additional sentence Reasoning trace
  available below. with nothing below"

errors: |
  None. No console errors, no backend errors. Pure rendering/content issue.

reproduction: |
  1. Backend running on :8000 (already running in background)
  2. Frontend running on :3000 (already running in background)
  3. Open http://localhost:3000
  4. Send a news-style query like "What's the latest fuel news?" or "Any diesel price trends today?"
  5. Wait for the assistant answer to render
  6. Observe: Market context caption + Sources details visible, then dangling "Reasoning trace available
     below." text with no trace below

started: |
  Discovered 2026-05-05 during /gsd:verify-work 8, immediately after Phase 8
  (search-context-sidebar-polish) completed. Phase 8 added the explicit MessageList `case 'search_only':`
  branch that routes to MarkdownAnswer. Prior to Phase 8 the branch was reached via the default fallback.

## Eliminated

<!-- empty -->

## Evidence

- timestamp: 2026-05-05T15:32:00Z
  checked: grep "Reasoning trace available below" across repo
  found: |
    Literal lives at backend/agent/nodes/response_node.py:43 as `_FOOTER = "*Reasoning trace available below.*"`.
    Used in 4 emission sites in response_node.py:
      - line 201 — deny path (`markdown = ... + f"\n\n{_FOOTER}"`)
      - line 131 — _render_prose_ok (every ok path)
      - line 286 — search_only branch: `markdown = ("Here's the latest market context.\n\n" f"{_FOOTER}")`
      - (none on clarify or partial)
    No FE strip regex matches this literal — FE only strips CAP_LINE_RE and MARKET_CONTEXT_LINE_RE.
  implication: BE always emits the footer pointer line on search_only payloads; FE does not strip it; the TracePanel that the footer references lives in a sibling column, not as a child rendered below the markdown.

- timestamp: 2026-05-05T15:33:00Z
  checked: backend/agent/nodes/response_node.py line 280-287 (search_only branch)
  found: |
    elif status == "search_only":
        markdown = (
            "Here's the latest market context.\n\n"
            f"{_FOOTER}"
        )
  implication: Footer is unconditionally appended on the search_only path. Compared to the OK path where the user sees prose + 4-row breakdown table + footer (visually anchored above a real table), the search_only path renders prose + footer with nothing above to anchor the "below" reference. SearchContextLine + Sources are above the markdown (in MarkdownAnswer's JSX), so the footer is the LAST element with nothing under it.

- timestamp: 2026-05-05T15:33:30Z
  checked: frontend/components/chat/MarkdownAnswer.tsx
  found: |
    Two strip regexes only:
      - CAP_LINE_RE = /^>\s*⚠\s*Cap\/floor applied\s*—\s*review recommended\s*\n\n?/
      - MARKET_CONTEXT_LINE_RE = /^>\s*\*\*Market context:\*\*[^\n]*\n\n?/
    No regex strips the *Reasoning trace available below.* footer. Markdown is rendered verbatim through ReactMarkdown.
  implication: FE does not silence the footer. Anything BE emits in markdown is rendered in the chat bubble.

- timestamp: 2026-05-05T15:33:45Z
  checked: frontend/components/ChatApp.tsx and ChatColumn.tsx
  found: |
    ChatApp mounts <TracePanel /> at line 209 as a SEPARATE column (right column of three-column shell). MessageList is inside ChatColumn (center column). The trace component is NOT a child of MessageList nor MarkdownAnswer.
  implication: The footer copy "Reasoning trace available below." is misleading on every path (the trace lives in a sibling column, not "below" the markdown). It only "feels" wrong on search_only because there is no visual anchor (no breakdown table) above the footer line — on OK the user reads through a table and then a "see full trace" pointer; on search_only the user reads two short sentences with the second pointing at nothing visible in their column.

- timestamp: 2026-05-05T15:34:00Z
  checked: frontend/__tests__/components/MessageList.search_only.test.tsx fixture
  found: |
    Test fixture at line 22 includes the footer literal in the markdown:
      "> **Market context:** Diesel up 3% on supply concerns\n\nHere's the latest market context.\n\n*Reasoning trace available below.*"
    No assertion forbids the footer presence — fixture mirrors current BE output.
  implication: Removing the BE emission requires updating this fixture to match (drop trailing footer line) so the test continues to mirror current BE output.

## Resolution

root_cause: |
  backend/agent/nodes/response_node.py — the search_only branch (lines 280-287
  pre-fix) unconditionally appended `_FOOTER = "*Reasoning trace available
  below.*"` to the markdown body. On every other status the footer is
  visually anchored above by either a 4-row breakdown table (ok / partial
  with surcharge_result) or longer prose (clarify / deny). On search_only
  the prose is one short sentence ("Here's the latest market context."),
  so the footer stands alone with nothing under it in the chat bubble.
  The TracePanel that the footer points at lives in a SIBLING column
  (right column of the three-column app shell), not as a child rendered
  below the markdown — so the "below" reference was misleading on this
  path. SearchContextLine + Sources details (rendered ABOVE the markdown
  by MarkdownAnswer) already surface the trace-relevant content inline
  on search_only, so the pointer is redundant on this branch.

fix: |
  Drop the `_FOOTER` append from the search_only branch in
  response_node.py. Markdown becomes a single sentence:
  `"Here's the latest market context."`. Existing OK / deny paths keep
  the footer because they are visually anchored by a table / longer
  prose, and the trace pointer is genuinely useful when there's more
  reasoning detail the user might want to inspect. FE drift-prevention
  fixture in MessageList.search_only.test.tsx updated to mirror the
  new wire (no behavioural assertion change — fixture-only tightening).

verification: |
  - BE: pytest backend/tests/test_response_node.py -x → 17/17 green
    (the two search_only tests `test_response_renders_news_prose_for_search_only_flow`
    and `test_response_renders_news_prose_even_when_loop_budget_exhausted`
    assert presence of "Here's the latest market context" and absence of
    clarify prose — neither asserts footer presence/absence — both still pass).
  - BE: pytest backend/tests/ → 194/194 green.
  - FE: vitest run __tests__/components/MessageList.search_only.test.tsx → 1/1 green.
  - FE: vitest run (full suite) → 122/122 across 28 files green.
  - grep "Reasoning trace available below" in frontend/ → 0 matches; in backend/
    → 1 match (the surviving _FOOTER constant in response_node.py used by ok/deny
    paths). Confirms the footer is only emitted on paths where it's appropriate.
  - Awaiting live human verification: send a news query in the already-open
    browser, confirm the chat bubble shows SearchContextLine + Sources +
    "Here's the latest market context." with NO dangling trace-pointer line.

files_changed:
  - backend/agent/nodes/response_node.py
  - frontend/__tests__/components/MessageList.search_only.test.tsx

## Resolution Confirmed

- **Live verify date:** 2026-05-05
- **Verified by:** user, live browser session
- **Outcome:** User confirmed chat bubble on a news-style query shows SearchContextLine + Sources + "Here's the latest market context." with no dangling trace-pointer line. Fix confirmed end-to-end.
- **Commit:** 470a04b
