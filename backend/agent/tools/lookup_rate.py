"""TOOL-03: lookup_rate — SQLite rate-table lookup with half-open weight tiers.

Phase 999.9 (D-05): signature extended to (shipping_type, origin_zone,
dest_zone, weight_kg). origin_zone is derived from origin_hub_id at the
caller site (pricing_agent_node) via origin_zone_for(hub_id) from
backend/agent/tools/hubs.py.

Implements D-13 (half-open intervals [min, max)), C-02 (sentinel
weight_max_kg=999 rather than NULL), and D-14 (ValueError on miss) —
UNCHANGED from Phase 1.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from backend.agent.tools.models import RateResult
from backend.config import DATABASE_PATH

__all__ = ["lookup_rate"]

logger = logging.getLogger(__name__)

_DB_PATH = Path(DATABASE_PATH)


def lookup_rate(
    shipping_type: str,
    origin_zone: str,
    dest_zone: str,
    weight_kg: float,
) -> RateResult:
    """Look up the base rate for a shipment from rate_table (Phase 999.9 D-05).

    Uses half-open weight intervals [weight_min_kg, weight_max_kg) per D-13.
    The top tier (50+ kg) stores weight_max_kg = 999 as sentinel (C-02);
    weight_kg >= 999 raises ValueError.

    Args:
        shipping_type: "bounce" | "retail_standard" | "retail_fast".
        origin_zone: "central-1" | "central-2" | "central-3" — derived
            from origin hub_id via origin_zone_for(hub_id).
        dest_zone: "central-1" | "central-2" | "central-3" — destination
            zone (RouteData.zone, populated by route_agent_node).
        weight_kg: Positive float; valid range (0, 999).

    Returns:
        RateResult(base_rate, currency="THB", rate_tier=<min>-<max>kg or <min>+kg).

    Raises:
        ValueError: On non-positive weight, unknown shipping_type/zones,
            or weight outside any tier (including >= 999).
    """
    if weight_kg <= 0:
        raise ValueError(
            f"weight_kg must be positive, got {weight_kg}"
        )

    query = """
        SELECT base_rate_thb, weight_min_kg, weight_max_kg
        FROM rate_table
        WHERE shipping_type = ?
          AND origin_zone = ?
          AND dest_zone = ?
          AND weight_min_kg <= ?
          AND ? < weight_max_kg
        LIMIT 1
    """
    with sqlite3.connect(_DB_PATH) as conn:
        row = conn.execute(
            query,
            (shipping_type, origin_zone, dest_zone, weight_kg, weight_kg),
        ).fetchone()

    if row is None:
        raise ValueError(
            f"No rate found for shipping_type={shipping_type!r}, "
            f"origin_zone={origin_zone!r}, dest_zone={dest_zone!r}, "
            f"weight_kg={weight_kg}"
        )

    base_rate, wmin, wmax = row
    tier = f"{wmin}-{wmax}kg" if wmax < 999 else f"{wmin}+kg"
    logger.info(
        "lookup_rate: %s/%s->%s/%.2fkg -> base_rate=%s tier=%s",
        shipping_type, origin_zone, dest_zone, weight_kg, base_rate, tier,
    )
    return RateResult(
        base_rate=float(base_rate),
        currency="THB",
        rate_tier=tier,
    )
