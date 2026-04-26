---
phase: 04-frontend-reasoning-trace
plan: 04
subsystem: ui
tags: [react, react-19, recharts, dashboard, charts, vitest, msw, typescript, hooks, error-boundary]

requires:
  - phase: 04-frontend-reasoning-trace
    provides: Plan 04-02 — useFuelPrices(days), useConversations() (items/loading/error), api.getConversation(threadId), RANGE_OPTIONS, DEFAULT_RANGE_DAYS, SURCHARGE_HISTORY_LIMIT, ConversationSummary, ConversationDetail, SurchargeResult types
provides:
  - RangeToggle — 7d|30d|90d radiogroup with LOCKED accent on active
  - FuelPriceChart — Recharts LineChart consuming useFuelPrices(days), with state-driven re-fetch on range change
  - useSurchargeHistory(items, loading) — Walks recent threads in parallel via Promise.all, returns chart-ready SurchargeHistoryPoint[]
  - SurchargeHistoryChart — Recharts BarChart derived client-side from useConversations + useSurchargeHistory
  - DashboardView — Composes both charts inside a local ChartErrorBoundary so chart render failures cannot blank the dashboard
  - SurchargeHistoryPoint type exported from useSurchargeHistory
affects: [04-05-app-shell]

tech-stack:
  added: []
  patterns:
    - "ResponsiveContainer cloneElement shim — vi.mock('recharts') replaces ResponsiveContainer with a wrapper that clones its single child with width/height props, bypassing jsdom's missing ResizeObserver. Required because Recharts 3 measures via observer in production but jsdom returns 0px."
    - "isAnimationActive={false} on every Recharts series (<Line>, <Bar>) — Pitfall 4 mitigation, prevents animation flicker on every state-driven re-fetch (range toggle, thread refresh)"
    - "Promise.all over per-thread getConversation calls — Pitfall 8 mitigation; per-thread .catch(() => null) keeps a single 500 from poisoning the whole chart"
    - "Inline ChartErrorBoundary class component co-located inside frontend/components/dashboard/DashboardView.tsx — respects Wave 3 parallel-write boundary (frontend/components/shared/ is owned by 04-03 sibling). Integrator (04-05) can swap to the canonical shared/ErrorBoundary post-merge."
    - "Tooltip formatter typed against Recharts 3 ValueType union — Recharts 3 made the formatter signature stricter than the documented examples; coercion via `typeof value === 'number' ? value : Number(value)` keeps behaviour identical and tsc clean"

key-files:
  created:
    - frontend/components/dashboard/RangeToggle.tsx
    - frontend/components/dashboard/FuelPriceChart.tsx
    - frontend/components/dashboard/SurchargeHistoryChart.tsx
    - frontend/components/dashboard/DashboardView.tsx
    - frontend/hooks/useSurchargeHistory.ts
    - frontend/__tests__/components/RangeToggle.test.tsx
    - frontend/__tests__/components/FuelPriceChart.test.tsx
    - frontend/__tests__/components/SurchargeHistoryChart.test.tsx
    - frontend/__tests__/hooks/useSurchargeHistory.test.tsx
  modified: []

key-decisions:
  - Inlined ChartErrorBoundary in DashboardView.tsx instead of importing @/components/shared/ErrorBoundary — Wave 3 parallel-execution boundary forbids touching frontend/components/shared/ which is owned by 04-03; integrator 04-05 may swap once both Wave 3 plans merge
  - Inlined animate-pulse div for chart loading skeletons instead of importing @/components/shared/LoadingSkeleton — same parallel-write reason as ErrorBoundary
  - vi.mock('recharts') with ResponsiveContainer cloneElement shim is test-only — production code uses real ResponsiveContainer with width=100% height=300; the mock fixes jsdom's missing ResizeObserver so the SVG-path smoke test (Pitfall 3 verification) actually exercises the chart path
  - Tooltip formatter coerces value via `typeof === 'number'` check rather than asserting/casting — Recharts 3's ValueType is a union including string and undefined, and the coercion-with-fallback preserves the chart's runtime behaviour while satisfying strict tsc

