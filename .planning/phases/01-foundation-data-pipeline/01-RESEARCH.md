# Phase 1: Foundation & Data Pipeline - Research

**Researched:** 2026-04-04
**Domain:** Python data pipeline, SQLite seeding, Pydantic models, surcharge calculation
**Confidence:** HIGH

## Summary

Phase 1 is a greenfield Python phase with no existing code beyond empty `__init__.py` files and `.gitkeep` placeholders. The work divides into four clear areas: (1) data generation and seeding scripts that produce CSV files and load them into SQLite, (2) an EPPO fuel price fetcher that scrapes Thailand's energy statistics website, (3) a pure-function surcharge calculator with the formula specified in `docs/architecture.md`, and (4) foundational type definitions (AgentState TypedDict, Pydantic input/output models) that every downstream phase imports.

The critical dependency is Python 3.11+ -- the system currently only has Python 3.9.6 (macOS system Python). A virtual environment with Python 3.11+ must be created as the first task. All other dependencies (pydantic, pandas, requests, beautifulsoup4, pytest) are standard PyPI packages with no compatibility concerns.

EPPO does not provide a public API for diesel prices. Data must be scraped from Excel files hosted on `eppo.go.th` or from their Petroleum Price Statistic pages. The decision to ship a pre-scraped seed CSV (D-07) is critical -- it ensures the project works offline and avoids scraping fragility during demos.

**Primary recommendation:** Set up the Python 3.11+ venv and `requirements.txt` first, then build scripts in dependency order: generate_rate_table.py -> seed_database.py -> fetch_fuel_prices.py. Define all Pydantic/TypedDict models before the surcharge function so it can use typed inputs/outputs from the start.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 5 weight tiers: 0-5kg, 5-10kg, 10-20kg, 20-50kg, 50+kg
- **D-02:** Realistic THB base rates modeled on Thai Express pricing (~50-500 THB), increasing by zone distance and weight, with documented assumptions in the generation script
- **D-03:** Minimal columns: shipping_type, zone, weight_min_kg, weight_max_kg, base_rate_thb
- **D-04:** Generated CSV committed to data/raw/express_rate_table.csv for reproducibility -- anyone cloning gets the same data
- **D-05:** Web scrape EPPO public price board for diesel B7 prices
- **D-06:** Fetch 6 months of daily price history (~180 data points)
- **D-07:** Ship a pre-scraped seed CSV in data/raw/eppo_diesel_prices.csv as fallback -- project always works without internet
- **D-08:** CSV columns: date (YYYY-MM-DD), diesel_b7_price (THB/L), source (eppo/ptt)
- **D-09:** Constants configured via environment variables: BASELINE_DIESEL_PRICE, SURCHARGE_CAP, SURCHARGE_FLOOR (matches existing .env.example pattern)
- **D-10:** Pure function lives in backend/agent/tools/calculate_surcharge.py -- Phase 2 wraps it as a LangGraph tool
- **D-11:** Invalid inputs (bad shipping_type, missing data) raise ValueError with descriptive messages -- callers handle errors
- **D-12:** Tests use hand-calculated known input/output pairs for each shipping type, including cap/floor trigger cases and traffic adjustment (Bounce only)

