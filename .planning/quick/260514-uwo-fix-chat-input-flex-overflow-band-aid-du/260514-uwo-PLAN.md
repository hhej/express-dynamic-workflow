---
quick_id: 260514-uwo
type: quick
mode: quick
wave: 1
depends_on: []
files_modified:
  - frontend/components/chat/ChatColumn.tsx
  - frontend/components/chat/MessageList.tsx
  - .planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md
autonomous: true
branch: docs/quick-260514-uwo-chat-ui-pragmatic-fix
requirements: []
must_haves:
  truths:
    - "Chat input row stays inside the viewport on long chats (no off-screen overflow)"
    - "React no longer emits the duplicate-key warning `a-{thread_id}-1` during the 9-turn demo run"
    - "Existing frontend MessageList tests stay green after the assistant-key revert"
    - "BE-side duplicate `message_id` regression is captured as an actionable backlog item for post-demo investigation"
  artifacts:
    - path: "frontend/components/chat/ChatColumn.tsx"
      provides: "min-h-0 added to chat-tab and dashboard-tab flex containers — child <ol> can shrink so the input row sits at the bottom instead of being pushed off-screen"
      contains: "min-h-0"
    - path: "frontend/components/chat/MessageList.tsx"
      provides: "Assistant <li> key band-aided back to `a-${m.id}-${i}` with dated comment block preserving the Debug 999.5 history AND adding the new 2026-05-14 deferral note"
      contains: "Band-aided 2026-05-14"
    - path: ".planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md"
      provides: "Backlog/debug-lead artifact documenting the symptom, two hypotheses, repro path, and why investigation is deferred until post-W6 demo"
      contains: "_next_turn_idx"
  key_links:
    - from: "frontend/components/chat/ChatColumn.tsx"
      to: "frontend/components/chat/MessageList.tsx"
      via: "flex parent — min-h-0 on the parent lets the <ol> child (overflow-y-auto) actually scroll instead of bloating the column"
      pattern: "min-h-0"
    - from: "frontend/components/chat/MessageList.tsx"
      to: ".planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md"
      via: "comment in MessageList.tsx points readers at the debug artifact for the deferred BE root-cause hunt"
      pattern: "999.12"
---

<objective>
Two pragmatic frontend fixes ahead of the W6 demo, plus one backlog artifact for the BE regression we're choosing NOT to chase before recording.

1. **Real fix:** Chat input is being pushed off-screen on long chats because the tab-body flex containers in `ChatColumn.tsx` lack `min-h-0`. Adding `min-h-0` lets the scrollable `<ol>` child actually shrink, keeping the input row docked at the bottom of the viewport.
2. **Band-aid:** React is warning about a duplicate `a-${m.id}` key during the 11-turn demo run — the BE-stamped `message_id` is colliding (likely a `_next_turn_idx` or `_attach_message_ids` bug). To unblock the demo, revert the assistant `<li>` key to the index-suffixed form (`a-${m.id}-${i}`). The existing Debug 999.5 comment block is preserved verbatim AND extended with a dated note that names this as a deliberate band-aid, points at the backlog item, and commits us to removing the suffix once the BE side is verified clean post-demo.
3. **Backlog:** A debug-lead artifact in `.planning/debug/` captures the symptom, two competing hypotheses, the 9-turn demo repro path, and the reason this is deferred — so the post-demo investigation has a starting point.

Purpose: De-risk the W6 demo recording without taking on BE work during the W5 code freeze, while leaving an explicit paper trail so the band-aid does not silently outlive the demo.

Output:
- `frontend/components/chat/ChatColumn.tsx` — `min-h-0` added to both tab-body containers
- `frontend/components/chat/MessageList.tsx` — assistant key reverted with extended comment block
- `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md` — new backlog artifact
</objective>

<execution_context>
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/workflows/execute-plan.md
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@frontend/components/chat/ChatColumn.tsx
@frontend/components/chat/MessageList.tsx
@frontend/components/ChatApp.tsx

