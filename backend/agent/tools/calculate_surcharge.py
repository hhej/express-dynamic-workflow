"""Pure surcharge calculation function (D-10).

Lives in backend/agent/tools/calculate_surcharge.py.
Phase 2 wraps this as a LangGraph tool.
"""
from __future__ import annotations

from backend.agent.tools.models import SurchargeResult
from backend.config import (
    BASELINE_DIESEL_PRICE,
    SHIPPING_MULTIPLIERS,
    SURCHARGE_CAP,
    SURCHARGE_FLOOR,
)


def calculate_surcharge(
    base_rate: float,
    current_diesel_price: float,
    shipping_type: str,
    traffic_severity: int = 1,
) -> SurchargeResult:
    """Calculate fuel surcharge for a shipment.

    Implements the surcharge formula from docs/architecture.md:
    1. fuel_delta_pct = (current - baseline) / baseline
    2. surcharge_pct = fuel_delta_pct * shipping_multiplier
    3. If bounce: surcharge_pct += traffic_severity * 0.02
    4. Clamp to [SURCHARGE_FLOOR, SURCHARGE_CAP]
    5. surcharge_amount = base_rate * surcharge_pct
    6. total = base_rate + surcharge_amount

    Args:
        base_rate: Base shipping rate in THB from rate table.
        current_diesel_price: Current diesel B7 price in THB/L.
        shipping_type: One of "bounce", "retail_standard", "retail_fast".
        traffic_severity: Traffic severity 1-5 (only affects bounce). Per D-11.

    Returns:
        SurchargeResult with surcharge_pct, surcharge_amount, total, capped.

    Raises:
        ValueError: If shipping_type is invalid or inputs are out of range (D-11).
    """
    # --- Input validation (D-11) ---
    if base_rate <= 0:
        raise ValueError(f"base_rate must be positive, got {base_rate}")

    if shipping_type not in SHIPPING_MULTIPLIERS:
        valid_types = ", ".join(sorted(SHIPPING_MULTIPLIERS.keys()))
        raise ValueError(
            f"Invalid shipping_type '{shipping_type}'. "
            f"Must be one of: {valid_types}"
        )

    if not (1 <= traffic_severity <= 5):
        raise ValueError(
            f"traffic_severity must be 1-5, got {traffic_severity}"
        )

    # --- Surcharge formula ---
    # Step 1: Fuel delta percentage
    fuel_delta_pct = (
        (current_diesel_price - BASELINE_DIESEL_PRICE) / BASELINE_DIESEL_PRICE
    )

    # Step 2: Apply shipping type multiplier
    surcharge_pct = fuel_delta_pct * SHIPPING_MULTIPLIERS[shipping_type]

    # Step 3: Traffic adjustment (bounce only, per CALC-03)
    if shipping_type == "bounce":
        surcharge_pct += traffic_severity * 0.02

    # Step 4: Clamp to [floor, cap] (CALC-04)
    capped = False
    if surcharge_pct > SURCHARGE_CAP:
        surcharge_pct = SURCHARGE_CAP
        capped = True
    elif surcharge_pct < SURCHARGE_FLOOR:
        surcharge_pct = SURCHARGE_FLOOR
        capped = True

    # Step 5-6: Calculate amounts
    surcharge_pct = round(surcharge_pct, 4)
    surcharge_amount = round(base_rate * surcharge_pct, 2)
    total = round(base_rate + surcharge_amount, 2)

    return SurchargeResult(
        surcharge_pct=surcharge_pct,
        surcharge_amount=surcharge_amount,
        total=total,
        capped=capped,
    )