### Claude's Discretion
- Zone-province mapping granularity (province-level vs district-level for central-1, central-2, central-3)
- Exact rate values within realistic THB ranges
- EPPO scraping implementation details (library choice, parsing approach)
- AgentState and Pydantic model field naming beyond what's in docs/architecture.md
- Test file organization and pytest configuration

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | Data pipeline seeds SQLite database with rate table (3 shipping types, 3 zones, multiple weight tiers) | Standard stack (pandas, sqlite3), seed_database.py pattern, rate table schema |
| DATA-02 | fetch_fuel_prices.py fetches historical diesel prices from EPPO and stores in data/raw/ | EPPO scraping approach (requests + pandas read_excel), fallback CSV pattern |
| DATA-03 | generate_rate_table.py creates simulated Express rate table with documented assumptions | Pure Python/pandas CSV generation with D-01 through D-04 constraints |
| DATA-04 | seed_database.py loads CSVs into SQLite (data/express.db) | pandas to_sql pattern, SQLite schema creation |
| DATA-05 | Zone definitions configured for Central Region (central-1, central-2, central-3) with province mappings | Zone mapping dict pattern, province-level granularity recommendation |
| CALC-01 | Three shipping types with distinct multipliers: Bounce (1.0x), Retail Standard (0.5x), Retail Fast (0.8x) | Surcharge formula from architecture.md, multiplier constants |
| CALC-02 | Surcharge formula uses configurable baseline diesel price (default 29.94 THB/L) | Environment variable loading pattern (D-09) |
| CALC-03 | Traffic adjustment applied for Bounce shipments only (2% per severity level, 1-5 scale) | Traffic adjustment logic in surcharge function |
| CALC-04 | Surcharge cap at 15% maximum, floor at -5% minimum (configurable via env) | Cap/floor clamping pattern with env config |
| TOOL-06 | All tools use structured Pydantic input/output models for deterministic, testable responses | Pydantic BaseModel patterns for tool I/O |
| ORCH-06 | Agent state schema (AgentState TypedDict) manages messages, fuel_data, route_data, shipping_type, weight_kg, surcharge_result, reasoning_trace, next_step | TypedDict definition from architecture.md |
| DOC-03 | .env.example with all required API key placeholders | Existing .env.example already has surcharge config -- needs verification of completeness |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Budget:** Free-tier APIs only -- Gemini Flash, Google Maps ($200/mo credit), EPPO public data
- **LLM:** Gemini 2.0 Flash only -- no paid model APIs
- **Repo structure:** Must follow brief-mandated layout (agent/, app/, data/, docs/, notebooks/)
- **Secrets:** Never commit .env -- .env.example required, violations affect grade
- **Git practice:** Descriptive commit messages, feature branches, IT Lead holds majority of commits
- **Python conventions:** PEP 8, Black formatting (88 char lines), Google-style docstrings, type hints on all functions
- **Naming:** snake_case for files/functions, PascalCase for classes/TypedDict, UPPER_CASE for constants
- **File locations:** Tools in `backend/agent/tools/`, state in `backend/agent/state.py`, scripts in `data/scripts/`
- **GSD Workflow:** All changes through GSD commands

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 | Input/output model validation for tools | Industry standard for Python data validation; required by TOOL-06 |
| pandas | 2.3.3 | CSV processing, rate table generation, Excel parsing | Standard data manipulation; already referenced in project docs |
| pytest | 8.4.2 | Unit testing for surcharge formula and models | Python testing standard; no test infra exists yet |
| requests | 2.32.5 | HTTP client for EPPO scraping | Simple, reliable HTTP; already installed |
| beautifulsoup4 | 4.14.3 | HTML/XML parsing for EPPO data extraction | Standard scraping parser; already installed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| openpyxl | 3.1.5 | Excel file reading (EPPO publishes .xls/.xlsx) | Required by pandas.read_excel for .xlsx files |
| xlrd | 2.0.1 | Legacy .xls file reading | Only if EPPO files are .xls format (older Excel) |
| python-dotenv | 1.1.1 | Load .env for surcharge config constants | Development convenience; env vars in production |
| langgraph | 0.6.11 | Import BaseMessage type for AgentState typing | Only for type reference; not used at runtime in Phase 1 |
| langchain-core | 0.3.83 | Provides BaseMessage used in AgentState.messages | Type dependency for AgentState definition |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| requests + bs4 | httpx | httpx is async-native but overkill for batch scraping scripts |
| pandas read_excel | openpyxl directly | pandas wraps openpyxl and adds DataFrame convenience |
| python-dotenv | os.environ only | dotenv is more developer-friendly for local dev |

**Installation:**
```bash
# Phase 1 requirements (add to requirements.txt)
pip install pydantic==2.12.5 pandas==2.3.3 pytest==8.4.2 requests==2.32.5 beautifulsoup4==4.14.3 openpyxl==3.1.5 python-dotenv==1.1.1 langgraph==0.6.11
```

**Note on langgraph:** Including langgraph in Phase 1 requirements is needed solely to import `langchain_core.messages.BaseMessage` for the `AgentState` TypedDict. The graph itself is not built until Phase 2-3. Alternatively, type the `messages` field as `list[dict]` in Phase 1 and upgrade to `list[BaseMessage]` in Phase 2 -- this avoids pulling in the full LangGraph dependency tree early. Recommend the latter approach to keep Phase 1 lightweight.

