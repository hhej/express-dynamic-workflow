---
phase: 04-frontend-reasoning-trace
plan: 01
subsystem: ui
tags: [next.js, react, tailwind-v4, vitest, playwright, msw, typescript, sse, recharts, react-markdown]

requires:
  - phase: 03-graph-assembly-and-api
    provides: Backend API contract — ChatRequest, ConversationSummary, FuelPricePoint, 5-event SSE envelope, TraceEntry, FinalPayload, SurchargeResult
provides:
  - Buildable Next.js 15.5.x + React 19.2.x scaffold under frontend/
  - Tailwind v4 wired via @tailwindcss/postcss plugin and @import "tailwindcss"
  - overrides.react-is collapsing to single 19.2.5 (Recharts blank-chart pitfall mitigation)
  - Path aliases: @/components, @/hooks, @/lib, @/types
  - Hand-mirrored TS contracts (frontend/types/api.types.ts, agent.types.ts) preserving snake_case
  - Vitest + Testing Library + MSW + Playwright fully wired
  - SSE fixture helper makeSseStream + happy/capped/clarify/partial canonical payloads
  - MSW handlers for all 4 backend endpoints (/api/chat SSE, /api/conversations, /api/conversations/:id, /api/fuel-prices)
  - Sample fixtures (SAMPLE_CONVERSATIONS, SAMPLE_FUEL_PRICES) for downstream component tests
affects: [04-02-streaming-chat, 04-03-reasoning-trace, 04-04-history-charts, 04-05-app-shell]

tech-stack:
  added:
    - next@^15.5.15
    - react@^19.2.5
    - react-dom@^19.2.5
    - tailwindcss@^4.2.4
    - "@tailwindcss/postcss@^4.2.4"
    - recharts@^3.8.1
    - react-markdown@^10.1.0
    - remark-gfm@^4.0.1
    - clsx@^2.1.1
    - geist@^1.7.0
    - vitest@^4.1.5
    - "@vitejs/plugin-react@^6.0.1"
    - "@testing-library/react@^16.3.2"
    - "@testing-library/user-event@^14"
    - "@testing-library/jest-dom@^6"
    - jsdom@^29
    - msw@^2.13.6
    - "@playwright/test@^1.59.1"
    - "@eslint/eslintrc"
  patterns:
    - Hand-mirrored TS contracts (no codegen) to preserve snake_case JSON wire shape
    - SSE fixture helper enqueues `data: <json>\n\n` frames into ReadableStream and closes controller (Pitfall 10)
    - Single react-is via package.json overrides (Pitfall 3)
    - Tailwind v4 single-line @import (NOT v3 @tailwind triple) (Pitfall 5)
    - MSW node handlers reference fixtures by relative path; tests import via @/types alias

key-files:
  created:
    - frontend/package.json
    - frontend/tsconfig.json
    - frontend/postcss.config.mjs
    - frontend/.prettierrc
    - frontend/eslint.config.mjs
    - frontend/app/globals.css
    - frontend/app/layout.tsx
    - frontend/app/page.tsx
    - frontend/types/api.types.ts
    - frontend/types/agent.types.ts
    - frontend/vitest.config.ts
    - frontend/playwright.config.ts
    - frontend/__tests__/setup.ts
    - frontend/__tests__/mocks/handlers.ts
    - frontend/__tests__/mocks/server.ts
    - frontend/__tests__/fixtures/sse.ts
    - frontend/__tests__/fixtures/agentState.ts
    - frontend/__tests__/lib/sse.placeholder.test.ts
  modified:
    - .env.example (added NEXT_PUBLIC_API_BASE_URL)
    - frontend/.gitignore (added /coverage, /playwright-report, /test-results)

