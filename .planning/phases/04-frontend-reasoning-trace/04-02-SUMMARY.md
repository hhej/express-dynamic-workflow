---
phase: 04-frontend-reasoning-trace
plan: 02
subsystem: ui
tags: [react, react-19, sse, fetch-streams, vitest, msw, hooks, typescript, abort-controller, localstorage]

requires:
  - phase: 04-frontend-reasoning-trace
    provides: Plan 04-01 — TS contracts (SSEEvent, TraceEntry, FinalPayload, ConversationSummary, FuelPricePoint), MSW handlers for all 4 backend endpoints, makeSseStream + happyTurnEvents fixtures
provides:
  - parseSseStream — generic Response → SSEEvent stream parser with chunk-boundary buffering, abort, and malformed-frame tolerance
  - api client — typed listConversations / getConversation / fuelPrices / postChat plus ApiError carrying HTTP status
  - formatters — formatTHB, formatPercent, formatRelativeTime (Intl-only, no date-fns/dayjs)
  - constants — API_BASE_URL, EXAMPLE_PROMPTS (3), RANGE_OPTIONS (7d/30d/90d), DEFAULT_RANGE_DAYS, LOCAL_STORAGE_KEYS, SURCHARGE_HISTORY_LIMIT
  - useChatStream — useReducer-backed SSE consumer (idle/streaming/done/error); aborts in-flight stream on new send (D-08 + Pitfall 7); persists thread_id to localStorage on meta event (D-20)
  - useConversations — items/loading/error + refresh + resume; resume() persists thread_id so follow-up turns continue the resumed thread
  - useFuelPrices(days) — re-fetches on days change with cancellation-safe useEffect (Pitfall 8)
  - jsdom Storage polyfill in __tests__/setup.ts mitigating Node 25 + Vitest 4 interaction
affects: [04-03-streaming-chat, 04-04-history-charts, 04-05-app-shell]

tech-stack:
  added: []
  patterns:
    - parseSseStream(response, onEvent, signal) — single-purpose generic; never throws on malformed frames; cleanly cancels reader on abort
    - api.* surface returns parsed JSON for GETs and a raw Response for POST /api/chat (so caller can pipe body to parseSseStream)
    - useChatStream tracks threadIdRef alongside state.threadId so the send() callback never carries stale closure values
    - useChatStream's "abort then dispatch START" ordering enforces D-08 single-turn invariant — earlier liveTrace cleared before newer events arrive
    - Map-backed Storage polyfill installed pre-tests instead of relying on jsdom's url-derived Storage (Node 25 ships globalThis.localStorage that vitest's jsdom populator skips because `(k in global)` is true)

key-files:
  created:
    - frontend/lib/sse.ts
    - frontend/lib/api.ts
    - frontend/lib/formatters.ts
    - frontend/lib/constants.ts
    - frontend/hooks/useChatStream.ts
    - frontend/hooks/useConversations.ts
    - frontend/hooks/useFuelPrices.ts
    - frontend/__tests__/lib/sse.test.ts
    - frontend/__tests__/lib/api.test.ts
    - frontend/__tests__/hooks/useChatStream.test.tsx
    - frontend/__tests__/hooks/useConversations.test.tsx
    - frontend/__tests__/hooks/useFuelPrices.test.tsx
  modified:
    - frontend/__tests__/setup.ts

key-decisions:
  - parseSseStream tolerates malformed JSON by logging via console.error and continuing — one bad frame cannot poison a whole turn (matches D-08 "current-turn-only liveTrace" intent: even if a frame is dropped, the rest of the turn renders)
  - useChatStream.send() uses useCallback with empty deps and reads threadId via a ref — prevents stale-closure bugs where two rapid sends would both read the pre-meta threadId
  - DONE dispatch deliberately deferred to the finally block so SSE 'error' events that precede a 'done' frame still leave status="error" rather than being clobbered by a late DONE
  - Map-backed Storage polyfill installed in setup.ts instead of patching vitest config — Node 25 + Vitest 4 + jsdom 29 conspiracy means jsdom-provided localStorage never reaches global; polyfill is a single, transparent fix that stays out of production code paths
  - D-08 abort assertion reformulated to inspect liveTrace contents (must be exactly the 5 second-turn events) instead of asserting on the upstream stream's cancel() callback — MSW does not propagate fetch consumer's reader.cancel() to its source, but the user-visible invariant is exactly what we test