**Version verification:** All versions confirmed via `pip3 index versions` on 2026-04-04.

## Architecture Patterns

### Recommended Project Structure
```
data/
  raw/
    express_rate_table.csv      # Generated, committed (D-04)
    eppo_diesel_prices.csv      # Pre-scraped seed (D-07)
  scripts/
    generate_rate_table.py      # Creates rate table CSV (DATA-03)
    fetch_fuel_prices.py        # Scrapes EPPO diesel prices (DATA-02)
    seed_database.py            # Loads CSVs into SQLite (DATA-04)
  express.db                    # SQLite database (gitignored, built from scripts)
backend/
  agent/
    state.py                    # AgentState TypedDict (ORCH-06)
    tools/
      __init__.py
      calculate_surcharge.py    # Pure surcharge function (D-10)
      models.py                 # Pydantic input/output models (TOOL-06)
  config.py                     # Environment variable loading
  tests/
    __init__.py
    test_surcharge.py           # Surcharge formula tests (D-12)
    test_models.py              # Pydantic model validation tests
    test_seed.py                # Database seeding smoke tests
.env.example                    # API key placeholders (DOC-03)
requirements.txt                # Python dependencies
```

### Pattern 1: Pure Surcharge Function
**What:** Surcharge calculation as a standalone pure function with no side effects
**When to use:** Any calculation that Phase 2 will wrap as a LangGraph tool
**Example:**
```python
# backend/agent/tools/calculate_surcharge.py
# Source: docs/architecture.md surcharge formula spec

from backend.agent.tools.models import SurchargeInput, SurchargeResult
import os

# Constants with env var overrides
BASELINE_DIESEL_PRICE = float(os.environ.get("BASELINE_DIESEL_PRICE", "29.94"))
SURCHARGE_CAP = float(os.environ.get("SURCHARGE_CAP", "0.15"))
SURCHARGE_FLOOR = float(os.environ.get("SURCHARGE_FLOOR", "-0.05"))

SHIPPING_MULTIPLIERS = {
    "bounce": 1.0,
    "retail_standard": 0.5,
    "retail_fast": 0.8,
}

def calculate_surcharge(
    base_rate: float,
    current_diesel_price: float,
    shipping_type: str,
    traffic_severity: int = 1,
) -> SurchargeResult:
    """Calculate fuel surcharge for a shipment.

    Args:
        base_rate: Base shipping rate in THB from rate table.
        current_diesel_price: Current diesel B7 price in THB/L.
        shipping_type: One of "bounce", "retail_standard", "retail_fast".
        traffic_severity: Traffic severity 1-5 (only affects bounce).

    Returns:
        SurchargeResult with surcharge_pct, surcharge_amount, total, capped.

    Raises:
        ValueError: If shipping_type is invalid or inputs are out of range.
    """
    if shipping_type not in SHIPPING_MULTIPLIERS:
        raise ValueError(
            f"Invalid shipping_type: '{shipping_type}'. "
            f"Must be one of: {list(SHIPPING_MULTIPLIERS.keys())}"
        )
    if base_rate <= 0:
        raise ValueError(f"base_rate must be positive, got {base_rate}")
    if not 1 <= traffic_severity <= 5:
        raise ValueError(f"traffic_severity must be 1-5, got {traffic_severity}")

    fuel_delta_pct = (current_diesel_price - BASELINE_DIESEL_PRICE) / BASELINE_DIESEL_PRICE
    surcharge_pct = fuel_delta_pct * SHIPPING_MULTIPLIERS[shipping_type]

    # Traffic adjustment: Bounce only, 2% per severity level
    if shipping_type == "bounce":
        surcharge_pct += traffic_severity * 0.02

    # Apply cap and floor
    capped = False
    if surcharge_pct > SURCHARGE_CAP:
        surcharge_pct = SURCHARGE_CAP
        capped = True
    elif surcharge_pct < SURCHARGE_FLOOR:
        surcharge_pct = SURCHARGE_FLOOR
        capped = True

    surcharge_amount = base_rate * surcharge_pct
    total = base_rate + surcharge_amount

    return SurchargeResult(
        surcharge_pct=round(surcharge_pct, 4),
        surcharge_amount=round(surcharge_amount, 2),
        total=round(total, 2),
        capped=capped,
    )
```