patterns-established:
  - "Component-scoped Wave-3 fallback pattern: when a parallel sibling owns the canonical component path, inline a minimal local fallback inside your owned directory; the integrator swaps to the canonical import after merge. Documented by inline comments referencing the sibling plan."
  - "Recharts × jsdom test pattern: vi.mock('recharts', async () => { ... ResponsiveContainer: cloneElement shim ... }) — forces SVG rendering in tests where ResizeObserver is missing. Re-use this pattern for any chart smoke test in this codebase."

requirements-completed: [UI-04]

duration: 5min
completed: 2026-04-26
---

# Phase 04 Plan 04: Dashboard Charts (UI-04) Summary

**Recharts dashboard with 7d/30d/90d fuel-price line chart and client-derived surcharge-history bar chart — both wrapped in a local ChartErrorBoundary, both with Pitfall 4 (animation flicker) and Pitfall 8 (N+1 fetches) explicitly mitigated.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-26T04:51:21Z
- **Completed:** 2026-04-26T04:57:04Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 9 (9 created + 0 modified)

## Accomplishments

- `RangeToggle` is a `role="radiogroup"` segmented control with the LOCKED accent (`bg-blue-600 text-white`) on the active option. No-op on already-active click — `onChange` only fires when selection actually changes.
- `FuelPriceChart` renders a Recharts `<LineChart>` with `stroke="#2563eb"` (the LOCKED accent reserved for chart use), `isAnimationActive={false}` (Pitfall 4), and the LOCKED title `Diesel price (THB/L)`. Loading / empty / error states render the LOCKED copy verbatim from UI-SPEC §Copywriting.
- `useSurchargeHistory(items, loading)` walks the most-recent `SURCHARGE_HISTORY_LIMIT` (20) threads, fetches each via `api.getConversation` inside a single `Promise.all` (Pitfall 8 — parallelism asserted by test 3 which counts concurrent in-flight requests), drops threads where `surcharge_result === null`, and silently catches per-thread fetch failures so one bad thread cannot blank the chart.
- `SurchargeHistoryChart` renders a Recharts `<BarChart>` with `fill="#2563eb"` (LOCKED accent), `isAnimationActive={false}`, and the LOCKED title `Recent surcharges`. Loading / empty / error states render the LOCKED copy verbatim. Empty state copy includes the explicit "Ask the chat for a surcharge to populate this chart" instruction so first-time users know how to seed it.
- `DashboardView` composes both charts inside a local `ChartErrorBoundary` (class component) so a Recharts render failure (e.g., the React 19 + react-is mismatch escape-hatch from Pitfall 3) does not blank the rest of the app — only that chart's section shows the alert message.
- 18 / 18 tests pass across 4 files (4 RangeToggle + 5 FuelPriceChart + 4 useSurchargeHistory + 5 SurchargeHistoryChart). `npm run type-check` and `npm run build` both exit 0.
- Wave-3 parallel-write contract preserved: zero writes outside the agent's declared scope (`frontend/components/dashboard/`, `frontend/hooks/useSurchargeHistory.ts`, the four declared test files).

## Task Commits

1. **Task 1 RED — failing tests for RangeToggle and FuelPriceChart** — `2aa2dcd` (test)
2. **Task 1 GREEN — implement RangeToggle and FuelPriceChart with Recharts × React 19 mitigations** — `bb393dd` (feat)
3. **Task 2 RED — failing tests for useSurchargeHistory and SurchargeHistoryChart** — `2ccfc69` (test)
4. **Task 2 GREEN — add useSurchargeHistory hook, SurchargeHistoryChart, and DashboardView** — `7721ec7` (feat)

## Files Created/Modified

### Created — frontend/components/dashboard/

