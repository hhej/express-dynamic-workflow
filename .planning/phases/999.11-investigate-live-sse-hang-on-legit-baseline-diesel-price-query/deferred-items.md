# Deferred items — Phase 999.11

Out-of-scope discoveries surfaced during Plan 05 execution. NOT fixed in this plan; logged for future cleanup.

## Phase 10 list-checkbox drift in ROADMAP.md

**Found during:** Plan 05 Task 3 (REQUIREMENTS/ROADMAP/STATE flips).

**Issue:** `ROADMAP.md` line 40 still shows Phase 10 as `- [ ] **Phase 10: Unify Refusal Copy on Planner Bypass Paths**` (active-phases checklist), even though:
- `REQUIREMENTS.md` line 117 shows `| GUARD-07 | Phase 10 | Complete |`
- `STATE.md` says "Last completed: Phase 999.10 ... — 2026-05-11"
- Plans 999.10-01..03 are all marked `[x]` in the Phase 10 detail block

The discrepancy looks like a missed roadmap update during Phase 999.10's metadata-commit step (the detail block was updated but the active-phases active checklist row was not flipped).

**Why deferred:** Out of scope — Phase 999.11 Plan 05's responsibility is Phase 11/FIX-02 closure. Touching Phase 10's checkbox here would conflate two phases' progress reporting. Fix belongs in a follow-up housekeeping commit or the v1.1 milestone-audit step.

**Fix when convenient:** Single-line edit on `ROADMAP.md` line 40 — flip `[ ]` → `[x]`, append `(3/3 plans) — completed 2026-05-11` to match Phase 9/Phase 11 styling.

## ROADMAP Progress table Phase 10 row

**Found during:** Same.

**Issue:** `ROADMAP.md` Progress table line 136 shows:
```
| 10. Unify Refusal Copy on Planner Bypass Paths | v1.1 | 0/3 | Planned (awaiting execute) | - |
```
This contradicts the Phase 10 detail block (which lists 3 plans all `[x]`) and `REQUIREMENTS.md`. Same root cause as above (missed roadmap update on Phase 10 closure).

**Why deferred:** Same as above.

**Fix when convenient:** Single-line edit — replace with:
```
| 10. Unify Refusal Copy on Planner Bypass Paths | v1.1 | 3/3 | Complete | 2026-05-11 |
```