key-decisions:
  - Replaced create-next-app boilerplate (Next 16) with Next 15.5.x pin per plan; deleted auto-generated AGENTS.md/CLAUDE.md/README.md (targeted Next 16 docs that no longer apply)
  - Migrated eslint.config.mjs from native ESM `eslint-config-next/core-web-vitals` import to FlatCompat — eslint-config-next 15.5.x exports `.js` files which the bare specifier could not resolve (Rule 3 blocking fix)
  - Kept default Next.js public/ SVG assets (file/globe/next/vercel/window) committed — harmless boilerplate, will be removed/replaced organically by 04-05 when the app shell lands

patterns-established:
  - "snake_case-on-the-wire: TS interfaces never camelCase backend fields (api.types.ts + agent.types.ts comments enforce this)"
  - "SSE testing pattern: makeSseStream(events) returns closable ReadableStream; Pitfall 10 invariant — controller.close() AFTER enqueue loop"
  - "MSW base URL pinned to NEXT_PUBLIC_API_BASE_URL default (http://localhost:8000); component code that switches base URL must update API_BASE in handlers.ts"

requirements-completed: [UI-01, UI-02, UI-03, UI-04, UI-05, UI-06]

duration: 7min
completed: 2026-04-26
---

# Phase 04 Plan 01: Frontend Foundation Summary

**Next.js 15 + React 19 + Tailwind v4 scaffold with overrides.react-is, hand-mirrored snake_case TS contracts mirroring backend models + SSE envelope, and Vitest + Playwright + MSW test infra with canonical SSE fixtures (happy/capped/clarify/partial)**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-26T04:27:22Z
- **Completed:** 2026-04-26T04:34:45Z
- **Tasks:** 3
- **Files modified:** 21 (19 created + 2 modified)

## Accomplishments

- Buildable, lintable, type-safe Next.js project — `npm run build`, `npm run type-check`, `npm test` all green
- React 19 + Recharts 3 compatibility unblocked: react-is collapsed to a single 19.2.5 across all consumers (testing-library, eslint-plugin-react, recharts) via `overrides.react-is`
- Tailwind v4 PostCSS plugin pipeline working with the v4 `@import "tailwindcss"` syntax (v3 `@tailwind` triple would silently no-op)
- Backend API contract mirrored verbatim with snake_case preserved — ChatRequest, ConversationSummary, FuelPricePoint, ConversationDetail, ReplayedMessage, plus the 5-event SSEEvent union and the 12-field TraceEntry
- Test infrastructure ready end-to-end: jsdom Vitest env, MSW node server with handlers for all 4 backend endpoints, Playwright chromium launched on :3000 via webServer
- Canonical SSE fixtures available for every downstream plan: HAPPY_TRACE (5 nodes), HAPPY_PAYLOAD, CAPPED_PAYLOAD, CLARIFY_PAYLOAD, PARTIAL_PAYLOAD, and `happyTurnEvents()` builder

## Task Commits

1. **Task 1: Scaffold Next.js 15 + Tailwind v4 with pinned versions** — `525d9af` (feat)
2. **Task 2: Hand-write TS contracts mirroring backend** — `02b9598` (feat)
3. **Task 3: Vitest + Playwright + MSW with SSE fixtures** — `a63b7cc` (test)

## Files Created/Modified

