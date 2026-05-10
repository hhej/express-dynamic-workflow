"""Environment-based configuration for surcharge calculation (D-09)."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present (development convenience)
load_dotenv()


_STATIC_BASELINE_FALLBACK: float = 29.94  # historical pre-2024 anchor


def _compute_rolling_baseline(window_days: int = 90) -> float:
    """Phase 999.9 calibration fix: rolling-mean baseline from EPPO CSV.

    The original static 29.94 was a pre-2024 anchor; with 2026 prices
    near 40 THB/L, every query tripped the 15% surcharge cap and the
    agent's reasoning collapsed into a flat "cap applied". A 90-day
    rolling mean tracks "recent normal" so the surcharge varies with
    actual fuel signal instead of always saturating.

    Falls back to ``_STATIC_BASELINE_FALLBACK`` if the CSV is missing,
    empty, or unreadable — so first-run / fresh-checkout flows still
    boot with a sensible number.

    Restart-to-pick-up semantics: this runs once at module import.
    Mirrors the hubs.py / calculate_route.py one-shot load pattern.
    """
    csv_path = (
        Path(__file__).resolve().parent.parent
        / "data" / "raw" / "eppo_diesel_prices.csv"
    )
    try:
        import pandas as pd

        df = pd.read_csv(csv_path, parse_dates=["date"])
        if "diesel_b7_price" not in df.columns or df.empty:
            return _STATIC_BASELINE_FALLBACK
        cutoff = df["date"].max() - pd.Timedelta(days=window_days)
        recent = df[df["date"] >= cutoff]
        if recent.empty:
            return _STATIC_BASELINE_FALLBACK
        return round(float(recent["diesel_b7_price"].mean()), 2)
    except Exception:  # noqa: BLE001 — broad catch is intentional fallback
        return _STATIC_BASELINE_FALLBACK


# Surcharge formula constants. Explicit env override always wins (tests
# pin to 29.94 for hand-calculated formula cases; prod can pin to a
# specific value if EPPO data temporarily unreliable).
_baseline_env = os.environ.get("BASELINE_DIESEL_PRICE")
BASELINE_DIESEL_PRICE: float = (
    float(_baseline_env)
    if _baseline_env
    else _compute_rolling_baseline(90)
)
SURCHARGE_CAP: float = float(os.environ.get("SURCHARGE_CAP", "0.15"))
SURCHARGE_FLOOR: float = float(os.environ.get("SURCHARGE_FLOOR", "-0.05"))

# Shipping type multipliers (not env-configurable -- business logic)
SHIPPING_MULTIPLIERS: dict = {
    "bounce": 1.0,
    "retail_standard": 0.5,
    "retail_fast": 0.8,
}

# Database paths
DATABASE_PATH: str = os.environ.get("DATABASE_PATH", "data/express.db")
CHECKPOINT_PATH: str = os.environ.get("CHECKPOINT_PATH", "data/checkpoints.db")

# --- Phase 2: Tool & Agent Node configuration ---

# API keys (env-only; no defaults -- tests mock, dev reads from .env)
GOOGLE_MAPS_API_KEY: str = os.environ.get("GOOGLE_MAPS_API_KEY", "")
GOOGLE_API_KEY: str = os.environ.get("GOOGLE_API_KEY", "")

# Gemini model selection (ChatGoogleGenerativeAI target)
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# Fuel scrape timeout (httpx, seconds) -- D-04
FUEL_FETCH_TIMEOUT: float = float(os.environ.get("FUEL_FETCH_TIMEOUT", "10"))

# Route cache TTL (seconds) -- D-07
ROUTE_CACHE_TTL_SECONDS: int = int(
    os.environ.get("ROUTE_CACHE_TTL_SECONDS", "900")
)

# Traffic-ratio bucket thresholds for severity 2..5 -- D-06
# Comma-separated floats in env; parsed to list[float].
# ratio < bucket[0] -> severity 1; < bucket[1] -> 2; ... ; >= bucket[-1] -> 5
_traffic_raw = os.environ.get("TRAFFIC_RATIO_BUCKETS", "1.1,1.3,1.5,1.8")
TRAFFIC_RATIO_BUCKETS: list = [
    float(x.strip()) for x in _traffic_raw.split(",") if x.strip()
]

# --- Phase 3: Graph & API configuration ---

# Fuel data freshness TTL for D-12 cache-aware planner skip (seconds).
FUEL_DATA_TTL_SECONDS: int = int(
    os.environ.get("FUEL_DATA_TTL_SECONDS", "3600")
)

# D-04 max planner-loop iterations per request (1 init + ≤4 specialists + 1 respond).
PLANNER_MAX_ITERATIONS: int = int(
    os.environ.get("PLANNER_MAX_ITERATIONS", "6")
)

# --- Phase 5: Polish & Observability configuration ---

# D-04 HITL approval gate threshold (THB). When surcharge_result.total
# exceeds this value, the hitl_gate node calls interrupt() and waits
# for user approval. Calibrated against data/express.db rate distribution
# to gate ~9% of representative demo queries (RESEARCH §HITL Threshold
# Calibration). Override via env to demo more or fewer gate triggers.
HITL_TOTAL_THB_THRESHOLD: float = float(
    os.environ.get("HITL_TOTAL_THB_THRESHOLD", "500.0")
)

# D-12 Tavily search cache TTL (seconds). Default 30 min; matches
# Phase 2 D-07 ROUTE_CACHE_TTL_SECONDS pattern (env-driven, in-process
# TTLCache shared with backend/agent/tools/_cache.py).
SEARCH_CACHE_TTL_SECONDS: int = int(
    os.environ.get("SEARCH_CACHE_TTL_SECONDS", "1800")
)

# D-09 Tavily API key for search_fuel_news tool. Empty string -> tool
# raises RuntimeError on first invocation, caught by search_agent_node
# and converted to a warn trace entry (D-12 graceful failure).
TAVILY_API_KEY: str = os.environ.get("TAVILY_API_KEY", "")

# D-13 Langfuse Cloud free-tier credentials. ALL THREE must be set for
# the callback handler to attach; missing any one → graceful no-op so
# CLAUDE.md local-reproducibility constraint is preserved.
LANGFUSE_HOST: str = os.environ.get(
    "LANGFUSE_HOST", "https://cloud.langfuse.com"
)
LANGFUSE_PUBLIC_KEY: str = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY: str = os.environ.get("LANGFUSE_SECRET_KEY", "")

# --- Quick task 260509-utd: guardrail hardening configuration ---

# Per-turn tool-invocation cap (TOOL-09). Trips guard_input with
# category='cost_bombing' when the next specialist would push the count
# past this value. Default 6 matches PLANNER_MAX_ITERATIONS order of
# magnitude (3-5 happy-path tool calls + headroom for D-22 retries).
# Bump to 8 if any legitimate path trips it (RESEARCH Open Question 2).
MAX_TOOL_CALLS_PER_TURN: int = int(
    os.environ.get("MAX_TOOL_CALLS_PER_TURN", "6")
)

# When True, guard_input invokes Gemini on category='unclear' verdicts
# to second-guess the rules-first classifier. Default False per RESEARCH
# Open Question 1 — protects the 15 RPM Gemini budget. Flip to True
# right before the demo if the dry-run pack (backend/tests/adversarial_pack.txt)
# shows misses (Pitfall 2). Accepts the standard truthy strings.
GUARD_INPUT_USE_LLM_FALLBACK: bool = os.environ.get(
    "GUARD_INPUT_USE_LLM_FALLBACK", ""
).strip().lower() in {"1", "true", "yes", "on"}


# Quick 260509-eum: Cold-start fuel CSV refresh opt-out.
# When set to a truthy value ("1","true","yes","on", case-insensitive),
# the FastAPI lifespan skips the auto-refresh of
# data/raw/eppo_diesel_prices.csv. Default behavior in production:
# enabled (refresh runs in background on startup if CSV is stale).
# Tests set this to "1" to avoid network attempts.
EXPRESS_SKIP_COLDSTART_REFRESH: bool = os.environ.get(
    "EXPRESS_SKIP_COLDSTART_REFRESH", ""
).strip().lower() in {"1", "true", "yes", "on"}
