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
import re
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Resolve paths relative to this script, not cwd
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent
RAW_DIR = DATA_DIR / "raw"
OUTPUT_PATH = RAW_DIR / "eppo_diesel_prices.csv"
SEED_PATH = RAW_DIR / "eppo_diesel_prices.csv"

# EPPO renamed the petroleum-statistics menu item between 2026-04-03 and
# 2026-05-09 (Joomla slug changed: ``en-petroleum-statistic`` ->
# ``petroleumprice-statistic``). Pin the new index page for the User-Agent
# probe in tests/observability and pin the P09 (Table 9: Retail Price of
# Petroleum Products in Bangkok) Excel directly -- the static asset path
# under ``/epposite/images/.../Petroleum_Prices/`` has been stable for
# years; the volatile thing is the Joomla index above it.
EPPO_URL = (
    "https://www.eppo.go.th/index.php/en/en-energystatistics"
    "/petroleumprice-statistic"
)
EPPO_P09_URL = (
    "https://www.eppo.go.th/epposite/images/Energy-Statistics"
    "/energyinformation/Energy_Statistics/Petroleum_Prices/P09.xls"
)
# EPPO's "Oil Sharing" daily snapshot. Renders today's Bangkok retail
# prices per station (Diesel HSD B7 included). Source of TODAY's daily
# row -- P09 only updates monthly so it cannot answer "what's the price
# today?" until the month closes. The image-based product label for
# Diesel B7 is ``oil_name6v2.png`` (verified 2026-05-09).
EPPO_OIL_SHARE_URL = (
    "https://www.eppo.go.th/templates/eppo_v15_mixed/eppo_oil"
    "/eppo_oil_gen_new.php"
)
_OIL_SHARE_DIESEL_B7_LABEL = "oil_name6v2.png"

# Pretend to be a real browser; EPPO's Imperva CDN sometimes filters bare
# python-requests UA strings.
EPPO_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 30  # seconds

# P09.xls layout (verified 2026-05-09 against a sheet last saved 2026-05-01):
#   - Single sheet "2003-current", 924 rows x 21 cols
#   - Col 0: row labels -- "<YEAR> (MIN)" or "-<MON> (MIN)" alternating
#            with "(WT.AVG)" / "(MAX)" continuation rows. We capture the
#            most recent year + month and emit a row whenever we see a
#            WT.AVG bucket (the canonical "month average").
#   - Col 8: HSD ** B7 (Diesel B7) per row 4-5 header. Confirmed against
#            historical reference points (e.g. 2025-12 WT.AVG = 30.81 baht
#            matches Nationthailand-reported retail prices).
_P09_DIESEL_B7_COL = 8
_P09_MONTH_LABELS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_P09_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_P09_MONTH_RE = re.compile(
    r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b"
)

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