### Created
- `frontend/package.json` — Pinned next@^15.5.15, react@^19.2.5, recharts@^3.8.1, plus full test toolchain. `overrides.react-is` forces 19.2.5 single-copy.
- `frontend/tsconfig.json` — Strict mode, ES2022 target, `@/components|@/hooks|@/lib|@/types` aliases, no allowJs.
- `frontend/postcss.config.mjs` — Tailwind v4 plugin (`@tailwindcss/postcss`), no autoprefixer (v4 handles it).
- `frontend/eslint.config.mjs` — FlatCompat-based extends of `next/core-web-vitals` + `next/typescript` (15.x compat).
- `frontend/.prettierrc` — `singleQuote: true`, `trailingComma: 'all'`, `printWidth: 100`.
- `frontend/app/globals.css` — `@import "tailwindcss";` (v4 single-line; replaces v3 `@tailwind` triple).
- `frontend/app/layout.tsx` — Root layout with GeistSans/GeistMono fonts and "Express Surcharge Agent" metadata title.
- `frontend/app/page.tsx` — Placeholder home page until 04-05 wires `<ChatApp />`.
- `frontend/types/api.types.ts` — `ChatRequest`, `ConversationSummary`, `FuelPricePoint`, `ConversationDetail`, `ReplayedMessage` (snake_case preserved).
- `frontend/types/agent.types.ts` — `AgentName`, `TraceStatus`, `TraceEntry` (12 fields), `SurchargeResult`, `FinalStatus`, `FinalPayload`, `SSEEvent` (5-variant discriminated union).
- `frontend/vitest.config.ts` — jsdom env, `@/` alias, react plugin, setup file wired.
- `frontend/playwright.config.ts` — chromium project, webServer launches `npm run dev` on :3000, 30s test timeout.
- `frontend/__tests__/setup.ts` — `@testing-library/jest-dom/vitest` matchers + MSW server lifecycle (listen on `unhandled='error'`, reset, close).
- `frontend/__tests__/mocks/server.ts` — `setupServer(...handlers)` MSW node instance.
- `frontend/__tests__/mocks/handlers.ts` — POST `/api/chat` returns SSE stream from `happyTurnEvents()`; GET `/api/conversations` returns sample list; GET `/api/conversations/:threadId` returns hydrated detail; GET `/api/fuel-prices` returns 7-day series.
- `frontend/__tests__/fixtures/sse.ts` — `makeSseStream` helper, `HAPPY_TRACE` (5-step planner→fuel→route→pricing→response), `HAPPY/CAPPED/CLARIFY/PARTIAL` payloads, `happyTurnEvents(threadId)` builder.
- `frontend/__tests__/fixtures/agentState.ts` — `SAMPLE_CONVERSATIONS` (2 entries), `SAMPLE_FUEL_PRICES` (7-day THB/L from EPPO).
- `frontend/__tests__/lib/sse.placeholder.test.ts` — Smoke test asserting SSE frames are well-formed `data: <json>\n\n` and meta/answer/done are all present.
- `frontend/.gitignore`, `frontend/next.config.ts`, `frontend/app/favicon.ico`, `frontend/public/*.svg` — boilerplate from create-next-app, kept for build correctness.

### Modified
- `.env.example` — Appended `# Phase 4 frontend\nNEXT_PUBLIC_API_BASE_URL=http://localhost:8000` after the Phase 3 block.

## Decisions Made

- **Next 15 over Next 16** — create-next-app@latest installs Next 16 and warns "this is not the Next.js you know". Plan pins Next 15.5.x (matches PROJECT.md tech-stack lock). I deleted auto-generated frontend/AGENTS.md, frontend/CLAUDE.md, frontend/README.md because they reference Next 16 deprecation notices that do not apply to our pinned 15.5.x install.
- **eslint.config.mjs migration to FlatCompat** — the create-next-app v16 template imports `eslint-config-next/core-web-vitals` (no extension), but eslint-config-next@15.5.x ships those exports as `.js` files only — the bare specifier could not resolve under ESLint 9's flat-config loader. Switched to `@eslint/eslintrc`'s FlatCompat which is the canonical 15.x pattern (matches Next.js 15 docs).
- **Default public/ SVG assets retained** — frontend/public/{file,globe,next,vercel,window}.svg are scaffold artifacts. Removing them is cosmetic; downstream UI plans (04-05) will replace `<HomePage>` and the assets at the same time. Keeping them costs ~10 KB.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] eslint.config.mjs incompatible with eslint-config-next 15.x**
- **Found during:** Task 1 (after `npm run build`)
- **Issue:** create-next-app's generated eslint.config.mjs uses bare specifier imports (`import nextVitals from "eslint-config-next/core-web-vitals"`) which require the v16 package layout. eslint-config-next@^15.5.15 only exports `.js` files at those subpaths, so build linting failed with `ERR_MODULE_NOT_FOUND`.
- **Fix:** Rewrote eslint.config.mjs to use `@eslint/eslintrc`'s FlatCompat with `compat.extends("next/core-web-vitals", "next/typescript")` — the canonical 15.x flat-config pattern. Installed `@eslint/eslintrc` as devDependency.
- **Files modified:** frontend/eslint.config.mjs, frontend/package.json, frontend/package-lock.json
- **Verification:** `npm run build` now lints cleanly and exits 0.
- **Committed in:** 525d9af (Task 1 commit)

