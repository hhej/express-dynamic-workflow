# Phase 1: Foundation & Data Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 01-foundation-data-pipeline
**Areas discussed:** Rate table design, Fuel price sourcing, Surcharge formula impl

---

## Rate Table Design

### Weight tiers

| Option | Description | Selected |
|--------|-------------|----------|
| 5 tiers | 0-5kg, 5-10kg, 10-20kg, 20-50kg, 50+kg -- realistic granularity | ✓ |
| 3 tiers (minimal) | Small, Medium, Large -- simpler | |
| 8+ tiers (detailed) | Fine-grained weight brackets | |

**User's choice:** 5 tiers (Recommended)

### Rate values

| Option | Description | Selected |
|--------|-------------|----------|
| Realistic THB ranges | Base rates modeled on Thai Express pricing (~50-500 THB) | ✓ |
| Simple multiplier grid | Start at round number, fixed multipliers | |
| You decide | Claude picks reasonable rates | |

**User's choice:** Realistic THB ranges (Recommended)

### CSV commitment

| Option | Description | Selected |
|--------|-------------|----------|
| Commit CSV | Generate once, commit to data/raw/ for reproducibility | ✓ |
| Generate on setup | Run script during setup, don't commit | |

**User's choice:** Commit CSV (Recommended)

### Extra columns

| Option | Description | Selected |
|--------|-------------|----------|
| Just the basics | shipping_type, zone, weight_min_kg, weight_max_kg, base_rate_thb | ✓ |
| Add currency + effective_date | Include currency and date metadata | |
| You decide | Claude adds what makes sense | |

**User's choice:** Just the basics (Recommended)

---

## Fuel Price Sourcing

### EPPO source

| Option | Description | Selected |
|--------|-------------|----------|
| Web scrape EPPO site | Scrape from EPPO's public price board | ✓ |
| PTT price board API | More structured but less official | |
| Both with fallback | Try EPPO first, fall back to PTT | |

**User's choice:** Web scrape EPPO site (Recommended)

### History depth

| Option | Description | Selected |
|--------|-------------|----------|
| 6 months | ~180 data points of daily diesel prices | ✓ |
| 1 year | ~365 data points | |
| 30 days only | Minimal history | |

**User's choice:** 6 months (Recommended)

### Fallback strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Ship a seed CSV | Pre-scraped CSV committed as fallback | ✓ |
| Generate synthetic data | Create realistic data if scrape fails | |
| Fail with clear error | No pipeline fallback | |

**User's choice:** Ship a seed CSV (Recommended)

### CSV format

| Option | Description | Selected |
|--------|-------------|----------|
| date, diesel_b7_price, source | Minimal columns for SQLite loading | ✓ |
| Include multiple fuel types | Multiple fuel type columns | |
| You decide | Claude picks columns | |

**User's choice:** date, diesel_b7_price, source (Recommended)

---

## Surcharge Formula Implementation

### Configuration approach

| Option | Description | Selected |
|--------|-------------|----------|
| Environment variables | BASELINE_DIESEL_PRICE, SURCHARGE_CAP, SURCHARGE_FLOOR in .env | ✓ |
| Python config module | backend/config.py with defaults | |
| Both (config + env override) | Config module with env var overrides | |

**User's choice:** Environment variables (Recommended)

### Function location

| Option | Description | Selected |
|--------|-------------|----------|
| Own module | backend/agent/tools/calculate_surcharge.py | ✓ |
| Shared utils module | backend/utils/surcharge.py | |
| You decide | Claude picks location | |

**User's choice:** Own module (Recommended)

### Error handling

| Option | Description | Selected |
|--------|-------------|----------|
| Raise ValueError | Invalid inputs raise ValueError with descriptive message | ✓ |
| Return error dict | Return {error: str} instead of raising | |
| You decide | Claude picks approach | |

**User's choice:** Raise ValueError (Recommended)

### Test strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Known input/output pairs | Hand-calculated test cases for each shipping type | ✓ |
| Property-based tests | Random inputs with invariant checks | |
| Both | Known pairs + property tests | |

**User's choice:** Known input/output pairs (Recommended)

---

## Claude's Discretion

- Zone-province mapping granularity
- Exact rate values within realistic ranges
- EPPO scraping implementation details
- AgentState/Pydantic model field naming
- Test file organization

## Deferred Ideas

None -- discussion stayed within phase scope
