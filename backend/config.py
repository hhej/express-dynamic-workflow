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