### Pattern 2: Pydantic Tool Models
**What:** Structured input/output models for all agent tools
**When to use:** Every tool needs typed, validated I/O (TOOL-06)
**Example:**
```python
# backend/agent/tools/models.py
from pydantic import BaseModel, Field

class SurchargeInput(BaseModel):
    """Input for surcharge calculation tool."""
    base_rate: float = Field(gt=0, description="Base shipping rate in THB")
    current_diesel_price: float = Field(gt=0, description="Current diesel B7 price THB/L")
    shipping_type: str = Field(description="bounce | retail_standard | retail_fast")
    traffic_severity: int = Field(default=1, ge=1, le=5, description="Traffic 1-5 scale")

class SurchargeResult(BaseModel):
    """Output from surcharge calculation."""
    surcharge_pct: float = Field(description="Surcharge percentage (e.g., 0.05 = 5%)")
    surcharge_amount: float = Field(description="Surcharge amount in THB")
    total: float = Field(description="Base rate + surcharge in THB")
    capped: bool = Field(description="Whether cap or floor was applied")

class FuelData(BaseModel):
    """Fuel price data from EPPO/PTT."""
    price: float = Field(description="Current diesel B7 price in THB/L")
    date: str = Field(description="Price date YYYY-MM-DD")
    unit: str = Field(default="THB/L")
    source: str = Field(description="Data source: eppo or ptt")
    baseline: float = Field(description="Baseline diesel price for comparison")
    delta_pct: float = Field(description="Percentage change from baseline")

class RouteData(BaseModel):
    """Route calculation output."""
    origin: str
    destination: str
    distance_km: float
    duration_min: int
    traffic_severity: int = Field(ge=1, le=5)
    zone: str = Field(description="central-1, central-2, or central-3")

class RateResult(BaseModel):
    """Rate table lookup output."""
    base_rate: float = Field(description="Base rate in THB")
    currency: str = Field(default="THB")
    rate_tier: str = Field(description="Weight tier description")
```

### Pattern 3: AgentState TypedDict
**What:** Central state schema for the LangGraph orchestrator
**When to use:** Defined once in Phase 1, imported by every agent node
**Example:**
```python
# backend/agent/state.py
# Source: docs/architecture.md Agent State section
from typing import TypedDict

class AgentState(TypedDict):
    """Central state for the LangGraph agent graph.

    All agent nodes read from and write to this state dict.
    Fields use snake_case per project conventions.
    """
    messages: list[dict]                   # Conversation history (upgrade to BaseMessage in Phase 2)
    fuel_data: dict | None                 # FuelData as dict, or None if not fetched
    route_data: dict | None                # RouteData as dict, or None if not fetched
    shipping_type: str | None              # "bounce" | "retail_standard" | "retail_fast"
    weight_kg: float | None                # Shipment weight in kg
    surcharge_result: dict | None          # SurchargeResult as dict, or None
    reasoning_trace: list[dict]            # Steps taken by agents for transparency
    next_step: str                         # Routing key for conditional edges
```

### Pattern 4: CSV-to-SQLite Seeding
**What:** Load CSV files into SQLite with proper schema
**When to use:** seed_database.py (DATA-04)
**Example:**
```python
# data/scripts/seed_database.py
import pandas as pd
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent
DB_PATH = DATA_DIR / "express.db"
RAW_DIR = DATA_DIR / "raw"

def seed_rate_table(conn: sqlite3.Connection) -> int:
    """Load rate table CSV into SQLite."""
    df = pd.read_csv(RAW_DIR / "express_rate_table.csv")
    df.to_sql("rate_table", conn, if_exists="replace", index=False)
    return len(df)

def seed_fuel_prices(conn: sqlite3.Connection) -> int:
    """Load fuel price CSV into SQLite."""
    df = pd.read_csv(RAW_DIR / "eppo_diesel_prices.csv")
    df.to_sql("fuel_prices", conn, if_exists="replace", index=False)
    return len(df)

def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        rate_count = seed_rate_table(conn)
        fuel_count = seed_fuel_prices(conn)
        conn.commit()
        print(f"Seeded {rate_count} rate table rows, {fuel_count} fuel price rows")
        print(f"Database: {DB_PATH}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
```