<!--
  KEY CONSTRAINTS — re-read before each task:
  - W5 code freeze. NO new features. NO BE changes. NO new tests.
  - Branch: docs/quick-260514-uwo-chat-ui-pragmatic-fix (already checked out).
  - All commits land on this branch. Do NOT bump the v1.1.0 tag. Do NOT touch ROADMAP.md.
  - Existing test suites must stay green:
    - `cd backend && pytest backend/tests/` (no BE changes, so this is a sanity check at most)
    - `cd frontend && npm test` — pay attention to `frontend/__tests__/components/MessageList.test.tsx` and
      `frontend/__tests__/components/MessageList.search_only.test.tsx`; if either keys off the assistant key shape
      (snapshot or `getByRole`-with-key-derived-name), it may need to be updated to match the new band-aided key.
      If a test breaks ONLY because of the key suffix being restored, it is expected to be updated — the band-aid
      itself is the point of this task.
  - Visual verification of the input-row layout fix is deferred to the user (frontend hot-reloads on save at
    http://localhost:3000). Executor MUST NOT spin up or restart any dev server. A quick `curl -s -o /dev/null -w '%{http_code}'
    http://localhost:3000` to confirm the dev server is reachable is fine if one is already running, but is not required.
-->

<interfaces>
<!--
  Relevant existing patterns the executor must respect — extracted from the touched files.
  No new types or interfaces are created by this plan.
-->

From frontend/components/chat/ChatColumn.tsx (lines 79-83 + 113-117 — the two flex containers being modified):

```tsx
// Chat tab body — line ~79
<div
  className={clsx(
    'flex-1 flex-col',
    tab === 'chat' ? 'flex' : 'hidden',
  )}
>
  <MessageList .../>
  <div className="flex flex-col gap-2 border-t border-white/10 p-4"> {/* input row */}
    <HubPicker .../>
    <ChatInput .../>
  </div>
</div>

// Dashboard tab body — line ~113
<div
  className={clsx(
    'flex-1 flex-col',
    tab === 'dashboard' ? 'flex' : 'hidden',
  )}
>
  <DashboardView />
</div>
```

The `<ol>` inside MessageList already carries `overflow-y-auto`. Tailwind's `flex-1` does not imply `min-h-0`,
so the child `<ol>` cannot shrink below its content size — pushing the input row past the viewport.
Adding `min-h-0` to BOTH tab-body containers is the load-bearing fix (chat tab is the one with the visible
bug; dashboard tab gets it for symmetry so a future dashboard-internal scroll doesn't repeat the pattern).

From frontend/components/chat/MessageList.tsx (lines 98-119 — the assistant <li>):

```tsx
return (
  <li
    // Debug 999.5 (2026-05-09): key reverted from `a-${m.id}-${i}`
    // back to `a-${m.id}`. The `-${i}` suffix was a defensive band-aid
    // ... (load-bearing 11-line comment block — see file for full text)
    // through, we WANT React to warn so we can chase the root cause.
    key={`a-${m.id}`}
    className="max-w-[85%] space-y-2 self-start glass-surface px-4 py-2 text-sm text-text-primary"
  >
```

The existing 11-line comment block (lines 100-111) is LOAD-BEARING and MUST be preserved verbatim. The new
2026-05-14 note is APPENDED to it, not replacing it. The key value itself changes from `a-${m.id}` back to
`a-${m.id}-${i}`.
</interfaces>

<related_artifacts>
<!-- Debug-artifact convention (sampled from .planning/debug/resolved/): -->
<!--   - Filename: {phase-or-issue-number}-{kebab-description}.md -->
<!--   - YAML frontmatter: status, trigger, created, updated (ISO 8601 UTC) -->
<!--   - Sections: Current Focus / Symptoms / Eliminated / Evidence (Evidence/Eliminated can be empty stubs). -->
<!-- The new file lives at the top of .planning/debug/ (NOT in resolved/) because the investigation is open/deferred. -->

@.planning/debug/resolved/999.5-fix-resume-flow-appending-duplicate-assistant-message.md
</related_artifacts>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix chat input flex overflow by adding min-h-0 to ChatColumn tab bodies</name>
  <files>frontend/components/chat/ChatColumn.tsx</files>
  <action>
Edit `frontend/components/chat/ChatColumn.tsx`. Add the Tailwind utility `min-h-0` to the two tab-body `<div>` containers' className lists.

**Change 1 — chat tab body (line 79-83 region):**

Before:
```tsx
<div
  className={clsx(
    'flex-1 flex-col',
    tab === 'chat' ? 'flex' : 'hidden',
  )}
>
```

After:
```tsx
<div
  className={clsx(
    'flex-1 flex-col min-h-0',
    tab === 'chat' ? 'flex' : 'hidden',
  )}
>
```

**Change 2 — dashboard tab body (line 113-117 region) — symmetry only, no current bug:**

Before:
```tsx
<div
  className={clsx(
    'flex-1 flex-col',
    tab === 'dashboard' ? 'flex' : 'hidden',
  )}
>
```

After:
```tsx
<div
  className={clsx(
    'flex-1 flex-col min-h-0',
    tab === 'dashboard' ? 'flex' : 'hidden',
  )}
>
```

**Why this fixes it:** the `<ol>` inside `MessageList` already has `overflow-y-auto`, but a flex child cannot
shrink below its intrinsic content size without `min-h-0` (browser default `min-height: auto`). Without
`min-h-0` on the flex column parent, the `<ol>` grows to fit ALL messages, pushing the input row past the
viewport bottom on long chats. With `min-h-0`, the `<ol>` shrinks to fill the available space and scrolls
internally — exactly the layout we already advertise via `overflow-y-auto`.

Do NOT touch any other class, prop, or component in this file. Do NOT add a comment in the source — the
PR / commit message carries the rationale (this is a Tailwind one-token fix). Do NOT modify `MessageList.tsx`
or the inner input-row `<div>` — they are correct already.

After saving, the dev server (if running) hot-reloads automatically. Do NOT restart it.

Commit (atomic):

```
fix(quick-260514-uwo): add min-h-0 to ChatColumn tab bodies so input row stays in viewport on long chats
```
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow/frontend &amp;&amp; npx tsc --noEmit -p tsconfig.json 2&gt;&amp;1 | tail -20 &amp;&amp; grep -n "min-h-0" /Users/pollot/Desktop/express-dynamic-workflow/frontend/components/chat/ChatColumn.tsx</automated>
  </verify>
  <done>
- `frontend/components/chat/ChatColumn.tsx` has `min-h-0` in both tab-body div classNames (chat AND dashboard).
- `npx tsc --noEmit` passes with no new errors.
- `grep -n "min-h-0" frontend/components/chat/ChatColumn.tsx` returns 2 hits.
- Atomic commit created on `docs/quick-260514-uwo-chat-ui-pragmatic-fix`.
- Visual confirmation deferred to user (frontend hot-reloads on save).
  </done>
</task>

<task type="auto">
  <name>Task 2: Band-aid the duplicate assistant React key with dated deferral comment</name>
  <files>frontend/components/chat/MessageList.tsx</files>
  <action>
Edit `frontend/components/chat/MessageList.tsx`. Revert the assistant `<li>` key from `a-${m.id}` back to
`a-${m.id}-${i}`, KEEPING the entire Debug 999.5 comment block (current lines 100-111) verbatim AND appending
a new dated note below it.

**Locate** lines 98-119 (the assistant `<li>` block). The current state is:

```tsx
return (
  <li
    // Debug 999.5 (2026-05-09): key reverted from `a-${m.id}-${i}`
    // back to `a-${m.id}`. The `-${i}` suffix was a defensive band-aid
    // shipped in quick task 260509-e0p that masked the real duplicate-
    // append bug in ChatApp.tsx. With the real fix in place
    // (handleResume guard-seed + done-effect dep narrowing), m.id —
    // which is the BE-stamped message_id `{thread_id}-{turn_idx}` for
    // canonical assistants and `replay-noncanonical-${i}` for HITL
    // pre-pause partials — is unique within `messages`. Using array
    // index in keys is a React anti-pattern: it silently masks
    // reconciliation bugs and breaks list-update animations / focus
    // retention. If a future regression ever lets a duplicate id slip
    // through, we WANT React to warn so we can chase the root cause.
    key={`a-${m.id}`}
    className="max-w-[85%] space-y-2 self-start glass-surface px-4 py-2 text-sm text-text-primary"
  >
```

**Replace** with (Debug 999.5 block preserved EXACTLY, new dated block appended, key suffix restored):

```tsx
return (
  <li
    // Debug 999.5 (2026-05-09): key reverted from `a-${m.id}-${i}`
    // back to `a-${m.id}`. The `-${i}` suffix was a defensive band-aid
    // shipped in quick task 260509-e0p that masked the real duplicate-
    // append bug in ChatApp.tsx. With the real fix in place
    // (handleResume guard-seed + done-effect dep narrowing), m.id —
    // which is the BE-stamped message_id `{thread_id}-{turn_idx}` for
    // canonical assistants and `replay-noncanonical-${i}` for HITL
    // pre-pause partials — is unique within `messages`. Using array
    // index in keys is a React anti-pattern: it silently masks
    // reconciliation bugs and breaks list-update animations / focus
    // retention. If a future regression ever lets a duplicate id slip
    // through, we WANT React to warn so we can chase the root cause.
    //
    // Band-aided 2026-05-14 for W6 demo. Duplicate `message_id`
    // regression detected during 11-turn full-demo run — root cause
    // likely in BE `_next_turn_idx` (refused-turn counting?) or
    // `_attach_message_ids` (replay double-stamp?). See
    // `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`
    // backlog item. Remove the `-${i}` suffix once BE side is verified
    // clean post-demo via /gsd:debug.
    key={`a-${m.id}-${i}`}
    className="max-w-[85%] space-y-2 self-start glass-surface px-4 py-2 text-sm text-text-primary"
  >
```

**Critical constraints:**
- The Debug 999.5 block (12 comment lines) is preserved BYTE-FOR-BYTE. Do not "tidy up" wording, line breaks,
  or punctuation.
- The new 2026-05-14 block sits BELOW the Debug 999.5 block, separated by a single `//` blank-comment line.
- The new block references the backlog filename EXACTLY as `999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`
  (this matches the file the next task creates).
- The key value changes from `a-${m.id}` to `a-${m.id}-${i}`. Nothing else on the `<li>` changes — className,
  children, and surrounding logic stay untouched.

After saving, run the frontend test suite to catch any snapshot/key-derived breakage:

```bash
cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npm test -- --run
```

Pay particular attention to:
- `frontend/__tests__/components/MessageList.test.tsx`
- `frontend/__tests__/components/MessageList.search_only.test.tsx`

If a test fails purely because it asserts a key shape (e.g., a snapshot matching `a-{id}` without the index
suffix, or a `data-testid` derived from the key), update the test fixture to match the new band-aided shape —
the band-aid is the intended end state of this task. Do NOT loosen any assertion that is checking actual
rendered content / behaviour. If the failure is ambiguous (e.g., looks like a real reconciliation regression),
STOP and flag it back to the user instead of papering over it.

Commit (atomic):

```
fix(quick-260514-uwo): band-aid duplicate assistant React key for W6 demo (BE _next_turn_idx hunt deferred — see 999.12 backlog)
```
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow/frontend &amp;&amp; npm test -- --run 2&gt;&amp;1 | tail -40 &amp;&amp; grep -n "a-\${m.id}-\${i}" /Users/pollot/Desktop/express-dynamic-workflow/frontend/components/chat/MessageList.tsx &amp;&amp; grep -n "Band-aided 2026-05-14" /Users/pollot/Desktop/express-dynamic-workflow/frontend/components/chat/MessageList.tsx &amp;&amp; grep -n "Debug 999.5 (2026-05-09)" /Users/pollot/Desktop/express-dynamic-workflow/frontend/components/chat/MessageList.tsx</automated>
  </verify>
  <done>
- Assistant `<li>` key is `a-${m.id}-${i}` (verified by grep).
- Debug 999.5 (2026-05-09) comment block preserved verbatim (verified by grep).
- New "Band-aided 2026-05-14" comment block appended (verified by grep) and references
  `999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`.
- `npm test -- --run` exits 0. Any test fixture updated for the key-shape change is committed together with
  the source change (a single atomic commit covers both).
- Atomic commit created on `docs/quick-260514-uwo-chat-ui-pragmatic-fix`.
  </done>
</task>

<task type="auto">
  <name>Task 3: Log the BE duplicate message_id regression as a backlog/debug-lead artifact</name>
  <files>.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md</files>
  <action>
Create a new debug-lead artifact at
`.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`.

The convention (sampled from `.planning/debug/resolved/999.5-*.md` and the broader `.planning/debug/` directory)
is YAML frontmatter + sections (Current Focus, Symptoms, Eliminated, Evidence). For an OPEN/DEFERRED item the
sections are stubs — they fill in once `/gsd:debug` picks the item up post-demo.

Write this exact content (substitute today's date `2026-05-14` into both frontmatter timestamps):

```markdown
---
status: deferred
trigger: "Duplicate React key warning `Encountered two children with the same key, `a-{thread_id}-1`` emitted by frontend/components/chat/MessageList.tsx during the 11-turn full-demo run on 2026-05-14. Two distinct assistant turns inside a single thread were stamped by the BE with the same `message_id` (`{thread_id}-1`). FE band-aided 2026-05-14 in quick task 260514-uwo by reverting the assistant <li> key to `a-${m.id}-${i}`; root cause on the BE side is unfixed."
created: 2026-05-14T00:00:00Z
updated: 2026-05-14T00:00:00Z
deferred_until: post-W6-demo
related_quick_tasks:
  - 260514-uwo (FE band-aid shipped here)
  - 260509-e0p (prior FE band-aid for resume-flow duplicate; Debug 999.5 removed it after the real fix)
related_resolved:
  - .planning/debug/resolved/999.5-fix-resume-flow-appending-duplicate-assistant-message.md
---

## Current Focus

hypothesis (CURRENT — two competing root causes, neither yet proven):

  A. `_next_turn_idx` mis-counts refused turns.
     If a HITL-refused turn increments (or fails to increment) the turn counter inconsistently with the
     committed-message turn counter, two real assistant turns can end up sharing the same `turn_idx` and
     therefore the same composed `message_id = `{thread_id}-{turn_idx}``. Refused/denied approval flows are
     the most likely site because they branch through a different graph path than the happy path.

  B. `_attach_message_ids` double-stamps on replay / resume.
     `backend/api/routes/conversations.py::_attach_message_ids` is responsible for stamping `message_id` onto
     the LAST assistant of each turn when a conversation is loaded for resume. If the loader runs over an
     already-stamped history (e.g., a checkpoint that was persisted post-stamp), or if the "last assistant of
     each turn" boundary disagrees with `_next_turn_idx`'s boundary, two rows can receive the same id.

test: After the W6 demo recording is in the can, run the 9-turn demo script from
      `.planning/milestones/v1.1-*` (the canonical demo path documented in the final v1.1 docs) against a
      fresh uvicorn process, capture the BE-side log of every `message_id` assigned in
      `backend/api/routes/chat.py::_drain_events` AND every `_attach_message_ids` call in
      `backend/api/routes/conversations.py`. Cross-reference against the FE-side React warning trail
      (currently masked by the `-${i}` suffix; either temporarily un-band-aid in a scratch branch OR diff
      `messages[].id` directly).

expecting: One of A or B reproduces deterministically. If neither does, the regression is replay-dependent
           (only fires when checkpointer state from a specific v1.1 build hits a newer code path) and we
           need to narrow further.

next_action: Pick up via `/gsd:debug` post-W6-demo. Do NOT investigate during W5 code freeze.

## Symptoms

expected: Each assistant turn within a single thread receives a unique BE-stamped `message_id` of the form
          `{thread_id}-{turn_idx}` where `turn_idx` monotonically increases. The FE's React reconciliation
          key `a-${m.id}` is therefore unique within `messages`.

actual: During an 11-turn full-demo run on 2026-05-14, two distinct assistant turns were stamped with
        `{thread_id}-1` (turn_idx=1 used twice). React emitted the `Encountered two children with the same
        key` warning. No visible UI break (the second `<li>` just inherits the reconciliation behaviour of
        the first), but list-update animations / focus retention are at risk and the warning pollutes the
        demo console.

errors: `Warning: Encountered two children with the same key, `a-{thread_id}-1`.` (origin:
        frontend/components/chat/MessageList.tsx, line ~112 pre-band-aid).

reproduction:
1. Start a fresh uvicorn + Next dev server pair.
2. Run the 9-turn demo script from the v1.1 final docs (the canonical demo path).
3. Continue past turn 9 into the extended HITL flow (refusal + retry) to reach 11 turns total.
4. Observe React duplicate-key warning around turn 11 in the browser console.

started: First observed during the 2026-05-14 pre-demo dry-run. Did NOT appear in the v1.1 verification
         (3 fresh uvicorn × 5-run PASS_UNDER_30S battery) because that battery exercises a shorter,
         non-HITL path.

## Eliminated

(none yet — investigation deferred)

## Evidence

(none yet — investigation deferred)

## Why Deferred

- W5 code freeze: BE changes are out-of-scope until after the W6 demo recording.
- FE band-aid in quick task 260514-uwo (assistant `<li>` key reverted to `a-${m.id}-${i}`) prevents the
  duplicate-key warning from polluting the demo console without changing any rendered behaviour.
- The duplicate `message_id` itself is purely cosmetic in the current demo path — `FeedbackButtons` use
  `payload.message_id` for the POST body but the two affected rows happen to render the same payload anyway,
  so feedback submission is not silently misdirected. (Confirm this in evidence post-demo before removing
  the band-aid.)
- Removing the band-aid is gated on:
  1. Proving root cause (A or B above) via `/gsd:debug`.
  2. Shipping the BE fix on a feature branch off `develop`.
  3. Verifying with the same 11-turn demo path that no duplicate is produced.
  4. Confirming no FE test relies on the band-aided key shape (re-run `npm test`).
```

Do NOT change any existing file in `.planning/debug/`. Do NOT add this file to `.planning/debug/resolved/` —
it is open / deferred, not resolved.

Commit (atomic):

```
docs(quick-260514-uwo): log duplicate message_id BE regression as 999.12 debug-lead backlog item (deferred post-W6-demo)
```
  </action>
  <verify>
    <automated>test -f /Users/pollot/Desktop/express-dynamic-workflow/.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md &amp;&amp; grep -E "^status: deferred$" /Users/pollot/Desktop/express-dynamic-workflow/.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md &amp;&amp; grep -E "_next_turn_idx" /Users/pollot/Desktop/express-dynamic-workflow/.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md &amp;&amp; grep -E "_attach_message_ids" /Users/pollot/Desktop/express-dynamic-workflow/.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md &amp;&amp; grep -E "deferred_until: post-W6-demo" /Users/pollot/Desktop/express-dynamic-workflow/.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md</automated>
  </verify>
  <done>
- File exists at `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`
  (NOT in `resolved/`).
- Frontmatter carries `status: deferred`, `deferred_until: post-W6-demo`, `created` and `updated` at
  `2026-05-14T00:00:00Z`, and lists `260514-uwo` plus `260509-e0p` under `related_quick_tasks`.
- Both hypothesis names appear: `_next_turn_idx` AND `_attach_message_ids`.
- "Symptoms" section names the React warning verbatim and references the 9-turn demo script as the repro
  path.
- "Why Deferred" lists the four gating conditions for removing the band-aid.
- Atomic commit created on `docs/quick-260514-uwo-chat-ui-pragmatic-fix`.
  </done>
</task>

</tasks>

<verification>

After all three tasks land on `docs/quick-260514-uwo-chat-ui-pragmatic-fix`:

1. **Three atomic commits**, in order, on the branch:

   ```bash
   git -C /Users/pollot/Desktop/express-dynamic-workflow log --oneline -3 docs/quick-260514-uwo-chat-ui-pragmatic-fix
   ```

   Expect three lines, newest first:
   - `docs(quick-260514-uwo): log duplicate message_id BE regression as 999.12 debug-lead backlog item (deferred post-W6-demo)`
   - `fix(quick-260514-uwo): band-aid duplicate assistant React key for W6 demo (BE _next_turn_idx hunt deferred — see 999.12 backlog)`
   - `fix(quick-260514-uwo): add min-h-0 to ChatColumn tab bodies so input row stays in viewport on long chats`

2. **Existing test suites green:**

   ```bash
   cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npm test -- --run
   ```

   Exit 0. Any MessageList test that was updated for the key shape change rides in Task 2's commit.

   Backend sanity (no BE files touched, so this is a smoke check):

   ```bash
   cd /Users/pollot/Desktop/express-dynamic-workflow && pytest backend/tests/ -q --no-header 2>&1 | tail -10
   ```

   Should pass — no BE files changed.

3. **TypeScript clean:**

   ```bash
   cd /Users/pollot/Desktop/express-dynamic-workflow/frontend && npx tsc --noEmit -p tsconfig.json
   ```

   No new errors introduced.

4. **No unintended files touched:**

   ```bash
   git -C /Users/pollot/Desktop/express-dynamic-workflow diff --name-only develop..HEAD
   ```

   Output MUST be exactly (order may vary):
   - `frontend/components/chat/ChatColumn.tsx`
   - `frontend/components/chat/MessageList.tsx`
   - `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`
   - (optionally) `frontend/__tests__/components/MessageList.test.tsx` OR
     `frontend/__tests__/components/MessageList.search_only.test.tsx` IF Task 2 had to update a snapshot/key
     fixture. Anything else is a scope violation — investigate before merging.

5. **Visual verification deferred to user.** Tell the user explicitly:
   > Frontend hot-reloaded on save. Visit http://localhost:3000, hold a long enough chat to push the
   > scrollable region past the viewport, and confirm the input row stays docked at the bottom (the
   > flex-overflow fix). Then run the 11-turn demo flow and confirm the React duplicate-key warning is
   > silenced in the browser console (the band-aid). If either is still broken, do NOT merge —
   > report back.

</verification>

<success_criteria>

- [ ] `frontend/components/chat/ChatColumn.tsx` has `min-h-0` in both tab-body div classNames.
- [ ] `frontend/components/chat/MessageList.tsx` assistant `<li>` key is `a-${m.id}-${i}`.
- [ ] The Debug 999.5 (2026-05-09) 12-line comment block is preserved verbatim in MessageList.tsx.
- [ ] A new "Band-aided 2026-05-14" comment block follows it, referencing
      `999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`.
- [ ] `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md` exists with
      `status: deferred`, both hypotheses named, the 9-turn demo repro path, and the "Why Deferred" section.
- [ ] Three atomic commits on `docs/quick-260514-uwo-chat-ui-pragmatic-fix` with the message format above.
- [ ] `npm test -- --run` passes; `pytest backend/tests/` passes; `npx tsc --noEmit` clean.
- [ ] `git diff --name-only develop..HEAD` contains ONLY the three files listed above (plus optionally one
      MessageList test fixture file).
- [ ] No changes to `ROADMAP.md`. No tag bumps. No BE changes. No new tests.

</success_criteria>

<output>
After completion, create
`.planning/quick/260514-uwo-fix-chat-input-flex-overflow-band-aid-du/260514-uwo-SUMMARY.md`
documenting:
- The three commits (hashes + subjects).
- The grep / test outputs from each task's `<verify>` block.
- The exact wording of the message you give the user about visual verification (per
  `verification` step 5 above).
- An explicit pointer: "Next step — pick up
  `.planning/debug/999.12-investigate-duplicate-message-id-regression-in-be-stamping.md`
  via `/gsd:debug` AFTER the W6 demo recording is locked. Do NOT touch before then."
</output>
