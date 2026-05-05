"""Environment-based configuration for surcharge calculation (D-09)."""
import os

from dotenv import load_dotenv

# Load .env file if present (development convenience)
load_dotenv()

# Surcharge formula constants
BASELINE_DIESEL_PRICE: float = float(
    os.environ.get("BASELINE_DIESEL_PRICE", "29.94")
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
