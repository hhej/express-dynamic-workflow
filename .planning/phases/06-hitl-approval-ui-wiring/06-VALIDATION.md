---
phase: 06
slug: hitl-approval-ui-wiring
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-05
---

# Phase 06 — Validation Strategy

> Per-phase validation contract reconstructed from PLAN/SUMMARY artifacts after phase completion (State B reconstruction).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 2.x + @testing-library/react + jsdom + MSW |
| **Config file** | `frontend/vitest.config.ts` |
| **Quick run command** | `cd frontend && npx vitest run __tests__/components/<file>.test.tsx` |
| **Full suite command** | `cd frontend && npx vitest run` |
| **TypeScript check** | `cd frontend && npx tsc --noEmit` |
| **Production build** | `cd frontend && npm run build` |
| **Estimated runtime** | ~6s (vitest); ~30s (next build) |

---

## Sampling Rate

- **After every task commit:** Run scoped `npx vitest run __tests__/components/<file>.test.tsx`
- **After every plan wave:** Run full `npx vitest run` + `npx tsc --noEmit`
- **Before `/gsd:verify-work`:** Full suite green + `npm run build` exits 0
- **Max feedback latency:** ~6s for vitest, ~30s for build

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-T1 | 01 | 1 | UI-01 | unit + build | `cd frontend && npx vitest run __tests__/components/TraceStep.test.tsx && npx tsc --noEmit && npm run build` | ✅ | ✅ green |
| 06-02-T1 | 02 | 1 | UI-01 | unit | `cd frontend && npx vitest run __tests__/components/ApprovalCard.test.tsx __tests__/components/MessageList.test.tsx __tests__/components/ChatInput.test.tsx && npx tsc --noEmit` | ✅ | ✅ green |
| 06-02-T2 | 02 | 1 | ORCH-09, UI-01 | unit + build | `cd frontend && npx vitest run __tests__/components/ChatColumn.test.tsx __tests__/components/ChatApp.test.tsx && npx tsc --noEmit && npm run build` | ✅ | ✅ green |
| 06-03-T1 | 03 | 2 | ORCH-09, UI-01 | integration (MSW SSE) | `cd frontend && npx vitest run __tests__/components/ChatApp.integration.test.tsx` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Requirement Coverage Matrix

| Requirement | Behavior | Test File | Test Marker | Status |
|-------------|----------|-----------|-------------|--------|
| UI-01 | TraceStep renders non-empty label for all 7 AgentName variants (drift prevention) | [TraceStep.test.tsx](frontend/__tests__/components/TraceStep.test.tsx) | `AGENT_NAMES` exhaustive loop (D-15.1) | COVERED |
| UI-01 | `next build` + `tsc --noEmit` exit 0 (TS2739 cleared) | npm/tsc commands in 06-01-T1 verify | build pipeline | COVERED |
| UI-01 | ApprovalCard renders inline red error line on failed POST | [ApprovalCard.test.tsx](frontend/__tests__/components/ApprovalCard.test.tsx) | D-10 / D-11 / `text-red-700` | COVERED |
| UI-01 | ChatInput shows locked HITL placeholder while paused | [ChatColumn.test.tsx](frontend/__tests__/components/ChatColumn.test.tsx) + [ChatApp.integration.test.tsx](frontend/__tests__/components/ChatApp.integration.test.tsx) | D-08 placeholder forwarding | COVERED |
| UI-01 | ChatColumn forwards approval props to MessageList → ApprovalCard | [ChatColumn.test.tsx](frontend/__tests__/components/ChatColumn.test.tsx) | D-15.2 props-forwarding | COVERED |
| ORCH-09 | High-value query → ApprovalCard renders end-to-end via SSE | [ChatApp.integration.test.tsx](frontend/__tests__/components/ChatApp.integration.test.tsx) | "approve flow" / D-15.3 | COVERED |
| ORCH-09 | Approve resumes graph → MarkdownAnswer renders final answer | [ChatApp.integration.test.tsx](frontend/__tests__/components/ChatApp.integration.test.tsx) | "approve flow" + resume POST contract | COVERED |
| ORCH-09 | Deny short-circuits → PartialCard renders deny prose | [ChatApp.integration.test.tsx](frontend/__tests__/components/ChatApp.integration.test.tsx) | "deny flow" + PARTIAL_PAYLOAD | COVERED |
| ORCH-09, UI-01 | ChatInput disabled during awaiting_approval window | [ChatApp.integration.test.tsx](frontend/__tests__/components/ChatApp.integration.test.tsx) | `toBeDisabled()` after approval_required | COVERED |

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No Wave 0 stubs needed — Vitest, MSW, jsdom, @testing-library/react were all installed before Phase 06.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live HITL flow against real backend (visual color contrast on yellow-50/yellow-300 ApprovalCard palette; real-time SSE under production network conditions) | ORCH-09 | Integration test mocks SSE via MSW; visual palette + real-network behavior require human eye + running backend | Start backend (`uvicorn backend.api.main:app --port 8000`) + frontend (`npm run dev`); send a high-value shipment query exceeding the approval threshold; observe ApprovalCard renders within 5 seconds with surcharge totals; verify ChatInput placeholder reads "Awaiting your approval — use Approve / Deny above"; click Approve → MarkdownAnswer renders; repeat with Deny → PartialCard renders. (Optional pre-tag-v1.0 UAT — flagged as not blocking by VERIFICATION.md.) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands (4/4)
- [x] Sampling continuity: every task has its own scoped vitest invocation
- [x] Wave 0 covers all MISSING references — none missing
- [x] No watch-mode flags (all commands use `vitest run`)
- [x] Feedback latency < 30s (vitest ~6s, build ~30s)
- [x] Full suite passes: 28 files / 122 tests (re-run 2026-05-05)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-05 (State B reconstruction post-phase; all requirements have automated verification, no gaps found).

---

## Validation Audit 2026-05-05

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Tests already covering all requirements | 4 task-level + 1 cross-cutting integration |

State B reconstruction: PLAN/SUMMARY/VERIFICATION artifacts confirm every requirement (ORCH-09, UI-01) has an automated verify command tied to a passing test file. Full suite re-run on 2026-05-05 confirmed 122/122 green. No auditor agent spawn required.