patterns-established:
  - "snake_case-on-the-wire preserved: thread_id stays thread_id in api.ts query strings, postChat body, useChatStream META dispatches; LOCAL_STORAGE_KEYS.threadId is camelCase only because it's a JS object key — its VALUE is still the snake_case string 'thread_id'"
  - "Hook pattern: 'use client' first non-comment line; localStorage reads in useEffect (Pitfall 6 — never during render); side-effect cleanup via cancelled flag (useFuelPrices) or AbortController (useChatStream)"
  - "TDD discipline: RED commit (test only), GREEN commit (impl + test pass) — git log shows 4 commits across 2 tasks (test→feat × 2)"

requirements-completed: [UI-01, UI-06]

duration: 8min
completed: 2026-04-26
---

# Phase 04 Plan 02: Streaming Chat Data Layer Summary

**Generic SSE parser, typed api client + ApiError, three React hooks (useChatStream / useConversations / useFuelPrices) that hide fetch + AbortController + localStorage from UI components — UI-01 and UI-06 data-layer satisfied**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-26T04:38:29Z
- **Completed:** 2026-04-26T04:46:10Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 13 (12 created + 1 modified)

## Accomplishments

- `parseSseStream(response, onEvent, signal?)` correctly handles three subtle cases the UI plans would otherwise re-implement: chunk-boundary frame buffering (Pitfall 7), abort signal mid-stream, and malformed JSON tolerance (logs and continues)
- Typed `api` client with `ApiError(status, message)` so callers can branch on retryability without duck-typing fetch responses; `postChat` deliberately returns the raw Response so consumers can pipe the body into parseSseStream
- `useChatStream` exposes a tagged-union ChatStatus state machine (`idle | streaming | done | error`) and enforces the D-08 single-turn invariant by aborting any in-flight stream before starting a new one — the second send's META wins, the first turn's trace events never leak into liveTrace
- `useConversations.resume()` writes thread_id to localStorage so the next chat turn (a new useChatStream send) continues the resumed thread automatically — no extra wiring required in components
- 21 tests pass across 6 files (4 sse + 5 api + 5 useChatStream + 3 useConversations + 3 useFuelPrices + 1 pre-existing placeholder); type-check + Next build both clean
- Diagnosed and fixed a Node 25 / Vitest 4 / jsdom 29 interaction that left `window.localStorage` as an empty `{}` lacking storage methods — installed a Map-backed Storage polyfill in `__tests__/setup.ts`

## Task Commits

1. **Task 1 RED: failing tests for SSE parser and API client** — `9506357` (test)
2. **Task 1 GREEN: implement SSE parser, api client, formatters, constants** — `ae57664` (feat)
3. **Task 2 RED: failing tests for useChatStream, useConversations, useFuelPrices** — `c447d45` (test)
4. **Task 2 GREEN: implement three hooks + Storage polyfill fix** — `6fdeb09` (feat)

## Files Created/Modified

### Created — frontend/lib/

- `frontend/lib/sse.ts` — `parseSseStream(response, onEvent, signal?)`. Buffers across `\n\n` boundaries, calls `reader.cancel()` when signal aborts, logs `console.error` and skips on malformed JSON.
- `frontend/lib/api.ts` — `api.{listConversations, getConversation, fuelPrices, postChat}` + `ApiError extends Error` carrying HTTP status. GETs return parsed JSON; postChat returns raw Response.
- `frontend/lib/formatters.ts` — `formatTHB`, `formatPercent`, `formatRelativeTime` using `Intl.RelativeTimeFormat`. No date-fns/dayjs dependency.
- `frontend/lib/constants.ts` — `API_BASE_URL` (env-derived), `EXAMPLE_PROMPTS` (3 D-09 demo seeds), `RANGE_OPTIONS` (7d/30d/90d), `DEFAULT_RANGE_DAYS=30`, `LOCAL_STORAGE_KEYS={threadId:'thread_id', feedback:'feedback'}`, `SURCHARGE_HISTORY_LIMIT=20`.

### Created — frontend/hooks/

