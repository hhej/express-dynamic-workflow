---
quick_id: 260514-uwo
type: quick
mode: quick
phase: quick
plan: 260514-uwo
subsystem: frontend/chat
branch: docs/quick-260514-uwo-chat-ui-pragmatic-fix
tags:
  - frontend
  - ui-fix
  - band-aid
  - w5-code-freeze
  - w6-demo-prep
  - debug-backlog
dependency-graph:
  requires:
    - "frontend/components/chat/ChatColumn.tsx (existing tab-body flex layout)"
    - "frontend/components/chat/MessageList.tsx (Debug 999.5 comment block from prior quick task 260509-e0p)"
    - ".planning/debug/ convention (frontmatter + Current Focus/Symptoms/Eliminated/Evidence sections)"
  provides:
    - "Input-row layout fix: chat input stays docked at viewport bottom on long chats (min-h-0)"
    - "Demo-console silence: React duplicate-key warning suppressed for W6 demo via assistant <li> key band-aid"
    - "Debug backlog artifact 999.12: deferred BE root-cause hunt for duplicate `message_id` stamping"
  affects:
    - "frontend/components/chat/ChatColumn.tsx"
    - "frontend/components/chat/MessageList.tsx"
    - ".planning/debug/ (new open item — not in resolved/)"
tech-stack:
  added: []
  patterns:
    - "Tailwind min-h-0 on flex column parents to let overflow-y-auto children actually shrink"
    - "Dated comment-block layering: preserve prior context verbatim, append new dated rationale"
    - "Deferred debug artifact convention: open item lives at top of .planning/debug/, gating conditions in 'Why Deferred'"
key-files:
  created:
    - .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md
  modified:
    - frontend/components/chat/ChatColumn.tsx
    - frontend/components/chat/MessageList.tsx
decisions:
  - "Ship FE band-aid (revert assistant key to `a-${m.id}-${i}`) instead of chasing BE root cause during W5 code freeze"
  - "Preserve Debug 999.5 (2026-05-09) comment block byte-for-byte and APPEND the 2026-05-14 deferral note — do not rewrite history"
  - "Apply min-h-0 to both chat AND dashboard tab bodies for symmetry, even though only the chat tab manifests the bug today"
  - "Place 999.12 artifact at the top of .planning/debug/ (NOT resolved/) — it is open and gates on four explicit conditions"
metrics:
  duration: "2m 6s"
  completed: "2026-05-14T15:22:03Z"
  tasks_completed: 3
  files_modified: 2
  files_created: 1
  commits: 3
---

# Quick Task 260514-uwo: Fix chat input flex overflow + band-aid duplicate React key Summary

Two pragmatic FE fixes ahead of the W6 demo (input-row stays in viewport via `min-h-0`; duplicate React key silenced via assistant `<li>` key revert) plus a debug-lead backlog artifact at `.planning/debug/999.12-...md` capturing the deferred BE root-cause hunt.

## Commits

| Order | Hash      | Subject                                                                                                                            |
| ----- | --------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| 1     | `e2fb71d` | `fix(quick-260514-uwo): add min-h-0 to ChatColumn tab bodies so input row stays in viewport on long chats`                         |
| 2     | `c9f2bcb` | `fix(quick-260514-uwo): band-aid duplicate assistant React key for W6 demo (BE _next_turn_idx hunt deferred — see 999.12 backlog)` |
| 3     | `01be8f6` | `docs(quick-260514-uwo): log duplicate message_id BE regression as 999.12 debug-lead backlog item (deferred post-W6-demo)`         |

All three commits land on `docs/quick-260514-uwo-chat-ui-pragmatic-fix` (branched from `develop`). No tag bumps, no ROADMAP changes, no BE touches.

## What Changed

### Task 1 — `min-h-0` on ChatColumn tab bodies (commit `e2fb71d`)

`frontend/components/chat/ChatColumn.tsx`:

- Line 81: `'flex-1 flex-col'` → `'flex-1 flex-col min-h-0'` (chat tab body)
- Line 115: `'flex-1 flex-col'` → `'flex-1 flex-col min-h-0'` (dashboard tab body)

**Why it works:** the `<ol>` inside `MessageList` already has `overflow-y-auto`, but a flex child cannot shrink below its intrinsic content size without `min-h-0` (browser default `min-height: auto`). Without `min-h-0` on the flex column parent, the `<ol>` grew to fit ALL messages, pushing the input row past the viewport bottom on long chats. With `min-h-0`, the `<ol>` shrinks to fill the available space and scrolls internally.

Dashboard tab gets the same treatment for symmetry — no current bug there, but a future dashboard-internal scroll would repeat the pattern otherwise.

**Verification:**

```
$ npx tsc --noEmit -p tsconfig.json
(no output — clean)

$ grep -n "min-h-0" frontend/components/chat/ChatColumn.tsx
81:          'flex-1 flex-col min-h-0',
115:          'flex-1 flex-col min-h-0',
```

### Task 2 — Band-aid assistant `<li>` key (commit `c9f2bcb`)

`frontend/components/chat/MessageList.tsx`:

- Key on assistant `<li>`: `a-${m.id}` → `a-${m.id}-${i}` (line 120)
- Debug 999.5 (2026-05-09) comment block (lines 100-111) preserved **verbatim**
- New "Band-aided 2026-05-14" comment block appended (lines 112-119), separated by a single `//` blank-comment line, referencing the 999.12 backlog item by filename and committing to suffix removal post-demo

