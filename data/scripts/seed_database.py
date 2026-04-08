"""Seed SQLite database from CSV files and zone definitions.

Reads rate table CSV, fuel price CSV, and zone definitions JSON,
then loads them into data/express.db as tables: rate_table,
fuel_prices, and zones.

Usage:
    python data/scripts/seed_database.py
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd

# Resolve paths relative to this script to avoid cwd issues
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "express.db"

RATE_TABLE_CSV = RAW_DIR / "express_rate_table.csv"
FUEL_PRICES_CSV = RAW_DIR / "eppo_diesel_prices.csv"
ZONE_DEFINITIONS_JSON = RAW_DIR / "zone_definitions.json"


def seed_rate_table(conn: sqlite3.Connection) -> int:
    """Load rate table CSV into SQLite.

    Args:
        conn: SQLite database connection.

    Returns:
        Number of rows inserted.
    """
    df = pd.read_csv(RATE_TABLE_CSV)
    df.to_sql("rate_table", conn, if_exists="replace", index=False)
    return len(df)


def seed_fuel_prices(conn: sqlite3.Connection) -> int:
    """Load fuel prices CSV into SQLite.

    Args:
        conn: SQLite database connection.

    Returns:
        Number of rows inserted.
    """
    df = pd.read_csv(FUEL_PRICES_CSV)
    df.to_sql("fuel_prices", conn, if_exists="replace", index=False)
    return len(df)


def _seed_zones(conn: sqlite3.Connection) -> int:
    """Load zone definitions JSON into SQLite zones table.

    Args:
        conn: SQLite database connection.

    Returns:
        Number of zones inserted.
    """
    with open(ZONE_DEFINITIONS_JSON, "r") as f:
        zones = json.load(f)

    conn.execute(
        "CREATE TABLE IF NOT EXISTS zones "
        "(zone_id TEXT PRIMARY KEY, name TEXT, provinces TEXT)"
    )
    conn.execute("DELETE FROM zones")

    for zone_id, zone_data in zones.items():
        conn.execute(
            "INSERT INTO zones (zone_id, name, provinces) VALUES (?, ?, ?)",
            (zone_id, zone_data["name"], json.dumps(zone_data["provinces"])),
        )

    conn.commit()
    return len(zones)


def main() -> None:
    """Seed express.db with rate table, fuel prices, and zone data."""
    conn = sqlite3.connect(DB_PATH)

    try:
        rate_count = seed_rate_table(conn)
        fuel_count = seed_fuel_prices(conn)
        zone_count = _seed_zones(conn)
        conn.commit()

        print(
            f"Seeded {rate_count} rate table rows, "
            f"{fuel_count} fuel price rows, "
            f"{zone_count} zones -> {DB_PATH}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