def _parse_p09_workbook(content: bytes) -> pd.DataFrame:
    """Parse P09.xls (Table 9: Retail Price of Petroleum Products in Bangkok).

    Walks the pivoted layout of the "2003-current" sheet, capturing one
    monthly row per WT.AVG bucket. Out-of-band header / footnote rows are
    ignored automatically because they don't carry a current
    (year, month) pair when WT.AVG is encountered.

    Args:
        content: Raw bytes of the .xls workbook downloaded from EPPO.

    Returns:
        DataFrame with columns ``date`` (YYYY-MM-01 strings),
        ``diesel_b7_price`` (float, baht/litre), ``source`` ("eppo").

    Raises:
        ValueError: If no rows can be extracted (e.g. EPPO changed the
            sheet name or column layout).
    """
    # ``pd.read_excel`` for legacy BIFF .xls requires the ``xlrd`` engine.
    # Pinned in requirements.txt; a missing dep raises ImportError up the
    # call stack, which the cold-start refresh swallows per D-03.
    df_raw = pd.read_excel(
        BytesIO(content),
        header=None,
        sheet_name="2003-current",
        engine="xlrd",
    )

    current_year: int | None = None
    current_month: int | None = None
    rows: list[dict] = []

    for i in range(len(df_raw)):
        c0 = df_raw.iat[i, 0]
        c1 = df_raw.iat[i, 1] if df_raw.shape[1] > 1 else None
        s0 = "" if pd.isna(c0) else str(c0).strip()
        s1 = "" if pd.isna(c1) else str(c1).strip()

        # Year detection: matches both the per-year header row (e.g.
        # "2026 (MIN)") AND the year-as-string (e.g. "2003").
        m_year = _P09_YEAR_RE.search(s0)
        if m_year:
            current_year = int(m_year.group(1))
            current_month = None  # reset; we're inside the year header

        # Month detection: rows like "-JAN (MIN)" or "-MAR (MIN)".
        m_month = _P09_MONTH_RE.search(s0.upper())
        if m_month:
            current_month = _P09_MONTH_LABELS[m_month.group(1)]

        # WT.AVG bucket label can land in col 0 OR col 1 (the workbook
        # has been edited inconsistently across decades).
        is_wtavg = (
            "WT.AVG" in s0.upper().replace(" ", "")
            or "WT.AVG" in s1.upper().replace(" ", "")
        )
        if not (is_wtavg and current_year and current_month):
            continue

        price = df_raw.iat[i, _P09_DIESEL_B7_COL]
        if not pd.notna(price) or not isinstance(price, (int, float)):
            continue

        rows.append(
            {
                "date": f"{current_year:04d}-{current_month:02d}-01",
                "diesel_b7_price": round(float(price), 4),
                "source": "eppo",
            }
        )

    if not rows:
        raise ValueError(
            "P09.xls parsed but no diesel B7 monthly rows extracted -- "
            "EPPO may have changed the sheet name or column layout"
        )

    return pd.DataFrame(rows, columns=["date", "diesel_b7_price", "source"])


def _scrape_oil_share_today() -> float | None:
    """Scrape today's diesel B7 retail price from EPPO's oil-share snapshot.

    EPPO's "Oil Sharing" page renders the current day's Bangkok retail
    prices per station (PTT, Bangchak, Shell, etc). The Diesel B7 row is
    identified by an image label (``oil_name6v2.png``) since the table
    headers are PNGs. We pick the FIRST station's price (typically PTT)
    -- all major stations within Bangkok publish the same retail price
    for B7 because of the regulated structure, so the choice of station
    doesn't change the value.

    Returns:
        The diesel B7 price (baht/litre) as a float, OR ``None`` when the
        page cannot be parsed (label not found, no numeric prices, etc.).
        Caller decides whether ``None`` is acceptable -- this function
        does NOT raise on parse failure so it can be used as a soft
        secondary source alongside P09.

    Raises:
        requests.exceptions.RequestException: Only on network failure.
            (Parse failures return ``None`` instead.)
    """
    headers = {"User-Agent": EPPO_USER_AGENT}
    response = requests.get(
        EPPO_OIL_SHARE_URL, timeout=REQUEST_TIMEOUT, headers=headers
    )
    response.raise_for_status()

    html = response.text
    label_idx = html.find(_OIL_SHARE_DIESEL_B7_LABEL)
    if label_idx == -1:
        logger.warning(
            "Oil-share page parsed but %s label not found; EPPO may have "
            "renamed the diesel B7 label image",
            _OIL_SHARE_DIESEL_B7_LABEL,
        )
        return None

    # The label sits inside an ``<img>`` whose enclosing div is followed
    # by a sibling ``<div class='oil_price_colum'>NN.NN</div>`` per
    # station. Grab the first numeric price after the label, ignoring
    # commented-out blocks (HTML comments around obsolete columns).
    after = html[label_idx:]
    # Strip HTML comments so we don't trip on ``<!-- ... -->`` price stubs.
    after = re.sub(r"<!--.*?-->", "", after, flags=re.DOTALL)
    price_match = re.search(
        r"oil_price_colum'>\s*([0-9]+\.[0-9]+)\s*<",
        after,
    )
    if not price_match:
        logger.warning(
            "Oil-share page parsed but no numeric diesel B7 price found "
            "after the %s label",
            _OIL_SHARE_DIESEL_B7_LABEL,
        )
        return None

    return float(price_match.group(1))


