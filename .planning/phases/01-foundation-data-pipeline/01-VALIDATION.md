---
phase: 1
slug: foundation-data-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest backend/tests/ -x -q` |
| **Full suite command** | `python -m pytest backend/tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest backend/tests/ -x -q`
- **After every plan wave:** Run `python -m pytest backend/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | DATA-01 | unit | `python -m pytest backend/tests/test_rate_table.py -v` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | DATA-02 | unit | `python -m pytest backend/tests/test_seed_database.py -v` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | DATA-03 | unit | `python -m pytest backend/tests/test_fuel_prices.py -v` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | CALC-01 | unit | `python -m pytest backend/tests/test_surcharge.py -v` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 1 | ORCH-06 | unit | `python -m pytest backend/tests/test_state.py -v` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 1 | DOC-03 | file | `test -f .env.example` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/conftest.py` — shared fixtures (tmp db paths, sample data)
- [ ] `backend/tests/test_rate_table.py` — stubs for DATA-01, DATA-02
- [ ] `backend/tests/test_seed_database.py` — stubs for DATA-04, DATA-05
- [ ] `backend/tests/test_fuel_prices.py` — stubs for DATA-03
- [ ] `backend/tests/test_surcharge.py` — stubs for CALC-01 through CALC-04
- [ ] `backend/tests/test_state.py` — stubs for ORCH-06
- [ ] `pytest` install — if not in requirements

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| EPPO scraping live | DATA-03 | Requires internet + EPPO uptime | Run `python data/scripts/fetch_fuel_prices.py` and verify CSV output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
