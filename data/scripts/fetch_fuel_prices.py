"""Fetch diesel B7 fuel prices from EPPO with seed CSV fallback.

Attempts to scrape the Thailand Department of Energy Business (EPPO)
petroleum statistics page. On any failure (network, parse, format),
falls back to the pre-scraped seed CSV in data/raw/eppo_diesel_prices.csv.

Usage:
    python data/scripts/fetch_fuel_prices.py
"""

import logging
import shutil
from pathlib import Path

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