### Anti-Patterns to Avoid
- **Hardcoding surcharge constants:** Use env vars as specified in D-09. Never embed 29.94 as a literal in calculation code.
- **Raw dict returns from calculation functions:** Always return Pydantic models -- Phase 2 needs structured outputs (TOOL-06).
- **Mixing scraping logic with data processing:** Keep fetch_fuel_prices.py focused on I/O; parsing and CSV writing are separate concerns within the script.
- **Using `dict` type for AgentState fields:** Use `dict | None` with clear comments about which Pydantic model the dict represents. This enables type safety improvements in Phase 2.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSV parsing | Custom file reader | `pandas.read_csv` | Handles encoding, dtypes, missing values |
| Excel reading | Manual binary parsing | `pandas.read_excel` + openpyxl | EPPO files are Excel format |
| Data validation | if/else chains | Pydantic `BaseModel` with `Field` constraints | Automatic error messages, serialization |
| SQLite table creation | Manual CREATE TABLE | `pandas.DataFrame.to_sql` | Schema inferred from DataFrame dtypes |
| Environment variables | Custom config parser | `python-dotenv` + `os.environ` | Industry standard, zero learning curve |
| HTML scraping | Regex on HTML | BeautifulSoup4 | Handles malformed HTML, navigable tree |

**Key insight:** Phase 1 is infrastructure -- every shortcut or hand-rolled solution becomes technical debt that 4 subsequent phases inherit. Using standard libraries here means downstream phases can trust data formats.

## Common Pitfalls

### Pitfall 1: Python Version Mismatch
**What goes wrong:** Code uses `dict | None` union syntax (3.10+) or `TypedDict` improvements (3.11+) but runs on system Python 3.9.
**Why it happens:** macOS ships Python 3.9.6; developers forget to activate venv.
**How to avoid:** First task must create `.venv` with Python 3.11+. Add a version check at the top of key scripts. Document `python3.11 -m venv .venv` in setup instructions.
**Warning signs:** `SyntaxError` on `X | Y` type unions, missing `typing` features.

### Pitfall 2: EPPO Website Structure Changes
**What goes wrong:** Scraper breaks because EPPO changes their page layout or file URLs.
**Why it happens:** Government websites update without notice; no stable API exists.
**How to avoid:** Ship pre-scraped seed CSV (D-07). Make the scraper best-effort with graceful fallback. Use try/except with clear error messages. Test with the seed CSV, not live scraping.
**Warning signs:** HTTP 403, empty dataframes, changed column names in Excel files.

### Pitfall 3: Floating Point Precision in Surcharge Calculation
**What goes wrong:** `surcharge_pct` of 0.14999999999 instead of 0.15 causes capping logic to behave unexpectedly.
**Why it happens:** IEEE 754 floating point arithmetic.
**How to avoid:** Use `round()` on final outputs (shown in code example). Compare with small epsilon if needed for cap boundary. Test exact cap/floor boundary cases (D-12).
**Warning signs:** Tests fail intermittently on exact boundary values.

### Pitfall 4: SQLite File Path Issues
**What goes wrong:** `seed_database.py` creates `express.db` in wrong directory when run from different working directories.
**Why it happens:** Relative paths resolve against `os.getcwd()`, not script location.
**How to avoid:** Use `Path(__file__).parent` to resolve paths relative to script file. Set `DATABASE_PATH` env var as backup.
**Warning signs:** "No such table" errors in Phase 2 when agents try to query the DB.

### Pitfall 5: Rate Table Weight Tier Gaps or Overlaps
**What goes wrong:** A weight of exactly 5.0kg matches two tiers, or no tier at all.
**Why it happens:** Inclusive vs exclusive boundary confusion in weight_min_kg/weight_max_kg.
**How to avoid:** Use exclusive upper bound: 0-5 means weight_min=0, weight_max=5; 5-10 means weight_min=5, weight_max=10. Document convention. The lookup_rate tool (Phase 2) should use `weight >= min AND weight < max` (except last tier which is `>=`).
**Warning signs:** Duplicate or missing results in rate lookups.

### Pitfall 6: .env.example Drift from Actual Requirements
**What goes wrong:** New env vars added in code but not in .env.example, causing setup failures for teammates.
**Why it happens:** .env.example is treated as "set and forget" documentation.
**How to avoid:** Review .env.example as part of every phase completion. The existing file already has surcharge config -- verify it stays in sync.
**Warning signs:** Teammates get KeyError on env vars that work on your machine.