- `frontend/components/dashboard/RangeToggle.tsx` — Segmented control. Imports `RANGE_OPTIONS` from `@/lib/constants`. Uses `clsx` for conditional accent classes. Click-handler short-circuits when the option is already active.
- `frontend/components/dashboard/FuelPriceChart.tsx` — Recharts `<LineChart>` consuming `useFuelPrices(days)`. Loading state renders an inline animate-pulse div (replaces the canonical `<LoadingSkeleton>` because that file is owned by Wave 3 sibling 04-03). Tooltip formatter coerces `ValueType` via `typeof === 'number'` to satisfy Recharts 3's stricter typed-charts signature.
- `frontend/components/dashboard/SurchargeHistoryChart.tsx` — Recharts `<BarChart>` consuming `useConversations()` and `useSurchargeHistory(items, loading)`. X-axis tilts labels at -20° with `interval={0}` so all 20 chart-data labels remain readable when many threads exist.
- `frontend/components/dashboard/DashboardView.tsx` — Composes both charts inside a local `ChartErrorBoundary` class component. Top-level layout uses the LOCKED spacing tokens (`gap-6 p-6` per UI-SPEC §Spacing).

### Created — frontend/hooks/

- `frontend/hooks/useSurchargeHistory.ts` — Hook + `SurchargeHistoryPoint` interface export. `Promise.all` over `slice(0, SURCHARGE_HISTORY_LIMIT)` getConversation calls; per-call `.catch(() => null)` so one failure does not blank others; outer-Promise.all error path is unreachable in practice (kept for defensive defence). Sorts oldest → newest before returning so the bar chart reads naturally left-to-right.

### Created — frontend/__tests__/

- `frontend/__tests__/components/RangeToggle.test.tsx` — 4 tests: renders 3 LOCKED labels; active styling; click→onChange; no-op on already-active click.
- `frontend/__tests__/components/FuelPriceChart.test.tsx` — 5 tests: LOCKED title; SVG-path smoke (Pitfall 3 react-is verification); 503 → LOCKED error copy; empty array → LOCKED empty copy; source grep for `isAnimationActive={false}` and `stroke="#2563eb"`. Mocks Recharts `ResponsiveContainer` via `cloneElement` shim.
- `frontend/__tests__/components/SurchargeHistoryChart.test.tsx` — 5 tests: LOCKED title; SVG bar smoke; LOCKED empty copy when all threads have null surcharge_result; LOCKED error copy on conversations 500; source grep for `isAnimationActive={false}` and `fill="#2563eb"`. Same `ResponsiveContainer` shim as FuelPriceChart.
- `frontend/__tests__/hooks/useSurchargeHistory.test.tsx` — 4 tests: returns chart-ready points; drops null surcharge_result; `Promise.all` parallelism asserted via concurrent-call counter (≥2 in flight); per-thread failure isolation (1 of 3 fails → 2 points, error stays null).

### Modified

None.

## Decisions Made

- **Inline `ChartErrorBoundary` in `DashboardView.tsx` instead of importing `@/components/shared/ErrorBoundary`** — Wave 3 parallel-write boundary forbids writes to `frontend/components/shared/`. The shared `ErrorBoundary` is owned by 04-03 (chat surface). The integrator (04-05) can swap to the canonical import once both Wave 3 plans merge; until then the inline class fulfils the same plan invariant ("a render failure does not blank the whole app").
- **Inline `animate-pulse` div for loading skeletons instead of importing `@/components/shared/LoadingSkeleton`** — Same parallel-write reason as `ErrorBoundary`. The visual is identical (`bg-gray-50 rounded animate-pulse`) so the integrator's swap is mechanical.
- **`vi.mock('recharts')` with `ResponsiveContainer` `cloneElement` shim** — jsdom does not implement `ResizeObserver`, which Recharts 3's `ResponsiveContainer` uses to compute width. Without this shim the inner `<LineChart>` / `<BarChart>` render at width=0 and emit no SVG paths, which would defeat Pitfall 3's whole purpose (verify React 19 × react-is via SVG-path smoke). The shim is test-only — production code uses the real `ResponsiveContainer` with `width="100%" height={300}`.
- **`useSurchargeHistory` outer-Promise.all `.catch` handler is preserved** even though per-thread `.catch(() => null)` makes the outer `.catch` unreachable in practice — kept as defensive depth so an unexpected synchronous throw inside the `.then` mapping cannot leave the hook stuck in `loading=true`. The "single failed getConversation" test verifies that the per-thread isolation is the active path (error stays null).
- **`Tooltip formatter` typed loosely against Recharts 3's `ValueType`** — Recharts 3 made the formatter signature stricter than the 2.x examples we modelled the chart on. Adding a `typeof value === 'number'` check with a `Number()` fallback preserves the chart's runtime behaviour (THB formatting on numeric values) while satisfying tsc. No alternative was simpler — using `as` casts to silence the error would have been brittle.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Wave 3 parallel-write boundary forbids `frontend/components/shared/` imports**