- `frontend/hooks/useChatStream.ts` — `'use client'`. useReducer with 7 action types (START / META / TRACE / ANSWER / ERROR / DONE / RESET). Owns AbortController via ref so a new send() aborts the previous one. Reads stored thread_id post-mount in useEffect (Pitfall 6). Persists thread_id from META event into localStorage. DONE dispatch lives in finally so an early ERROR event isn't clobbered by a trailing DONE.
- `frontend/hooks/useConversations.ts` — `'use client'`. items/loading/error + refresh + resume. resume() returns ConversationDetail and writes thread_id to localStorage so the very next useChatStream.send() continues the thread (D-14 → D-20 chain).
- `frontend/hooks/useFuelPrices.ts` — `'use client'`. Cancellation-safe useEffect (closure-scoped `cancelled` flag) keyed on `[days]`. Surfaces ApiError unchanged when a 503 fires.

### Created — frontend/__tests__/

- `frontend/__tests__/lib/sse.test.ts` — 4 tests: happy path order, split chunk, malformed JSON tolerance, abort signal stops further onEvent calls.
- `frontend/__tests__/lib/api.test.ts` — 5 tests: list mock, detail mock with surcharge_result, fuelPrices URL inspection, postChat returns Response, 503 raises ApiError with status.
- `frontend/__tests__/hooks/useChatStream.test.tsx` — 5 tests: happy stream order, localStorage persistence, reset clears state + storage, SSE error event surfaces error+status, second send aborts first (assertion reformulated — see Decisions Made).
- `frontend/__tests__/hooks/useConversations.test.tsx` — 3 tests: load on mount, refresh re-fetches, resume persists + returns detail.
- `frontend/__tests__/hooks/useFuelPrices.test.tsx` — 3 tests: load via MSW, days re-fetch, 503 → error.

### Modified

- `frontend/__tests__/setup.ts` — Installed Map-backed Storage polyfill before MSW server lifecycle hooks. Replaces both `globalThis.localStorage` and `window.localStorage` with a Storage-shaped object backed by `Map<string,string>`.

## Decisions Made

- **DONE in finally, not in 'done' case** — If we dispatched DONE on the SSE 'done' event directly, an 'error' event followed by 'done' (the documented happy-error sequence per backend D-18) would clobber `status="error"` back to `done`. Instead, error sets a `sawError` flag, and finally only dispatches DONE if `!sawError && !signal.aborted`. This matches Plan 04-01's HAPPY/CAPPED/CLARIFY fixtures' answer→done ordering AND the error→done ordering tested in Test 4.
- **threadIdRef alongside state.threadId** — useCallback with empty deps means send() captures threadId only at mount. A user who sends two messages back-to-back (without intervening renders the React batching could ignore) would otherwise both submit with the pre-meta threadId. The ref is updated synchronously in the META case and via useEffect on state.threadId change.
- **Storage polyfill in setup.ts** — Three options were on the table: (a) NODE_OPTIONS=--no-experimental-webstorage in npm test (brittle, depends on Node version), (b) vitest.config environmentOptions.jsdom.url (jsdom default URL is already `http://localhost:3000`, so this fixed nothing), (c) inline polyfill in setup.ts (transparent, version-agnostic, scoped to tests). Chose (c). The polyfill matches Web Storage spec for the methods our code actually uses (clear/getItem/setItem/removeItem); length and key(index) are also implemented for completeness.
- **D-08 abort assertion via liveTrace, not stream.cancel()** — Original test asserted `firstAborted` flag set in the upstream stream's `cancel()` callback. MSW does not propagate the fetch consumer's `reader.cancel()` back to the underlying source's cancel callback in vitest's jsdom + Undici environment, so the flag stayed false even though the abort genuinely aborted. The behaviour we actually care about is "first turn's trace events do NOT leak into liveTrace" — that's what we now assert. Same invariant, observable from the consumer side.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] window.localStorage missing methods under Node 25 + Vitest 4**

- **Found during:** Task 2 (first hooks test run after RED→GREEN)
- **Issue:** `window.localStorage.clear is not a function` in every test that touched localStorage. Diagnosis revealed three layers:
  1. Node 25.x ships an experimental `globalThis.localStorage` enabled by default. Without `--localstorage-file=...` it is an empty object `{}`.
  2. Vitest 4's jsdom env populates `global` with `dom.window` props via `populateGlobal`. But its `getWindowKeys` filter says `if (k in global) return keysArray.includes(k)` — and `localStorage` is not in the special KEYS list, so when Node's broken localStorage is already on global the jsdom one is filtered out.
  3. Consequence: `window.localStorage` resolves to the Node-shipped empty object that lacks `clear/getItem/setItem/removeItem`.