**2. [Rule 3 - Blocking] frontend/ scaffold collision with .gitkeep**
- **Found during:** Task 1 (first `npx create-next-app` invocation)
- **Issue:** create-next-app aborts when target dir contains files. The pre-existing `frontend/.gitkeep` (placeholder) blocked scaffolding.
- **Fix:** Removed `.gitkeep` before scaffold; staged the deletion in the Task 1 commit (matches plan's files_modified expectation that .gitkeep ceases to exist).
- **Files modified:** frontend/.gitkeep (deleted)
- **Verification:** Scaffold succeeded; `[ ! -f frontend/.gitkeep ]` true.
- **Committed in:** 525d9af (Task 1 commit)

**3. [Rule 1 - Bug] Auto-generated frontend/{AGENTS,CLAUDE,README}.md target wrong Next version**
- **Found during:** Task 1 (post-scaffold inspection)
- **Issue:** create-next-app@16 emits frontend/AGENTS.md with the warning "This is NOT the Next.js you know" and frontend/CLAUDE.md `@AGENTS.md` re-export. Since we downgraded to Next 15.5.x, those files would mislead any future agent/developer.
- **Fix:** Deleted the three auto-generated docs. The repo-root CLAUDE.md (manually authored) remains the source of truth.
- **Files modified:** frontend/AGENTS.md, frontend/CLAUDE.md, frontend/README.md (all deleted)
- **Verification:** None of the three exist in the Task 1 commit; no test depends on them.
- **Committed in:** 525d9af (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** All deviations were caused by the Next 15 → Next 16 generator drift that the plan implicitly anticipated by pinning versions. Each fix preserves the plan's declared end state. No scope creep.

## Issues Encountered

- `npm install` warned about 3 moderate severity vulnerabilities — all in transitive deps of Playwright/Vitest/Next; out of scope for Wave 0 scaffold per scope-boundary rule. Logged for future security pass.
- `npm ls react-is --depth=0` returns empty (react-is is purely transitive). Verified the single-version invariant via deeper `npm ls react-is | grep -oE "react-is@[0-9]+\.[0-9]+\.[0-9]+" | sort -u` → only `react-is@19.2.5`.

## User Setup Required

None — Wave 0 is fully autonomous. The `.env.example` update means anyone running the frontend later only needs to `cp .env.example frontend/.env.local` and edit `NEXT_PUBLIC_API_BASE_URL` if their backend isn't on :8000.

## Next Phase Readiness

Plan 04-02 (Streaming Chat) can now:
- Import `SSEEvent`, `TraceEntry`, `FinalPayload` from `@/types/agent.types`
- Import `ChatRequest`, `ConversationSummary`, `FuelPricePoint` from `@/types/api.types`
- Use `makeSseStream`, `happyTurnEvents`, `HAPPY_TRACE`, `CAPPED_PAYLOAD` etc. from `@/__tests__/fixtures/sse`
- Drop new MSW handlers into `__tests__/mocks/handlers.ts` without re-wiring the server
- Run `npm test` and get a green baseline before adding any production code

No blockers. The Tailwind v4 + Recharts + react-markdown stack is installed and resolves cleanly, so 04-04 (charts) won't hit the blank-render pitfall.

## Self-Check: PASSED

All 18 declared output files exist in the working tree and all 3 task commits (525d9af, 02b9598, a63b7cc) are present in `git log`. Build, type-check, single-react-is invariant, and the placeholder Vitest run all reported green.

---
*Phase: 04-frontend-reasoning-trace*
*Completed: 2026-04-26*