## Code Examples

### EPPO Fuel Price Fetching
```python
# data/scripts/fetch_fuel_prices.py
# Approach: Download EPPO Excel files, parse diesel B7 prices, save as CSV

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

RAW_DIR = Path(__file__).parent.parent / "raw"
OUTPUT_FILE = RAW_DIR / "eppo_diesel_prices.csv"
SEED_FILE = RAW_DIR / "eppo_diesel_prices_seed.csv"  # Fallback

# EPPO Petroleum Price Statistics - Weekly retail prices
# URL pattern from https://www.eppo.go.th/index.php/en/en-energystatistics/petroleumprice-statistic
EPPO_WEEKLY_URL = "https://www.eppo.go.th/epposite/images/Energy-Statistics/energyinformation/Energy_Statistics/Petroleum_Prices/P09.xls"

def fetch_from_eppo() -> pd.DataFrame:
    """Fetch diesel B7 prices from EPPO Excel file.

    Returns:
        DataFrame with columns: date, diesel_b7_price, source
    """
    response = requests.get(EPPO_WEEKLY_URL, timeout=30)
    response.raise_for_status()

    # Parse the Excel file -- exact sheet/column depends on EPPO format
    # This needs adjustment based on actual file structure
    df = pd.read_excel(
        response.content,
        sheet_name=0,
        engine="xlrd",  # .xls format
    )

    # Extract and clean diesel B7 column
    # (Column names and structure will need adjustment for actual EPPO format)
    # ...

    return df

def main():
    """Fetch EPPO prices with fallback to seed CSV."""
    try:
        df = fetch_from_eppo()
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"Fetched {len(df)} price records to {OUTPUT_FILE}")
    except Exception as e:
        print(f"EPPO fetch failed: {e}")
        if SEED_FILE.exists():
            print(f"Using seed CSV: {SEED_FILE}")
            # Copy seed as the active file
        else:
            print("No seed CSV available. Create manually.")
            raise

if __name__ == "__main__":
    main()
```

### Rate Table Generation
```python
# data/scripts/generate_rate_table.py
# Generates Express rate table CSV with documented assumptions (D-02, D-04)

import pandas as pd
from pathlib import Path

OUTPUT_FILE = Path(__file__).parent.parent / "raw" / "express_rate_table.csv"

# Rate table assumptions (D-01, D-02):
# - 3 shipping types x 3 zones x 5 weight tiers = 45 rows
# - Prices increase by zone distance and weight tier
# - Modeled on Thai Express domestic pricing (~50-500 THB range)

SHIPPING_TYPES = ["bounce", "retail_standard", "retail_fast"]
ZONES = ["central-1", "central-2", "central-3"]
WEIGHT_TIERS = [
    (0, 5),      # 0-5 kg
    (5, 10),     # 5-10 kg
    (10, 20),    # 10-20 kg
    (20, 50),    # 20-50 kg
    (50, 9999),  # 50+ kg (use large upper bound)
]

# Base rates by (shipping_type, zone) -- cheapest tier
# Assumptions documented inline:
# - Bounce (B2B bulk): lowest per-kg rate, distance-sensitive
# - Retail Standard: mid-range, zone-based flat-ish
# - Retail Fast: premium, same/next-day
BASE_RATES = {
    ("bounce", "central-1"): [50, 85, 140, 280, 450],
    ("bounce", "central-2"): [65, 110, 175, 340, 500],
    ("bounce", "central-3"): [80, 130, 210, 400, 550],
    ("retail_standard", "central-1"): [55, 90, 150, 300, 480],
    ("retail_standard", "central-2"): [70, 115, 185, 360, 520],
    ("retail_standard", "central-3"): [90, 140, 220, 420, 580],
    ("retail_fast", "central-1"): [75, 120, 190, 370, 550],
    ("retail_fast", "central-2"): [95, 150, 230, 430, 600],
    ("retail_fast", "central-3"): [120, 180, 270, 500, 650],
}

def generate() -> pd.DataFrame:
    rows = []
    for st in SHIPPING_TYPES:
        for zone in ZONES:
            rates = BASE_RATES[(st, zone)]
            for i, (wmin, wmax) in enumerate(WEIGHT_TIERS):
                rows.append({
                    "shipping_type": st,
                    "zone": zone,
                    "weight_min_kg": wmin,
                    "weight_max_kg": wmax,
                    "base_rate_thb": rates[i],
                })
    return pd.DataFrame(rows)

def main():
    df = generate()
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Generated {len(df)} rate table rows to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
```

