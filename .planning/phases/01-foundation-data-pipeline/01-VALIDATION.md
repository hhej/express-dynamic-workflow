---
phase: 1
slug: foundation-data-pipeline
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-04
last_audit: 2026-05-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest backend/tests/ -x -q` |
| **Full suite command** | `python -m pytest backend/tests/ -v` |
| **Estimated runtime** | ~9 seconds (236 tests) |

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
| 01-01-01 | 01 | 1 | DATA-01 | integration | `python -m pytest backend/tests/test_seed_database.py::TestSeedDatabaseRateTable -v` | ✅ | ✅ green |
| 01-01-02 | 01 | 1 | DATA-02 | unit | `python -m pytest backend/tests/test_fuel_prices.py -v` | ✅ | ✅ green |
| 01-01-03 | 01 | 1 | DATA-03 | unit | `python -m pytest backend/tests/test_rate_table.py -v` | ✅ | ✅ green |
| 01-01-04 | 01 | 1 | DATA-04 | integration | `python -m pytest backend/tests/test_seed_database.py -v` | ✅ | ✅ green |
| 01-01-05 | 01 | 1 | DATA-05 | unit | `python -m pytest backend/tests/test_zones.py backend/tests/test_seed_database.py::TestSeedDatabaseZones -v` | ✅ | ✅ green |
| 01-02-01 | 02 | 1 | TOOL-06 | unit | `python -m pytest backend/tests/test_models.py -v` | ✅ | ✅ green |
| 01-02-02 | 02 | 1 | ORCH-06 | unit | `python -m pytest backend/tests/test_models.py::TestAgentState -v` | ✅ | ✅ green |
| 01-03-01 | 03 | 1 | CALC-01..04 | unit | `python -m pytest backend/tests/test_surcharge.py -v` | ✅ | ✅ green |
| 01-03-02 | 03 | 1 | DOC-03 | file | `test -f .env.example` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| EPPO scraping live | DATA-02 (live path) | Requires internet + EPPO uptime; automated path covers fallback only | Run `python data/scripts/fetch_fuel_prices.py` with network enabled and confirm "Fetched N rows from EPPO" |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-05-05

---

## Validation Audit 2026-05-05

| Metric | Count |
|--------|-------|
| Gaps found | 5 |
| Resolved | 5 |
| Escalated | 0 |

**New tests added:**
- `backend/tests/test_rate_table.py` — 12 tests (DATA-03)
- `backend/tests/test_seed_database.py` — 15 tests (DATA-01, DATA-04, DATA-05)
- `backend/tests/test_fuel_prices.py` — 8 tests (DATA-02 fallback path)
- `backend/tests/test_zones.py` — 7 tests (DATA-05)

**Run results:** 42 new tests pass (0.40s); full backend suite 236 pass (~9s); no regressions.
