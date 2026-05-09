"""Fetch diesel B7 fuel prices from EPPO with seed CSV fallback.

Attempts to scrape the Thailand Department of Energy Business (EPPO)
petroleum statistics page. On any failure (network, parse, format),
falls back to the pre-scraped seed CSV in data/raw/eppo_diesel_prices.csv.

Also exposes a reusable cold-start refresh API consumed by the FastAPI
backend (Quick 260509-eum):
    - ``is_csv_stale()`` -- timezone-aware (Asia/Bangkok) staleness predicate
    - ``refresh_csv()``  -- skip-if-fresh / scrape-and-write / log-and-continue

Usage:
    python data/scripts/fetch_fuel_prices.py
"""

import logging
import shutil
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Resolve paths relative to this script, not cwd
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent
RAW_DIR = DATA_DIR / "raw"
OUTPUT_PATH = RAW_DIR / "eppo_diesel_prices.csv"
SEED_PATH = RAW_DIR / "eppo_diesel_prices.csv"

EPPO_URL = (
    "https://www.eppo.go.th/index.php/en/en-energystatistics"
    "/en-petroleum-statistic"
)

REQUEST_TIMEOUT = 30  # seconds

# Project timezone -- the data domain is Thailand fuel prices, so the
# "is the CSV current today?" question must be asked in Bangkok time
# even when the host runs in UTC. zoneinfo is stdlib in Python 3.11+
# (project pins 3.11+); no tzdata pip dep needed on macOS/Linux.
BANGKOK_TZ = ZoneInfo("Asia/Bangkok")


def _today_bangkok() -> date:
    """Return today's calendar date in Asia/Bangkok.

    Defined as a module-level seam so tests can monkeypatch the clock
    without poking ``datetime.now``.
    """
    return datetime.now(BANGKOK_TZ).date()


def _scrape_eppo() -> pd.DataFrame:
    """Attempt to scrape EPPO petroleum statistics page.

    Returns:
        DataFrame with columns: date, diesel_b7_price, source

    Raises:
        Exception: On any network, parse, or data format error.
    """
    response = requests.get(EPPO_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Look for downloadable Excel/CSV links on the page
    # EPPO page structure may change; this is a best-effort scrape
    links = soup.find_all("a", href=True)
    excel_links = [
        link["href"]
        for link in links
        if link["href"].endswith((".xlsx", ".xls", ".csv"))
    ]

    if not excel_links:
        raise ValueError(
            "No downloadable data files found on EPPO statistics page"
        )

    # Download the first matching file
    file_url = excel_links[0]
    if not file_url.startswith("http"):
        file_url = f"https://www.eppo.go.th{file_url}"

    file_response = requests.get(file_url, timeout=REQUEST_TIMEOUT)
    file_response.raise_for_status()

    # Parse based on file type
    if file_url.endswith(".csv"):
        from io import StringIO

        df = pd.read_csv(StringIO(file_response.text))
    else:
        from io import BytesIO

        df = pd.read_excel(BytesIO(file_response.content))

    # Normalize columns to expected format
    df = df.rename(
        columns={
            "Date": "date",
            "Diesel B7": "diesel_b7_price",
            "diesel_b7": "diesel_b7_price",
        }
    )
    df["source"] = "eppo"

    required_cols = {"date", "diesel_b7_price", "source"}
    if not required_cols.issubset(set(df.columns)):
        raise ValueError(
            f"Missing required columns. Found: {df.columns.tolist()}, "
            f"need: {required_cols}"
        )

    return df[["date", "diesel_b7_price", "source"]]


def _load_seed_csv() -> pd.DataFrame:
    """Load pre-scraped seed CSV as fallback.

    Returns:
        DataFrame with columns: date, diesel_b7_price, source
    """
    return pd.read_csv(SEED_PATH)


def is_csv_stale(
    csv_path: Path = OUTPUT_PATH,
    today: date | None = None,
) -> bool:
    """Return True iff the CSV's max(date) is strictly older than today.

    D-01 contract:
      - Asia/Bangkok timezone (when ``today`` is None we resolve via
        ``_today_bangkok`` -- never naive ``date.today()``).
      - Strict ``<`` means today's row is fresh (boundary equality
        is NOT stale; clock skew safe -- a future date is also fresh).
      - Missing / empty / corrupt CSV returns True so the cold-start
        path will at least *attempt* a refresh; ``refresh_csv``'s own
        try/except handles the rest per D-03.

    Args:
        csv_path: Path to the CSV; defaults to module ``OUTPUT_PATH``.
        today: Optional override (used by tests). Defaults to
            ``_today_bangkok()``.

    Returns:
        bool -- True when refresh should be attempted.
    """
    if today is None:
        today = _today_bangkok()

    if not csv_path.exists():
        return True

    try:
        df = pd.read_csv(csv_path)
        # Coerce malformed dates to NaT and drop them so a single bad
        # row doesn't poison the whole predicate.
        parsed = pd.to_datetime(df["date"], errors="coerce").dt.date
        parsed = parsed.dropna()
        if parsed.empty:
            return True
        return parsed.max() < today
    except Exception:  # broad: any pandas/IO failure -> force refresh attempt
        return True


def refresh_csv(today: date | None = None) -> bool:
    """Refresh ``OUTPUT_PATH`` from EPPO when stale; log-and-continue on failure.

    D-03 contract:
      - When the CSV is fresh: skip the scrape entirely and return False.
      - When stale: call ``_scrape_eppo`` inside try/except; on success
        write the DataFrame to ``OUTPUT_PATH`` and return True; on any
        exception log a WARNING (with traceback) and return False --
        the existing CSV is left UNTOUCHED so the dashboard renders
        last-known data.

    Note: this wrapper does NOT fall back to ``_load_seed_csv`` -- the
    seed-fallback semantic belongs to the CLI ``main()`` (which is the
    "give me a CSV no matter what" entry). The cold-start contract is
    "refresh if you can, otherwise leave the existing CSV alone".

    Args:
        today: Optional override forwarded to ``is_csv_stale``.

    Returns:
        bool -- True iff a fresh scrape was written to OUTPUT_PATH.
    """
    if not is_csv_stale(OUTPUT_PATH, today):
        logger.info(
            "Fuel CSV is fresh (max date >= today); "
            "skipping cold-start refresh"
        )
        return False

    try:
        df = _scrape_eppo()
    except Exception as exc:
        logger.warning(
            "Cold-start fuel refresh failed: %s; existing CSV untouched",
            exc,
            exc_info=True,
        )
        return False

    df.to_csv(OUTPUT_PATH, index=False)
    logger.info(
        "Cold-start fuel refresh: wrote %d rows to %s",
        len(df),
        OUTPUT_PATH,
    )
    return True


def main() -> None:
    """Fetch fuel prices from EPPO or fall back to seed CSV."""
    try:
        df = _scrape_eppo()
        df.to_csv(OUTPUT_PATH, index=False)
        print(f"Fetched {len(df)} rows from EPPO -> {OUTPUT_PATH}")
    except Exception as e:
        logger.warning("EPPO scrape failed: %s. Using seed CSV fallback.", e)
        df = _load_seed_csv()
        print(f"Using seed CSV fallback ({len(df)} rows)")


if __name__ == "__main__":
    main()