- **Fix:** Installed a minimal Map-backed Storage polyfill in `frontend/__tests__/setup.ts` that runs before any test hook. Both `globalThis.localStorage` and `window.localStorage` are reassigned via `Object.defineProperty(..., {configurable:true, writable:true})` so subsequent tests can re-clear or re-stub if needed.
- **Files modified:** frontend/__tests__/setup.ts
- **Verification:** All 11 hooks tests pass; the diagnostic test that previously printed `localStorage own prop: []` now reports a real Storage object with all 4 methods plus `length` and `key(i)`.
- **Committed in:** 6fdeb09 (Task 2 GREEN commit)

**2. [Rule 1 - Bug] D-08 abort test asserted on a non-propagating internal flag**

- **Found during:** Task 2 (after Storage polyfill landed, the abort test was the only remaining failure)
- **Issue:** Test asserted `firstAborted` set inside the upstream MSW stream's `cancel()` callback. parseSseStream calls `reader.cancel()` correctly, but in vitest's Undici/jsdom fetch path the cancellation does not propagate to MSW's source-side cancel callback. The hook IS aborting (no leaked trace events from first turn), but the flag was unobservable.
- **Fix:** Reformulated the assertion to inspect `result.current.liveTrace` and `finalPayload` — the second turn's 5 happy events must be the only entries in liveTrace, and the second turn's HAPPY_PAYLOAD must be the finalPayload. This is the actual D-08 invariant ("current-turn-only liveTrace"), observable from the consumer.
- **Files modified:** frontend/__tests__/hooks/useChatStream.test.tsx
- **Verification:** Test passes; if the `abortRef.current?.abort()` line is removed from useChatStream.send, the test fails with `liveTrace.length` showing 6 events (1 from first turn + 5 from second).
- **Committed in:** 6fdeb09 (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both deviations were caused by toolchain ergonomics (Node 25 storage shim, MSW cancel-propagation), not by anything in the hook's production logic. The end state matches the plan's `must_haves.truths` exactly — every claim in the plan's truths block is now exercised by a passing test.

## Issues Encountered

- The `--localstorage-file` warning printed by Node 25 on every test run is benign and unrelated to the polyfill (it's a Node-process-level deprecation notice). Suppressing it would require a Node CLI flag at the test runner level; out of scope for this plan, will revisit if it becomes noisy in CI.
- ESLint did not flag the `_controller` unused-binding inside the start callback of the test stream — explicitly named `start(_controller)` to make the intent (held-open stream) self-documenting. No lint rule needed.

## User Setup Required

None — Wave 2 is fully autonomous. No new env vars, no new external services. The frontend stack and test infra installed by Plan 04-01 were sufficient.

## Next Phase Readiness

Plan 04-03 (Streaming Chat UI) can now:

- Import `useChatStream` from `@/hooks/useChatStream` — components reduce to dispatching `send(message)` and rendering `liveTrace` / `finalPayload` / `status` / `error`.
- Import `useConversations` from `@/hooks/useConversations` for the history sidebar — `resume(threadId)` already wires the next chat turn correctly.
- Import `useFuelPrices(days)` from `@/hooks/useFuelPrices` for the fuel-price chart in 04-04.
- Import `formatTHB / formatPercent / formatRelativeTime` from `@/lib/formatters` for surcharge cards and timestamps.
- Reference `EXAMPLE_PROMPTS` and `RANGE_OPTIONS` from `@/lib/constants` instead of duplicating string literals.

No blockers. The hooks have no Suspense, no React Query, no external state library — they're plain React 19 primitives so 04-03's components can stay pure-render and snapshot-stable.

## Self-Check: PASSED

All 12 declared output files exist on disk and all 4 task commits (9506357, ae57664, c447d45, 6fdeb09) are present in `git log`. `npm test -- --run __tests__/lib/ __tests__/hooks/` reports 21 passing tests; `npm run type-check` and `npm run build` exit 0.

---
*Phase: 04-frontend-reasoning-trace*
*Completed: 2026-04-26*
