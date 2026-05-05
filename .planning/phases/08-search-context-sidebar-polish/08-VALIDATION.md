---
phase: 08
slug: search-context-sidebar-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest 2.x (frontend) |
| **Config file** | `backend/pytest.ini`, `frontend/vitest.config.ts` |
| **Quick run command** | `cd backend && pytest tests/test_response_node.py -q` (BE) / `cd frontend && npx vitest run __tests__/components/MessageList.test.tsx` (FE) |
| **Full suite command** | `cd backend && pytest -q && cd ../frontend && npx vitest run` |
| **Estimated runtime** | ~30 seconds full suite |

---

## Sampling Rate

- **After every task commit:** Run quick command for the touched layer (BE or FE)
- **After every plan wave:** Run full suite for both layers
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Filled by gsd-planner once tasks are written. Each row maps a task to an automated verify command and the requirement it closes.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD     | TBD  | TBD  | TOOL-05 / UI-02 / UI-06 | TBD | TBD | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements — no Wave 0 needed.*
- pytest + fixtures already wired (`backend/tests/conftest.py`)
- vitest + MSW + @testing-library/react already wired (`frontend/__tests__/mocks/server.ts`, `frontend/vitest.config.ts`)
- No new dependencies required (React Context is built-in to React 19 already in `frontend/package.json`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual confirmation that SearchContextLine renders clickable sources in browser when `'search_only'` status arrives | UI-02 | UI rendering correctness is best confirmed visually | Start dev server, send Tavily-only news query (e.g. "What's the diesel news today?"), verify SearchContextLine appears with sources expandable and clickable |
| Sidebar refresh visible after a completed turn without page reload | UI-06 | UX continuity check | Start dev server, send a complete surcharge query, observe sidebar updates with new turn entry within ~1s of FinalStatus arrival |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (none required)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
