---
phase: 4
slug: frontend-reasoning-trace
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-26
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest 4.x + @testing-library/react 16.x + Playwright 1.59 (E2E) |
| **Config file** | `frontend/vitest.config.ts` and `frontend/playwright.config.ts` (Wave 0 installs) |
| **Quick run command** | `cd frontend && npm test -- --run` |
| **Full suite command** | `cd frontend && npm test -- --run && npx playwright test` |
| **Estimated runtime** | ~30 seconds (unit) + ~60 seconds (E2E) |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm test -- --run`
- **After every plan wave:** Run `cd frontend && npm test -- --run && npx playwright test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD — populated by planner | TBD | TBD | UI-01..06 | unit/E2E | `cd frontend && npm test -- --run` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/package.json` — Next 15.5.15, React 19.2.5, Tailwind v4, Recharts 3.8.1, react-markdown 10, plus `"overrides": { "react-is": "^19.2.5" }`
- [ ] `frontend/vitest.config.ts` + `frontend/vitest.setup.ts` — JSDOM environment, Testing Library matchers
- [ ] `frontend/playwright.config.ts` — Playwright + Next dev server fixture
- [ ] `frontend/__tests__/` — stub test files for UI-01..UI-06 (red until implementation lands)
- [ ] `frontend/__tests__/fixtures/sse.ts` — fake SSE event streams for hooks/components
- [ ] `frontend/__tests__/mocks/handlers.ts` — MSW handlers for `/api/chat`, `/api/conversations*`, `/api/fuel-prices`

*Wave 0 must scaffold these before any UI implementation tasks ship.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reasoning trace updates "feel live" alongside streaming answer | UI-02 | Subjective UX (perceived smoothness, layout shift) | `cd frontend && npm run dev`, send query, watch trace panel populate while answer streams |
| Recharts dashboard renders without blank-chart bug on React 19.2.x | UI-04 | Visual artifact only detectable in browser | `cd frontend && npm run dev`, navigate to `/dashboard`, confirm fuel + history charts render |
| Sidebar resume restores full conversation including trace | UI-05 | E2E covers click flow but visual fidelity needs eyeballing | `cd frontend && npm run dev`, send 2 queries, refresh, click prior thread in sidebar |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