### Zone-Province Mapping
```python
# Recommendation: Province-level granularity for Central Region
# Source: docs/architecture.md zone definitions

ZONE_PROVINCES = {
    "central-1": [
        "Bangkok",           # กรุงเทพมหานคร (inner areas)
        "Nonthaburi",        # นนทบุรี
        "Samut Prakan",      # สมุทรปราการ (inner districts)
    ],
    "central-2": [
        "Pathum Thani",      # ปทุมธานี
        "Nakhon Pathom",     # นครปฐม (inner)
        "Samut Sakhon",      # สมุทรสาคร
    ],
    "central-3": [
        "Ayutthaya",         # พระนครศรีอยุธยา
        "Ang Thong",         # อ่างทอง
        "Saraburi",          # สระบุรี
        "Suphan Buri",       # สุพรรณบุรี
    ],
}
```

**Note on zone mapping:** Province-level is recommended over district-level because (1) Google Maps API returns province-level geocoding reliably, (2) the Route Agent in Phase 2 needs a simple lookup from destination to zone, and (3) district-level adds complexity without grading value.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 validators | Pydantic v2 `model_validator`, `field_validator` | 2023 (v2 release) | v2 is 5-17x faster; use v2 syntax exclusively |
| `typing.Optional[X]` | `X \| None` | Python 3.10+ | Cleaner syntax; requires 3.10+ |
| `typing.TypedDict` basic | `typing.TypedDict` with `Required`/`NotRequired` | Python 3.11 | Better state schema expressiveness |
| Manual CSV-to-DB loading | `pandas.DataFrame.to_sql()` | Stable pattern | One-liner replaces manual INSERT loops |
| `langgraph` pre-0.4 state | `langgraph` 0.4+ `StateGraph` with annotations | 2025 | Phase 1 defines TypedDict; Phase 2-3 uses StateGraph |

**Deprecated/outdated:**
- Pydantic v1 `validator` decorator: Use v2 `field_validator` instead
- `from typing import Optional, Union, Dict, List`: Use builtin `dict`, `list`, `X | None` (Python 3.10+)

## Open Questions

1. **EPPO Excel File Format**
   - What we know: EPPO publishes weekly retail petroleum prices as Excel files (P09.xls). Diesel B7 is one of many fuel types listed.
   - What's unclear: Exact column names, sheet structure, whether date format is Thai Buddhist calendar (BE) or Gregorian. The .xls format suggests xlrd engine.
   - Recommendation: Download one file manually during implementation, inspect structure, then code the parser. The seed CSV (D-07) derisks this entirely -- if scraping is fragile, the seed CSV ensures the project always works.

2. **AgentState `messages` Type in Phase 1**
   - What we know: Architecture.md specifies `list[BaseMessage]` which requires `langchain-core` import.
   - What's unclear: Whether to pull in the full langchain-core dependency in Phase 1 just for typing.
   - Recommendation: Use `list[dict]` in Phase 1 with a comment noting the Phase 2 upgrade path. This keeps Phase 1 dependencies minimal and avoids importing LangGraph packages before they are needed.

3. **Weight Tier Upper Bound for 50+ kg**
   - What we know: D-01 specifies "50+kg" as the final tier.
   - What's unclear: What `weight_max_kg` should be for the unbounded tier.
   - Recommendation: Use 9999 as sentinel value. Document in generate_rate_table.py. The lookup_rate tool (Phase 2) should treat `weight_max_kg >= 9999` as unbounded.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All Python code (type syntax, TypedDict) | -- | 3.9.6 (system) | Install via pyenv or Homebrew |
| pip | Package installation | Yes | 23.2.1 | -- |
| SQLite | Database | Yes | 3.43.2 | -- |
| Node.js | Not needed in Phase 1 | Yes | 25.9.0 | -- |
| Internet access | EPPO scraping (DATA-02) | Yes | -- | Seed CSV fallback (D-07) |

**Missing dependencies with no fallback:**
- **Python 3.11+**: System Python is 3.9.6. Must install Python 3.11+ before any Phase 1 work. Use `brew install python@3.12` or `pyenv install 3.12`. This is a blocking prerequisite.

