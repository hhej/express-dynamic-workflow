---
status: partial
phase: 05-polish-observability-docs
source: [05-VERIFICATION.md]
started: 2026-05-03T18:30Z
updated: 2026-05-03T18:30Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. demo.mp4 or demo.gif recording
expected: docs/demo.mp4 or docs/demo.gif exists and shows an end-to-end agent run with parallel trace timestamps and HITL approval card
result: [pending]

### 2. 5 PNG screenshots + v1.0 annotated git tag
expected: docs/screenshots/chat-breakdown.png, trace-parallel.png, dashboard.png, hitl-approval.png, langfuse-trace.png all present; git tag v1.0 exists as an annotated tag
result: [pending]

### 3. Langfuse dashboard shows traced LLM calls and formula_accuracy + user_feedback Scores
expected: Navigating to Langfuse Cloud shows chat_turn traces with CallbackHandler spans, formula_accuracy Score (0.0 or 1.0), and user_feedback Score (-1 or 1) after a full demo run
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