**Why band-aid not real fix:** the 11-turn full-demo run on 2026-05-14 surfaced a BE-side duplicate `message_id` regression. Real fix would require modifying `backend/api/routes/conversations.py::_attach_message_ids` and/or `_next_turn_idx`, which is out-of-scope during W5 code freeze. Reverting to the index-suffixed key silences the React warning in the demo console without changing rendered behaviour. Root-cause hunt is parked in 999.12 (see Task 3).

**Verification:**

```
$ npm test -- --run
Test Files  30 passed (30)
     Tests  145 passed (145)
  Duration  6.34s

$ grep -n "a-\${m\.id}-\${i}" frontend/components/chat/MessageList.tsx
100:            // Debug 999.5 (2026-05-09): key reverted from `a-${m.id}-${i}`
120:            key={`a-${m.id}-${i}`}

$ grep -n "Band-aided 2026-05-14" frontend/components/chat/MessageList.tsx
113:            // Band-aided 2026-05-14 for W6 demo. Duplicate `message_id`

$ grep -n "Debug 999.5 (2026-05-09)" frontend/components/chat/MessageList.tsx
100:            // Debug 999.5 (2026-05-09): key reverted from `a-${m.id}-${i}`
```

No FE tests broke — zero snapshot/key-fixture updates were required, which is the cleanest possible outcome for a band-aid revert. All 30 test files / 145 tests pass.

### Task 3 — 999.12 debug-lead backlog artifact (commit `01be8f6`)

New file: `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`

YAML frontmatter:

- `status: deferred`
- `deferred_until: post-W6-demo`
- `created` / `updated`: `2026-05-14T00:00:00Z`
- `related_quick_tasks`: `260514-uwo` (this FE band-aid), `260509-e0p` (prior FE band-aid for resume-flow duplicate)
- `related_resolved`: links to `.planning/debug/resolved/999.5-fix-resume-flow-appending-duplicate-assistant-message.md`

Sections:

- **Current Focus** — two competing hypotheses:
  - **A.** `_next_turn_idx` mis-counts refused HITL turns
  - **B.** `_attach_message_ids` double-stamps on replay / resume
- **Symptoms** — expected vs actual, exact React warning text, 4-step reproduction via 11-turn demo flow, started timestamp + why v1.1 verification battery missed it (it doesn't exercise HITL refusal+retry)
- **Eliminated** / **Evidence** — empty stubs (deferred)
- **Why Deferred** — four explicit gating conditions for removing the FE band-aid

**Verification:**

```
$ test -f .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md && echo FOUND
FOUND

$ grep -E "^status: deferred$" 999.12-...md
status: deferred

$ grep -E "_next_turn_idx" 999.12-...md  (matched in two hypothesis paragraphs)
$ grep -E "_attach_message_ids" 999.12-...md  (matched in hypothesis B + test plan)

$ grep -E "deferred_until: post-W6-demo" 999.12-...md
deferred_until: post-W6-demo
```

## Deviations from Plan

None — plan executed exactly as written. Three atomic commits, no scope creep, no fixture updates required, no auto-fixes triggered.

## Test Outcomes

| Check                                                    | Result | Detail                                                                  |
| -------------------------------------------------------- | ------ | ----------------------------------------------------------------------- |
| `npx tsc --noEmit -p tsconfig.json` (post-Task 1)        | PASS   | No output (clean)                                                       |
| `npm test -- --run` (post-Task 2)                        | PASS   | 30 test files / 145 tests; 6.34s duration                               |
| `npx tsc --noEmit -p tsconfig.json` (overall, post-Task 3) | PASS   | No output (clean)                                                       |
| `git diff --name-only develop..HEAD`                     | PASS   | Exactly the 3 expected files; no scope leak                             |
| Three atomic commits on branch                           | PASS   | `e2fb71d` → `c9f2bcb` → `01be8f6`, all on `docs/quick-260514-uwo-...` |

Backend test suite was NOT run because no BE files were touched (per plan scope — `git diff --name-only develop..HEAD` confirms zero BE files in the diff). The plan's optional `pytest backend/tests/` smoke check is moot.

## Visual Verification (Deferred to User)

Frontend hot-reloaded on save — no server restart was attempted by the executor. The user-facing handoff message:

> Frontend hot-reloaded on save. Visit http://localhost:3000, hold a long enough chat to push the scrollable region past the viewport, and confirm the input row stays docked at the bottom (the flex-overflow fix). Then run the 11-turn demo flow and confirm the React duplicate-key warning is silenced in the browser console (the band-aid). If either is still broken, do NOT merge — report back.

## Next Step

Pick up `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md` via `/gsd:debug` **AFTER** the W6 demo recording is locked. Do NOT touch before then. The four gating conditions for removing the `-${i}` band-aid are documented in the artifact's "Why Deferred" section.

## Self-Check: PASSED

- `frontend/components/chat/ChatColumn.tsx` — FOUND (modified, `min-h-0` at lines 81 + 115)
- `frontend/components/chat/MessageList.tsx` — FOUND (modified, key + comment block updated at lines 100-120)
- `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md` — FOUND (90 lines, frontmatter + 5 sections)
- Commit `e2fb71d` — FOUND in `git log --oneline`
- Commit `c9f2bcb` — FOUND in `git log --oneline`
- Commit `01be8f6` — FOUND in `git log --oneline`
- Frontend test suite green (30/30 files, 145/145 tests)
- TypeScript clean (no `--noEmit` errors)
- Scope clean (`git diff --name-only develop..HEAD` returns exactly the three intended files)
