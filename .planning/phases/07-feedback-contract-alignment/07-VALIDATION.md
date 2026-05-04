---
phase: 7
slug: feedback-contract-alignment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) / vitest (frontend) |
| **Config file** | backend/pytest.ini, frontend/vitest.config.ts |
| **Quick run command** | `cd backend && pytest tests/ -x -q` / `cd frontend && npx vitest run` |
| **Full suite command** | `cd backend && pytest && cd ../frontend && npx vitest run && npx tsc --noEmit` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command for the layer touched (backend or frontend)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Populated by gsd-planner after PLAN.md files are written.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | API-05 / OBS-02 / UI-05 | TBD | TBD | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Populated by gsd-planner after analyzing the validation architecture in 07-RESEARCH.md.

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live thumbs-up click produces `user_feedback` Score row in Langfuse | OBS-02 | Requires real Langfuse credentials, real backend instance, and human-driven UI click; the appearance of a remote Score row in the Langfuse SaaS dashboard cannot be asserted from automated tests | 1) Start backend with valid LANGFUSE_* env vars; 2) Start frontend; 3) Send a chat message; 4) Click thumbs-up on the assistant response; 5) Open Langfuse dashboard for the trace; 6) Confirm a `user_feedback` Score row exists with value=1; 7) Save screenshot to `docs/screenshots/langfuse-feedback-score.png` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
