---
phase: 5
slug: polish-observability-docs
status: nyquist-compliant
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-02
audited: 2026-05-05
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Audited 2026-05-05 against actual code + test state. All code requirements have automated coverage; manual items are documentation/visual verification only.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest 8.x |
| **Frontend framework** | vitest 2.x (jsdom) |
| **Backend config** | `pyproject.toml` (pytest section) |
| **Frontend config** | `frontend/vitest.config.ts` |
| **Backend quick run** | `.venv/bin/pytest backend/tests/ -x -q` |
| **Backend full run** | `.venv/bin/pytest backend/tests/` |
| **Frontend run** | `cd frontend && npm test -- --run` |
| **Last green** | 2026-05-05 — backend 236/236, frontend 122/122 |
| **Estimated runtime** | ~8s backend, ~6s frontend |

---

## Sampling Rate

- **After every task commit:** `.venv/bin/pytest backend/tests/ -x -q` (touched module's tests if scoped)
- **After every plan wave:** `.venv/bin/pytest backend/tests/`
- **Before `/gsd:verify-work`:** Full backend + frontend suites green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01 | 01 | 1 | OBS-01, OBS-03 | unit | `pytest backend/tests/test_observability.py backend/tests/test_state_phase5.py` | ✅ | ✅ green |
| 05-02 | 02 | 2 | OBS-01, OBS-03 | integration | `pytest backend/tests/test_observability_wiring.py backend/tests/test_api_chat.py` | ✅ | ✅ green |
| 05-03 | 03 | 2 | ORCH-07 | unit + integration | `pytest backend/tests/test_parallel_fanout.py backend/tests/test_planner.py` | ✅ | ✅ green |
| 05-04 | 04 | 3 | TOOL-05 | unit + integration | `pytest backend/tests/test_search_fuel_news.py backend/tests/test_search_agent.py backend/tests/test_planner.py backend/tests/test_response_node.py` | ✅ | ✅ green |
| 05-05 | 05 | 4 | ORCH-09 | unit + integration | `pytest backend/tests/test_hitl_gate.py backend/tests/test_response_node.py backend/tests/test_api_chat.py` | ✅ | ✅ green |
| 05-06 | 06 | 5 | API-05, OBS-02 | unit + component | `pytest backend/tests/test_api_feedback.py` + `vitest run __tests__/components/{ApprovalCard,SearchContextLine,FeedbackButtons}.test.tsx` | ✅ | ✅ green |
| 05-07 | 07 | 6 | DOC-01, DOC-02, DOC-04 | manual | n/a — markdown rendering on GitHub | ✅ docs present | ⚪ manual-only |
| 05-08 | 08 | 7 | ORCH-07 (gap-1) | unit + integration | `pytest backend/tests/test_planner.py backend/tests/test_graph.py` | ✅ | ✅ green |
| 05-09 | 09 | 7 | ORCH-03, ORCH-08, DOC-01, DOC-02, DOC-04 (gap-2) | unit + integration | `pytest backend/tests/test_route_agent.py backend/tests/test_graph.py` (DOC-* manual) | ✅ | ✅ green |
| 05-10 | 10 | 8 | TOOL-05, ORCH-01 (gap-3) | unit + integration | `pytest backend/tests/test_planner.py backend/tests/test_response_node.py backend/tests/test_graph.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · ⚪ manual-only*

---

## Wave 0 Requirements

> Wave 0 was implemented inside Plan 05-01 (Wave 1). All preconditions confirmed at audit time:

- [x] Python venv runs 3.11+ (langfuse 3.x compatible)
- [x] `backend/tests/conftest.py` — shared fixtures present (mock Langfuse, mock Tavily, AsyncSqliteSaver test harness)
- [x] AgentState fields registered: `approval_decision`, `search_context` (verified at `backend/agent/state.py`)
- [x] `backend/agent/observability.py` — `get_callback_handler`, `seed_trace_id`, `post_formula_accuracy_score` present
- [x] Test stubs created and matured for: parallel fan-out (ORCH-07), HITL gate (ORCH-09), Tavily search (TOOL-05), feedback scoring (OBS-02), formula accuracy (OBS-03), API approval (API-05/ORCH-09)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Langfuse dashboard shows traced LLM + tool calls | OBS-01 | Live Langfuse UI; needs API keys + running server | Run a query with `LANGFUSE_*` env set, open Langfuse Cloud trace, confirm `chat_turn_*` spans for planner/fuel/route/pricing/response |
| User feedback shows as Langfuse Score | OBS-02 | Live Langfuse UI; needs API keys + running server | Submit thumbs vote, refresh Langfuse trace, confirm `user_feedback` Score (-1 or 1) |
| `formula_accuracy` Score visible per pricing turn | OBS-03 | Live Langfuse UI; needs API keys + running server | Run pricing query, confirm `formula_accuracy` Score (0.0 or 1.0) on the trace |
| README, architecture, data-sources render correctly on GitHub | DOC-01, DOC-02, DOC-04 | Markdown + Mermaid rendering nuances | Push branch, open files in GitHub web UI, confirm Mermaid diagrams render |
| HITL approval card surfaces in frontend | API-05, ORCH-09 | End-to-end UI flow against running backend | High-value query → ApprovalCard appears → approve → final response renders |
| Demo video showing parallel timestamps + HITL | ROADMAP §Phase 5 success criterion 1 | Cannot run a screen recorder | Record `docs/demo.mp4` per Plan 05-07 Task 4 |
| 5 PNG screenshots for submission | DOC-01 | Cannot capture browser screenshots | Capture per Plan 05-07 Task 4: chat-breakdown, trace-parallel, dashboard, hitl-approval, langfuse-trace |
| Annotated `v1.0` git tag | Submission deliverable D-21 | IT Lead pushes tag; cannot push to remote | `git tag -a v1.0 -m "..." && git push origin v1.0` |

---

## Validation Sign-Off

- [x] All code-bearing tasks have automated verify (10/10 plans; DOC-* and submission deliverables intentional manual-only)
- [x] Sampling continuity: every consecutive task has automated tests in passing suite
- [x] Wave 0 covers all MISSING references — none outstanding
- [x] No watch-mode flags in commands
- [x] Feedback latency < 60s (backend ~8s, frontend ~6s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-05

---

## Validation Audit 2026-05-05

| Metric | Count |
|--------|-------|
| Plans audited | 10 |
| Code requirements covered automatically | 9 (ORCH-01, ORCH-03, ORCH-07, ORCH-08, ORCH-09, TOOL-05, API-05, OBS-01, OBS-02, OBS-03) |
| Manual-only categories | 3 (docs rendering, live Langfuse dashboard, submission deliverables) |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Backend tests | 236/236 passing |
| Frontend tests | 122/122 passing |

**Verdict:** Phase 5 is Nyquist-compliant. Every code requirement has at least one automated test in the passing suite. Manual items are intentional human-only checkpoints (documentation rendering, live Langfuse dashboard, submission deliverables) that cannot be programmatically verified by design.