def _scrape_eppo() -> pd.DataFrame:
    """Scrape EPPO Bangkok retail diesel B7 and merge with seed CSV.

    Combines two EPPO sources to fill both gaps:

      1. **Table 9 / P09.xls** (monthly Bangkok retail aggregates) --
         provides multi-month historical depth for any month newer than
         the seed CSV's max date.
      2. **Oil-Sharing daily snapshot** -- provides TODAY's daily price
         (Asia/Bangkok), which P09 cannot supply until the month closes.

    The output is the union of:
      - the existing OUTPUT_PATH / SEED_PATH CSV (preserves the rich
        daily history that ships with the repo), AND
      - P09 monthly rows whose date is strictly AFTER the seed CSV's max,
      - today's daily snapshot (when available), keyed by today's
        Bangkok-TZ date.

    Failure semantics:
      - P09 is the primary source. Its network/parse failure raises (the
        caller's try/except will swallow per D-03).
      - The daily snapshot is best-effort. If it fails, we still return
        the P09-merged frame and log a warning -- the caller's stale
        check (D-01) will see whatever max date P09 supplied.

    Returns:
        DataFrame with columns ``date``, ``diesel_b7_price``, ``source``.
        Sorted ascending by date; no duplicates.

    Raises:
        Exception: On any network, parse, or data format error from the
            P09 download. Daily-snapshot failures are logged and swallowed.
    """
    headers = {"User-Agent": EPPO_USER_AGENT}
    file_response = requests.get(
        EPPO_P09_URL, timeout=REQUEST_TIMEOUT, headers=headers
    )
    file_response.raise_for_status()

    fresh = _parse_p09_workbook(file_response.content)

    # Best-effort daily snapshot. Catch broad Exception so a parse change
    # on the oil-share page does NOT take down the primary refresh path.
    try:
        today_price = _scrape_oil_share_today()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Oil-share daily snapshot failed: %s", exc)
        today_price = None

    if today_price is not None:
        today_str = _today_bangkok().isoformat()
        fresh = pd.concat(
            [
                fresh,
                pd.DataFrame(
                    [
                        {
                            "date": today_str,
                            "diesel_b7_price": round(today_price, 4),
                            "source": "eppo",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    # Merge with existing seed/CSV, preserving daily-resolution history.
    # When the seed file is missing (e.g. fresh checkout of a future repo
    # state), the scraped data is the entire output.
    if SEED_PATH.exists():
        try:
            existing = pd.read_csv(SEED_PATH)
        except Exception as exc:
            logger.warning(
                "Existing fuel CSV %s unreadable (%s); using EPPO data only",
                SEED_PATH,
                exc,
            )
            existing = pd.DataFrame(
                columns=["date", "diesel_b7_price", "source"]
            )
    else:
        existing = pd.DataFrame(columns=["date", "diesel_b7_price", "source"])

    if existing.empty:
        merged = fresh.drop_duplicates(subset=["date"], keep="last")
        merged = merged.sort_values("date").reset_index(drop=True)
        return merged[["date", "diesel_b7_price", "source"]]

    # Only append fresh rows whose date is STRICTLY after the seed max --
    # this keeps the daily seed dense and only fills the gap with monthly
    # points + today's daily snapshot where no seed daily data exists.
    existing_max_date = pd.to_datetime(
        existing["date"], errors="coerce"
    ).max()
    fresh["_dt"] = pd.to_datetime(fresh["date"], errors="coerce")
    new_rows = fresh[fresh["_dt"] > existing_max_date].drop(columns=["_dt"])

    merged = pd.concat([existing, new_rows], ignore_index=True)
    # Defensive dedup on date (keep last = freshest scrape on conflict
    # within the appended block; seed rows are upstream and untouched
    # because their dates are <= existing_max_date by construction).
    merged = merged.drop_duplicates(subset=["date"], keep="last")
    merged = merged.sort_values("date").reset_index(drop=True)
    return merged[["date", "diesel_b7_price", "source"]]


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
