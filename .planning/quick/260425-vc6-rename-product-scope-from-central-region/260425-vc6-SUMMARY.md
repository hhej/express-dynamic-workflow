---
quick_id: 260425-vc6
slug: rename-product-scope-from-central-region
date: 2026-04-25
status: complete
verification: passed
---

# Quick Task 260425-vc6 Summary

## Outcome

Renamed user-facing product scope language from **"Central Region"** to **"Bangkok Metro"** across docs, code docstrings, and runtime error messages. Internal zone identifiers (`central-1/2/3`) were intentionally preserved to avoid churn in rate tables, fixtures, and `lookup_rate` logic.

Resolves backlog item **999.2 option (b)**.

## Files Changed (7)

| File | Change |
|------|--------|
| `CLAUDE.md` | Project description + Google Maps data source line |
| `.planning/PROJECT.md` | "What This Is", validated zone requirement, Out of Scope entry (3 hits) |
| `README.md` | Tagline, scope line, EPPO data source row, limitation line (4 hits) |
| `docs/architecture.md` | Overview section |
| `backend/agent/tools/calculate_route.py` | 2 docstrings + 1 `ValueError` runtime message |
| `data/scripts/generate_rate_table.py` | Module docstring + zone-definitions comment |
| `.planning/ROADMAP.md` | New **Backlog** section with 999.2 marked Resolved 2026-04-25 |

## Commits

- `59176a5` docs(quick-260425-vc6): rename Central Region → Bangkok Metro in user-facing docs
- `f2fbc99` refactor(quick-260425-vc6): rename Central Region → Bangkok Metro in code docstrings + ValueError
- `4889bf6` docs(quick-260425-vc6): mark backlog 999.2 resolved in ROADMAP

Note: `.planning/PROJECT.md` was updated inline by the user before the executor ran; that change carried into the docs commit via the regular `git diff` flow.

## Verification

- `grep -rn "Central Region" backend/ docs/ README.md CLAUDE.md .planning/PROJECT.md data/scripts/` → **CLEAN** (zero matches in in-scope files)
- `python -m pytest backend/tests/ -q` → **103 passed, 0 failed** (matches prior baseline)
- `git diff --check central-[123]` → **no zone-identifier churn**
- 6 source files committed against `acbc3b5` merge base + ROADMAP.md committed in 4889bf6

## Out-of-Scope (Preserved)

- `central-1`, `central-2`, `central-3` zone identifiers — load-bearing in rate tables and fixtures
- Test fixture data using `central-*` zone names
- Existing `.planning/phases/*/SUMMARY.md` and historical artifacts (point-in-time records)
- `.planning/REQUIREMENTS.md`, `.planning/codebase/`, `.planning/research/` (internal planning records)

## Branch Context Note

This quick task was executed on branch `fix/planner-merge`. The earlier backlog item commits (999.1, 999.2, 999.3) were authored on `feat/graph-assembly-api-layer` and have not yet been merged to develop, so the Backlog section here was created fresh containing only the 999.2 resolution record. When the feat branch eventually merges, the two Backlog sections may need to be reconciled (low risk — both are append-only).

## Future Possibility (Option a)

Backlog 999.2 option (a) — expanding the zone classifier and rate table to cover proper Central Region cities (Lop Buri, Kanchanaburi, etc.) — remains open as a v2.0 possibility. It would require new zone definitions, rate table rows, and Google Maps coverage testing.
