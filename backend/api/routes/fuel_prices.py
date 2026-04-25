"""GET /api/fuel-prices?days=N (API-04).

Per D-20, reads directly from ``data/raw/eppo_diesel_prices.csv``
rather than querying SQLite -- Phase 1 only seeded the rate_table; the
fuel CSV is the canonical historical source the dashboard chart will
consume in Phase 4.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Query

from backend.api.models import FuelPricePoint

__all__ = ["router"]

router = APIRouter()

# Resolve the CSV path relative to the repo root. This module lives at
# backend/api/routes/fuel_prices.py -- parents[3] of the resolved path
# is the repo root (.../routes -> .../api -> .../backend -> repo).
_CSV_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "raw"
    / "eppo_diesel_prices.csv"
)


@router.get("/api/fuel-prices", response_model=List[FuelPricePoint])
async def fuel_prices(
    days: int = Query(
        30,
        ge=1,
        le=365,
        description="Window in days; clamped to available CSV rows",
    ),
):
    """Return the last ``days`` rows of fuel-price data from the EPPO CSV.

    Filters by ``date >= today - days`` and sorts ascending so the
    Recharts dashboard can plot left-to-right without a re-sort step.
    Returns HTTP 503 if the CSV has not yet been seeded -- the chart
    cannot render without source data and a missing file is a deployment
    issue, not a 404.
    """
    if not _CSV_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Fuel price CSV not seeded: {_CSV_PATH}",
        )

    cutoff: date = date.today() - timedelta(days=days)
    rows: list[FuelPricePoint] = []
    with _CSV_PATH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            except (KeyError, ValueError):
                # Skip malformed rows rather than 500 the whole request.
                continue
            if d < cutoff:
                continue
            rows.append(
                FuelPricePoint(
                    date=r["date"],
                    price=float(r["diesel_b7_price"]),
                    unit="THB/L",
                    source=r.get("source", "eppo"),
                )
            )

    rows.sort(key=lambda x: x.date)
    return rows
