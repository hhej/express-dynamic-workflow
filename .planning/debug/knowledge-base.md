# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## fix-eppo-scraper-url-restructure — EPPO petroleum-statistics URL slug renamed and Excel structure changed; scraper failed with 404
- **Date:** 2026-05-09
- **Error patterns:** requests.exceptions.HTTPError, 404 Client Error, Component not found, en-petroleum-statistic, _scrape_eppo, fetch_fuel_prices, eppo.go.th, dashboard 7d empty, dashboard 30d empty, fetched 0 rows from EPPO
- **Root cause:** EPPO renamed the Joomla menu slug from `en-petroleum-statistic` to `petroleumprice-statistic` and restructured the page to expose pivoted Excel tables (P03..P09). The original `_scrape_eppo()` both targeted the dead URL and assumed a flat-header CSV/Excel — it could not parse P09's pivoted MIN/WT.AVG/MAX-by-month layout. The legacy `xlrd` driver was also missing from the venv, blocking BIFF .xls reads. P09 alone is monthly; the published daily snapshot lives on a separate oil-share PHP page.
- **Fix:** Rewrote `_scrape_eppo()` to (1) download `P09.xls` from the new direct URL, (2) parse via a dedicated `_parse_p09_workbook()` that walks the "2003-current" sheet and emits one row per month from the WT.AVG bucket of column 8 (HSD B7), (3) optionally pull today's daily snapshot via `_scrape_oil_share_today()` (parses `oil_name6v2.png` row label on the EPPO oil-share page), and (4) merge with the seed CSV (append only rows strictly newer than the seed max, dedup on date). Added `xlrd==2.0.2` to requirements. Added `TestScrapeEppoInternals` (5 tests) for the new internals. Public contract preserved.
- **Files changed:** data/scripts/fetch_fuel_prices.py, data/raw/eppo_diesel_prices.csv, requirements.txt, backend/tests/test_fuel_prices.py
---
