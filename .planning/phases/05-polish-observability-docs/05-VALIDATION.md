---
phase: 5
slug: polish-observability-docs
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-02
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Concrete test map populated by the planner from `05-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend) + jest/vitest if frontend tests added |
| **Config file** | `backend/pyproject.toml` (pytest section) — Wave 0 installs/extends if missing |
| **Quick run command** | `cd backend && pytest -x -q tests/` |
| **Full suite command** | `cd backend && pytest tests/ --maxfail=3` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest -x -q tests/` (only the touched module's tests if scoped)
- **After every plan wave:** Run `cd backend && pytest tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Populated by planner from RESEARCH.md § Validation Architecture. Each plan task with code surface area MUST have a row here.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD-by-planner | 0X | W | REQ-XX | unit/integration | `pytest tests/...` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Populated by planner. Expected items based on RESEARCH.md:

- [ ] Python venv bump to 3.11 (or pin `langfuse<3.0`) — **decision required before any other Wave**
- [ ] `backend/tests/conftest.py` — shared fixtures (mock Langfuse, mock Tavily, AsyncSqliteSaver test harness)
- [ ] New state fields registered (`approval_status`, `approval_threshold`, `news_data` etc.) before parallel/HITL waves
- [ ] `backend/agent/observability.py` stub — Langfuse callback handler + `seed_trace_id()` helper
- [ ] Test stubs created for: parallel fan-out (ORCH-07), HITL gate (ORCH-09), Tavily search tool (TOOL-05), feedback scoring (OBS-03), API approval endpoint (API-05)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

> Populated by planner. Expected items:

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Langfuse dashboard shows traced LLM + tool calls | OBS-01, OBS-02 | Visual UI verification on hosted Langfuse | Run a query, open Langfuse trace URL, confirm spans for planner/fuel/route/pricing/response |
| User feedback shows as Langfuse score | OBS-03 | Visual UI verification | Submit thumbs up/down, refresh Langfuse trace, confirm score entry |
| README, architecture docs render correctly on GitHub | DOC-01, DOC-02, DOC-04 | Markdown rendering nuances | Push branch, view docs on GitHub web UI |
| HITL approval surfaces in frontend chat | API-05, ORCH-09 | UI flow verification | High-value query → approval card appears → approve → final response renders |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