**Missing dependencies with fallback:**
- None -- all other dependencies are installable via pip once Python 3.11+ is available.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | None -- needs creation (Wave 0) |
| Quick run command | `python -m pytest backend/tests/ -x -q` |
| Full suite command | `python -m pytest backend/tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CALC-01 | Three shipping types with distinct multipliers | unit | `python -m pytest backend/tests/test_surcharge.py::test_shipping_multipliers -x` | Wave 0 |
| CALC-02 | Configurable baseline diesel price | unit | `python -m pytest backend/tests/test_surcharge.py::test_baseline_config -x` | Wave 0 |
| CALC-03 | Traffic adjustment for Bounce only | unit | `python -m pytest backend/tests/test_surcharge.py::test_traffic_adjustment -x` | Wave 0 |
| CALC-04 | Cap at 15%, floor at -5% | unit | `python -m pytest backend/tests/test_surcharge.py::test_cap_floor -x` | Wave 0 |
| TOOL-06 | Pydantic models validate correctly | unit | `python -m pytest backend/tests/test_models.py -x` | Wave 0 |
| ORCH-06 | AgentState TypedDict importable | unit | `python -m pytest backend/tests/test_state.py -x` | Wave 0 |
| DATA-01 | Rate table has 3 types x 3 zones x 5 tiers | smoke | `python -m pytest backend/tests/test_seed.py::test_rate_table_completeness -x` | Wave 0 |
| DATA-03 | generate_rate_table produces valid CSV | smoke | `python -m pytest backend/tests/test_seed.py::test_generate_rate_table -x` | Wave 0 |
| DATA-04 | seed_database loads into SQLite | smoke | `python -m pytest backend/tests/test_seed.py::test_seed_database -x` | Wave 0 |
| DATA-02 | fetch_fuel_prices runs (with seed fallback) | smoke | `python -m pytest backend/tests/test_seed.py::test_fuel_prices_fallback -x` | Wave 0 |
| DATA-05 | Zone definitions complete | unit | `python -m pytest backend/tests/test_models.py::test_zone_definitions -x` | Wave 0 |
| DOC-03 | .env.example has all placeholders | manual-only | Visual check | -- |

### Sampling Rate
- **Per task commit:** `python -m pytest backend/tests/ -x -q`
- **Per wave merge:** `python -m pytest backend/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/__init__.py` -- package init
- [ ] `backend/tests/test_surcharge.py` -- covers CALC-01, CALC-02, CALC-03, CALC-04
- [ ] `backend/tests/test_models.py` -- covers TOOL-06, DATA-05
- [ ] `backend/tests/test_state.py` -- covers ORCH-06
- [ ] `backend/tests/test_seed.py` -- covers DATA-01, DATA-02, DATA-03, DATA-04
- [ ] `backend/tests/conftest.py` -- shared fixtures (tmp database, test env vars)
- [ ] `requirements.txt` -- includes pytest
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest]` -- test config with paths

## Sources

### Primary (HIGH confidence)
- `docs/architecture.md` -- AgentState schema, surcharge formula, zone definitions, tool specs
- `.env.example` -- Existing surcharge config defaults verified
- `pip3 index versions` -- All package versions verified on 2026-04-04
- [EPPO Petroleum Price Statistic](https://www.eppo.go.th/index.php/en/en-energystatistics/petroleumprice-statistic) -- Excel download URLs, data format

### Secondary (MEDIUM confidence)
- [EPPO Data Catalog](https://catalog.eppo.go.th/en/group/petroleum-price) -- Alternative data portal (returned 403, may require Thai IP or session)
- Pydantic v2 documentation -- Model validation patterns (well-known, stable API)

### Tertiary (LOW confidence)
- EPPO Excel file internal structure -- Column names and sheet layout unknown until downloaded; the seed CSV approach (D-07) mitigates this risk entirely

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages verified via pip index, well-known Python ecosystem
- Architecture: HIGH -- patterns directly from docs/architecture.md and CONTEXT.md locked decisions
- Pitfalls: HIGH -- based on concrete environment findings (Python 3.9 system version) and standard Python development experience
- EPPO scraping: MEDIUM -- website exists and Excel files are accessible, but exact file format is unverified

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable domain -- Python packages, SQLite, data formats unlikely to change)
