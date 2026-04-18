"""TOOL-01: fetch_fuel_price -- 3-level fallback chain (D-01, D-02, D-03, D-04).

Level 1: live EPPO scrape with 2 retries, exponential backoff (1s, 2s).
         STUBBED with NotImplementedError until live selectors are captured
         (see Open Question 2 in 02-RESEARCH.md and Phase 5 polish).
Level 2: latest row of data/raw/eppo_diesel_prices.csv (Phase 1 seed).
Level 3: BASELINE_DIESEL_PRICE constant (never fails).

This tool NEVER raises -- the baseline fallback is always reachable.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
import pandas as pd

from backend.agent.tools.models import FuelData
from backend.config import BASELINE_DIESEL_PRICE, FUEL_FETCH_TIMEOUT

__all__ = ["fetch_fuel_price"]

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FUEL_CSV = _REPO_ROOT / "data" / "raw" / "eppo_diesel_prices.csv"
_EPPO_URL = (
    "https://www.eppo.go.th/index.php/en/en-energystatistics"
    "/en-petroleum-statistic"
)


def fetch_fuel_price() -> FuelData:
    """Return current diesel B7 price via a 3-level fallback chain.

    Returns:
        FuelData with source in {'eppo_live', 'eppo_cached_csv',
        'hardcoded_baseline'}. Never raises.
    """
    # Level 1: live scrape with exponential backoff (D-04)
    for attempt, backoff in enumerate([0, 1, 2]):
        if backoff:
            time.sleep(backoff)
        try:
            price, date = _scrape_eppo_live()
            logger.info("fuel: level 1 (eppo_live) succeeded")
            return _build_fuel_data(price, date, "eppo_live")
        except (httpx.HTTPError, ValueError, NotImplementedError) as e:
            logger.warning(
                "fuel: level 1 attempt %d failed: %s", attempt + 1, e
            )

    # Level 2: cached CSV
    try:
        price, date = _read_cached_csv()
        logger.info("fuel: level 2 (eppo_cached_csv) succeeded")
        return _build_fuel_data(price, date, "eppo_cached_csv")
    except (FileNotFoundError, pd.errors.EmptyDataError, ValueError) as e:
        logger.warning("fuel: level 2 CSV fallback failed: %s", e)

    # Level 3: hardcoded baseline -- always works
    logger.info("fuel: level 3 (hardcoded_baseline) serving default")
    today = pd.Timestamp.utcnow().strftime("%Y-%m-%d")
    return _build_fuel_data(BASELINE_DIESEL_PRICE, today, "hardcoded_baseline")


def _build_fuel_data(price: float, date: str, source: str) -> FuelData:
    """Assemble a FuelData with rounded price and delta_pct (D-03 source values)."""
    price = round(float(price), 2)
    delta = round(
        (price - BASELINE_DIESEL_PRICE) / BASELINE_DIESEL_PRICE, 4
    )
    return FuelData(
        price=price,
        date=date,
        unit="THB/L",
        source=source,
        baseline=BASELINE_DIESEL_PRICE,
        delta_pct=delta,
    )


def _scrape_eppo_live() -> tuple[float, str]:
    """Level 1 live scrape.

    Stubbed per Open Question 2 -- selectors need to be captured from live
    EPPO HTML before this can be implemented. The 3-level chain is designed
    so the CSV fallback makes this non-blocking for Phase 2.

    Raises:
        NotImplementedError: Always, until Phase 5 polish.
    """
    # The live fetch body is left as a seam for when selectors are captured:
    # resp = httpx.get(_EPPO_URL, timeout=FUEL_FETCH_TIMEOUT)
    # resp.raise_for_status()
    # soup = BeautifulSoup(resp.text, "html.parser")
    # ...
    raise NotImplementedError("scrape selectors: capture live HTML first")


def _read_cached_csv() -> tuple[float, str]:
    """Level 2: latest row of data/raw/eppo_diesel_prices.csv.

    Raises:
        FileNotFoundError: CSV missing.
        pd.errors.EmptyDataError: CSV has no data rows.
        ValueError: CSV has header only.
    """
    df = pd.read_csv(_FUEL_CSV)
    if df.empty:
        raise ValueError("fuel price CSV is empty (header only)")
    latest = df.sort_values("date").iloc[-1]
    return float(latest["diesel_b7_price"]), str(latest["date"])
