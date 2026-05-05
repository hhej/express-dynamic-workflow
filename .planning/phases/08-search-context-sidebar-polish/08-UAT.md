---
status: complete
phase: 08-search-context-sidebar-polish
source: [08-01-search-context-wiring-SUMMARY.md, 08-02-conversations-provider-SUMMARY.md]
started: 2026-05-05T15:00:00Z
updated: 2026-05-05T15:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Tavily news query renders SearchContextLine with sources
expected: SearchContextLine "Market context:" caption + collapsible "Sources: N" details with clickable target=_blank links + no surcharge breakdown table on a Tavily news-style query (status='search_only')
result: issue
reported: "it's show Market Context + Sources, but we got additional sentence 'Reasoning trace available below.' with nothing below"
severity: minor
note: SearchContextLine + Sources render correctly. The dangling 'Reasoning trace available below.' footer text appears with no trace component beneath it on the search_only path.

### 2. Sidebar updates immediately after completed turn (no page reload)
expected: After sending a surcharge query and the answer renders, the new conversation entry appears in the left sidebar within ~1 second of the answer (the `done` SSE event), without needing a page reload or manual refresh
result: pass

## Summary

total: 2
passed: 1
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "On status='search_only' payloads, no 'Reasoning trace available below.' footer appears unless an actual trace renders beneath it"
  status: failed
  reason: "User reported: it's show Market Context + Sources, but we got additional sentence 'Reasoning trace available below.' with nothing below"
  severity: minor
  test: 1
  artifacts: []
  missing: []
  context: "Main rendering path works (SearchContextLine + Sources visible). Dangling footer text appears with no trace component beneath it. Likely BE markdown emits the 'Reasoning trace available below.' line on search-only paths even when there's no trace to render, OR FE strips the blockquote but leaves the trace-pointer footer."
