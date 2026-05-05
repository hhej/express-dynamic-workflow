---
phase: 08
slug: search-context-sidebar-polish
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-05
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest 4.x (frontend) |
| **Config file** | `backend/pytest.ini`, `frontend/vitest.config.ts` |
| **Quick run command** | `python -m pytest backend/tests/test_response_node.py -q` (BE) / `cd frontend && npx vitest run __tests__/components/MessageList.search_only.test.tsx __tests__/hooks/useConversations.test.tsx __tests__/components/ChatApp.integration.test.tsx` (FE) |
| **Full suite command** | `python -m pytest backend/tests/ -q && cd frontend && npx vitest run` |
| **Estimated runtime** | ~30 seconds full suite |

---

## Sampling Rate

- **After every task commit:** Run quick command for the touched layer (BE or FE)
- **After every plan wave:** Run full suite for both layers
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01.T1 | 01 | 1 | TOOL-05 | pytest (drift-prevention) | `python -m pytest backend/tests/test_response_node.py::test_response_forwards_search_context_in_final_payload_when_present backend/tests/test_response_node.py::test_response_search_context_is_none_in_final_payload_when_absent backend/tests/test_response_node.py::test_response_deny_path_forwards_search_context_in_final_payload -q` | ✅ `backend/tests/test_response_node.py` | ✅ green |
| 08-01.T2 | 01 | 1 | UI-02 | vitest + @testing-library/react | `cd frontend && npx vitest run __tests__/components/MessageList.search_only.test.tsx` | ✅ `frontend/__tests__/components/MessageList.search_only.test.tsx` | ✅ green |
| 08-02.T1 | 02 | 1 | UI-06 (refactor) | vitest renderHook | `cd frontend && npx vitest run __tests__/hooks/useConversations.test.tsx` | ✅ `frontend/__tests__/hooks/useConversations.test.tsx` | ✅ green |
| 08-02.T2 | 02 | 1 | UI-06 (migration) | vitest + tsc | `cd frontend && npx vitest run __tests__/components/ChatApp.test.tsx __tests__/components/ChatApp.integration.test.tsx && npx tsc --noEmit` | ✅ `frontend/components/ChatApp.tsx` | ✅ green |
| 08-02.T3 | 02 | 1 | UI-06 (drift-prevention) | vitest + MSW integration | `cd frontend && npx vitest run __tests__/components/ChatApp.integration.test.tsx` | ✅ `frontend/__tests__/components/ChatApp.integration.test.tsx` (D-14 describe block) | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covered all phase requirements — no Wave 0 needed.*
- pytest + fixtures already wired (`backend/tests/conftest.py`)
- vitest + MSW + @testing-library/react already wired (`frontend/__tests__/mocks/server.ts`, `frontend/vitest.config.ts`)
- No new dependencies required (React Context is built-in to React 19 already in `frontend/package.json`)

---

## Manual-Only Verifications

> Both items below are now backed by automated drift-prevention tests (see Per-Task Map). They are retained as **supplementary visual smoke checks** for live demo confidence, not as primary coverage.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual confirmation that SearchContextLine renders clickable sources in browser when `'search_only'` status arrives | UI-02 (supplementary) | Live link interactivity feel — automated test asserts attributes, not visual layout | Start dev server, send Tavily-only news query (e.g. "What's the diesel news today?"), verify SearchContextLine appears with sources expandable and clickable |
| Sidebar refresh visible after a completed turn without page reload | UI-06 (supplementary) | UX continuity feel — automated test asserts the wire, not the perceived latency | Start dev server, send a complete surcharge query, observe sidebar updates with new turn entry within ~1s of FinalStatus arrival |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none required)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-05

---

## Validation Audit 2026-05-05

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

Phase 8 was executed with TDD-first drift-prevention tests in both plans. The audit confirmed all 3 requirements (TOOL-05, UI-02, UI-06) have automated coverage that exercises the production wire (BE final_payload contract, FE rendering dispatch, FE provider-shared sidebar refresh). No gaps required filling.

**Tests verified green at audit:**
- `backend/tests/test_response_node.py` — 17/17 (3 new drift-prevention)
- `frontend/__tests__/components/MessageList.search_only.test.tsx` — 1/1
- `frontend/__tests__/hooks/useConversations.test.tsx` — 3/3 (with provider wrapper)
- `frontend/__tests__/components/ChatApp.integration.test.tsx` — 3/3 (incl. new D-14 sidebar refresh)