- **Found during:** Task 2 (DashboardView.tsx draft)
- **Issue:** The plan's `key_links` specifies `DashboardView -> frontend/components/shared/ErrorBoundary.tsx` and the original action snippet imports `@/components/shared/ErrorBoundary` plus `@/components/shared/LoadingSkeleton`. Both files are owned by Wave 3 sibling 04-03 and explicitly outside this agent's writable paths (`frontend/components/{shared,chat,trace,sidebar}/` blocked).
- **Fix:** Inlined a small `ChartErrorBoundary` class component co-located inside `DashboardView.tsx`, and inlined `animate-pulse bg-gray-50 rounded` divs in place of `<LoadingSkeleton>`. Both fallbacks share the same Tailwind classes that the canonical components are expected to use, so the integrator (04-05) can swap to the canonical imports with a one-line change after the Wave 3 merge.
- **Files modified:** frontend/components/dashboard/DashboardView.tsx, frontend/components/dashboard/FuelPriceChart.tsx, frontend/components/dashboard/SurchargeHistoryChart.tsx
- **Verification:** All 18 tests pass against the inlined fallbacks; type-check + build clean. `git diff --name-only` shows zero writes outside the agent's declared scope.
- **Committed in:** bb393dd (Task 1 GREEN), 7721ec7 (Task 2 GREEN)

**2. [Rule 1 - Bug] Recharts `ResponsiveContainer` returns 0px width under jsdom — Pitfall 3 SVG-path smoke would always pass null**

- **Found during:** Task 1 (after first GREEN attempt)
- **Issue:** `npm test` showed FuelPriceChart's "renders an SVG with at least one Line path" test fail with `expected null not to be null`. The render output included a `<div class="recharts-wrapper">` but no inner SVG. Diagnosis: Recharts 3's `ResponsiveContainer` measures via `ResizeObserver`, which jsdom does not implement; the inner chart sees width=0 and emits no SVG paths. Without this fix the entire Pitfall 3 verification (the whole point of the test) would silently pass via the "or empty/error state" fallback in test 1 instead of actually exercising the SVG render path.
- **Fix:** Added `vi.mock('recharts', ...)` to both chart test files. The mock replaces `ResponsiveContainer` with a function that calls `React.cloneElement(children, { width: 600, height: 300 })`, forcing the inner `<LineChart>` / `<BarChart>` to render at fixed dimensions. All other Recharts exports (`Line`, `Bar`, `XAxis`, `YAxis`, `Tooltip`, `CartesianGrid`, `LineChart`, `BarChart`) come from the real module, so the smoke test still verifies the actual Recharts × React 19 path.
- **Files modified:** frontend/__tests__/components/FuelPriceChart.test.tsx, frontend/__tests__/components/SurchargeHistoryChart.test.tsx
- **Verification:** Both SVG-path smoke tests now pass with `paths.length` > 0. Production code unchanged — the mock is test-scoped via `vi.mock`.
- **Committed in:** bb393dd (Task 1 GREEN — also picked up by Task 2 GREEN)

**3. [Rule 1 - Bug] Recharts 3 `Tooltip` formatter signature is stricter than Recharts 2 examples**

