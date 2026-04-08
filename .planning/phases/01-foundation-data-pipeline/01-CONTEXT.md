# Phase 1: Foundation & Data Pipeline - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Seeded SQLite database with rate tables, zone definitions, and fuel price history. Plus the Pydantic models, AgentState TypedDict, surcharge formula as a pure function, and .env.example. This is the foundation everything else builds on.

</domain>

<decisions>
## Implementation Decisions

### Rate table design
- **D-01:** 5 weight tiers: 0-5kg, 5-10kg, 10-20kg, 20-50kg, 50+kg
- **D-02:** Realistic THB base rates modeled on Thai Express pricing (~50-500 THB), increasing by zone distance and weight, with documented assumptions in the generation script
- **D-03:** Minimal columns: shipping_type, zone, weight_min_kg, weight_max_kg, base_rate_thb
- **D-04:** Generated CSV committed to data/raw/express_rate_table.csv for reproducibility — anyone cloning gets the same data

### Fuel price sourcing
- **D-05:** Web scrape EPPO public price board for diesel B7 prices
- **D-06:** Fetch 6 months of daily price history (~180 data points)
- **D-07:** Ship a pre-scraped seed CSV in data/raw/eppo_diesel_prices.csv as fallback — project always works without internet
- **D-08:** CSV columns: date (YYYY-MM-DD), diesel_b7_price (THB/L), source (eppo/ptt)

### Surcharge formula implementation
- **D-09:** Constants configured via environment variables: BASELINE_DIESEL_PRICE, SURCHARGE_CAP, SURCHARGE_FLOOR (matches existing .env.example pattern)
- **D-10:** Pure function lives in backend/agent/tools/calculate_surcharge.py — Phase 2 wraps it as a LangGraph tool
- **D-11:** Invalid inputs (bad shipping_type, missing data) raise ValueError with descriptive messages — callers handle errors
- **D-12:** Tests use hand-calculated known input/output pairs for each shipping type, including cap/floor trigger cases and traffic adjustment (Bounce only)

### Claude's Discretion
- Zone-province mapping granularity (province-level vs district-level for central-1, central-2, central-3)
- Exact rate values within realistic THB ranges
- EPPO scraping implementation details (library choice, parsing approach)
- AgentState and Pydantic model field naming beyond what's in docs/architecture.md
- Test file organization and pytest configuration

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & agent state
- `docs/architecture.md` -- Agent state schema (AgentState TypedDict), surcharge formula spec, zone definitions, tool specifications, conditional routing table

### Project context
- `.planning/REQUIREMENTS.md` -- Phase 1 requirements: DATA-01 through DATA-05, CALC-01 through CALC-04, TOOL-06, ORCH-06, DOC-03
- `.planning/PROJECT.md` -- Tech stack constraints (Gemini Flash, SQLite, free-tier only), grading criteria, timeline

### Environment
- `.env.example` -- All required API key placeholders and surcharge config defaults

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — codebase is scaffold-only with empty `__init__.py` files and `.gitkeep` placeholders

### Established Patterns
- Directory structure follows brief-mandated layout: backend/agent/nodes/, backend/agent/tools/, data/scripts/, data/raw/
- Python conventions documented in .planning/codebase/CONVENTIONS.md (PEP 8, Black formatting, Google-style docstrings, TypedDict for state)

### Integration Points
- data/raw/*.csv files consumed by data/scripts/seed_database.py to produce data/express.db
- backend/agent/tools/calculate_surcharge.py will be imported by Phase 2 tool wrapper
- backend/agent/state.py (AgentState) imported by every agent node in Phase 2+
- .env.example referenced by all phases for configuration

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-data-pipeline*
*Context gathered: 2026-04-04*