- **Found during:** Task 2 (post-GREEN type-check)
- **Issue:** `npm run type-check` failed with `Type '(v: number) => string' is not assignable to type 'Formatter<ValueType, NameType>'. Types of parameters 'v' and 'value' are incompatible. Type 'ValueType | undefined' is not assignable to type 'number'.` Recharts 3 typed `ValueType` as a union (`string | number | (string | number)[]`) and the formatter receives `ValueType | undefined`. Modelling the formatter on Recharts 2-era examples produced an unsound signature.
- **Fix:** Rewrote both Tooltip formatters to accept the implicit `ValueType` parameter, then coerce via `typeof value === 'number' ? value : Number(value)` with a `Number.isFinite` fallback. Runtime behaviour is identical for the numeric `total` / `price` values our charts pass; tsc is now happy.
- **Files modified:** frontend/components/dashboard/FuelPriceChart.tsx, frontend/components/dashboard/SurchargeHistoryChart.tsx
- **Verification:** `npm run type-check` exits 0; all 18 tests still pass.
- **Committed in:** 7721ec7 (Task 2 GREEN)

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 bugs)
**Impact on plan:** All three deviations preserve the plan's `must_haves.truths` exactly. The inline fallback pattern is the only deviation visible to the integrator, and it's documented in inline comments referencing the sibling plan. The other two deviations are test-environment / typing quirks that the plan's pseudocode could not have predicted without running it. End state matches the plan's declared output 1:1.

## Issues Encountered

- Node 25 `--localstorage-file` warning prints once per test worker — same benign Node-process notice carried over from 04-02. Out of scope; will revisit if it becomes noisy in CI.
- The `ResponsiveContainer` mock currently only handles a single child element (`React.cloneElement(children, ...)`). If a future component wraps multiple children inside a single `ResponsiveContainer` we will need to extend the shim, but Recharts only ever has one chart-family child per container so this is not a practical limitation.

## User Setup Required

None — Wave 3 is fully autonomous. No new env vars, no new external services. The frontend stack (Recharts 3.8.1, React 19.2.5, the `react-is` override) installed by 04-01 was sufficient.

## Next Phase Readiness

Plan 04-05 (App Shell) can now:

- Import `DashboardView` from `@/components/dashboard/DashboardView` and place it inside the Chat | Dashboard tab toggle (D-04).
- Import `FuelPriceChart` and `SurchargeHistoryChart` directly if it ever needs to render them outside `DashboardView` (e.g., for a dedicated dashboard route).
- Import `useSurchargeHistory(items, loading)` if it ever needs to derive surcharge points from a different conversations source (e.g., a search-filtered list).
- Swap the inline `ChartErrorBoundary` and `animate-pulse` divs to the canonical `@/components/shared/{ErrorBoundary,LoadingSkeleton}` once 04-03 merges. The swap is a 4-line change in DashboardView, FuelPriceChart, and SurchargeHistoryChart.

No blockers for 04-05. The Pitfall 3 (react-is), Pitfall 4 (animation flicker), and Pitfall 8 (Promise.all) mitigations are all proven by passing tests; the integrator inherits a working dashboard tab.

## Known Stubs

The inline `ChartErrorBoundary` (DashboardView.tsx) and inline `animate-pulse` skeleton divs (FuelPriceChart.tsx, SurchargeHistoryChart.tsx) are intentional Wave-3 fallbacks, not stubs that prevent the plan's goal. Both render the correct visuals; they're flagged here only so 04-05's integrator knows the imports may be swapped to `@/components/shared/...` after the Wave 3 merge for code-deduplication.

## Self-Check: PASSED

All 9 declared output files exist on disk. All 4 task commits (2aa2dcd, bb393dd, 2ccfc69, 7721ec7) are present in `git log`. `npm test` for the 4 plan-04-04 test files reports 18 / 18 passing; `npm run type-check` and `npm run build` both exit 0. Verification grep checks: `isAnimationActive={false}` present in both chart files (Pitfall 4); `#2563eb` present as `stroke=` in FuelPriceChart and `fill=` in SurchargeHistoryChart (LOCKED accent); `Central Region` returns no matches (Bangkok Metro lock preserved).

---
*Phase: 04-frontend-reasoning-trace*
*Completed: 2026-04-26*
